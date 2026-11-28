# Sürüm notları

## 0.4.0 — Erken beta yayın adayı

- Bilgisayardan veya sürükleyerek JPG/PNG kapak seçimi; görsel yeniden sıkıştırılmaz.
- Mevcut, kaynak ve elle yüklenen kapak için gerçek piksel ölçüsü, biçim ve dosya boyutu.
- Genel web metinleri kaynaktan bağımsız; sonuçlarda gerçek kaynak adı korunur.
- Kitapyurdu, deneysel 1000Kitap ve tüm etkin kaynaklar seçenekleri web arayüzünde.
- BookOrbit aynı sağlayıcı adresinden iki kaynağı ortak süre bütçesiyle arar;
  sonuçlar dengeli sıralanır, tek kaynak hatası diğerinin sonuçlarını engellemez.
- İki kaynağın kalıcı kitap kimlikleri desteklenir; sağlayıcı anahtarı korunur.
- Tek kaynak ve birleşik aramaların önbellek anahtarları ayrıdır; kitap önbelleği
  kaynak kimlikleriyle paylaşılır ve toplam boyut sınırı korunur.
- Kapak biçimi değişince dosya uzantısı ve XHTML/SVG/CSS referansları da güncellenir.
- Kullanıcı NAS kurulumunu ve testlerini tamamladığını bildirdi. Genel kaynak
  paketi kişisel IP/ağ bilgileri ve özel NAS YAML dosyaları içermez.
- GHCR imaj yayını ve GitHub CI, v0.4.0 etiketi oluşturulduğunda ayrıca doğrulanır.

## 0.3.0 — Künye / NAS deneme adayı

- Bağımsız Künye web arayüzü; mevcut BookOrbit sağlayıcı kimliği korunur.
- İsteğe bağlı EPUB 3 yükseltmesi ve yinelenen başlangıç kapaklarının düzeltilmesi.
- İndirilecek dosyadan okunan alan ve kapak karşılaştırması; incelemeden indirme başlamaz.
- İlk yüklenen metadata, kapak ve çıktı seçeneklerine geri dönme.
- Kaynak veya hazırlanmış çıktı için sınırlı kitap kontrol raporu.
- Eksik görseller, kırık bağlantılar, içindekiler ve arşiv yapısı denetlenir.
- EPUB ve KEPUB çıktıları tarayıcı belleğinde inceleme için tutulur; dosya sunucuda saklanmaz.
- [Önizleme kapsamı ve sınırlar](docs/KUNYE_PREVIEW.md).

## 0.2.0 — Yayımlanmamış geliştirme adayı

- Mevcut .kepub/.kepub.epub metadata düzenleme; Kobo span ve bölüm dosyaları korunur.
- Gerçek EPUB → KEPUB dönüşümü: Kepubify 5.0.0, tarayıcı worker'ında ve yerel WASM dosyalarıyla.

- Aynı FastAPI servisinde EPUB yükleme, metadata düzenleme ve indirme arayüzü.
- Kitapyurdu baskı seçimi, alan bazında aktarım ve varsayılan boş alanları doldurma.
- EPUB 2/3 için yazar, çevirmen rolü, Türkçe açıklama, yayınevi, tarih, dil ve ISBN.
- İsteğe bağlı kaynak JPEG/PNG kapağı; bölüm/font dosyaları ve ana kimlik korunur.
- Sınırlı ve kalıcı saklama yapmayan ZIP/XML işleme, aynı origin ve API token kontrolü.
- 141 yerel test ve resmi API uygunluk kontrolü geçti. Tarayıcıda canlı kaynakla
  örnek EPUB yükleme, aktarma ve indirme tamamlandı. Bu ilk arayüz daha sonra kullanıcı tarafından NAS ve Kobo üzerinde denendi.
- [Ayrıntılar](docs/WEB_EDITOR.md).

## 0.1.2 — 2026-11-27 / erken beta

