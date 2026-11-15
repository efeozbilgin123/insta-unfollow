"""Bilgisayardaki Microsoft Edge'i kalıcı profille açar ve girişi bekler."""
from __future__ import annotations

import threading
import time

from . import config

INSTAGRAM = "https://www.instagram.com/"


class EdgeMissing(Exception):
    pass


def open_instagram(pw):
    try:
        ctx = pw.chromium.launch_persistent_context(
            str(config.data_dir() / "profile"), channel="msedge", headless=False, no_viewport=True)
    except Exception as e:  # Playwright kanal/çalıştırılabilir dosya hataları
        text = str(e).lower()
        if "msedge" in text or "executable" in text or "channel" in text or "not found" in text:
            raise EdgeMissing(str(e)) from e
        raise
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(INSTAGRAM)
    return ctx, page


def wait_for_login(page, client, stop: threading.Event, poll: float = 2.0) -> str | None:
    while not stop.is_set():
        try:
            if not page.url.startswith(INSTAGRAM):
                time.sleep(poll)
                continue
            name = client.current_username()
        except Exception:
            name = None
        if name:
            return name
        time.sleep(poll)
    return None
