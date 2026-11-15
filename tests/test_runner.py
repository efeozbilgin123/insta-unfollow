import threading

import pytest

from istek_geri_cek import config
from istek_geri_cek.instagram_api import ApiError, LoginRequired, NetworkError, RateLimited, Status
from istek_geri_cek.runner import CheckSummary, Runner
from istek_geri_cek.store import Outcome, Progress, Store

P, F, N, X = Status.PENDING, Status.FOLLOWING, Status.NONE, Status.NOT_FOUND


class Clock:
    def __init__(self):
        self.t = 1_000_000.0
        self.sleeps = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class FakeClient:
    """statuses[u] is a list consumed one lookup at a time (last one repeats)."""

    def __init__(self, statuses, clock, lookup_errors=None, cancel_errors=None, on_cancel=None):
        self.statuses = {u: list(v) for u, v in statuses.items()}
        self.clock = clock
        self.lookup_errors = lookup_errors or {}   # u -> list of exceptions to raise first
        self.cancel_errors = cancel_errors or {}
        self.on_cancel = on_cancel
        self.lookups, self.cancels, self.cancel_at = [], [], []

    def lookup(self, u):
        self.lookups.append(u)
        errs = self.lookup_errors.get(u)
        if errs:
            raise errs.pop(0)
        seq = self.statuses[u]
        s = seq.pop(0) if len(seq) > 1 else seq[0]
        return s, (None if s is X else "id_" + u)

    def self_check(self, username):
        return "id_self"

    def cancel(self, uid):
        u = uid[3:]
        errs = self.cancel_errors.get(u)
        if errs:
            raise errs.pop(0)
        self.cancels.append(u)
        self.cancel_at.append(self.clock.t)
        if self.on_cancel:
            self.on_cancel(u)


def make(tmp_path, statuses, users=None, **kw):
    clock = Clock()
    client = FakeClient(statuses, clock, **kw)
    store = Store(tmp_path)
    prog = Progress(account="efe", usernames=list(users or statuses))
    events = []
    stop = threading.Event()
    r = Runner(client, store, prog, emit=events.append, sleep=clock.sleep, now=clock.now,
               rand=lambda a, b: a, stop=stop)
    return r, client, store, prog, events, clock, stop


def test_check_makes_no_cancels(tmp_path):
    r, c, *_ = make(tmp_path, {"a": [P], "b": [F], "c": [X]})
    assert r.check() == CheckSummary(pending=1, accepted=1, no_request=0, not_found=1)
    assert c.cancels == []


def test_check_records_final_outcomes_for_non_pending(tmp_path):
    r, c, store, prog, *_ = make(tmp_path, {"a": [P], "b": [F], "c": [X], "d": [N]})
    r.check()
    assert prog.results == {"b": Outcome.ACCEPTED, "c": Outcome.NOT_FOUND, "d": Outcome.NO_REQUEST}
    assert store.load("efe").results == prog.results


def test_accepted_between_check_and_run_is_not_cancelled(tmp_path):
    r, c, _, prog, *_ = make(tmp_path, {"a": [P, F]})
    r.check()
    r.run()
    assert c.cancels == []
    assert prog.results["a"] is Outcome.ACCEPTED


def test_cancel_verified(tmp_path):
    r, c, _, prog, events, *_ = make(tmp_path, {"a": [P, P, N], "b": [P, P, N]})
    r.check()
    r.run()
    assert c.cancels == ["a", "b"]
    assert prog.results == {"a": Outcome.CANCELLED, "b": Outcome.CANCELLED}
    assert prog.trial_done
    kinds = [e.kind for e in events]
    assert "trial_ok" in kinds and kinds[-1] == "done"


def test_cancel_not_taking_is_failed_and_stops_trial(tmp_path):
    r, c, _, prog, events, *_ = make(tmp_path, {"a": [P], "b": [P]})
    r.run()
    assert c.cancels == ["a"]
    assert prog.results == {"a": Outcome.FAILED}
    assert not prog.trial_done
    assert (events[-1].kind, events[-1].reason) == ("stopped", "trial_failed")


def test_following_after_cancel_is_failed(tmp_path):
    r, c, _, prog, *_ = make(tmp_path, {"a": [P, F]})
    prog.trial_done = True
    r.run()
    assert prog.results["a"] is Outcome.FAILED


def test_trial_skips_non_pending_users(tmp_path):
    r, c, _, prog, events, *_ = make(tmp_path, {"a": [F], "b": [P, N]})
    r.run()
    assert c.cancels == ["b"]
    assert prog.trial_done


