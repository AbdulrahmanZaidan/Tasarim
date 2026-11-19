# TA-8: projenin bütün durumu (19 Kasım 2026)

Abdurrahman, bu belge projenin şu anki halini baştan sona anlatıyor: ne bitti, ne kaldı, kim ne yapacak, siparişler, araçlar nasıl kullanılır. Birlikte okuyup iş bölümüne karar verelim.

---

## 1. Tek cümle

74HC entegrelerle breadboard üzerinde kendi 8 bitlik bilgisayarımızı yapıyoruz; Haziran 2027'de C ile yazılmış Snake oyunu VGA ekranda, PS/2 klavyeyle oynanacak.

| | |
|---|---|
| Ad | **TA-8**: **T**aha ve **A**bdurrahman, 8 bit (19 Kasım'a kadar TD-8) |
| İşlemci | 8 bit veri, 16 bit adres, mikrokodlu, 1 MHz (4 MHz saat, 4 faz) |
| Komut seti | 53 komut, 88 opcode |
| Bellek | 32 KB ROM (flash), 28 KB RAM, 2 KB ekran belleği, giriş/çıkış `F800–FFFF` |
| Görüntü ve giriş | VGA 640×480 zamanlaması, 40×30 karakter; PS/2 klavye |
| Ölçek | 92 entegre (işlemci 63), 24 breadboard |
| Takvim | Simülasyon: 27 Ekim – 3 Ocak (10 hafta, şu an **4. hafta**). Breadboard: Ocak – Haziran 2027 |

Planın tamamı: [SISTEM-PLANI.md](../SISTEM-PLANI.md) (teknik), [PROJE-PLANI.md](../PROJE-PLANI.md) (bütçe ve malzeme). Terimlerin sade açıklaması: 4. hafta raporunun **Sözlük** sekmesi ([hafta4.html#sozluk](https://abdulrahmanzaidan.github.io/Tasarim/raporlar/hafta4.html#sozluk)).

---

## 2. Modüller: kim, ne durumda

| Modül | Ne yapar | Sorumlu | Durum |
|---|---|---|---|
| M1 saat / reset / durdurma | 4 fazlı saat, STOP, WAIT, GO, reset | Abdurrahman | **Digital'de testli** (hafta1, 4/4). K1 geçti |
| M2 kontrol ünitesi | Mikrokod ROM'ları, kontrol latch'i, kod çözücüler, breakpoint | Taha | **Digital'de testli** (kabul testleri) |
| M3 adres registerları | PC, AR, X, SP | Abdurrahman | **Digital'de testli** (hafta3, 4/4) |
| M4 veri ve ALU | A, IR, F, iki ALU flash'ı | Abdurrahman | **Digital'de testli** (hafta2–3, 7/7, 10.000 vektör) |
| M5 bellek | ROM, RAM, adres çözme, LED ve durum portu | Taha | **Digital'de testli** (kabul testleri) |
| Bütün işlemci | M1–M5 bir arada | ikimiz | **Sıfır fark** (3 program, 33.170 çevrime kadar). K2 geçti |
| M6 VGA | Ekran zamanlaması, karakter hattı, çıkış | Abdurrahman | **Zamanlama kısmı Digital'de** (hafta5, 11 entegre). Karakter hattı ve çıkış katı sırada. Henüz `cpu.py` netlist'inde değil |
| M7 PS/2 klavye | Seri alıcı, susturma, temizleme | Abdurrahman (planın takviminde 6. hafta Taha) | Sırada; şimdilik test tezgâhında taklit |
| M8 hata ayıklama | Breakpoint, BUSREQ, MANUAL paneli, Arduino kartı | Taha | **Breakpoint ve BUSREQ netlist'te, testli** (17 Kasım). MANUAL paneli sırada. Arduino yazılımı hazır, donanımda denenmedi |

Bütün bağlantılar tek kaynaktan: `sim/ta8/hw/cpu.py` (netlist). Digital dosyaları, bağlantı tablosu ([TA8-baglanti-tablosu.md](TA8-baglanti-tablosu.md)) ve testler buradan üretiliyor. `.dig` dosyalarını elle düzenleme; netlist'i değiştirip yeniden üret.

---

## 3. Yazılım: ne hazır

| Parça | Durum |
|---|---|
| Komut seti (`isa.py`), mikrokod ve ALU ROM'ları | Hazır, tek kaynak |
| Assembler, iki emülatör, çarpma/bölme/yazdırma kütüphanesi | Hazır |
| Test vektörü üreticisi, çip seviyesi simülatör (gecikmeli), Digital'e dışa aktarım | Hazır |
| **C derleyicisi (`tacc`)** | **Bitti (19 Kasım):** planın C alt kümesinin tamamı, son parça `switch` atlama tablosu da eklendi. Snake'i derliyor, 200 rastgele programda doğru |
| Snake (C) | Emülatörde oynanıyor: `py play.py examples/snake.c` |
| Açılış kendi kendini test ROM'u | Hazır: ALU, RAM, yığın, ekran belleği |
| Arduino iz ve yükleme yazılımı | Hazır, Mega olmadığı için donanımda denenmedi |
| Otomatik testler | **305**, hepsi geçiyor |

---

## 4. Kilometre taşları

| | Ne | Tarih | Durum |
|---|---|---|---|
| K1 | Saat modülünün testleri geçiyor | 9 Kas | Geçti (18 Kas) |
| K2 | İşlemci simülasyonda emülatörle sıfır fark | 23 Kas | Geçti |
| K3 | Simülasyonda ekrana yazı (CPU + VGA + PS/2 birlikte, Digital'de) | 14 Ara | M6'nın geri kalanı ve M7 gerekiyor |
| K4 | Tasarım donduruldu, yapıma hazır | 3 Oca | KiCad şemaları, yerleşim planı |

---

## 5. İş bölümü: önümüzdeki üç hafta

| Hafta | Taha | Abdurrahman | Birlikte |
|---|---|---|---|
| **Bu hafta (19–23 Kas)** | ~~C derleyicisinin son parçası~~ (bitti); 5. hafta raporu taslağı | M6'yı `cpu.py` netlist'ine taşımak (birlikte, aşağıda) | Siparişlerin ilk kısmı (bölüm 6) |
| **5. hafta (24–30 Kas)** | MANUAL paneli; M7 PS/2'ye başlangıç | M6 karakter hattı: ekran belleği adres seçimi (3× 74HC157), VRAM, font ROM'u, 74HC166, çıkış katı | Parçalar gelince giriş testleri, **prototip a** (saat modülü breadboard'da, osiloskopla) |
| **6. hafta (1–7 Ara)** | M7 PS/2 Digital'de; prototip d (gerçek klavye) | M6 VRAM penceresi (CPU ile paylaşım), prototip c (gerçek monitör) | Kalan malzeme siparişi (1–7 Aralık) |

Sonrası: 7. hafta bütün sistem Digital'de ekrana yazı (K3), 8. hafta KiCad şemaları (Abdurrahman: M1, M3, M4, M6; Taha: M2, M5, M7, Arduino kartı), 9. hafta breadboard yerleşim planı, 10. hafta tasarımı dondurma.

**M6'yı netlist'e taşımak:** senin `Abdurrahman/hafta5/m6_uret.py` içindeki `chips()` listesi `sim/ta8/hw/cpu.py`'de `m6_vga()` diye bir modül olur; test tezgâhındaki VRAM taklidi (X1) ve `VWR_s` girişi kalkar, yerine senin sinyallerin gelir. Böylece bütün işlemci + ekran zamanlaması tek devrede, emülatörle karşılaştırılabilir.

**Senin bulgun (74HC74, 25 MHz'i en kötü gecikmede ikiye bölemiyor):** prototip c'de DCLK'yi osiloskopla ölçeceğiz. Gerekirse ÷2 için 74AC74 ya da doğrudan 12,5 MHz osilatör.

### Raporlar

1–4. hafta raporları yayında. Sıradaki raporların önerilen konuları:

| Rapor | Taha | Abdurrahman |
|---|---|---|
| 5. hafta (24–30 Kas) | C derleyicisi (tamamlandı) ve hata ayıklama donanımı (breakpoint, BUSREQ) | M6 VGA zamanlaması (`hafta5` klasörün hazır) |
| 6. hafta (1–7 Ara) | Snake oyunu (C ile) | M6 karakter hattı |
| 7. hafta (8–14 Ara) | Açılış testi ROM'u, Arduino yazılımı | M6 + işlemci birlikte, ekranda yazı |

Her rapor sade bir "bu hafta, kısaca" bölümü ve Sözlük sekmesiyle hazırlanıyor. Kendi `haftaN/README.md` notunu her hafta yazmaya devam et; rapordaki senin sekmen ondan hazırlanıyor.

---

## 6. Siparişler (sırayla, acele etmeden)

**Önce yurt içi, stokta az kalanlar** (19 Kasım'da kontrol edildi):

| Parça | Adet | Fiyat | Nereden |
|---|---|---|---|
| 25 MHz osilatör (5'li lot), **son 1 lot** | 1 lot | 464 TL | [n11](https://www.n11.com/urun/25000mhz-kristal-osilator-5-adet-128897159) |
| 74HC161 (25'li), **son 1 lot** | 1 lot | 464 TL | [n11](https://www.n11.com/urun/74hc161n-dip-philips-74-serisi-entegre-25-adet-115911320) |
| PC74HCT688P (6'lı), **son 1 lot** | 1 lot | 334 TL | [n11](https://www.n11.com/urun/pc74hct688p-dip-74-serisi-entegreler-6-adet-56292675) |
| SST39SF010-90 flash (3'lü), son 2 lot | 2 lot | 2 × 573 TL | [n11](https://www.n11.com/urun/sst39sf010-90-4c-ph-entegre-3-adet-128902116) |
| CY62256 SRAM (2'li) | 2 lot | 2 × 915 TL | [n11](https://www.n11.com/urun/cy62256ll-70pc-28pin-diger-entegreler-2-adet-128900107) |
| 74HC163 (25'li) | 1 lot | 556 TL | [n11](https://www.n11.com/urun/mc74hc163-dip-motorola-74-serisi-entegreler-25-adet-128898167) |
| 4 MHz osilatör (4'lü) | 1 lot | 557 TL | [n11](https://www.n11.com/urun/4000mhz-kristal-osilator-4-adet-128896944) |
| Arduino Mega 2560 R3 klon (CH340, kablo dahil) | 1 | 868 TL | [direnc.net](https://www.direnc.net/arduino-mega-2560-r3-klon-usb-kablo-dahil-en) |
| 74HC191 | 4 | 4 × 13 TL | [direnc.net](https://www.direnc.net/74hc191--syn-positive-edge-triggered-4-bit-bidirectional-binary-counter) |

**Yurt dışı (tek paket):** SST39SF010A-70 flash × 10, [AliExpress](https://tr.aliexpress.com/item/1005007458436336.html), yaklaşık 17,7 €. Önce üniversiteden **MODEL muafiyet yazısı** (gönderi ≤ 30 €); yazı olmazsa gümrük +4.000–6.000 TL. 70 ns'likler mikrokod ve ALU soketlerine, 90 ns'likler program ROM'u gibi yerlere.

**1–7 Aralık:** kalan entegreler, breadboard'lar, kablolar, pasifler ([PROJE-PLANI 14.2 ve 14.5](../PROJE-PLANI.md)).

Gelen her parça giriş testinden geçer (liste: [Taha/hafta4/README.md](../Taha/hafta4/README.md) bölüm 5): flash'lar okuldaki T48'de sil-yaz-doğrula, SRAM'ler T48'de ya da Arduino ile, sayaçlar breadboard'da 1 Hz saatle.

---

## 7. Araçlar: nasıl çalıştırılır

Hepsi `sim/` klasöründen, Python 3.12, ek paket yok:

```
py -3 -m unittest                                   bütün testler (305, ~5 dk)
py -3 cli.py run examples/merhaba.asm               assembly programı emülatörde
py -3 -m tacc examples/merhaba.c -o build/merhaba_c.asm --run   C programını derle ve çalıştır (-o şart: yoksa merhaba.asm ezilir)
py -3 play.py examples/snake.c                      Snake'i terminalde oyna
py -3 cli.py hw run examples/merhaba.asm            çip seviyesi simülatörde, emülatörle karşılaştır
py -3 cli.py hw digital --run 600                   Digital dosyalarını üret ve Digital'de koştur
py -3 cli.py vectors alu -n 10 --format csv         test tablosu (alu, urom, cs, decode, trace)
py -3 cli.py hw wiring -o ../Tahadan-Abdurrahmana/TA8-baglanti-tablosu.md
```

- Digital: masaüstündeki **"Digital (TA-8)"** kısayolu. Hazır kabul testleri `sim/digital_kabul/` içinde: dosyayı aç, araç çubuğunun en sağındaki yeşil tikli düğme.
- Çalışma düzeni: işe başlamadan `git pull`; netlist ya da mikrokod değişirse `py cli.py hw digital` ve `py -3 -m unittest`; her hafta `Abdurrahman/haftaN/README.md`.

---

## 8. Açık riskler

| Risk | Ne zaman bakılır |
|---|---|
| WAIT kararının payı en kötü durumda ~3 ns | Prototip a, osiloskop |
| 74HC74'ün 25 MHz'i ikiye bölmesi (senin bulgun) | Prototip c |
| Flash ve SRAM çıkış geriliminin 74HC için yeterliliği (VOH) | Prototip b |
| MODEL muafiyet yazısı gecikirse flash'lar gecikir | Bu hafta başvuru |
| Mega yok | Bu hafta sipariş |

Ad değişikliğinin ayrıntısı (eski ve yeni dosya adları): [README.md](README.md), en üstteki 19 Kasım bölümü.
