# İstek Geri Çek — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A single-file Windows `.exe` that reads the user's Instagram data-export ZIP, logs in through the user's own Edge browser, and slowly withdraws every still-pending outgoing follow request — never touching accepted follows.

**Architecture:** Pure-Python core (ZIP parsing, progress store, run logic) is fully unit-tested on Linux. All Instagram specifics live in one module that runs `fetch` inside the logged-in Instagram page via Playwright (`channel="msedge"`, persistent profile). A Tkinter window is the only UI; all Playwright work runs on one worker thread and talks to the UI through a `queue.Queue`.

**Tech Stack:** Python 3.12, Playwright (sync API), Tkinter, pytest, PyInstaller, GitHub Actions (`windows-latest`, `ubuntu-latest`).

**Spec:** `docs/superpowers/specs/2026-11-15-istek-geri-cek-design.md`

## Global Constraints

- Windows 10/11 only; one `.exe`, built `--onefile --noconsole`, name `IstekGeriCek.exe`.
- Browser: system Edge via `channel="msedge"`; no bundled Chromium.
- The program never asks for or stores a password. Reports never contain cookies or tokens.
- Every user-facing string is Turkish and lives in `src/istek_geri_cek/strings.py`.
- Data dir: `%LOCALAPPDATA%\IstekGeriCek\` (Edge profile in `profile\`, progress files, `log.txt`). On non-Windows (tests), fall back to `~/.istek_geri_cek/`.
- Cancel only when a fresh status check, made immediately before the call, says the request is still pending.
- Default pacing: random 40–90 s between cancels, max 60 cancels per rolling hour, random 3–6 s between status-only lookups. All in `config.py`.
- On rate-limit / `feedback_required` / `checkpoint_required`: stop immediately, save progress, show the "yarın tekrar aç" message. No aggressive retry.
- All Instagram endpoints, headers, and the app id are unverified recall and live only in `instagram_api.py`.
- Version string `__version__` in `src/istek_geri_cek/__init__.py`, shown in the window title.

## Review Focus

1. Usernames with dots, underscores, digits, uppercase, or hrefs like `https://www.instagram.com/_u/ali.veli/` → parsed to `ali.veli` (lowercased), no duplicates.
2. Wrong file (not a ZIP, a ZIP without follow-request files, a ZIP the user already extracted and re-zipped with an extra top folder) → clear Turkish message, no crash. Nested paths must be found.
3. Program closed mid-run and reopened → resumes; usernames already in a final outcome are never re-checked or re-cancelled.
4. Session expires mid-run (`login_required`) → back to the login step with progress kept, then continue.
5. Network drop during a call → up to 3 retries with 10/30/60 s backoff, then pause with a Turkish message; never counted as a cancel.

---

## File Structure

```
pyproject.toml
src/istek_geri_cek/__init__.py      # __version__ = "0.1.0"
src/istek_geri_cek/config.py        # pacing constants, data_dir()
src/istek_geri_cek/strings.py       # all Turkish copy
src/istek_geri_cek/zip_reader.py    # ZIP -> usernames
src/istek_geri_cek/instagram_api.py # everything Instagram-specific
src/istek_geri_cek/store.py         # resumable progress per account
src/istek_geri_cek/runner.py        # check / trial / full-run logic
src/istek_geri_cek/report.py        # plain-text report
src/istek_geri_cek/browser.py       # Edge launch, login wait
src/istek_geri_cek/ui.py            # Tkinter screens + worker thread
src/istek_geri_cek/__main__.py      # entry point, --smoke-test
tests/...
.github/workflows/build.yml
docs/KULLANIM.md                    # friend-facing guide
README.md
```

---

### Task 1: Project scaffold and ZIP reader

**Files:**
- Create: `pyproject.toml`, `src/istek_geri_cek/__init__.py`, `src/istek_geri_cek/zip_reader.py`, `tests/test_zip_reader.py`, `tests/conftest.py`

**Interfaces:**
- Produces:
  - `class ExportError(Exception)` with attribute `kind: str` — one of `"not_zip"`, `"no_requests"`.
  - `read_usernames(zip_path: str | Path) -> list[str]` — lowercased, de-duplicated, order of first appearance.
  - `find_export_zip(folder: Path) -> Path | None` — newest `*.zip` in folder whose name starts with `instagram-` (export naming), else `None`.

`pyproject.toml`: package in `src/`, deps `playwright>=1.47`; dev extra `pytest`. `conftest.py` provides a `make_zip(tmp_path, files: dict[str, str]) -> Path` fixture.

- [ ] **Step 1: Write the failing tests**

