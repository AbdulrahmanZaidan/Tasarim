# Taha'dan Abdurrahman'a: Tasarım Notları ve Yapılacaklar Listesi

Selam Abdurrahman, tasarımda gözden kaçmış veya unutulmuş olabilecek teknik detayları, 2. haftadaki şemalarda düzeltmemiz gereken yerleri ve 3. haftada yapılacakları senin için tek bir yerde topladım. Devreleri çizerken doğrudan buradaki pin ve çip listesini referans alabilirsin.

---

## 1. ÖNEMLİ: 2. Hafta Register Şemalarında Düzeltilecek Noktalar (SAP-1 → TD-8 Farkı)

2. haftada çizdiğin **A Register**, **B Register** ve **Instruction Register (IR)** şemaları klasik **Ben Eater (SAP-1)** yapısına göre (`74LS173` + `B registerı`) olmuş. Bizim **TD-8 Sistem Planımızda ([SISTEM-PLANI.md bölüm 5.1](../SISTEM-PLANI.md#51-registerlar-hepsi-clk--ile-yüklenir-senkron-izinli))** tasarımımız şu şekilde:

### A) TD-8'de **B Registerı YOK**
- **Neden:** ALU'muzun sol girişi doğrudan `A` registerından (`A[7:0]`), sağ girişi ise doğrudan **ortak veri yolundan (`DB[7:0]`)** geliyor.
- **Ne yapılacak:** B Register şemasını tamamen kaldırabiliriz; projede B registerı kullanılmayacak.

### B) `74LS173` yerine **`74HC377`** (ve `74HC` ailesi)
- İki adet 4-bitlik `74LS173` yerine tek pakette 8-bit tutan **`74HC377`** kullanıyoruz (`A` ve `IR` registerları için).
- Bütün entegrelerimiz `74LS` değil **`74HC`** serisi olacak (`74HC245`, `74HC377`, `74HC161` vb.).

### C) **A Registerı** Bağlantıları (Veri Yolundan Değil, ALU Çıkışından Yüklenir!)
SAP-1'de A registerı girişini veri yolundan (`BUS`) alır ama **TD-8'de A registerı girişini yalnızca ALU'nun 8-bitlik sonuç çıkışından (`R[7:0]`) alır**:
- **Çip:** 1× `74HC377` + 1× `74HC245` + 8 LED (`220 Ω` dirençlerle) + `100 nF` kondansatör.
- **Giriş (`D0–D7`):** `R_0–R_7` (ALU'nun sonuç çıkışı; `DB` veri yolu **değil**!).
- **Saat (`CP`):** `CLK` (M1 saat modülünden gelen ana commit saati, `B→C` yükselen kenarı).
- **Yükleme İzni (`/E`):** `/DD_A` (Kontrol ünitesindeki `#DD` `74HC138` kod çözücüsünün `Y2` çıkışı, aktif-düşük).
- **Çıkış (`Q0–Q7` → `A_0–A_7`):**
  1. Doğrudan ALU'nun sol girişine (`A[7:0]`) gider.
  2. 8 adet LED'e gider.
  3. `74HC245` üzerinden ortak veri yoluna (`DB_0–DB_7`) bağlanır. `74HC245`'in `/OE` bacağına kontrol ünitesinin `#DS` (`74HC138`) kod çözücüsünden gelen **`/OE_A`** (`Y2`) sinyali bağlanır.

### D) **Instruction Register (IR)** Bağlantıları (Veri Yoluna Geri Çıkmaz, 8 Bitin Hepsi Kullanılır!)
SAP-1'de IR'nin sadece 4 biti kontrol ünitesine gider ve yanında `74LS245` vardır. **TD-8'de ise opcode 8 bittir ve IR veri yoluna geri çıkmaz**:
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
- [ ] `Abdurrahman/hafta2/` içine register şemalarının `.pdsprj` dosyası ve TD-8'e uyarlanmış (`74HC377` A, IR, `74HC161` F) yükleme testi ekran görüntüsü.
- [ ] Takıldığın veya benden (yazılım/ROM imajı/test vektörü tarafında) istediğin bir şey olursa [`../Abdurrahmandan-Tahaya/README.md`](../Abdurrahmandan-Tahaya/README.md) dosyasına yazabilirsin!
