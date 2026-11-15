"""Hız ayarları ve veri klasörü."""
import os
from pathlib import Path

CANCEL_DELAY = (40, 90)        # saniye, iki geri çekme arası (rastgele)
LOOKUP_DELAY = (3, 6)          # saniye, yalnızca kontrol sorguları arası
MAX_CANCELS_PER_HOUR = 60
NETWORK_BACKOFF = (10, 30, 60)  # ağ hatasında yeniden deneme beklemeleri
APP_NAME = "IstekGeriCek"


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    d = Path(base) / APP_NAME if base else Path.home() / ".istek_geri_cek"
    d.mkdir(parents=True, exist_ok=True)
    return d
