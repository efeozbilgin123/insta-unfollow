"""Instagram "Bilgilerini indir" ZIP'inden bekleyen istek kullanıcı adlarını okur."""
from __future__ import annotations

import json
import re
import zipfile
import zlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

_VALID = re.compile(r"^[a-z0-9._]{1,30}$")
_HOSTS = {"www.instagram.com", "instagram.com"}


class ExportError(Exception):
    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind  # "not_zip" | "no_requests"


def _from_href(href) -> str | None:
    if not isinstance(href, str) or not href:
        return None
    u = urlparse(href)
    if u.netloc.lower() not in _HOSTS:
        return None
    parts = [p for p in u.path.split("/") if p and p != "_u"]
    return parts[-1] if parts else None


def _clean(name) -> str | None:
    if not isinstance(name, str) or not name:
        return None
    name = name.strip().lstrip("@").lower()
    return name if _VALID.match(name) else None


def _walk_json(node, out: list[str]) -> None:
    if isinstance(node, dict):
        sld = node.get("string_list_data")
        if isinstance(sld, list):
            for entry in sld:
                if not isinstance(entry, dict):
                    continue
                name = _clean(entry.get("value")) or _clean(node.get("title")) or _clean(_from_href(entry.get("href")))
                if name:
                    out.append(name)
            if not sld:
                name = _clean(node.get("title"))
                if name:
                    out.append(name)
        for v in node.values():
            if isinstance(v, (dict, list)):
                _walk_json(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_json(v, out)


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            name = _clean(_from_href(dict(attrs).get("href")))
            if name:
                self.names.append(name)


def read_usernames(zip_path: str | Path) -> list[str]:
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as e:
        raise ExportError("not_zip") from e
    found: list[str] = []
    matched = False
    with zf:
        for member in sorted(zf.namelist()):
            base = member.rsplit("/", 1)[-1].lower()
            if "follow_requests" not in base:
                continue
            try:
                raw = zf.read(member).decode("utf-8", errors="replace")
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error, OSError) as e:
                raise ExportError("not_zip") from e
            if base.endswith(".json"):
                matched = True
                try:
                    _walk_json(json.loads(raw), found)
                except json.JSONDecodeError:
                    continue
            elif base.endswith(".html"):
                matched = True
                p = _Links()
                p.feed(raw)
                found.extend(p.names)
    if not matched:
        raise ExportError("no_requests")
    return list(dict.fromkeys(found))


def find_export_zip(folder: Path) -> Path | None:
    try:
        cands = [p for p in Path(folder).glob("*.zip") if p.name.lower().startswith("instagram-")]
    except OSError:
        return None
    return max(cands, key=lambda p: p.stat().st_mtime, default=None)
