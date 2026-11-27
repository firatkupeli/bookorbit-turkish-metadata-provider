# 0.1.1 kaynak yayın paketi denetimleri

27 Kasım 2026. Yerel kaynak paketinin hazırlanması, GitHub CI ve herkese açık
imaj yayınına ait sonuçlar birlikte kaydedilmiştir.

- Kişisel LAN IP'si, ağ adı, alan adı ve kullanıcı klasörü bilgileri kaynak
  dosyalarından çıkarıldı; gerçek env dosyaları ve eski NAS arşivleri dışlandı.
- Ortak Docker ağı ve macvlan sabit IP kurulumları ayrı env örnekleriyle sunulur.
  Zorunlu ağ/IP değişkenleri eksikse Compose sessizce yanlış ağ seçmez.
- Python uygulama testleri, Ruff denetimleri ve resmi conformance aracı
  çevrimdışı fixture servisine karşı çalıştırılır.
- Kaynak ZIP'i izin listesiyle oluşturulur; dosya SHA-256 manifesti, arşiv
  bütünlük kontrolü ve ayrı ZIP SHA-256 dosyası içerir.
- GitHub Actions, sabit commit kimliklerine bağlanır. Kaynak yüklemesi testleri;
  sürüm etiketi ise testlerden sonra GHCR yayınını tetikler.
- Bu makinede Docker Engine bulunmadığından konteyner çalışma kontrolleri
  yerelde yapılmadı. GitHub CI'da Docker build ve salt okunur konteyner testi
  başarılı tamamlandı. Kullanıcının NAS/BookOrbit denemesi ayrı doğrulandı.
- GHCR'da amd64 ve arm64 imajları yayımlandı, paket Public yapıldı ve her iki
  mimarinin bütün katmanları oturumsuz indirilip SHA-256 ile doğrulandı.
  ARM64 fiziksel cihazda denenmedi.
- Kitapyurdu otomatik erişim ve içerik yeniden kullanımı için açık izin
  doğrulanmış değildir; bu durum README ve kaynak incelemesinde açıkça belirtilir.

## Yerel sonuçlar

| Kontrol | Sonuç |
| --- | --- |
| `python -m pytest -q` | 73 geçti; 1 Starlette/httpx eskime uyarısı |
| `ruff check .` / `ruff format --check .` | Başarılı |
| `uv lock --check` | Başarılı |
| Resmi checker → çevrimdışı fixture servisi | 0 hata, 0 uyarı |
| Compose 5.8.1 `config` | İki örnek de doğru değişkenlerle geçerli |
| Eksik ağ / eksik macvlan IP | Beklendiği gibi yapılandırma hatası |

Compose denetimi Docker Engine kullanmadan yapıldı; Windows CLI indirmesinin
SHA-256 özeti resmi Docker Compose GitHub release varlığıyla karşılaştırıldı.
Bu bir konteyner çalıştırma testi değildir. Uygunluk çıktısı:
[conformance-offline-0.1.1.txt](conformance-offline-0.1.1.txt).
Starlette uyarısı test hatası değildir ve gizlenmemiştir.
Statik sır taraması kapsamlı güvenlik denetimi sayılmaz.

## GitHub ve imaj yayını sonuçları

- [İlk Tests çalışması](https://github.com/firatkupeli/bookorbit-turkish-metadata-provider/actions/runs/46026742807): başarılı.
- [v0.1.1 Publish container](https://github.com/firatkupeli/bookorbit-turkish-metadata-provider/actions/runs/46027864425):
  `verify / test` ve `publish` başarılı.
- Türkçe README güncellemesinin
  [Tests çalışması](https://github.com/firatkupeli/bookorbit-turkish-metadata-provider/actions/runs/46029932482): başarılı.
- [v0.1.1 erken beta sürümü](https://github.com/firatkupeli/bookorbit-turkish-metadata-provider/releases/tag/v0.1.1)
  ve [public paket](https://github.com/users/firatkupeli/packages/container/bookorbit-turkish-metadata-provider)
  yayımlandı.
- [Anonim indirme kaydı](public-pull-verification-0.1.1.json):
  amd64 ve arm64 için manifestler, config ve tüm katmanlar doğrulandı.
- Bu sonuçlar, canlı kaynakta her sorgu/baskı veya gerçek ARM cihaz desteği
  için kapsamlı test yapıldığı anlamına gelmez.
