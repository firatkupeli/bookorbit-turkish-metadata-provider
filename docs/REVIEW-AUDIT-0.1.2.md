# 0.1.2 inceleme denetimi

Durum: **0.1.2 erken beta yayımlandı — 27 Kasım 2026**.
Bu dosya, yayın öncesi yerel doğrulamaları ve aşağıdaki yayın sonrası
kontrolleri ayrı ayrı kaydeder. 0.1.1 sürümünün tarihsel kayıtları korunur.

## İncelemenin kaynağı

[PR #10 ilk inceleme](https://github.com/bookorbit/bookorbit-metadata-providers/pull/10#pullrequestreview-5986640708)
ve [ikinci inceleme](https://github.com/bookorbit/bookorbit-metadata-providers/pull/10#pullrequestreview-6008805414)
bu sağlayıcının kendi kaynak sözleşmesine göre değerlendirildi. Diğer
sağlayıcıların uygulama kodu alınmadı.

## Bulgular ve sonuçlar

| Konu | Bizim sağlayıcıdaki sonuç |
| --- | --- |
| Yeniden başlatma sonrası kimlik | `kitapyurdu:<ürün-id>` doğrudan kaynağa çözümlenir; arama/önbellek gerekmez. Yeni uygulama ömründe ilk işlem olarak lookup testi eklendi. |
| Wire alanları | `pages`, `languageCode`, `isbn13` / `isbn10` kullanılıyor; Field Rules adlarıyla karıştırılmıyor. Mevcut sözleşme testleri geçti. |
| Çevirmenler | Ayrı `translators` uzantısı; yazarlara eklenmiyor, BookOrbit'in alan desteği olarak bildirilmez. |
| Açıklama | Düz metne çevrilir, paragraflar korunur. İçindekiler bölümü ayrıca eklenmez. |
| ISBN yer tutucusu | **Düzeltildi:** checksum'dan geçen `0000000000` reddedilir; uydurma ISBN-13'e dönüştürülmez. |
| ISBN karakterleri | **Düzeltildi:** ISBN alanlarına ASCII dışı rakamlar kabul edilmez. |
| Geçersiz ISBN + metin | **Düzeltildi:** başlık/yazar varsa metin araması sürer. Geçersiz ISBN-only isteği 400 döner. |
| Geçerli ISBN + başlık | ISBN önce aranır; yedek metin aramasında da aynı ISBN'li baskı zorunluluğu korunur. |
| Hata + 429 | **Düzeltildi:** önceki 502, daha sonra gelen 429 ve `Retry-After` bilgisini gizlemez. Hata başarılı boş sonuç gibi önbelleğe alınmaz. |
| Tarih ve dil | Gözlenen Türkçe/ISO tarihler ISO biçimine çevrilir. Kaynakta baskı dili yoksa alan atlanır; Türkçe varsayılmaz. |
| Kapak | **Düzeltildi:** gözlenen daha büyük JSON-LD görseli seçilir; geçersiz/eksik bağlantıda güvenilir kaynak popup URL'sine dönülür. |
| Media types / renk | API ve katalog `book` / `#00866a` ile uyumlu. Puan/seri/tür/sesli kitap desteği iddia edilmez. |
| İstek ve gövde sınırı | Kaynak başına sıralama, iki saniyelik aralık, 2 MiB gövde sınırı, en fazla beş ayrıntı ve toplam 12 saniye korunur. |
| Sıralama / yazar | Yazar ve başlık önceliği korunur. Bilinen farklı yazarları eleme davranışı, önceki yanlış kitap regresyonunu önlediği için kaldırılmadı. Farklı dildeki aliaslar ISBN'siz aramada sonuç vermeyebilir; README'lerde açıklandı. |
| Rust'a özgü kurallar | Rust sabiti/Cargo sürümü ve crate kodu maddeleri uygulanmaz. Python proje, API sürümü, Compose/env ve lock sürümleri birlikte güncellendi. |

## Canlı görsel kontrolü

Kaynak HTML'de zaten bulunan bağlantılar, görsel sunucusunun robots.txt
kurallarına göre ve istekler arasında iki saniye bırakılarak kontrol edildi.

| Ürün | JSON-LD `wi:800` bağlantısı | Popup `mh:1000` bağlantısı |
| --- | --- | --- |
| Şehit! / 711075 | 800 × 1248, HTTP 200 | 638 × 995, HTTP 200 |
| Otomatik Portakal / 51855 | 800 × 1358, HTTP 200 | 346 × 587, HTTP 200 |

URL dönüştürme veya tahmini boyut parametresi üretilmez; uygulama yalnız
sayfada bulunan güvenilir `img.kitapyurdu.com` bağlantılarını seçer.
Bu gözlem bütün kitapların orijinal görsel kalitesi için garanti değildir.

## Test durumu

- 0.1.1 başlangıcı: 73 test geçti.
- Yeni 19 regresyon senaryosu eklendi; toplam **92 test geçti**.
- İlk 16 yeni senaryonun 10'u ve büyük kapak testi, ilgili düzeltmelerden
  önce hataları yeniden üretti.
- Bir Starlette/httpx eskime uyarısı mevcut; test hatası değildir.
- Docker derlemesi ve salt okunur konteyner kontrolleri GitHub CI içinde geçti.
  Yerel bilgisayarda Docker Engine kullanılmadı.
- Gerçek ARM cihaz testi yapılmadı.
- Kimlik anahtarı `turkish-metadata` ve eski kitap kimlikleri değişmedi.

## API ve canlı süreç doğrulaması

- [Resmi uygunluk aracı](conformance-offline-0.1.2.txt), fixture HTTP servisine
  karşı 0 hata / 0 uyarı ile tamamlandı.
- [Canlı kaynak kaydı](live-verification-0.1.2.json): soğuk başlık+yazar+ISBN
  araması Şehit! / Kaveh Akbar / 9786255539007 / 424 sayfa kaydını döndürdü.
- Yerel sağlayıcı süreci kapatılıp yeni süreç başlatıldı. Başka arama yapılmadan
  ilk kitap isteği olarak aynı kimlikle lookup 200 ve aynı başlık döndürdü.
- Geçersiz ISBN + metin araması doğru baskıyı döndürdü; geçersiz ISBN-only 400.
- Bunlar yeni kaynak kodun yerel Uvicorn süreçlerindeki kontrolleridir;
  yayımlanmış 0.1.2 Docker imajı/ARM cihaz testi olarak sunulmaz.

## Yayın sonrası doğrulama

- [v0.1.2 Pre-release](https://github.com/firatkupeli/bookorbit-turkish-metadata-provider/releases/tag/v0.1.2) yayımlandı.
- [Publish container](https://github.com/firatkupeli/bookorbit-turkish-metadata-provider/actions/runs/46052947375) içindeki `verify / test` ve `publish` işleri başarılı.
  Yayımlanan kod revizyonu: `5f2ffc356137e3c5c10e1c6bdf8f12aa49d5243e`.
- `ghcr.io/firatkupeli/bookorbit-turkish-metadata-provider:0.1.2` herkese açıktır.
  `latest` etiketi üretilmez; sürüm etiketi kullanılır.
- [Oturumsuz indirme kaydı](public-pull-verification-0.1.2.json): amd64 ve arm64
  için bütün katmanlar indirildi; 19 farklı blobun boyutu ve SHA-256 özeti doğrulandı.
  Kullanıcı hesabı/PAT kullanılmadı; yalnız anonim GHCR pull tokenı kullanıldı.
  Her iki imajın sürüm etiketi ve paketlenmiş uygulama sürümü `0.1.2`,
  konteyner kullanıcısı `10001:10001` olarak kontrol edildi.
- İmaj indeksi SHA-256:
  `sha256:d0d1a8d5da2ac4e7751e7e258c189335a77a62b4dba8dbbdac41cc266e1bee00`.
- Kurucu, Synology DS224+ üzerinde yayımlanan 0.1.2 imajıyla BookOrbit denemesini
  tamamladığını bildirdi. Bu, otomatik 92 testten ayrı bir kullanıcı denemesidir.
- Gerçek ARM donanımında çalışma testi yapılmadı. İmaj indirme ve katman
  doğrulaması, ARM donanımı üzerinde çalıştırma testi değildir.
- [Katalog PR #11](https://github.com/bookorbit/bookorbit-metadata-providers/pull/11)
  0.1.2 sürümüne güncellendi. Resmi listeye kabul, bakımcı incelemesine bağlıdır.
