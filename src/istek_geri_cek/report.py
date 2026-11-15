"""Kullanıcının gönderebileceği düz metin rapor (çerez/şifre içermez)."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from . import config, strings
from .store import Outcome, Progress


def build_report(p: Progress, version: str, extra: str = "") -> str:
    lines = [f"İstek Geri Çek {version}", f"Tarih: {datetime.now():%Y-%m-%d %H:%M}",
             f"Hesap: @{p.account}", f"Toplam: {len(p.usernames)}", f"Deneme yapıldı: {p.trial_done}", ""]
    for o in Outcome:
        lines.append(f"{strings.OUTCOME_LABELS[o.value]}: {sum(1 for v in p.results.values() if v is o)}")
    lines.append(f"İşlenmedi: {len([u for u in p.usernames if u not in p.results])}")
    for o in (Outcome.FAILED, Outcome.NOT_FOUND, Outcome.ACCEPTED):
        names = [u for u, v in p.results.items() if v is o]
        if names:
            lines += ["", f"{strings.OUTCOME_LABELS[o.value]}:"] + [f"  @{u}" for u in names]
    if extra:
        lines += ["", "Teknik ayrıntı:", extra]
    log = config.data_dir() / "log.txt"
    if log.exists():
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
        lines += ["", "Günlük (son satırlar):"] + tail
    return "\n".join(lines) + "\n"


def _desktop() -> Path:
    return Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"


def save_report(text: str) -> Path:
    name = f"IstekGeriCek-rapor-{datetime.now():%Y%m%d-%H%M}.txt"
    for folder in (_desktop(), config.data_dir()):
        try:
            if folder.is_dir():
                path = folder / name
                path.write_text(text, encoding="utf-8")
                return path
        except OSError:
            continue
    raise OSError("rapor kaydedilemedi")
