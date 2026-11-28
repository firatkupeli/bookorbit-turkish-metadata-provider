# Künye — EPUB & KEPUB Atölyesi

[English](README.en.md)

> **0.4.0 / erken beta yayın adayı.**
> Manuel JPG/PNG kapak yükleme, mevcut/kaynak/yüklenen kapakların gerçek
> ölçüleri ve web arayüzünde kaynak seçimi eklendi. 1000Kitap deneysel kaynaktır.
> BookOrbit aynı sağlayıcı adresinden Kitapyurdu ve 1000Kitap'ı birlikte arar.
> EPUB 3, KEPUB ve indirmeden önce karşılaştırma korunur.
> [Kullanım ve sınırlar](docs/KUNYE_PREVIEW.md).
> BookOrbit API'si ve sağlayıcı kimliği korunur. NAS kurulumu ve kullanıcı
> testleri tamamlandı. Hazır 0.4.0 imajını kullanmadan önce bu sürümün
> **Publish container** işinin başarılı ve paketin Public olduğunu doğrulayın.

> Önceki **0.1.2** imajı yalnız eski sağlayıcıyı içerir; Künye web arayüzü ve
> 1000Kitap desteği için 0.4.0 gerekir. [Önceki sürüm denetimi](docs/REVIEW-AUDIT-0.1.2.md).

BookOrbit için Python 3.12 ve FastAPI ile geliştirilmiş, MIT lisanslı Türkçe
metadata sağlayıcısı. İlk kaynak **Kitapyurdu**; yeni kaynaklar ayrı adaptörlerle
eklenebilir. 0.4.0'da **1000Kitap** da deneysel olarak desteklenir.
BookOrbit veya metadata kaynaklarının resmi ürünü değildir.

BookOrbit'te `/search` iki kaynağı aynı toplam süre bütçesiyle arar; sonuçlar
kaynaklar arasında dönüşümlü sıralanır. Tek kaynak hata verirse diğerinin
sonuçları `partial: true` ile döner. `/book/kitapyurdu:<id>` kayıtları korunur;
`/book/1000kitap:<id>` de desteklenir. Tek sağlayıcı adresi ve aynı Field Rules
kullanılır. Web arayüzünde tek kaynak seçimi ayrıca çalışır.

**0.4.0 doğrulaması:** 189 otomatik test, Ruff ve resmî BookOrbit uygunluk
kontrolü geçti. Örnek EPUB 3 ve KEPUB çıktılarında EPUBCheck 5.4.0 hata veya
uyarı bildirmedi. Kurucu NAS kurulumunu ve testlerini tamamladığını bildirdi.
Bu, sınırlı kullanıcı kabul testidir; her kitap veya cihaz için garanti değildir.
ARM64 fiziksel cihaz testi yapılmadı. [Doğrulama kapsamı](docs/KUNYE_PREVIEW.md),
[makinece okunabilir kayıt](docs/preview-verification-0.4.0.json),
[sürüm notları](CHANGELOG.md).

## Kaynak erişimi

Belgelenmiş, herkese açık bir Kitapyurdu metadata API'si doğrulanamadı.
Sağlayıcı, gerçek HTTP yanıtlarıyla doğrulanan arama ve ürün **HTML sayfalarını**
JSON-LD ve HTML alanlarından okur. Tahmini API adresi, giriş bilgisi veya
CAPTCHA aşımı kullanmaz; çalışma sırasında robots.txt kurallarını denetler.

**Metadata otomasyonu ve açıklama/kapakların yeniden kullanımı için açık izin
doğrulanmış değildir.** robots.txt bir içerik lisansı değildir; MIT yalnız bu
projenin kodunu kapsar. Erişim yönteminin ve incelenen koşulların ayrıntıları:
[kaynak erişimi](docs/SOURCE_ACCESS.md), [üçüncü taraf bildirimleri](THIRD_PARTY_NOTICES.md).
Kendi kullanımınızın koşullara uygunluğunu kaynakla netleştirin.

## Desteklenen bilgiler

| Bilgi | API alanı | Not |
| --- | --- | --- |
| Başlık / yazar | `title`, `authors` | UTF-8 ve Türkçe karakter desteği |
| Açıklama | `description` | HTML temizlenir, düz metin döner |
| Kapak | `cover` | BookOrbit API'sinde gerçek URL; web editörü seçilen kapağı indirebilir |
| Yayınevi | `publisher` | Baskıya ait değer |
| Yayın tarihi / yılı | `publishedDate`, `publishedYear` | ISO tarih / dört haneli yıl |
| Sayfa sayısı | `pages` | BookOrbit destek bildirimi: `pageCount` |
| Dil | `languageCode` | Kaynakta doğrulanan dil |
| ISBN | `isbn13`, `isbn10` | Kontrol basamağı doğrulanır |
| Çevirmen | `translators` | Uzantı; BookOrbit henüz içe aktarmaz |

