"""Kontrol → tek deneme → hepsi akışı. Instagram'a güvenli ve yavaş davranır."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from . import config
from .instagram_api import ApiError, LoginRequired, NetworkError, RateLimited, Status
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
    reason: str | None = None  # rate_limited | login | network | user | trial_failed


@dataclass
class CheckSummary:
    pending: int
    accepted: int
    no_request: int
    not_found: int


class _Stop(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class Runner:
    def __init__(self, client, store: Store, progress: Progress, emit: Callable[[Event], None],
                 sleep: Callable[[float], None], now: Callable[[], float],
                 rand: Callable[[float, float], float], stop: threading.Event):
        self.client, self.store, self.p = client, store, progress
        self.emit, self._sleep, self.now, self.rand, self.stop = emit, sleep, now, rand, stop

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
                self._sleep(backoff[attempt])

    def _record(self, u: str, outcome: Outcome) -> None:
        self.p.results[u] = outcome
        self.store.save(self.p)

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
                try:
                    status, _ = self._retry(lambda: self.client.lookup(u))
                except ApiError:
                    self._record(u, Outcome.FAILED)
                    continue
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
                            no_request=vals.count(Outcome.NO_REQUEST), not_found=vals.count(Outcome.NOT_FOUND))

    # ---- geri çekme --------------------------------------------------------
    def _respect_hourly_cap(self) -> None:
        cutoff = self.now() - 3600
        self.p.cancel_times = [t for t in self.p.cancel_times if t > cutoff]
        if len(self.p.cancel_times) >= config.MAX_CANCELS_PER_HOUR:
            wait = self.p.cancel_times[0] + 3600 - self.now() + 1
            self.emit(self._event("waiting", seconds=wait))
            self._wait(wait)

    def _process(self, u: str) -> tuple[Outcome, bool]:
        """Bir kişiyi işler. (sonuç, geri çekme çağrısı yapıldı mı) döner."""
        try:
            status, uid = self._retry(lambda: self.client.lookup(u))
        except ApiError:
            self._record(u, Outcome.FAILED)
            return Outcome.FAILED, False
        if status is not Status.PENDING:
            self._record(u, _NON_PENDING[status])
            return _NON_PENDING[status], False
        self._respect_hourly_cap()
        # Taze kontrol PENDING dedi: hemen geri çek. Buradan sonra yeniden kontrol bitene
        # kadar durdurma isteğine bakılmaz.
        try:
            self._retry(lambda: self.client.cancel(uid))
        except ApiError:
            self._record(u, Outcome.FAILED)
            return Outcome.FAILED, True
        self.p.cancel_times.append(self.now())
        self.store.save(self.p)
        try:
            after, _ = self._retry(lambda: self.client.lookup(u))
        except ApiError:
            after = Status.PENDING
        outcome = Outcome.FAILED if after in (Status.PENDING, Status.FOLLOWING) else Outcome.CANCELLED
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
