from istek_geri_cek import __main__ as entry


class FakePage:
    def goto(self, url):
        self.url = url

    def inner_text(self, sel):
        return "ok"


class FakeBrowser:
    pages = []

    def new_page(self):
        return FakePage()

    def close(self):
        pass


class FakeChromium:
    def __init__(self, fail=False):
        self.fail = fail

    def launch_persistent_context(self, user_data_dir, **kw):
        if self.fail:
            raise RuntimeError("Edge yok")
        assert kw["channel"] == "msedge" and kw["headless"] is True
        assert user_data_dir
        return FakeBrowser()


class FakePW:
    def __init__(self, fail=False):
        self.chromium = FakeChromium(fail)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_smoke_flag_writes_ok(tmp_path, monkeypatch):
    gui = []
    monkeypatch.setattr(entry, "sync_playwright", lambda: FakePW())
    monkeypatch.setattr(entry, "_check_gui", lambda: gui.append(1))
    out = tmp_path / "smoke.txt"
    assert entry.main(["--smoke-test", str(out)]) == 0
    assert out.read_text().startswith("OK 0.1.0")
    assert gui == [1]


def test_smoke_failure_writes_traceback(tmp_path, monkeypatch):
    monkeypatch.setattr(entry, "sync_playwright", lambda: FakePW(fail=True))
    monkeypatch.setattr(entry, "_check_gui", lambda: None)
    out = tmp_path / "smoke.txt"
    assert entry.main(["--smoke-test", str(out)]) == 1
    assert "Edge yok" in out.read_text()


def test_check_gui_imports_ui_and_tk():
    import importlib.util
    if importlib.util.find_spec("tkinter") is None:
        import pytest
        pytest.skip("tkinter yok")
    entry._check_gui(create_window=False)