```python
def test_json_pending_value_field(make_zip):
    z = make_zip({"connections/followers_and_following/pending_follow_requests.json":
        json.dumps({"relationships_follow_requests_sent": [
            {"title": "", "string_list_data": [{"href": "https://www.instagram.com/Ali.Veli", "value": "Ali.Veli", "timestamp": 1}]}]})})
    assert read_usernames(z) == ["ali.veli"]

def test_json_title_and_u_href_fallback(make_zip):
    # newer export shape: username in title, href with /_u/ and trailing slash, no value
    z = make_zip({"x/pending_follow_requests.json": json.dumps({"relationships_follow_requests_sent": [
        {"title": "zeynep_99", "string_list_data": [{"href": "https://www.instagram.com/_u/zeynep_99/"}]},
        {"title": "", "string_list_data": [{"href": "https://www.instagram.com/_u/mehmet.k/"}]}]})})
    assert read_usernames(z) == ["zeynep_99", "mehmet.k"]

def test_merges_recent_and_dedupes(make_zip):
    # pending + recent_follow_requests.json both contain "a"; result ["a", "b"]

def test_html_format(make_zip):
    z = make_zip({"connections/followers_and_following/pending_follow_requests.html":
        '<html><body><a href="https://www.instagram.com/ayse.y">ayse.y</a>'
        '<a href="https://www.instagram.com/_u/can_01/">can_01</a>'
        '<a href="https://help.instagram.com/123">yardım</a></body></html>'})
    assert read_usernames(z) == ["ayse.y", "can_01"]

def test_nested_top_folder(make_zip):
    # file under "instagram-ali-2026-11-15/connections/..." is still found

def test_not_a_zip(tmp_path):
    p = tmp_path / "x.zip"; p.write_text("hello")
    with pytest.raises(ExportError) as e: read_usernames(p)
    assert e.value.kind == "not_zip"

def test_zip_without_requests(make_zip):
    # zip with only "followers_1.json" -> ExportError kind "no_requests"

def test_find_export_zip_picks_newest(tmp_path):
    # two instagram-*.zip files with different mtimes + an unrelated foo.zip -> newest instagram one
```

- [ ] **Step 2: Run** `pytest tests/test_zip_reader.py -v` — Expected: FAIL (module not found).

- [ ] **Step 3: Implement `zip_reader.py`.** Match any member whose basename contains `follow_requests` and ends in `.json` or `.html`. JSON: walk recursively; for every dict that has a `string_list_data` list, take per entry `value` → else the dict's non-empty `title` → else last non-empty path segment of `href` (drop a leading `_u` segment). HTML: stdlib `html.parser`; collect `href`s whose host is exactly `www.instagram.com` or `instagram.com`, take last non-`_u` segment. Accept only `[a-z0-9._]{1,30}` after lowercasing.

- [ ] **Step 4: Run** `pytest tests/test_zip_reader.py -v` — Expected: all PASS.

- [ ] **Step 5: Commit** `feat: export ZIP reader`.

---

### Task 2: Instagram API module

**Files:**
- Create: `src/istek_geri_cek/instagram_api.py`, `tests/test_instagram_api.py`

**Interfaces:**
- Consumes: a page object with `evaluate(js: str, arg) -> Any` (Playwright `Page`; tests use a fake).
- Produces:
  - `class Status(Enum)`: `PENDING`, `FOLLOWING`, `NONE`, `NOT_FOUND`.
  - `class RateLimited(Exception)`, `class LoginRequired(Exception)`, `class NetworkError(Exception)`.
  - `class InstagramClient(page)` with:
    - `current_username() -> str | None` (None = not logged in)
    - `lookup(username: str) -> tuple[Status, str | None]` — returns status and user id (id is None for NOT_FOUND)
    - `cancel(user_id: str) -> None`
  - Pure helpers (tested directly): `classify_response(status: int, body: dict | None) -> None` (raises the right exception or returns), `status_from_friendship(fs: dict) -> Status`.

Calls (TO VERIFY on first real run; keep them as module-level constants):
- `APP_ID = "936619743392459"`, header `X-IG-App-ID`; POSTs add `X-CSRFToken` from the `csrftoken` cookie and `Content-Type: application/x-www-form-urlencoded`.
- Profile: `GET /api/v1/users/web_profile_info/?username={u}` → `data.user.id`; 404 or `data.user == null` → NOT_FOUND.
- Friendship: `GET /api/v1/friendships/show/{id}/` → `outgoing_request: true` → PENDING; `following: true` → FOLLOWING; else NONE.
- Cancel: `POST /api/v1/friendships/destroy/{id}/` body `user_id={id}`.
- Current user: `ds_user_id` cookie → `GET /api/v1/users/{id}/info/` → `user.username`.

