from pathlib import Path

from istek_geri_cek import report
from istek_geri_cek.store import Outcome, Progress


def _prog():
    p = Progress(account="efe", usernames=["a", "b", "c", "d", "e"])
    p.results = {"a": Outcome.CANCELLED, "b": Outcome.CANCELLED, "c": Outcome.ACCEPTED,
                 "d": Outcome.NOT_FOUND, "e": Outcome.FAILED}
    return p


def test_report_has_counts_and_no_secrets():
    text = report.build_report(_prog(), "0.1.0")
    assert "0.1.0" in text and "@efe" in text
    assert "Geri çekildi: 2" in text
    assert "Kabul etmiş (dokunulmadı): 1" in text
    assert "Hesap artık yok: 1" in text
    assert "Başarısız: 1" in text
    assert "e" in text.split("Başarısız")[-1]
    low = text.lower()
    assert "csrftoken" not in low and "sessionid" not in low


def test_save_report_falls_back_to_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "_desktop", lambda: tmp_path / "yok" / "Desktop")
    monkeypatch.setattr(report.config, "data_dir", lambda: tmp_path)
    path = report.save_report("merhaba")
    assert path.parent == tmp_path and path.read_text(encoding="utf-8") == "merhaba"
    assert path.name.startswith("IstekGeriCek-rapor-")
