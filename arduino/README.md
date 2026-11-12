# TD-8 Arduino hata ayıklama kartı: iz ve yükleme

> **Durum: sürüm 0.1, donanımda HİÇ çalıştırılmadı.**
> Sketch yalnızca `arduino:avr:mega` için derlendi. Bilgisayar tarafı, sketch'in Python ikizi
> olan sahte bir cihazla (`sim/td8/ardu.py`, `FakeDevice`) sınandı. Aşağıdaki pin eşlemesi
> **taslaktır**; kart kablolanınca kesinleşecek. Pin değişirse önce sketch'teki tablo, sonra bu
> belge değişir.

Plan: SISTEM-PLANI bölüm 10 (M8), 3.1–3.4, 4.2, 16 (kabul ölçütü 3);
`tasarim-taslaklari/ISA-v0-sentez.md` 4.10 ve 6.5.

## Ne yapar

| Mod | Ne olur |
|---|---|
| **İz** | MCLK'yı Arduino üretir (74HC153 saat seçicisi **I3**'te; bu kaynak SLOW sayılır). Arduino fazı Q1/Q2'den okur; her commit kenarından (CLK yükselişi, B→C) hemen önce AB, DB ve 24 bitlik kontrol kelimesini örnekler, bilgisayara 6 baytlık kayıt olarak yollar. Bilgisayar bu izi MicroEmu iziyle çevrim çevrim karşılaştırır ve **farkın başladığı ilk çevrimi ve alanı** yazar. Makine adımlanabilir (tek çevrim ya da tek MCLK). |
| **Yükleme** | /BUSREQ'i indirir, BUSACK'ı bekler (500 ms zaman aşımı), AB/DB'yi sürüp /ARD_WR darbesiyle RAM'e yazar, her baytı /ARD_RD ile geri okuyup doğrular, pinleri yüksek empedansa alır, /BUSREQ'i bırakır. **BUSACK = 1 görülmeden AB/DB hiçbir zaman çıkış yapılmaz** ve her bayttan önce yeniden denetlenir. |

## Dosyalar

