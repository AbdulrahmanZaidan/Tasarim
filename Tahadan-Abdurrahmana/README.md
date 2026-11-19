# Taha'dan Abdurrahman'a: Tasarım Notları ve Yapılacaklar Listesi

Selam Abdurrahman, tasarımda gözden kaçmış veya unutulmuş olabilecek teknik detayları, 2. haftadaki şemalarda düzeltmemiz gereken yerleri ve 3. haftada yapılacakları senin için tek bir yerde topladım. Devreleri çizerken doğrudan buradaki pin ve çip listesini referans alabilirsin. **En yeni mesaj en üstte.**

---

## YENİ (19 Kasım): Projenin adı TA-8 oldu, dosya adları değişti

18 Kasım'daki çalışmaların için eline sağlık. Bütün testlerin bende de geçti (M1 4, registerlar 4, ALU 3, M3 4, M6 2).

Projenin adı **TA-8**: **T**aha ve **A**bdurrahman'ın baş harfleri, 8 bit. Ad kod dahil her yerde değişti. `git pull` yapmadan önce kendi değişikliklerini commit et.

| Eski | Yeni |
|---|---|
| `sim/td8/` (Python paketi), `from td8 ...` | `sim/ta8/`, `from ta8 ...` |
| `sim/tdcc/` (C derleyicisi), `py -m tdcc` | `sim/tacc/`, `py -m tacc` |
| `sim/digital/td8.dig`, `TD8_SST39SF010_*.dig`, `TD8_CY62256.dig` | `ta8.dig`, `TA8_SST39SF010_*.dig`, `TA8_CY62256.dig` |
| `Tahadan-Abdurrahmana/TD8-baglanti-tablosu.md` | `TA8-baglanti-tablosu.md` |
| `arduino/td8_debug/` | `arduino/ta8_debug/` |
| `TD8_DIGITAL_HOME` ortam değişkeni | `TA8_DIGITAL_HOME` |
| Ekrandaki yazılar ("MERHABA, TD-8!", Snake başlığı, açılış testi) | "MERHABA, TA-8!" … (uzunluklar aynı, çevrim sayıları değişmedi) |

**Senin klasöründe ben değiştirdim:** dosya adları (`TA8_*.dig`, `ta8_islemci_*`), notlardaki ve `.dig`/`.svg` dosyalarındaki adlar, `m6_uret.py`'deki `from ta8 ...` satırları, `merhaba_ekran.png` (artık "MERHABA, TA-8!"). Dosyaların Digital'de açılıp testlerinin geçtiğini denedim. Diğer ekran görüntülerinde (`*_digital_ekran.png`) eski etiketler görünebilir. İstersen kendi aracınla yeniden üret.

**4. hafta raporu:** genel bakışa sade bir "bu hafta, kısaca" ve gelecek hafta planı, bir de Sözlük sekmesi eklendi. Deniz sekmesindeki "gelecek hafta: birleştirme" çelişkisi düzeltildi. Senin sekmene dokunmadım.

---

## 17 Kasım: 3. Hafta Notun ve Bu Haftanın (17–23 Kasım) İşleri

13 Kasım'daki notunu (`Abdurrahman/hafta3/`) okudum, eline sağlık. 4. hafta raporu yayında: <https://abdulrahmanzaidan.github.io/Tasarim/raporlar/hafta4.html>. Senin sekmende notunu özetledim. Aşağıda notla ilgili üç konu ve bu hafta senden beklenenler var.

### 1. Notundaki şemalar TA-8 değil, SAP-1

Notundaki ALU, RAM ve MAR, Ben Eater'ın SAP-1 bilgisayarının devreleri. Bizim TA-8'de bu üç parça başka türlü yapılıyor:

| Notunda | TA-8'de | Kimde / nerede |
|---|---|---|
| ALU: 2× 74LS283 + 2× 74LS86; yalnız toplama ve çıkarma | ALU **2 flash'ta tablo** (Proteus'ta 2× 27C512, `alu_lo.bin`, `alu_hi.bin`). 25 işlem: toplama, çıkarma, AND/OR/XOR, kaydırmalar… Toplayıcı entegresi yok | Sende (M4). Bağlantısı aşağıda bölüm 3.B; [SISTEM-PLANI 5.2–5.3](../SISTEM-PLANI.md#52-alu-2-flashta-tablo) |
| Bayraklar: CF ve ZF, 74LS173 | Dört bayrak: **Z, C, N, V**. Register **74HC161** (4-bit register olarak, `/PE = NOT FL`). `C = Clo OR Chi` (1× 74HC32) | Sende (M4). Bölüm 1.E |
| RAM: 2× 74189, **16 bayt**, 4-bit adres | RAM **CY62256, 32 KB** (28 KB'ı kullanılıyor: `8000–EFFF`), **16-bit adres** | **Bende (M5).** Digital'de test edildi (`sim/digital/m5_bellek.dig`). Senin çizmen gerekmiyor |
| MAR: 4-bit 74LS173 | **Ayrı bir MAR yok.** Adres yolunu dört register sürüyor: PC, AR, X, SP (74HC161/191 + 74HC245). AR, MAR'ın işini görüyor ama 16 bit ve sayabiliyor | Sende (M3). Bölüm 3.A |
| Elle programlama: PROG anahtarı, DIP ile veri, SW4 ile yazma | Yok. Program flash'a T48 programlayıcıyla yazılıyor ya da Arduino ile RAM'e yükleniyor | Sonraki iş (M8) |
| 74LS ailesi | **74HC** ailesi | Hepsi |

Yani bu üç şemayı TA-8'e uyarlamak yerine **RAM ve MAR'ı bırak**, M4 (A, IR, F, ALU flash'ları) ve M3 (PC, AR, X, SP) şemalarını çiz.

### 2. Şemaların kaynağı ve notun başlığı

- Şemalar, Ben Eater'ın sitesinde yayımladığı SAP-1 şemalarıyla aynı görünüyor: KiCad çizimi, entegre ve LED numaraları da aynı (U16–U34, D74–D81 gibi). Hocanın göreceği sayfada başkasının şeması bizim çizimimiz gibi durmasın diye **görselleri rapora koymadım**, yalnızca notunu özetledim. Kendi çizdiğin Proteus şemalarını koyarsan raporda onları gösteririz. Bir yerden şema ya da fikir alırsak kaynağını yazalım: "Ben Eater'ın şeması, şu adresten" gibi.
- Notunda "simülasyon dosyası, zaman diyagramı veya ölçüm kaydı yok; tablolar beklenen sonuç" yazıyor. Raporda bir modülü "bitti" saymamız için **Proteus'ta çalışırken alınmış ekran görüntüsü** ve **ölçülen sonuç** gerekiyor (aşağıda bölüm 3).
- Notunun başında "Hazırlayanlar: Abdel Rahman Zidan ve Taha Deniz Akgül" yazıyor. Bu not senin; yalnız kendi adını yazman yeterli.

### 3. Bu hafta senden beklenenler (öncelik sırasıyla)

Takvime göre ([SISTEM-PLANI bölüm 13](../SISTEM-PLANI.md#13-takvim-simülasyon-dönemi-10-hafta-27-ekim-2026--3-ocak-2027)) bu hafta bütün işlemcinin birleştirilmesi ve prototip a var, ama M1, M3 ve M4 henüz bitmedi. Önce onları bitirelim:

| # | İş | Teslim | Nasıl test edilir |
|---|---|---|---|
| 1 | **M1 saat modülü testleri** (ilk kilometre taşı K1, 9 Kasım'dan beri gecikmede) | `.pdsprj` + 4 testin dalga şekli ekran görüntüsü | Aşağıdaki bölüm 2'deki 4 test: normal çalışma, STOP, WAIT, GO ve /RESET_s. WAIT 138'inin G1 bacağı artık **CLK**'ye bağlı (bölüm 0'daki düzeltme) |
| 2 | **M4: A, IR, F ve ALU** (74HC377, 74HC377, 74HC161, 2× 27C512) | `.pdsprj` + ekran görüntüleri | `cd sim` → `py cli.py vectors alu -n 10 --format csv`. 10 satırın her birinde girişleri (OP, A, B, C, Z) ver, çıkışların (R, Z, C, N, V) tabloyla aynı olduğunu göster |
| 3 | **ROM dosyası denemesi** | [Abdurrahmandan-Tahaya](../Abdurrahmandan-Tahaya/README.md)'ya tek satır | 27C512'ye `build/proteus/alu_lo.bin` yükle; `.bin` mi `.hex` mi çalıştı, yaz |
| 4 | **M3: PC, AR, X, SP** | `.pdsprj` + ekran görüntüleri | PC sayıyor ve AR'dan yükleniyor; AR ve X veri yolundan iki parça halinde yükleniyor; SP reset'te FF, push'ta azalıp pop'ta artıyor; aynı anda tek bir register adres yolunu sürüyor |

**Hazır yardımlar:**
- **Digital'de M1, M3 ve M4 devreleri hazır:** `sim/digital/m1_saat.dig`, `m3_adres.dig`, `m4_alu.dig`. Her entegre Digital'in 74xx kütüphanesindeki bacaklı çip, her bacakta sinyal adı var. Proteus'ta aynı bağlantıları kurman için örnek olarak açabilirsin (Digital ücretsiz, kurulum `sim/README.md`'de).
- **Her bacağın bağlantısı:** [TA8-baglanti-tablosu.md](TA8-baglanti-tablosu.md), bölüm M1, M3, M4.
- Takıldığın yeri [Abdurrahmandan-Tahaya](../Abdurrahmandan-Tahaya/README.md)'ya yaz, aynı gün bakarım.

**Teslim yeri ve tarihi:** `Abdurrahman/hafta4/README.md` + `.pdsprj` dosyaları + ekran görüntüleri, **23 Kasım Pazar akşamına kadar**. 5. hafta raporu bunlarla hazırlanacak. README'de her test için bir tablo olsun: *ne verildi, ne bekleniyordu, ne görüldü (ekran görüntüsü)*.

---

## 0. 12 Kasım: Sorularının Cevabı ve Senin İçin Hazırlananlar

### Soru 1: Proteus'ta ROM'lara `.bin` mi `.hex` mi yükleyeceğiz?

**`.bin` kullan.** Ama `sim/build/` altındaki eski dosyaları değil, yeni `sim/build/proteus/` klasöründekileri:

- `sim/build/*.hex` dosyaları Digital programının biçiminde (Intel HEX değil). **Proteus bunları okuyamaz.**
- `cd sim` → `py cli.py roms` komutu artık `sim/build/proteus/` klasörünü de üretiyor: her ROM için 64 KB'lık `.bin` ve Intel HEX biçiminde `.hex`. (`build/` klasörü GitHub'a girmiyor; komutu kendi bilgisayarında çalıştırman gerek. Python 3.12 yeterli, ek paket yok.)
- Proteus kütüphanesinde SST39SF010 (128 KB flash) büyük olasılıkla yok. Yerine **27C512** (64 KB EPROM) koy: A0–A15 bacakları aynı işi görüyor. Bizim devrede flash'ların A16 bacağı zaten 0'a bağlı olduğu için 64 KB yetiyor.

| Proteus'taki ROM | Yüklenecek dosya |
|---|---|
| Mikrokod ROM'ları (3 adet) | `build/proteus/urom0.bin`, `urom1.bin`, `urom2.bin` |
| ALU ROM'ları (2 adet) | `build/proteus/alu_lo.bin`, `alu_hi.bin` |
| Program ROM'u | `py cli.py asm examples/merhaba.asm --ihex` → `examples/merhaba.bin` (32 KB) ve `merhaba.hex` (Intel HEX) |

Proteus tarafını ben deneyemedim (bende kurulu değil); bilgi forumlardan. 27C512'nin özellikler penceresindeki imaj dosyası alanına `.bin`'i verip dene, olmazsa aynı adlı `.hex`'i dene ve hangisinin çalıştığını `Abdurrahmandan-Tahaya` dosyasına yaz.

### Soru 2: Sinyal adları şemadaki etiketlerle aynı olsun

Bunun için **[TA8-baglanti-tablosu.md](TA8-baglanti-tablosu.md)** hazır: işlemcinin 59 entegresinin **her bacağının** hangi sinyale bağlandığı, modül modül (M1, M2, M3, M4, yardımcı kapılar, M5). Proteus'ta net etiketlerini bu tablodaki adlarla aynı verirsen modüller birleşirken ad uyuşmazlığı olmaz.

- Tablo elle yazılmadı, `sim/ta8/hw/cpu.py` dosyasındaki bağlantı listesinden üretildi. Bu bağlantı listesi simülasyonda emülatörle **çevrim çevrim sıfır farkla** çalışıyor (6 program, 88 komutun hepsi). Yani tablodaki gibi bağlanan devre çalışır.
- İki ad sözlükte yoktu, ben verdim: A registerının çıkışları `ACC0..ACC7`, AR registerının çıkışları `AR0..AR15`.
- Tablo yalnız kablo bağlantısını söyler. Şemayı çizmek, Proteus'ta çalıştırmak ve test etmek yine sende.

### M1'de bir değişiklik: WAIT 138'inin G1 bacağı CLK'ye

Simülasyon planda bir zamanlama hatası buldu: VRAM'e yazarken bekleme (WAIT) kararı en kötü gecikmelerle 250 ns'ye yetişmiyordu (flip-flop'un kurulum süresiyle ~272 ns). Düzeltme tek kablo:

- **Eski:** WAIT 74HC138'inde G1 = VCC; Johnson `Q2' = NAND(/Q1, OR(/WAIT, /Q2))`.
- **Yeni:** G1 = **CLK**; Johnson `Q2' = NAND(/Q1, /WAIT)`. Aradaki OR kapısı kalktı.

Bağlantı tablosu ve [SISTEM-PLANI.md bölüm 3.6](../SISTEM-PLANI.md) yeni haliyle. Düzeltilmiş halde süre 247 ns, pay yalnız ~3 ns; saat modülünün prototipinde (prototip a) osiloskopla bakmamız gerekecek.

### Test etmek için

- **Modül testleri için hazır tablolar:** `py cli.py vectors alu`, `urom`, `cs` (kod çözücüler), `decode` (adres çözme). `--format csv` eklersen Excel'de açılır. Her satır "bu girişleri ver, şu çıkışları görmelisin" diyor.
- **Bütün işlemci için:** `py cli.py vectors trace examples/merhaba.asm --format csv` her çevrimde adres yolunda, veri yolunda ve 24 kontrol hattında ne olması gerektiğini veriyor (573 satır). Proteus'ta aynı programı çalıştırıp karşılaştırabiliriz.
- **Digital kullanmak istersen:** ücretsiz, Java ile çalışıyor. Bende kurulu; kurulum notu `sim/README.md`'de.

---

## 1. ÖNEMLİ: 2. Hafta Register Şemalarında Düzeltilecek Noktalar (SAP-1 → TA-8 Farkı)

2. haftada çizdiğin **A Register**, **B Register** ve **Instruction Register (IR)** şemaları klasik **Ben Eater (SAP-1)** yapısına göre (`74LS173` + `B registerı`) olmuş. Bizim **TA-8 Sistem Planımızda ([SISTEM-PLANI.md bölüm 5.1](../SISTEM-PLANI.md#51-registerlar-hepsi-clk--ile-yüklenir-senkron-izinli))** tasarımımız şu şekilde:

### A) TA-8'de **B Registerı YOK**
- **Neden:** ALU'muzun sol girişi doğrudan `A` registerından (`A[7:0]`), sağ girişi ise doğrudan **ortak veri yolundan (`DB[7:0]`)** geliyor.
- **Ne yapılacak:** B Register şemasını tamamen kaldırabiliriz; projede B registerı kullanılmayacak.

### B) `74LS173` yerine **`74HC377`** (ve `74HC` ailesi)
- İki adet 4-bitlik `74LS173` yerine tek pakette 8-bit tutan **`74HC377`** kullanıyoruz (`A` ve `IR` registerları için).
- Bütün entegrelerimiz `74LS` değil **`74HC`** serisi olacak (`74HC245`, `74HC377`, `74HC161` vb.).

### C) **A Registerı** Bağlantıları (Veri Yolundan Değil, ALU Çıkışından Yüklenir!)
SAP-1'de A registerı girişini veri yolundan (`BUS`) alır ama **TA-8'de A registerı girişini yalnızca ALU'nun 8-bitlik sonuç çıkışından (`R[7:0]`) alır**:
- **Çip:** 1× `74HC377` + 1× `74HC245` + 8 LED (`220 Ω` dirençlerle) + `100 nF` kondansatör.
- **Giriş (`D0–D7`):** `R_0–R_7` (ALU'nun sonuç çıkışı; `DB` veri yolu **değil**!).
- **Saat (`CP`):** `CLK` (M1 saat modülünden gelen ana commit saati, `B→C` yükselen kenarı).
- **Yükleme İzni (`/E`):** `/DD_A` (Kontrol ünitesindeki `#DD` `74HC138` kod çözücüsünün `Y2` çıkışı, aktif-düşük).
- **Çıkış (`Q0–Q7` → `A_0–A_7`):**
  1. Doğrudan ALU'nun sol girişine (`A[7:0]`) gider.
  2. 8 adet LED'e gider.
  3. `74HC245` üzerinden ortak veri yoluna (`DB_0–DB_7`) bağlanır. `74HC245`'in `/OE` bacağına kontrol ünitesinin `#DS` (`74HC138`) kod çözücüsünden gelen **`/OE_A`** (`Y2`) sinyali bağlanır.

### D) **Instruction Register (IR)** Bağlantıları (Veri Yoluna Geri Çıkmaz, 8 Bitin Hepsi Kullanılır!)
SAP-1'de IR'nin sadece 4 biti kontrol ünitesine gider ve yanında `74LS245` vardır. **TA-8'de ise opcode 8 bittir ve IR veri yoluna geri çıkmaz**:
- **Çip:** 1× `74HC377` + 8 LED (`220 Ω` dirençlerle) + `100 nF` kondansatör. (**`74HC245` YOK!**)
- **Giriş (`D0–D7`):** `DB_0–DB_7` (Ortak 8-bit veri yolu).
- **Saat (`CP`):** `CLK`.
- **Yükleme İzni (`/E`):** `/DD_IR` (`#DD` `74HC138` kod çözücüsünün `Y1` çıkışı, aktif-düşük).
- **Çıkış (`Q0–Q7` → `IR_0–IR_7`):** 8 bitin **tamamı** (`IR_0..IR_7`) doğrudan 3 adet mikrokod ROM'unun (`uROM0, uROM1, uROM2`) **`A4–A11`** adres pinlerine ve 8 adet LED'e gider.

### E) **Flags (Bayrak) Registerı (`F` — `Z, C, N, V`)**
M4 modülündeki üçüncü register 4-bitlik bayrak registerıdır:
- **Çip:** 1× `74HC161` (sayıcı özelliği kapalı: `CEP = 0`, `CET = 0`, yalnızca 4-bitlik paralel yüklemeli ve reset'li register olarak kullanılır).
- **Giriş (`P0–P3`):** ALU'dan gelen `Z, C, N, V` bayrak sinyalleri.
- **Saat (`CP`):** `CLK`.
- **Yükleme İzni (`/PE`):** `/FL` (`FL` kontrol bitinin `74HC04` ile terslenmiş hali, aktif-düşük).
- **Reset (`/MR`):** `/RESET_s` (Reset basıldığında tüm bayraklar `0000` olur).
- **Çıkış (`Q0–Q3`):** `Z, C, N, V` → Mikrokod ROM'larının `A12–A15` pinlerine, ALU'ya (`C` ve `Z` geri beslemesi) ve 4 adet LED'e gider.

---

## 2. 1. Haftadan Kalan Saat Modülü (M1) Testleri (Kilometre Taşı K1)

Saat modülünde (`M1`) 4 fazın (`C → D → A → B`) üretimini kurmuştun. İlk kilometre taşını (**K1**) tamamlandı olarak işaretleyebilmemiz için [SISTEM-PLANI.md bölüm 3](../SISTEM-PLANI.md#3-saat-reset-durdurma-m1) ve `Abdurrahman/hafta1/README.md`'deki şu 4 durumu Proteus'ta test edip ekran görüntüsü almamız gerekiyor:

1. **Normal çalışma:**
   - `CLK = Q2` (`C` ve `D` fazlarında yüksek, `B→C` kenarında yükseliyor).
   - `LCLK = /Q1` (`D` ve `A` fazlarında yüksek, `C→D` kenarında yükseliyor).
   - `WSTB = NOR(Q1, Q2)` (Yalnızca `A` fazında yüksek — 250 ns yazma darbesi).
2. **`STOP = 1` testi:** `STOP` sinyali `1` yapıldığında sayacın **`C` fazında (`Q1=1, Q2=1`)** durup beklemesi (`Q1' = !Q2 | (STOP & Q1)`).
3. **`WAIT = 1` testi:** `WAIT` sinyali `1` yapıldığında sayacın **`D` fazında (`Q1=0, Q2=1`)** beklemesi (`Q2' = Q1 | (WAIT & Q2)`).
4. **`GO` ve `/RESET_s` testi:** Duran makinede `GO` darbesi gelince tam **1 çevrim (`C→D→A→B→C`)** çalışıp tekrar durması; `/RESET_s` gelince doğrudan `C` fazına park etmesi.

---

## 3. Bu Haftanın (3. Hafta: 10–16 Kasım) Donanım İşleri

[SISTEM-PLANI.md bölüm 13](../SISTEM-PLANI.md#13-takvim-simülasyon-dönemi-10-hafta-27-ekim-2026--3-ocak-2027) takvimine göre bu haftaki modüllerimiz **M3 (Adres Registerları)** ve **M4 (ALU)**:

### A) M3 Adres Registerları (`PC`, `AR`, `X`, `SP`) — [SISTEM-PLANI.md bölüm 5.1](../SISTEM-PLANI.md#51-registerlar-hepsi-clk--ile-yüklenir-senkron-izinli)

| Register | Genişlik | Kullanılacak Çipler | Nasıl Bağlanacak? |
|---|---|---|---|
| **PC** (Program Counter) | 16-bit | 4× `74HC161` + 4× `74HC245` + 16 LED | `CP = CLK`, `/MR = /RESET_s`. Sayma: `CEP = PCINC` (`161`'lerin `TC` çıkışları bir üst çipin `CET`'sine zincirlenir). Paralel yükleme: `/PE = /PCLD`, girişleri (`P`) doğrudan **`AR` registerının 16-bit çıkışına (`PCIN`)** bağlıdır! Çıkışı: 2× `74HC245` ile `AB[15:0]` adres yoluna; ayrıca 2× `74HC245` (`PCL` ve `PCH`, `/OE_PCL` ve `/OE_PCH`) ile `DB[7:0]` veri yoluna gider. |
| **AR** (Address Register) | 16-bit | 4× `74HC161` + 2× `74HC245` + 16 LED | `CP = CLK`, `/MR = /RESET_s`. Girişleri `DB[7:0]` veri yoluna bağlı. Alt 8 bitin (2× `161`) yükleme izni `/PE = /DD_ARL`, üst 8 bitin (2× `161`) yükleme izni `/PE = /DD_ARH`. Sayma: `CEP = ARINC`. Çıkışı: hem `PC`'nin girişine (`PCIN`) hem de 2× `74HC245` ile `AB[15:0]`'a gider. |
| **X** (Pointer Register) | 16-bit | 4× `74HC161` + 2× `74HC245` + 16 LED | `AR` ile aynı yapıda: girişi `DB[7:0]`, alt 8 bit `/PE = /DD_XL`, üst 8 bit `/PE = /DD_XH`, sayma `CEP = XINC`. Çıkışı 2× `74HC245` ile yalnızca `AB[15:0]`'a gider. |
| **SP** (Stack Pointer) | 8-bit (`$EF` sayfasında) | 2× `74HC191` + 2× `74HC245` + 8 LED | Yukarı/aşağı sayıcı. `D` girişlerinin hepsi `1` (`VCC`), `/PL = /RESET_s` (reset'te `$FF` yüklenir). Sayma izni: alt çip `/CE = NOT SPCNT`, üst çip `/CE = NAND(SPCNT, MAX/MIN_alt)`. Yön: `D/U = SPDN` (`1`=aşağı/push, `0`=yukarı/pop). Çıkışı: 1× `74HC245` ile `AB[7:0]`'a; üst 8 bit (`AB[15:8]`) için 1× `74HC245`'in girişleri sabit **`$EF` (`11101111`)** olarak bağlanır. |

**Adres Yolu Seçicisi (`#AS`):**
- `PC`, `AR`, `X` ve `EF:SP`'nin `AB` sürücülerinin (`74HC245`) `/OE` bacakları bir adet **`74HC139`** kod çözücüsünün `Y0, Y1, Y2, Y3` çıkışlarına bağlanır (`A0, A1 = ASRC[1:0]`, `/G = BUSACK`). Böylece iki register aynı anda adres yoluna çıkamaz.

### B) M4 ALU (2× `SST39SF010` Flash Tablosu) — [SISTEM-PLANI.md bölüm 5.2](../SISTEM-PLANI.md#52-alu-2-flashta-tablo)
- `sim/` klasöründe `py gen_roms.py` çalıştırıldığında `sim/build/alu_lo.bin` (ve `.hex`) ile `sim/build/alu_hi.bin` (ve `.hex`) üretiliyor.
- Proteus'ta iki adet `SST39SF010` (128K×8 ROM) koyup bu imajları yükleyeceğiz:
  - **`ALU-L` Adres Pinleri:** `A0..3 = A[3:0]`, `A4..7 = DB[3:0]`, `A8 = C`, `A9 = A[4]`, `A10..14 = ALUOP[4:0]`, `A15 = A[7]`, `A16 = 0`.
  - **`ALU-L` Veri Çıkışları:** `D0..3 = R[3:0]`, `D4 = c4`, `D5 = Zlo`, `D6 = Clo`.
  - **`ALU-H` Adres Pinleri:** `A0..3 = A[7:4]`, `A4..7 = DB[7:4]`, `A8 = c4`, `A9 = Zlo`, `A10 = Z`, `A11..15 = ALUOP[4:0]`, `A16 = 0`.
  - **`ALU-H` Veri Çıkışları:** `D0..3 = R[7:4]`, `D4 = Z_yeni`, `D5 = Chi`, `D6 = N_yeni`, `D7 = V_yeni`.
  - **Carry Birleştirme:** `C_yeni = Clo OR Chi` (1× `74HC32` kapısı).

---

## 4. Klasörlere Eklenecek Dosyalar Hatırlatması

Danışman hocaya gösterirken eksik kalmaması için:
- [ ] `Abdurrahman/hafta1/` içine M1 saat modülünün `.pdsprj` dosyası ve dalga şekli ekran görüntüsü.
- [ ] `Abdurrahman/hafta2/` içine register şemalarının `.pdsprj` dosyası ve TA-8'e uyarlanmış (`74HC377` A, IR, `74HC161` F) yükleme testi ekran görüntüsü.
- [ ] Takıldığın veya benden (yazılım/ROM imajı/test vektörü tarafında) istediğin bir şey olursa [`../Abdurrahmandan-Tahaya/README.md`](../Abdurrahmandan-Tahaya/README.md) dosyasına yazabilirsin!
