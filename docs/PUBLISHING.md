# GitHub yayını ve sonraki sürümler

> **0.1.2 erken beta yayımlandı.** İki mimarinin katmanları oturumsuz
> indirilip doğrulandı. [Güncel denetim](REVIEW-AUDIT-0.1.2.md).

## Yayımlanmış sürüm

- [Kaynak depo](https://github.com/firatkupeli/bookorbit-turkish-metadata-provider)
- [v0.1.2 erken beta](https://github.com/firatkupeli/bookorbit-turkish-metadata-provider/releases/tag/v0.1.2)
- [Container paketi](https://github.com/users/firatkupeli/packages/container/bookorbit-turkish-metadata-provider)
- [Başarılı yayın iş akışı](https://github.com/firatkupeli/bookorbit-turkish-metadata-provider/actions/runs/46052947375)

Herkese açık imajın `PROVIDER_IMAGE` değeri:

```dotenv
PROVIDER_IMAGE=ghcr.io/firatkupeli/bookorbit-turkish-metadata-provider:0.1.2
```

amd64 ve arm64 imajları için oturumsuz indirme ve SHA-256 denetimi tamamlandı.
[Doğrulama kaydı](REVIEW-AUDIT-0.1.2.md),
[imaj indirme sonuçları](public-pull-verification-0.1.2.json).
Hazır imaj kurulumunda `docker compose pull`, ardından
`docker compose up -d --no-build` kullanın.
Genel kurulum [Türkçe README](../README.md) ve [English README](../README.en.md)
içindedir; GUI adımları [Synology rehberindedir](SYNOLOGY.md).

## Kaynak paketi oluşturma

```sh
python tools/prepare_release.py --check-only
python tools/prepare_release.py
```

Bu komutlar yerel ZIP üretir; GitHub veya GHCR'a yükleme yapmaz.
Araç yalnız izin verilen kaynak dosyalarını toplar, seçili özel adres/anahtar
desenlerini denetler ve `dist` altında kaynak ZIP'i ile SHA-256 dosyası oluşturur.
ZIP içindeki `RELEASE-MANIFEST.json` dosya özetlerini içerir.
.env, sanal ortam, önbellekler, eski arşivler ve yerel Compose override dosyaları
pakete alınmaz. Taramalar kapsamlı sır/güvenlik denetimi sayılmaz.

GitHub'a dosya yüklerken ZIP'i ayrı boş klasöre çıkarın ve proje kökünün
**dosyalarını** yükleyin. `.github`, `.gitignore` ve env örnekleri dahil
olmalıdır. Gerçek .env ve eski NAS arşivlerini eklemeyin.
Manifest bir dosya anlık görüntüsünü tarif eder; belgeler değiştirildiğinde
manifest de birlikte yenilenmelidir.

## Sonraki sürümü yayımlama

1. Uygulama, proje, Compose/env varsayılanları ve `uv.lock` sürümlerini
   uyumlu güncelleyin; testleri ve kaynak erişim/koşul incelemesini tamamlayın.
2. Değişiklikleri yükleyip GitHub Actions **Tests** sonucunun başarılı
   olmasını bekleyin.
3. Yeni uygulama sürümüyle eşleşen, başında `v` olan yeni etiket oluşturun.
   Mevcut sürüm etiketlerini başka commit'lere taşımayın.
4. Etiket testleri tekrar çalıştırır; **Publish container** amd64 ve arm64
   imajlarını GHCR'a gönderir. Tam sürüm imaj etiketini kullanın;
   bu iş akışı `latest` etiketi üretmez.
5. Paket görünürlüğünü ve oturumsuz indirmeyi kontrol edin.
   Public depo, paket görünürlüğünü tek başına garanti etmez.
6. Release notlarını test kapsamı ve bilinen sınırlarla yazın.
   Erken beta sürümünü Pre-release olarak işaretleyin.
   ARM64 build/indirme, fiziksel cihaz çalışma testi olarak sunulmamalıdır.
7. İsteğe bağlı kaynak ZIP'i ve SHA-256 dosyasını Release'e ekleyin.
   Kurulum belgelerini ve manifesti birlikte güncelleyin.

İş akışı otomatik `GITHUB_TOKEN` ile çalışır; depoya kişisel erişim
tokenı eklemek gerekmez. `packages: write` yalnız yayın işine verilmiştir.
Başka hesaba fork edilirse GHCR adresi o hesabın/deponun adıyla oluşur;
yukarıdaki adres bu projeye aittir.

BookOrbit resmi sağlayıcı kataloğuna ekleme ayrı bir katkıdır.
Bu yayın işlemi kataloğa otomatik kayıt oluşturmaz.

Kaynaklar:
[BookOrbit yayın rehberi](https://github.com/bookorbit/bookorbit/blob/54cba36e0914f307e2c9d82571d04e626f1586e1/docs/BUILDING_METADATA_PROVIDERS.md),
[GitHub Container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry),
[GitHub Actions ile imaj yayını](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images).