- `0000000000` ISBN-10 yer tutucusu ve ASCII dışı ISBN rakamları reddedilir;
  kaynaktaki yer tutucu ISBN artık ISBN-13'e dönüştürülmez.
- Geçersiz ISBN yanında başlık/yazar varsa metin aramasına devam edilir.
  Yalnız geçersiz ISBN için 400 korunur; geçerli ISBN tam eşleşme şartı değişmez.
- Önceki 502 hatası, daha sonra gelen 429 ve `Retry-After` bilgisini gizlemez.
- Sayfada gerçekten bulunan daha büyük JSON-LD kapak URL'si önceliklendirilir;
  eksik/güvenilmeyen bağlantıda doğrulanmış kaynak popup URL'sine dönülür.
- Yeniden başlatma sonrası ilk işlem olarak kalıcı kimlikle lookup dahil
  19 yeni regresyon testi eklendi. Sağlayıcı anahtarı ve kimlik biçimi korunur.
- 92 otomatik test, resmi uygunluk denetimi ve Docker kontrolleri GitHub CI'da geçti.
- amd64/arm64 hazır imajları yayımlandı; katmanları oturumsuz indirilip doğrulandı.
- Kurucu, Synology DS224+ üzerinde 0.1.2 hazır imaj denemesini tamamladığını bildirdi.
- Denetim ayrıntıları: [REVIEW-AUDIT-0.1.2.md](docs/REVIEW-AUDIT-0.1.2.md).

## 0.1.1 — 2026-11-27

- `Şehit! / Kaveh Akbar` aramasında farklı yazarlara ait kitapların dönmesi düzeltildi.
  Yazar, kaynakta başlıkla birlikte aranır; kaynak önizlemelerindeki bilinen farklı
  yazarlar ayrıntı indirilmeden elenir ve kitap ayrıntısında tekrar doğrulanır.
- Kaynak listesindeki adaylar sonuç sınırı uygulanmadan önce yazar ve normalize
  başlık benzerliğine göre sıralanır. Türkçe karakterler ve başlıktaki apostrof
  farklılıkları karşılaştırmalarda normalleştirilir.
- ISBN araması kaynakta boş dönerse başlık+yazar araması denenir. Sonuç yine de
  istenen ISBN ile tam eşleşmek zorundadır. Soğuk önbellekte yalnız ISBN ile
  aramanın kaynak indeksi sınırlaması devam eder.
- 404 dönen bir aday istenen sonuç sayısını doldurmuş sayılmaz. Ayrıntı istekleri
  kaynak başına `MAX_RESULTS` ve toplam süre bütçesiyle sınırlı kalır.
- Varsayılan süre bütçesi 12 saniyeye çıkarıldı. BookOrbit için 15 saniye veya üzeri
  timeout kullanın. Kaynak istekleri arasındaki 2 saniyelik aralık korunur.
- Synology Compose dosyasında desteklenmediği gözlenen CPU/PID kotaları kullanılmaz;
  256 MiB bellek sınırı kullanılır. Mevcut ağ adı ve sabit IP kullanıcı ayarlarıdır.
- 73 çevrimdışı test geçti. Gerçek Kitapyurdu kaynağıyla boş önbellek testi,
  `Şehit!` ISBN `9786255539007` için Kaveh Akbar / Holden Kitap kaydını 9,297 saniyede
  döndürdü; önceden doğrudan kitap lookup yapılmadı. Resmi conformance: 0 hata, 0 uyarı.
- Yayın paketi: kişisel ağ değerleri kaldırıldı; genel ve macvlan env örnekleri,
  Türkçe/İngilizce belgeler, çevrimdışı CI ve isteğe bağlı GHCR yayın iş akışı eklendi.
  0.1.1 NAS kurulumu ile sınırlı BookOrbit elle arama / Auto-fill denemesi doğrulandı.

## 0.1.0

İlk FastAPI sağlayıcısı, Kitapyurdu HTML adaptörü, Docker paketleri ve resmi
BookOrbit sözleşmesi testleri.
