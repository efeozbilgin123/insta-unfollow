"""Hesap başına kaldığı yerden devam edilebilir ilerleme kaydı."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path


class Outcome(str, Enum):
    CANCELLED = "CANCELLED"
    ACCEPTED = "ACCEPTED"
    NO_REQUEST = "NO_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    FAILED = "FAILED"


@dataclass
class Progress:
    account: str
    usernames: list[str]
    checked: dict[str, str] = field(default_factory=dict)
    results: dict[str, Outcome] = field(default_factory=dict)
    trial_done: bool = False
    cancel_times: list[float] = field(default_factory=list)


class Store:
    def __init__(self, dir: Path):
        self.dir = Path(dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, account: str) -> Path:
        return self.dir / f"progress_{account}.json"

    @staticmethod
    def _read(path: Path) -> Progress | None:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            d["results"] = {k: Outcome(v) for k, v in d.get("results", {}).items()}
            known = {f.name for f in fields(Progress)}
            return Progress(**{k: v for k, v in d.items() if k in known})
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def load(self, account: str) -> Progress | None:
        return self._read(self._path(account))

    def save(self, p: Progress) -> None:
        d = asdict(p)
        d["results"] = {k: v.value for k, v in p.results.items()}
        path = self._path(p.account)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

    def start(self, account: str, usernames: list[str]) -> Progress:
        """Yeni bir ZIP için temiz kayıt. Saatlik sınır için eski geri çekme zamanları korunur."""
        old = self.load(account)
        p = Progress(account=account, usernames=list(usernames),
                     cancel_times=list(old.cancel_times) if old else [])
        self.save(p)
        return p

    def pending_work(self, p: Progress) -> list[str]:
        return [u for u in p.usernames if u not in p.results]

    def latest_unfinished(self) -> Progress | None:
        files = sorted(self.dir.glob("progress_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        for f in files:
            p = self._read(f)
            if p and self.pending_work(p):
                return p
        return None
