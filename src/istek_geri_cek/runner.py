"""Kontrol → tek deneme → hepsi akışı. Instagram'a güvenli ve yavaş davranır."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from . import config
from .instagram_api import ApiError, LoginRequired, NetworkError, RateLimited, Status, UnexpectedResponse
from .store import Outcome, Progress, Store

_NON_PENDING = {
    Status.FOLLOWING: Outcome.ACCEPTED,
    Status.NONE: Outcome.NO_REQUEST,
    Status.NOT_FOUND: Outcome.NOT_FOUND,
}


@dataclass
class Event:
    kind: str  # checking | checked | trial_ok | progress | waiting | done | stopped
    done: int = 0
    total: int = 0
    username: str | None = None
    seconds: float | None = None
    reason: str | None = None  # rate_limited | login | network | user | trial_failed | unexpected


@dataclass
class CheckSummary:
    pending: int
    accepted: int
    no_request: int
    not_found: int
    failed: int = 0


class _Stop(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class Runner:
    def __init__(self, client, store: Store, progress: Progress, emit: Callable[[Event], None],
                 sleep: Callable[[float], None], now: Callable[[], float],
                 rand: Callable[[float, float], float], stop: threading.Event):
        self.client, self.store, self.p = client, store, progress
        self.emit, self._sleep, self.now, self.rand, self.stop = emit, sleep, now, rand, stop
        self._api_error_streak: list[str] = []

    # ---- yardımcılar -------------------------------------------------------
    def _event(self, kind: str, **kw) -> Event:
        return Event(kind, done=len(self.p.results), total=len(self.p.usernames), **kw)

    def _wait(self, seconds: float) -> None:
        remaining = seconds
        while remaining > 0:
            if self.stop.is_set():
                raise _Stop("user")
            step = min(1.0, remaining)
            self._sleep(step)
            remaining -= step

    def _retry(self, fn):
        backoff = config.NETWORK_BACKOFF
        for attempt in range(len(backoff) + 1):
            try:
                return fn()
            except NetworkError:
                if attempt == len(backoff):
                    raise
                self.emit(self._event("waiting", seconds=backoff[attempt]))
                self._wait(backoff[attempt])

    def _record(self, u: str, outcome: Outcome) -> None:
        self.p.results[u] = outcome
        self.store.save(self.p)

    def _lookup(self, u: str):
        """Taze durum sorgusu. Tek kişilik 4xx → FAILED; art arda 3 tane → sistemik, durdur."""
        try:
            result = self._retry(lambda: self.client.lookup(u))
        except ApiError:
            self._record(u, Outcome.FAILED)
            self._api_error_streak.append(u)
            if len(self._api_error_streak) >= 3:
                for name in self._api_error_streak:
                    self.p.results.pop(name, None)
                raise UnexpectedResponse("art arda 3 ApiError")
            return None
        self._api_error_streak.clear()
        return result

    def _guarded(self, body) -> bool:
        """body() çalıştırır; durdurma sebeplerini olaya çevirir. Tamamlandıysa True."""
        try:
            body()
            return True
        except RateLimited:
            reason = "rate_limited"
        except LoginRequired:
            reason = "login"
        except NetworkError:
            reason = "network"
        except UnexpectedResponse:
            reason = "unexpected"
        except _Stop as s:
            reason = s.reason
        self.store.save(self.p)
        self.emit(self._event("stopped", reason=reason))
        return False

    # ---- kontrol (hiçbir şeyi değiştirmez) ---------------------------------
    def check(self) -> CheckSummary | None:
        def body():
            todo = [u for u in self.store.pending_work(self.p) if u not in self.p.checked]
            for i, u in enumerate(todo):
                if self.stop.is_set():
                    raise _Stop("user")
                self.emit(Event("checking", done=i, total=len(todo), username=u))
                found = self._lookup(u)
                if found is None:
                    continue
                status, _ = found
                self.p.checked[u] = status.name
                if status in _NON_PENDING:
                    self.p.results[u] = _NON_PENDING[status]
                self.store.save(self.p)
                if i < len(todo) - 1:
                    self._wait(self.rand(*config.LOOKUP_DELAY))

        if not self._guarded(body):
            return None
        s = self.summary()
        self.emit(self._event("checked"))
        return s

    def summary(self) -> CheckSummary:
        r = self.p.results
        vals = list(r.values())
        pending = sum(1 for u, st in self.p.checked.items() if st == Status.PENDING.name and u not in r)
        return CheckSummary(pending=pending, accepted=vals.count(Outcome.ACCEPTED),
                            no_request=vals.count(Outcome.NO_REQUEST), not_found=vals.count(Outcome.NOT_FOUND),
                            failed=vals.count(Outcome.FAILED))

    # ---- geri çekme --------------------------------------------------------
    def _respect_hourly_cap(self) -> None:
        cutoff = self.now() - 3600
        self.p.cancel_times = [t for t in self.p.cancel_times if t > cutoff]
        if len(self.p.cancel_times) >= config.MAX_CANCELS_PER_HOUR:
            wait = self.p.cancel_times[0] + 3600 - self.now() + 1
            self.emit(self._event("waiting", seconds=wait))
            self._wait(wait)

    def _process(self, u: str) -> tuple[Outcome, bool]:
        """Bir kişiyi işler. (sonuç, geri çekme çağrısı yapıldı mı) döner.

        Kural: geri çekme çağrısı YALNIZCA araya hiçbir bekleme girmeden yapılan taze bir
        PENDING sorgusunun hemen ardından gönderilir. Geri çekme ağ hatası verirse körlemesine
        tekrarlanmaz; beklenir ve sorgu + geri çekme çifti baştan yapılır.
        """
        backoff = config.NETWORK_BACKOFF
        for attempt in range(len(backoff) + 1):
            self._respect_hourly_cap()
            found = self._lookup(u)
            if found is None:
                return Outcome.FAILED, False
            status, uid = found
            if status is not Status.PENDING:
                if attempt > 0 and status is Status.NONE:
                    # Önceki geri çekme isteği ağ hatasına rağmen Instagram'a ulaşmış.
                    self.p.cancel_times.append(self.now())
                    self._record(u, Outcome.CANCELLED)
                    return Outcome.CANCELLED, True
                self._record(u, _NON_PENDING[status])
                return _NON_PENDING[status], attempt > 0
            try:
                self.client.cancel(uid)
                break
            except ApiError:
                self._record(u, Outcome.FAILED)
                return Outcome.FAILED, True
            except NetworkError:
                if attempt == len(backoff):
                    raise
                self.emit(self._event("waiting", seconds=backoff[attempt]))
                self._wait(backoff[attempt])
        # Buradan sonra yeniden kontrol bitene kadar durdurma isteğine bakılmaz.
        self.p.cancel_times.append(self.now())
        self.store.save(self.p)
        try:
            found = self._lookup(u)
        except UnexpectedResponse:
            found = None
        after = found[0] if found else None
        outcome = Outcome.CANCELLED if after is Status.NONE else Outcome.FAILED
        self._record(u, outcome)
        return outcome, True

    def run(self) -> None:
        def body():
            for u in self.store.pending_work(self.p):
                if self.stop.is_set():
                    raise _Stop("user")
                self.emit(self._event("progress", username=u))
                outcome, cancelled = self._process(u)
                if cancelled and not self.p.trial_done:
                    if outcome is Outcome.FAILED:
                        raise _Stop("trial_failed")
                    self.p.trial_done = True
                    self.store.save(self.p)
                    self.emit(self._event("trial_ok", username=u))
                self.emit(self._event("progress"))
                if self.store.pending_work(self.p):
                    delay = config.CANCEL_DELAY if cancelled else config.LOOKUP_DELAY
                    self._wait(self.rand(*delay))
            self.emit(self._event("done"))

        self._guarded(body)
