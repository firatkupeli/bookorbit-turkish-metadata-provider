# Synology DS224+ / Container Manager

Bu rehber kendi BookOrbit kurulumunuzdaki ağ adını ve gerekiyorsa boş IP adresini
kullanır. Depoda kişiye özel ağ adı veya sabit LAN adresi bulunmaz.
DS224+ için amd64, tek worker ve 256 MiB bellek sınırı kullanılır.
CPU/PID kotası gerektirilmez; bazı DSM çekirdeklerinde bu kotalar desteklenmez.

## 1. Kurulum türünü seçin

- **Ortak Docker ağı:** `compose.yaml` ve `.env.example` kullanın.
  BookOrbit sunucu konteynerinin eriştiği mevcut ağı `BOOKORBIT_NETWORK` olarak girin.
  Sağlayıcı adresi `http://turkish-metadata:8080` olur.
- **Mevcut macvlan üzerinde ayrı IP:** `compose.synology.yaml` ve
  `.env.synology.example` kullanın. BookOrbit'in bu ağa erişmesi gerekir.
  Bu örnek yeni macvlan ağı oluşturmaz.

Container Manager → **Ağ** bölümünde BookOrbit'in bağlı olduğu ağı bulun.
Birden çok ağ varsa BookOrbit sunucusunun bulunduğu, sağlayıcıyı da bağlayabileceğiniz
ağı seçin. Macvlan için alt ağı ve ağ geçidini kontrol edin; kullanacağınız IP'nin
bu alt ağda, boş ve DHCP dağıtım aralığının dışında olduğundan emin olun.
DHCP aralığı kontrolü yönlendiricide yapılır. Ağın otomatik IP havuzu dışında
sabit adres kullanmak mümkündür; adres yine ağın alt ağında olmalıdır.

## 2. Dosyaları hazırlayın

1. Kaynak paketini File Station ile örneğin
   `/volume1/docker/bookorbit-turkish-metadata-provider` klasörüne çıkarın.
   `Dockerfile`, `requirements.txt`, `main.py` ve `app` aynı kökte olmalıdır.
2. Seçtiğiniz kurulumun env örneğini **kopyalayıp** `.env` adıyla kaydedin.
   Sonunda `.txt` kalmadığını kontrol edin.
3. `BOOKORBIT_NETWORK` değerine gerçek mevcut ağ adını yazın.
4. Macvlan kullanıyorsanız `PROVIDER_IPV4_ADDRESS` alanına kendi boş IP'nizi girin.
   Bu alan ile ağ adı boşsa Compose bilerek hata verir.
5. Hazır imajı yalnız v0.4.0 Publish container işi başarılı ve paket Public
   olduktan sonra kullanın. `.env` içindeki `PROVIDER_IMAGE` satırını ayarlayın:

   ```dotenv
   PROVIDER_IMAGE=ghcr.io/firatkupeli/bookorbit-turkish-metadata-provider:0.4.0
   ```

6. Container Manager GUI'sinde hazır imajın kullanılmasını sağlamak için
   NAS'taki kurulum kopyasının YAML dosyasında `turkish-metadata` servisi
   altındaki `build:` bölümünü ve ona bağlı girintili `context:` /
   varsa `dockerfile:` satırlarını kaldırın. `image:`, `environment:`,
   güvenlik ve ağ ayarlarını koruyun. Böylece GUI kaynak kod derlemek
   yerine GHCR imajını kullanır. Kaynaktan derleme istiyorsanız `build`
   bölümünü koruyun ve `PROVIDER_IMAGE` değerini boş bırakın.
7. İsteğe bağlı `AUTH_TOKEN` ayarlayın; boş bıraktığınızda BookOrbit
   Authorization alanı da boş olmalıdır.

GUI'de yanlış Compose dosyasının seçilmesini önlemek için NAS'taki **kurulum
kopyasında** yalnız seçtiğiniz YAML dosyasını tutun ve onu `docker-compose.yml`
adıyla kaydedin. Bu, kaynak depodaki iki örneği değiştirmenizi gerektirmez.
Geliştirme ortamı `.venv`, eski ZIP'ler ve gerçek env dosyaları GitHub'a yüklenmez.

## 3. Projeyi oluşturun

1. Container Manager → **Proje → Oluştur**.
2. Proje adı olarak `bookorbit-turkish-metadata`, yol olarak hazırladığınız
   klasörü seçin. Mevcut `docker-compose.yml` dosyasını kullanın.
