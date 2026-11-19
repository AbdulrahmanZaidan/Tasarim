# Hafta 5 (24–30 Kasım 2026): C derleyicisi ve hata ayıklama donanımı

## Özet

| İş | Sonuç |
|---|---|
| C derleyicisi `tacc` | Planın C alt kümesinin tamamını derliyor; son parça `switch` atlama tablosu bu hafta eklendi |
| Kod hızı | Plandaki hedeflerle aynı; ekrana metinde karakter başına 4 çevrim fazla |
| Doğrulama | 200 rastgele C programı (~4.400 ifade), ayrı bir Python hesaplayıcıyla aynı sonuç |
| Breakpoint | 2× 74HC688 + BRK flip-flop'u; adrese her okuma ya da yazmadan sonra duruyor |
| BUSREQ / BUSACK | Arduino işlemciyi en çok 7 saat darbesinde durduruyor, yolları alıyor, belleğe yazıp okuyor |
| Entegre sayısı | 59 → 63; hiçbir modülde plandaki adet aşılmıyor |
| Bulgu | Ekran belleği bekleme (WAIT) kararı en kötü gecikmede yetişmiyordu; tek kablo değişikliğiyle düzeltildi |
| Testler | Derleyici 52, bütün işlemci 29, Digital 37 test; hepsi geçiyor |

## 1. C derleyicisi: `tacc`

Derleyici, C ile yazılan programı TA-8'in komutlarına çeviren program. Zincir: C kaynağı → `tacc` → assembly → assembler → ROM imajı → flash.

```
> py -m tacc examples/merhaba.c -o build/merhaba_c.asm --run
build\merhaba_c.asm: 89 satır assembly, ROM 253 byte, RAM 8020-8029 (10 byte)
RefEmu: durdu (HALT) · 6943 çevrim (6.94 ms @ 1 MHz) · LED=01010101 ($55)
|  MERHABA, TA-8!                        |
```

`-o` şart: verilmezse çıktı `examples/merhaba.asm` olur ve elle yazılmış dosyanın üzerine yazar.

