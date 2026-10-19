# SkyFeed Studio

DJI Goggles 3 görüntüsünü **USB-C kablosuyla** bilgisayara alır. Görüntüyü temiz ve düşük gecikmeyle gösterir, stabilize eder, kaydeder ve aynı anda birden fazla platforma yayınlar. macOS (Apple Silicon) ve Windows'ta çalışır. Arayüz 8 dilde, varsayılan dil İngilizce.

---

## Kurulum

### macOS: DMG oluşturma
1. `build_mac_app.command` dosyasına çift tıkla. İlk derleme 5-10 dakika sürer, sonunda `dist/SkyFeed-Studio-0.4.0.dmg` oluşur.
2. DMG'yi aç ve **SkyFeed Studio**'yu Applications klasörüne sürükle.
3. Gözlükte bir kere **Settings › About › “OTG Wired Connection to Computer”** ayarını aç. Gözlüğü veri taşıyan bir USB-C kabloyla bağla. macOS USB erişimi için şifre sorar.

Gereksinimler: Apple Silicon Mac ve **macOS 14 veya üstü**.

DMG'yi başka bir Mac'e verirsen, o Mac ilk açılışta uygulamayı engeller. Çözüm: Sistem Ayarları › Gizlilik ve Güvenlik › **Yine de Aç**. Alternatif: `xattr -cr "/Applications/SkyFeed Studio.app"`

### Windows
1. `setup_windows.bat` dosyasını çalıştır. Python ve ffmpeg kurulur, ardından tek seferlik **Zadig** sürücü adımı gelir.
2. `build_windows_app.bat` dosyasını çalıştır. Uygulama `dist\SkyFeedStudio\SkyFeedStudio.exe` olarak oluşur.

**Zadig adımı:** Options › List All Devices seçeneğini işaretle. `2CA3 0020` ve yanında `MI 00` yazan cihazı seç, **WinUSB** seçip **Replace Driver**'a bas. Listede `MI 01` de varsa onu da WinUSB yap.

---

## Arayüz

- **Üst çubuk:** Bağlantı durumu ve bildirimler solda. Tekrar, fotoğraf, **Kaydet**, **Yayına Başla**, videoyu ayırma ve tam ekran düğmeleri sağda.
- **Orta:** Video tertemiz durur; üstüne hiçbir şey çizilmez.
- **Alt şerit:** Bağlantı kalitesi, fps ve bitrate grafiği, uçuş süresi, kayıt ve yayın süresi, stabilizasyon durumu, saat. Telemetride voltaj bulunursa **BAT** kutucuğu da çıkar.
- **Sağ ray:** Yayın, Görüntü, Kayıt, Tanılama ve Ayarlar panelleri. Açık olan simgeye tekrar tıklarsan panel kapanır.
- **Videoyu ayır (D tuşu):** Video ayrı bir pencereye geçer. O pencereyi ikinci monitörde tam ekran yapabilirsin; pencereyi kapatınca video ana pencereye geri döner.

## Stabilizasyon nasıl çalışıyor

FPV kameralar çok geniş açılı (balıkgözü). Sarsıntı da neredeyse tamamen kameranın **dönmesinden** geliyor. Görüntüyü düz bir şekilde kaydırarak düzeltmeye çalışınca kenarlar merkezden farklı hareket eder; sağ ve sol "nefes alıyor" ya da farklı zoom'lanıyor gibi görünür. Bu yüzden SkyFeed Studio:
1. Lens modelini kullanarak kameranın 3 boyutlu dönüşünü hesaplar.
2. Her pikseli bu dönüşün tersine çevirerek düzeltir.

**Akıcı mod (varsayılan):** Sadece birkaç kare ileriye baktığı için dönüşlerde geride kalmaz, geri savrulma ("gelgit") olmaz. Bu ekranda ve çıkışlarda yaklaşık 0,2 saniye gecikme olur; gözlüğün etkilenmez.

**Gecikmesiz mod:** Hiç bekleme yapmaz, karşılığında biraz daha az pürüzsüzdür.

