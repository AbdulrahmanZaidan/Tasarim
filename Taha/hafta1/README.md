# Hafta 1 (27 Ekim – 2 Kasım 2026): simülasyon araçları

## Ne yapıldı

- Python simülasyon araçları yazıldı ([`sim/`](../../sim/), ayrıntı: [sim/README.md](../../sim/README.md)):
  - **Komut seti:** `isa.py`, 53 komut ve 88 opcode tek dosyada.
  - **ROM üreticileri:** mikrokod (3 çip), ALU (2 çip), VGA zamanlaması ve yazı tipi. Toplam 7 imaj, her biri 128 KB.
  - **Assembler:** `asm.py`.
  - **İki bağımsız emülatör:** mikroadım (`emu_micro.py`) ve komut seviyesi (`emu_ref.py`).
  - **Testler:** 27 otomatik test.
- Sistem planı ve proje planı yazıldı: [SISTEM-PLANI.md](../../SISTEM-PLANI.md), [PROJE-PLANI.md](../../PROJE-PLANI.md).

**Kullanılan araçlar:** Python 3.12 (yalnızca standart kütüphane), unittest, Git/GitHub.

## Sonuç

30 Ekim'de çalıştırıldı (`sim/` klasöründe):

```
> py -m unittest
Ran 27 tests in 8.508s
OK

> py gen_roms.py
build: urom0-2, alu_lo, alu_hi, vga_timing, font (.bin + .hex, 128 KB)
Komut sayısı: 53, opcode sayısı: 88

> py cli.py run examples/merhaba.asm
durdu (HALT) · 573 çevrim (0.57 ms @ 1 MHz)
PC=001D A=55 X=0041 SP=FF Z=1 C=0 N=0 V=0 LED=01010101
|  MERHABA, TD-8!                        |
```

## Sorunlar / sorular

- Plan devre simülasyonunu Digital'de yapmayı öngörüyordu, saat modülü Proteus'ta yapıldı. Sonraki modüller için hangi araçta devam edileceğine karar verilmeli. ROM imajlarının (`.bin`) ve test vektörlerinin nasıl yükleneceği buna bağlı.

## Gelecek hafta

- `isa.py`'yi öğrenmek, yeni test programları yazıp emülatörde çalıştırmak.
- Kontrol ünitesi (M2): mikrokod ROM imajlarını simülasyondaki devreye yüklemek.
