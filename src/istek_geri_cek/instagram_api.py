"""Instagram'a özgü her şey burada.

UYARI: Aşağıdaki endpoint'ler, header'lar ve APP_ID hafızadan yazıldı ve gerçek bir
hesapla ilk denemede doğrulanacak. Bir şey değişirse yalnızca bu dosya düzeltilir.
"""
from __future__ import annotations

import logging
from enum import Enum
from urllib.parse import quote

log = logging.getLogger("istek_geri_cek")

BASE = "https://www.instagram.com"
APP_ID = "936619743392459"
PROFILE_URL = BASE + "/api/v1/users/web_profile_info/?username={username}"
FRIENDSHIP_URL = BASE + "/api/v1/friendships/show/{user_id}/"
CANCEL_URL = BASE + "/api/v1/friendships/destroy/{user_id}/"
USER_INFO_URL = BASE + "/api/v1/users/{user_id}/info/"

RATE_LIMIT_MESSAGES = ("feedback_required", "checkpoint_required", "please wait", "rate_limit")
LOGIN_MESSAGES = ("login_required",)

# Sayfa içinde çalışır: oturum çerezleri otomatik gider, CSRF çerezden okunur.
_REQUEST_JS = """
async (a) => {
  const csrf = (document.cookie.match(/(?:^|; )csrftoken=([^;]*)/) || [])[1] || "";
  const headers = {"X-IG-App-ID": a.app_id, "X-Requested-With": "XMLHttpRequest"};
  if (a.method === "POST") {
    headers["X-CSRFToken"] = csrf;
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  }
  try {
    const r = await fetch(a.url, {method: a.method, headers, body: a.body || undefined, credentials: "include"});
    let body = null;
    try { body = await r.json(); } catch (e) {}
    return {status: r.status, body};
  } catch (e) {
    return {status: 0, body: null};
  }
}
"""



class Status(Enum):
    PENDING = "PENDING"
    FOLLOWING = "FOLLOWING"
    NONE = "NONE"
    NOT_FOUND = "NOT_FOUND"


class RateLimited(Exception):
    pass


class LoginRequired(Exception):
    pass


class NetworkError(Exception):
    pass


class UnexpectedResponse(Exception):
    """Yanıt beklenen biçimde değil: hiçbir şey kaydedilmez, iş durur."""


class ApiError(Exception):
    """Tek bir kullanıcıya özgü hata (4xx): o kişi 'başarısız' sayılır, iş devam eder."""


def classify_response(status: int, body: dict | None) -> None:
    msg = str((body or {}).get("message", "")).lower()
    if status == 429 or any(m in msg for m in RATE_LIMIT_MESSAGES):
        raise RateLimited(msg or str(status))
    if any(m in msg for m in LOGIN_MESSAGES) or status == 401:
        raise LoginRequired(msg or str(status))
    if status == 0 or status >= 500:
        raise NetworkError(str(status))
    if status >= 400 and status != 404:
        raise ApiError(f"{status} {msg}")


def status_from_friendship(fs: dict) -> Status:
    out, fol = (fs or {}).get("outgoing_request"), (fs or {}).get("following")
    if not isinstance(out, bool) or not isinstance(fol, bool):
        raise UnexpectedResponse(f"friendship: {fs!r}"[:300])
    if fol:  # kabul edilmiş takip her zaman önceliklidir: asla geri çekme
        return Status.FOLLOWING
    return Status.PENDING if out else Status.NONE


class InstagramClient:
    def __init__(self, page):
        self.page = page

    def _call(self, url: str, method: str = "GET", body: str | None = None) -> tuple[int, dict | None]:
        r = self.page.evaluate(_REQUEST_JS, {"url": url, "method": method, "body": body, "app_id": APP_ID})
        status, data = int(r.get("status", 0)), r.get("body")
        if not 200 <= status < 300:
            # yalnızca yanıt gövdesi kaydedilir; header/çerez asla
            log.warning("instagram %s %s -> %s %s", method, url.split("?")[0], status, repr(data)[:300])
        classify_response(status, data)
        return status, data

    def current_username(self) -> str | None:
        cookies = {c.get("name"): c.get("value") for c in self.page.context.cookies()}
        uid = cookies.get("ds_user_id")
        if not uid:
            return None
        status, data = self._call(USER_INFO_URL.format(user_id=uid))
        name = (((data if isinstance(data, dict) else {}).get("user")) or {}).get("username")
        if status != 200 or not isinstance(name, str) or not name:
            raise UnexpectedResponse(f"user info {status}: {data!r}"[:300])
        return name.lower()

    def self_check(self, username: str) -> str:
        """Kendi profilini okuyabildiğimizi doğrular (profil endpoint'i için kanarya)."""
        status, data = self._call(PROFILE_URL.format(username=quote(username)))
        user = ((data if isinstance(data, dict) else {}).get("data") or {}).get("user")
        if status != 200 or not isinstance(user, dict) or not user.get("id"):
            raise UnexpectedResponse(f"self profile {status}: {data!r}"[:300])
        return str(user["id"])

    def lookup(self, username: str) -> tuple[Status, str | None]:
        status, data = self._call(PROFILE_URL.format(username=quote(username)))
        if status == 404:
            return Status.NOT_FOUND, None
        user = ((data if isinstance(data, dict) else {}).get("data") or {}).get("user")
        if not isinstance(user, dict) or not user.get("id"):
            raise UnexpectedResponse(f"profile {status}: {data!r}"[:300])
        uid = str(user["id"])
        status, fs = self._call(FRIENDSHIP_URL.format(user_id=uid))
        if status == 404:
            raise UnexpectedResponse(f"friendship 404 for existing user {uid}")
        return status_from_friendship(fs if isinstance(fs, dict) else {}), uid

    def cancel(self, user_id: str) -> None:
        self._call(CANCEL_URL.format(user_id=user_id), method="POST", body=f"user_id={user_id}")