Yalnız kitap türü desteklenir. Subtitle, ilk yayın tarihi, seri, tür, puan ve sesli
kitap alanları bildirilmez. Eksik bilgiler uydurulmaz; çevirmenler yazarlara eklenmez.
Kitapyurdu yayın tarihi, eserin ilk yayın tarihi olarak yorumlanmamalıdır.

Arama başlık, yazar ve ISBN alır. ISBN verildiğinde yalnız tam ISBN eşleşmesi
döndürülür. ISBN'siz aramada bilinen farklı yazarlar elenir; başlık/yazar benzerliği
adayların sırasını belirler. Kaynağın indeksi bazı geçerli ISBN'lerde boş döner:
soğuk önbellekte **ISBN ile birlikte başlık ve yazarı da gönderin**. İndeksin
tamamı taranmaz; her sorgu için sonuç garantisi yoktur.
Geçersiz ISBN yanında başlık veya yazar varsa metin araması yapılır; yalnızca
geçersiz ISBN gönderilirse 400 döner. ISBN'siz aramada farklı dildeki yazar
aliasları eşleşmeyebilir; bu durumda doğrulanmış ISBN kullanın.

## Docker ile kurulum

Docker Engine ve Compose v2 gerekir. Genel pakette kişisel IP, ağ adı veya
hazır erişim anahtarı bulunmaz; mevcut ağınızı `.env` içinde belirtin.

### Kaynak koddan kurulum — 0.4.0

1. Kaynak dosyalarını tek klasöre çıkarın; `Dockerfile`, `app` ve `main.py`
   aynı kökte olmalıdır.
2. `.env.example` dosyasını `.env` adıyla kopyalayın.
3. `BOOKORBIT_NETWORK` alanına BookOrbit sunucu konteynerinin bağlı olduğu
   mevcut Docker ağını yazın. Bu alan örnek dosyada boş bırakılmıştır.
4. `PROVIDER_IMAGE` boşken proje klasöründe çalıştırın:

   ```sh
   docker compose config --quiet
   docker compose up -d --build
   docker compose ps
   ```

Compose mevcut ağı kullanır; yeni ağ veya veritabanı oluşturmaz. Port 8080
Docker ağına açılır. BookOrbit ve sağlayıcı aynı ağdan erişebilmelidir.
Web düzenleyicisi aynı servisin `/` adresindedir.

### Hazır 0.4.0 imajını kullanma

Bu yöntemi **v0.4.0 Publish container** işi başarıyla tamamlandıktan ve paket
Public olduktan sonra kullanın. İmaj adresi:

```dotenv
PROVIDER_IMAGE=ghcr.io/firatkupeli/bookorbit-turkish-metadata-provider:0.4.0
```

Kendi `.env` dosyanızda bu değeri ayarladıktan sonra:

```sh
docker compose config --quiet
docker compose pull
docker compose up -d --no-build
docker compose ps
```

Yayımlanmış Public imajı indirmek için GHCR oturumu veya kişisel token gerekmez.
`--no-build` hazır imaj yerine yerel kaynak derlenmesini önler.

### Synology DS224+

Ortak ağ veya macvlan kurulumu için [Synology rehberini](docs/SYNOLOGY.md) kullanın.
Ağ ve kullanılacak boş IP'yi kendi kurulumunuza göre girin. NAS kurulum
klasöründe yalnız seçtiğiniz Compose dosyasını `docker-compose.yml` adıyla
kullanın; alternatif örneği `.bak` olarak saklayabilirsiniz.
DS224+ örneği `linux/amd64` içindir. Yayın iş akışı amd64/arm64 imajlarını
hazırlar; fiziksel ARM64 çalışma testi yapılmamıştır.

## BookOrbit'e ekleme

Settings → Library → Metadata → Providers → External bölümünde sağlayıcı ekleyin:

| Ayar | Değer |
| --- | --- |
| Address | `http://turkish-metadata:8080` — ortak Docker ağı için |
| Authorization header | `AUTH_TOKEN` boşsa boş; ayarlıysa `Bearer <kendi-tokenınız>` |
| Allow private address | Açık |
| Timeout | 15 saniye veya üzeri |

Sabit macvlan IP kullanıyorsanız adresi kendi seçtiğiniz IP ve 8080 portuyla girin.
HTTPS/domain veya Web Station yerel Docker bağlantısı için gerekmez.
Önce **Test**, ardından ISBN'si bilinen tek kitapta elle arama yapın.