def test_hourly_cap(tmp_path):
    users = {f"u{i}": [P, N] for i in range(61)}
    r, c, _, prog, events, clock, _ = make(tmp_path, users)
    r.run()
    assert len(c.cancels) == 61
    assert c.cancel_at[60] - c.cancel_at[0] >= 3600
    assert any(e.kind == "waiting" for e in events)


def test_delay_between_cancels_in_range(tmp_path):
    users = {f"u{i}": [P, N] for i in range(5)}
    r, c, *_ = make(tmp_path, users)
    r.run()
    gaps = [b - a for a, b in zip(c.cancel_at, c.cancel_at[1:])]
    lo, hi = config.CANCEL_DELAY
    assert all(lo <= g <= hi + 10 for g in gaps), gaps


def test_rate_limited_stops_and_saves(tmp_path):
    r, c, store, prog, events, *_ = make(tmp_path, {"a": [P, N], "b": [P, N]},
                                         cancel_errors={"b": [RateLimited("x")]})
    r.run()
    saved = store.load("efe")
    assert saved.results == {"a": Outcome.CANCELLED}
    assert (events[-1].kind, events[-1].reason) == ("stopped", "rate_limited")


def test_login_required_stops_and_resume_skips_done(tmp_path):
    statuses = {"u1": [P, N], "u2": [P, N], "u3": [P, N]}
    r, c, store, prog, events, clock, stop = make(tmp_path, statuses,
                                                  lookup_errors={"u3": [LoginRequired("x")]})
    r.run()
    assert (events[-1].kind, events[-1].reason) == ("stopped", "login")
    reloaded = store.load("efe")
    c.lookups.clear()
    r2 = Runner(c, store, reloaded, emit=events.append, sleep=clock.sleep, now=clock.now,
                rand=lambda a, b: a, stop=stop)
    r2.run()
    assert "u1" not in c.lookups and "u2" not in c.lookups
    assert reloaded.results["u3"] is Outcome.CANCELLED


def test_network_retries_then_stops(tmp_path):
    r, c, _, prog, events, clock, _ = make(tmp_path, {"a": [P]},
                                           lookup_errors={"a": [NetworkError()] * 4})
    r.run()
    waits = [e.seconds for e in events if e.kind == "waiting"]
    assert waits == list(config.NETWORK_BACKOFF)
    assert sum(clock.sleeps) == sum(config.NETWORK_BACKOFF)
    assert (events[-1].kind, events[-1].reason) == ("stopped", "network")
    assert prog.results == {}


def test_network_recovers_within_retries(tmp_path):
    r, c, _, prog, *_ = make(tmp_path, {"a": [P, N]}, lookup_errors={"a": [NetworkError()]})
    r.run()
    assert prog.results["a"] is Outcome.CANCELLED


def test_api_error_marks_user_failed_and_continues(tmp_path):
    r, c, _, prog, *_ = make(tmp_path, {"a": [F], "b": [P, N], "c": [P, N]},
                             lookup_errors={"c": [ApiError("400")]})
    r.run()
    assert prog.results["c"] is Outcome.FAILED
    assert prog.results["b"] is Outcome.CANCELLED


def test_stop_event_never_between_cancel_and_recheck(tmp_path):
    holder = {}
    r, c, _, prog, events, clock, stop = make(tmp_path, {"a": [P, N], "b": [P, N]},
                                              on_cancel=lambda u: holder["stop"].set())
    holder["stop"] = stop
    r.run()
    assert prog.results == {"a": Outcome.CANCELLED}
    assert c.cancels == ["a"]
    assert (events[-1].kind, events[-1].reason) == ("stopped", "user")


# ---- final review fixes ----------------------------------------------------
from istek_geri_cek.instagram_api import UnexpectedResponse


class TimedClient(FakeClient):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.lookup_at = []

    def lookup(self, u):
        self.lookup_at.append((u, self.clock.t))
        return super().lookup(u)


def test_every_cancel_immediately_follows_a_fresh_lookup(tmp_path):
    """C1: the hourly-cap wait must not sit between the PENDING lookup and the cancel."""
    clock = Clock()
    users = {f"u{i}": [P, N] for i in range(62)}
    client = TimedClient(users, clock)
    prog = Progress(account="efe", usernames=list(users))
    events = []
    Runner(client, Store(tmp_path), prog, emit=events.append, sleep=clock.sleep, now=clock.now,
           rand=lambda a, b: a, stop=threading.Event()).run()
    assert any(e.kind == "waiting" for e in events)
    for u, t in zip(client.cancels, client.cancel_at):
        last = [lt for lu, lt in client.lookup_at if lu == u and lt <= t][-1]
        assert last == t, (u, last, t)


