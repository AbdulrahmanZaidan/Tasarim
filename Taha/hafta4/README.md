# Hafta 4 (17–23 Kasım 2026): kontrol ünitesi ve bellek modülleri

Planda (SISTEM-PLANI bölüm 1) kontrol ünitesi (M2) ve bellek (M5) Kişi 2'nin, yani benim modüllerim. İkisi de devre seviyesinde, Digital'de test ediliyor.

## Özet

| İş | Sonuç |
|---|---|
| Çip seviyesi simülatör | 25 entegre modeli (23 çeşit 74HC + flash + SRAM), gecikmeli |
| Digital'e dışa aktarım | Bağlantı listesi Digital'in `.dig` dosyasına çevriliyor; her entegre Digital'in kendi 74xx çipi |
| Kontrol ünitesi (M2) | Mikrokod (3 ROM + kontrol latch'i) 1.000 vektör, kod çözücüler 512 satır: geçti |
| Bellek (M5) | Adres çözme 1.096 vektör: geçti |
| ALU tabloları | 10.000 rastgele vektör: geçti |
| Giriş testi listesi | Gelen her parça için test ve geçme ölçütü |
| C derleyicisi | Üzerinde çalışılıyor; 6. hafta notunda anlatılacak |
| Testler | +59 entegre modeli testi ve Digital modül testleri |

## 1. İki modül

- **Kontrol ünitesi (M2):** adım sayacı, 3 mikrokod ROM'u, kontrol latch'i, kod çözücüler. Komutun her adımında hangi kontrol hatlarının açılacağına karar verir. Planda M2'ye ait breakpoint karşılaştırıcıları (2× 74HC688) hata ayıklama işiyle birlikte sonra eklenecek.
- **Bellek (M5):** program ROM'u, RAM, adres çözme, LED portu, durum portu (KSTAT: klavye ve DIP anahtarları). Adres çözme, adres yolundaki değere göre hangi çipin seçileceğine karar verir.

## 2. Çip seviyesi simülatör

Emülatör işlemcinin **ne yapması gerektiğini** söylüyor. Çip seviyesi simülatör ise **kabloların doğru bağlanıp bağlanmadığını** söylüyor: her entegre ayrı bir model, her bacak ayrı bir tel.

Neden:
- Digital gerçek gecikmeleri modellemiyor. Bu simülatörde her entegrenin gecikmesi var (tipik ve en kötü değerler), böylece 1 MHz'de sinyallerin yetişip yetişmediği görülüyor.
- Modüllerin bağlantısı şema çizilmeden önce deneniyor. Hata şemada değil kodda bulunuyor.
- Aynı bağlantı listesinden hem Digital dosyası hem Proteus/breadboard için bağlantı tablosu üretiliyor. Üç yerde aynı devre olduğundan emin oluyoruz.

Neleri yakalıyor: iki entegrenin aynı hatta aynı anda çıkış vermesi (bus çakışması), boşta kalan giriş, kurulum/tutma süresi ihlali, belleğe hatalı yazma.

Testlerin gerçekten hata yakaladığı denendi: entegre modellerinde yapılan 7 bilinçli bozmanın 7'si yakalandı.

Dosyalar: `sim/ta8/hw/kernel.py` (çekirdek), `chips.py` (25 entegre modeli; gecikme tablosunun bir kısmı tahmin, dosyada işaretli).

## 3. Digital'e dışa aktarım

`sim/ta8/hw/digital.py` bağlantı listesini Digital'in `.dig` dosyasına çeviriyor. Her entegre Digital'in kendi 74xx kütüphanesindeki bacaklı çip; her bacakta sinyal adı var.

- Dışa aktarılan devreler Digital'de ve bizim simülatörde aynı sonucu veriyor: 23 çeşit entegrenin hepsi, datasheet kurallarına uyan uyaranla denendi.
- Digital gecikmeleri modellemez: orada yalnız işlev doğrulanır, zamanlama bizim simülatörde.
- **Bulgu:** Digital, ROM dosyasının göreli yolunu devre dosyasına göre çözmüyor. Bu yüzden ROM içerikleri `.dig` dosyasının içine gömüldü.
- Dosyalar Digital'in arayüzünde açılıyor; testler komut satırından çalıştırılıyor.

Dosyalar: `sim/digital/m2_kontrol.dig`, `m5_bellek.dig` ve diğer modüller.

## 4. Modül testleri: planın kabul ölçütleri

Vektörleri test vektörü üreticisi veriyor, Digital tabloyu satır satır deniyor (SISTEM-PLANI bölüm 12.3).

| Ne | Modül | Vektör | Sonuç |
|---|---|---|---|
| ALU tabloları (2 flash) | M4 | 10.000 rastgele | geçti |
| Mikrokod (3 ROM + kontrol latch'i) | M2 | 1.000 | geçti |
| Kod çözücüler | M2 | 512 (tam tablo) | geçti |
| Adres çözme | M5 | 1.096 (96 sınır adresi + 1.000 rastgele) | geçti |

Her dosyada modülün entegreleri ve test tablosu birlikte: `sim/digital_kabul/` (`m2_urom.dig`, `m2_cs.dig`, `m4_alu_tablo.dig`, `m5_cozme.dig`). Digital'de açıp araç çubuğundaki test düğmesiyle çalıştırılabilir; yeniden üretmek için `cd sim` → `py -3 digital_kabul/uret.py`.

Testlerin hata yakaladığı da denendi: bilerek bozulan devreler Digital'de kalıyor (ör. ALU'da iki adres bacağı yer değiştirince).

ALU'nun tabloları flash içeriği; M4 modülünün kendisi (registerlar ve şema) Abdurrahman'da.

## 5. Gelen parçalar için giriş testi listesi

Her parça kullanılmadan önce bir kez denenir; sonuç lab defterine yazılır.

| Parça | Test | Geçme ölçütü |
|---|---|---|
| SST39SF010 (flash) | T48 programlayıcıda sil, `build/urom0.bin` yaz, doğrula | Doğrulama hatasız. Hız eki (-70 / -90) not edilir: -70'ler mikrokod ve ALU soketlerine |
| CY62256 (SRAM) | T48'in SRAM testi; yoksa Arduino ile 55/AA yaz-oku | Bütün adreslerde hatasız |
| 74HC161, 74HC191 | Breadboard'da 1 Hz saatle say, LED'lerde izle; reset ve yükleme | 0–15 sayıyor, /MR ve /PE çalışıyor; 191 iki yönde sayıyor |
| 74HC245 | Bir yöne veri geçir, /OE ile kapat | /OE = 1 iken çıkış boşta |
| 74HC138, 74HC139 | 3 anahtarla adres ver, 8 LED | Her adreste yalnız bir çıkış 0 |
| 74HC273, 74HC377 | Anahtarlardan veri yükle; 377'de izin girişi | Saat kenarında yüklüyor; /E = 1 iken yüklemiyor |
| 4 MHz ve 25 MHz osilatör | Osiloskopla frekans ve genlik | Frekans doğru, 0–5 V arası temiz kare dalga |
| Çıkış gerilimi (VOH) | Flash ve SRAM çıkışını yük altında ölç (prototip b) | 4 V'un üstünde. Altındaysa 74HCT'ye geçilecek çipler: DOGRULAMA.md madde 7 |

## 6. Testler

- **+59 entegre modeli testi** (`test_hw_chips.py`): her entegrenin doğruluk tablosu ve simülatörün çekirdeği.
- **Digital modül testleri** (`test_hw_digital.py`): yukarıdaki kabul ölçütleri ve dışa aktarılan çiplerin bizim simülatörle karşılaştırılması.

## Gelecek hafta

- Bütün işlemcinin birleştirilmesi: bütün modüller bir arada, emülatörle çevrim çevrim karşılaştırma.
- C derleyicisi: 6. hafta notunun konusu.

## Kullanılan araçlar

Python 3.12 (yalnızca standart kütüphane), unittest, Java (Temurin JDK 21), Digital v0.31, Git/GitHub.
