# TA-8 CPU kablolama tablosu

Kaynak: `sim/ta8/hw/cpu.py` (üretilmiştir, elle düzenlemeyin). Bacak numaraları DIP kılıf, pin adları datasheet adları (`sim/ta8/hw/chips.py`). "— (boş)" bağlanmayan çıkış.

## Plan düzeltmeleri

- PLAN DÜZELTMESİ: WAIT yolu (SISTEM-PLANI 3.6, ISA-v0-sentez 5.4 yol 3): plan Q2' = NAND(/Q1, OR(/WAIT, /Q2)) ve 138 G1 = VCC diyor; elle hesap ~236 ns < 250 ns. Hesap, LCLK'in MCLK kenarından Johnson 74HC74'ün kendi CP→Q gecikmesi kadar (en kötü ~44 ns) sonra yükseldiğini ve 74HC74 kurulum süresini (~15 ns) atlıyor: D→A kararı LCLK'e değil MCLK'ye göre örneklenir. Simülasyonda max köşede, 1 MHz'de /WAIT kararı C→D MCLK kenarından ~257 ns sonra geliyor; VRAM'e pencere kapalıyken yapılan her yazma beklemeden A fazına geçiyor (merhaba.asm: 14 yazmanın 12'si, bekleme 0). Düzeltme: WAIT 138'inin G1 ucu VCC yerine CLK (= Q2); bu, OR(/WAIT, /Q2)'yi 138'in içinde yapar. Johnson Q2' = NAND(/Q1, /WAIT) olur, bir kapı seviyesi (OR, en kötü 25 ns) kalkar ve U104'ün 1. OR kapısı boşa çıkar. Mantık birebir aynı (/WAIT' = /WAIT | /Q2). Max köşede karar ~232 ns + kurulum 15 = 247 < 250 ns (pay ~3 ns: sınırda; osiloskopla doğrulanmalı).

## Entegre sayımı

| Modül | Plan (15.1) | Netlist | Kurulmayan | Açıklanmamış fark |
|---|---:|---:|---:|---:|
| M1 Saat / reset / durdurma | 14 | 11 | 3 | 0 |
| M2 Kontrol ünitesi | 13 | 13 | 0 | 0 |
| M3 Adres registerları | 22 | 22 | 0 | 0 |
| M4 Veri ve ALU | 8 | 8 | 0 | 0 |
| CPU yardımcı kapıları | 4 | 3 | 1 | 0 |
| M5 Bellek + I/O | 6 | 6 | 0 | 0 |
| M6 VGA zamanlaması | 19 | 11 | 8 | 0 |
| **Toplam (CPU + M6, M7 hariç)** | **86** | **74** | **12** | **0** |

Kurulmayanlar:
- M1 NE555 ×1: kapsam dışı: yavaş saat kaynağı; MCLK test tezgâhından
- M1 74HC153 ×1: kapsam dışı: saat kaynağı seçici
- M1 74HC14 ×1: kapsam dışı: RC reset / buton debounce / 555 kare dalgası
- AUX 74HC00 ×1: kapsam dışı değil: 138'li WAIT (DOGRULAMA 2.5) ve G1 = CLK düzeltmesiyle NAND(MEMW_L, /VWR_s) ve OR kalktı; 12 NAND'ın 7'si yetiyor, 2. yardımcı 74HC00 gereksiz
- M6 SST39SF010 ×1: sırada: font ROM'u (8.3)
- M6 74HC157 ×3: sırada: VRAM adres seçimi (8.3, 8.5)
- M6 CY62256 ×1: sırada: VRAM (şimdilik TB X1 taklidi)
- M6 74HC245 ×1: sırada: DB → VRAM tamponu, /OE = /BUFEN (8.5)
- M6 74HC166 ×1: sırada: glyph kaydırma registerı (8.3)
- M6 74HC08 ×1: sırada: çıkış katı AND(QH, BLANK_n) (8.4)

## M1 Saat / reset / durdurma

### U101 · 74HC74

Johnson sayacı (3.1): FF1 = Q1, FF2 = Q2. Fazlar A=00 B=10 C=11 D=01. CLK = Q2 (net adı CLK), LCLK = /Q1. /RESET_s her iki FF'yi /SD ile 1'e kurar → C fazı (3.4). /RD kullanılmaz (VCC).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/1RD` | `VCC` |
| 2 | `1D` | `Q1_D` |
| 3 | `1CP` | `MCLK` |
| 4 | `/1SD` | `/RESET_s` |
| 5 | `1Q` | `Q1` |
| 6 | `/1Q` | `LCLK` |
| 7 | `GND` | *GND* (güç) |
| 8 | `/2Q` | `/CLK` |
| 9 | `2Q` | `CLK` |
| 10 | `/2SD` | `/RESET_s` |
| 11 | `2CP` | `MCLK` |
| 12 | `2D` | `Q2_D` |
| 13 | `/2RD` | `VCC` |
| 14 | `VCC` | *VCC* (güç) |

### U102 · 74HC74

Reset senkronlayıcısı (3.4): 2 FF, D1 = VCC. /RESET düşünce iki FF de hemen 0 (asenkron başlama), bırakılınca 1 iki MCLK kenarında geçer (senkron bırakma). Giriş /RESET: RC + buton + Arduino → 74HC14 çıkışı; 74HC14 ve RC 5. hafta, burada test tezgâhından temiz aktif-düşük giriş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/1RD` | `/RESET` |
| 2 | `1D` | `VCC` |
| 3 | `1CP` | `MCLK` |
| 4 | `/1SD` | `VCC` |
| 5 | `1Q` | `RST_S1` |
| 6 | `/1Q` | — (boş) |
| 7 | `GND` | *GND* (güç) |
| 8 | `/2Q` | — (boş) |
| 9 | `2Q` | `/RESET_s` |
| 10 | `/2SD` | `VCC` |
| 11 | `2CP` | `MCLK` |
| 12 | `2D` | `RST_S1` |
| 13 | `/2RD` | `/RESET` |
| 14 | `VCC` | *VCC* (güç) |

### U103 · 74HC00

Johnson sonraki durum (3.1, 3.6): Q1' = NAND(Q2, NAND(STOP, Q1)) (= !Q2 | STOP&Q1, 2 kapı); Q2' = NAND(/Q1, /WAIT); /WAIT, 138'in G1 = Q2 ucu sayesinde zaten OR(/WAIT, /Q2). 4. kapı /GO = NAND(sync2, /prev) (3.3). PLAN DÜZELTMESİ (PLAN_FIXES[0]).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `1A` | `STOP` |
| 2 | `1B` | `Q1` |
| 3 | `1Y` | `STOP_Q1_n` |
| 4 | `2A` | `CLK` |
| 5 | `2B` | `STOP_Q1_n` |
| 6 | `2Y` | `Q1_D` |
| 7 | `GND` | *GND* (güç) |
| 8 | `3Y` | `Q2_D` |
| 9 | `3A` | `LCLK` |
| 10 | `3B` | `/WAIT` |
| 11 | `4Y` | `/GO` |
| 12 | `4A` | `GO_S2` |
| 13 | `4B` | `/GO_PREV` |
| 14 | `VCC` | *VCC* (güç) |

### U104 · 74HC32

