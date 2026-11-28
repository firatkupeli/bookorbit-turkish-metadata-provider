# EPUB web düzenleyicisi — 0.2.0 geliştirme notları

Bu belge 0.2.0 geliştirme dönemindeki kapsamı ve testleri kaydeder.
Güncel Künye 0.4.0 özellikleri ve NAS kullanıcı testleri için
[kullanım ve doğrulama rehberine](KUNYE_PREVIEW.md) bakın.

## Kullanım

Sağlayıcının kök adresini tarayıcıda açın. Aynı sunucunun 8080 portunda web
arayüzü ve BookOrbit API'si birlikte çalışır.

1. Bir `.epub`, `.kepub.epub` veya `.kepub` dosyası seçin veya bırakın. Mevcut metadata ve kapak okunur.
2. ISBN, kitap adı ve yazarla Kitapyurdu araması yapın.
3. ISBN, yazar ve yayıneviyle baskıyı kontrol edip sonucu seçin.
4. Aktarılacak alanları işaretleyin. **Yalnız boş alanları doldur** başlangıçta
   açıktır; mevcut dolu bir alanı değiştirmek için bu seçeneği kapatın.
5. İsterseniz kaynak kapağını seçin, alanları elle düzenleyin ve kitabı indirin.
6. İndirme biçiminde **Kobo KEPUB (.kepub.epub)** seçilirse normal EPUB, resmî
   Kepubify 5.0.0 WebAssembly ile bu tarayıcıda dönüştürülür. Orijinal biçimi
   koru seçeneğinde yalnız metadata yazılır. Mevcut KEPUB yeniden dönüştürülmez;
   Kobo span kimlikleri ve bölüm dosyaları korunur.

Başlık, yazarlar, çevirmenler, açıklama, yayınevi, yayın tarihi, dil ve ISBN
düzenlenebilir. Çevirmenler EPUB'ta `trl` katkı rolüyle yazılır. Sayfa sayısı
arama sonucunda bilgi olarak gösterilir; standart dışı bir EPUB alanı üretilmez.
Ana başlık düzenlenirken alt başlıklar ve diğer başlıklar korunur.

## Sunucu ve dosya davranışı

- EPUB 2 ve EPUB 3 paketlerinin OPF metadata belgesi düzenlenir. Metadata işleminde kitabın EPUB
  sürümü değiştirilmez. Bölüm dosyaları, sıralama, stiller ve fontlar korunur.
  Yeni KEPUB dönüşümünde Kobo için bölüm işaretlemesi ve gerekli paket düzeltmeleri
  yapılır; mevcut KEPUB'ın metadata düzenlemesinde bölüm içeriği değiştirilmez.
- Yeni dosya indirilir; kullanıcının yüklediği orijinal dosyaya yazılmaz.
- Her okuma ve indirme isteğinde dosya yeniden gönderilir. EPUB'lar oturum,
  önbellek veya bir veritabanında tutulmaz. Multipart geçici dosyaları istek
  sonunda kapatılır. Arama önbelleği kitap dosyası değil, kaynak metadata içerir.
- Kitapyurdu'na EPUB gönderilmez; yalnız ISBN, başlık ve yazar sorguları gider.
- `AUTH_TOKEN` ayarlıysa **Bağlantı ayarı** altında anahtarı girin. Tarayıcı
  anahtarı yalnız açık sekmede tutar; localStorage/cookie kullanılmaz.
- Yükleme ve indirme yolları aynı origin kontrolü, mevcut API kimlik doğrulaması
  ve istek sınırlamasını kullanır. Harici CDN veya font isteği yoktur. Kepubify JavaScript/WASM dosyaları sürümü
  sabitlenmiş olarak bu sunucudan sunulur; kitap üçüncü taraf dönüştürücüye gönderilmez.
- Kapak indirmeleri yalnız sabit HTTPS görsel kaynağına gider. Görsel sunucusunun
  robots.txt kuralları, bekleme aralığı, boyut sınırı ve 429 yanıtları uygulanır.
  Kaynaktan gelen yönlendirme farklı bir sunucuya gidemez.

## Sınırlar

