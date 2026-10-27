# TD-8 Sistem Planı

> Sürüm 0.2 · 27 Ekim 2026 · Yapım Ocak–Haziran 2027 · 2 kişilik bitirme projesi
> Bu dosya sistemin Türkçe ana referansı. Kaynaklar:
> - [tasarim-taslaklari/ISA-v0-sentez.md](tasarim-taslaklari/ISA-v0-sentez.md): ayrıntılı tasarım, İngilizce
> - [tasarim-taslaklari/DOGRULAMA.md](tasarim-taslaklari/DOGRULAMA.md): düzeltmeler
> - [sim/td8/isa.py](sim/td8/isa.py): **komut setinin tek kaynağı**
>
> Bir şey değişecekse sıra şu:
> 1. `sim/td8/isa.py` güncellenir;
> 2. `py gen_roms.py` ve testler çalıştırılır;
> 3. bu dosya güncellenir.
>
> Proje yönetimi (bütçe, kararlar, satın alma) için: [PROJE-PLANI.md](PROJE-PLANI.md).

## İçindekiler

0. Sistem bir bakışta
1. Modüller ve sorumluluklar
2. Sinyal sözlüğü
3. Saat, reset, durdurma (M1)
4. Kontrol ünitesi (M2)
5. Veri yolu: registerlar ve ALU (M3, M4)
6. Komut seti
7. Bellek, adres çözme ve I/O (M5)
8. VGA (M6)
9. PS/2 klavye (M7)
10. Hata ayıklama altyapısı (M8)
11. Yazılım
12. Simülasyon planı
13. Takvim: simülasyon dönemi (10 hafta)
14. Yapım dönemi (Ocak – Haziran 2027)
15. Entegre listesi ve breadboard yerleşimi
16. Kabul ölçütleri
17. Çalışma düzeni
18. Açık noktalar

---

## 0. Sistem bir bakışta

| Özellik | Değer |
|---|---|
| İşlemci | TD-8: 8-bit veri, 16-bit adres. Mikrokodlu, 74HC entegrelerle kurulu, kendi komut setimiz. |
| Saat | MCLK 4 MHz, 4 fazlı çevrim, CPU 1 MHz. Tek adım, 555 ve Arduino ile de sürülebilir. |
| Komut seti | 53 komut, 88 opcode. Registerlar: A, X (16), SP, PC. Flag'ler: Z C N V. |
| Bellek | 32 KB ROM, 28 KB RAM, 2 KB VRAM (yalnız yazılır), I/O `F800–FFFF` |
| Görüntü | VGA 640×480 zamanlaması, 40×30 karakter metin, tek renk |
| Giriş | PS/2 klavye |
| Yazılım | Python araç zinciri: ROM üreticileri, assembler, emülatörler, C alt kümesi derleyicisi |
| Hata ayıklama | 24 kontrol LED'i, manuel panel, breakpoint/watchpoint, mikroadım ve komut adımlama, Arduino ile iz karşılaştırma |
| Ölçek | 92 entegre, 24 breadboard, yaklaşık 1.850 kablo |
| Demo | C ile yazılmış Snake, Arduino takılı değilken ROM'dan çalışır |

```
 ┌──────────────┐  CLK, LCLK, WSTB   ┌───────────────────────────────────────────────┐
 │ M1 SAAT      │──────────────────► │ M2 KONTROL                                    │
 │ 4 faz        │◄── STOP, WAIT ──── │ STEP + IR + F ─► 3× uROM ─► 3× 74HC273        │
 │ reset/adım   │                    │ = 24 bitlik kontrol kelimesi (LED'li)         │
 └──────────────┘                    └──────┬──────────────┬───────────────┬─────────┘
                                       ASRC │         DSRC │          DDST │  ALUOP FL MEMW
                                            ▼              ▼               ▼  PCINC PCLD ...
 ┌──────────────────────────────────┐   ┌──────────────────────────────────────────────┐
 │ M3 ADRES: PC AR X (16) + SP (8)  │   │ M4 VERİ: A, IR, F + ALU (2× flash tablo)     │
 │ AB'yi 8× 74HC245 sürer           │   │ DB'yi MEM / A / PCL / PCH sürer              │
 └───────────────┬──────────────────┘   └────────────────────┬─────────────────────────┘
                 │ AB (16 bit)                               │ DB (8 bit)
   ┌─────────────┼───────────────┬──────────────┬────────────┴────┬────────────────┐
   ▼             ▼               ▼              ▼                 ▼                ▼
 ┌────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────────┐ ┌─────────────┐
 │ROM 32K │ │RAM 28K   │ │I/O: LED,     │ │M7 PS/2   │ │M6 VGA: VRAM,     │ │M8 DEBUG:    │
 │(flash) │ │(CY62256) │ │KSTAT, DIP    │ │klavye    │ │font, zamanlama   │ │panel, BP,   │
 └────────┘ └──────────┘ └──────────────┘ └──────────┘ │ROM'u, 25 MHz     │ │Arduino      │
                                                       └──────────────────┘ └─────────────┘
```

**Temel tasarım ilkeleri:**
1. **Kenar disiplini.** Tüm registerlar tek bir saat kenarında yüklenir (B→C, "commit"). Yükleme izni senkron enable ile verilir; saat hattına kapı konmaz.
2. **Çakışmasız bus.** Bus sürücülerinin /OE uçlarını yalnızca kod çözücü çıkışları sürer, yani iki kaynak aynı anda açılamaz.
3. **Güvenli yazma.** Bellek yazma sinyali (/WE) yalnızca A fazında aktiftir. Adres ve veri bu fazdan bir faz önce oturmuş olur ve bir faz sonrasına kadar sabit kalır.
4. **Tek kaynaktan üretim.** Mikrokod, ALU ve zamanlama ROM'ları aynı Python kaynağından üretilir. Emülatör de aynı tabloları kullandığı için donanımla aynı sonucu verir.
5. **Bağımsız VGA.** VGA kendi saatiyle çalışır. CPU bozuk olsa bile görüntü üretir.

---

## 1. Modüller ve sorumluluklar

| Modül | Görev | Entegre | Breadboard | Sorumlu |
|---|---|---|---|---|
| **M1** Saat / reset / durdurma | 4 fazlı saat, kaynak seçimi, STOP/GO, WAIT, reset senkronizasyonu, BUSREQ | 14 | 3 | Kişi 1 |
| **M2** Kontrol ünitesi | STEP sayacı, 3× uROM, kontrol latch'i, kod çözücüler, breakpoint | 13 | 4 | Kişi 2 |
| **M3** Adres registerları | PC, AR, X (16-bit), SP (8-bit), AB sürücüleri | 22 | 6 | Kişi 1 |
| **M4** Veri ve ALU | A, IR, F, 2× ALU flash'ı, DB sürücüleri | 8 | 2 | Kişi 1 |
| CPU yardımcı kapıları | /RD, /WR, STOP mantığı, RAM /CE | 4 | M1 ve M5 kartlarında | Kişi 2 |
| **M5** Bellek + I/O | ROM, RAM, adres çözme, LED portu, KSTAT | 6 | 2 | Kişi 2 |
| **M6** VGA | Nokta ve karakter sayaçları, zamanlama ROM'u, VRAM, font ROM'u, kaydırma registerı, çıkış katı | 19 | 5 | Kişi 1 |
| **M7** PS/2 | Seri alıcı, klavyeyi susturma (inhibit), okuma sonrası temizleme | 6 | 1 | Kişi 1 |
| **M8** Hata ayıklama | Manuel panel (çipsiz), Arduino Mega kartı (çipsiz), 24+ LED | 0 | M2 kartlarında | Kişi 2 |
| **M9** Güç | Raylar, besleme noktaları, bus LED'leri | – | 1 | ikisi |
| **Toplam** | | **92** | **24** | |

