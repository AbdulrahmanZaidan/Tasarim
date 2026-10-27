# TD-8 simülasyon araçları

Bu klasör devre simülasyonunun yazılım tarafıdır. **Devrenin kendisi Digital'de çizilir.** Buradaki araçlar:

1. **ROM imajları:** Digital'deki ROM bileşenlerine ve gerçek flash çiplerine yüklenecek içerikler (mikrokod, ALU tabloları, VGA zamanlaması, font).
2. **Assembler:** TD-8 programlarını çevirir.
3. **İki emülatör:** Programı çalıştırır ve devrenin vermesi gereken doğru sonucu söyler. Digital'deki devre ya da breadboard ondan farklı davranırsa hata bulunmuş olur.
4. **Test vektörleri:** Digital'in test bileşenine yapıştırılır.

Tasarımın tamamı: [../SISTEM-PLANI.md](../SISTEM-PLANI.md)

## Kurulum

| Ne | Nasıl |
|---|---|
| Python 3.12 | Kurulu (`py --version`). Ek paket gerekmez, yalnızca standart kütüphane kullanılıyor. |
| Java 17 | [adoptium.net](https://adoptium.net) → Temurin 17 (LTS) → Windows x64 `.msi`. Digital için gerekli. |
| Digital | [github.com/hneemann/Digital/releases](https://github.com/hneemann/Digital/releases) → `Digital.zip` indirin, bir klasöre açın, `Digital.exe`'yi çalıştırın. |

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
py cli.py vectors alu -n 1000 > alu_test.txt    Digital ALU testi için vektörler
py cli.py vectors urom -n 1000 > urom_test.txt  Digital kontrol ünitesi testi için vektörler
py -m unittest                                  tüm testler (~20 s)
```

## Dosyalar

| Dosya | İçerik |
|---|---|
| `td8/isa.py` | **Komut setinin tek kaynağı:** kontrol kelimesi, ALU kodları, 88 opcode'un mikroadımları |
| `td8/microcode.py` | uROM0..2 imajlarını üretir; kuralları denetler (SISTEM-PLANI 4.5) |
| `td8/alu.py` | 8-bit referans ALU ve iki nibble flash'ının tabloları |
| `td8/vga.py` | VGA zamanlama ROM'u, test fontu, `font8x8_basic.h` dönüştürücüsü, sayaç simülasyonu |
| `td8/asm.py` | Assembler (yazım kuralları dosyanın başında) |
| `td8/bus.py` | Bellek haritası, I/O (klavye, KSTAT, LED), VRAM penceresi modeli |
| `td8/emu_micro.py` | Mikroadım emülatörü: üretilen imajları aynen çalıştırır, çevrim çevrim iz verir |
| `td8/emu_ref.py` | Komut seviyesi emülatör: mikrokoddan bağımsız, çapraz kontrol için |
| `cli.py`, `gen_roms.py` | Komut satırı |
| `examples/` | `merhaba.asm` (ekrana yazı), `klavye.asm` (PS/2 byte'larını gösterir) |
| `tests/` | ALU (8 milyon girişin hepsi), mikrokod kuralları, assembler, iki emülatörün eşdeğerliği, VGA zamanlaması |
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
- **VGA:**
  - 400 nokta × 525 satır; HSYNC 48 nokta, VSYNC 2 satır, 40 × 480 görünür alan.
  - VRAM pencereleri doğru iç içe.
  - Sayaçlar herhangi bir başlangıç durumundan bir kare içinde toparlanıyor.

## Digital'de kullanım

- **ROM bileşenleri:**
  - Ayarlar: veri genişliği 8, adres genişliği 17.
  - İçerik: veri alanında "Yükle" ile `build/` altındaki `.bin` dosyasını seçin. Kabul etmezse aynı adlı `.hex` dosyasını deneyin (Logisim "v2.0 raw" biçimi).
- **Test bileşeni:** `py cli.py vectors ...` çıktısını yapıştırın. Devredeki giriş ve çıkışların etiketleri, vektörün ilk satırındaki adlarla **aynı** olmalı:
  - ALU için `OP A B Cin Zin R Z C N V`;
  - kontrol ünitesi için `STEP IR Z C N V CW0 CW1 CW2`.
- **İlk modül:** M1 saat (SISTEM-PLANI bölüm 3 ve 12.3). Bitince sırasıyla M3, M2, M4 gelir.

## Komut eklemek ya da değiştirmek

1. `td8/isa.py` içinde adımları yazın (yazım: `adres/kaynak/hedef/ALU bitler`, örnek `AR/MEM/A/ADD FL NEXT`).
2. Komut seviyesindeki anlamını `td8/emu_ref.py`'ye ekleyin.
3. `py -m unittest` çalıştırın. Mikrokod kuralı ihlal edilirse hata mesajı hangi adım olduğunu söyler.
4. `py gen_roms.py` ile imajları yenileyin, `SISTEM-PLANI.md`'yi güncelleyin, commit edin.

## Sırada ne var (SISTEM-PLANI bölüm 13 ve 14)

| Ne zaman | İş |
|---|---|
| Simülasyon 3. hafta | Emülatör izinden çevrim çevrim Digital test vektörü üreticisi (bütün CPU testi) |
| Simülasyon 7. hafta | Gerçek font: `font8x8_basic.h` (kamu malı) → `py cli.py roms --font ...` |
| Simülasyon 9. hafta | Arduino iz ve yükleme yazılımı |
| Yapım 1–11. hafta | C derleyicisi (`tdcc`), runtime (`__mul16`, `__divmod16`), `crt0`, `hw.h` |
| Yapım 12–17. hafta | Snake (C), açılış test ROM'u |
