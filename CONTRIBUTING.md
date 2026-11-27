# Katkıda bulunma

Hata bildirirken sürümü, arama türünü, beklenen baskıyı ve kimliksizleştirilmiş
hata çıktısını ekleyin. Token, gerçek .env, kişisel kitaplık URL'si, LAN adresi
ve tam günlük paylaşmayın. Kitapyurdu sayfa biçimi değiştiğinde küçültülmüş
örnek ve ilgili ayrıştırıcı testi tercih edilir.

## Geliştirme ortamı

Python 3.12+ gerekir. Sanal ortamı etkinleştirdikten sonra:

```sh
python -m pip install -r requirements.txt -r requirements-dev.txt
ruff check .
ruff format --check .
python -m pytest -q
python tools/prepare_release.py --check-only
```

Alternatif: `uv sync --locked` ve komutları `uv run` ile çalıştırın.
Uygulamayı `python -m uvicorn main:app --host 127.0.0.1 --port 8080` ile
başlatabilirsiniz. Bu normal uygulama gerçek kaynağa istek gönderir.

## Resmi uygunluk aracı

API sözleşmesini kaynak siteye trafik göndermeden sınamak için ayrı terminalde:

```sh
python -m uvicorn tests.offline_app:app --host 127.0.0.1 --port 8099
```

Ardından Go kurulu ortamda:

```sh
go run ./tools/conformance/main.go -url http://127.0.0.1:8099 -query "Otomatik Portakal"
```

Bu fixture servisi yalnız test içindir; üretime kurulmaz. Canlı kaynağı kontrol
ederken normal uygulamayı kullanın, istek aralığını düşürmeyin ve sürekli canlı
test döngüleri oluşturmayın. CI testleri gerçek Kitapyurdu erişimine bağlı değildir.

## Yeni kaynak

1. Önce resmi API/HTML yollarını, kullanım koşullarını ve robots kurallarını doğrulayın.
2. `app/sources/base.py` arayüzüne uygun ayrı adaptör ekleyin.
3. `app/api.py` içindeki `create_app` kaynak kurulumuna adaptörü bağlayın.
   Çoklu kaynak sıralaması/bütçesini `app/service.py` içinde açıkça tasarlayın;
   yalnız yeni dosya eklemek otomatik çoklu kaynak desteği oluşturmaz.
4. Mevcut `turkish-metadata` anahtarını ve `kitapyurdu:` kimliklerini koruyun;
   yeni kaynak için ayrı kimlik öneki kullanın.
5. Gerçekte sağlayabildiğiniz alanları bildirin. Veri uydurmayın, çevirmenleri
   yazarlara eklemeyin, ISBN varsa baskı doğrulamasını gevşetmeyin.
6. Başarı, yanlış eşleşme, boş sonuç, 429, kaynak hatası ve süre sınırı testleri ekleyin.

`tests/fixtures` dosyalarını olabildiğince küçük tutun. Hesap, yorum, izleme
belirteci, betik ve gereksiz telifli içeriği taşımayın.
Sürüm değiştirirken `app/__init__.py`, `pyproject.toml`, Compose/env
varsayılanları ve `uv.lock` uyumlu olmalıdır.
