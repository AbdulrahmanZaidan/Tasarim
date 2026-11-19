# Hafta 6 (1–7 Aralık 2026): M6 netlist'te, KiCad şemaları, malzeme listesi

Hazırlayan: Abdurrahman

## Özet

- **M6 zamanlaması ana netlist'te:** `sim/ta8/hw/cpu.py` `m6_vga()` (U701–U711). `hafta5/m6_uret.py` artık devreyi buradan alıyor; tek kaynak.
- **CPU + M6 birlikte çalışıyor:** `merhaba.asm`, gerçek 25 MHz VGA zamanlamasıyla, emülatörle **sıfır fark**. CPU, M6'nın açtığı VRAM penceresini ~15,4 ms bekliyor; "MERHABA, TA-8!" VRAM'e 482–522. satırlar arasında yazılıyor, pencere dışında yazma yok.
- **VWR senkronlayıcısı kuruldu:** M1'deki U111'in boş iki flip-flop'u VWR'yi (T1 Q7) iki MCLK ile VWR_s'e çeviriyor (plan 3.6).
- **KiCad şemaları** netlist'ten üretiliyor: `py cli.py hw kicad` → `sim/kicad/`, PDF: [TA8_semalar.pdf](TA8_semalar.pdf).
- **Malzeme listesi:** [BOM.md](BOM.md), LCSC'ye yüklenecek dosya [BOM-lcsc.csv](BOM-lcsc.csv).

## 1. İki kip: `build(vga=...)`

| Kip | M6 | VWR_s | Hız | Kullanım |
|---|---|---|---|---|
| `'taklit'` (varsayılan) | yok | test tezgâhından | hızlı | sıfır fark testleri, Digital dosyaları |
| `'netlist'` | U701–U711, OSC25 = 25 MHz | U111 FF2/FF3, VWR'den | ~25 kat yavaş | M6 testleri, KiCad, bağlantı tablosu |

```
HwCpu(prog.image, vga='netlist')      # test tezgâhı
cpu.build(vga='netlist')               # yalnız netlist
```

Pencere kapalıyken WAIT bir kareye (16,8 ms) kadar sürebildiği için `HwCpu.run()`'ın "takıldı" sınırı netlist kipinde 5 ms'den 20 ms'ye çıktı.

## 2. Sonuçlar

| Test | Sonuç |
|---|---|
| merhaba.asm, CPU + M6, emülatörle karşılaştırma | sıfır fark, 573 çevrim, HALT |
| VRAM yazmaları | 14, hepsi satır 482–522 arasında; pencere dışında 0 |
| WAIT ile bekleme | 15,4 ms (açılışta kare 0, pencere satır 482'de açılıyor) |
| M6 ile CPU'nun ortak netleri | yalnız VWR ve SLOW (istenmeyen çakışma yok) |
| Entegre sayımı (M6) | plan 19, netlist 11, sırada 8, açıklanmamış fark 0 |

Testler: `sim/tests/test_m6_netlist.py` (7 test), `test_kicad.py` artık M6 dahil kartla.

## 3. Sırada (M6'nın kalanı)

VRAM adres seçimi (3× 74HC157), VRAM (CY62256; şimdilik TB X1 taklidi), font ROM'u, 74HC166, DB → VRAM tamponu (74HC245, /BUFEN), çıkış katı (74HC08). Bunlar gelince X1 kalkar ve ekrandaki yazı Digital'de görülür (K3).