1. kapı boş, girişleri GND (planda OR(/WAIT, /Q2); düzeltmeyle 138'in G1 ucuna taşındı). STOP denkleminin 3 OR'u (3.3): MICRO|NEXT_L, HALT_L|BRK_L, (HALT_L|BRK_L)|(STEPMODE_s&(MICRO|NEXT_L)). 4. STOP OR'u (BRQ_s) AUX U503'te. PLAN DÜZELTMESİ (PLAN_FIXES[0]).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `1A` | `GND` |
| 2 | `1B` | `GND` |
| 3 | `1Y` | — (boş) |
| 4 | `2A` | `MICRO` |
| 5 | `2B` | `NEXT_L` |
| 6 | `2Y` | `STOP_MN` |
| 7 | `GND` | *GND* (güç) |
| 8 | `3Y` | `STOP_HB` |
| 9 | `3A` | `HALT_L` |
| 10 | `3B` | `BRK_L` |
| 11 | `4Y` | `STOP_T` |
| 12 | `4A` | `STOP_HB` |
| 13 | `4B` | `STOP_SM` |
| 14 | `VCC` | *VCC* (güç) |

### U105 · 74HC08

STEPMODE_s & (MICRO|NEXT_L); (…) & !GO. 3. ve 4. kapı BUSACK D = BRQ_s & Q1 & Q2 (10): istek var ve makine C fazında.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `1A` | `STEPMODE_s` |
| 2 | `1B` | `STOP_MN` |
| 3 | `1Y` | `STOP_SM` |
| 4 | `2A` | `STOP_T` |
| 5 | `2B` | `/GO` |
| 6 | `2Y` | `STOP_G` |
| 7 | `GND` | *GND* (güç) |
| 8 | `3Y` | `BRQ_Q1` |
| 9 | `3A` | `BRQ_s` |
| 10 | `3B` | `Q1` |
| 11 | `4Y` | `BUSACK_D` |
| 12 | `4A` | `BRQ_Q1` |
| 13 | `4B` | `CLK` |
| 14 | `VCC` | *VCC* (güç) |

### U106 · 74HC02

WSTB = NOR(Q1, Q2): A fazında. 2. kapı BRK D = NOR(/MATCH, /ACCESS): breakpoint adresine bu çevrimde okuma ya da yazma var (10). 3, 4 boş, girişleri GND.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `1Y` | `WSTB` |
| 2 | `1A` | `Q1` |
| 3 | `1B` | `CLK` |
| 4 | `2Y` | `BRK_D` |
| 5 | `2A` | `/MATCH` |
| 6 | `2B` | `/ACCESS` |
| 7 | `GND` | *GND* (güç) |
| 8 | `3A` | `GND` |
| 9 | `3B` | `GND` |
| 10 | `3Y` | — (boş) |
| 11 | `4A` | `GND` |
| 12 | `4B` | `GND` |
| 13 | `4Y` | — (boş) |
| 14 | `VCC` | *VCC* (güç) |

### U107 · 74HC175

GO senkronlayıcısı (sync1, sync2, prev; GO = sync2 & !prev tam bir MCLK) ve STEPMODE senkronlayıcısı. /MR planda yok: VCC seçildi (reset GO'yu etkilemesin). GO_BTN: RC + 74HC14 çıkışı (5. hafta), burada temiz giriş. MICRO senkronlanmaz (plan 3.3: yalnız STEPMODE_s).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `VCC` |
| 2 | `Q0` | `GO_S1` |
| 3 | `/Q0` | — (boş) |
| 4 | `D0` | `GO_BTN` |
| 5 | `D1` | `GO_S1` |
| 6 | `/Q1` | — (boş) |
| 7 | `Q1` | `GO_S2` |
| 8 | `GND` | *GND* (güç) |
| 9 | `CP` | `MCLK` |
| 10 | `Q2` | `GO_PREV` |
| 11 | `/Q2` | `/GO_PREV` |
| 12 | `D2` | `GO_S2` |
| 13 | `D3` | `STEPMODE` |
| 14 | `/Q3` | — (boş) |
| 15 | `Q3` | `STEPMODE_s` |
| 16 | `VCC` | *VCC* (güç) |

### U108 · 74HC138

WAIT (3.6, DOGRULAMA 2.5): G1 = CLK (= Q2; planda VCC), /G2A = /FPAGE, /G2B = A11, A = /MEMW, B = VWR_s, C = GND. Y0 = /WAIT (F000–F7FF'ye yazma VE pencere kapalı VE Q2 = 1, yani C ya da D fazı). Y1–Y7 boş. PLAN DÜZELTMESİ (PLAN_FIXES[0]).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `A0` | `/MEMW` |
| 2 | `A1` | `VWR_s` |
| 3 | `A2` | `GND` |
| 4 | `/E1` | `/FPAGE` |
| 5 | `/E2` | `AB11` |
| 6 | `E3` | `CLK` |
| 7 | `/Y7` | — (boş) |
| 8 | `GND` | *GND* (güç) |
| 9 | `/Y6` | — (boş) |
| 10 | `/Y5` | — (boş) |
| 11 | `/Y4` | — (boş) |
| 12 | `/Y3` | — (boş) |
| 13 | `/Y2` | — (boş) |
| 14 | `/Y1` | — (boş) |
| 15 | `/Y0` | `/WAIT` |
| 16 | `VCC` | *VCC* (güç) |

### U109 · 74HC245

CLK tamponu (3.5): her çıkış ayrı bir yıldız dal (gerçekte 47 Ω seri). Dallar: PC | AR | X | SP+STEP | A+F+IR (aynı dal, 3.5) | LED + BRK (+KCLR, M7) | test noktası. 8. kanal boş: A7 = GND (çıkışı boşta salınmasın diye), B7 bağlı değil.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `CLK` |
| 3 | `A1` | `CLK` |
| 4 | `A2` | `CLK` |
| 5 | `A3` | `CLK` |
| 6 | `A4` | `CLK` |
| 7 | `A5` | `CLK` |
| 8 | `A6` | `CLK` |
| 9 | `A7` | `GND` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | — (boş) |
| 12 | `B6` | `CLK_TP` |
| 13 | `B5` | `CLK_IO` |
| 14 | `B4` | `CLK_AFI` |
| 15 | `B3` | `CLK_SP` |
| 16 | `B2` | `CLK_X` |
| 17 | `B1` | `CLK_AR` |
| 18 | `B0` | `CLK_PC` |
| 19 | `/OE` | `GND` |
| 20 | `VCC` | *VCC* (güç) |

### U110 · 74HC74

FF1 BRK (10): commit'te (CLK, LED dalı) BRK D örneklenir. BRK_L = 1 → STOP → makine C'de durur; GO bir çevrim çalıştırır ve sonraki commit BRK'yi yeniden örnekler (o çevrimde erişim yoksa 0). FF2 BUSACK (10): MCLK ile, D = BRQ_s & C fazı. BUSACK = 1 → #DS ve #AS kapalı (AB, DB sürülmez). İkisi de /RESET_s ile temizlenir (3.4). /Q çıkışları boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/1RD` | `/RESET_s` |
| 2 | `1D` | `BRK_D` |
| 3 | `1CP` | `CLK_IO` |
| 4 | `/1SD` | `VCC` |
| 5 | `1Q` | `BRK_L` |
| 6 | `/1Q` | — (boş) |
| 7 | `GND` | *GND* (güç) |
| 8 | `/2Q` | — (boş) |
| 9 | `2Q` | `BUSACK` |
| 10 | `/2SD` | `VCC` |
| 11 | `2CP` | `MCLK` |
| 12 | `2D` | `BUSACK_D` |
| 13 | `/2RD` | `/RESET_s` |
| 14 | `VCC` | *VCC* (güç) |

### U111 · 74HC175

/BUSREQ senkronlayıcısı (10): 2 FF, BRQ_s = NOT /BUSREQ iki MCLK gecikmeyle (/Q1). BRQ_s → STOP (U503) ve BUSACK D (U105). /MR = VCC (U107 gibi). FF2, FF3 VWR ×2 senkronlayıcısı (3.6): VWR (M6, T1 Q7) → VWR_S1 → VWR_s, iki MCLK kenarı. VWR 12.5 MHz DCLK ile değişir, MCLK ile ilgisiz: iki FF metastabiliteye karşı.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `VCC` |
| 2 | `Q0` | `BRQ_S1n` |
| 3 | `/Q0` | — (boş) |
| 4 | `D0` | `/BUSREQ` |
| 5 | `D1` | `BRQ_S1n` |
| 6 | `/Q1` | `BRQ_s` |
| 7 | `Q1` | — (boş) |
| 8 | `GND` | *GND* (güç) |
| 9 | `CP` | `MCLK` |
| 10 | `Q2` | `VWR_S1` |
| 11 | `/Q2` | — (boş) |
| 12 | `D2` | `VWR` |
| 13 | `D3` | `VWR_S1` |
| 14 | `/Q3` | — (boş) |
| 15 | `Q3` | `VWR_s` |
| 16 | `VCC` | *VCC* (güç) |

## M2 Kontrol ünitesi

### U201 · SST39SF010

uROM0 (4.1): A0–3 STEP, A4–11 IR, A12–15 Z C N V, A16 BANK jumper (= GND, bank 0). /CE = GND, /WE = VCC, /OE = MANUAL (panel 5. hafta: MANUAL = 0). -70 (DOGRULAMA 2b). Çıkış: kontrol kelimesi bit 0–7.

| Bacak | Pin | Net |
|---:|---|---|
| 2 | `A16` | `GND` |
| 3 | `A15` | `V` |
| 4 | `A12` | `Z` |
| 5 | `A7` | `IR3` |
| 6 | `A6` | `IR2` |
| 7 | `A5` | `IR1` |
| 8 | `A4` | `IR0` |
| 9 | `A3` | `STEP3` |
| 10 | `A2` | `STEP2` |
| 11 | `A1` | `STEP1` |
| 12 | `A0` | `STEP0` |
| 13 | `DQ0` | `ASRC0` |
| 14 | `DQ1` | `ASRC1` |
| 15 | `DQ2` | `DSRC0` |
| 16 | `GND` | *GND* (güç) |
| 17 | `DQ3` | `DSRC1` |
| 18 | `DQ4` | `DSRC2` |
| 19 | `DQ5` | `DDST0` |
| 20 | `DQ6` | `DDST1` |
| 21 | `DQ7` | `DDST2` |
| 22 | `/CE` | `GND` |
| 23 | `A10` | `IR6` |
| 24 | `/OE` | `MANUAL` |
| 25 | `A11` | `IR7` |
| 26 | `A9` | `IR5` |
| 27 | `A8` | `IR4` |
| 28 | `A13` | `C` |
| 29 | `A14` | `N` |
| 31 | `/WE` | `VCC` |
| 32 | `VCC` | *VCC* (güç) |

### U202 · SST39SF010

uROM1 (4.1): A0–3 STEP, A4–11 IR, A12–15 Z C N V, A16 BANK jumper (= GND, bank 0). /CE = GND, /WE = VCC, /OE = MANUAL (panel 5. hafta: MANUAL = 0). -70 (DOGRULAMA 2b). Çıkış: kontrol kelimesi bit 8–15.

| Bacak | Pin | Net |
|---:|---|---|
| 2 | `A16` | `GND` |
| 3 | `A15` | `V` |
| 4 | `A12` | `Z` |
| 5 | `A7` | `IR3` |
| 6 | `A6` | `IR2` |
| 7 | `A5` | `IR1` |
| 8 | `A4` | `IR0` |
| 9 | `A3` | `STEP3` |
| 10 | `A2` | `STEP2` |
| 11 | `A1` | `STEP1` |
| 12 | `A0` | `STEP0` |
| 13 | `DQ0` | `ALUOP0` |
| 14 | `DQ1` | `ALUOP1` |
| 15 | `DQ2` | `ALUOP2` |
| 16 | `GND` | *GND* (güç) |
| 17 | `DQ3` | `ALUOP3` |
| 18 | `DQ4` | `ALUOP4` |
| 19 | `DQ5` | `FL` |
| 20 | `DQ6` | `MEMW` |
| 21 | `DQ7` | `MARK` |
| 22 | `/CE` | `GND` |
| 23 | `A10` | `IR6` |
| 24 | `/OE` | `MANUAL` |
| 25 | `A11` | `IR7` |
| 26 | `A9` | `IR5` |
| 27 | `A8` | `IR4` |
| 28 | `A13` | `C` |
| 29 | `A14` | `N` |
| 31 | `/WE` | `VCC` |
| 32 | `VCC` | *VCC* (güç) |

### U203 · SST39SF010

uROM2 (4.1): A0–3 STEP, A4–11 IR, A12–15 Z C N V, A16 BANK jumper (= GND, bank 0). /CE = GND, /WE = VCC, /OE = MANUAL (panel 5. hafta: MANUAL = 0). -70 (DOGRULAMA 2b). Çıkış: kontrol kelimesi bit 16–23.

| Bacak | Pin | Net |
|---:|---|---|
| 2 | `A16` | `GND` |
| 3 | `A15` | `V` |
| 4 | `A12` | `Z` |
| 5 | `A7` | `IR3` |
| 6 | `A6` | `IR2` |
| 7 | `A5` | `IR1` |
| 8 | `A4` | `IR0` |
| 9 | `A3` | `STEP3` |
| 10 | `A2` | `STEP2` |
| 11 | `A1` | `STEP1` |
| 12 | `A0` | `STEP0` |
| 13 | `DQ0` | `PCINC` |
| 14 | `DQ1` | `PCLD` |
| 15 | `DQ2` | `ARINC` |
| 16 | `GND` | *GND* (güç) |
| 17 | `DQ3` | `XINC` |
| 18 | `DQ4` | `SPCNT` |
| 19 | `DQ5` | `SPDN` |
| 20 | `DQ6` | `NEXT` |
| 21 | `DQ7` | `HALT` |
| 22 | `/CE` | `GND` |
| 23 | `A10` | `IR6` |
| 24 | `/OE` | `MANUAL` |
| 25 | `A11` | `IR7` |
| 26 | `A9` | `IR5` |
| 27 | `A8` | `IR4` |
| 28 | `A13` | `C` |
| 29 | `A14` | `N` |
| 31 | `/WE` | `VCC` |
| 32 | `VCC` | *VCC* (güç) |

### U204 · 74HC273

Kontrol latch'i 0 (4.2): CP = LCLK (C→D), /MR = /RESET_s (NOP kelimesi). LCLK doğrudan 74HC74'ten (3.5).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `Q0` | `ASRC0_L` |
| 3 | `D0` | `ASRC0` |
| 4 | `D1` | `ASRC1` |
| 5 | `Q1` | `ASRC1_L` |
| 6 | `Q2` | `DSRC0_L` |
| 7 | `D2` | `DSRC0` |
| 8 | `D3` | `DSRC1` |
| 9 | `Q3` | `DSRC1_L` |
| 10 | `GND` | *GND* (güç) |
| 11 | `CP` | `LCLK` |
| 12 | `Q4` | `DSRC2_L` |
| 13 | `D4` | `DSRC2` |
| 14 | `D5` | `DDST0` |
| 15 | `Q5` | `DDST0_L` |
| 16 | `Q6` | `DDST1_L` |
| 17 | `D6` | `DDST1` |
| 18 | `D7` | `DDST2` |
| 19 | `Q7` | `DDST2_L` |
| 20 | `VCC` | *VCC* (güç) |

### U205 · 74HC273

Kontrol latch'i 1 (4.2): CP = LCLK (C→D), /MR = /RESET_s (NOP kelimesi). LCLK doğrudan 74HC74'ten (3.5).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `Q0` | `ALUOP0_L` |
| 3 | `D0` | `ALUOP0` |
| 4 | `D1` | `ALUOP1` |
| 5 | `Q1` | `ALUOP1_L` |
| 6 | `Q2` | `ALUOP2_L` |
| 7 | `D2` | `ALUOP2` |
| 8 | `D3` | `ALUOP3` |
| 9 | `Q3` | `ALUOP3_L` |
| 10 | `GND` | *GND* (güç) |
| 11 | `CP` | `LCLK` |
| 12 | `Q4` | `ALUOP4_L` |
| 13 | `D4` | `ALUOP4` |
| 14 | `D5` | `FL` |
| 15 | `Q5` | `FL_L` |
| 16 | `Q6` | `MEMW_L` |
| 17 | `D6` | `MEMW` |
| 18 | `D7` | `MARK` |
| 19 | `Q7` | `MARK_L` |
| 20 | `VCC` | *VCC* (güç) |

### U206 · 74HC273

Kontrol latch'i 2 (4.2): CP = LCLK (C→D), /MR = /RESET_s (NOP kelimesi). LCLK doğrudan 74HC74'ten (3.5).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `Q0` | `PCINC_L` |
| 3 | `D0` | `PCINC` |
| 4 | `D1` | `PCLD` |
| 5 | `Q1` | `PCLD_L` |
| 6 | `Q2` | `ARINC_L` |
| 7 | `D2` | `ARINC` |
| 8 | `D3` | `XINC` |
| 9 | `Q3` | `XINC_L` |
| 10 | `GND` | *GND* (güç) |
| 11 | `CP` | `LCLK` |
| 12 | `Q4` | `SPCNT_L` |
| 13 | `D4` | `SPCNT` |
| 14 | `D5` | `SPDN` |
| 15 | `Q5` | `SPDN_L` |
| 16 | `Q6` | `NEXT_L` |
| 17 | `D6` | `NEXT` |
| 18 | `D7` | `HALT` |
| 19 | `Q7` | `HALT_L` |
| 20 | `VCC` | *VCC* (güç) |

### U207 · 74HC138

#DS (4.3): G1 = VCC, /G2A = BUSACK, /G2B = GND (ISA-v0-sentez 4.3). Y0 (yok), Y5–Y6 (ayrılmış), Y7 (yok/panel) boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `A0` | `DSRC0_L` |
| 2 | `A1` | `DSRC1_L` |
| 3 | `A2` | `DSRC2_L` |
| 4 | `/E1` | `BUSACK` |
| 5 | `/E2` | `GND` |
| 6 | `E3` | `VCC` |
| 7 | `/Y7` | — (boş) |
| 8 | `GND` | *GND* (güç) |
| 9 | `/Y6` | — (boş) |
| 10 | `/Y5` | — (boş) |
| 11 | `/Y4` | `/OE_PCH` |
| 12 | `/Y3` | `/OE_PCL` |
| 13 | `/Y2` | `/OE_A` |
| 14 | `/Y1` | `/MRD` |
| 15 | `/Y0` | — (boş) |
| 16 | `VCC` | *VCC* (güç) |

### U208 · 74HC138

#DD (4.3): hep izinli. Çıkışlar senkron yükleme izinleri (saat değil). Y0 (yok), Y7 (yasak) boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `A0` | `DDST0_L` |
| 2 | `A1` | `DDST1_L` |
| 3 | `A2` | `DDST2_L` |
| 4 | `/E1` | `GND` |
| 5 | `/E2` | `GND` |
| 6 | `E3` | `VCC` |
| 7 | `/Y7` | — (boş) |
| 8 | `GND` | *GND* (güç) |
| 9 | `/Y6` | `/DD_ARH` |
| 10 | `/Y5` | `/DD_ARL` |
| 11 | `/Y4` | `/DD_XH` |
| 12 | `/Y3` | `/DD_XL` |
| 13 | `/Y2` | `/DD_A` |
| 14 | `/Y1` | `/DD_IR` |
| 15 | `/Y0` | — (boş) |
| 16 | `VCC` | *VCC* (güç) |

### U209 · 74HC139

1. yarı #AS (4.3): /G = BUSACK, Y0..Y3 → PC/AR/X/SP AB tamponlarının /OE'si. 2. yarı #MS (7.2): /G = /FPAGE, A = A11, B = GND → Y0 /VRAMSEL, Y1 /IOSEL; Y2, Y3 boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/1E` | `BUSACK` |
| 2 | `1A0` | `ASRC0_L` |
| 3 | `1A1` | `ASRC1_L` |
| 4 | `/1Y0` | `/AB_PC` |
| 5 | `/1Y1` | `/AB_AR` |
| 6 | `/1Y2` | `/AB_X` |
| 7 | `/1Y3` | `/AB_SP` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/2Y3` | — (boş) |
| 10 | `/2Y2` | — (boş) |
| 11 | `/2Y1` | `/IOSEL` |
| 12 | `/2Y0` | `/VRAMSEL` |
| 13 | `2A1` | `GND` |
| 14 | `2A0` | `AB11` |
| 15 | `/2E` | `/FPAGE` |
| 16 | `VCC` | *VCC* (güç) |

### U212 · 74HC688

Breakpoint karşılaştırıcısı, alt bayt (10): AB0..7 = BP0..7 ve /BP_EN = 0 ise /MATCH_LO = 0. BP0..15: 16 DIP anahtarı; /BP_EN: breakpoint açma anahtarı (pull-up, açık = kapalı; planda yok, 0000 adresinde istemeden durmasın diye).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/G` | `/BP_EN` |
| 2 | `P0` | `AB0` |
| 3 | `Q0` | `BP0` |
| 4 | `P1` | `AB1` |
| 5 | `Q1` | `BP1` |
| 6 | `P2` | `AB2` |
| 7 | `Q2` | `BP2` |
| 8 | `P3` | `AB3` |
| 9 | `Q3` | `BP3` |
| 10 | `GND` | *GND* (güç) |
| 11 | `P4` | `AB4` |
| 12 | `Q4` | `BP4` |
| 13 | `P5` | `AB5` |
| 14 | `Q5` | `BP5` |
| 15 | `P6` | `AB6` |
| 16 | `Q6` | `BP6` |
| 17 | `P7` | `AB7` |
| 18 | `Q7` | `BP7` |
| 19 | `/P=Q` | `/MATCH_LO` |
| 20 | `VCC` | *VCC* (güç) |

### U213 · 74HC688

Breakpoint karşılaştırıcısı, üst bayt, kademeli (10): /G = alt baytın sonucu. /MATCH = 0 ⇔ AB = BP ve breakpoint açık. BRK D = NOR(/MATCH, /ACCESS) (U106).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/G` | `/MATCH_LO` |
| 2 | `P0` | `AB8` |
| 3 | `Q0` | `BP8` |
| 4 | `P1` | `AB9` |
| 5 | `Q1` | `BP9` |
| 6 | `P2` | `AB10` |
| 7 | `Q2` | `BP10` |
| 8 | `P3` | `AB11` |
| 9 | `Q3` | `BP11` |
| 10 | `GND` | *GND* (güç) |
| 11 | `P4` | `AB12` |
| 12 | `Q4` | `BP12` |
| 13 | `P5` | `AB13` |
| 14 | `Q5` | `BP13` |
| 15 | `P6` | `AB14` |
| 16 | `Q6` | `BP14` |
| 17 | `P7` | `AB15` |
| 18 | `Q7` | `BP15` |
| 19 | `/P=Q` | `/MATCH` |
| 20 | `VCC` | *VCC* (güç) |

### U210 · 74HC161

STEP sayacı (4.4): CEP = CET = 1, /PE = NOT NEXT, P = 0000 (senkron sıfırlama), /MR = /RESET_s. CLK dalı: SP+STEP (3.5). TC boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_SP` |
| 3 | `D0` | `GND` |
| 4 | `D1` | `GND` |
| 5 | `D2` | `GND` |
| 6 | `D3` | `GND` |
| 7 | `CEP` | `VCC` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/NEXT` |
| 10 | `CET` | `VCC` |
| 11 | `Q3` | `STEP3` |
| 12 | `Q2` | `STEP2` |
| 13 | `Q1` | `STEP1` |
| 14 | `Q0` | `STEP0` |
| 15 | `TC` | — (boş) |
| 16 | `VCC` | *VCC* (güç) |

### U211 · 74HC04

Kutup düzeltmeleri (4.2): FL → F /PE, PCLD → PC /PE, NEXT → STEP /PE, SPCNT → SP /CE (alt), MEMW → /MEMW. 6. kapı boş (girişi GND).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `1A` | `FL_L` |
| 2 | `1Y` | `/FL` |
| 3 | `2A` | `PCLD_L` |
| 4 | `2Y` | `/PCLD` |
| 5 | `3A` | `NEXT_L` |
| 6 | `3Y` | `/NEXT` |
| 7 | `GND` | *GND* (güç) |
| 8 | `4Y` | `/SPCNT` |
| 9 | `4A` | `SPCNT_L` |
| 10 | `5Y` | `/MEMW` |
| 11 | `5A` | `MEMW_L` |
| 12 | `6Y` | — (boş) |
| 13 | `6A` | `GND` |
| 14 | `VCC` | *VCC* (güç) |

## M3 Adres registerları

### U301 · 74HC161

PC bit 0–3. PC (5.1): /PE = /PCLD, P = AR (PCIN, 16 bit birden), CEP = PCINC, /MR = /RESET_s → 0000. CET zinciri: CET = VCC (planda yalnız "CET chained from TC"; ilk kademe VCC seçildi).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_PC` |
| 3 | `D0` | `AR0` |
| 4 | `D1` | `AR1` |
| 5 | `D2` | `AR2` |
| 6 | `D3` | `AR3` |
| 7 | `CEP` | `PCINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/PCLD` |
| 10 | `CET` | `VCC` |
| 11 | `Q3` | `PC3` |
| 12 | `Q2` | `PC2` |
| 13 | `Q1` | `PC1` |
| 14 | `Q0` | `PC0` |
| 15 | `TC` | `PC_TC0` |
| 16 | `VCC` | *VCC* (güç) |

### U302 · 74HC161

PC bit 4–7. PC (5.1): /PE = /PCLD, P = AR (PCIN, 16 bit birden), CEP = PCINC, /MR = /RESET_s → 0000. CET zinciri: CET = önceki kademenin TC'si.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_PC` |
| 3 | `D0` | `AR4` |
| 4 | `D1` | `AR5` |
| 5 | `D2` | `AR6` |
| 6 | `D3` | `AR7` |
| 7 | `CEP` | `PCINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/PCLD` |
| 10 | `CET` | `PC_TC0` |
| 11 | `Q3` | `PC7` |
| 12 | `Q2` | `PC6` |
| 13 | `Q1` | `PC5` |
| 14 | `Q0` | `PC4` |
| 15 | `TC` | `PC_TC1` |
| 16 | `VCC` | *VCC* (güç) |

### U303 · 74HC161

PC bit 8–11. PC (5.1): /PE = /PCLD, P = AR (PCIN, 16 bit birden), CEP = PCINC, /MR = /RESET_s → 0000. CET zinciri: CET = önceki kademenin TC'si.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_PC` |
| 3 | `D0` | `AR8` |
| 4 | `D1` | `AR9` |
| 5 | `D2` | `AR10` |
| 6 | `D3` | `AR11` |
| 7 | `CEP` | `PCINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/PCLD` |
| 10 | `CET` | `PC_TC1` |
| 11 | `Q3` | `PC11` |
| 12 | `Q2` | `PC10` |
| 13 | `Q1` | `PC9` |
| 14 | `Q0` | `PC8` |
| 15 | `TC` | `PC_TC2` |
| 16 | `VCC` | *VCC* (güç) |

### U304 · 74HC161

PC bit 12–15. PC (5.1): /PE = /PCLD, P = AR (PCIN, 16 bit birden), CEP = PCINC, /MR = /RESET_s → 0000. CET zinciri: CET = önceki kademenin TC'si. TC boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_PC` |
| 3 | `D0` | `AR12` |
| 4 | `D1` | `AR13` |
| 5 | `D2` | `AR14` |
| 6 | `D3` | `AR15` |
| 7 | `CEP` | `PCINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/PCLD` |
| 10 | `CET` | `PC_TC2` |
| 11 | `Q3` | `PC15` |
| 12 | `Q2` | `PC14` |
| 13 | `Q1` | `PC13` |
| 14 | `Q0` | `PC12` |
| 15 | `TC` | — (boş) |
| 16 | `VCC` | *VCC* (güç) |

### U305 · 74HC161

AR bit 0–3. AR (5.1): P = DB, alt çift /DD_ARL, üst çift /DD_ARH, CEP = ARINC. Çıkışlar = PCIN. CET zinciri: CET = VCC (planda yalnız "CET chained from TC"; ilk kademe VCC seçildi).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_AR` |
| 3 | `D0` | `DB0` |
| 4 | `D1` | `DB1` |
| 5 | `D2` | `DB2` |
| 6 | `D3` | `DB3` |
| 7 | `CEP` | `ARINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/DD_ARL` |
| 10 | `CET` | `VCC` |
| 11 | `Q3` | `AR3` |
| 12 | `Q2` | `AR2` |
| 13 | `Q1` | `AR1` |
| 14 | `Q0` | `AR0` |
| 15 | `TC` | `AR_TC0` |
| 16 | `VCC` | *VCC* (güç) |

### U306 · 74HC161

AR bit 4–7. AR (5.1): P = DB, alt çift /DD_ARL, üst çift /DD_ARH, CEP = ARINC. Çıkışlar = PCIN. CET zinciri: CET = önceki kademenin TC'si.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_AR` |
| 3 | `D0` | `DB4` |
| 4 | `D1` | `DB5` |
| 5 | `D2` | `DB6` |
| 6 | `D3` | `DB7` |
| 7 | `CEP` | `ARINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/DD_ARL` |
| 10 | `CET` | `AR_TC0` |
| 11 | `Q3` | `AR7` |
| 12 | `Q2` | `AR6` |
| 13 | `Q1` | `AR5` |
| 14 | `Q0` | `AR4` |
| 15 | `TC` | `AR_TC1` |
| 16 | `VCC` | *VCC* (güç) |

### U307 · 74HC161

AR bit 8–11. AR (5.1): P = DB, alt çift /DD_ARL, üst çift /DD_ARH, CEP = ARINC. Çıkışlar = PCIN. CET zinciri: CET = önceki kademenin TC'si.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_AR` |
| 3 | `D0` | `DB0` |
| 4 | `D1` | `DB1` |
| 5 | `D2` | `DB2` |
| 6 | `D3` | `DB3` |
| 7 | `CEP` | `ARINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/DD_ARH` |
| 10 | `CET` | `AR_TC1` |
| 11 | `Q3` | `AR11` |
| 12 | `Q2` | `AR10` |
| 13 | `Q1` | `AR9` |
| 14 | `Q0` | `AR8` |
| 15 | `TC` | `AR_TC2` |
| 16 | `VCC` | *VCC* (güç) |

### U308 · 74HC161

AR bit 12–15. AR (5.1): P = DB, alt çift /DD_ARL, üst çift /DD_ARH, CEP = ARINC. Çıkışlar = PCIN. CET zinciri: CET = önceki kademenin TC'si. TC boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_AR` |
| 3 | `D0` | `DB4` |
| 4 | `D1` | `DB5` |
| 5 | `D2` | `DB6` |
| 6 | `D3` | `DB7` |
| 7 | `CEP` | `ARINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/DD_ARH` |
| 10 | `CET` | `AR_TC2` |
| 11 | `Q3` | `AR15` |
| 12 | `Q2` | `AR14` |
| 13 | `Q1` | `AR13` |
| 14 | `Q0` | `AR12` |
| 15 | `TC` | — (boş) |
| 16 | `VCC` | *VCC* (güç) |

### U309 · 74HC161

X bit 0–3. X (5.1): P = DB, /DD_XL, /DD_XH, CEP = XINC. CET zinciri: CET = VCC (planda yalnız "CET chained from TC"; ilk kademe VCC seçildi).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_X` |
| 3 | `D0` | `DB0` |
| 4 | `D1` | `DB1` |
| 5 | `D2` | `DB2` |
| 6 | `D3` | `DB3` |
| 7 | `CEP` | `XINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/DD_XL` |
| 10 | `CET` | `VCC` |
| 11 | `Q3` | `X3` |
| 12 | `Q2` | `X2` |
| 13 | `Q1` | `X1` |
| 14 | `Q0` | `X0` |
| 15 | `TC` | `X_TC0` |
| 16 | `VCC` | *VCC* (güç) |

### U310 · 74HC161

X bit 4–7. X (5.1): P = DB, /DD_XL, /DD_XH, CEP = XINC. CET zinciri: CET = önceki kademenin TC'si.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_X` |
| 3 | `D0` | `DB4` |
| 4 | `D1` | `DB5` |
| 5 | `D2` | `DB6` |
| 6 | `D3` | `DB7` |
| 7 | `CEP` | `XINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/DD_XL` |
| 10 | `CET` | `X_TC0` |
| 11 | `Q3` | `X7` |
| 12 | `Q2` | `X6` |
| 13 | `Q1` | `X5` |
| 14 | `Q0` | `X4` |
| 15 | `TC` | `X_TC1` |
| 16 | `VCC` | *VCC* (güç) |

### U311 · 74HC161

X bit 8–11. X (5.1): P = DB, /DD_XL, /DD_XH, CEP = XINC. CET zinciri: CET = önceki kademenin TC'si.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_X` |
| 3 | `D0` | `DB0` |
| 4 | `D1` | `DB1` |
| 5 | `D2` | `DB2` |
| 6 | `D3` | `DB3` |
| 7 | `CEP` | `XINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/DD_XH` |
| 10 | `CET` | `X_TC1` |
| 11 | `Q3` | `X11` |
| 12 | `Q2` | `X10` |
| 13 | `Q1` | `X9` |
| 14 | `Q0` | `X8` |
| 15 | `TC` | `X_TC2` |
| 16 | `VCC` | *VCC* (güç) |

### U312 · 74HC161

X bit 12–15. X (5.1): P = DB, /DD_XL, /DD_XH, CEP = XINC. CET zinciri: CET = önceki kademenin TC'si. TC boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_X` |
| 3 | `D0` | `DB4` |
| 4 | `D1` | `DB5` |
| 5 | `D2` | `DB6` |
| 6 | `D3` | `DB7` |
| 7 | `CEP` | `XINC_L` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/DD_XH` |
| 10 | `CET` | `X_TC2` |
| 11 | `Q3` | `X15` |
| 12 | `Q2` | `X14` |
| 13 | `Q1` | `X13` |
| 14 | `Q0` | `X12` |
| 15 | `TC` | — (boş) |
| 16 | `VCC` | *VCC* (güç) |

### U313 · 74HC191

SP alt nibble (5.1): /CE = NOT SPCNT (U211), D/U = SPDN (1 = aşağı), D = 1111, /PL = /RESET_s → F. MAX/MIN → üst /CE NAND'ı (U501). /RC boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `D1` | `VCC` |
| 2 | `Q1` | `SP1` |
| 3 | `Q0` | `SP0` |
| 4 | `/CE` | `/SPCNT` |
| 5 | `D/U` | `SPDN_L` |
| 6 | `Q2` | `SP2` |
| 7 | `Q3` | `SP3` |
| 8 | `GND` | *GND* (güç) |
| 9 | `D3` | `VCC` |
| 10 | `D2` | `VCC` |
| 11 | `/PL` | `/RESET_s` |
| 12 | `MAX/MIN` | `SP_MM0` |
| 13 | `/RC` | — (boş) |
| 14 | `CP` | `CLK_SP` |
| 15 | `D0` | `VCC` |
| 16 | `VCC` | *VCC* (güç) |

### U314 · 74HC191

SP üst nibble: /CE = NAND(SPCNT, MAX/MIN_alt) (U501). MAX/MIN ve /RC boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `D1` | `VCC` |
| 2 | `Q1` | `SP5` |
| 3 | `Q0` | `SP4` |
| 4 | `/CE` | `/SPCNT_HI` |
| 5 | `D/U` | `SPDN_L` |
| 6 | `Q2` | `SP6` |
| 7 | `Q3` | `SP7` |
| 8 | `GND` | *GND* (güç) |
| 9 | `D3` | `VCC` |
| 10 | `D2` | `VCC` |
| 11 | `/PL` | `/RESET_s` |
| 12 | `MAX/MIN` | — (boş) |
| 13 | `/RC` | — (boş) |
| 14 | `CP` | `CLK_SP` |
| 15 | `D0` | `VCC` |
| 16 | `VCC` | *VCC* (güç) |

### U315 · 74HC245

AB tamponu: PC alt → AB0–7. DIR = VCC (A→B), /OE = /AB_PC (#AS).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `PC0` |
| 3 | `A1` | `PC1` |
| 4 | `A2` | `PC2` |
| 5 | `A3` | `PC3` |
| 6 | `A4` | `PC4` |
| 7 | `A5` | `PC5` |
| 8 | `A6` | `PC6` |
| 9 | `A7` | `PC7` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `AB7` |
| 12 | `B6` | `AB6` |
| 13 | `B5` | `AB5` |
| 14 | `B4` | `AB4` |
| 15 | `B3` | `AB3` |
| 16 | `B2` | `AB2` |
| 17 | `B1` | `AB1` |
| 18 | `B0` | `AB0` |
| 19 | `/OE` | `/AB_PC` |
| 20 | `VCC` | *VCC* (güç) |

### U316 · 74HC245

AB tamponu: PC üst → AB8–15. DIR = VCC (A→B), /OE = /AB_PC (#AS).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `PC8` |
| 3 | `A1` | `PC9` |
| 4 | `A2` | `PC10` |
| 5 | `A3` | `PC11` |
| 6 | `A4` | `PC12` |
| 7 | `A5` | `PC13` |
| 8 | `A6` | `PC14` |
| 9 | `A7` | `PC15` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `AB15` |
| 12 | `B6` | `AB14` |
| 13 | `B5` | `AB13` |
| 14 | `B4` | `AB12` |
| 15 | `B3` | `AB11` |
| 16 | `B2` | `AB10` |
| 17 | `B1` | `AB9` |
| 18 | `B0` | `AB8` |
| 19 | `/OE` | `/AB_PC` |
| 20 | `VCC` | *VCC* (güç) |

### U317 · 74HC245

AB tamponu: AR alt → AB0–7. DIR = VCC (A→B), /OE = /AB_AR (#AS).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `AR0` |
| 3 | `A1` | `AR1` |
| 4 | `A2` | `AR2` |
| 5 | `A3` | `AR3` |
| 6 | `A4` | `AR4` |
| 7 | `A5` | `AR5` |
| 8 | `A6` | `AR6` |
| 9 | `A7` | `AR7` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `AB7` |
| 12 | `B6` | `AB6` |
| 13 | `B5` | `AB5` |
| 14 | `B4` | `AB4` |
| 15 | `B3` | `AB3` |
| 16 | `B2` | `AB2` |
| 17 | `B1` | `AB1` |
| 18 | `B0` | `AB0` |
| 19 | `/OE` | `/AB_AR` |
| 20 | `VCC` | *VCC* (güç) |

### U318 · 74HC245

AB tamponu: AR üst → AB8–15. DIR = VCC (A→B), /OE = /AB_AR (#AS).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `AR8` |
| 3 | `A1` | `AR9` |
| 4 | `A2` | `AR10` |
| 5 | `A3` | `AR11` |
| 6 | `A4` | `AR12` |
| 7 | `A5` | `AR13` |
| 8 | `A6` | `AR14` |
| 9 | `A7` | `AR15` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `AB15` |
| 12 | `B6` | `AB14` |
| 13 | `B5` | `AB13` |
| 14 | `B4` | `AB12` |
| 15 | `B3` | `AB11` |
| 16 | `B2` | `AB10` |
| 17 | `B1` | `AB9` |
| 18 | `B0` | `AB8` |
| 19 | `/OE` | `/AB_AR` |
| 20 | `VCC` | *VCC* (güç) |

### U319 · 74HC245

AB tamponu: X alt → AB0–7. DIR = VCC (A→B), /OE = /AB_X (#AS).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `X0` |
| 3 | `A1` | `X1` |
| 4 | `A2` | `X2` |
| 5 | `A3` | `X3` |
| 6 | `A4` | `X4` |
| 7 | `A5` | `X5` |
| 8 | `A6` | `X6` |
| 9 | `A7` | `X7` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `AB7` |
| 12 | `B6` | `AB6` |
| 13 | `B5` | `AB5` |
| 14 | `B4` | `AB4` |
| 15 | `B3` | `AB3` |
| 16 | `B2` | `AB2` |
| 17 | `B1` | `AB1` |
| 18 | `B0` | `AB0` |
| 19 | `/OE` | `/AB_X` |
| 20 | `VCC` | *VCC* (güç) |

### U320 · 74HC245

AB tamponu: X üst → AB8–15. DIR = VCC (A→B), /OE = /AB_X (#AS).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `X8` |
| 3 | `A1` | `X9` |
| 4 | `A2` | `X10` |
| 5 | `A3` | `X11` |
| 6 | `A4` | `X12` |
| 7 | `A5` | `X13` |
| 8 | `A6` | `X14` |
| 9 | `A7` | `X15` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `AB15` |
| 12 | `B6` | `AB14` |
| 13 | `B5` | `AB13` |
| 14 | `B4` | `AB12` |
| 15 | `B3` | `AB11` |
| 16 | `B2` | `AB10` |
| 17 | `B1` | `AB9` |
| 18 | `B0` | `AB8` |
| 19 | `/OE` | `/AB_X` |
| 20 | `VCC` | *VCC* (güç) |

### U321 · 74HC245

AB tamponu: SP → AB0–7. DIR = VCC (A→B), /OE = /AB_SP (#AS).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `SP0` |
| 3 | `A1` | `SP1` |
| 4 | `A2` | `SP2` |
| 5 | `A3` | `SP3` |
| 6 | `A4` | `SP4` |
| 7 | `A5` | `SP5` |
| 8 | `A6` | `SP6` |
| 9 | `A7` | `SP7` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `AB7` |
| 12 | `B6` | `AB6` |
| 13 | `B5` | `AB5` |
| 14 | `B4` | `AB4` |
| 15 | `B3` | `AB3` |
| 16 | `B2` | `AB2` |
| 17 | `B1` | `AB1` |
| 18 | `B0` | `AB0` |
| 19 | `/OE` | `/AB_SP` |
| 20 | `VCC` | *VCC* (güç) |

### U322 · 74HC245

AB tamponu: EF sabiti → AB8–15 (A girişleri EF = 1110 1111'e bağlı). DIR = VCC (A→B), /OE = /AB_SP (#AS).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `VCC` |
| 3 | `A1` | `VCC` |
| 4 | `A2` | `VCC` |
| 5 | `A3` | `VCC` |
| 6 | `A4` | `GND` |
| 7 | `A5` | `VCC` |
| 8 | `A6` | `VCC` |
| 9 | `A7` | `VCC` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `AB15` |
| 12 | `B6` | `AB14` |
| 13 | `B5` | `AB13` |
| 14 | `B4` | `AB12` |
| 15 | `B3` | `AB11` |
| 16 | `B2` | `AB10` |
| 17 | `B1` | `AB9` |
| 18 | `B0` | `AB8` |
| 19 | `/OE` | `/AB_SP` |
| 20 | `VCC` | *VCC* (güç) |

## M4 Veri ve ALU

### U401 · 74HC161

F (5.1): 4-bit register olarak 161, /PE = NOT FL (U211), CEP = CET = 0, /MR = /RESET_s → 0000. Q0..3 = Z C N V (uROM A12–15). TC boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/RESET_s` |
| 2 | `CP` | `CLK_AFI` |
| 3 | `D0` | `Znew` |
| 4 | `D1` | `Cnew` |
| 5 | `D2` | `Nnew` |
| 6 | `D3` | `Vnew` |
| 7 | `CEP` | `GND` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `/FL` |
| 10 | `CET` | `GND` |
| 11 | `Q3` | `V` |
| 12 | `Q2` | `N` |
| 13 | `Q1` | `C` |
| 14 | `Q0` | `Z` |
| 15 | `TC` | — (boş) |
| 16 | `VCC` | *VCC* (güç) |

### U402 · 74HC377

A (5.1): D = R, /E = /DD_A. Reset yok (açılışta belirsiz).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/E` | `/DD_A` |
| 2 | `Q0` | `ACC0` |
| 3 | `D0` | `R0` |
| 4 | `D1` | `R1` |
| 5 | `Q1` | `ACC1` |
| 6 | `Q2` | `ACC2` |
| 7 | `D2` | `R2` |
| 8 | `D3` | `R3` |
| 9 | `Q3` | `ACC3` |
| 10 | `GND` | *GND* (güç) |
| 11 | `CP` | `CLK_AFI` |
| 12 | `Q4` | `ACC4` |
| 13 | `D4` | `R4` |
| 14 | `D5` | `R5` |
| 15 | `Q5` | `ACC5` |
| 16 | `Q6` | `ACC6` |
| 17 | `D6` | `R6` |
| 18 | `D7` | `R7` |
| 19 | `Q7` | `ACC7` |
| 20 | `VCC` | *VCC* (güç) |

### U403 · 74HC377

IR (5.1): D = DB, /E = /DD_IR. Reset yok (0. adım her IR için FETCH).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/E` | `/DD_IR` |
| 2 | `Q0` | `IR0` |
| 3 | `D0` | `DB0` |
| 4 | `D1` | `DB1` |
| 5 | `Q1` | `IR1` |
| 6 | `Q2` | `IR2` |
| 7 | `D2` | `DB2` |
| 8 | `D3` | `DB3` |
| 9 | `Q3` | `IR3` |
| 10 | `GND` | *GND* (güç) |
| 11 | `CP` | `CLK_AFI` |
| 12 | `Q4` | `IR4` |
| 13 | `D4` | `DB4` |
| 14 | `D5` | `DB5` |
| 15 | `Q5` | `IR5` |
| 16 | `Q6` | `IR6` |
| 17 | `D6` | `DB6` |
| 18 | `D7` | `DB7` |
| 19 | `Q7` | `IR7` |
| 20 | `VCC` | *VCC* (güç) |

### U404 · 74HC245

A → DB (#DS Y2).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `ACC0` |
| 3 | `A1` | `ACC1` |
| 4 | `A2` | `ACC2` |
| 5 | `A3` | `ACC3` |
| 6 | `A4` | `ACC4` |
| 7 | `A5` | `ACC5` |
| 8 | `A6` | `ACC6` |
| 9 | `A7` | `ACC7` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `DB7` |
| 12 | `B6` | `DB6` |
| 13 | `B5` | `DB5` |
| 14 | `B4` | `DB4` |
| 15 | `B3` | `DB3` |
| 16 | `B2` | `DB2` |
| 17 | `B1` | `DB1` |
| 18 | `B0` | `DB0` |
| 19 | `/OE` | `/OE_A` |
| 20 | `VCC` | *VCC* (güç) |

### U405 · 74HC245

PCL → DB (#DS Y3).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `PC0` |
| 3 | `A1` | `PC1` |
| 4 | `A2` | `PC2` |
| 5 | `A3` | `PC3` |
| 6 | `A4` | `PC4` |
| 7 | `A5` | `PC5` |
| 8 | `A6` | `PC6` |
| 9 | `A7` | `PC7` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `DB7` |
| 12 | `B6` | `DB6` |
| 13 | `B5` | `DB5` |
| 14 | `B4` | `DB4` |
| 15 | `B3` | `DB3` |
| 16 | `B2` | `DB2` |
| 17 | `B1` | `DB1` |
| 18 | `B0` | `DB0` |
| 19 | `/OE` | `/OE_PCL` |
| 20 | `VCC` | *VCC* (güç) |

### U406 · 74HC245

PCH → DB (#DS Y4).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `PC8` |
| 3 | `A1` | `PC9` |
| 4 | `A2` | `PC10` |
| 5 | `A3` | `PC11` |
| 6 | `A4` | `PC12` |
| 7 | `A5` | `PC13` |
| 8 | `A6` | `PC14` |
| 9 | `A7` | `PC15` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `DB7` |
| 12 | `B6` | `DB6` |
| 13 | `B5` | `DB5` |
| 14 | `B4` | `DB4` |
| 15 | `B3` | `DB3` |
| 16 | `B2` | `DB2` |
| 17 | `B1` | `DB1` |
| 18 | `B0` | `DB0` |
| 19 | `/OE` | `/OE_PCH` |
| 20 | `VCC` | *VCC* (güç) |

### U407 · SST39SF010

ALU-L (5.2): A0–3 = A[3:0], A4–7 = DB[3:0], A8 = C, A9 = A4, A10–14 = ALUOP, A15 = A7, A16 = tablo jumper'ı (GND). D0–3 = R0–3, D4 = c4, D5 = Zlo, D6 = Clo, D7 boş. Hep etkin. -70.

| Bacak | Pin | Net |
|---:|---|---|
| 2 | `A16` | `GND` |
| 3 | `A15` | `ACC7` |
| 4 | `A12` | `ALUOP2_L` |
| 5 | `A7` | `DB3` |
| 6 | `A6` | `DB2` |
| 7 | `A5` | `DB1` |
| 8 | `A4` | `DB0` |
| 9 | `A3` | `ACC3` |
| 10 | `A2` | `ACC2` |
| 11 | `A1` | `ACC1` |
| 12 | `A0` | `ACC0` |
| 13 | `DQ0` | `R0` |
| 14 | `DQ1` | `R1` |
| 15 | `DQ2` | `R2` |
| 16 | `GND` | *GND* (güç) |
| 17 | `DQ3` | `R3` |
| 18 | `DQ4` | `c4` |
| 19 | `DQ5` | `Zlo` |
| 20 | `DQ6` | `Clo` |
| 21 | `DQ7` | — (boş) |
| 22 | `/CE` | `GND` |
| 23 | `A10` | `ALUOP0_L` |
| 24 | `/OE` | `GND` |
| 25 | `A11` | `ALUOP1_L` |
| 26 | `A9` | `ACC4` |
| 27 | `A8` | `C` |
| 28 | `A13` | `ALUOP3_L` |
| 29 | `A14` | `ALUOP4_L` |
| 31 | `/WE` | `VCC` |
| 32 | `VCC` | *VCC* (güç) |

### U408 · SST39SF010

ALU-H (5.2): A0–3 = A[7:4], A4–7 = DB[7:4], A8 = c4, A9 = Zlo, A10 = Z, A11–15 = ALUOP, A16 = GND. D0–3 = R4–7, D4 = Z, D5 = Chi, D6 = N, D7 = V. -70.

| Bacak | Pin | Net |
|---:|---|---|
| 2 | `A16` | `GND` |
| 3 | `A15` | `ALUOP4_L` |
| 4 | `A12` | `ALUOP1_L` |
| 5 | `A7` | `DB7` |
| 6 | `A6` | `DB6` |
| 7 | `A5` | `DB5` |
| 8 | `A4` | `DB4` |
| 9 | `A3` | `ACC7` |
| 10 | `A2` | `ACC6` |
| 11 | `A1` | `ACC5` |
| 12 | `A0` | `ACC4` |
| 13 | `DQ0` | `R4` |
| 14 | `DQ1` | `R5` |
| 15 | `DQ2` | `R6` |
| 16 | `GND` | *GND* (güç) |
| 17 | `DQ3` | `R7` |
| 18 | `DQ4` | `Znew` |
| 19 | `DQ5` | `Chi` |
| 20 | `DQ6` | `Nnew` |
| 21 | `DQ7` | `Vnew` |
| 22 | `/CE` | `GND` |
| 23 | `A10` | `Z` |
| 24 | `/OE` | `GND` |
| 25 | `A11` | `ALUOP0_L` |
| 26 | `A9` | `Zlo` |
| 27 | `A8` | `c4` |
| 28 | `A13` | `ALUOP2_L` |
| 29 | `A14` | `ALUOP3_L` |
| 31 | `/WE` | `VCC` |
| 32 | `VCC` | *VCC* (güç) |

## CPU yardımcı kapıları

### U501 · 74HC00

SP üst /CE = NAND(SPCNT, MAX/MIN_alt) (5.1); RAM /CE = NAND(A15, /FPAGE) (7.2); /MWR = NAND(MEMW_L, WSTB) (7.2). 4. kapı boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `1A` | `SPCNT_L` |
| 2 | `1B` | `SP_MM0` |
| 3 | `1Y` | `/SPCNT_HI` |
| 4 | `2A` | `AB15` |
| 5 | `2B` | `/FPAGE` |
| 6 | `2Y` | `/RAM_CE` |
| 7 | `GND` | *GND* (güç) |
| 8 | `3Y` | `/MWR` |
| 9 | `3A` | `MEMW_L` |
| 10 | `3B` | `WSTB` |
| 11 | `4Y` | — (boş) |
| 12 | `4A` | `GND` |
| 13 | `4B` | `GND` |
| 14 | `VCC` | *VCC* (güç) |

### U502 · 74HC08

/RD = AND(/MRD, /ARD_RD), /WR = AND(/MWR, /ARD_WR) (2). 3. kapı /ACCESS = AND(/MRD, /MEMW): bu çevrim belleği okuyor ya da yazıyor (breakpoint, 10). 4. boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `1A` | `/MRD` |
| 2 | `1B` | `/ARD_RD` |
| 3 | `1Y` | `/RD` |
| 4 | `2A` | `/MWR` |
| 5 | `2B` | `/ARD_WR` |
| 6 | `2Y` | `/WR` |
| 7 | `GND` | *GND* (güç) |
| 8 | `3Y` | `/ACCESS` |
| 9 | `3A` | `/MRD` |
| 10 | `3B` | `/MEMW` |
| 11 | `4Y` | — (boş) |
| 12 | `4A` | `GND` |
| 13 | `4B` | `GND` |
| 14 | `VCC` | *VCC* (güç) |

### U503 · 74HC32

C = OR(Clo, Chi) (5.2); /LED_E = OR(/IOSEL, /MEMW) (7.2); VRAM /WE = OR(/WR, /VRAMSEL) (7.2; VRAM M6'da, burada taklit X1); STOP'un son OR'u BRQ_s | (…) (3.3).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `1A` | `Clo` |
| 2 | `1B` | `Chi` |
| 3 | `1Y` | `Cnew` |
| 4 | `2A` | `/IOSEL` |
| 5 | `2B` | `/MEMW` |
| 6 | `2Y` | `/LED_E` |
| 7 | `GND` | *GND* (güç) |
| 8 | `3Y` | `/VRAM_WE` |
| 9 | `3A` | `/WR` |
| 10 | `3B` | `/VRAMSEL` |
| 11 | `4Y` | `STOP` |
| 12 | `4A` | `BRQ_s` |
| 13 | `4B` | `STOP_G` |
| 14 | `VCC` | *VCC* (güç) |

## M5 Bellek + I/O

### U601 · SST39SF010

Program ROM (7.1): A0–14 = AB, A15/A16 = bank jumper'ları (GND: bank 0), /CE = A15 (doğrudan kablo), /OE = /RD, /WE = VCC. -90 (DOGRULAMA 2b: -90 eski stok program ROM'una).

| Bacak | Pin | Net |
|---:|---|---|
| 2 | `A16` | `GND` |
| 3 | `A15` | `GND` |
| 4 | `A12` | `AB12` |
| 5 | `A7` | `AB7` |
| 6 | `A6` | `AB6` |
| 7 | `A5` | `AB5` |
| 8 | `A4` | `AB4` |
| 9 | `A3` | `AB3` |
| 10 | `A2` | `AB2` |
| 11 | `A1` | `AB1` |
| 12 | `A0` | `AB0` |
| 13 | `DQ0` | `DB0` |
| 14 | `DQ1` | `DB1` |
| 15 | `DQ2` | `DB2` |
| 16 | `GND` | *GND* (güç) |
| 17 | `DQ3` | `DB3` |
| 18 | `DQ4` | `DB4` |
| 19 | `DQ5` | `DB5` |
| 20 | `DQ6` | `DB6` |
| 21 | `DQ7` | `DB7` |
| 22 | `/CE` | `AB15` |
| 23 | `A10` | `AB10` |
| 24 | `/OE` | `/RD` |
| 25 | `A11` | `AB11` |
| 26 | `A9` | `AB9` |
| 27 | `A8` | `AB8` |
| 28 | `A13` | `AB13` |
| 29 | `A14` | `AB14` |
| 31 | `/WE` | `VCC` |
| 32 | `VCC` | *VCC* (güç) |

### U602 · CY62256

RAM CY62256-70 (7.1): 8000–EFFF. /CE = NAND(A15, /FPAGE) (U501), /OE = /RD, /WE = /WR.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `A14` | `AB14` |
| 2 | `A12` | `AB12` |
| 3 | `A7` | `AB7` |
| 4 | `A6` | `AB6` |
| 5 | `A5` | `AB5` |
| 6 | `A4` | `AB4` |
| 7 | `A3` | `AB3` |
| 8 | `A2` | `AB2` |
| 9 | `A1` | `AB1` |
| 10 | `A0` | `AB0` |
| 11 | `IO0` | `DB0` |
| 12 | `IO1` | `DB1` |
| 13 | `IO2` | `DB2` |
| 14 | `GND` | *GND* (güç) |
| 15 | `IO3` | `DB3` |
| 16 | `IO4` | `DB4` |
| 17 | `IO5` | `DB5` |
| 18 | `IO6` | `DB6` |
| 19 | `IO7` | `DB7` |
| 20 | `/CE` | `/RAM_CE` |
| 21 | `A10` | `AB10` |
| 22 | `/OE` | `/RD` |
| 23 | `A11` | `AB11` |
| 24 | `A9` | `AB9` |
| 25 | `A8` | `AB8` |
| 26 | `A13` | `AB13` |
| 27 | `/WE` | `/WR` |
| 28 | `VCC` | *VCC* (güç) |

### U603 · 74HC20

/FPAGE = NAND4(A15..A12) (7.2). 2. kapı boş (girişleri GND).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `1A` | `AB15` |
| 2 | `1B` | `AB14` |
| 4 | `1C` | `AB13` |
| 5 | `1D` | `AB12` |
| 6 | `1Y` | `/FPAGE` |
| 7 | `GND` | *GND* (güç) |
| 8 | `2Y` | — (boş) |
| 9 | `2A` | `GND` |
| 10 | `2B` | `GND` |
| 12 | `2C` | `GND` |
| 13 | `2D` | `GND` |
| 14 | `VCC` | *VCC* (güç) |

### U604 · 74HC138

#IOR (7.2): A0..A2, G1 = VCC (ISA-v0-sentez 6.1), /G2A = /IOSEL, /G2B = /RD. Y0 /KBD_RD (F800), Y1 /STAT_RD (F801), Y2–Y7 ayrılmış (boş).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `A0` | `AB0` |
| 2 | `A1` | `AB1` |
| 3 | `A2` | `AB2` |
| 4 | `/E1` | `/IOSEL` |
| 5 | `/E2` | `/RD` |
| 6 | `E3` | `VCC` |
| 7 | `/Y7` | — (boş) |
| 8 | `GND` | *GND* (güç) |
| 9 | `/Y6` | — (boş) |
| 10 | `/Y5` | — (boş) |
| 11 | `/Y4` | — (boş) |
| 12 | `/Y3` | — (boş) |
| 13 | `/Y2` | — (boş) |
| 14 | `/Y1` | `/STAT_RD` |
| 15 | `/Y0` | `/KBD_RD` |
| 16 | `VCC` | *VCC* (güç) |

### U605 · 74HC377

LED portu (7.3): /E = OR(/IOSEL, /MEMW) commit'te örneklenir, CP = CLK (LED dalı). F800–FFFF'e her yazma buraya.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/E` | `/LED_E` |
| 2 | `Q0` | `LED0` |
| 3 | `D0` | `DB0` |
| 4 | `D1` | `DB1` |
| 5 | `Q1` | `LED1` |
| 6 | `Q2` | `LED2` |
| 7 | `D2` | `DB2` |
| 8 | `D3` | `DB3` |
| 9 | `Q3` | `LED3` |
| 10 | `GND` | *GND* (güç) |
| 11 | `CP` | `CLK_IO` |
| 12 | `Q4` | `LED4` |
| 13 | `D4` | `DB4` |
| 14 | `D5` | `DB5` |
| 15 | `Q5` | `LED5` |
| 16 | `Q6` | `LED6` |
| 17 | `D6` | `DB6` |
| 18 | `D7` | `DB7` |
| 19 | `Q7` | `LED7` |
| 20 | `VCC` | *VCC* (güç) |

### U606 · 74HC245

KSTAT (7.3): b7 = KRDY, b6 = VWR_s, b5..b0 = DIP SW5..SW0 → DB, /OE = /STAT_RD. DIP: anahtar + pull-up/down (burada test tezgâhı girişi).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `DIR` | `VCC` |
| 2 | `A0` | `DIP0` |
| 3 | `A1` | `DIP1` |
| 4 | `A2` | `DIP2` |
| 5 | `A3` | `DIP3` |
| 6 | `A4` | `DIP4` |
| 7 | `A5` | `DIP5` |
| 8 | `A6` | `VWR_s` |
| 9 | `A7` | `KRDY` |
| 10 | `GND` | *GND* (güç) |
| 11 | `B7` | `DB7` |
| 12 | `B6` | `DB6` |
| 13 | `B5` | `DB5` |
| 14 | `B4` | `DB4` |
| 15 | `B3` | `DB3` |
| 16 | `B2` | `DB2` |
| 17 | `B1` | `DB1` |
| 18 | `B0` | `DB0` |
| 19 | `/OE` | `/STAT_RD` |
| 20 | `VCC` | *VCC* (güç) |

## M6 VGA zamanlaması

### U701 · 74HC74

FF1: 25 MHz ÷ 2 → DCLK 12.5 MHz (8.1). FF2: LD flip-flop'u, D = NAND4(Q2, Q1, Q0, 1); LD = /Q yalnız noktanın 0. periyodunda 1, CCLK = Q = /LD.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/1RD` | `VCC` |
| 2 | `1D` | `/DCLK` |
| 3 | `1CP` | `OSC25` |
| 4 | `/1SD` | `VCC` |
| 5 | `1Q` | `DCLK` |
| 6 | `/1Q` | `/DCLK` |
| 7 | `GND` | *GND* (güç) |
| 8 | `/2Q` | `LD` |
| 9 | `2Q` | `CCLK` |
| 10 | `/2SD` | `VCC` |
| 11 | `2CP` | `DCLK` |
| 12 | `2D` | `LD_D` |
| 13 | `/2RD` | `VCC` |
| 14 | `VCC` | *VCC* (güç) |

### U702 · 74HC163

Nokta sayacı (8.1): DCLK ile sayar; karakter = 8 nokta (Q0–Q2, mod 8). Q3 kullanılmaz.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `VCC` |
| 2 | `CP` | `DCLK` |
| 3 | `D0` | `GND` |
| 4 | `D1` | `GND` |
| 5 | `D2` | `GND` |
| 6 | `D3` | `GND` |
| 7 | `CEP` | `VCC` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `VCC` |
| 10 | `CET` | `VCC` |
| 11 | `Q3` | `DOT3` |
| 12 | `Q2` | `DOT2` |
| 13 | `Q1` | `DOT1` |
| 14 | `Q0` | `DOT0` |
| 15 | `TC` | — (boş) |
| 16 | `VCC` | *VCC* (güç) |

### U703 · 74HC20

LD_D = NAND4(DOT2, DOT1, DOT0, 1): nokta 7'de 0. 2. kapı boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `1A` | `DOT2` |
| 2 | `1B` | `DOT1` |
| 4 | `1C` | `DOT0` |
| 5 | `1D` | `VCC` |
| 6 | `1Y` | `LD_D` |
| 7 | `GND` | *GND* (güç) |
| 8 | `2Y` | — (boş) |
| 9 | `2A` | `GND` |
| 10 | `2B` | `GND` |
| 12 | `2C` | `GND` |
| 13 | `2D` | `GND` |
| 14 | `VCC` | *VCC* (güç) |

### U704 · 74HC163

HCHAR alt 4 bit (8.2). /MR senkron temizleme = /HEND (ROM D4): H = 49'dan sonra 0.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/HEND` |
| 2 | `CP` | `CCLK` |
| 3 | `D0` | `GND` |
| 4 | `D1` | `GND` |
| 5 | `D2` | `GND` |
| 6 | `D3` | `GND` |
| 7 | `CEP` | `VCC` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `VCC` |
| 10 | `CET` | `VCC` |
| 11 | `Q3` | `H3` |
| 12 | `Q2` | `H2` |
| 13 | `Q1` | `H1` |
| 14 | `Q0` | `H0` |
| 15 | `TC` | `H_TC` |
| 16 | `VCC` | *VCC* (güç) |

### U705 · 74HC163

HCHAR üst 2 bit (H4, H5); Q2, Q3 kullanılmaz.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/HEND` |
| 2 | `CP` | `CCLK` |
| 3 | `D0` | `GND` |
| 4 | `D1` | `GND` |
| 5 | `D2` | `GND` |
| 6 | `D3` | `GND` |
| 7 | `CEP` | `VCC` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `VCC` |
| 10 | `CET` | `H_TC` |
| 11 | `Q3` | `H7` |
| 12 | `Q2` | `H6` |
| 13 | `Q1` | `H5` |
| 14 | `Q0` | `H4` |
| 15 | `TC` | — (boş) |
| 16 | `VCC` | *VCC* (güç) |

### U706 · 74HC04

HEND = NOT /HEND: VLINE satır sonunda bir artar. 2–6. kapı boş.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `1A` | `/HEND` |
| 2 | `1Y` | `HEND` |
| 3 | `2A` | `GND` |
| 4 | `2Y` | — (boş) |
| 5 | `3A` | `GND` |
| 6 | `3Y` | — (boş) |
| 7 | `GND` | *GND* (güç) |
| 8 | `4Y` | — (boş) |
| 9 | `4A` | `GND` |
| 10 | `5Y` | — (boş) |
| 11 | `5A` | `GND` |
| 12 | `6Y` | — (boş) |
| 13 | `6A` | `GND` |
| 14 | `VCC` | *VCC* (güç) |

### U707 · 74HC163

VLINE bit 0–3 (8.2): yalnız HEND = 1 iken (satır sonu) sayar. /MR = /VEND (ROM D5).

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/VEND` |
| 2 | `CP` | `CCLK` |
| 3 | `D0` | `GND` |
| 4 | `D1` | `GND` |
| 5 | `D2` | `GND` |
| 6 | `D3` | `GND` |
| 7 | `CEP` | `HEND` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `VCC` |
| 10 | `CET` | `HEND` |
| 11 | `Q3` | `V3` |
| 12 | `Q2` | `V2` |
| 13 | `Q1` | `V1` |
| 14 | `Q0` | `V0` |
| 15 | `TC` | `V_TC1` |
| 16 | `VCC` | *VCC* (güç) |

### U708 · 74HC163

VLINE bit 4–7.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/VEND` |
| 2 | `CP` | `CCLK` |
| 3 | `D0` | `GND` |
| 4 | `D1` | `GND` |
| 5 | `D2` | `GND` |
| 6 | `D3` | `GND` |
| 7 | `CEP` | `HEND` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `VCC` |
| 10 | `CET` | `V_TC1` |
| 11 | `Q3` | `V7` |
| 12 | `Q2` | `V6` |
| 13 | `Q1` | `V5` |
| 14 | `Q0` | `V4` |
| 15 | `TC` | `V_TC2` |
| 16 | `VCC` | *VCC* (güç) |

### U709 · 74HC163

VLINE bit 8–9; Q2, Q3 kullanılmaz.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/MR` | `/VEND` |
| 2 | `CP` | `CCLK` |
| 3 | `D0` | `GND` |
| 4 | `D1` | `GND` |
| 5 | `D2` | `GND` |
| 6 | `D3` | `GND` |
| 7 | `CEP` | `HEND` |
| 8 | `GND` | *GND* (güç) |
| 9 | `/PE` | `VCC` |
| 10 | `CET` | `V_TC2` |
| 11 | `Q3` | `V11` |
| 12 | `Q2` | `V10` |
| 13 | `Q1` | `V9` |
| 14 | `Q0` | `V8` |
| 15 | `TC` | — (boş) |
| 16 | `VCC` | *VCC* (güç) |

### U710 · SST39SF010

Zamanlama ROM'u (8.2): A0–5 = H, A6–15 = V, A16 = SLOW. İçerik ta8.vga.timing_rom().

| Bacak | Pin | Net |
|---:|---|---|
| 2 | `A16` | `SLOW` |
| 3 | `A15` | `V9` |
| 4 | `A12` | `V6` |
| 5 | `A7` | `V1` |
| 6 | `A6` | `V0` |
| 7 | `A5` | `H5` |
| 8 | `A4` | `H4` |
| 9 | `A3` | `H3` |
| 10 | `A2` | `H2` |
| 11 | `A1` | `H1` |
| 12 | `A0` | `H0` |
| 13 | `DQ0` | `R_HSYNC_n` |
| 14 | `DQ1` | `R_VSYNC_n` |
| 15 | `DQ2` | `R_BLANK_n` |
| 16 | `GND` | *GND* (güç) |
| 17 | `DQ3` | `R_BUFEN_n` |
| 18 | `DQ4` | `/HEND` |
| 19 | `DQ5` | `/VEND` |
| 20 | `DQ6` | `R_VMUX` |
| 21 | `DQ7` | `R_VWR` |
| 22 | `/CE` | `GND` |
| 23 | `A10` | `V4` |
| 24 | `/OE` | `GND` |
| 25 | `A11` | `V5` |
| 26 | `A9` | `V3` |
| 27 | `A8` | `V2` |
| 28 | `A13` | `V7` |
| 29 | `A14` | `V8` |
| 31 | `/WE` | `VCC` |
| 32 | `VCC` | *VCC* (güç) |

### U711 · 74HC377

T1 registerı (8.2): /E = /LD = CCLK, CP = DCLK; ROM çıkışlarını karakter sınırında yakalar, böylece sync/blank kayan glyph ile aynı hizada çıkar (8.3). Q7 = VWR → M1 U111 senkronlayıcısı → VWR_s.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/E` | `CCLK` |
| 2 | `Q0` | `/HSYNC` |
| 3 | `D0` | `R_HSYNC_n` |
| 4 | `D1` | `R_VSYNC_n` |
| 5 | `Q1` | `/VSYNC` |
| 6 | `Q2` | `BLANK_n` |
| 7 | `D2` | `R_BLANK_n` |
| 8 | `D3` | `R_BUFEN_n` |
| 9 | `Q3` | `/BUFEN` |
| 10 | `GND` | *GND* (güç) |
| 11 | `CP` | `DCLK` |
| 12 | `Q4` | `T1_HEND_n` |
| 13 | `D4` | `/HEND` |
| 14 | `D5` | `/VEND` |
| 15 | `Q5` | `T1_VEND_n` |
| 16 | `Q6` | `VMUX` |
| 17 | `D6` | `R_VMUX` |
| 18 | `D7` | `R_VWR` |
| 19 | `Q7` | `VWR` |
| 20 | `VCC` | *VCC* (güç) |

## Test tezgâhı taklitleri (M6/M7 yerine; entegre sayımına girmez)

### X1 · CY62256

VRAM taklidi (M6 yok): yalnız yazılır. A0–10 = AB0–10, /WE = OR(/WR, /VRAMSEL) (U503), /OE = VCC. Gerçekte veri DB → 74HC245 (/OE = /BUFEN) üzerinden, adres 3× 74HC157 üzerinden gelir; burada doğrudan DB/AB.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `A14` | `GND` |
| 2 | `A12` | `GND` |
| 3 | `A7` | `AB7` |
| 4 | `A6` | `AB6` |
| 5 | `A5` | `AB5` |
| 6 | `A4` | `AB4` |
| 7 | `A3` | `AB3` |
| 8 | `A2` | `AB2` |
| 9 | `A1` | `AB1` |
| 10 | `A0` | `AB0` |
| 11 | `IO0` | `DB0` |
| 12 | `IO1` | `DB1` |
| 13 | `IO2` | `DB2` |
| 14 | `GND` | *GND* (güç) |
| 15 | `IO3` | `DB3` |
| 16 | `IO4` | `DB4` |
| 17 | `IO5` | `DB5` |
| 18 | `IO6` | `DB6` |
| 19 | `IO7` | `DB7` |
| 20 | `/CE` | `GND` |
| 21 | `A10` | `AB10` |
| 22 | `/OE` | `VCC` |
| 23 | `A11` | `GND` |
| 24 | `A9` | `AB9` |
| 25 | `A8` | `AB8` |
| 26 | `A13` | `GND` |
| 27 | `/WE` | `/VRAM_WE` |
| 28 | `VCC` | *VCC* (güç) |

### X2 · 74HC540

Klavye okuma tamponu taklidi (M7'nin 74HC540'ı, /OE1 = /KBD_RD): KSR0..7 = kaydırma registerının terslenmiş veri bitleri (test tezgâhı; boşken 00 → DB'de FF, bus.py ile aynı). KRDY de test tezgâhından; okuma sonrası temizleme (KCLR) test tezgâhında modellenir.

| Bacak | Pin | Net |
|---:|---|---|
| 1 | `/OE1` | `/KBD_RD` |
| 2 | `A0` | `KSR0` |
| 3 | `A1` | `KSR1` |
| 4 | `A2` | `KSR2` |
| 5 | `A3` | `KSR3` |
| 6 | `A4` | `KSR4` |
| 7 | `A5` | `KSR5` |
| 8 | `A6` | `KSR6` |
| 9 | `A7` | `KSR7` |
| 10 | `GND` | *GND* (güç) |
| 11 | `/Y7` | `DB7` |
| 12 | `/Y6` | `DB6` |
| 13 | `/Y5` | `DB5` |
| 14 | `/Y4` | `DB4` |
| 15 | `/Y3` | `DB3` |
| 16 | `/Y2` | `DB2` |
| 17 | `/Y1` | `DB1` |
| 18 | `/Y0` | `DB0` |
| 19 | `/OE2` | `GND` |
| 20 | `VCC` | *VCC* (güç) |

## Pull direnci, sabitler ve test tezgâhı girişleri

| Net | Tür | Değer |
|---|---|---|
| `AB0` | pull (10k yukarı) | 1 |
| `AB1` | pull (10k yukarı) | 1 |
| `AB2` | pull (10k yukarı) | 1 |
| `AB3` | pull (10k yukarı) | 1 |
| `AB4` | pull (10k yukarı) | 1 |
| `AB5` | pull (10k yukarı) | 1 |
| `AB6` | pull (10k yukarı) | 1 |
| `AB7` | pull (10k yukarı) | 1 |
| `AB8` | pull (10k yukarı) | 1 |
| `AB9` | pull (10k yukarı) | 1 |
| `AB10` | pull (10k yukarı) | 1 |
| `AB11` | pull (10k yukarı) | 1 |
| `AB12` | pull (10k yukarı) | 1 |
| `AB13` | pull (10k yukarı) | 1 |
| `AB14` | pull (10k yukarı) | 1 |
| `AB15` | pull (10k yukarı) | 1 |
| `DB0` | pull (10k aşağı) | 0 |
| `DB1` | pull (10k aşağı) | 0 |
| `DB2` | pull (10k aşağı) | 0 |
| `DB3` | pull (10k aşağı) | 0 |
| `DB4` | pull (10k aşağı) | 0 |
| `DB5` | pull (10k aşağı) | 0 |
| `DB6` | pull (10k aşağı) | 0 |
| `DB7` | pull (10k aşağı) | 0 |
| `/ARD_RD` | pull (10k yukarı) | 1 |
| `/ARD_WR` | pull (10k yukarı) | 1 |
| `/BUSREQ` | pull (10k yukarı) | 1 |
| `MANUAL` | sabit (5. hafta, pasif değer) | 0 |
| `/RESET` | test tezgâhı girişi | varsayılan 1 |
| `GO_BTN` | test tezgâhı girişi | varsayılan 0 |
| `STEPMODE` | test tezgâhı girişi | varsayılan 0 |
| `MICRO` | test tezgâhı girişi | varsayılan 0 |
| `/BP_EN` | test tezgâhı girişi | varsayılan 1 |
| `BP0` | test tezgâhı girişi | varsayılan 0 |
| `BP1` | test tezgâhı girişi | varsayılan 0 |
| `BP2` | test tezgâhı girişi | varsayılan 0 |
| `BP3` | test tezgâhı girişi | varsayılan 0 |
| `BP4` | test tezgâhı girişi | varsayılan 0 |
| `BP5` | test tezgâhı girişi | varsayılan 0 |
| `BP6` | test tezgâhı girişi | varsayılan 0 |
| `BP7` | test tezgâhı girişi | varsayılan 0 |
| `BP8` | test tezgâhı girişi | varsayılan 0 |
| `BP9` | test tezgâhı girişi | varsayılan 0 |
| `BP10` | test tezgâhı girişi | varsayılan 0 |
| `BP11` | test tezgâhı girişi | varsayılan 0 |
| `BP12` | test tezgâhı girişi | varsayılan 0 |
| `BP13` | test tezgâhı girişi | varsayılan 0 |
| `BP14` | test tezgâhı girişi | varsayılan 0 |
| `BP15` | test tezgâhı girişi | varsayılan 0 |
| `DIP0` | test tezgâhı girişi | varsayılan 0 |
| `DIP1` | test tezgâhı girişi | varsayılan 0 |
| `DIP2` | test tezgâhı girişi | varsayılan 0 |
| `DIP3` | test tezgâhı girişi | varsayılan 0 |
| `DIP4` | test tezgâhı girişi | varsayılan 0 |
| `DIP5` | test tezgâhı girişi | varsayılan 0 |
| `SLOW` | test tezgâhı girişi | varsayılan 0 |
| `KRDY` | test tezgâhı girişi | varsayılan 0 |
| `KSR0` | test tezgâhı girişi | varsayılan 0 |
| `KSR1` | test tezgâhı girişi | varsayılan 0 |
| `KSR2` | test tezgâhı girişi | varsayılan 0 |
| `KSR3` | test tezgâhı girişi | varsayılan 0 |
| `KSR4` | test tezgâhı girişi | varsayılan 0 |
| `KSR5` | test tezgâhı girişi | varsayılan 0 |
| `KSR6` | test tezgâhı girişi | varsayılan 0 |
| `KSR7` | test tezgâhı girişi | varsayılan 0 |
| `MCLK` | saat | yarım periyot 125 ns |
| `OSC25` | saat | yarım periyot 20 ns |

## Notlar

- M1 kapsam dışı: NE555, 74HC153 (kaynak seçici; MCLK doğrudan test tezgâhından), 74HC14 (RC/debounce).
- M2 kapsam dışı: MANUAL paneli yok: MANUAL = 0 (uROM /OE açık); 24 latch girişindeki 47k pull-down'lar ve DB DIP anahtarları da panelle birlikte.
- AB: 16× 10k pull-up (boşta FFFF).
- DB: 8× 10k pull-down (boşta 00).
- Planda yardımcı 74HC00 ×2. 138'li WAIT çözümüyle (DOGRULAMA 2.5) NAND(MEMW_L, /VWR_s) kapısı kalktı ve Johnson 3 NAND + 1 OR oldu; 12 NAND'ın 7'si kullanılıyor (M1 U103: 4, U501: 3). 2. yardımcı 74HC00 gereksiz, netlist'te yok.
- /ARD_RD, /ARD_WR, /BUSREQ: Arduino takılı değilken 10k pull-up. /BUSREQ açık-drain (Arduino yalnız 0 sürer ya da bırakır).
- M6 kapsam dışı (sırada, 8.3–8.4): VRAM adres seçimi (3× 74HC157), VRAM (CY62256; şimdilik TB X1), font ROM'u, 74HC166, DB tamponu 74HC245 (/BUFEN), çıkış katı (74HC08, dirençler). SLOW test tezgâhından (gerçekte saat seçici).
- VWR_s M1'deki U111'de VWR'den (M6) senkronlanıyor (vga='netlist').
