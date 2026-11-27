# Doğrulama kaydı

> 0.1.2 adayı için güncel 92 test, API ve canlı süreç kayıtları:
> [İnceleme denetimi](REVIEW-AUDIT-0.1.2.md). Aşağıdaki bölüm yayımlanmış
> 0.1.1 sürümünün tarihsel doğrulamasıdır.

Tarih: **27 Kasım 2026**. Sürüm: **0.1.1 / erken beta**.
Resmi API gereksinimleri uygulama geliştirilmeden önce incelendi.

## Resmi kaynaklar

| Kaynak | İncelenen revizyon |
| --- | --- |
| [BookOrbit](https://github.com/bookorbit/bookorbit/tree/54cba36e0914f307e2c9d82571d04e626f1586e1) | `54cba36e0914f307e2c9d82571d04e626f1586e1` |
| [External Provider API](https://github.com/bookorbit/bookorbit/blob/54cba36e0914f307e2c9d82571d04e626f1586e1/docs/BUILDING_METADATA_PROVIDERS.md) | Uçlar, alanlar, hata ve yetenek bildirimi |
| [Kurulum rehberi](https://github.com/bookorbit/bookorbit/blob/54cba36e0914f307e2c9d82571d04e626f1586e1/docs/METADATA_PROVIDERS.md) | Ortak ağ ve private address ayarı |
| [HTTP istemcisi](https://github.com/bookorbit/bookorbit/blob/54cba36e0914f307e2c9d82571d04e626f1586e1/server/src/modules/metadata-http-provider/http-provider.client.ts) | 2 MiB yanıt, URL-encoded kimlik, HTTP durumları |
| [Alan eşlemesi](https://github.com/bookorbit/bookorbit/blob/54cba36e0914f307e2c9d82571d04e626f1586e1/server/src/modules/metadata-fetch/providers/http/http-metadata-provider.ts) | pages/pageCount, languageCode/language, tarih ve ISBN |
| [Resmi sağlayıcı deposu / LubimyCzytac](https://github.com/bookorbit/bookorbit-metadata-providers/tree/30a5ef4aca62beb93561fac8333d0a926a77e365) | `30a5ef4aca62beb93561fac8333d0a926a77e365` |
| [Moly](https://github.com/FlyinPancake/bookorbit-moly-provider/tree/a41cdce5a92dabd0da0de2034db40f53c75446e4) | `a41cdce5a92dabd0da0de2034db40f53c75446e4` |

Moly ve LubimyCzytac tasarım referansı olarak okundu, uygulama kodları kopyalanmadı.
Resmi MIT lisanslı conformance aracı değiştirilmeden alındı. Git blob özeti:
`284c9b37be011c8d9cc8b4e73268fd612d6ccc42`; lisansı yanında korunur.

## Sözleşme

`GET /provider/info`, `GET /search`, `GET /book/{providerId}` desteklenir.
Kalıcı sağlayıcı anahtarı `turkish-metadata` ve kaynak kimliği
`kitapyurdu:<sayısal-kimlik>` biçimi korunur.
Arama yanıtı `matches` dizisi ve gerekirse `partial: true` içerir.
`providerId` ve `title` zorunlu; yıl metin, sayfa sayısı sayı, yazarlar dizidir.
BookOrbit üst sınırı 50 sonuç / 2 MiB'dir; uygulama daha küçük varsayılanlar kullanır.
BookOrbit timeout ayarı 2–30 saniyedir; bu sağlayıcının 12 saniyelik bütçesi için
15 saniye veya üzeri önerilir. `translators` mevcut resmi alan eşlemesinde yoktur.

## Otomatik ve canlı doğrulama

73 çevrimdışı uygulama testi; API sözleşmesi, UTF-8, ISBN doğrulama, yazar/baskı
eşlemesi, önbellek/TTL/boyut, süre/kısmi sonuç, 400/401/404/429/502/503,
Retry-After, robots, yönlendirme, kaynak aralığı ve yanıt boyutunu kapsar.
Yayın hazırlığına ait ek denetimler [RELEASE-CHECKS.md](RELEASE-CHECKS.md) içindedir.

0.1.1 canlı testinde boş önbellekle başlık `Şehit!`, yazar `Kaveh Akbar`,
ISBN `9786255539007` sorgusu **9,297 saniyede** 200 döndü.
Sonuç `kitapyurdu:711075`, Holden Kitap, 424 sayfa, 2025-02-27,
çevirmen Berkan M. Şimşek; `partial: false`.
ISBN'siz başlık+yazar da aynı kaydı buldu.
[Canlı kayıt](live-verification-0.1.1.json);
[resmi uygunluk çıktısı](conformance-0.1.1.txt): **0 hata, 0 uyarı**.

0.1.0 tarihsel çıktıları:
[canlı test](live-verification.json), [conformance](conformance-final.txt).
Bunlar güncel test sayısı veya yeni sürümün yerine geçmez.
Yalnız ISBN'li soğuk kaynak araması bazı baskılarda boş döndü;
bu kaynak indeksi sınırlaması devam eder. [Kaynak incelemesi](SOURCE_ACCESS.md).

## Gerçek NAS ve BookOrbit denemesi

Kurulumu yapan kullanıcı Synology DS224+ üzerinde 0.1.1 derlemesini
**Exit Code: 0** ile tamamladı, çalışan konteyner ve sürüm doğrulandı.
BookOrbit'te birkaç kitapta elle arama doğru göründü. Tek kitapta Field Rules
üzerinden Auto-fill çalıştı; açıklama ve yayınevi doğrulanıp kaydedildi.
Bu, sınırlı kullanıcı kabul testidir; kütüphane çapında regresyon testi değildir.

## GitHub CI ve herkese açık imaj

[Tests çalışması](https://github.com/firatkupeli/bookorbit-turkish-metadata-provider/actions/runs/46026742807)
ve [v0.1.1 yayın çalışması](https://github.com/firatkupeli/bookorbit-turkish-metadata-provider/actions/runs/46027864425)
başarılı tamamlandı. Yayındaki `verify / test` işi Ruff, çevrimdışı testler,
resmi conformance aracı, Docker build ve salt okunur konteyner kontrollerini geçti.
Bu CI testi gerçek Kitapyurdu erişimine bağlı değildir.

Herkese açık imaj:

```text
ghcr.io/firatkupeli/bookorbit-turkish-metadata-provider:0.1.1
```

`linux/amd64` ve `linux/arm64` manifestleri ile bütün katmanları, kullanıcı adı,
kişisel erişim anahtarı, Docker oturumu veya tarayıcı oturumu kullanmadan
GHCR Registry API üzerinden indirildi. Manifest/katman SHA-256 özetleri doğrulandı.
Toplam 19 benzersiz blob ve 103655581 bayt doğrulandı.
[Makinece okunabilir test kaydı](public-pull-verification-0.1.1.json).

Çok mimarili imajın index özeti:

```text
sha256:61c611164a951ebd879989dafa2c43576daf5b14baf13a5d3f3b8a01fbc00fb1
```

Bu indirme testi, yayımlanan imajın çalıştırılması anlamına gelmez.
amd64 Docker çalışma kontrolleri GitHub CI'da geçti; NAS/BookOrbit denemesi
yukarıda ayrı kayıtlıdır. ARM64 fiziksel cihazda çalışma testi yapılmamıştır.
Bu çalışma bilgisayarında Docker Engine bulunmamaktadır.
