# 0.1.2 inceleme denetimi

Durum: **yayımlanmamış aday**. Bu dosya yerel doğrulama sonuçlarını kaydeder;
0.1.2 imajının GHCR'da bulunduğu veya GitHub CI'nın bu sürümü çalıştırdığı
iddia edilmez. Yayımlanmış 0.1.1 imajı ve katalog PR #11 değiştirilmedi.

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
- Yeni Docker imajı henüz oluşturulmadı; bu bilgisayarda Docker Engine yoktur.
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

## Yayın sırası

1. Kaynak değişikliklerini kendi sağlayıcı deposuna yükleyin ve CI'yı bekleyin.
2. CI geçince yeni `v0.1.2` erken beta sürümünü yayımlayın.
3. GHCR 0.1.2 imajının iki mimarisini ve anonim indirmeyi doğrulayın.
4. NAS'ta yayımlanmış hazır imaja geçip BookOrbit Test/Search fresh uygulayın.
5. Mevcut katalog PR #11'in sürümünü ve test açıklamasını 0.1.2'ye güncelleyin.
   Bu kayıt, henüz bulunmayan bir imaja yönlendirilmemelidir.
