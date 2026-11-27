# Sürüm notları

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
