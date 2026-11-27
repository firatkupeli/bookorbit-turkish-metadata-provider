# Kitapyurdu erişim incelemesi

İnceleme: 27 Kasım 2026. Bu kayıt o gün doğrulanan yöntemi açıklar; koşulların
değişmeyeceğine veya bir içerik kullanım izni bulunduğuna ilişkin beyan değildir.

## Doğrulanan yöntem

Belgelenmiş, herkese açık bir resmi metadata API'si bulunamadı. Uygulama,
[Kitapyurdu ana sayfasında](https://www.kitapyurdu.com/) gözlenen arama bağlantısı
ve gerçek HTTP yanıtlarıyla doğrulanan şu HTML yollarını kullanır:

- Arama: `https://www.kitapyurdu.com/index.php?route=product/list&filter_name=...`
- Sayısal detay: `https://www.kitapyurdu.com/index.php?route=product/product&product_id=...`
- Kanonik örnek:
  [Otomatik Portakal](https://www.kitapyurdu.com/kitap/otomatik-portakal-ciltsiz/51855.html).
- Kitap JSON-LD'si ve görünür ürün alanları; kapakta sayfanın gerçek
  `img.kitapyurdu.com` URL'si. Kapak sağlayıcıdan proxy edilmez.

Gizli/mobil API, hesap oturumu, tahmini JSON uç noktası, CAPTCHA çözümü veya
403 engeli aşımı kullanılmaz. Aynı HTTPS origin'ine en fazla üç yönlendirme
izlenir; kaynak yanıtları 2 MiB ile sınırlıdır.

## Robots ve istek davranışı

[Metin sunucusunun robots.txt dosyası](https://www.kitapyurdu.com/robots.txt)
inceleme sırasında kullanılan arama/ürün yollarını engellemiyordu.
`/admin/`, `/system/`, `/image/`, `/img/`, `/download/` engelliydi.
[Görsel sunucusu](https://img.kitapyurdu.com/robots.txt) genel robotlara izin,
msnbot'a engel bildiriyordu. Görsel indirmeyi sağlayıcı yapmaz.

Uygulama robots.txt dosyasını çalışma sırasında önbellekli olarak denetler;
kurallar okunamazsa veya yol engellenirse ürün isteği göndermez.
Kaynak istekleri arasında varsayılan en az iki saniye vardır. 429 ve
Retry-After işlenir; hata halinde sınırsız yeniden deneme yapılmaz.
Önbellek ve toplam süre bütçesi gereksiz kaynak trafiğini azaltır.

## Kullanım koşulları ve haklar

İncelenen resmi sayfalar:
[Yardım](https://www.kitapyurdu.com/index.php?route=information/information&information_id=53),
[Hakkımızda](https://www.kitapyurdu.com/index.php?route=information/information&information_id=22),
[kayıt](https://www.kitapyurdu.com/index.php?route=account/register),
[KVKK](https://www.kitapyurdu.com/index.php?route=information/information&information_id=3).

Bu inceleme, otomatik metadata erişimi veya açıklama ve kapakların yeniden
kullanımı/dağıtımı için açık izin doğrulamaya yetmedi. **Erişim yöntemi
doğrulandı; kullanım ve yeniden dağıtım izni doğrulanmadı.**
robots.txt kuralları bu izinlerin yerine geçmez.

MIT lisansı proje kodu içindir. Üçüncü taraf metinler ve görseller hak
sahiplerine aittir. Depoda kapak dosyası, tam kaynak sayfa arşivi veya toplu
metadata veri seti yayımlanmaz; testlerde biçim doğrulaması için küçültülmüş
HTML parçaları bulunur. Bkz. [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
Yeni bir kaynak eklenirken aynı erişim ve koşul incelemesi ayrı yapılmalıdır.