def test_cancel_network_error_is_not_blindly_retried(tmp_path):
    """C2: after a failed cancel POST, re-lookup first; an accepted follow must not be cancelled."""
    r, c, _, prog, *_ = make(tmp_path, {"a": [P, F]}, cancel_errors={"a": [NetworkError()]})
    r.run()
    assert c.cancels == []
    assert prog.results["a"] is Outcome.ACCEPTED


def test_cancel_network_error_retries_with_fresh_lookup(tmp_path):
    r, c, _, prog, *_ = make(tmp_path, {"a": [P, P, N]}, cancel_errors={"a": [NetworkError()]})
    r.run()
    assert c.cancels == ["a"]
    assert prog.results["a"] is Outcome.CANCELLED


def test_unexpected_response_stops_and_records_nothing(tmp_path):
    """C3"""
    r, c, _, prog, events, *_ = make(tmp_path, {"a": [P]}, lookup_errors={"a": [UnexpectedResponse("x")]})
    r.check()
    assert prog.results == {} and prog.checked == {}
    assert (events[-1].kind, events[-1].reason) == ("stopped", "unexpected")


def test_post_cancel_not_found_is_failed(tmp_path):
    """C3: only an exact NONE after cancel counts as CANCELLED (trial must not pass on garbage)."""
    r, c, _, prog, events, *_ = make(tmp_path, {"a": [P, X]})
    r.run()
    assert prog.results["a"] is Outcome.FAILED
    assert (events[-1].kind, events[-1].reason) == ("stopped", "trial_failed")


def test_three_consecutive_api_errors_stop_without_final_results(tmp_path):
    """I2: a systemic 4xx must not mark everyone FAILED and end with 'nothing to do'."""
    errs = {u: [ApiError("400")] for u in "abc"}
    r, c, _, prog, events, *_ = make(tmp_path, {"a": [P], "b": [P], "c": [P], "d": [P]}, lookup_errors=errs)
    assert r.check() is None
    assert prog.results == {}
    assert (events[-1].kind, events[-1].reason) == ("stopped", "unexpected")


def test_summary_counts_failed(tmp_path):
    r, c, _, prog, *_ = make(tmp_path, {"a": [P], "b": [P]}, lookup_errors={"a": [ApiError("400")]})
    s = r.check()
    assert s.failed == 1 and s.pending == 1


def test_network_backoff_is_stoppable_and_visible(tmp_path):
    """I8"""
    holder = {}
    r, c, _, prog, events, clock, stop = make(tmp_path, {"a": [P]},
                                              lookup_errors={"a": [NetworkError()] * 4})
    def sleep(s):
        clock.sleep(s)
        if clock.t - 1_000_000.0 >= 5:
            stop.set()
    r._sleep = sleep
    r.run()
    assert any(e.kind == "waiting" for e in events)
    assert (events[-1].kind, events[-1].reason) == ("stopped", "user")
    assert sum(clock.sleeps) < 10


def test_cancel_network_error_but_post_landed_counts_as_cancelled(tmp_path):
    r, c, _, prog, *_ = make(tmp_path, {"a": [P, N]}, cancel_errors={"a": [NetworkError()]})
    r.run()
    assert prog.results["a"] is Outcome.CANCELLED
    assert prog.trial_done


# ---- advisor pass ------------------------------------------------------------
def test_trial_needs_verified_cancel(tmp_path):
    r, c, _, prog, events, *_ = make(tmp_path, {"a": [P, F], "b": [P, N]}, cancel_errors={"a": [NetworkError()]})
    r.run()
    assert prog.results["a"] is Outcome.ACCEPTED
    trial = [e for e in events if e.kind == "trial_ok"]
    assert trial and trial[0].username == "b"


def test_stop_event_carries_error_detail(tmp_path):
    r, c, _, prog, events, *_ = make(tmp_path, {"a": [P]}, lookup_errors={"a": [UnexpectedResponse("marker-123")]})
    r.check()
    assert "marker-123" in (events[-1].detail or "")


def test_check_canary_stops_when_own_profile_unreadable(tmp_path):
    r, c, _, prog, events, *_ = make(tmp_path, {"a": [P]})
    def broken(name):
        raise UnexpectedResponse("own profile")
    c.self_check = broken
    assert r.check() is None
    assert c.lookups == []
    assert (events[-1].kind, events[-1].reason) == ("stopped", "unexpected")
