# TA-8 simülasyon araçları

Bu klasör devre simülasyonunun yazılım tarafıdır. Buradaki araçlar:

1. **ROM imajları:** Digital'deki ROM bileşenlerine ve gerçek flash çiplerine yüklenecek içerikler (mikrokod, ALU tabloları, VGA zamanlaması, font).
2. **Assembler:** TA-8 programlarını çevirir.
3. **İki emülatör:** Programı çalıştırır ve devrenin vermesi gereken doğru sonucu söyler. Digital'deki devre ya da breadboard ondan farklı davranırsa hata bulunmuş olur.
4. **Test vektörleri:** Digital'in test bileşenine yapıştırılır ya da Proteus/Arduino kaydıyla karşılaştırılır.
5. **Çip seviyesi devre (`ta8/hw/`):** İşlemcinin 63 entegresi pin pin bağlı ve gecikmeli olarak simüle ediliyor; emülatörle çevrim çevrim sıfır fark veriyor. Aynı bağlantı listesinden Digital dosyaları ve Proteus/breadboard için bağlantı tablosu üretilir.
6. **C derleyicisi (`tacc/`):** C alt kümesini TA-8 assembly'sine çevirir.
7. **Snake (`examples/snake.c`) ve `play.py`:** Final demosunun oyunu; emülatörde klavyeyle oynanır.
8. **Arduino aracı (`ardu_cli.py`, `../arduino/`):** Breadboard'daki makinenin izini alıp emülatörle karşılaştırır, RAM'e program yükler. Donanımda henüz denenmedi.

Tasarımın tamamı: [../SISTEM-PLANI.md](../SISTEM-PLANI.md)

## Kurulum

