# 0.1.1 kaynak yayın paketi denetimleri

27 Kasım 2026. Bu paket GitHub'a gönderilmeden önce yerel olarak hazırlanmıştır.

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
- Bu makinede Docker Engine bulunmadığından yeni workflow'un Docker smoke
  adımları yerelde çalıştırılamaz. Önceki 0.1.1 amd64 imajı kullanıcı NAS'ında
  derlendi ve BookOrbit üzerinden sınandı; yeni genel ayarların CI çalışması
  depoya yüklemeden sonra ayrıca doğrulanmalıdır.
- ARM64 fiziksel cihazda denenmedi. GHCR imajı henüz yayımlanmadı.
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
