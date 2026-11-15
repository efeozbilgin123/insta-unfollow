from istek_geri_cek.store import Outcome, Progress, Store


def _p(account="efe", users=("a", "b", "c")):
    return Progress(account=account, usernames=list(users))


def test_round_trip(tmp_path):
    s = Store(tmp_path)
    p = _p()
    p.checked["a"] = "PENDING"
    p.results["a"] = Outcome.CANCELLED
    p.trial_done = True
    p.cancel_times.append(123.5)
    s.save(p)
    q = s.load("efe")
    assert q == p
    assert q.results["a"] is Outcome.CANCELLED


def test_pending_work_skips_results(tmp_path):
    p = _p()
    p.results["b"] = Outcome.ACCEPTED
    assert Store(tmp_path).pending_work(p) == ["a", "c"]


def test_latest_unfinished(tmp_path):
    s = Store(tmp_path)
    done = _p("done", ["a"])
    done.results["a"] = Outcome.CANCELLED
    s.save(done)
    assert s.latest_unfinished() is None
    s.save(_p("open", ["x"]))
    assert s.latest_unfinished().account == "open"


def test_corrupt_file_loads_none(tmp_path):
    (tmp_path / "progress_efe.json").write_text('{"account": "ef')
    s = Store(tmp_path)
    assert s.load("efe") is None
    assert s.latest_unfinished() is None


def test_atomic_write_leaves_no_tmp(tmp_path):
    Store(tmp_path).save(_p())
    assert [f.name for f in tmp_path.iterdir()] == ["progress_efe.json"]


def test_start_new_zip_is_fresh_but_keeps_cancel_times(tmp_path):
    """I9: an explicit new ZIP must not inherit old final results."""
    s = Store(tmp_path)
    old = _p("efe", ["a", "b"])
    old.results["a"] = Outcome.CANCELLED
    old.cancel_times = [5.0]
    old.trial_done = True
    s.save(old)
    p = s.start("efe", ["a", "c"])
    assert p.usernames == ["a", "c"] and p.results == {} and p.checked == {}
    assert p.cancel_times == [5.0] and p.trial_done is False
    assert s.load("efe") == p


def test_start_without_existing(tmp_path):
    p = Store(tmp_path).start("yeni", ["x"])
    assert p == Progress(account="yeni", usernames=["x"])


def test_load_ignores_unknown_keys(tmp_path):
    import json
    (tmp_path / "progress_efe.json").write_text(json.dumps(
        {"account": "efe", "usernames": ["a"], "future_field": 1}))
    assert Store(tmp_path).load("efe").usernames == ["a"]
