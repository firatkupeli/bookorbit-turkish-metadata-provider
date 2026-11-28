# v0.4.0 — Künye: EPUB / KEPUB Atölyesi

Bu metin v0.4.0 GitHub Release açıklaması için hazırlanmıştır.
Sürüm erken beta olarak **Pre-release** işaretlenmelidir.

## Yenilikler

- Künye web arayüzünde EPUB / mevcut KEPUB metadata düzenleme.
- Kitapyurdu ve deneysel 1000Kitap arasında kaynak seçimi.
- BookOrbit'te aynı sağlayıcı bağlantısıyla iki kaynaktan birleşik arama;
  dengeli sonuç sırası ve kaynak hatalarında kısmi sonuç desteği.
- Manuel JPG/PNG kapak yükleme; mevcut, kaynak ve yüklenen görselin gerçek
  piksel ölçüsü, biçim ve dosya boyutunu gösterme.
- İndirilecek dosyadan okunan önce/sonra metadata ve kapak karşılaştırması.
- İsteğe bağlı EPUB 3 yükseltmesi, EPUB → Kobo KEPUB dönüşümü ve kitap kontrol raporu.
- Yinelenen başlangıç kapaklarının düzeltilmesi; kapak biçimi değiştiğinde
  dosya uzantısı ile XHTML/SVG/CSS referanslarının güncellenmesi.
- İlk yüklendiği bilgilere geri dönme. Kitap dosyaları işlem sonrası sunucuda saklanmaz.

## Uyumluluk ve doğrulama

- BookOrbit sağlayıcı anahtarı `turkish-metadata` ve mevcut Kitapyurdu kitap
  kimlikleri korunur. `1000kitap:<id>` kayıtlarına doğrudan erişim desteklenir.
- 189 otomatik test, Ruff ve resmî BookOrbit uygunluk denetimi geçti.
- Üretilmiş EPUB 3 ve KEPUB örnekleri EPUBCheck 5.4.0'dan 0 hata / 0 uyarıyla geçti.
- Kurucu NAS kurulumunu ve kullanıcı kabul testlerini tamamladığını bildirdi.
- Güncel kapsam: [Künye rehberi](KUNYE_PREVIEW.md) ve
  [makinece okunabilir test kaydı](preview-verification-0.4.0.json).
- GitHub CI, imaj derlemesi, paket görünürlüğü ve oturumsuz indirme sonuçları
  yayın sırasında ayrıca doğrulanmalıdır; bu not bunların tamamlandığı iddiasını içermez.

## Kurulum ve sınırlar

- Kurulum için [Türkçe README](../README.md) veya [English README](../README.en.md).
- Yayın işi başarıyla tamamlandığında tam sürüm imaj etiketi
  `ghcr.io/firatkupeli/bookorbit-turkish-metadata-provider:0.4.0` kullanılır.
- 1000Kitap deneysel HTML kaynağıdır. Bazı baskıları bulmak için ISBN yanında
  başlık ve yazar da gerekir; kaynak erişimi ve süre bütçesine göre kısmi sonuç olabilir.
- Çevirmen bilgisi web editöründe bulunur; BookOrbit mevcut eşlemesinde bu alanı içe aktarmaz.
- Fiziksel ARM64 cihaz testi yapılmadı. Her kitap ve okuyucu için uyumluluk garantisi verilmez.
- MIT lisansı proje kodunu kapsar. Üçüncü taraf metadata ve kapakların hakları
  ilgili sahiplerine aittir; [kaynak erişimi incelemesi](SOURCE_ACCESS.md).
