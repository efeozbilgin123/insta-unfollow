"""Giriş noktası. `--smoke-test DOSYA`: CI'da paketin çalıştığını kanıtlar."""
from __future__ import annotations

import sys
import tempfile
import traceback

from playwright.sync_api import sync_playwright

from istek_geri_cek import __version__


def _check_gui(create_window: bool = True) -> None:
    """Paketin arayüz kısmının (Tk + ui modülü) gerçekten içinde olduğunu kanıtlar."""
    import tkinter as tk

    import istek_geri_cek.ui  # noqa: F401
    if create_window:
        root = tk.Tk()
        root.withdraw()
        root.update()
        root.destroy()


def _smoke(path: str) -> int:
    try:
        _check_gui()
        with tempfile.TemporaryDirectory() as profile, sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(profile, channel="msedge", headless=True)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("data:text/html,<p>ok</p>")
            assert page.inner_text("p") == "ok"
            ctx.close()
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
