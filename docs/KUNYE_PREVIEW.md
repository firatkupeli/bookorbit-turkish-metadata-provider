# Künye 0.4.0 — Kullanım ve doğrulama

Web arayüzünün adı **Künye — EPUB & KEPUB Atölyesi** olarak değişti.
BookOrbit sağlayıcı anahtarı `turkish-metadata`, API uçları, kimlik doğrulaması,
konteyner portu ve ağ yapılandırmaları korunur. Kullanıcı 0.4.0 NAS kurulumunu
ve testlerini tamamladığını bildirdi. Herkese açık GitHub/GHCR yayınının
kontrolleri ayrı yapılır; yerel/NAS sonucu CI sonucu olarak sunulmaz.

## Kapak yükleme ve kaynak seçimi

Kapak bölümünde **Mevcut kapağı koru**, **Kaynak kapağını kullan** veya
**Yüklediğim kapağı kullan** seçilir. Bilgisayardan dosya seçilebilir veya
kapak alanına bırakılabilir. Yalnız doğrulanan, tek kare JPG/PNG kabul edilir:
en çok 5 MiB ve 20 milyon piksel. Görsel yeniden boyutlandırılmaz veya
sıkıştırılmaz. EXIF yönü ölçülere yansıtılır. Mevcut, kaynak ve elle yüklenen
kapaklar gerçek piksel ölçüsü, biçim ve dosya boyutuyla gösterilir.
Karşılaştırma penceresi indirilecek dosyadaki kapağı ve ölçüsünü gösterir.

Web araması **Kitapyurdu**, **1000Kitap · Deneysel** veya **Tüm etkin kaynaklar**
ile yapılabilir. Kaynak değişince eski sonuçlar ve kaynak kapağı temizlenir;
elle düzenlenen alanlar korunur. 1000Kitap HTML araması ve JSON-LD alanlarını
okur; her baskı/ISBN bulunmayabilir. ISBN ile başlık ve yazar da girilmesi önerilir.
Kaynak hata verirse başka bir kaynağa sessizce geçilmez. Tüm kaynaklar seçeneği
kısmi sonuç durumunu bildirir. Amazon eklenmedi.

BookOrbit aynı sağlayıcı adresinden iki kaynağı birlikte arar. Sağlayıcı anahtarı,
port, kimlik doğrulaması ve mevcut `kitapyurdu:<id>` kayıtları korunur;
`1000kitap:<id>` kayıtları da arama ve doğrudan kitap erişiminde desteklenir.
İki kaynak ortak süre bütçesiyle çalışır; birinin yavaşlaması diğerini bekletmez.
Sonuç limiti kaynaklar arasında dönüşümlü paylaşılır. Aynı ISBN'in iki kaynak
kaydı farklı kaynak kapak/açıklamaları seçilebilsin diye ayrı kalır. Bir kaynak
hata verirse mevcut sonuçlar kısmi yanıtla döner; bu yanıt arama önbelleğine yazılmaz.
Her iki kaynak başarısızsa hata döner. Web'deki tek kaynak seçimi BookOrbit'in
birleşik aramasını veya önbelleğini değiştirmez.

### 0.4.0 doğrulaması — 2026-11-28

- 189 test geçti; test ortamındaki mevcut Starlette/httpx eskime uyarısı sürüyor.
- Aynı ISBN'in iki kaynak kaydı, iki yönlü hata toleransı, süre aşımındaki
  kısmi ilerleme, önbellek ayrımı ve yeniden başlatma sonrası kitap erişimi doğrulandı.
- Ruff, JavaScript sözdizimi, bağımlılık kilidi ve herkese açık paket denetimi geçti.
- Resmî BookOrbit uygunluk aracı: 0 hata, 0 uyarı; mevcut sağlayıcı anahtarı
  ve `kitapyurdu` kitap kimlikleri doğrulandı.
- Canlı 1000Kitap aramasında bir ISBN eşleşmesi ve 275 × 385 JPEG kaynak kapağı okundu.
- Birleşik BookOrbit API'sinde `Şehit!` ISBN `9786255539007` araması iki kaynaktan
  da 424 sayfalı kaydı döndürdü: `kitapyurdu:711075`, `1000kitap:482332`.
  12 saniyelik bütçe sonunda bulunan kayıtlar `partial: true` ile korundu.