All requests go through one JS function that calls `fetch(url, {credentials: "include", ...})` and returns `{status, body}` (body parsed JSON or null). A rejected `fetch` (TypeError) returns `{status: 0}`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("status,body,exc", [
    (429, None, RateLimited),
    (400, {"message": "feedback_required"}, RateLimited),
    (400, {"message": "checkpoint_required"}, RateLimited),
    (401, {"message": "login_required"}, LoginRequired),
    (403, {"message": "login_required"}, LoginRequired),
    (0, None, NetworkError),
    (500, None, NetworkError),
])
def test_classify_raises(status, body, exc): ...

def test_classify_ok(): assert classify_response(200, {"status": "ok"}) is None

def test_status_from_friendship():
    assert status_from_friendship({"outgoing_request": True, "following": False}) is Status.PENDING
    assert status_from_friendship({"outgoing_request": False, "following": True}) is Status.FOLLOWING
    assert status_from_friendship({}) is Status.NONE

def test_lookup_not_found(fake_page):  # fake returns 404 for web_profile_info
    assert InstagramClient(fake_page).lookup("yok") == (Status.NOT_FOUND, None)

def test_lookup_pending(fake_page):  # profile 200 id "42", friendship outgoing_request True
    assert InstagramClient(fake_page).lookup("ali") == (Status.PENDING, "42")

def test_cancel_posts_destroy(fake_page):
    InstagramClient(fake_page).cancel("42")
    assert fake_page.calls[-1]["url"].endswith("/api/v1/friendships/destroy/42/")
    assert fake_page.calls[-1]["method"] == "POST"
```

The fake page records the `arg` dict (`url`, `method`, `body`) passed to `evaluate` and returns scripted `{status, body}` values.

- [ ] **Step 2: Run** `pytest tests/test_instagram_api.py -v` — Expected: FAIL.
- [ ] **Step 3: Implement** per the interface above.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat: Instagram API module (endpoints to verify)`.

---

### Task 3: Progress store and config

**Files:**
- Create: `src/istek_geri_cek/config.py`, `src/istek_geri_cek/store.py`, `tests/test_store.py`

**Interfaces:**
- Produces:
  - `config.data_dir() -> Path` (creates it), constants `CANCEL_DELAY = (40, 90)`, `LOOKUP_DELAY = (3, 6)`, `MAX_CANCELS_PER_HOUR = 60`, `NETWORK_BACKOFF = (10, 30, 60)`.
  - `class Outcome(str, Enum)`: `CANCELLED`, `ACCEPTED` (was following, untouched), `NO_REQUEST`, `NOT_FOUND`, `FAILED`.
  - `class Progress` dataclass: `account: str`, `usernames: list[str]`, `checked: dict[str, str]` (username → Status name), `results: dict[str, Outcome]`, `trial_done: bool`, `cancel_times: list[float]`.
  - `Store(dir: Path)`: `load(account) -> Progress | None`, `save(p: Progress)`, `latest_unfinished() -> Progress | None`, `pending_work(p) -> list[str]` (usernames without a result, original order).

File: `progress_<account>.json`, written atomically (write temp + `os.replace`).