| Dosya | İçerik |
|---|---|
| `arduino/td8_debug/td8_debug.ino` | Arduino Mega 2560 sketch'i |
| `sim/td8/ardu.py` | Bilgisayar tarafı: çerçeveleme, istemci, iz karşılaştırma, yükleme, sahte cihaz |
| `sim/ardu_cli.py` | Komut satırı |
| `sim/tests/test_ardu.py` | Donanımsız testler (protokol sabitleri sketch'ten okunup karşılaştırılır) |

## Pin eşlemesi (TASLAK)

Bus ve kontrol kelimesi tek okumada alınsın diye her bayt bir porta oturur. Mega'da 8 biti de
dışarı çıkan portlar A, B, C, F, K ve L'dir. PB7 (pin 13) kartın LED'idir ve açılışta
bootloader onu sürer, bu yüzden CW23 (HALT) PD7'ye alındı.

| Sinyal | Yön (Arduino'dan bakınca) | Mega pinleri | Port |
|---|---|---|---|
| AB0..AB7 | giriş / çıkış | 22, 23, …, 29 | PORTA PA0..PA7 |
| AB8..AB15 | giriş / çıkış | 37, 36, …, 30 | PORTC PC0..PC7 |
| DB0..DB7 | giriş / çıkış | 49, 48, …, 42 | PORTL PL0..PL7 |
| CW0..CW7 (uROM0: ASRC, DSRC, DDST) | giriş | A0..A7 (54..61) | PORTF PF0..PF7 |
| CW8..CW15 (uROM1: ALUOP, FL, MEMW, MARK) | giriş | A8..A15 (62..69) | PORTK PK0..PK7 |
| CW16..CW22 (uROM2: PCINC..NEXT) | giriş | 53, 52, 51, 50, 10, 11, 12 | PORTB PB0..PB6 |
| CW23 (HALT) | giriş | 38 | PORTD PD7 |
| Q1 | giriş | 6 | PORTH PH3 |
| CLK (= Q2) | giriş | 7 | PORTH PH4 |
| STOP | giriş | 8 | PORTH PH5 |
| BUSACK | giriş | 9 | PORTH PH6 |
| MCLK | çıkış | 41 | PORTG PG0 → 74HC153 I3 |
| /ARD_RD | çıkış (boşta 1) | 40 | PORTG PG1 |
| /ARD_WR | çıkış (boşta 1) | 39 | PORTG PG2 |
| /BUSREQ | açık-drain (yalnız 0 ya da yüksek empedans) | 4 | PORTG PG5 |
| /RESET | açık-drain | 2 | PORTE PE4 |
| GND | | GND | makineyle ortak |

Toplam 57 sinyal + GND. Boş: 0 ve 1 (USB seri, kullanılmamalı), 13 (LED), diğerleri.
Kontrol kelimesi kontrol latch'inin (3× 74HC273) **çıkışlarından** alınır (LED'lerin
bağlandığı uçlar), ROM'dan değil.

**Makine tarafında gerekenler** (planda bir kısmı yazmıyor, bkz. "Planla ilgili notlar"):

- Bütün Arduino hatlarında 470 Ω seri direnç (plan: AB, DB ve strobe'lar; öneri: hepsi).
- /BUSREQ'te 10k pull-up (planda var), **/ARD_RD ve /ARD_WR'de 10k pull-up**, **MCLK hattında
  (153'ün I3 girişinde) 10k pull-down**. Arduino takılı değilken ya da kendi reseti
  sırasında bütün pinleri giriştir; bu dirençler olmazsa hatlar yüzer.
- Arduino'yu makine kapalıyken bağlı ve açık bırakmayın: çıkış pinleri (MCLK, /ARD_RD,
  /ARD_WR) 470 Ω üzerinden makineyi koruma diyotlarından besler.

## Okuma anı neden B fazının sonu

| Kenar / faz | Ne olur (SISTEM-PLANI 3.1) |
|---|---|
| C→D (LCLK↑) | Kontrol latch'i yeni kelimeyi alır |
| D | Kod çözücüler, AB/DB kaynakları oturur, bellek erişimi başlar |
| A | MEMW varsa yazma darbesi |
| **B** | Her şey bir faz boyunca sabit: okuma verisi ve ALU sonucu oturmuş |
| **B→C (CLK↑)** | **Commit**; hemen ardından (C→D'de) CW değişir |

Faz B'deyken (Q1 = 1, Q2 = 0) bir sonraki MCLK yükselen kenarı her koşulda commit'tir
(Johnson sayacında B'den sonra hep C gelir; STOP ve WAIT bunu etkilemez). Sketch her MCLK
darbesinden önce fazı okur; faz B ise ~1 µs bekler, AB, DB ve CW'yi okur, sonra darbeyi verir.
Bu değerler commit'in kullandığı değerlerdir ve emülatör izindeki satırla aynı anlamdadır.
Çevrim MCLK sayılarak değil fazdan bulunur; bu yüzden WAIT (D'de bekleme) ya da STOP
(C'de bekleme) izi kaydırmaz. Arduino saatinde her faz en az ~1 µs sürer (makinede 250 ns),
yani her şey rahatça oturur. Commit darbesinden sonra faz C değilse iz `END_PHASE` ile biter
(saat ya da Q1/CLK kablosu sorunu).

## Seri protokol

115200 değil **1.000.000 baud** (16 MHz'de U2X ile tam; 8N1). Sorun olursa sketch'te ve
`ardu.py`'de `SERIAL_BAUD` birlikte değiştirilir (test ikisinin aynı olduğunu denetler).

**Çerçeve** (iki yönde aynı):

```
A5 5A | TİP | SIRA | UZUNLUK (0..250) | YÜK | CRC lo | CRC hi
```

- CRC-16, polinom 0x8408 (yansıtılmış CCITT), başlangıç FFFF, son XOR yok
  (avr-libc `_crc_ccitt_update`; "123456789" → 6F91). TİP, SIRA, UZUNLUK ve YÜK üzerinden.
- Çok baytlı sayılar küçük-sonlu (little-endian).
- SIRA: bilgisayar 1..255 verir; cihaz yanıtta aynısını döner. 0 = cihazın kendiliğinden
  gönderdiği açılış duyurusu (açılışta HELLO yanıtı).
- **Yeniden senkron:** bilgisayar bozuk çerçevede yalnız ilk baytı atıp yeniden tarar (kesik
  çerçevenin içindeki sağlam çerçeve de kurtulur, araya giren çöp atlanır). Cihaz bozuk
  çerçevede SYNC aramaya döner, `ERR_CRC` ile yanıt verir; çerçeve içinde iki bayt arası
  100 ms'yi aşarsa yarım çerçeveyi atar. Bilgisayar zaman aşımında ya da `ERR_CRC`'de yeniden
  dener (yalnız tekrarı zararsız komutlarda; TRACE, STEP, CLOCK yeniden denenmez).

**Komutlar** (yanıt tipi = komut | 80h; hata yanıtı tipi FF):

| Komut | Kod | Yük | Yanıt yükü |
|---|---|---|---|
| HELLO | 01 | – | protokol, sürüm (2), en büyük yük, en büyük blok, çerçeve başına kayıt, mod, `"TD8-ARDU"` |
| STATUS | 02 | – | mod, pinler, çevrim sayacı (u32), pinlerdeki AB/DB/CW (6), CRC hataları (u16), kesik çerçeveler (u16), bus tutuluyor |
| MODE | 03 | mod (0 serbest, 1 iz) | mod |
| RESET | 04 | – | pinler, C'den çıkmak için verilen MCLK darbesi (u32) |
| TRACE | 05 | N (u32) | önce TRACE_DATA çerçeveleri, sonda: bitiş nedeni, verilen çevrim (u32), çevrim sayacı (u32), pinler |
| STEP | 06 | – | bitiş nedeni, pinler, çevrim (u32), kayıt (6) |
| CLOCK | 07 | n (u16) | pinler, çevrim sayacı (u32); olan commit'ler TRACE_DATA ile |
| READ | 08 | adres (u16), uzunluk (1..128) | adres (u16), veri |
| WRITE | 09 | adres (u16), bayraklar (bit0 = her baytı geri oku), veri (1..128) | adres (u16), uzunluk |
| BUS | 0A | 1 = bus'ı al ve tut, 0 = bırak | tutuluyor, pinler |

- **TRACE_DATA** (tip A0): ilk çevrim numarası (u32) + en çok 40 kayıt. Kayıt 6 bayt:
  AB lo, AB hi, DB, CW0, CW1, CW2 (CW = bit 0..23, SISTEM-PLANI 4.2). Bilgisayar çevrim
  numaralarının kesintisiz olduğunu denetler; kayıp çerçeve izi geçersiz sayar.
- İz sırasında bilgisayardan gelen **herhangi bir bayt izi durdurur** (`END_ABORT`).
- İz modunda bellek/bus komutları CPU'yu en çok **bir çevrim** ilerletir (BUSREQ senkronlayıcısı
  iki MCLK ister, STOP yalnız C'de etkilidir): o çevrim de TRACE_DATA ile gönderilir, iz kopmaz.
- **Bitiş nedenleri:** 0 tamam, 1 HALT, 2 ilerlemiyor (1024 darbede commit yok: STOP = 1 ya da
  saat yok), 3 bilgisayar durdurdu, 4 commit sonrası faz C değil.
- **Hata kodları:** 1 CRC, 2 bilinmeyen komut, 3 uzunluk, 4 geçersiz değer, 5 yanlış mod,
  6 bus tutuluyor, 7 BUSACK gelmedi, 8 BUSACK erişim sırasında düştü, 9 doğrulama,
  10 reset etki etmiyor, 11 reset sonrası C'den çıkılmadı, 12 makine başka saatle koşuyor.
  Hata yükü: komut, kod, pinler, (doğrulamada adres, yazılan, okunan).
- **Pinler baytı:** b0 Q1, b1 CLK, b2 STOP, b3 BUSACK, b4 /BUSREQ düşük, b5 /RESET düşük,
  b6 bus Arduino'da, b7 iz modu. Faz (Q1, Q2): A = 00, B = 10, C = 11, D = 01.

Bütün sabitler sketch'teki `>>> PROTOKOL` bloğunda ve `ardu.py`'deki aynı adlı blokta;
`tests/test_ardu.py` ikisini karşılaştırır.

## İz hızı (tahmin; ölçülmedi)

| | Değer |
|---|---|
| Çevrim başına bayt | 6 + (5 başlık + 2 CRC + 4 numara) / 40 ≈ 6,28 |
| Seri hattın üst sınırı, 1 Mbaud | ≈ 15.900 çevrim/s → 1.000.000 çevrim ≈ 63 s |
| Arduino işlemci sınırı (derlenmiş kodun komut sayımından kaba tahmin) | çevrim başına ~25 µs darbe + örnekleme, ~55 µs `Serial.write` ve gönderme kesmesi, ~8 µs CRC ≈ 90 µs → **≈ 11.000 çevrim/s** |
| **Beklenen** | **≈ 10.000–12.000 çevrim/s → 1.000.000 çevrim ≈ 1,5 dakika** |
| 115200 baud'da | ≈ 1.800 çevrim/s → 1.000.000 çevrim ≈ 9 dakika |
| Bilgisayar tarafı (sahte cihaz + karşılaştırıcı, ölçüldü) | ≈ 67.000 çevrim/s; darboğaz değil |

Hız gerekirse: `Serial` yerine UDR0'a doğrudan yazmak (kesme ve halka tampon yükü kalkar,
hat sınırına yaklaşır) ya da 2 Mbaud.

## Kullanım

### 1. Derleme ve yükleme (arduino-cli, taşınabilir kurulum)

`araclar\arduino-cli\` altında; yapılandırma her şeyi `araclar\arduino-cli\veri\` altında tutar.
Komutlar `Tasarim` klasöründen, `cmd` içinde:

```
set CLI="C:\Users\deniz\Desktop\bitirme ödevi\araclar\arduino-cli\arduino-cli.exe" --config-file "C:\Users\deniz\Desktop\bitirme ödevi\araclar\arduino-cli\arduino-cli.yaml"
%CLI% compile --fqbn arduino:avr:mega --build-path "C:\Users\deniz\Desktop\bitirme ödevi\araclar\arduino-cli\veri\derleme\td8_debug" arduino\td8_debug
%CLI% upload -p COM5 --fqbn arduino:avr:mega --input-dir "C:\Users\deniz\Desktop\bitirme ödevi\araclar\arduino-cli\veri\derleme\td8_debug" arduino\td8_debug
```

Derleme sonucu (12 Kasım 2026): program 5454 bayt (%2), RAM 711 bayt (%8). **Yükleme
(upload) denenmedi** (kart yok). Yüklerken Arduino makineye bağlı olmasın ya da makinenin
saat seçicisi I3'te olmasın: bootloader sırasında pinler giriştir.

Bilgisayarda gerçek port için: `py -3 -m pip install pyserial` (yalnız `--port` için gerekir).

### 2. İz modu (kabul ölçütü 3)

1. Makineyi durdurun (RUN/STEP → STEP ya da reset basılı), saat seçiciyi **I3**'e alın
   (seçici yalnız makine dururken değiştirilir), RUN/STEP'i **RUN**'a, breakpoint'i kapalıya alın.
2. Programın ROM bölümü flash'ta olmalı (T48). RAM bölümünü araç yükler.
3. Klavyeyi çıkarın (gerçek tuş zamanlaması emülatörde yok); DIP anahtarlarını `--dip`'e yazın.
4. `cd sim` ve:

```
py -3 ardu_cli.py trace examples/komut_testi.asm --port COM5 --cycles 1000000 --dip 00
```

Akış: iz moduna geç → (RAM bölümü varsa) yükle ve doğrula → reset (makine 0. çevrimin
D fazında kalır) → N çevrim iz → MicroEmu ile akarken karşılaştır. Fark varsa ilk farklı
çevrim, farklı alanlar (`AB`, `DB`, `CW.XINC` …) ve önceki 3 çevrim yazılır, çıkış kodu 1.
`--save iz.txt` alınan izi `vectors.parse_trace`'in okuduğu biçimde kaydeder; `--rom ROM.bin`
flash'taki ROM programdan farklıysa emülatöre onu verir.

Adım adım: `step 5` (5 çevrim, her biri `microcode.describe` ile), `clock 1` (tek MCLK;
faz faz), `status`, `peek 8100 16`.

### 3. Yükleme modu

```
py -3 ardu_cli.py load program.asm --port COM5 --reset
```

Makine kendi saatinde (I0) çalışırken programın 8000–EFFF bölümü yazılır, her bayt ve
sonunda bütün blok geri okunup doğrulanır. `--reset` yükledikten sonra makineyi resetler;
programın 8000'den başlaması için SW0 = 1 ve SW0'ı okuyup 8000'e atlayan bir açılış ROM'u
gerekir (`sim/examples/acilis_testi.asm` bunu yapıyor: SW0 = 1 ise büyük RAM testini atlayıp 8000'e geçer). Saat seçici I3'teyse `--mod iz`.

### 4. Donanımsız deneme

Her komut `--port` yerine `--fake` ile sahte cihazda çalışır:

```
py -3 ardu_cli.py trace examples/merhaba.asm --fake
py -3 ardu_cli.py trace examples/merhaba.asm --fake --fake-db-flip 100:0x04
py -3 ardu_cli.py trace examples/komut_testi.asm --fake --fake-cw-stuck 19:0
py -3 ardu_cli.py load program.asm --fake --fake-no-busack
```

Testler: `py -3 -m unittest tests.test_ardu -v`.

**Bağlanırken:** Mega, port açılınca DTR ile resetlenir (bootloader ~1–2 s). Araç DTR'yi
pasif açmayı dener; olmazsa açılış duyurusunu bekler (3 s). Reset istenmiyorsa Mega'nın
RESET–GND arasına 10 µF konabilir (yüklerken çıkarılır). Arduino resetlenince mod serbest
olur ve çevrim sayacı sıfırlanır; makinenin durumu bozulmaz (pinler giriş olur; MCLK
pull-down'ı gerekir).

## Bilinen sınırlar ve denenmeyenler

- **Hiçbir şey donanımda denenmedi:** pin eşlemesi, zamanlamalar (darbe genişlikleri,
  örnekleme beklemesi, /ARD_RD ve /ARD_WR süreleri), reset dizisi (RC'nin bırakma süresi),
  BUSREQ el sıkışması, 1 Mbaud seri hat, USB-seri çevirici, DTR davranışı, `arduino-cli upload`,
  iz hızı.
- Sahte cihaz makineyi çevrim seviyesinde modeller (MicroEmu + Johnson fazı + BUSREQ
  senkronlayıcısı + BUSACK); gerçek kapı gecikmeleri, yüzen hatlar, gürültü yok. Serbest
  modda makinenin komutlar arasında koşması modellenmez.
- Kaybolan bir iz çerçevesi yeniden istenmez; o iz geçersiz sayılır ve baştan alınır.
- Emülatörde RAM açılışta sıfırdır; gerçek RAM rastgeledir. İlk değer vermeden RAM okuyan
  programlar iz karşılaştırmasında farklı çıkar.
- Arduino LED portuna yazamaz (LED latch'i commit'te, CLK ile yüklenir); I/O yazmaları
  etkisizdir. VRAM'e yazma yalnız SLOW modda güvenlidir; VRAM geri okunamaz (doğrulamasız yazın).
- 555 gibi çok yavaş bir dış saat, iz modundaki "başka saat var mı" denetiminden
  (5 ms gözlem) kaçabilir.
- STATUS'taki AB/DB/CW, pinlerin o anki değeridir; makine koşarken anlamsızdır.

## Planla ilgili notlar (eksik ya da çelişkili yerler)

1. **Pin sayısı:** 6.5 "Q1, Q2, CLK" sayıyor; CLK = Q2 (saat tamponundan geçmiş hali). Sketch
   yalnız Q1 ve CLK'yi okur: 57 sinyal (plan ~58).
2. **/ARD_RD ve /ARD_WR pull-up'ları planda yok.** Arduino takılı değilken ya da resetlenirken
   bu hatlar yüzer; /RD = AND(/MRD, /ARD_RD) rastgele düşerse bellek DB'yi sürer (çakışma),
   /WR düşerse RAM bozulur. 10k pull-up gerekli.
3. **MCLK hattı (153 I3) için pull-down yok.** Arduino resetlenirken pin giriştir; I3 seçiliyse
   yüzen saat makineyi rastgele ilerletir.
4. **470 Ω yalnız AB, DB ve strobe'larda.** CW ve durum hatlarında da önerilir: Arduino bir
   hatayla bu pinleri sürerse HC çıkışlarıyla doğrudan kısa devre olur.
5. **Arduino'nun /RESET hattı nereye bağlanıyor** yazmıyor. Açılış RC'sinin (10k/10 µF)
   düğümüne bağlanırsa bırakma ~70–100 ms sürer (sketch 1 s'ye kadar bekler) ve indirince
   10 µF pinden boşalır (470 Ω ile ~10 mA, sorun değil). Ayrı bir 74HC14 girişi daha temiz.
6. **BRQ senkronlayıcısının saati** yazmıyor; MCLK varsayıldı. BUSREQ CPU'yu hemen durdurmaz:
   STOP yalnız C'de etkilidir, yani istek sırasında en çok bir çevrim daha çalışır
   ("kaldığı yerden devam eder" doğru, ama "hemen durur" değil). İz modunda bu çevrim kaydedilir.
7. **SW0 ile 8000'den başlatma:** plan (7.3, ISA-v0-sentez 4.8) açılış ROM'unun SW0 = 1 ise
   8000'e atladığını söylüyor. Bunu `sim/examples/acilis_testi.asm` yapıyor; C programlarının açılış kodu
   `sim/lib/crt0.asm` yapmıyor. Yüklenen program EF00'a kadar uzanmamalı (yığın sayfası).
8. **Arduino'nun saat seçiciyi okuyamaması:** seçici bir anahtar; sketch I3'te olup olmadığını
   bilemez, yalnız reset sonrası fazın kendiliğinden değişip değişmediğine bakar.
9. **Kabul ölçütü 3** için RAM'in açılış içeriği, klavye ve DIP anahtarları emülatörle aynı
   tutulmalı; plan bunları yazmıyor (yukarıdaki iz modu adımları).