- Tarayıcıda 1200 × 1800 JPEG yüklendi; kaynak kapağı ve mevcut 1 × 1 PNG ile
  ölçüler karşılaştırıldı. Manuel kapak otomatik seçildi.
- Gerçek EPUB 3 + KEPUB çıktısı incelemeden indirildi. Yüklenen JPEG baytları,
  kitap kimliği, Kobo işaretleri ve tek başlangıç kapağı doğrulandı.
- Hem EPUB 3 hem indirilen KEPUB için EPUBCheck 5.4.0: 0 hata, 0 uyarı.
- İlk bilgilere dönüş, kapakları temizledi ve özgün biçimi/sürüm seçimini geri getirdi.
  Tarayıcı konsolunda hata veya uyarı görülmedi.
- Kullanıcı 0.4.0'ın NAS'ta derlenip testleri geçtiğini bildirdi. Bu sonuç
  sınırlı kullanıcı kabul testidir. Fiziksel Kobo denemesi 0.3.0 için
  ayrıca bildirilmişti; 0.4.0 için bağımsız cihaz testi iddiası yapılmaz.

Makinece okunabilir kayıt: [preview-verification-0.4.0.json](preview-verification-0.4.0.json).

## Karşılaştırma, geri alma ve kitap kontrolü

1. EPUB/KEPUB'u yükleyin. İsterseniz **Yüklenen kitabı kontrol et** düğmesiyle
   kaynak dosyanın raporunu açın.
2. Metadata, kapak ve çıktı seçeneklerini belirleyin.
3. **Değişiklikleri incele** dosyayı hazırlar; gerekiyorsa tarayıcıda KEPUB'a
   dönüştürür. Hazırlanan dosya aynı sunucuda salt okunur biçimde yeniden
   okunur ve denetlenir. Metadata alanlarının ve kapağın önce/sonra görünümü,
   gerçek çıktının içinden alınır.
4. **İndir**, karşılaştırılan dosyanın aynısını tarayıcı belleğinden indirir;
   ikinci bir metadata yazma veya kaynak kapağı indirme işlemi yapılmaz.
5. **Düzenlemeye dön** pencereyi kapatır. Bir alan veya çıktı seçeneği
   değiştirilirse önceki hazırlanmış dosya geçersiz olur; yeni karşılaştırma
   oluşturulur.
6. **İlk bilgilere dön**, ilk yüklenen metadata ve kapak seçimini geri getirir;
   EPUB 3 anahtarını kapatır ve indirme biçimini orijinale döndürür.

Kitap kontrolü; ZIP bütünlüğünü, okuma sırasını, içindekiler kaydını,
XHTML/SVG/NCX ve CSS içindeki yerel kaynakları, eksik görselleri, bölüm içi
bağlantı hedeflerini ve yinelenen kapak sayfalarını denetler. Harici
bağlantılara istek atılmaz. İlk 100 bulgu gösterilir; büyük kitaplarda
denetim sınırına ulaşılması açıkça belirtilir. Rapor bir EPUBCheck
sertifikası veya görsel/cihaz uyumluluğu garantisi değildir.

EPUB'lar sunucuda saklanmaz. İnceleme için hazırlanmış tek dosya yalnız açık
tarayıcı sekmesinin belleğinde tutulur. Yeni dosya veya değişiklikle
geçersizleşir. Kapak önizlemesinden sonra kaynak görseli değişirse sessizce
farklı bir kapak kullanmak yerine baskının yeniden seçilmesi istenir.

### 0.3.0 yerel doğrulaması

- 167 otomatik test; Ruff biçim/kod ve JavaScript sözdizimi denetimleri geçti.
- Sabit örnek kaynak yanıtlarıyla gerçek tarayıcı akışında 7 değişen alan,
  kapak değişimi, EPUB 3 yükseltmesi ve çıktı raporu görüldü.
- Hem EPUB 3 hem KEPUB inceleme penceresinden indirildi. Geri alma; metadata,
  kapak, sürüm anahtarı ve çıktı biçimini sıfırladı. İkinci düzenlemede yeni
  başlık karşılaştırmada ve indirilen dosyada doğrulandı.