- [ ] **Step 1: Write failing tests:** round-trip save/load; `pending_work` skips usernames with results; `latest_unfinished` returns None when all have results; a truncated/corrupt JSON file → `load` returns None (no crash); atomic write leaves no `.tmp` file.
- [ ] **Step 2: Run** `pytest tests/test_store.py -v` — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat: resumable progress store`.

---

### Task 4: Runner (check → trial → full)

**Files:**
- Create: `src/istek_geri_cek/runner.py`, `tests/test_runner.py`

**Interfaces:**
- Consumes: `InstagramClient`-like object (`lookup`, `cancel`), `Store`, `Progress`, `Outcome`, `Status`, exceptions, config constants.
- Produces:
  - `@dataclass Event`: `kind: str` (`"checking"`, `"checked"`, `"trial_ok"`, `"progress"`, `"waiting"`, `"done"`, `"stopped"`), `done: int`, `total: int`, `username: str | None`, `seconds: float | None`, `reason: str | None` (`"rate_limited"`, `"login"`, `"network"`, `"user"`, `"trial_failed"`).
  - `@dataclass CheckSummary`: `pending: int`, `accepted: int`, `no_request: int`, `not_found: int`.
  - `Runner(client, store, progress, emit: Callable[[Event], None], sleep: Callable[[float], None], now: Callable[[], float], rand: Callable[[float, float], float], stop: threading.Event)` with:
    - `check() -> CheckSummary` — lookups only, no changes; records `checked`; NOT_FOUND / FOLLOWING / NONE get final results immediately (`NOT_FOUND`, `ACCEPTED`, `NO_REQUEST`). Skips usernames already checked.
    - `run() -> None` — if not `trial_done`: process first pending, verify, set `trial_done`, emit `trial_ok` (or stop with `trial_failed` if the result is FAILED). Then process the rest.

Processing one username: fresh `lookup` → if not PENDING, record the matching non-cancel outcome and do **not** cancel → else `cancel(id)` → `lookup` again → still PENDING or FOLLOWING → `FAILED`, else `CANCELLED`. Save after every username. Before each cancel, enforce `MAX_CANCELS_PER_HOUR` against `cancel_times` (emit `waiting` with seconds, sleep in ≤1 s slices honouring `stop`). `RateLimited` → save, emit `stopped/rate_limited`, return. `LoginRequired` → save, emit `stopped/login`, return. `NetworkError` → retry with `NETWORK_BACKOFF`; after the last fails emit `stopped/network`. `stop` set → emit `stopped/user` at the next safe point (never between cancel and its re-check).

- [ ] **Step 1: Write failing tests** (FakeClient with scripted statuses; `sleep` records calls; `now` is a fake clock advanced by `sleep`):
  - `test_check_makes_no_cancels`: 3 users (PENDING, FOLLOWING, NOT_FOUND) → `cancel` never called; summary `CheckSummary(1,1,0,1)`.
  - `test_accepted_between_check_and_run_is_not_cancelled`: checked PENDING, fresh lookup in `run` returns FOLLOWING → no cancel, outcome `ACCEPTED`.
  - `test_cancel_verified`: PENDING then NONE after cancel → `CANCELLED`.
  - `test_cancel_not_taking_is_failed`: still PENDING after cancel → `FAILED`; on trial → `stopped/trial_failed` and no further cancels.
  - `test_hourly_cap`: 61 pending users, fake clock → the 61st cancel happens ≥ 3600 s after the 1st; a `waiting` event was emitted.
  - `test_delay_between_cancels_in_range`: every sleep between cancels is within `CANCEL_DELAY` (rand stub returns bounds).
  - `test_rate_limited_stops_and_saves`: cancel raises RateLimited on user 2 → user 1 result saved, user 2 has no result, event `stopped/rate_limited`.
  - `test_login_required_stops_and_resume_skips_done`: LoginRequired on user 3; new Runner on reloaded progress → users 1–2 not looked up again.
  - `test_network_retries_then_stops`: lookup raises NetworkError 4× → sleeps 10, 30, 60 then `stopped/network`; no result recorded.
  - `test_stop_event_never_between_cancel_and_recheck`: stop set inside `cancel` → re-check still happens, result recorded, then `stopped/user`.
- [ ] **Step 2: Run** `pytest tests/test_runner.py -v` — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest -v` — all PASS.
- [ ] **Step 5: Commit** `feat: safe check/trial/full runner`.

---

### Task 5: Browser launch, entry point, smoke test

**Files:**
- Create: `src/istek_geri_cek/browser.py`, `src/istek_geri_cek/__main__.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: `config.data_dir()`, `InstagramClient`.
- Produces:
  - `class EdgeMissing(Exception)`.
  - `open_instagram(pw) -> tuple[BrowserContext, Page]` — `pw.chromium.launch_persistent_context(data_dir()/"profile", channel="msedge", headless=False, no_viewport=True)`, opens `https://www.instagram.com/`. Maps Playwright's "executable doesn't exist"/channel errors to `EdgeMissing`.
  - `wait_for_login(page, client, stop, poll=2.0) -> str | None` — polls `client.current_username()` until non-None or `stop`.
  - `main(argv: list[str] | None = None) -> int`: `--smoke-test PATH` launches Edge **headless** with a temp profile, loads `data:text/html,<p>ok</p>`, writes `"OK <version>"` to PATH, returns 0 (on any exception writes the traceback to PATH, returns 1). Without flags: starts the UI (Task 6).

- [ ] **Step 1: Write failing test** `test_smoke_flag_writes_ok` — monkeypatch the Playwright launcher with a fake → `main(["--smoke-test", str(out)]) == 0` and `out.read_text().startswith("OK 0.1.0")`; `test_smoke_failure_writes_traceback` → returns 1.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat: Edge launcher and smoke-test entry`.

---

### Task 6: Tkinter UI, strings, report

**Files:**
- Create: `src/istek_geri_cek/strings.py`, `src/istek_geri_cek/report.py`, `src/istek_geri_cek/ui.py`, `tests/test_report.py`, `tests/test_strings.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `run_app() -> None` (called from `main`); `build_report(p: Progress, version: str) -> str`; `save_report(text) -> Path` (writes `IstekGeriCek-rapor-YYYYMMDD-HHMM.txt` to Desktop, falling back to data dir).