- Tek EPUB: 25 MiB; açılmış arşiv: 128 MiB; en fazla 4.000 arşiv girdisi.
- XML: 2 MiB, en fazla 64 derinlik ve 20.000 düğüm. DTD ve entity reddedilir.
- JPEG/PNG kapak: 5 MiB. SVG veya farklı kapak türleri korunur; otomatik
  değiştirilmez. Font gizleme kimliği ve paket ana kimliği değiştirilmez.
- Ana kimliği ISBN olan bir kitabın ISBN'si bu sürümde değiştirilemez.
- Şifreli/DRM korumalı kitaplar ve dijital imzalı EPUB'lar düzenlenmez.
  Standart font obfuscation dosyaları ve kimlikleri korunur.
- ZIP girdileri dosya sistemine çıkarılmaz. Yinelenen, dışarı taşan, şifreli
  veya sembolik bağlantı girdileri reddedilir.
- Aynı anda bir EPUB okuma/yazma işlemi yapılır. Yükleme süresi 30 saniyeyle
  sınırlıdır. Bir sonraki istek çalışırken düzenleyici 429 döner.

Bu bir EPUB onarım veya tam EPUBCheck servisi değildir. Test edilen örneklerde
ZIP bütünlüğü, OPF alanları ve kitap içeriği korunması kontrol edilmiştir;
her okuyucu cihazı ve her yayıncı paketi için doğrulama iddia edilmez.

## Yerel çalıştırma

```sh
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8080 --workers 1 --no-access-log
```

Tarayıcıda `http://127.0.0.1:8080` adresini açın.
Docker kaynak derlemesinde `PROVIDER_IMAGE` boş bırakılır. Compose örnekleri,
multipart geçici dosyaları için `/tmp` alanını 64 MiB olarak ayırır.
256 MiB konteyner bellek sınırı korunur. Gerçek 0.2.0 Docker/NAS denemesi,
yayın iş akışındaki derlemeden sonra yapılmalıdır.

Ters proxy kullanılıyorsa gövde sınırını en az 26 MiB yapın; Nginx için örnek:

```nginx
client_max_body_size 26M;
```

## Doğrulama

- Python 3.12: 141 test geçti; Ruff biçim ve kod denetimleri geçti.
- Resmi BookOrbit API uygunluk aracı: [0 hata, 0 uyarı](conformance-offline-0.2.0.txt).
- [Tarayıcı ve canlı kaynak denemesi](web-editor-verification-0.2.0.json):
  yalnız üretilmiş örnek metin taşıyan bir EPUB yüklendi; Şehit! kaydı bulundu;
  metadata, çevirmen ve kaynak kapağı aktarıldı; yeni EPUB tarayıcıdan indirildi.
  Bölüm, font, ana kimlik ve diğer dosyalar karşılaştırıldı.
- Mobil genişlik ve masaüstü düzeni görüldü; tarayıcı konsolunda hata yoktu.
- Bunlar yerel Python/tarayıcı sonuçlarıdır; yayımlanmış Docker imajı veya NAS
  çalışma testi olarak sunulmaz.

Kaynak içeriğinin hak ve erişim koşulları için [kaynak erişimi](SOURCE_ACCESS.md).

## KEPUB doğrulaması

[Doğrulama kaydı](kepub-verification-0.2.0.json): gerçek EPUB → KEPUB dönüşümü,
Kobo span eklenmesi, metin ve ana kimlik korunması kontrol edildi. Tarayıcıdan
KEPUB indirildi; aynı dosya yeniden yüklenip metadata değiştirildi ve bölüm
dosyaları/Kobo span kimlikleri byte düzeyinde karşılaştırıldı. Fiziksel Kobo
cihazında okuma testi yapılmadı. Dönüşüm bir worker içinde en fazla 120 saniye
çalışır; çıktı 25 MiB'ı aşarsa veya kaynak kayıpsız dönüştürülemiyorsa hata gösterilir.

Docker imajına ek dönüştürücü program veya Go çalışma ortamı kurulmaz.
Vendored dosyalar, npm SHA-512 arşiv özeti ve dosya SHA-256 kayıtlarıyla doğrulandı.
