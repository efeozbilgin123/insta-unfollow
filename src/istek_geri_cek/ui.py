"""Tek pencereli Tkinter arayüzü.

Bütün Playwright işleri tek bir arka plan iş parçacığında (worker) çalışır. Arayüz ona
`_submit(fonksiyon)` ile iş yollar, sonuçları `event_q` üzerinden `root.after` ile okur.
"""
from __future__ import annotations

import logging
import os
import queue
import random
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font, messagebox, ttk

from . import __version__, config, strings
from .browser import INSTAGRAM, BrowserClosed, EdgeMissing, open_instagram, single_instance_lock, wait_for_login
from .instagram_api import InstagramClient
from .report import build_report, save_report
from .runner import Runner
from .store import Outcome, Progress, Store
from .zip_reader import ExportError, find_export_zip, read_usernames

log = logging.getLogger("istek_geri_cek")
AVG_CANCEL_SECONDS = sum(config.CANCEL_DELAY) / 2


class Worker(threading.Thread):
    """Playwright'ın sahibi. İşleri sırayla çalıştırır."""

    def __init__(self, event_q: queue.Queue, fake: bool):
        super().__init__(daemon=True)
        self.cmd_q: queue.Queue = queue.Queue()
        self.event_q = event_q
        self.fake = fake
        self.pw = self.ctx = self.page = self.client = None

    def run(self):
        if not self.fake:
            from playwright.sync_api import sync_playwright
            self.pw = sync_playwright().start()
        while True:
            fn = self.cmd_q.get()
            if fn is None:
                break
            try:
                fn(self)
            except EdgeMissing:
                log.exception("Edge yok")
                self.event_q.put(("edge_missing", None))
            except BrowserClosed:
                log.warning("Edge penceresi kapandı")
                self.event_q.put(("browser_closed", None))
            except Exception as e:  # beklenmeyen: arayüze bildir, programı çökertme
                log.exception("beklenmeyen hata")
                self.event_q.put(("error", f"{type(e).__name__}: {e}"))
        try:
            if self.ctx:
                self.ctx.close()
            if self.pw:
                self.pw.stop()
        except Exception:
            pass

    def ensure_browser(self, url: str | None = None):
        if self.fake:
            from .fake import FakeClient
            self.client = self.client or FakeClient()
            return
        if self.ctx is not None and self.page.is_closed():
            raise BrowserClosed()
        if self.ctx is None:
            self.ctx, self.page = open_instagram(self.pw)
            self.client = InstagramClient(self.page)
            if not url:
                self.page.goto(INSTAGRAM)
        if url:
            self.page.goto(url)
        else:
            try:
                self.page.bring_to_front()
            except Exception:
                pass


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.fake = os.environ.get("ISTEK_FAKE") == "1"
        self.store = Store(config.data_dir())
        self.event_q: queue.Queue = queue.Queue()
        self.worker = Worker(self.event_q, self.fake)
        self.worker.start()
        self.stop = threading.Event()
        self.progress: Progress | None = None
        self.usernames: list[str] = []
        self.last_error = ""
        self.handlers = {}
        self.fresh_zip = False
        root.report_callback_exception = self._callback_error

        root.title(strings.TITLE.format(version=__version__))
        root.minsize(560, 420)
        root.geometry("640x480")
        for name in ("TkDefaultFont", "TkTextFont"):
            font.nametofont(name).configure(size=12)
        self.big = font.Font(size=16, weight="bold")
        style = ttk.Style()
        style.configure("Big.TButton", font=("TkDefaultFont", 13), padding=10)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.frame = None
        root.after(200, self._poll)
        self.welcome()

    # ---- altyapı -----------------------------------------------------------
    def _submit(self, fn):
        self.worker.cmd_q.put(fn)

    def _callback_error(self, exc, val, tb):
        log.error("arayüz hatası", exc_info=(exc, val, tb))
        self.on_error(f"{exc.__name__}: {val}")

    def _poll(self):
        try:
            while True:
                kind, payload = self.event_q.get_nowait()
                handler = self.handlers.get(kind) or getattr(self, f"on_{kind}", None)
                if handler:
                    try:
                        handler(payload)
                    except Exception as e:
                        log.exception("olay işlenemedi: %s", kind)
                        self.on_error(f"{type(e).__name__}: {e}")
        except queue.Empty:
            pass
        finally:
            self.root.after(200, self._poll)

    def screen(self, title: str, body: str = "") -> ttk.Frame:
        if self.frame:
            self.frame.destroy()
        self.handlers = {}
        self.frame = ttk.Frame(self.root, padding=24)
        self.frame.pack(fill="both", expand=True)
        ttk.Label(self.frame, text=title, font=self.big).pack(anchor="w", pady=(0, 12))
        if body:
            self.label(body)
        return self.frame

    def label(self, text: str, **kw) -> ttk.Label:
        lbl = ttk.Label(self.frame, text=text, wraplength=580, justify="left", **kw)
        lbl.pack(anchor="w", pady=4)
        return lbl

    def button(self, text: str, cmd, **pack) -> ttk.Button:
        b = ttk.Button(self.frame, text=text, command=cmd, style="Big.TButton")
        b.pack(fill="x", pady=6, **pack)
        return b

    def quit(self):
        self.stop.set()
        self.worker.cmd_q.put(None)
        deadline = time.time() + 5

        def finish():
            if self.worker.is_alive() and time.time() < deadline:
                return self.root.after(100, finish)
            self.root.destroy()

        finish()

    # ---- 1. hoş geldin -----------------------------------------------------
    def welcome(self):
        unfinished = self.store.latest_unfinished()
        if unfinished:
            self.screen(strings.WELCOME_TITLE, strings.RESUME_Q.format(
                done=len(unfinished.results), total=len(unfinished.usernames)))
            self.button(strings.BTN_RESUME, lambda: self.resume(unfinished))
            self.button(strings.BTN_NEW, self._welcome_plain)
            return
        self._welcome_plain()

    def _welcome_plain(self):
        self.screen(strings.WELCOME_TITLE, strings.WELCOME_BODY)
        self.button(strings.BTN_HAVE_ZIP, self.pick)
        self.button(strings.BTN_NEED_GUIDE, self.guide)

    def resume(self, p: Progress):
        self.progress = p
        self.usernames = p.usernames
        self.login()

    # ---- 2. rehber ---------------------------------------------------------
    def guide(self):
        self.screen(strings.GUIDE_TITLE)
        for i, step in enumerate(strings.GUIDE_STEPS, 1):
            self.label(f"{i}.  {step}")
        self.button(strings.BTN_OPEN_DYI, lambda: self._submit(lambda w: w.ensure_browser(strings.DYI_URL)))
        row = ttk.Frame(self.frame)
        row.pack(fill="x", pady=8)
        ttk.Button(row, text=strings.BTN_BACK, command=self._welcome_plain).pack(side="left")
        ttk.Button(row, text=strings.BTN_HAVE_ZIP, command=self.pick).pack(side="right")

    # ---- 3. dosya seçme ----------------------------------------------------
    def pick(self, error: str | None = None):
        self.screen(strings.PICK_TITLE, strings.PICK_BODY)
        if error:
            self.label(error, foreground="#b00020")
        found = find_export_zip(Path.home() / "Downloads")
        if found:
            self.label(strings.PICK_FOUND.format(name=found.name))
            self.button(strings.BTN_USE_FOUND, lambda: self.load_zip(found))
        self.button(strings.BTN_BROWSE, self._browse)
        ttk.Button(self.frame, text=strings.BTN_BACK, command=self._welcome_plain).pack(anchor="w", pady=8)

    def _browse(self):
        path = filedialog.askopenfilename(
            title=strings.PICK_TITLE, initialdir=str(Path.home() / "Downloads"),
            filetypes=[("ZIP", "*.zip"), ("*", "*.*")])
        if path:
            self.load_zip(Path(path))

    def load_zip(self, path: Path):
        try:
            names = read_usernames(path)
        except ExportError as e:
            return self.pick(strings.EXPORT_ERRORS[e.kind])
        if not names:
            return self.pick(strings.EXPORT_ERRORS["empty"])
        log.info("ZIP okundu: %d kullanıcı adı", len(names))
        self.usernames = names
        self.progress = None
        self.fresh_zip = True
        self.login()

    # ---- 4. giriş ----------------------------------------------------------
    def login(self):
        self.screen(strings.LOGIN_TITLE, strings.OPENING)
        status = self.frame.winfo_children()[-1]
        self.stop.clear()

        def job(w: Worker):
            w.ensure_browser()
            self.event_q.put(("login_ready", None))
            name = "deneme_hesabi" if w.fake else wait_for_login(w.page, w.client, self.stop)
            if name:
                self.event_q.put(("logged_in", name))

        self.handlers["login_ready"] = lambda _: status.configure(text=strings.LOGIN_BODY)
        self.handlers["logged_in"] = self.after_login
        self._submit(job)

    def after_login(self, account: str):
        log.info("giriş: @%s", account)
        if self.fresh_zip:
            self.progress = self.store.start(account, self.usernames)
            self.fresh_zip = False
        elif self.progress is None or self.progress.account != account:
            # yarım iş başka bir hesaba ait: yanlış hesaba uygulama
            self.screen(strings.WELCOME_TITLE, strings.WRONG_ACCOUNT)
            return self.button(strings.BTN_CLOSE, self.quit)
        self.check()

    # ---- 5. kontrol + onay -------------------------------------------------
    def _runner(self, w: Worker) -> Runner:
        emit = lambda e: self.event_q.put(("runner", e))
        if w.fake:
            return Runner(w.client, self.store, self.progress, emit, sleep=time.sleep, now=time.time,
                          rand=lambda a, b: 0.3, stop=self.stop)
        return Runner(w.client, self.store, self.progress, emit, sleep=time.sleep, now=time.time,
                      rand=random.uniform, stop=self.stop)

    def check(self):
        self.screen(strings.PROGRESS_TITLE)
        bar = ttk.Progressbar(self.frame, mode="determinate", maximum=1)
        bar.pack(fill="x", pady=12)
        line = self.label(strings.CHECKING.format(done=0, total="…"))
        self.button(strings.BTN_STOP, self.stop.set)

        def on_runner(e):
            if e.kind == "checking":
                bar.configure(maximum=max(1, e.total), value=e.done)
                line.configure(text=strings.CHECKING.format(done=e.done, total=e.total))
            elif e.kind == "stopped":
                self.stopped(e.reason)

        def job(w: Worker):
            summary = self._runner(w).check()
            if summary is not None:
                self.event_q.put(("checked", summary))

        self.handlers["runner"] = on_runner
        self.handlers["checked"] = self.confirm
        self._submit(job)

    def confirm(self, s):
        self.screen(strings.WELCOME_TITLE)
        self.label(strings.CONFIRM_ACCOUNT.format(account=self.progress.account), font=self.big)
        if s.pending == 0:
            if not s.failed:
                self.label(strings.CONFIRM_NONE)
            return self.done(keep_screen=True)
        self.label(strings.CONFIRM_COUNTS.format(
            pending=s.pending, accepted=s.accepted, not_found=s.not_found,
            hours=strings.duration(s.pending * AVG_CANCEL_SECONDS)))
        if s.failed:
            self.label(strings.CONFIRM_FAILED.format(failed=s.failed))
        self.button(strings.BTN_START, self.run)
        self.button(strings.BTN_NO, lambda: (self.screen(strings.WELCOME_TITLE, strings.WRONG_ACCOUNT),
                                             self.button(strings.BTN_CLOSE, self.quit)))

    # ---- 6. ilerleme -------------------------------------------------------
    def run(self):
        self.stop.clear()
        self.screen(strings.PROGRESS_TITLE)
        p = self.progress
        bar = ttk.Progressbar(self.frame, mode="determinate", maximum=max(1, len(p.usernames)))
        bar.pack(fill="x", pady=12)
        count = self.label("", font=self.big)
        user = self.label("")
        left = self.label("")
        note = self.label(strings.PROGRESS_NOTE)
        self.button(strings.BTN_STOP, self.stop.set)

        def refresh(e):
            bar.configure(value=e.done)
            count.configure(text=strings.PROGRESS_LINE.format(done=e.done, total=e.total))
            remaining = len(self.store.pending_work(p)) * AVG_CANCEL_SECONDS
            left.configure(text=strings.PROGRESS_LEFT.format(left=strings.duration(remaining)))

        def on_runner(e):
            if e.kind == "progress":
                refresh(e)
                if e.username:
                    user.configure(text=strings.PROGRESS_USER.format(username=e.username))
            elif e.kind == "trial_ok":
                note.configure(text=strings.TRIAL_OK)
            elif e.kind == "waiting":
                user.configure(text=strings.WAITING.format(left=strings.duration(e.seconds or 0)))
            elif e.kind == "done":
                self.done()
            elif e.kind == "stopped":
                self.stopped(e.reason)

        self.handlers["runner"] = on_runner
        self._submit(lambda w: self._runner(w).run())

    # ---- durma / hata ------------------------------------------------------
    def stopped(self, reason: str):
        log.info("durdu: %s", reason)
        if reason == "login":
            self.progress = self.store.load(self.progress.account) or self.progress
            self.usernames = self.progress.usernames
            self.screen(strings.LOGIN_TITLE, strings.STOP_MESSAGES["login"])
            return self._relogin()
        self.screen(strings.PROGRESS_TITLE, strings.STOP_MESSAGES[reason])
        if reason == "network":
            # tekrar dene her zaman kontrol + onay ekranından geçer
            self.button(strings.BTN_RETRY, self.check)
        self._report_button()
        self.button(strings.BTN_CLOSE, self.quit)

    def _relogin(self):
        def job(w: Worker):
            w.ensure_browser(None if w.fake else "https://www.instagram.com/accounts/login/")
            name = "deneme_hesabi" if w.fake else wait_for_login(w.page, w.client, self.stop)
            if name:
                self.event_q.put(("relogged", name))

        def relogged(name):
            if name != self.progress.account:
                self.screen(strings.WELCOME_TITLE, strings.WRONG_ACCOUNT)
                return self.button(strings.BTN_CLOSE, self.quit)
            self.check()

        self.handlers["relogged"] = relogged
        self._submit(job)

    def on_error(self, detail: str):
        self.last_error = detail
        self.screen(strings.PROGRESS_TITLE, strings.UNEXPECTED)
        self._report_button()
        self.button(strings.BTN_CLOSE, self.quit)

    def on_browser_closed(self, _):
        self.screen(strings.WELCOME_TITLE, strings.BROWSER_CLOSED)
        self.button(strings.BTN_CLOSE, self.quit)

    def on_edge_missing(self, _):
        self.screen(strings.WELCOME_TITLE, strings.EDGE_MISSING)
        self.button(strings.BTN_CLOSE, self.quit)

    def _report_button(self):
        msg = ttk.Label(self.frame, text="", wraplength=580)

        def save():
            p = self.progress or Progress(account="?", usernames=self.usernames)
            try:
                path = save_report(build_report(p, __version__, self.last_error))
                msg.configure(text=strings.REPORT_SAVED.format(path=path))
            except OSError as e:
                msg.configure(text=str(e))

        self.button(strings.BTN_SAVE_REPORT, save)
        msg.pack(anchor="w")

    # ---- 7. bitiş ----------------------------------------------------------
    def done(self, keep_screen: bool = False):
        vals = list(self.progress.results.values())
        if not keep_screen:
            self.screen(strings.DONE_TITLE)
        self.label(strings.DONE_SUMMARY.format(
            cancelled=vals.count(Outcome.CANCELLED), accepted=vals.count(Outcome.ACCEPTED),
            not_found=vals.count(Outcome.NOT_FOUND), failed=vals.count(Outcome.FAILED)))
        self.button(strings.BTN_SHOW_LIST, self.show_list)
        self._report_button()
        self.button(strings.BTN_CLOSE, self.quit)

    def show_list(self):
        win = tk.Toplevel(self.root)
        win.title(strings.BTN_SHOW_LIST)
        win.geometry("420x480")
        text = tk.Text(win, wrap="word")
        text.pack(fill="both", expand=True)
        for u in self.progress.usernames:
            o = self.progress.results.get(u)
            text.insert("end", f"@{u} — {strings.OUTCOME_LABELS[o.value] if o else '…'}\n")
        text.configure(state="disabled")


def run_app() -> None:
    logging.basicConfig(filename=str(config.data_dir() / "log.txt"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    log.info("başladı, sürüm %s", __version__)
    lock = single_instance_lock()
    if lock is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(strings.WELCOME_TITLE, strings.ALREADY_RUNNING)
        root.destroy()
        return
    root = tk.Tk()
    App(root)
    root.mainloop()
    lock.close()