3. **İleri**. Web Station web portalı seçeneğini kapalı bırakın.
4. Özette **Oluşturduktan sonra projeyi başlatın** seçili olabilir. **Bitti**.
5. Hazır imaj kurulumunda indirme/oluşturma işleminin tamamlanmasını ve
   **Exit Code: 0** görünmesini bekleyin. Kaynaktan kurulumda ayrıca derleme
   adımları görünür. Konteynerin çalıştığını ve sağlık durumunu kontrol edin.
   Public GHCR imajını indirmek için GitHub hesabı veya token gerekmez.

SSH ile hazır imaj kurulumu (seçilen YAML'nin adını kullanın):

```sh
docker compose -f compose.synology.yaml config --quiet
docker compose -f compose.synology.yaml pull
docker compose -f compose.synology.yaml up -d --no-build
docker compose -f compose.synology.yaml ps
```

Ortak ağ için komuttaki dosya `compose.yaml` olur. GUI kopyasında dosyayı
yeniden adlandırdıysanız komutlarda da o adı kullanın. SSH üzerinden
`--no-build` derlemeyi kapatır; yukarıdaki YAML `build` kaldırma adımı
özellikle GUI kurulumunu açık hâle getirir.

## 4. BookOrbit'e bağlayın

Settings → Library → Metadata → Providers → External → Add:

- Ortak ağ adresi: `http://turkish-metadata:8080`.
- Macvlan adresi: kendi seçtiğiniz IP ile `http://<kendi-IP-adresiniz>:8080`.
- **Allow private address:** açık.
- **Timeout:** en az 15 saniye.
- **Authorization header:** token yoksa boş; varsa `Bearer <kendi-tokenınız>`.

Kaydedin ve **Test** çalıştırın. HTTPS domaini veya Nginx yapılandırması bu
yerel bağlantı için gerekmez. Macvlan, NAS hostu ile konteyner arasındaki
doğrudan iletişimi kısıtlayabilir; NAS'tan adresin açılmaması BookOrbit'in aynı
ağdan erişemediği anlamına gelmez. Testi BookOrbit üzerinden yapın.

Önce ISBN'si bilinen tek kitapta elle arama ve doğru baskı kontrolü yapın.
Ardından [README'deki Field Rules](../README.md#otomatik-metadata--field-rules)
ayarlarını uygulayıp tek kitapta Auto-fill deneyin ve sonucu inceleyerek kaydedin.

## Güncelleme ve sorun giderme

Yeni hazır sürüm için `PROVIDER_IMAGE` etiketini o yayımlanmış sürüme
güncelleyin, imajı yeniden indirin ve sağlayıcı konteynerini yeniden oluşturun.
SSH üzerinden yukarıdaki `pull` ve `up -d --no-build` komutları kullanılabilir.
Yalnız yeniden başlatmak başka bir imaja geçiş yapmaz.

Kaynak koddan derlemede `build` bölümünü koruyun, `PROVIDER_IMAGE` değerini
boş bırakın ve `up -d --build` kullanın. Container Manager'da işlem adları
DSM sürümüne göre değişebilir. BookOrbit projesini değiştirmeyin;
sağlayıcıyı güncellemek için kaynak klasörünü silmeniz gerekmez.

- `NanoCPUs / CPU CFS` hatası: yerel eski YAML'deki `cpus` ayarını kaldırın.
  Bu pakette böyle bir ayar yoktur.
- `network ... not found`: `.env` içindeki ağ adını Container Manager ile karşılaştırın.
- Eksik değişken hatası: `.env` aynı klasörde mi, adı doğru mu, zorunlu değerler dolu mu?
- IP çakışması: projeyi durdurun ve doğrulanmış başka bir boş adres seçin.
- 401: BookOrbit Bearer değeri ile `AUTH_TOKEN` eşleşmeli.
- 429: bekleyip tekrar deneyin; kaynak aralığını düşürmeyin.
- Sağlık yeşil ama arama boş: başlık+yazar+ISBN gönderin; kaynak erişimini ve
  süre aşımını konteyner günlüğünden inceleyin. `/healthz` yalnız süreç kontrolüdür.

Günlük veya ekran görüntüsü paylaşırken token, özel URL, ağ adı ve IP bilgilerini temizleyin.
