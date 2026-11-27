# GitHub yayın hazırlığı

Bu kaynak paketi yerel olarak hazırlanmıştır. GitHub deposu, GitHub Release
veya GHCR imajı bu işlemle oluşturulmaz.

## Yerel paket

```sh
python tools/prepare_release.py --check-only
python tools/prepare_release.py
```

Araç yalnız izin verilen kaynak dosyalarını toplar, bilinen özel adres/anahtar
desenlerini denetler ve `dist` altında kaynak ZIP'i ile SHA-256 dosyası oluşturur.
ZIP içindeki `RELEASE-MANIFEST.json` dosya özetlerini içerir.
.env, sanal ortam, önbellekler, eski arşivler ve yerel Compose override dosyaları
pakete alınmaz. Taramalar tüm sır türlerini yakalama garantisi vermez.

GitHub'a yüklerken bu yeni kaynak ZIP'ini ayrı boş klasöre çıkarın ve içindeki
proje kökünün **dosyalarını** kullanın. ZIP'i tek dosya olarak yüklemek depoyu
çalışır bir kaynak deposu hâline getirmez. Gizli `.github`, `.gitignore` ve
env örneklerini de dahil edin. Eski NAS dağıtım ZIP'lerini yüklemeyin.

## Daha sonra yapılacak yayın adımları

1. Kendi hesabınızda boş `bookorbit-turkish-metadata-provider` deposu oluşturun;
   bu paketin README ve lisansı bulunduğu için ayrı başlangıç dosyası üretmeyin.
2. Temiz kaynak dosyalarını yükleyin. Gerçek .env dosyasını eklemeyin.
3. GitHub Actions **Tests** iş akışının başarılı olmasını bekleyin.
   Güvenlik bildirim kanalını etkinleştirin.
4. Kaynak ve koşul açıklamalarını gözden geçirdikten sonra `v0.1.1` etiketi
   oluşturun. Etiket uygulama ve proje sürümüyle eşleşmelidir.
5. Etiket, testleri tekrar çalıştırır; ardından **Publish container** iş akışı
   `linux/amd64` ve `linux/arm64` imajlarını GHCR'a gönderir.
   Bu paket `latest` etiketi üretmez. Tam sürüm etiketi kullanın.
6. GitHub Packages içinde oluşan imajın görünürlüğünü **Public** yapın ve
   oturumsuz pull işlemini doğrulayın. Public depo imaj görünürlüğünü tek başına
   garanti etmez.
7. GitHub Release'i erken beta / pre-release olarak sunun; kaynak ZIP'i ve
   SHA-256 dosyasını isteğe bağlı ekleyin. ARM64 build, gerçek cihaz testi
   olarak tanıtılmamalıdır.

İş akışı otomatik verilen `GITHUB_TOKEN` ile çalışır; depoya kişisel erişim
tokenı eklemek gerekmez. `packages: write` yalnız yayın işine verilmiştir.
Etiket yüklemek yayın işlemini tetiklediğinden, kaynak yüklemesinden ayrı bir adımdır.

İmaj gerçekten yayımlandıktan sonra, kendi hesabınız/deponuzla şu **şablonu**
`PROVIDER_IMAGE` olarak kullanabilirsiniz:

```text
ghcr.io/<owner>/<repository>:0.1.1
```

Bu bir doğrulanmış mevcut imaj adresi değildir. Hazır imajla kurulumda önce
`docker compose pull`, sonra `docker compose up -d --no-build` kullanın.
Yerel derleme için `PROVIDER_IMAGE` boş ve `up -d --build` yeterlidir.

BookOrbit resmi sağlayıcı kataloğuna ekleme daha sonra ayrı bir katkı olabilir;
önce herkese açık imaj, belgeler ve kullanılabilirlik doğrulanmalıdır.
Kaynaklar:
[BookOrbit yayın rehberi](https://github.com/bookorbit/bookorbit/blob/54cba36e0914f307e2c9d82571d04e626f1586e1/docs/BUILDING_METADATA_PROVIDERS.md),
[GitHub container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry),
[GitHub Actions ile imaj yayını](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images).
