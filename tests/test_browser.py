import threading

import pytest

from istek_geri_cek import browser
from istek_geri_cek.browser import BrowserClosed, EdgeMissing


class Page:
    def __init__(self, url="https://www.instagram.com/", closed_after=None):
        self.url = url
        self.closed_after = closed_after
        self.polls = 0
        self.gotos = []

    def is_closed(self):
        return self.closed_after is not None and self.polls >= self.closed_after

    def goto(self, url):
        self.gotos.append(url)
        self.url = url


class Client:
    def __init__(self, answers):
        self.answers = list(answers)

    def current_username(self):
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


def _wait(page, client, **kw):
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        page.polls += 1

    monkey = pytest.MonkeyPatch()
    monkey.setattr(browser.time, "sleep", sleep)
    try:
        return browser.wait_for_login(page, client, threading.Event(), poll=2.0, **kw), sleeps
    finally:
        monkey.undo()


def test_wait_for_login_returns_name():
    name, _ = _wait(Page(), Client([None, None, "efe"]))
    assert name == "efe"


def test_wait_for_login_navigates_back_to_instagram():
    """I3: after the guide moved the page to accountscenter, login wait must not hang."""
    page = Page(url="https://accountscenter.instagram.com/info_and_permissions/dyi/")
    name, _ = _wait(page, Client(["efe"]))
    assert name == "efe" and page.gotos == [browser.INSTAGRAM]


def test_wait_for_login_raises_when_window_closed():
    """I4"""
    with pytest.raises(BrowserClosed):
        _wait(Page(closed_after=2), Client([None] * 10))


def test_wait_for_login_backs_off_on_errors():
    """I4: API errors must not be polled every 2 s forever."""
    name, sleeps = _wait(Page(), Client([RuntimeError("x")] * 4 + ["efe"]))
    assert name == "efe"
    assert sleeps[-1] > sleeps[0]


class FailingChromium:
    def __init__(self, msg):
        self.msg = msg

    def launch_persistent_context(self, *a, **kw):
        raise RuntimeError(self.msg)


class PW:
    def __init__(self, msg):
        self.chromium = FailingChromium(msg)


def test_edge_missing_mapped(tmp_path, monkeypatch):
    monkeypatch.setattr(browser.config, "data_dir", lambda: tmp_path)
    with pytest.raises(EdgeMissing):
        browser.open_instagram(PW('Chromium distribution \'msedge\' is not found at C:\\...'))


def test_other_launch_errors_not_reported_as_edge_missing(tmp_path, monkeypatch):
    """I7"""
    monkeypatch.setattr(browser.config, "data_dir", lambda: tmp_path)
    with pytest.raises(RuntimeError):
        browser.open_instagram(PW("Target page, context or browser has been closed (msedge.exe)"))


def test_single_instance_lock():
    a = browser.single_instance_lock()
    assert a is not None
    assert browser.single_instance_lock() is None
    a.close()
    b = browser.single_instance_lock()
    assert b is not None
    b.close()


def test_wait_for_login_does_not_yank_user_mid_login():
    page = Page()
    class C:
        n = 0
        def current_username(self):
            C.n += 1
            if C.n == 1:
                page.url = "https://www.facebook.com/login"
            return "efe" if C.n == 3 else None
    name, _ = _wait(page, C())
    assert name == "efe" and page.gotos == []
