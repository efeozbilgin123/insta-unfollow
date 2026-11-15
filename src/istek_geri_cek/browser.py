"""Bilgisayardaki Microsoft Edge'i kalıcı profille açar ve girişi bekler."""
from __future__ import annotations

import logging
import socket
import threading
import time

from . import config

INSTAGRAM = "https://www.instagram.com/"
LOCK_PORT = 47613
_EDGE_MISSING_MARKERS = ("is not found at", "executable doesn't exist", "browsertype.launch: chromium distribution")
log = logging.getLogger("istek_geri_cek")


class EdgeMissing(Exception):
    pass


class BrowserClosed(Exception):
    pass


def single_instance_lock() -> socket.socket | None:
    """Programın ikinci kopyasını engeller. Kilit alınamazsa None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
        return s
    except OSError:
        s.close()
        return None


def open_instagram(pw):
    try:
        ctx = pw.chromium.launch_persistent_context(
            str(config.data_dir() / "profile"), channel="msedge", headless=False, no_viewport=True)
    except Exception as e:
        if any(m in str(e).lower() for m in _EDGE_MISSING_MARKERS):
            raise EdgeMissing(str(e)) from e
        raise
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, page


def wait_for_login(page, client, stop: threading.Event, poll: float = 2.0) -> str | None:
    delay = poll
    # Yalnızca başta Instagram'a dön (ör. rehberdeki sayfadan). Sonrasında kullanıcının
    # giriş akışına (Facebook ile giriş, doğrulama sayfaları) karışma.
    if not page.is_closed() and not page.url.startswith(INSTAGRAM):
        page.goto(INSTAGRAM)
    while not stop.is_set():
        if page.is_closed():
            raise BrowserClosed()
        try:
            name = client.current_username()
            delay = poll
        except Exception as e:
            if page.is_closed():
                raise BrowserClosed() from e
            log.warning("giriş kontrolü hatası: %s", e)
            name = None
            delay = min(delay * 2, 60)
        if name:
            return name
        time.sleep(delay)
    return None