| Ne | Nasıl |
|---|---|
| Python 3.12 | Kurulu (`py --version`). Ek paket gerekmez, yalnızca standart kütüphane kullanılıyor. |
| Java 17 ya da üstü | [adoptium.net](https://adoptium.net) → Temurin (LTS) → Windows x64. Digital için gerekli. `.zip` sürümü kurulum gerektirmez: bir klasöre açmak yeter. |
| Digital | [github.com/hneemann/Digital/releases](https://github.com/hneemann/Digital/releases) → `Digital.zip` indirin, bir klasöre açın. Java PATH'teyse `Digital.exe`, değilse `java -jar Digital.jar`. |

Taha'nın bilgisayarında ikisi de `Desktop\bitirme ödevi\araclar\` altında (JDK 21.0.13, Digital 0.31; masaüstünde "Digital (TA-8)" kısayolu). Digital'i kullanan testler bu klasörü arar; başka yerdeyse `TA8_DIGITAL_HOME` ortam değişkeniyle gösterilir, bulunamazsa o testler atlanır.

Komutların hepsi bu klasörde (`sim/`) çalıştırılır.

## Komutlar

```
py gen_roms.py                                  build/ altına tüm ROM imajları (.bin + .hex)
py cli.py roms --font font8x8_basic.h           gerçek fontla üret (yoksa test deseni)
py cli.py asm examples/merhaba.asm -l           programı çevir, listeyi göster, 32 KB .bin yaz
py cli.py run examples/merhaba.asm              mikroadım emülatöründe çalıştır, ekranı göster
py cli.py run examples/merhaba.asm --ref        komut seviyesi emülatörde çalıştır
py cli.py run examples/merhaba.asm --vga        VRAM penceresi beklemesini de modelle
py cli.py run examples/merhaba.asm --trace 20   ilk 20 çevrimin izi (AB, DB, kontrol kelimesi)
py cli.py run examples/klavye.asm --keys 1C,F0,1C --cycles 20000
py cli.py run examples/fibonacci.asm           16-bit Fibonacci (runtime kütüphanesiyle)
py cli.py run examples/asal.asm --ref --cycles 20000000   1000'den küçük asal sayılar
py cli.py roms                                  ayrıca build/proteus/: Proteus için 64 KB .bin + Intel HEX
py cli.py asm examples/merhaba.asm --ihex       program ROM'unun Intel HEX'i (Proteus)
py cli.py vectors alu -n 10000 -o alu_test.txt  ALU testi için vektörler
py cli.py vectors urom -n 1000 -o urom_test.txt kontrol ünitesi (mikrokod) testi için vektörler
py cli.py vectors cs                            kod çözücüler: tam tablo
py cli.py vectors decode                        adres çözme: her bölgenin sınır adresleri
py cli.py vectors trace examples/merhaba.asm    bütün işlemci: çevrim çevrim AB, DB, kontrol kelimesi
        (hepsinde --format csv ve -o DOSYA kullanılabilir)
py cli.py hw run examples/komut_testi.asm       çip seviyesindeki devreyi çalıştır, emülatörle karşılaştır
py cli.py hw run examples/merhaba.asm --corner max    en kötü gecikmelerle; zamanlama özetini de yazar
py cli.py hw wiring -o tablo.md                 bağlantı tablosu: her entegrenin her bacağı
py cli.py hw digital                            digital/ altındaki .dig dosyalarını yeniden üret
py cli.py hw digital --program examples/komut_testi.asm --run 800   Digital'de koştur, emülatörle karşılaştır
py -m tacc examples/merhaba.c -o build/merhaba_c.asm --run    C programını derle ve çalıştır
py cli.py run examples/acilis_testi.asm --ref --cycles 5000000    açılış kendi kendini test ROM'u (1,5 sn @ 1 MHz)
py play.py examples/snake.c                     Snake'i oyna: ok tuşları ya da WASD, Boşluk/Enter yeniden başlat, Esc çıkış
py play.py examples/snake.c --demo              hazır tuş senaryosunu oynat (~38 sn)
py ardu_cli.py trace examples/merhaba.asm --fake            Arduino aracını sahte cihazla dene
py ardu_cli.py trace examples/merhaba.asm --port COM5       gerçek kart: izi al, emülatörle karşılaştır (pyserial gerekir)
py ardu_cli.py load PROGRAM.asm --port COM5                 programı RAM'e 8000'den yükle ve doğrula
py -m unittest discover -s tests -t .           tüm testler (304 test, ~5 dk)
```

Windows konsolunda Türkçe harfler bozuk görünürse önce `set PYTHONIOENCODING=utf-8` yazın.

## Dosyalar

| Dosya | İçerik |
|---|---|
| `ta8/isa.py` | **Komut setinin tek kaynağı:** kontrol kelimesi, ALU kodları, 88 opcode'un mikroadımları |
| `ta8/microcode.py` | uROM0..2 imajlarını üretir; kuralları denetler (SISTEM-PLANI 4.5) |
| `ta8/alu.py` | 8-bit referans ALU ve iki nibble flash'ının tabloları |
| `ta8/vga.py` | VGA zamanlama ROM'u, test fontu, `font8x8_basic.h` dönüştürücüsü, sayaç simülasyonu |
| `ta8/asm.py` | Assembler (yazım kuralları dosyanın başında) |
| `ta8/bus.py` | Bellek haritası, I/O (klavye, KSTAT, LED), VRAM penceresi modeli |
| `ta8/emu_micro.py` | Mikroadım emülatörü: üretilen imajları aynen çalıştırır, çevrim çevrim iz verir |
| `ta8/emu_ref.py` | Komut seviyesi emülatör: mikrokoddan bağımsız, çapraz kontrol için |
| `ta8/vectors.py`, `ta8/ihex.py` | Test vektörü üreticisi, iz karşılaştırma (`compare_traces`), Intel HEX |
| `ta8/hw/kernel.py` | Çip seviyesi simülatörün çekirdeği: gecikmeli, olay tabanlı; bus çakışması, boş giriş, kurulum/tutma ihlallerini yakalar |
| `ta8/hw/chips.py` | 23 çeşit 74HC entegresi, SST39SF010 flash ve CY62256 SRAM modelleri; pin adları ve bacak numaraları dosyanın başında. Gecikme tablosunun bir kısmı tahmindir (işaretli) |
| `ta8/hw/cpu.py` | **İşlemcinin bağlantı listesi (netlist):** M1–M5 ve yardımcı kapılar, 59 entegre |
| `ta8/hw/harness.py` | Devreyi resetler, çalıştırır, her çevrimde izini alır ve emülatörle karşılaştırır |
| `ta8/hw/wiring.py` | Bağlantı tablosu ve entegre sayımı |
| `ta8/hw/digital.py`, `ta8/hw/digital_cpu.py` | Bağlantı listesini Digital'in `.dig` dosyasına çevirir; Digital'i komut satırından çalıştırıp izini alır |
| `tacc/` | C derleyicisi: ön işlemci, lexer, parser, tip denetimi, kod üretimi |
| `lib/crt0.asm`, `lib/rt_c.asm`, `lib/hw.h` | C programlarının açılış kodu, derleyicinin yardımcı rutinleri, donanım tanımları (`VRAM`, `LEDS`, `KBD`, `KSTAT`) |
| `play.py` | Etkileşimli çalıştırıcı: programı gerçek zamanlı koşturur, ekranı terminalde gösterir, tuşları PS/2 kodlarına çevirir |
| `ta8/ardu.py`, `ardu_cli.py` | Arduino hata ayıklama kartının bilgisayar tarafı: seri protokol, iz alma ve karşılaştırma, RAM'e yükleme. Sketch ve pin tablosu: [`../arduino/`](../arduino/README.md) |
| `cli.py`, `gen_roms.py` | Komut satırı |
| `lib/runtime.asm` | Çalışma zamanı kütüphanesi: `__mul16`, `__divmod16`, `print_u16`, `puts`. Programa `.include "../lib/runtime.asm"` ile eklenir; çağırma kuralı dosyanın başında |
| `examples/` | `merhaba.asm` (ekrana yazı), `klavye.asm` (PS/2 byte'larını gösterir), `fibonacci.asm`, `asal.asm` (runtime örnekleri), `komut_testi.asm` (88 opcode'un hepsi), `acilis_testi.asm` (açılış kendi kendini test ROM'u; LED ve hata kodları dosyanın başında); C örnekleri `merhaba.c`, `fib.c`, `sayac.c`, `snake.c` |
| `tests/` | ALU (8 milyon girişin hepsi), mikrokod kuralları, assembler, iki emülatörün eşdeğerliği, VGA zamanlaması, runtime rutinleri, vektörler, entegre modelleri, bütün işlemci, C derleyicisi |
| `digital/` | Üretilen Digital devreleri (`.dig`) |
| `build/` | Üretilen imajlar. Git'e girmez, `py gen_roms.py` ile yeniden üretilir. |

## Testler neyi garanti ediyor

- **ALU:** İki nibble tablosu birlikte, 25 işlem × 256 × 256 × C × Z girişlerinin hepsinde referans ALU ile aynı sonucu veriyor.
- **Mikrokod:**
  - Kurallar sağlanıyor: bus çakışması yok, yazma sırasında bellek okunmuyor, her yol NEXT ile bitiyor.
  - Her adresteki 0. adım FETCH.
  - Tanımsız opcode'lar makineyi durduruyor.
  - Çevrim sayıları plandaki tabloyla aynı.
- **Emülatörler:**
  - 150 rastgele programda iki emülatör her komuttan sonra aynı durumu ve aynı çevrim sayısını veriyor.
  - 48 sayı çifti için 16-bit karşılaştırmaların hepsi (işaretli/işaretsiz) doğru.
  - INCW/DECW'de zincirli Z, CALL/RET, stack ve JMPI çalışıyor.
  - Örnek programlar beklenen ekranı üretiyor.
  - Bu testlerin gerçek hataları yakaladığı denendi: PLA'dan bir adım silmek ya da ADC'yi ADD yapmak testi bozuyor.
- **Runtime (`lib/runtime.asm`):**
  - `__mul16` ve `__divmod16` 400'er girişte Python'un sonucuyla aynı (bölen 0 durumu dahil); 30 girişte iki emülatör aynı sonucu ve aynı çevrim sayısını veriyor.
  - `print_u16` 0, 9, 10, 9999, 10000, 65535 gibi sınırlarda ve 100 rastgele sayıda doğru yazıyor.
  - `fibonacci.asm` ve `asal.asm` beklenen ekranı üretiyor (168 asal).
- **Çip seviyesi devre (`ta8/hw/`):**
  - Her entegre modeli datasheet doğruluk tablosuna uyuyor (59 test).
  - 63 entegrelik işlemci, emülatörle çevrim çevrim aynı adres yolu, veri yolu ve kontrol kelimesini veriyor; sonunda registerlar, RAM, ekran belleği ve LED'ler de aynı. Programlar: `merhaba`, `komut_testi` (88 opcode), çarpma/bölme, `fibonacci` (33.170 çevrim), stack sınırları, `klavye`. Tipik ve en kötü gecikmelerde.
  - Rastgele açılış durumundan reset ile toparlanıyor; çalışırken reset her fazda doğru.
  - HALT/GO, mikroadım ve komut adımlama, VRAM beklemesi (WAIT) doğru.
  - Donanım breakpoint'i: komut getirmede ve RAM okuma/yazmada, adrese her erişimden sonra duruyor; GO ile devam edince emülatörle sıfır fark. Kapalıyken durmuyor, reset temizliyor.
  - BUSREQ: dört farklı fazda istek, BUSACK en çok 7 MCLK'de; bu sırada AB ve DB'yi hiçbir çip sürmüyor; Arduino ROM okuyor, RAM'e yazıp okuyor; bırakınca program sıfır farkla devam ediyor. Yükleme modu baştan sona: program RAM'e yazılıyor, SW0 = 1 ile reset sonrası 8000'den çalışıyor.
  - Bus çakışması, boş giriş, kurulum/tutma ihlali yok (bilinen kısa devir-teslim örtüşmeleri ayrı sayılıyor).
  - Entegre sayısı modül modül plandaki listeyi aşmıyor.
- **Digital (`tests/test_hw_digital.py`; Digital kurulu değilse atlanır):**
  - Dışa aktarılan devreler Digital'de bizim simülatörle aynı sonucu veriyor (23 çeşit entegrenin hepsi).
  - Planın kabul ölçütleri (12.3): ALU 10.000 vektör, mikrokod 1.000 vektör, kod çözücüler tam tablo, adres çözme sınır adresleri.
  - Bütün işlemci Digital'de emülatörle çevrim çevrim sıfır fark: `merhaba`, `komut_testi`, `fibonacci`.
  - Breakpoint ve BUSREQ Digital'de de: M1 modülünde ve bütün işlemcide (breakpoint'te durma, BUSREQ ile durup devam).
- **C derleyicisi (`tacc`):**
  - 200 rastgele C programı (~4.400 ifade) emülatörde ve bağımsız bir Python hesaplayıcıda aynı sonucu veriyor.
  - Kontrol akışı, fonksiyonlar, işaretçiler, diziler, switch, başlangıç değerleri, `const` tablolar, `volatile` erişimleri.
  - Desteklenmeyen yapılar (özyineleme, struct, long, float, fonksiyon işaretçisi) satır numaralı Türkçe hata veriyor.
- **Açılış testi (`examples/acilis_testi.asm`):**
  - Sağlam makinede iki emülatörde de "TEST TAMAM", aynı çevrim sayısı.
  - Bilerek konan arızalar yakalanıyor: RAM'de yapışık bit, bozuk yığın hücresi, kısa devre adres hattı (15 hattın her biri), ters çevrilmiş dallanma koşulları, bozuk mikroadımlar. ALU tablosu bozulmalarında kapsam işleme göre değişiyor (CLC, SEC, TST'de düşük).
  - SW0 = 1 iken RAM'deki program bozulmadan 8000'e geçiliyor.
- **Snake (`examples/snake.c`):**
  - Her hamleden sonra ekranın tamamı, yılanın konumu, skor ve LED'ler bağımsız bir Python modeliyle aynı.
  - Dönüşler, ters yön reddi, yem ve uzama, hızlanma, skor geçişleri, duvara ve kendine çarpma, yeniden başlama, kazanma.
  - Hamle başına ortalama 532 çevrim (~0,53 ms); VRAM yazmaları pencereye sığıyor.
- **Arduino aracı (`ta8/ardu.py`):**
  - Sahte cihazdan alınan iz emülatör iziyle aynı; bilerek konan hatalar doğru çevrimde ve doğru alanda bulunuyor.
  - RAM'e yükleme ve doğrulama, zaman aşımı, bozuk çerçeveden sonra yeniden senkron.
  - Sketch'teki protokol sabitleri Python'dakilerle aynı. Sketch `arduino:avr:mega` için derleniyor; **donanımda denenmedi.**
- **VGA:**
  - 400 nokta × 525 satır; HSYNC 48 nokta, VSYNC 2 satır, 40 × 480 görünür alan.
  - VRAM pencereleri doğru iç içe.
  - Sayaçlar herhangi bir başlangıç durumundan bir kare içinde toparlanıyor.

## Digital'de kullanım

`digital/` klasöründeki `.dig` dosyaları elle çizilmedi; `ta8/hw/cpu.py`'deki bağlantı listesinden `py cli.py hw digital` ile üretildi. Her entegre Digital'in kendi 74xx kütüphanesindeki bacaklı çipi olarak durur; her bacağın üstünde bağlı olduğu sinyalin adı yazar (tel çizilmez, aynı adlı uçlar bağlıdır).

| Dosya | İçerik |
|---|---|
| `digital/ta8.dig` | Bütün işlemci (63 entegre + VGA/klavye yerine 2 taklit) |
| `digital/m1_saat.dig` … `m5_bellek.dig`, `aux_kapilar.dig` | Modüller tek tek; modül sınırındaki sinyaller giriş/çıkış |
| `digital/TA8_*.dig` | Flash ve SRAM alt devreleri. ROM içerikleri dosyanın içine gömülü, ayrıca yükleme gerekmez |
| `digital/ornek_*.dig` | Dışa aktarıcının denendiği küçük devreler |
| `digital/arac/TA8Adim.java` | Digital'de saati adım adım çalıştırıp sinyalleri döken yardımcı |
| `digital_kabul/` | Kabul testleri: her dosyada modülün entegreleri ve test tablosu birlikte; Digital'de açıp test düğmesiyle denenir. `digital/` dışında durur, çünkü Digital açılan dosyanın klasörünü alt klasörleriyle tarar ve aynı adlı alt devreler karışır |

- **Açmak:** Digital'de `digital/ta8.dig`'i açın, simülasyonu başlatın. Varsayılan program `merhaba.asm`. Başka program için `py cli.py hw digital --program examples/X.asm`. Dosyaların arayüzde açıldığı görüldü; testler komut satırından çalıştırılıyor. Breakpoint için `BP` girişine adresi verip `BP_EN_n`'i 0 yapın; `BUSREQ_n` = 0 makineyi durdurur (BUSACK çıkışı 1 olur).
- **Mikrokod, ALU tablosu ya da bağlantı listesi değişince** `py cli.py hw digital` ile dosyaları yeniden üretin; iki test dosyaların güncel olduğunu denetler.
- **Digital'in doğruladığı:** işlev. Digital gecikmeleri modellemez; zamanlama `py cli.py hw run ... --corner max` ile bizim simülatörde denetlenir.
- **Kendi çizdiğiniz devreyi test etmek için:** test bileşenine `py cli.py vectors ...` çıktısını yapıştırın. Giriş ve çıkış etiketleri vektörün ilk satırındaki adlarla **aynı** olmalı (ALU için `OP A B Cin Zin R Z C N V`; kontrol ünitesi için `STEP IR Z C N V CW0 CW1 CW2`).

## Komut eklemek ya da değiştirmek

1. `ta8/isa.py` içinde adımları yazın (yazım: `adres/kaynak/hedef/ALU bitler`, örnek `AR/MEM/A/ADD FL NEXT`).
2. Komut seviyesindeki anlamını `ta8/emu_ref.py`'ye ekleyin.
3. `py -m unittest` çalıştırın. Mikrokod kuralı ihlal edilirse hata mesajı hangi adım olduğunu söyler.
4. `py gen_roms.py` ile imajları yenileyin, `SISTEM-PLANI.md`'yi güncelleyin, commit edin.

## Sırada ne var (SISTEM-PLANI bölüm 13 ve 14)

| Ne zaman | İş |
|---|---|
| Simülasyon 5. hafta | MANUAL paneli (uROM /OE, latch girişlerinde anahtarlar) ve saat kaynağı seçici (74HC153) |
| Simülasyon 5–7. hafta | VGA (M6) ve PS/2 (M7) netlist'i; taklitlerin yerine gerçek modüller |
| Simülasyon 7. hafta | Gerçek font: `font8x8_basic.h` (kamu malı) → `py cli.py roms --font ...` |
| Kart kurulunca | Arduino yazılımını donanımda denemek; pin tablosunu kesinleştirmek (`../arduino/README.md`) |
| Sürekli | C derleyicisi (`tacc`): ilk sürüm hazır. Eksikler: `switch` için atlama tablosu, struct |
| Yapım 12–17. hafta | Snake'in ince ayarı (hız, skor, yem) gerçek ekran ve klavyeyle |
