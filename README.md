# BookOrbit Turkish Metadata Provider

[English](README.en.md)

BookOrbit için Python 3.12 ve FastAPI ile geliştirilmiş, MIT lisanslı Türkçe
metadata sağlayıcısı. İlk kaynak **Kitapyurdu**; yeni kaynaklar ayrı adaptörlerle
eklenebilir. BookOrbit veya Kitapyurdu'nun resmi ürünü değildir.

**Durum: 0.1.1 / erken beta.** Resmi BookOrbit uygunluk denetimi geçti.
Synology DS224+ üzerinde derleme, BookOrbit bağlantısı, elle arama ve tek kitapta
Auto-fill akışı kullanıcı tarafından doğrulandı. Test kapsamı ve sınırlar:
[doğrulama kaydı](docs/VERIFICATION.md), [sürüm notları](CHANGELOG.md).

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
| Kapak | `cover` | Kaynaktaki gerçek görsel URL'si; proxy yapılmaz |
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

## Docker ile kurulum

Henüz herkese açık bir hazır imaj yayımlanmış olduğu varsayılmaz. Bu paket
kaynak koddan yerel derleme içindir. Docker Engine ve Compose v2 gerekir.

1. Bu deponun dosyalarını tek klasöre çıkarın.
2. `.env.example` dosyasını aynı klasörde `.env` adıyla kopyalayın.
3. `.env` içindeki `BOOKORBIT_NETWORK` değerini BookOrbit **sunucu
   konteynerinin** bağlı olduğu mevcut Docker ağıyla değiştirin.
   `bookorbit_default` yalnız örnektir. `PROVIDER_IMAGE` boş kalabilir.
4. Klasörde çalıştırın:

   ```sh
   docker compose config --quiet
   docker compose up -d --build
   docker compose ps
   ```

Compose mevcut ağı kullanır; yeni ağ veya veritabanı oluşturmaz. Port 8080
yalnız Docker ağına açılır. BookOrbit ve sağlayıcı aynı ağda olmalıdır.

**Synology Container Manager / DS224+:** Ortak ağ veya isteğe bağlı macvlan sabit
IP kurulumu için [adım adım Synology rehberini](docs/SYNOLOGY.md) kullanın.
Genel `compose.yaml` makinenin mimarisinde derler; DS224+ örneği amd64 seçer.
ARM64 için yayın iş akışı hazırlanmıştır; gerçek ARM cihaz testi yapılmamıştır.

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
| `PROVIDER_IMAGE` | Boş: yerel `bookorbit-turkish-metadata-provider:0.1.1` etiketi |
| `AUTH_TOKEN` | Boş: kimlik doğrulama yok; ayarlıysa Bearer gerekir |
| `USER_AGENT` | `BookOrbitTurkishMetadata/0.1.1`; mümkünse işletici iletişimi ekleyin |
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
göstermez. Ayrı admin paneli yoktur; ayarlar `.env` üzerinden yönetilir.
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
