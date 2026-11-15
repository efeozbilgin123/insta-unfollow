"""Giriş noktası. `--smoke-test DOSYA`: CI'da paketin çalıştığını kanıtlar."""
from __future__ import annotations

import sys
import traceback

from playwright.sync_api import sync_playwright

from istek_geri_cek import __version__


def _smoke(path: str) -> int:
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page()
            page.goto("data:text/html,<p>ok</p>")
            assert page.inner_text("p") == "ok"
            browser.close()
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"OK {__version__}\n")
        return 0
    except Exception:
        with open(path, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        return 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 2 and argv[0] == "--smoke-test":
        return _smoke(argv[1])
    from istek_geri_cek.ui import run_app
    run_app()
    return 0


if __name__ == "__main__":
    sys.exit(main())