Screens, in order, exactly as spec section "Akış": welcome (two buttons; if `Store.latest_unfinished()` exists, show "Kaldığın yerden devam edelim mi? (37 / 128)" first) → guide (numbered steps, button opens `https://accountscenter.instagram.com/info_and_permissions/dyi/` in Edge, emphasise **JSON**, **Tüm zamanlar**, **yalnızca "Takipçiler ve takip edilenler"**) → file pick (pre-filled with `find_export_zip(Downloads)`) → login wait → check results + account confirm ("Giriş yapılan hesap: @x. Bu senin hesabın mı?", counts, estimated time = pending × 65 s, "Evet, başlat" / "Hayır") → progress (bar, "37 / 128", current username, remaining time, "Durdur") → done (summary per spec: cancelled / accepted (untouched) / not found / failed, "Listeyi göster", "Raporu kaydet"). Stopped states map `reason` → message in `strings.py` (rate_limited → "Instagram biraz yavaşlamanı istedi. Programı yarın tekrar aç, kaldığı yerden devam eder."; login → back to login screen; network → "İnternet bağlantısı koptu…" with "Tekrar dene"; trial_failed → message + "Raporu kaydet"). `EdgeMissing` → message with link to `https://www.microsoft.com/edge`. Window title `İstek Geri Çek — sürüm {__version__}`. Large fonts (≥ 12 pt), min window 560×420.

Threading: one worker thread owns `sync_playwright()` and all page calls; UI only posts commands into `cmd_q` and polls `event_q` with `root.after(200, …)`.

- [ ] **Step 1: Write failing tests:** `test_report_has_counts_and_no_secrets` (report contains version, account, each outcome count, and no substring `csrftoken`/`sessionid`); `test_all_stop_reasons_have_messages` (every `Event.reason` value has a non-empty Turkish entry in `strings.STOP_MESSAGES`).
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement** strings, report, then ui. **Step 4: Run** `pytest -v` — PASS.
- [ ] **Step 5: Manual check (Linux, no Instagram):** `python -m istek_geri_cek` under `xvfb-run` with a fake client env var `ISTEK_FAKE=1` (worker uses a FakeClient with 5 scripted users and 1 s delays) — screenshot each screen; all text Turkish, nothing clipped.
- [ ] **Step 6: Commit** `feat: Turkish Tkinter UI and report`.

---

### Task 7: Windows build, release, guide

**Files:**
- Create: `.github/workflows/build.yml`, `docs/KULLANIM.md`, `README.md`

- [ ] **Step 1: Workflow.** Jobs: `test` (ubuntu, `pip install -e .[dev]`, `pytest -v`); `build` (windows-latest, needs test): `pip install . pyinstaller`, `pyinstaller --onefile --noconsole --name IstekGeriCek src/istek_geri_cek/__main__.py`, then smoke: `dist\IstekGeriCek.exe --smoke-test smoke.txt` (use `Start-Process -Wait` since it's a GUI-subsystem exe), fail unless `smoke.txt` starts with `OK`; upload artifact. `release` on tag `v*`: attach `IstekGeriCek.exe` and `KULLANIM.md` to a GitHub Release. Triggers: push to any branch, tags `v*`, `workflow_dispatch`.
- [ ] **Step 2: Push and verify** the run is green, including the smoke step output `OK 0.1.0`.
- [ ] **Step 3: `docs/KULLANIM.md`** — friend-facing Turkish guide: download link (latest release), SmartScreen "Ek bilgi → Yine de çalıştır" step, then what each screen asks. `README.md` — short developer notes: how to run tests, how to cut a release (`git tag v0.1.0 && git push --tags`), where Instagram specifics live and that they are unverified until the test-account run.
- [ ] **Step 4: Commit** `ci: Windows build, smoke test, release; guide`.

---

## After the plan: test-account run (with the user)

Not a coding task. Walk the user through the spec's test: Account A → pending requests to Account B (private) and 2–3 others, B accepts one; export A's data (JSON, all time, followers & following); run the `.exe`. Expected: check screen shows the accepted one as "kabul etmiş", trial cancels one and verifies, full run finishes, accepted follow remains. Fix `instagram_api.py` from the saved report if anything differs, bump version, re-release.
