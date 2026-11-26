# TA-8 malzeme listesi (BOM), eksiksiz

Hazırlayan: Abdurrahman · hafta 5.1 (24–30 Kasım 2026)

Kaynak: [SISTEM-PLANI bölüm 15.1](../../SISTEM-PLANI.md) (92 entegre), netlist ile karşılaştırıldı (`sim/ta8/hw/cpu.py`: M1–M5 aynı; M1'in NE555, 74HC153, 74HC14'ü MANUAL paneliyle gelecek) ve `Abdurrahman/hafta5/m6_uret.py` (M6 zamanlaması, 11 entegre, aynı).

**Sipariş planı:**
- Entegreler, osilatörler, pasifler, konnektörler: **LCSC, tek paket, Arabistan'a**.
- Breadboard, kablo, jumper: Türkiye (ağır ve ucuz).
- Arduino Mega, lojik analizör, ZIF, PLCC adaptör: AliExpress.
- PS/2 klavye: Trendyol.

LCSC dosyası: [`BOM-lcsc.csv`](BOM-lcsc.csv). LCSC → *Upload a BOM* ile yüklenince güncel stok ve fiyat tek seferde görünür.

**Yedek kuralı:** pahalı/az bulunan +%20; ucuz kapılar +2; tekli çiplerde +1.

---

## 1. Entegreler (LCSC)

| Parça | Modüller | Gerekli | Sipariş | Not |
|---|---|---|---|---|
| 74HC161 | M2 1, M3 12, M4 1 | 14 | 17 | |
| 74HC245 | M1 1, M3 8, M4 3, M5 1, M6 1 | 14 | 17 | |
| SST39SF010A flash | M2 3, M4 2, M5 1, M6 2 | 8 | 10 | **DIP stokta yok.** PLCC-32 alınır + PLCC32→DIP32 adaptör (bölüm 5) |
| 74HC163 | M6 6 | 6 | 8 | |
| 74HC74 | M1 3, M6 1, M7 1 | 5 | 7 | |
| 74AC74 | M6 (÷2 yedeği) | 0 | 3 | 74HC74'ün 25 MHz riski için; prototip c'de ölçülecek |
| 74HC377 | M4 2, M5 1, M6 1 | 4 | 5 | |
| 74HC138 | M1 1, M2 2, M5 1 | 4 | 5 | |
| 74HC08 | M1, AUX, M6, M7 | 4 | 6 | |
| 74HC157 | M6 3 | 3 | 4 | |
| 74HC273 | M2 3 | 3 | 4 | |
| 74HC00 | M1 1, AUX 2 | 3 | 5 | |
| 62256 SRAM (AS6C62256 / CY62256, DIP-28) | M5 RAM, M6 VRAM | 2 | 3 | |
| 74HC14 | M1, M7 | 2 | 3 | |
| 74HC20 | M5, M6 | 2 | 3 | |
| 74HC688 (74HCT688 de olur) | M2 breakpoint | 2 | 3 | |
| 74HC191 | M3 SP | 2 | 3 | |
| 74HC164 | M7 | 2 | 3 | |
| 74HC175 | M1 | 2 | 3 | |
| 74HC04 | M2, M6 | 2 | 3 | |
| 74HC32 | M1, AUX | 2 | 3 | |
| 74HC139 | M2 | 1 | 2 | |
| 74HC166 | M6 | 1 | 2 | |
| 74HC540 | M7 | 1 | 2 | |
| 74HC153 | M1 saat seçici | 1 | 2 | |
| 74HC02 | M1 | 1 | 2 | |
| NE555 | M1 yavaş saat | 1 | 2 | |
| TLC555 (CMOS) | M1 yedeği | 0 | 1 | |
| **Toplam** | | **92** | **131** | |

## 2. Osilatörler ve yarı iletkenler (LCSC)

| Parça | Gerekli | Sipariş | Not |
|---|---|---|---|
| 25.000 MHz osilatör, DIP-14/8 tam kılıf, 5 V | 1 | 2 | M6 nokta saati |
| 4.000 MHz osilatör, DIP-14/8, 5 V | 1 | 2 | M1 MCLK |
| 2N7000 | 1 | 3 | M7 susturma |
| 1N4148 | 3 | 10 | M7 |

## 3. Pasifler (LCSC)