- Kullanıcı 0.3.0 NAS kurulumunu, BookOrbit aramasını, web arayüzünü ve fiziksel
  Kobo okumasını tamamladığını bildirdi. Bu sınırlı kullanıcı kabul testidir.
  Sonraki 0.4.0 NAS testleri de kullanıcı tarafından tamamlandı.

## EPUB 3 anahtarı

İndirme biçiminin altındaki **EPUB 3’e yükselt** anahtarı başlangıçta kapalıdır.
EPUB 2 kitapta açılırsa paket sürümü 3.0 olarak yazılır; EPUB 3 standardında
paket sürüm alanının değeri 3.0'dır. Zaten EPUB 3 kitapta anahtar devre dışıdır.
Normal EPUB veya Kobo KEPUB çıktısıyla kullanılabilir.

- NCX içindekilerin başlıkları, bağlantıları ve iç içe sıralaması `nav.xhtml`
  belgesine aktarılır; varsa basılı sayfa listesi de taşınır. Eski NCX korunur.
- NCX yoksa okuma sırası ve bölüm başlıklarından gezinme oluşturulur.
- Görseller, stiller ve fontlar yeniden sıkıştırılarak dönüştürülmez. Gerekli
  XHTML/metadata değişiklikleri yapılırken bölümün metni karşılaştırılır.
- Paket ana kimliği korunur. Kaynakta ana kimlik eksikse kaynak dosya özetinden
  deterministik UUID oluşturulur; eski NCX kimliği bu kimlikle eşitlenir.
- Yerel kaynaklar, bağlantı hedefleri ve bölüm içi kimlikler denetlenir.
- Dönüşüm kitap başına toplam 16 MiB bölüm XML'i, 250.000 element ve 50.000
  bağlantıyla sınırlıdır. Genel yükleme sınırı 25 MiB olarak kalır.
- Etkileşimli içerik, özel bağlantı tabanı ve bazı eski font/tablo düzenleri
  otomatik dönüştürülmez; kullanıcıya açıklama gösterilir. Bu genel bir EPUB
  onarım servisi veya her kitap için tam EPUBCheck uygunluğu garantisi değildir.

## Kapak düzeltmesi

Metadata'da kapağı tanımlanmamış kitaplarda açıkça kapak olarak adlandırılmış
veya işaretlenmiş, yalnız görsel içeren başlangıç sayfaları da incelenir.
Kaynak kapağı seçilirse bu sayfalar aynı kapak görseline bağlanır ve yinelenen
kapak sayfaları okuma sırasından çıkarılır. Eski dosyalar arşivden silinmez;
bu sayfalara bağlantılar kalan kapak sayfasına yönlendirilir. Metin içeren
sayfalar ve bölüm içi görseller kapak kabul edilerek kaldırılmaz. Kapak seçili
değilse orijinal okuma sırası korunur.

Kepubify'nin standart `epub:type` XML özniteliği için ürettiği bilgilendirme
uyarısı açıkça tanınır; diğer dönüştürme uyarıları çıktıyı durdurur.
Mevcut KEPUB yeniden Kobo dönüşümüne sokulmaz.

## Denemeler

2026-11-28: Python 3.12 altında 156 test geçti. Ruff ve JavaScript sözdizimi
denetimleri geçti. Üretilmiş bir EPUB 2 örneğiyle yinelenen kapak, iç içe
içindekiler, dipnot bağlantıları, Türkçe metin ve görsel/stil korunması
kontrol edildi. Resmî EPUBCheck 5.4.0, kapak düzeltilmiş EPUB 3 çıktısında
0 hata ve 0 uyarı bildirdi. Gerçek Kepubify 5.0.0 WASM dönüşümünde tek kapak,
bölüm metni ve kaynaklar doğrulandı. Yerel tarayıcıdan EPUB 3 ve KEPUB indirildi.

0.2.0'daki yinelenen kapak bulgusu bu çalışmayı tetikledi. Sonraki 0.3.0
kurulumu kullanıcı tarafından NAS, BookOrbit, web ve fiziksel Kobo'da denendi.
Bu sonuç, yeni 0.4.0 özelliklerinin cihaz testi yerine geçmez.