### Otomatik metadata / Field Rules

Sağlayıcıyı kullanılacak alanlara `+ Add` ile ekleyip ilk sıraya sürükleyin.
Yalnız sağlayıcıyı kaydetmek otomatik doldurmaya katılması için yeterli değildir.

| Field Rules alanı | Başlangıç önerisi |
| --- | --- |
| Description | Türkçe sağlayıcı ilk; **If provided** |
| Title, Authors, Book cover | Türkçe sağlayıcı ilk; **Fill gaps** |
| Publisher, ISBNs, Published year | Türkçe sağlayıcı ilk; **Fill gaps** |
| Language, Page count | Türkçe sağlayıcı ilk; **Fill gaps** |

**Fill gaps** mevcut dolu değeri korur. **If provided** kaynak değer döndürürse
mevcut değerin üzerine yazabilir. Description için öneri Türkçe açıklamayı
önceliklendirmek içindir; mevcut açıklamayı korumak istiyorsanız Fill gaps seçin.

Desteklenmeyen alanlara bu sağlayıcıyı eklemeyin. Kaydedin, tek kitapta
**Auto-fill** çalıştırın, baskı/ISBN/yayınevi/kapak sonuçlarını inceleyip **Save**
ile onaylayın. İlk denemeyi toplu kütüphane üzerinde yapmayın.

## Ayarlar ve işletim

| Değişken | Varsayılan / açıklama |
| --- | --- |
| `BOOKORBIT_NETWORK` | Kurulumunuza göre zorunlu mevcut ağ |
| `PROVIDER_IPV4_ADDRESS` | Yalnız macvlan örneğinde zorunlu boş sabit IP |
| `PROVIDER_IMAGE` | Boş: yerel `bookorbit-turkish-metadata-provider:0.4.0` etiketi |
| `AUTH_TOKEN` | Boş: kimlik doğrulama yok; ayarlıysa Bearer gerekir |
| `USER_AGENT` | `BookOrbitTurkishMetadata/0.4.0`; mümkünse işletici iletişimi ekleyin |
| `SOURCE_INTERVAL_SECONDS` | 2; kaynak istekleri arasındaki en az süre |
| `REQUEST_TIMEOUT_SECONDS` | 5; tek kaynak isteği süresi |
| `DEADLINE_SECONDS` | 12; toplam arama bütçesi |
| `SEARCH_CACHE_TTL` / `BOOK_CACHE_TTL` | 900 / 86400 saniye |
| `CACHE_MAX_BYTES` | 16777216; serileştirilmiş önbellek veri sınırı |
| `API_REQUESTS_PER_MINUTE` | 60; süreç genelinde giriş isteği sınırı |
| `MAX_RESULTS` | 5; arama üst sınırı |

Önbellek bellektedir; yeniden başlatınca sıfırlanır. Bir worker kullanılır;
kaynak isteklerinin sırası ve istek sınırları süreç içinde tutulur. Birden çok
kopya bağımsız sınırlar oluşturur. Konteyner salt okunur dosya sistemi, ayrı
kullanıcı ve 256 MiB bellek sınırıyla çalışır. CPU kotası gerektirmez.

`/healthz` süreç sağlığını bildirir; Kitapyurdu erişiminin başarılı olduğunu
göstermez. EPUB web editörü `/` adresindedir; sunucu ayarları `.env` ile yönetilir.
FastAPI'nin etkileşimli API belgesi `/docs` adresindedir.

## API ve geliştirme

- `GET /provider/info` — kalıcı anahtar `turkish-metadata`, sürüm, yetenekler.
- `GET /search?query=...&author=...&isbn=...&limit=5&mediaType=book`
- `GET /book/{providerId}` — örneğin URL-encoded `kitapyurdu:711075`.
- 400 geçersiz sorgu, 401 kimlik doğrulama, 404 bulunamadı, 429 istek sınırı,
  502/503 kaynak hatası. Süre bütçesi dolduğunda kısmi sonuç bildirilebilir.

Kurulum, internetsiz testler, yeni adaptör ekleme ve resmi uygunluk denetimi:
[CONTRIBUTING.md](CONTRIBUTING.md).
Güvenlik: [SECURITY.md](SECURITY.md).
Yayın hazırlama: [docs/PUBLISHING.md](docs/PUBLISHING.md).

## Lisans

[MIT](LICENSE). Üçüncü taraf metadata, açıklamalar ve kapakların hakları ilgili
sahiplerinde kalır. Kaynaklardan alınan içerik için MIT lisansı verilmez.