| Parça | Gerekli (yaklaşık) | Sipariş | Nerede |
|---|---|---|---|
| 100 nF seramik, 2.54 mm bacak | 92 (çip başına 1) | 150 | Her entegre |
| 10 µF elektrolitik | 24 (kart başına 1) | 30 | Ray besleme |
| 100 µF elektrolitik | 3 | 5 | Güç girişi |
| 10 nF seramik | 1 | 5 | M7 zaman aşımı |
| 470 Ω | ~170 | 250 | LED'ler (~110), Arduino seri (~58), VGA RGB (3) |
| 10 kΩ SIP dizisi (9 bacak, 8 direnç) | 4 | 6 | AB/DB pull'ları |
| 10 kΩ | ~20 | 50 | Genel pull-up |
| 4.7 kΩ | ~30 | 50 | MANUAL paneli 24, PS/2 2 |
| 47 kΩ | 24 | 30 | MANUAL paneli |
| 2.2 kΩ | 8 | 10 | DB DIP switch'leri |
| 22 kΩ | 1 | 5 | M7 zaman aşımı |
| 100 Ω | 2 | 5 | HSYNC, VSYNC |

## 4. Gösterge, anahtar, konnektör (LCSC)

| Parça | Gerekli | Sipariş | Nerede |
|---|---|---|---|
| 3 mm LED (kırmızı, yeşil, sarı) | ~110 | 300 | Kontrol 24, PC/AR/X 48, A/IR/SP 24, durum ~10 |
| 8'li DIP switch | 6 (24 + 8 + 16 anahtar) | 8 | MANUAL paneli, DB, breakpoint |
| Tact buton | ~6 | 20 | GO, STEP, RESET… |
| SPDT anahtar (toggle/slide) | ~5 | 6 | RUN/STEP, MICRO, MANUAL, SLOW, BP açma |
| Pin header 40'lı + jumper şöntü | – | 10 + 20 | Renk, font bankası, NO-VGA jumper'ları |
| Mini-DIN-6 dişi | 1 | 2 | PS/2 |
| DE-15 (HD15) dişi | 1 | 2 | VGA |

## 5. AliExpress (Çin'den, aynı Arabistan adresine)

| Parça | Sipariş | Not |
|---|---|---|
| Arduino Mega 2560 klon | 1 | M8 iz/yükleme |
| PLCC32 → DIP32 adaptör kartı | 10 | Her flash için bir tane; T48 de DIP olarak programlar |
| 40 pinli ZIF soket | 4 | Sık yazılan flash'lar |
| 8 kanallı lojik analizör (24 MHz) | 1 | PulseView ile |
| ESD cımbız, IC sökücü | 1 + 1 | |

## 6. Türkiye

| Parça | Sipariş | Not |
|---|---|---|
| MB-102 830 delik breadboard | 30 (24 + 6 yedek) | Ağır, yurt içi ucuz |
| 22–24 AWG tek damar kablo, 6 renk | 6 × 25 m | Kırmızı, siyah, mavi, yeşil, beyaz, sarı |
| Hazır jumper seti (560) | 1 | Mevcut |
| Dupont şerit kablo | 3 | Arduino, VGA paneli |
| Kablo sıyırıcı | 1 | |
| PS/2 klavye (gerçek PS/2 fişli) | 1 | Trendyol |

## 7. Okulda / elimizde var

T48 programlayıcı, 5 V laboratuvar güç kaynağı, osiloskop, VGA monitör (kontrol edilecek).

---

## Notlar (LCSC, 19 Kasım kontrolü)

- **Flash:** SST39SF010A **PDIP-32 stokta yok** (0 adet, 37 $). PLCC-32 var: `SST39SF010A-55-4C-NHE` (C645928, 17 adet, 10+ 4,09 $) ve `SST39SF010A-55-4I-NHE-T` (C632839, 59 adet). 55 ns, 70 ns'den hızlı, sorun değil. Adaptörle breadboard'a takılır.
- **74HC DIP:** TI'ın bazı DIP'leri 0 stokta (ör. SN74HC377N, SN74HC166N). "Asian Brands" muadilleri stokta (ör. SN74HC166N(LX), 210 adet, 0,29 $). BOM yüklenince LCSC her satıra muadil önerir; **DIP/PDIP kılıf** seçildiğinden emin olun, SOIC değil.
- Toplam entegre maliyeti tahmini: ~60–90 $, flash ~41 $, pasif/konnektör ~30–40 $. Kargo (DHL, Arabistan) tahmini 25–40 $. Kesin rakam BOM yüklenince.
- **Arabistan gümrüğü:** 1.000 SAR'a (~267 $) kadar gümrük vergisi genelde yok, ama %15 KDV ödenir. Paketi 267 $'ın altında tutmak iyi olur. Adreste Saudi "national short address" kodu olmalı (2026'dan beri zorunlu).