Sentetik bir 150° FPV uçuşunda eski sürüme göre ölçülen sonuçlar:
- kalan titreme ≈3,5 kat az,
- kenarların kayması ≈2,6 kat az,
- dönüşlerdeki sapma ≈5 kat az.

**Kamera lensi** ayarı varsayılan olarak 150°. **Lensi düzelt** seçeneği balıkgözü görüntüyü düz (rectilinear) görüntüye çevirir.

**Kadraj:** Varsayılan **Otomatik** seçeneği videonun kendi oranını korur. Bunun yerine 16:9, 9:16 (dikey), 1:1, 4:5 veya 4:3 seçebilirsin. Yatay konum, zoom, 180° döndürme, ayna ve **Kadrajı sıfırla** düğmesi de bu bölümde.

## Yayın, kayıt ve diğerleri

**Yayın**
- YouTube, Twitch, Facebook, Instagram, Kick veya herhangi bir RTMP/RTMPS sunucusuna aynı anda yayın yapılabilir. Yayın anahtarları Anahtar Zinciri'nde saklanır.
- Görüntü donanım kodlayıcıyla bir kez kodlanır ve her 2 saniyede bir keyframe eklenir; sonradan katılan izleyiciler de görüntüyü hemen görür.

**Diğer çıkışlar**
- OBS / VLC için `udp://127.0.0.1:5600`.
- Telefon ve tarayıcı izleyici: QR kodu okutarak aynı Wi-Fi'daki herhangi bir cihazdan izlenebilir.

**Kayıt**
- Orijinal kalitede, yeniden kodlamadan kayıt. **Oto-kayıt** açıksa kayıt görüntü başladığı anda başlar.
- İstersen stabilize edilmiş ve kadrajlı bir kopya da kaydedilir.
- Anlık tekrar (B tuşu), fotoğraf (S tuşu), son kayıtların listesi ve boş disk alanı göstergesi.

**Ayarlar:** Görüntü varken bilgisayarın uyumasını engelleme (macOS), gecikme test saati, pencereyi her zaman üstte tutma, tüm ayarları sıfırlama.

### Kısayollar
| Tuş | İşlev |
|---|---|
| R / Space | Kaydı başlat / durdur |
| S | Fotoğraf |
| B | Tekrarı kaydet |
| D | Videoyu ayır / geri al |
| F veya çift tık | Tam ekran |
| H | Arayüzü gizle (OBS için temiz görünüm) |
| Tab | Paneli göster / gizle |

---

## Görüntü gelmezse
- **"Waiting for goggles"** mesajında kalıyorsa: Kablonun veri taşıdığından ve OTG ayarının açık olduğundan emin ol. OTG ayarını değiştirirken kablo takılı olmamalı.
- **"Waiting for keyframe"** görüyorsan: Gözlükte **"Share Liveview to Mobile Device via Wi-Fi"** ayarını kapatıp tekrar aç.
- Mac'te şifre penceresini iptal ettiysen üst çubuktaki **Reconnect** düğmesine bas.

## Geliştirme
- Uygulamayı kaynaktan çalıştırmak için: `python -m g3.app`
- Gözlük olmadan demo modu: `python -m g3.app --demo video.h264`
- Testler: `python -m pytest tests`
- Komut satırı sürümü: Mac'te `run_mac.command`, Windows'ta `run_windows.bat`.

| Dosya | Görevi |
|---|---|
| `g3/app.py` | Arayüz |
| `g3/stabilizer.py` | Lens modeli, dönüş tahmini, yumuşatma |
| `g3/render.py` | Kadraj |
| `g3/outputs.py` | Kodlayıcı, RTMP/RTMPS, UDP, tekrar |
| `g3/webview.py` | Tarayıcı izleyici |
| `g3/i18n.py` | Çeviriler |
| `g3/helper.py` | USB yardımcı süreci |
| `g3/protocol.py`, `g3/rndis.py`, `g3/netstack.py` | Gözlük protokolü |

## Krediler
USB protokol bilgileri açık kaynak **gogglecast** projesinden alındı: <https://github.com/Kristian-Buriasco/gogglecast>. Bu uygulamanın DJI ile bir bağlantısı yoktur.