**Yazılımda iş bölümü:**
- **Kişi 2:** isa.py, mikrokod, emülatör, assembler, C derleyici, Arduino yazılımı.
- **Kişi 1:** VGA zamanlama ve font araçları, PS/2 yazılım durum makinesi, Snake oyununun mantığı.

Yapımda kablolamayı paylaşın; hiç kimse yalnızca "kendi" kartını kablolamasın. Böylece iki kişi de her modülü bilir.

---

## 2. Sinyal sözlüğü

`/` ile başlayan isimler aktif-düşüktür. `_L` eki, kontrol latch'inden (273) çıkan değeri gösterir.

| Grup | Sinyal | Genişlik | Açıklama |
|---|---|---|---|
| Bus | **AB** | 16 | Adres yolu. Kaynakları PC, AR, X ve EF:SP; seçimi ASRC yapar. Boşta 10k pull-up ile FFFF okunur. |
| | **DB** | 8 | Veri yolu. Kaynakları MEM, A, PCL ve PCH; seçimi DSRC yapar. Boşta 10k pull-down ile 00 okunur. |
| | **R** | 8 | ALU sonucu. Yalnızca A registerının girişine gider, hiç yüzmez (floating olmaz). |
| | **PCIN** | 16 | AR çıkışları, PC'nin paralel yükleme girişlerine bağlı. |
| Saat | MCLK | 1 | 4 MHz ana saat (ya da 555 / Arduino / tek adım). |
| | Q1, Q2 | 2 | Johnson sayacı. Fazlar: A = 00, B = 10, C = 11, D = 01. |
| | **CLK** | 1 | = Q2. B→C'de yükselir. **Tek commit kenarı.** |
| | LCLK | 1 | = /Q1. C→D'de yükselir; kontrol latch'ini yükler. |
| | WSTB | 1 | = NOR(Q1, Q2). A fazında aktif; yazma darbesi. |
| | STOP, WAIT | 1+1 | STOP makineyi C fazında, WAIT ise D fazında tutar. |
| Kontrol kelimesi | ASRC | 2 | Adres kaynağı: 0 PC, 1 AR, 2 X, 3 EF:SP |
| | DSRC | 3 | DB kaynağı: 0 yok, 1 MEM, 2 A, 3 PCL, 4 PCH, 5–6 ayrılmış, 7 yok/panel |
| | DDST | 3 | Hedef: 0 yok, 1 IR, 2 A (R'den), 3 XL, 4 XH, 5 ARL, 6 ARH, 7 yasak |
| | ALUOP | 5 | ALU işlemi (bölüm 5.3) |
| | FL | 1 | Commit'te Z C N V'yi yükle |
| | MEMW | 1 | Bellek/I/O yazma (darbe A fazında) |
| | MARK | 1 | Osiloskop tetiği, LED ve iz işareti |
| | PCINC, PCLD | 1+1 | PC+1 / PC ← AR |
| | ARINC, XINC | 1+1 | AR+1 / X+1 |
| | SPCNT, SPDN | 1+1 | SP sayar; SPDN = 1 aşağı (push), 0 yukarı (pop) |
| | NEXT | 1 | STEP ← 0 (komutun son adımı) |
| | HALT | 1 | Bu adımdan sonra C fazında dur |
| Kod çözücüler | /MRD, /OE_A, /OE_PCL, /OE_PCH | | #DS (74HC138) çıkışları |
| | /DD_IR, /DD_A, /DD_XL, /DD_XH, /DD_ARL, /DD_ARH | | #DD (74HC138) çıkışları; senkron yükleme izinleri |
| Bellek | /RD, /WR | | /RD = AND(/MRD, /ARD_RD); /WR = AND(/MWR, /ARD_WR) |
| | /FPAGE | | F000–FFFF (74HC20) |
| | /VRAMSEL, /IOSEL | | 74HC139'un #MS yarısı |
| | /KBD_RD, /STAT_RD | | #IOR (74HC138) çıkışları |
| VGA | DCLK | | 12.5 MHz nokta saati (25 MHz / 2) |
| | /LD, CCLK | | Karakter sınırı yükleme darbesi ve sayaç saati |
| | H (6), V (10) | | Karakter ve satır sayaçları |
| | /HSYNC, /VSYNC, BLANK_n | | T1 registerından çıkar |
| | VMUX, VWR, /BUFEN | | VRAM sahiplik ve yazma pencereleri |
| | SLOW | | Yavaş saat modu; zamanlama ROM'unun A16 pini |
| PS/2 | KCLK, KDATA | | Klavye hatları (4.7k pull-up) |
| | KRDY | | Byte hazır (start biti işaretçisi) |
| | KCLR, /TIMEOUT | | Okuma sonrası temizleme ve yeniden senkron |
| Debug | /BUSREQ, BUSACK | | Arduino'nun bus'ı alması |
| | /ARD_RD, /ARD_WR | | Arduino'nun okuma/yazma sinyalleri |
| | BRK, GO, STEPMODE, MICRO | | Breakpoint ve adımlama |
| | MANUAL | | Paneli etkinleştirir, uROM /OE'yi kapatır |

---

## 3. Saat, reset, durdurma (M1)

### 3.1 4 fazlı çevrim

MCLK = 4 × CPU saati. İki 74HC74 flip-flop'u Johnson sayacı olarak kullanılır. Sonraki durum mantığı 4 NAND kapısıdır:

```
Q1' = !Q2 | (STOP & Q1)      → STOP = 1 iken C fazında kalır
Q2' =  Q1 | (WAIT & Q2)      → WAIT = 1 iken D fazında kalır
```

| Kenar / faz | Ne olur |
|---|---|
| **C→D** (LCLK ↑) | Kontrol latch'i yeni kelimeyi alır. CLK bu sırada yüksek, 191'in kuralları sağlanır. |
| **D** | Kod çözücüler değişir, AB ve DB kaynakları oturur, bellek erişimi başlar. WAIT burada değerlendirilir. |
| D→A (CLK ↓) | Hiçbir şey saatlenmez. WSTB yükselir. |
| **A** | MEMW varsa /WE düşük. VRAM yazması buraya ancak pencere açıkken gelir. |
| A→B | /WE yükselir. |
| **B** | Her şey bir faz boyunca sabit kalır; okuma verisi ve ALU sonucu oturur. |
| **B→C** (CLK ↑) | **Commit:** PC, AR, X, SP, A, IR, F, STEP, LED latch'i, BRK ve KCLR yüklenir (izinliyse). |
| **C** | uROM'lar yeni (STEP, IR, F) için arama yapar. STOP değerlendirilir. Duran makine her zaman bu fazda bekler. |

### 3.2 Saat kaynakları (74HC153, yalnız makine dururken değiştirilir)

| Seçim | Kaynak | CPU saati |
|---|---|---|
| I0 | 4.000 MHz osilatör | 1 MHz (varsayılan) |
| I1 | 6 ya da 8 MHz osilatör soketi | 1.5 / 2 MHz (deneysel) |
| I2 | NE555 + 74HC14 | ~0.25 Hz – 1 kHz |
| I3 | Arduino pini | İz modu |

S1 = 1 olduğunda kaynak yavaştır. Bu bilgi **SLOW** sinyali olarak VGA zamanlama ROM'unun A16 pinine gider (bölüm 8.5).

### 3.3 Durdurma ve adımlama

```
STOP = BRQ_s | ((HALT_L | BRK_L | (STEPMODE_s & (MICRO | NEXT_L))) & !GO)
```

- **GO butonu:** RC + 74HC14 + 74HC175 (sync1, sync2, prev). `GO = sync2 & !prev` tam bir MCLK sürer, böylece tam bir çevrim çalışır.
- **MICRO anahtarı:** Her mikroadımda ya da yalnız komut sonunda (NEXT) durmayı seçer.
- **HALT komutu:** Yazılım breakpoint'idir; GO ile devam edilir.

### 3.4 Reset

- **Kaynaklar:** Açılış RC'si (10k/10µF), RESET butonu ve Arduino'nun açık-drain hattı. Hepsi 74HC14'ten geçer, ardından 74HC74'te 2 flip-flop'la senkronlanır. Reset hemen etki eder, bırakılması MCLK'ya senkrondur.
- **/RESET_s'nin yaptıkları:**
  - Johnson sayacı C fazına alınır.
  - Kontrol latch'i NOP kelimesine (tümü sıfır) temizlenir.
  - STEP, PC, AR, X ve F 0 olur; SP FF olur (191 /PL).
  - BRK ve BUSACK temizlenir, PS/2 registerları temizlenir.
- **Bırakılınca:** C→D kenarında FETCH latch'lenir ve program **0000** adresinden başlar.

### 3.5 Saat dağıtımı

- CLK, saat tamponu olarak kullanılan bir 74HC245'ten geçer. Her çıkışta 47 Ω seri direnç var ve her dal en fazla 4 yük sürer (yıldız bağlantı).
- **A ve F aynı dalda olmalı.** A → ALU → F döngüsünün hold payı yalnızca ~8 ns.
- LCLK üç adet 273'ü doğrudan sürer (33 Ω).
- Her çipte 100 nF, her kartta 10–47 µF kondansatör.

### 3.6 WAIT (VRAM penceresi kapalıyken yazmayı bekletir)

74HC27 Türkiye'de bulunmadığı için bunun yerine 4. bir 74HC138 kullanılır:

```
74HC138: G1 = VCC, /G2A = /FPAGE, /G2B = A11, A = /MEMW_L, B = VWR_s, C = GND
Y0 = /WAIT   (F000–F7FF'ye yazma VE pencere kapalı)
Johnson: Q2' = NAND(/Q1, OR(/WAIT, /Q2))
```

En kötü durum gecikmesi ~236 ns. D fazı 1 MHz'de 250 ns olduğu için sığar.

---

## 4. Kontrol ünitesi (M2)

### 4.1 Mikrokod ROM adresi (3× SST39SF010, adres hatları paralel)

| Pin | A0–A3 | A4–A11 | A12 | A13 | A14 | A15 | A16 |
|---|---|---|---|---|---|---|---|
| Sinyal | STEP | IR | Z | C | N | V | BANK jumper'ı |

- Pinler: /CE = GND, /WE = VCC, **/OE = MANUAL** (panel modunda çıkışlar kapanır).
- **BANK jumper'ı:** 0 = denenmiş imaj, 1 = deneysel imaj. Yeni mikrokodu bank 1'e yazıp jumper'la deneyin; çalışmazsa jumper'ı geri alın.

### 4.2 Kontrol kelimesi (24 bit, ROM'da aktif-yüksek)

| ROM | Bit | Alan |
|---|---|---|
| uROM0 | 0–1 | ASRC |
| | 2–4 | DSRC |
| | 5–7 | DDST |
| uROM1 | 8–12 | ALUOP |
| | 13 | FL |
| | 14 | MEMW |
| | 15 | MARK |
| uROM2 | 16 | PCINC |
| | 17 | PCLD |
| | 18 | ARINC |
| | 19 | XINC |
| | 20 | SPCNT |
| | 21 | SPDN |
| | 22 | NEXT |
| | 23 | HALT |

- **Tümü sıfır kelime gerçek bir NOP'tur.** Kullanılmayan adımlara `HALT MARK NEXT` yazılır.
- Kutup düzeltmeleri tek bir 74HC04 ile yapılır: FL → F /PE, PCLD → PC /PE, NEXT → STEP /PE, SPCNT → SP /CE, MEMW → /MEMW.

### 4.3 Kod çözücüler

| İsim | Çip | Girişler | Çıkışlar |
|---|---|---|---|
| #DS | 74HC138 | DSRC; /G2A = BUSACK | Y1 /MRD, Y2 /OE_A, Y3 /OE_PCL, Y4 /OE_PCH |
| #DD | 74HC138 | DDST | Y1 /DD_IR, Y2 /DD_A, Y3 /DD_XL, Y4 /DD_XH, Y5 /DD_ARL, Y6 /DD_ARH |
| #AS | 74HC139 (yarısı) | ASRC; /G = BUSACK | AB tamponlarının /OE çiftleri |

### 4.4 Adım sayacı

- 74HC161, CP = CLK.
- `/PE = NOT NEXT`, P = 0000: senkron sıfırlama. Asenkron /CLR kullanılmaz, böylece glitch riski yok.
- En uzun komutlar (INCW, DECW, JMPI) 7 adım sürer; 16 adım sınırının çok altında.

### 4.5 Mikrokod üretici kuralları

Üretici, `sim/td8/microcode.py` içindeki kontrol işlevlerinde bu kuralları otomatik denetler:

1. **MEMW** varsa DSRC ∈ {A, PCL, PCH} olmalı. Yazma sırasında belleğin /OE'si hiçbir zaman açık olmaz.
2. **Yasak kodlar:** DDST ≠ 7. DSRC 5 ve 6 (ayrılmış) kullanılmaz.
3. **PC:** PCLD ve PCINC aynı adımda olmaz. PCLD, ARL veya ARH yüklemesiyle aynı adımda olmaz.
4. **ALU:** DDST = A ise ALU işlemi açıkça yazılmış olmalı (yüklemelerde PASSB).
5. **Yükleme ile artırma çakışmaz:** ARL/ARH yüklemesi ARINC ile, XL/XH yüklemesi XINC ile aynı adımda olmaz.
6. **Stack:** SPDN varsa SPCNT ve MEMW de olmalı (push).
7. **Fetch:** 0. adım her opcode, her flag değeri ve her bank için FETCH'tir.
8. **Komut sonu:** Her yol 16 adım içinde NEXT'e ulaşır. NEXT yalnızca son adımda bulunur.

---

## 5. Veri yolu: registerlar ve ALU (M3, M4)

### 5.1 Registerlar (hepsi CLK ↑ ile yüklenir, senkron izinli)

| Reg | Çip | Yükleme | Sayma | Reset | Çıkışlar |
|---|---|---|---|---|---|
| PC | 4× 74HC161 | /PE = /PCLD; P = AR (16 bit birden) | CEP = PCINC | 0000 | AB (2× 245), DB (PCL, PCH 245'leri), 16 LED |
| AR | 4× 74HC161 | P = DB; alt çift /DD_ARL, üst çift /DD_ARH | CEP = ARINC | 0000 | PCIN, AB (2× 245), 16 LED |
| X | 4× 74HC161 | P = DB; /DD_XL, /DD_XH | CEP = XINC | 0000 | AB (2× 245), 16 LED |
| SP | 2× 74HC191 | DB'den yüklenmez; D girişleri 1'e bağlı | /CE = NOT SPCNT; üst /CE = NAND(SPCNT, MAX/MIN_alt); D/U = SPDN | FF (/PL) | AB alt (245); AB üst = EF sabiti (245); 8 LED |
| A | 74HC377 | D = R, /E = /DD_A | – | belirsiz | ALU, DB (245), 8 LED |
| IR | 74HC377 | D = DB, /E = /DD_IR | – | belirsiz | uROM A4–A11, 8 LED |
| F | 74HC161 (4-bit register olarak) | /PE = NOT FL | CEP = CET = 0 | 0000 | uROM A12–A15, ALU, 4 LED |

**74HC161 yerine 74HC163:** VGA sayaçları dışında her yerde 161 şart, çünkü reset sırasında saat kenarı gelmez ve asenkron /MR gerekir. VGA sayaçlarında 161 de kullanılabilir: senkron temizleme yerine /PE ile 0000 yüklenir.

### 5.2 ALU: 2 flash'ta tablo

| ROM | Adres pinleri | Veri pinleri |
|---|---|---|
| ALU-L | A0–3 = A[3:0], A4–7 = DB[3:0], A8 = C, A9 = A[4], A10–14 = ALUOP, A15 = A[7], A16 = jumper | D0–3 = R[3:0], D4 = c4, D5 = Zlo, D6 = Clo |
| ALU-H | A0–3 = A[7:4], A4–7 = DB[7:4], A8 = c4, A9 = Zlo, A10 = Z, A11–15 = ALUOP, A16 = jumper | D0–3 = R[7:4], D4 = Z, D5 = Chi, D6 = N, D7 = V |

- `C = Clo OR Chi` (tek bir 74HC32 kapısı).
- İki flash da sürekli etkindir: /CE = /OE = GND. Çıkışları ortak bir bus'a bağlanmaz.

### 5.3 ALU işlem kodları (ALUOP)

| Kod | İsim | Sonuç | Z | C | N | V |
|---|---|---|---|---|---|---|
| 00 | PASSB | B | B==0 | korunur | B7 | **B6** (BIT için) |
| 01 / 02 | ADD / ADC | A+B / A+B+C | R==0 / **zincirli** | elde | R7 | taşma |
| 03 / 04 | SUB / SBC | A−B / A−B−!C | R==0 / **zincirli** | borç yok = 1 | R7 | taşma |
| 05–07 | AND / OR / XOR | A op B | R==0 | korunur | R7 | 0 |
| 08 / 09 | INC / DEC | A±1 | R==0 | korunur | R7 | taşma |
| 0A | NOT | ~A | R==0 | korunur | R7 | 0 |
| 0B | NEG | 0−A | R==0 | A==0 | R7 | A==80 |
| 0C / 0D | SHL / ROL | A<<1, bit0 = 0 / C | R==0 | A7 | R7 | 0 |
| 0E / 0F / 10 | SHR / ROR / ASR | A>>1, bit7 = 0 / C / A7 | R==0 | A0 | R7 | 0 |
| 11 | PASSA | A | R==0 | korunur | R7 | 0 |
| 12 / 13 | CLC / SEC | A | R==0 | 0 / 1 | R7 | 0 |
| 14 | SEX | A7 ? FF : 00 | R==0 | korunur | R7 | 0 |
| 15 / 16 | INCB / ADCB0 | B+1 / B+C | R==0 / **zincirli** | elde | R7 | taşma |
| 17 / 18 | DECB / SBCB0 | B−1 / B−!C | R==0 / **zincirli** | borç yok | R7 | taşma |
| 19–1F | POISON | A5 | 1 | 1 | 1 | 1 |

**Zincirli Z:** `Z = Z_eski AND (sonuç == 0)`. Yükleme ve saklama komutları flag'lere dokunmaz. Bu sayede iki byte'lık işlemden sonra Z, 16-bit sonucun gerçek Z'si olur.

**POISON:** Yanlış bir ALUOP kodu gelirse A = A5 olur ve dört flag'in hepsi 1 olur. Bu LED'lerde hemen göze çarpar.

---

## 6. Komut seti

### 6.1 Programcının gördüğü model

| Register | Genişlik | Not |
|---|---|---|
| A | 8 | Akümülatör. Tek ALU hedefi; her ikili işlemin sol girişi. |
| X | 16 | Pointer. Yalnızca yüklenir. `(X)` ve `(X+)` ile erişilir; artırma ek çevrim istemez. |
| SP | 8 | Stack `EF00–EFFF` sayfasında. Boş-azalan çalışır, açılışta `FF`. |
| PC | 16 | Açılışta `0000`. |
| F | Z C N V | Yalnızca ALU adımları değiştirir. |

**Adresleme modları:**

| Mod | Yazım | Örnek |
|---|---|---|
| Anında değer | `#n` | `LDA #$41` |
| Mutlak | `abs` | `LDA $8000` |
| X üzerinden | `(X)` | `LDA (X)` |
| X üzerinden, sonra X+1 | `(X+)` | `STA (X+)` |
| Bellek üzerinden atlama | `JMPI (abs)` | `JMPI (tablo)` |

Dallanmalar mutlak adres kullanır, yani menzil sınırı yok.

### 6.2 Opcode haritası

**M grubu:** `opcode = 0x40 + 4·işlem + mod`. Mod 0 `#`, 1 `abs`, 2 `(X)`, 3 `(X+)`.

| İşlem | # | abs | (X) | (X+) | Flag'ler |
|---|---|---|---|---|---|
| LDA | 40 | 41 | 42 | 43 | – |
| STA | (44 yasak) | 45 | 46 | 47 | – |
| ADD | 48 | 49 | 4A | 4B | Z C N V |
| ADC | 4C | 4D | 4E | 4F | Zz C N V |
| SUB | 50 | 51 | 52 | 53 | Z C N V |
| SBC | 54 | 55 | 56 | 57 | Zz C N V |
| AND | 58 | 59 | 5A | 5B | Z N, V=0 |
| OR | 5C | 5D | 5E | 5F | Z N, V=0 |
| XOR | 60 | 61 | 62 | 63 | Z N, V=0 |
| CMP | 64 | 65 | 66 | 67 | Z C N V |
| CPC | 68 | 69 | 6A | 6B | Zz C N V |
| BIT | (6C yasak) | 6D | 6E | 6F | N=M7, V=M6, Z=(M==0) |

Zz = zincirli Z. Çevrim sayısı: `#` 2, `abs` 4, `(X)` ve `(X+)` 2. Byte sayısı: `#` 2, `abs` 3, `(X)` ve `(X+)` 1.

**Diğer gruplar:**

| Opcode | Komut | Byte | Çevrim | Etki |
|---|---|---|---|---|
| 00 | HALT | 1 | 2 | Dur; GO ile devam |
| 01 | NOP | 1 | 2 | – |
| 80–88 | INC DEC NOT NEG SHL ROL SHR ROR ASR | 1 | 2 | A ← işlem(A), flag'ler |
| 89 | TST | 1 | 2 | A'nın flag'leri (Z, N, V=0) |
| 8A / 8B | CLC / SEC | 1 | 2 | C ← 0/1. Z ve N'yi A'dan yeniden hesaplar, V=0. |
| 8C | SEX | 1 | 2 | A ← (A7 ? FF : 00), yani `(int)(signed char)` için üst byte |
| 90 / 91 | LDX #nn / LDX abs | 3 / 3 | 3 / 5 | X ← değer / X ← M16 |
| 92 | INX | 1 | 2 | X ← X+1 |
| 93 / 94 | TAXL / TAXH | 1 | 2 | XL ← A / XH ← A |
| 98 / 99 | INCW abs / DECW abs | 3 | 7 | M16 ± 1. **A bozulur** (yeni üst byte). Z 16-bit olarak hesaplanır. |
| A0 / A1 | PHA / PLA | 1 | 2 / 3 | Push / pop A |
| A2 | JMP abs | 3 | 4 | PC ← abs |
| A3 | CALL abs | 3 | 5 | PCH ve PCL push edilir; PC ← abs |
| A4 | RET | 1 | 5 | PCL ve PCH pop edilir |
| A5 | JMPI (abs) | 3 | 7 | PC ← M16[abs]. **A bozulur.** |
| B0–BD | Bcc abs | 3 | 4 / 3 | Koşul sağlanırsa PC ← abs (alınırsa 4, alınmazsa 3 çevrim) |
| diğer | tanımsız | – | 2 | HALT + MARK |

### 6.3 Dallanma koşulları (`B0 + cc`)

| cc | Komut | Alınır eğer | C karşılığı (`CMP lo` / `CPC hi` sonrası) |
|---|---|---|---|
| 0 / 1 | BEQ / BNE | Z / !Z | `==` / `!=` |
| 2 / 3 | BCS (=BHS) / BCC (=BLO) | C / !C | işaretsiz `>=` / `<` |
| 4 / 5 | BMI / BPL | N / !N | işaret; klavye hazır mı |
| 6 / 7 | BVS / BVC | V / !V | VRAM penceresi (BIT sonrası) |
| 8 / 9 | BLT / BGE | N≠V / N=V | işaretli `<` / `>=` |
| A / B | BGT / BLE | !Z & N=V / Z \| N≠V | işaretli `>` / `<=` |
| C / D | BHI / BLS | C & !Z / !C \| Z | işaretsiz `>` / `<=` |

### 6.4 Mikroadım tabloları

Her adım bir tam çevrimdir. Gösterim: `adres kaynağı / DB kaynağı / hedef / ALU işlemi · diğer bitler`. Tüm tablo [sim/td8/isa.py](sim/td8/isa.py) içinde.

| Komut | Adımlar (FETCH'ten sonra) |
|---|---|
| FETCH (0. adım) | `PC/MEM/IR · PCINC` |
| OP1 / OP2 | `PC/MEM/ARL · PCINC` / `PC/MEM/ARH · PCINC` |
| LDA abs | OP1, OP2, `AR/MEM/A/PASSB · NEXT` |
| ADD (X+) | `X/MEM/A/ADD · FL XINC NEXT` |
| STA abs | OP1, OP2, `AR/A/-/- · MEMW NEXT` |
| PHA | `SP/A/-/- · MEMW SPCNT SPDN NEXT` |
| PLA | `SPCNT`, `SP/MEM/A/PASSB · NEXT` |
| CALL | OP1, OP2, `SP/PCH · MEMW SPCNT SPDN`, `SP/PCL · MEMW SPCNT SPDN PCLD NEXT` |
| RET | `SPCNT`, `SP/MEM/ARL · SPCNT`, `SP/MEM/ARH`, `PCLD NEXT` |
| JMPI | OP1, OP2, `AR/MEM/A/PASSB · ARINC`, `AR/MEM/ARH`, `-/A/ARL`, `PCLD NEXT` |
| INCW | OP1, OP2, `AR/MEM/A/INCB · FL`, `AR/A · MEMW ARINC`, `AR/MEM/A/ADCB0 · FL`, `AR/A · MEMW NEXT` |
| Bcc (alınır) | OP1, OP2, `PCLD NEXT` |
| Bcc (alınmaz) | `PCINC`, `PCINC NEXT` |

---

## 7. Bellek, adres çözme ve I/O (M5)

### 7.1 Bellek haritası

| Adres | İçerik |
|---|---|
| `0000–7FFF` | ROM, 32 KB (SST39SF010). A15 ve A16 jumper'la seçilir → 4 program bankı. |
| `8000–EFFF` | RAM, 28 KB (CY62256). `8000–80FF` runtime pseudo-registerları, `EF00–EFFF` stack. |
| `F000–F7FF` | VRAM, yalnızca yazılır. Karakterin adresi `F000 + 64·satır + sütun`. 0–39. sütunlar görünür. |
| `F800–FFFF` | I/O. Kayıtlar her 8 byte'ta bir tekrarlanır. |

### 7.2 Adres çözme

| Sinyal | Mantık |
|---|---|
| ROM /CE | = A15 (doğrudan kablo) |
| /FPAGE | NAND4(A15, A14, A13, A12), 74HC20 |
| RAM /CE | NAND(A15, /FPAGE) |
| /VRAMSEL, /IOSEL | 74HC139 #MS: /G = /FPAGE, A = A11, B = GND |
| #IOR | 74HC138: A0..A2 adres girişleri, /G2A = /IOSEL, /G2B = /RD → Y0 /KBD_RD, Y1 /STAT_RD |
| /LED_E | OR(/IOSEL, /MEMW), commit'te örneklenir |
| VRAM /WE | OR(/WR, /VRAMSEL) |
| /MWR | NAND(MEMW_L, WSTB) |

### 7.3 I/O registerları

| Adres | Yön | İsim | Anlamı |
|---|---|---|---|
| F800 | Okuma | KBD | PS/2 scan code byte'ı. KRDY = 1 iken okununca KRDY sıfırlanır ve klavye serbest kalır. |
| F801 | Okuma | KSTAT | b7 = KRDY (`BIT` ile N'ye düşer), b6 = VRAM penceresi açık (`BIT` ile V'ye düşer), b5..b0 = DIP switch'ler. SW0 = 1 ise açılışta 8000'deki program çalıştırılır. |
| F800 | Yazma | LEDS | 8 LED (74HC377) |

### 7.4 RAM yazma zamanlaması (CY62256-70, 1 MHz)

| Parametre | Gereken | Sağlanan |
|---|---|---|
| Adres kurulumu (/WE düşmeden önce) | 0 | ≥ 150 ns |
| /WE darbe genişliği | 50 ns | 250 ns |
| Veri kurulumu | 30 ns | ≥ 400 ns |
| Tutma (/WE yükseldikten sonra) | 0 | 250 ns |

---

## 8. VGA (M6)

### 8.1 Saatler

- 25.000 MHz osilatör → 74HC74 ile ikiye bölünür → **DCLK = 12.5 MHz** (80 ns). Bir nokta, ekranda iki VGA pikseli eder.
- Nokta sayacı bir 74HC163'tür. LD flip-flop'u: D = NAND4(Q2, Q1, Q0, 1), çıkış /Q'dan alınır (74HC20 ile).
- Bu sayede LD yalnızca karakterin 0. noktasında yüksek olur. CCLK = /LD.

| Değer | 25.000 MHz ile | Standart (25.175 MHz) |
|---|---|---|
| Yatay frekans | 31.25 kHz | 31.47 kHz |
| Dikey frekans | 59.5 Hz | 59.94 Hz |

### 8.2 Sayaçlar ve zamanlama ROM'u

**HCHAR (6 bit, 0–49) ve VLINE (10 bit, 0–524):**
- Senkron sayaçlar, CCLK ile sayar.
- Temizleme sinyalleri ROM'dan gelir: /HEND ve /VEND.
- Kullanılmayan değerler de temizlemeyi tetikler, böylece sistem açılışta bir kare içinde kendini toplar.

**Zamanlama ROM'u** (SST39SF010). Adres: A0–5 = H, A6–15 = V, A16 = SLOW.

| Bit | Sinyal | Bank 0 (normal) | Bank 1 (SLOW) |
|---|---|---|---|
| D0 | /HSYNC | H 41–46'da 0 (48 nokta) | aynı |
| D1 | /VSYNC | V 490–491'de 0 | aynı |
| D2 | BLANK_n | H 0–39 ve V 0–479'da 1 | aynı |
| D3 | /BUFEN | (V481, H10)'dan (V523, H40)'a kadar 0 | hep 0 |
| D4 | /HEND | H = 49'da ve H ≥ 50'de 0 | aynı |
| D5 | /VEND | V = 524 ve H = 49'da; V ≥ 525'te 0 | aynı |
| D6 | VMUX | V 481–523'te 1 | hep 1 |
| D7 | VWR | V 482–522'de 1 | hep 1 |

- **Yatay:** 40 görünür + 1 ön porch + 6 sync + 3 arka porch = 50 karakter = 400 nokta.
- **Dikey:** 480 + 10 + 2 + 33 = 525 satır.
- Sync'ler negatiftir.
- **T1 registerı** (74HC377, /E = /LD) ROM çıkışlarını karakter sınırında yakalar.

### 8.3 Karakter hattı

1. **Slot n:** VRAM adresi `{V8..V4, H5..H0}` olur (157'ler üzerinden). Karakter kodu ~115 ns içinde gelir.
2. **Font ROM'u:** Adresi A0–2 = V3..V1 (font satırı; her satır iki kez gösterilir), A3–10 = karakter kodu, A11–16 = font bankası jumper'ları. Çıkışı ≤ 260 ns'de hazır olur (bütçe 615 ns).
3. **Slot sonu:** 74HC166 glyph'i yükler (D7 = en soldaki nokta) ve T1, ROM(H = n)'yi yakalar.
4. **Slot n+1:** 8 nokta kaydırılarak dışarı verilir; sync ve blank de aynı anda çıkar. Böylece hizalama otomatik olur.

### 8.4 Çıkış katı

| Çıkış | Devre | Seviye / bağlantı |
|---|---|---|
| R, G, B | 74HC08: AND(QH, BLANK_n). Renk jumper'ı (beyaz/yeşil/amber), 470 Ω seri | ~0.69 V |
| HSYNC, VSYNC | 100 Ω seri | DE-15 pin 13, 14 |
| Toprak | | DE-15 pin 5–8 ve 10 |

### 8.5 CPU ile VRAM paylaşımı

| Pencere | Satırlar | Anlamı |
|---|---|---|
| VMUX | 481–523 | VRAM'in sahibi CPU |
| VWR | 482–522 | CPU yazmaya başlayabilir (kare başına ~1.31 ms) |
| /BUFEN | VMUX'un içinde | DB → VRAM tamponu açık. VRAM çıkışıyla en az 6 µs arayla açılıp kapanır. |

- **"Bekle, kaybetme":** Pencere kapalıyken yazmaya çalışan CPU D fazında bekletilir. Yazma hiç kaybolmaz.
- **SLOW modu:** 555 ya da Arduino saatinde VRAM sürekli CPU'nundur. Görüntü bozulur ama sync bozulmaz.
- **NO-VGA jumper'ı:** VGA kartı takılı değilken VWR_s = 1'e zorlanır, CPU takılmaz.

---

## 9. PS/2 klavye (M7)

| İşlev | Devre |
|---|---|
| Hat | KCLK ve KDATA, 4.7k pull-up + 74HC14. Mini-DIN-6: 1 veri, 3 GND, 4 +5 V, 5 saat. |
| Kaydırma | 2× 74HC164, KCLK'nın yükselen kenarında kaydırır. /KDATA girer: start biti (0) 1 olarak girip işaretçi görevi görür. |
| Çerçeve sonu | 11. kenarda start biti SR2.Q2'ye gelir → **KRDY**. |
| Okuma | 74HC540 (tersleyen, 3 durumlu) gerçek byte'ı DB'ye koyar; /OE1 = /KBD_RD. |
| Susturma | KRDY ve KCLR, diyotla VEYA'lanıp 2N7000'i sürer → KCLK düşük tutulur. Klavye bekler, byte kaybolmaz. |
| Temizleme | KCLR flip-flop'u: D = AND(KBD_RD, KRDY), CP = CLK. Bir çevrimlik temizleme darbesi verir: `/CLR164 = AND(/RESET_s, /KCLR, /TIMEOUT)`, iki 74HC08 kapısıyla. |
| Zaman aşımı | 22k / 10 nF, ~190 µs. Yarım kalan çerçeveyi atar. |

**Yazılım kuralları:**
- F800'ü yalnızca KRDY = 1 görüldükten sonra okuyun.
- `F0 xx` (tuş bırakma) ve `E0` önekini atlayın.
- W/A/S/D ve ok tuşlarını eşleyin.
- Açılışta klavyenin gönderdiği `AA` byte'ını bir kez okuyup atın.

---

## 10. Hata ayıklama altyapısı (M8)

| Araç | Ne işe yarar |
|---|---|
| 24 kontrol LED'i + PC/AR/X (16'şar), A, IR, SP LED'leri + faz, STOP, WAIT, HALT, BRK, BUSACK, MARK | Her mikroadımda makinenin durumunu gözle görmek |
| Manuel panel: MANUAL anahtarı + 24 DIP switch (47k/4.7k) + DB için 8 DIP switch (2.2k) | Mikrokod takılmadan her modülü elle test etmek. Örnek: `DDST=A ALUOP=PASSB FL`, veri 80, GO → A = 80, N = 1. |
| Breakpoint/watchpoint: 2× 74HC688 kademeli + 16 DIP switch | Belirtilen adres okunduğunda ya da yazıldığında makineyi durdurmak |
| RUN/STEP + MICRO + GO | Mikroadım ya da komut bazında adımlamak |
| HALT komutu, MARK biti | Yazılım breakpoint'i, osiloskop tetiği |
| Arduino Mega (~58 pin, 470 Ω seri dirençlerle, çip yok) | **İz modu:** MCLK'yı Arduino verir, her commit'te AB, DB ve kontrol kelimesini kaydeder. **Yükleme modu:** BUSREQ → RAM'e yazar → bırakır → SW0 ile reset. |
| `sim/` emülatörü | Arduino izini emülatör iziyle karşılaştırır ve **farkın başladığı ilk çevrimi** gösterir |

---

## 11. Yazılım

### 11.1 Araç zinciri

```
sim/td8/isa.py ──► gen_roms.py ──► build/urom0..2, alu_lo/hi, vga_timing, font (.bin + .hex)
       │                                  │
       ├──► asm.py (assembler) ──► program ROM imajı (.bin, T48 ile yazılır)
       │
       ├──► emu_micro.py: mikroadım emülatörü, ROM imajlarını aynen çalıştırır
       └──► emu_ref.py: komut seviyesi referans; mikrokodu çapraz kontrol eder

C kaynağı ──► tdcc (Python C derleyicisi, yapımın 1–11. haftası) ──► assembly ──► asm.py
```

### 11.2 C alt kümesi

- **Tipler:** `char` (işaretsiz), `signed char`, `int` (16-bit), `unsigned`, pointer'lar.
- **Veri:** global 1-D ve 2-D diziler, string'ler, ROM'da `const` tablolar, `volatile`.
- **Deyimler:** if/else, while, do/while, for, break, continue, return, switch (karşılaştırma zinciri ya da JMPI tablosu).
- **Operatörler:** Hepsi. `* / %` ve değişken miktarda kaydırma runtime'a çağrılır (`__mul16` ~250–400 çevrim, `__divmod16` ~600–900 çevrim).
- **v1'de yok:** recursion (derleyici hata verir), struct, long, float, fonksiyon pointer'ı.

### 11.3 Çağırma kuralı: statik çerçeve

- **Çerçeveler:** Her fonksiyonun parametreleri, yerelleri ve geçicileri sabit RAM adreslerinde durur. Birbirini çağırmayan fonksiyonların çerçeveleri, çağrı grafiğine göre üst üste bindirilir.
- **Argümanlar:** Çağıran, argümanları doğrudan çağrılanın parametre yuvalarına yazar. Argüman içinde çağrı varsa önce kendi geçicisine hesaplar.
- **Dönüş değeri:** `char` A'da, `int` ya da pointer `__rv`'de (8000).
- **Stack:** Yalnızca dönüş adresleri ve runtime'ın PHA/PLA'ları için.
- **crt0:** VRAM'i temizler, `.data`'yı kopyalar, `.bss`'i sıfırlar, `CALL main`, `HALT`.

**Örnek maliyetler (1 MHz'de µs):**

| Kod | µs |
|---|---|
| `a = b + c` (int) | 24 |
| `*p = x` | 11 |
| `if (x < y)` | 19–20 |
| 2 parametreli çağrı + dönüş | 82 |
| VRAM'e string yazma | 37 / karakter |

### 11.4 Snake

- **Veri:** `board[30*64]` RAM'de VRAM'in gölgesi (VRAM okunamadığı için). `body[256]` halka tampon. Konum = `satır·64 + sütun`.
- **Hamle başına ~0.6 ms.** Hız VWR kenarlarını sayarak ayarlanır: 6–8 karede bir hamle.
- **Yem:** 16-bit LFSR ile yerleştirilir.
- **Skor:** 4 basamaklı ondalık karakter olarak tutulur, bölme gerekmez.

---

## 12. Simülasyon planı

### 12.1 Araçlar

| Araç | Ne için |
|---|---|
| **Digital** (hneemann, Java 11+) | Devre simülasyonu; 74xx kütüphanesi, test vektörleri, VGA monitörü |
| **Python 3.12** | `sim/`: ROM imajları, assembler, emülatörler, testler; ileride C derleyicisi |
| KiCad | 13–15. haftada temiz şemalar ve breadboard yerleşimi |
| PulseView | Lojik analizör (yapım döneminde) |
| Git | Her çalışan durumun kaydı (ROM imajları dahil) |

### 12.2 Digital modeli

- **Dosya düzeni:** Her modül ayrı bir `.dig` dosyası olur: `m1_saat.dig`, `m2_kontrol.dig`, `m3_adres.dig`, `m4_alu.dig`, `m5_bellek.dig`, `m6_vga.dig`, `m7_ps2.dig`. Üst seviye `td8.dig` hepsini bağlar.
- **Çipler:** Mümkün olduğunca Digital'in **74xx kütüphanesindeki pinli çipler** kullanılır. Böylece şema breadboard kablolamasıyla bire bir eşleşir.
- **İlk hafta kontrolü:** Kütüphanede hangi çiplerin olduğuna bakın. Olmayanlar için aynı pin düzeninde alt devre yazın (olası adaylar: 74HC191, 166, 540, 688).
- **Flash'lar:** Digital'in ROM bileşenine `build/*.bin` (ya da `.hex`) imajları yüklenir.
- **Zamanlama:** Digital gerçek gecikmeleri modellemez. Zamanlama bölüm 3 ve 5.4'teki hesapla, ardından osiloskopla doğrulanır.

### 12.3 Modül testleri ve kabul ölçütleri

| Modül | Digital'de test | Kabul ölçütü |
|---|---|---|
| M1 Saat | Faz sırası; STOP C'de, WAIT D'de tutuyor mu; GO tam 1 çevrim mi; reset C'ye park ediyor mu | Test vektörlerinin hepsi geçer |
| M2 Kontrol | uROM'lara imajlar yüklenir; IR, flag ve STEP verilir; latch çıktısı karşılaştırılır | Python'un ürettiği 1.000 rastgele vektör geçer |
| M3 Adres | PC yükleme/artırma; AR ve X byte yükleme + artırma; SP push/pop | x0/xF ve FF/00 sınırları dahil geçer |
| M4 ALU | Tablolar yüklenir; Python referansından üretilen vektörler | 10.000 rastgele (işlem, A, B, C, Z) vektörü geçer |
| M5 Bellek | Adres çözme sınırları; /WE yalnızca A fazında | Her bölgenin ilk ve son adresi doğru çipi seçer |
| M6 VGA | Digital VGA monitöründe test deseni; sync sayımları | 400 × 525 nokta/satır, sync genişlikleri doğru |
| M7 PS/2 | Uyaran alt devresiyle byte gönderilir; KRDY, veri, susturma ve temizleme izlenir | `1C`, `F0 1C`, `E0 75` dizileri doğru okunur |
| Bütün CPU | Test programları; emülatör izinden üretilen çevrim çevrim AB/DB/CW vektörleri | Sıfır fark |
| Bütün sistem | CPU + VGA + PS/2: "MERHABA" yazısı, sonra Snake'in birkaç karesi | Ekranda görülür |

### 12.4 Simülasyonda yapılamayanlar → küçük prototipler

Bunlar gerçek parçalarla simülasyon döneminde masada denenir (PROJE-PLANI.md bölüm 15):

| | Prototip | Neyi doğrular |
|---|---|---|
| a | 4 fazlı saat + 161 + 245 | Çınlama, kenarlar |
| b | Flash + DIP switch'li ALU ROM'u | VOH, gecikme |
| c | 25 MHz → LD → 166, gerçek monitörde | Monitör sync'i kabul ediyor mu; 80 ns'lik yol |
| d | PS/2 alıcısı + gerçek klavye | Susturma ve yeniden gönderme davranışı |
| e | SRAM'e A fazında yazma | /WE zamanlaması |

---

## 13. Takvim: simülasyon dönemi (10 hafta, 27 Ekim 2026 – 3 Ocak 2027)

Yapım Ocak'ta başladığı için simülasyonda **yalnızca donanımı doğrulayan işler** var. C derleyicisi ve Snake yapım dönemine kaydı; emülatör sayesinde donanımı beklemeden yazılabiliyorlar (bölüm 14).

| Hafta | Tarih | Kişi 1 (donanım) | Kişi 2 (kontrol ve yazılım) | Kilometre taşı / sipariş |
|---|---|---|---|---|
| 1 | 27 Eki–2 Kas | Java ve Digital'i kur, 74xx kütüphanesini kontrol et, M1 saat modülüne başla | `sim/`'i çalıştır, isa.py'yi öğren, test programları yaz | **Sipariş:** stoğu azalan parçalar (PROJE-PLANI 15) |
| 2 | 3–9 Kas | M1 saat + testleri; M3 adres registerlarına başla | M2 kontrol ünitesi (uROM imajları, latch, kod çözücüler) | **K1: M1 testleri geçiyor** |
| 3 | 10–16 Kas | M3 bitir; M4 ALU + A, F, IR | M5 bellek + adres çözme + WAIT; emülatör izinden Digital test vektörü üreticisi | **Sipariş:** AliExpress flash paketi (MODEL yazısıyla) |
| 4 | 17–23 Kas | Bütün CPU'nun entegrasyonu (ikisi birlikte); prototip a | Bütün CPU'nun entegrasyonu; gelen parçaların giriş testleri | **K2: CPU Digital'de sıfır farkla çalışıyor** |
| 5 | 24–30 Kas | M6 VGA zamanlaması; prototip c (gerçek monitör) | Adımlama, breakpoint, BUSREQ mantığı Digital'de; prototip b (VOH) | |
| 6 | 1–7 Ara | M6 metin hattı + VRAM penceresi | M7 PS/2 Digital'de; prototip d (gerçek klavye) | **Sipariş:** kalan malzemenin hepsi |
| 7 | 8–14 Ara | Tüm sistem Digital'de: CPU + VGA + PS/2 | Gerçek font (`font8x8_basic`); `merhaba.asm` Digital VGA'da | **K3: Digital'de ekranda yazı** |
| 8 | 15–21 Ara | KiCad şemaları: M1, M3, M4, M6 | KiCad şemaları: M2, M5, M7, Arduino kartı; prototip e | |
| 9 | 22–28 Ara | Breadboard yerleşim planı (bölüm 15.2), modül test kontrol listeleri | Arduino iz ve yükleme yazılımının ilk sürümü | Parçaların hepsi geldi ve test edildi |
| 10 | 29 Ara–3 Oca | Tasarımı dondur, danışman incelemesi, tampon | Tasarımı dondur, danışman incelemesi, tampon | **K4: Yapıma hazır** |

**Sipariş zamanlaması:**
- AliExpress paketi 2–5 hafta sürebilir, en geç 3. haftada verilmeli.
- Kalan yerli parçalar 6. haftada sipariş edilir ki Ocak'tan önce gelip test edilsin.

---

## 14. Yapım dönemi (Ocak – Haziran 2027, ~23 hafta)

Başlangıç sınav takvimine göre 4 ya da 18 Ocak. Ocak'taki sınav haftaları hafif tutulur.

| Hafta | Donanım (ikisi birlikte kablolar) | Yazılım (çoğunlukla Kişi 2, evde) |
|---|---|---|
| 1–2 | Güç dağıtımı (önce çipsiz ölçüm), M1 saat ve durdurma. Paralel iş: VGA zamanlaması, monitör kilitlenene kadar. | C derleyici: lexer, parser |
| 3–5 | M2 kontrol latch'i + manuel panel. Paralel iş: VGA metin hattı, test fontuyla. | C derleyici: ifadeler, deyimler, kod üretimi |
| 6–8 | M4 ALU + A + F + IR, DB switch'leriyle. PS/2 tek başına. | C derleyici: fonksiyonlar, statik çerçeve, çağrı grafiği |
| 9–11 | M3: PC, AR, X, SP | Runtime (`__mul16`, `__divmod16`), `crt0`, `hw.h`; C'den "MERHABA" emülatörde |
| 12–13 | M5 bellek + I/O, Arduino kartı | Snake (C), emülatörde oynanıyor |
| 14–15 | Mikrokod takılır; Arduino izi emülatörle karşılaştırılır | Açılış kendi kendini test ROM'u |
| 16–17 | VGA ve PS/2 CPU'ya bağlanır | Snake ince ayarı: hız, skor, yem |
| 18–20 | C programları, Snake, Arduino'suz demo | |
| 21–23 | Tampon, 30 dakikalık dayanıklılık testi, tez yazımı, sunum hazırlığı | |

**Kilometre taşları:**
- 5\. hafta sonu (Şubat): saat + kontrol + VGA test deseni çalışıyor.
- 11\. hafta sonu (Mart): CPU'nun bütün registerları manuel panelle test edildi.
- 15\. hafta sonu (Nisan): CPU kendi başına program çalıştırıyor, iz sıfır farkla eşleşiyor.
- 20\. hafta sonu (Mayıs): Snake demosu çalışıyor.

**Daraltma sırası (zaman yetmezse):** LED portu → breakpoint → 2 MHz denemesi → renk jumper'ı. Snake demosu hiçbir zaman daraltılmaz. C derleyicisi gecikirse Snake önce assembly ile yazılır.

---

## 15. Entegre listesi ve breadboard yerleşimi

### 15.1 Modüllere göre entegreler (toplam 92)

| Modül | Entegreler |
|---|---|
| M1 Saat (14) | NE555, 74HC153, 74HC14, 74HC74 ×3, 74HC175 ×2, 74HC00, 74HC08, 74HC32, 74HC02, 74HC138 (WAIT), 74HC245 (saat tamponu) + 4 MHz osilatör |
| M2 Kontrol (13) | SST39SF010 ×3, 74HC273 ×3, 74HC138 ×2, 74HC139, 74HC161, 74HC04, 74HC688 ×2 |
| M3 Adres (22) | 74HC161 ×12, 74HC191 ×2, 74HC245 ×8 |
| M4 Veri/ALU (8) | 74HC161 (F), 74HC377 ×2 (A, IR), 74HC245 ×3, SST39SF010 ×2 (ALU) |
| Yardımcı (4) | 74HC00 ×2, 74HC08, 74HC32 |
| M5 Bellek (6) | SST39SF010 (ROM), CY62256 (RAM), 74HC20, 74HC138, 74HC377 (LED), 74HC245 (KSTAT) |
| M6 VGA (19) | 74HC74, 74HC163 ×6, SST39SF010 ×2 (zamanlama, font), 74HC377 (T1), 74HC157 ×3, CY62256 (VRAM), 74HC245, 74HC166, 74HC08, 74HC20, 74HC04 + 25 MHz osilatör |
| M7 PS/2 (6) | 74HC164 ×2, 74HC540, 74HC14, 74HC74, 74HC08 + 2N7000, 1N4148 ×3 |

**Parça numarasına göre:**

| Parça | Adet |
|---|---|
| 74HC161 | 14 |
| 74HC245 | 14 |
| SST39SF010 | 8 |
| 74HC163 | 6 |
| 74HC74 | 5 |
| 74HC377 | 4 |
| 74HC138 | 4 |
| 74HC08 | 4 |
| 74HC157, 74HC273, 74HC00 | 3'er |
| CY62256, 74HC14, 74HC20, 74HC688, 74HC191, 74HC164, 74HC175, 74HC04, 74HC32 | 2'şer |
| 74HC139, 74HC166, 74HC540, 74HC153, 74HC02, NE555 | 1'er |

Satın alma listesi ve fiyatlar: PROJE-PLANI.md bölüm 14.

### 15.2 Breadboard yerleşimi (24 kart, MB-102)

```
 Sıra 1:  [K1 Saat] [K2 Saat] [K3 Yardımcı] [K4 uROM0/1] [K5 uROM2+latch] [K6 Panel] [K7 Çözücüler+BP]
 Sıra 2:  [K8 PC]   [K9 PC]   [K10 AR]      [K11 AR/X]   [K12 X]          [K13 SP]
 Sıra 3:  [K14 ALU] [K15 A/F/IR] [K16 ROM+çözme] [K17 RAM+I/O] [K18 PS/2] [K24 Güç/bus LED]
 Ayrı panel: [K19–K23 VGA]  ←  şerit kabloyla AB[10:0], DB, /WR, /VRAMSEL, VWR, SLOW
```

- **Bus'lar:**
  - AB, sıra 2 boyunca yatay bir şerit üzerinden ilerler.
  - DB, sıra 3 boyunca ilerler.
  - Kontrol kelimesi, sıra 1'den aşağı doğru dağıtılır.
- **Kablo renkleri:** Kırmızı 5 V, siyah GND, mavi adres, yeşil veri, beyaz kontrol, sarı **yalnızca saat**.
- **Güç:** Her rayı iki ucundan besleyin; en uzak çipte ≥ 4.75 V ölçün.

---

## 16. Kabul ölçütleri

1. Snake, PS/2 klavyeyle oynanıyor. Arduino takılı değil, program ROM'dan, C'den derlenmiş.
2. Açılış ROM'u kendi kendini test ediyor: RAM, VRAM yazma, ALU işlemleri. Sonuç LED'lerde ve ekranda görünüyor.
3. Arduino izi ile emülatör izi en az 1.000.000 çevrim boyunca sıfır farkla eşleşiyor.
4. 1 MHz'de 30 dakika kesintisiz çalışıyor.
5. Her modülün test kaydı lab defterinde ve tezin "test ve doğrulama" bölümünde yer alıyor.

---

## 17. Çalışma düzeni

- **Git:** Her çalışan durum commit edilir. ROM imajları sürümlenir: `git tag urom-v0.3`.
- **Değişiklik sırası:** önce `isa.py` → sonra testler → sonra bu dosya → en son Digital ve donanım.
- **Lab defteri:** Her arızanın belirtisi, sebebi ve çözümü yazılır (PROJE-PLANI.md bölüm 9.4).
- **Haftalık toplantı:** 30 dakika. Kilometre taşlarına göre durum, bir sonraki haftanın işi.

---

## 18. Açık noktalar

| Konu | Ne zaman |
|---|---|
| Digital'in 74xx kütüphanesinde 191, 166, 540 ve 688 var mı | 1. hafta |
| T48 cihaz listesinde A'sız SST39SF010 (-90) var mı | Parçalar gelince |
| Gerçek 8×8 font: font8x8_basic (kamu malı); `sim/td8/vga.py` dönüştürücüsüyle | 7. hafta |
| VOH, PS/2 susturma, 80 ns'lik LD yolu | Prototip b, c, d |
| Simülasyon ve prototiplerde açık kalan diğer maddeler | [DOGRULAMA.md](tasarim-taslaklari/DOGRULAMA.md) bölüm 3 |
