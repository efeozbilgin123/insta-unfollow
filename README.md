# İstek Geri Çek

Instagram'da gönderilmiş ama kabul edilmemiş takip isteklerini geri çeken Windows uygulaması.
Kullanıcı kılavuzu: [docs/KULLANIM.md](docs/KULLANIM.md). Tasarım: `docs/superpowers/specs/`.

## Geliştirme

```bash
pip install -e ".[dev]"
pytest
```

Arayüzü gerçek Instagram olmadan denemek için: `ISTEK_FAKE=1 python -m istek_geri_cek`.

## Önemli: doğrulanmamış Instagram ayrıntıları

Endpoint'ler, header'lar ve APP_ID yalnızca `src/istek_geri_cek/instagram_api.py` içinde ve henüz
gerçek bir hesapla doğrulanmadı. İlk deneme deneme hesaplarıyla yapılmalı.

## Sürüm çıkarma

`src/istek_geri_cek/__init__.py` ve `pyproject.toml` içindeki sürümü artır, sonra:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

GitHub Actions Windows'ta `IstekGeriCek.exe`'yi derler, duman testini çalıştırır ve Release'e ekler.
