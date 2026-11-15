from istek_geri_cek import __main__ as entry


class FakePage:
    def goto(self, url):
        self.url = url

    def inner_text(self, sel):
        return "ok"


class FakeBrowser:
    def new_page(self):
        return FakePage()

    def close(self):
        pass


class FakeChromium:
    def __init__(self, fail=False):
        self.fail = fail

    def launch(self, **kw):
        if self.fail:
            raise RuntimeError("Edge yok")
        assert kw["channel"] == "msedge" and kw["headless"] is True
        return FakeBrowser()


class FakePW:
    def __init__(self, fail=False):
        self.chromium = FakeChromium(fail)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_smoke_flag_writes_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(entry, "sync_playwright", lambda: FakePW())
    out = tmp_path / "smoke.txt"
    assert entry.main(["--smoke-test", str(out)]) == 0
    assert out.read_text().startswith("OK 0.1.0")


def test_smoke_failure_writes_traceback(tmp_path, monkeypatch):
    monkeypatch.setattr(entry, "sync_playwright", lambda: FakePW(fail=True))
    out = tmp_path / "smoke.txt"
    assert entry.main(["--smoke-test", str(out)]) == 1
    assert "Edge yok" in out.read_text()