| | `merhaba.asm` | `merhaba.c` |
|---|---|---|
| ROM | 66 bayt | 253 bayt (açılış kodu 127 + program 111 + metin 15) |
| Çevrim | 573 | 6.943 (6.228'i açılışta ekranı temizlemek) |
| Karakter başına | 37 çevrim | 41 çevrim |

- **Var:** `char`, `signed char`, `int` (16 bit), `unsigned`, işaretçiler, 1 ve 2 boyutlu diziler, `enum`, `const` tablolar (ROM'da), `volatile`; if/else, while, do/while, for, switch, break, continue, return; bütün operatörler; `#include` ve `#define`.
- **Yok (satır numaralı Türkçe hata):** özyineleme, struct, long, float, fonksiyon işaretçisi, typedef, goto. İlk dördü planın ilk sürümünde de yok.

| C kodu | Plan | tacc |
|---|---|---|
| `a = b + c` (int) | 24 çevrim | 24 |
| `*p = x` | 11 | 11 |
| `if (x < y)` | 19–20 | 19–20 |
| 2 parametreli çağrı + dönüş | 82 | 82 |
| Ekrana metin | 37 / karakter | 41 / karakter |
| `x = y * 10` | – | 116 (çarpma rutini yerine kaydır-topla) |

### `switch` için atlama tablosu (bu hafta)

İki yol var: değeri case'lerle tek tek karşılaştırmak ya da her case'in adresini tutan tablodan JMPI ile doğrudan atlamak. Derleyici ortalama çevrime göre hızlı olanı seçiyor.

| Değer | Karşılaştırma, case başına | Tablo, sabit | Tablo ne zaman |
|---|---|---|---|
| 8 bit | ~5 çevrim | ~38 çevrim | ~14 case'ten itibaren |
| 16 bit | ~15 çevrim | ~52 çevrim | ~6 case'ten itibaren |

Tablo yalnız case'ler sıksa (en çok 128 giriş, case başına en çok 3). Hedef adres tablodan RAM'deki `__jt` hücresine (801C, `main`'den önce kopyalama için kullanılan yer) kopyalanıp `JMPI (__jt)` ile atlanıyor. Test: boşluk, aralık dışı (eksi, üst baytı dolu), düşme, break, continue; iki emülatörde. Bilerek iki yerden bozulunca test kalıyor.

**Nasıl test edildi:** 200 rastgele C programı hem emülatörde hem C kurallarını uygulayan ayrı bir Python hesaplayıcıda; geliştirme sırasında iki derleyici hatası yakaladı.

## 2. Hata ayıklama donanımı (plan 5. hafta)

**Breakpoint.** İki 74HC688 adres yolunu 16 anahtarla karşılaştırıyor (`/MATCH`). `/ACCESS = AND(/MRD, /MEMW)` o çevrimin belleği okuduğunu ya da yazdığını söylüyor. BRK flip-flop'u commit'te `NOR(/MATCH, /ACCESS)`'i örnekliyor; makine o çevrimin sonunda C fazında duruyor. GO bir çevrim ilerletiyor, reset temizliyor. Plana ek: `/BP_EN` açma anahtarı (yoksa anahtarlar 0000'dayken her açılışta durulurdu).

**BUSREQ.** `/BUSREQ` (açık-drain, 10k pull-up) 74HC175'te iki MCLK ile senkronlanıyor (`BRQ_s` → STOP). BUSACK flip-flop'u `BRQ_s & C fazı`'nı örnekliyor; BUSACK = 1 iken #DS ve #AS kapalı, AB ve DB'yi hiçbir CPU çipi sürmüyor. Arduino `/ARD_WR` ile yazıyor, `/ARD_RD` ile okuyor.

| Deneme | Sonuç |
|---|---|
| Komut adresinde breakpoint | `merhaba`'da 001D: 15 erişimin her birinde durdu; GO ile devam, emülatörle sıfır fark |
| RAM'de (watchpoint) | 8100'e 3 yazma ve 1 okumanın dördünde de durdu; yazılan değer bellekteydi |
| Kapalıyken, reset | Kapalıyken durmuyor; reset BRK'yi temizliyor |
| BUSREQ, çalışırken | 4 farklı fazda: BUSACK en çok 7 MCLK'de (çoğunlukla 3); ROM okundu, RAM'e yazılıp okundu; devam, sıfır fark |
| Yükleme baştan sona | 8000'e program yazıldı, doğrulandı, SW0 = 1 ile reset → çalıştı, LED 37h; sıfır fark |
| Digital | M1 modülünde senaryo; bütün işlemcide breakpoint'te durma, BUSREQ ile durup devam |
| Bozma denemesi | 4 bilinçli bozmanın 4'ü yakalandı |

| Modül | Plan | Kuruldu | Kalan |
|---|---:|---:|---|
| M1 Saat | 14 | 11 | NE555, 74HC153, 74HC14 |
| M2 Kontrol | 13 | 13 | – |
| M3 Adres | 22 | 22 | – |
| M4 Veri/ALU | 8 | 8 | – |
| Yardımcı | 4 | 3 | ikinci 74HC00 gereksiz |
| M5 Bellek | 6 | 6 | – |
| **Toplam** | **67** | **63** | 4 |

Dosyalar: `sim/ta8/hw/cpu.py` (U110, U111, U212, U213), `sim/ta8/hw/harness.py` (`set_breakpoint`, `run_to_stop`, `bus_request`, `ard_write`, `ard_read`, `bus_release`), `tests/test_hw_cpu.py` (`TestBreakpoint`, `TestBusRequest`).

## 3. Bulgu: WAIT kararı

- Plandaki hesap ~236 ns; simülasyonda en kötü gecikme + kurulum 272 ns > 250 ns pencere: yetişmiyor.
- Hesaptaki eksik: süre bir flip-flop gecikmesi (~44 ns) kadar sonradan başlatılmış, kurulum süresi eklenmemiş.
- Düzeltme: WAIT 74HC138'inin G1'i VCC yerine CLK. En kötü 247 ns. Pay ~3 ns: prototip a'da osiloskopla.

| Yol | Simülasyon (tipik / en kötü) | Elle hesap | Pencere |
|---|---|---|---|
| Bellekten oku, ALU, A'ya yaz | 254 / 393 ns | 254 / 403 ns | 750 ns |
| Mikrokod ROM'unda arama | 94 / 152 ns | 94 / 152 ns | 250 ns |
| WAIT, ilk tasarım | 111 / 272 ns | ~236 ns | 250 ns |
| WAIT, düzeltilmiş | 102 / 247 ns | – | 250 ns |

Hız denemesi: 1,5 MHz'de sıfır fark (yalnız WAIT en kötü gecikmede yetişmiyor); 2 MHz yalnız tipik gecikmelerle.

## Gelecek hafta

- Snake oyununu C ile yazmak.
- Gelen parçaların giriş testleri.

## Kullanılan araçlar

Python 3.12 (yalnızca standart kütüphane), unittest, Java (Temurin JDK 21), Digital v0.31, Git/GitHub.
