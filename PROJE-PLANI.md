# 8-bit Breadboard Bilgisayar — Proje Planı

> Bitirme projesi · 2 kişilik ekip · Plan tarihi: 27 Ekim 2026
> Simülasyon ve tasarım: 27 Ekim 2026 – 3 Ocak 2027 · Breadboard'da yapım: Ocak – Haziran 2027
> **Teknik tasarımın tamamı:** [SISTEM-PLANI.md](SISTEM-PLANI.md) · **Simülasyon yazılımı:** [sim/](sim/)

## Alınan kararlar

| Konu | Karar |
|---|---|
| Ekip | 2 kişi |
| Bütçe | 30.000 TL |
| İşlemci | Kendi komut setimiz **TD-8**, 74HC entegrelerle kurulan mikrokodlu CPU (aşağıdaki B yolu). **Danışman onayladı.** |
| FPGA | Kullanılmayacak |
| Ölçüm ve programlama | Osiloskop var. Okulda **ayarlı güç kaynağı ve EEPROM programlayıcı** var. |
| Takvim | Simülasyon 27 Ekim 2026 – 3 Ocak 2027 (10 hafta). Breadboard'da yapım **Ocak 2027**'de başlıyor; süre **Haziran 2027**'ye kadar (~23 hafta). |
| İthalat | Yalnızca flash çipleri, tek paket. Üniversite yazısıyla öğrenci "MODEL" muafiyeti kullanılacak (gönderi başına ≤30 €). |
| Final demo | C ile yazılmış, PS/2 klavyeyle oynanan, VGA ekranda çalışan Snake |

## Kısaca

- **İşlemci:** Kendi komut setinizi (ISA) tasarladığınız, 74HC entegrelerle kurulan, **mikrokodlu** bir CPU yapın. 8-bit veri yolu, **16-bit adres yolu** (64 KB) olsun. Ben Eater'ın SAP tasarımını olduğu gibi kopyalamayın. 16 byte RAM ve 4-bit adresle C de VGA da olmaz.
- **VGA:** Bitmap yerine **metin modu** yapın: 40×30 karakter, 640×480@60Hz zamanlaması.
- **C:** Kendi yazacağınız küçük bir C derleyicisi (C'nin bir alt kümesi, Python ile) ya da Small-C uyarlaması. GCC veya LLVM'i bu projeye uyarlamak gerçekçi değil.
- **Simülasyon:** Ana araç **Digital** (hneemann) olsun. Yanına bir Python emülatörü, customasm ve KiCad.
- **Hata ayıklama:** Bunu sonradan değil, tasarımın içine koyun. Tek adım saat, kontrol sinyali LED'leri, donanım breakpoint'i ve en önemlisi **Arduino Mega ile bir bus izleyici**: devre her saat adımında emülatörle otomatik karşılaştırılır.

---

## 1. En kritik karar: "işlemci yapmak" ne demek?

| Yol | Ne yapıyorsunuz | C | VGA | Risk | Yorum |
|---|---|---|---|---|---|
| A. Ben Eater SAP-1 kopyası | 4-bit adres, 16 byte RAM | Olmaz | Bağlanacak bellek yok | Düşük | C/VGA hedefiyle uyumsuz |
| **B. Kendi ISA'nızla 74xx CPU** | CPU'yu entegre entegre siz tasarlarsınız | Kendi derleyiciniz | Ayrı video devresi | Orta-yüksek | **Seçilen yol.** "İşlemciyi biz yaptık" demek için tam karşılık |
| C. W65C02 / Z80 tabanlı | Hazır CPU, sistemi siz kurarsınız | cc65 / SDCC hazır | Kolay | Düşük | İşlemciyi siz yapmamış olursunuz. Danışman kabul ederse yedek plan |
| D. Gigatron tarzı | CPU VGA'yı yazılımla üretir, ~35 entegre | glcc var ama ROM'u kopyalarsınız | Yazılımla | Yüksek | Çok zarif ama breadboard'da 6.25 MHz zor. İlham için inceleyin |

**Danışmana teyit ettirin:** "Kendi komut setimiz şart mı?" Şartsa B kesinleşir. Değilse C çok daha az riskli ama projenin "işlemci" kısmı kaybolur.

---

## 2. Önerilen mimari (B yolu)

> **Not:** Bu bölüm ilk öneri. Kesinleşen tasarım (TD-8) için **13. bölüme** bakın. Farklar:
> - B registerı yok;
> - SP 8-bit ve EF sayfasında;
> - stack'e göre adresleme yerine statik çerçeve kullanılıyor;
> - ALU, 74HC283 yerine flash tablosu.

### Temel özellikler

- 8-bit veri yolu, 16-bit adres yolu. Program ve veri aynı bellekte (von Neumann), çünkü C programlarının RAM'e yüklenip çalışabilmesi gerekiyor.
- Registerlar: A, B (genel amaçlı), X (16-bit pointer), SP (16-bit), PC (16-bit), IR, FLAGS (Z, C, N, V).
- Mikrokodlu kontrol. Mikrokod EEPROM'unun adresi = opcode (8 bit) + adım (4 bit) + flag (4 bit) = 16 bit. 3–4 paralel flash ile 24–32 kontrol sinyali çıkar. Flag'leri adrese katınca koşullu dallanma bedavaya gelir.
- Hedef saat **1 MHz**. Tasarımı 2 MHz'e göre yapın.
- Mantık ailesi **74HC** (74LS değil, gerekçesi 5. bölümde).

### Bellek haritası önerisi

| Adres | İçerik |
|---|---|
| `0000–7FFF` | ROM 32 KB: açılış kodu, monitör programı, runtime kütüphanesi |
| `8000–EFFF` | RAM 28 KB: yüklenen programlar, veri, stack (EFFF'den aşağı büyür) |
| `F000–F7FF` | VRAM 2 KB (CPU sadece yazar, 40×30 metin) |
| `F800–FFFF` | I/O: LED/7-segment portu, VGA durum biti, klavye, seri port |

Adres çözmek için bir 74HC138 ve birkaç kapı yeter.

### C'nin derlenebilmesi için ISA'da mutlaka olması gerekenler

Bunlar yoksa derleyici yazmak kabusa döner:

- 16-bit SP, PUSH/POP, CALL/RET
- Stack'e göre adresleme (`LD A,[SP+n]`): yerel değişkenler ve parametreler için
- Pointer üzerinden erişim (`LD A,[X]`, `ST [X+]`)
- ADC/SBC (16-bit `int` = iki 8-bit işlem), CMP ve Z/C/N/V'ye göre dallanma. İşaretli karşılaştırma için V flag'i gerekir.
- Sağa kaydırma: ALU'ya eklemek yerine bir 74HC541'i bitleri bir kaydırılmış şekilde bus'a bağlayın, bedavaya SHR elde edersiniz.
- Çarpma/bölme donanımda olmasın, runtime kütüphanesinde yazılımla yapılsın.

### Hata ayıklamayı kolaylaştıran tasarım kuralları

- **Bus'ı kimin süreceğini kodlayın:** 4 bitlik bir alan ve 74HC154 ile seçin. Böylece iki çipin aynı anda bus'a yazması fiziksel olarak imkânsız olur. Bus çakışması hem çip yakar hem de en garip hataları üretir.
- **Saat sinyalini asla kapı ile kesmeyin (gated clock):** Yüklemeyi enable pini olan çiplerle yapın (74HC377, 74HC161).
- **Mikrokod çıkışlarını latch'leyin:** EEPROM çıkışları adres değişirken kısa süre saçmalar (glitch). Kontrol kelimesini saatin düşen kenarında bir 74HC574'e alın. Bu hem glitch'i bitirir hem de LED sürmeye uygun bir çıkış verir.
- **RAM yazma sinyalini (WE) saatin ikinci yarısıyla sınırlayın.** Ben Eater'ın en bilinen sorunu buydu.
- **BUSREQ hattı ekleyin:** CPU'nun adres/veri sürücülerini yüksek empedansa (tri-state) alan bir hat. Böylece dışarıdan bir kart (Arduino) RAM'e program yazabilir.

---

## 3. VGA: mantıklı olan ve olmayan

### Mantıksız olanlar

- 640×480 tam çözünürlüklü renkli bitmap: 300 KB'tan fazla bellek ve breadboard'da 25 MHz piksel hızı demek.
- VGA'yı bir mikrodenetleyiciyle üretmek: "işlemciyi biz yaptık" iddiasını zayıflatır.

### Önerim: 40×30 metin modu

- 640×480@60Hz zamanlaması kullanın ama nokta saati 12.5875 MHz olsun (25.175 MHz osilatör ÷2). Yatayda 320 piksel olur, 8×8 fontun her pikseli 2×2 çizilir, sonuç **40×30 karakter**. 25.175 MHz osilatör bulamazsanız 25 MHz de çoğu monitörde çalışır.
- Zamanlama: yatay 400 nokta (320 görünür + 8 ön boşluk + 48 sync + 24 arka boşluk), dikey 525 satır (480 + 10 + 2 + 33). İki sync de negatif.
- **Satır adımını 2'nin kuvveti seçin:** VRAM adresi = {satır (5 bit), sütun (6 bit)}. Böylece donanımda çarpma gerekmez, sadece kablo bağlarsınız. 64 sütunun 40'ı kullanılır, hepsi 2 KB'a sığar.
- Font ROM adresi = {karakter kodu, font satırı (3 bit)}. Çıkış 74HC166 kaydırma yazmacına, oradan RGB'ye gider.
- Toplam ~18–25 entegre: sayıcılar (74HC163), sync üreten çözücü (latch'li), VRAM, adres seçici (74HC157), font ROM, kaydırma yazmacı, DAC dirençleri.

### En zor kısım: CPU ve video devresi aynı VRAM'e nasıl erişecek?

| Yöntem | Nasıl çalışır | Artı | Eksi |
|---|---|---|---|
| **1. Sadece dikey boşlukta yazma (ilk sürüm için önerim)** | CPU VRAM'e sadece ekranın çizilmediği dikey boşlukta (VBLANK) bağlanır. Yazılım durum bitini bekler | En basit donanım, iki saat birbirinden bağımsız | Kare başına ~1.4 ms pencere. 1 MHz'de karede ~60–90 karakter, tam ekran ~0.3 sn. Oyun için yeterli |
| 2. Zaman paylaşımı (Apple II / C64 tarzı) | CPU saati video saatinden türetilir. Her karakter süresinin yarısı videonun, yarısı CPU'nun | CPU istediği an yazar | Tek saat alanı, tasarım daha sıkı |
| 3. Çift portlu RAM (IDT7132 vb.) | Erişimi donanım halleder | Kolay | Pahalı ve zor bulunur |

İlk sürümde 1 numarayı yapın, vakit kalırsa 2'ye geçin. VRAM'e sadece yazılacağı için ekran kaydırma işini RAM'de tuttuğunuz bir gölge kopyadan yaparsınız.

### VGA'da tipik hatalar (çoğu simülasyonda da yakalanır)

- Boşluk süresince RGB sıfır olmazsa monitör siyah seviyesini yanlış ölçer, renkler soluk veya kayık çıkar. RGB'yi BLANK sinyaliyle AND'leyin.
- VRAM, font ROM ve kaydırma yazmacı zinciri 2 karakterlik gecikme ekler. Sync ve blank sinyallerini de aynı miktarda geciktirin, yoksa görüntü kayar veya son sütun kesilir.
- Sync çözücünün çıkışını latch'lemezseniz sayıcı geçişlerindeki glitch'ler monitörü senkrondan düşürür.
- DAC: monitör girişi 75 Ω, tam beyaz 0.7 V. 2-bit renk kanalı için yaklaşık 680 Ω (yüksek bit) ve 1.3–1.5 kΩ (düşük bit). Bunu Falstad veya LTspice'ta doğrulayın.

Karakter başına renk (ön/arka plan) ve bitmap grafik modu bonus hedef olsun.

---

## 4. C desteği: gerçekçi yol

| Yol | Ne kadar C | İş yükü | Yorum |
|---|---|---|---|
| **Kendi C alt küme derleyiciniz (Python)** | char/int, pointer, dizi, fonksiyon (özyineleme dahil), if/while/for | Orta (1 kişi, ~4–6 hafta) | **Önerim.** Tezde ayrı bir katkı olur. Kod üretimi "16-bit akümülatör + stack" kalıbıyla basit |
| Small-C uyarlaması | K&R'a yakın alt küme | Düşük-orta | 1980'de tam da 8-bit makineler için yazıldı. Kod üretici ~50 kalıptan ibaret |
| LCC uyarlaması | Neredeyse tam C89 | Yüksek | Magic-1 ve Gigatron'da kullanıldı, çalıştığı kanıtlı ama ağır |
| GCC/LLVM | Tam C | Çok yüksek | Mantıksız |

### Araç zinciri

```
oyun.c → [derleyiciniz] → oyun.asm → [customasm] → oyun.bin
                                                     ├→ Python emülatörü
                                                     ├→ Digital simülasyonu (ROM/RAM'e yüklenir)
                                                     └→ gerçek donanım (EEPROM ya da Arduino ile RAM'e)
```

Runtime kütüphanesinde olması gerekenler: `putchar` (VRAM'e yazar, imleç ve kaydırma), basit bir `printf`, `mul/div/mod`, `memset/memcpy`, klavye okuma.

**Hız beklentisi:** 1 MHz'de komut başına ~4–8 mikroadım düşerse saniyede ~125–250 bin komut çalışır. 16-bit `int` işlemleri birkaç komut sürdüğü için C kodu yavaş olur ama Snake, Pong ya da hesap makinesi için yeter. Mümkün olduğunca `char` kullanın.

---

## 5. Neler eklenmeli, neler çıkarılmalı

### Kapsam: 3 seviye

Jüriye en azından 1. seviyesi kesin çalışan bir sistemle gidersiniz.

- **Seviye 1 (mutlaka):** CPU, ROM ve RAM, tüm komut seti, LED/7-segment çıkışı, tek adım/debug donanımı, assembly programları.
- **Seviye 2 (hedef = final demo):** VGA metin modu, C derleyici, C'den ekrana `printf("Merhaba")`, Arduino ile program yükleme, PS/2 klavye, C ile yazılmış Snake.
- **Seviye 3 (bonus):** Renkli karakterler, Pong gibi ek oyunlar, basit ses (sayıcı + kare dalga), monitör programı, seri port.

### Eklemesi mantıklı olanlar

- Debug altyapısı (9. bölüm). Getirisi en yüksek ekleme bu.
- PS/2 klavye: 2 kaydırma yazmacı ve bir sayıcıyla ~4–5 entegre. Snake demosu için gerekli.
- Kendini test eden bir ROM programı: her komutu dener, sonucu ekrana veya LED'e hata kodu olarak yazar.

### Çıkarın ya da hiç başlamayın

- **Kesmeler (interrupt):** Mikrokodu çok karmaşıklaştırır. Durum bitlerini yoklamak (polling) yeter.
- **Pipeline, cache, MMU, 16-bit veri yolu, kayan nokta.**
- **Kablolarla sabitlenmiş (hardwired) kontrol ünitesi:** Her hata kablo değişikliği demektir. Mikrokod ise bir Python betiğiyle yeniden üretilir.
- **74LS181, 6845 CRTC, çift portlu RAM gibi çipler:** Üretimi bitmiş ya da nadir. Bulunamazsa proje durur.
- **74LS ailesi:** 100 entegrede 1–2 A çeker ve ısınır. 74HC bunun çok altında kalır. Tek dikkat noktası: CMOS girişleri boşta bırakılamaz.
- **Mikrodenetleyicinin bilgisayarın işlevsel parçası olması:** Arduino sadece geliştirme ve test aracı olmalı (JTAG gibi). Demo onsuz çalışmalı.

---

## 6. Hangi programları indirmeli

| Araç | Ne için | Not |
|---|---|---|
| **Digital** (github.com/hneemann/Digital) | Ana mantık simülasyonu | Java gerekir (Temurin JDK). 74xx çipler gerçek kılıfında ve pin numaralarıyla var, yani simülasyon aynı zamanda kablolama planınız olur. Sync sinyallerinden görüntü çizen bir VGA monitör bileşeni var. Test vektörleri yerleşik. Verilog/VHDL çıkarabiliyor |
| Python 3 + VS Code | Emülatör, mikrokod üretici, derleyici, test betikleri | |
| customasm | Kendi komut setiniz için assembler | Kuralları bir dosyada tanımlarsınız, assembler yazmanız gerekmez |
| KiCad | Nihai şemalar, malzeme listesi (BOM), netlist'ten kablo listesi | Tasarım Digital'de kesinleşince çizin |
| PulseView (sigrok) | Ucuz lojik analizörün yazılımı | |
| Falstad CircuitJS / LTspice | Analog kısımlar: VGA DAC, reset devresi, 555 | |
| Git + GitHub | Her şeyi sürüm kontrolünde tutun (mikrokod imajları dahil) | |
| (Opsiyonel) Icarus Verilog + GTKWave + IceChips | Gerçek gecikmeli 74xx modelleriyle zamanlama simülasyonu | |
| (Opsiyonel) Logisim-evolution | Digital'e alternatif | Okullarda yaygın ama daha yavaş, sync sinyalinden VGA çizen bileşeni yok |

**Proteus/Multisim:** Okullarda yaygın ama 100 entegreli bir sistemde program koşturmak için yavaş ve VGA desteği yok. Bu proje için önermem.

---

## 7. "Eksiksiz simülasyon" nasıl yapılır

Tek bir simülasyon yetmez. Aynı programı farklı seviyelerde çalıştırıp çıktıları karşılaştırırsınız:

1. **Tek doğruluk kaynağı:** Komut seti ve mikrokod tablosu tek bir dosyada dursun. Bu dosya artık [sim/td8/isa.py](sim/td8/isa.py). Python araçları bu dosyadan şunları üretir: mikrokod ROM imajları, ALU tabloları, assembler'ın komut tablosu, emülatör. Böylece "emülatörde çalışıyor, donanımda çalışmıyor" uyumsuzlukları baştan önlenir.
2. **Komut seviyesinde emülatör (Python):** Hızlıdır, derleyici çıktısını burada test edersiniz. Her komuttan sonra bir iz (trace) satırı yazar: PC, A, B, X, SP, flag'ler.
3. **Mikroadım seviyesinde emülatör:** Emülatör doğrudan mikrokod ROM imajını yorumlayarak çalışsın. Mikrokod hatalarını donanımdan önce bulur ve aynı formatta mikroadım izi üretir.
4. **Çip seviyesinde Digital simülasyonu:** Her modül ayrı bir alt devre olsun (her biri ileride bir veya birkaç breadboard). Her modülün kendi test vektörleri olsun. Sonra tam bilgisayar Digital'de aynı `.bin` dosyasını çalıştırır ve izi emülatörün iziyle karşılaştırılır.
5. **Zamanlama analizi (elle, bir tabloda):** Digital gerçek gecikmeleri modellemez, bunu siz hesaplarsınız. Kritik yol örneği: saat → register çıkışı → bus → ALU (2× 74HC283 taşıma zinciri) → flag → mikrokod flash adresi (SST39SF010A 70 ns; AT28C256 kullanılırsa 150 ns) → kontrol sinyali → bir sonraki saat kenarı.
6. **Donanım:** Aynı test vektörleri Arduino ile breadboard modüllerine uygulanır (9. bölüm).

**Simülasyonun size göstermeyeceği şeyler:** gevşek kontak, boşta kalmış CMOS girişleri, saat hattında çınlama (ringing) ve çift tetikleme, güç düşümü, eksik dekuplaj kondansatörü, EEPROM glitch'leri, bir çıkışa fazla giriş bağlanması (fan-out). Bunlara karşı tek koruma, tasarım kuralları ve **erken yapılmış küçük bir breadboard prototipi**.

---

## 8. Malzeme seçimi

> **Not:** Bu bölüm ilk öneri. Türkiye'de bulunabilirliğe göre güncellenmiş liste ve fiyatlar **14. ve 15. bölümde**.
> - 25.175 MHz yerine 25.000 MHz;
> - 74HC154 yerine 2× 74HC138;
> - AS6C62256 yerine CY62256;
> - BB830 yerine MB-102 + giriş testi;
> - 22 AWG yerine 24 AWG / Cat6.

### Ana çipler

| İşlev | Çip |
|---|---|
| Register | 74HC377 (yükleme enable'ı var). Bus'a çıkış verecekse yanına 74HC541/245 |
| Bus sürücü | 74HC245 / 74HC541 |
| PC, X (16-bit) | 74HC161/163 ×4 (senkron, yüklenebilir sayıcı) |
| SP | ALU üzerinden güncellenir ya da ileri/geri sayan sayıcı (dikkatli tasarım ister) |
| ALU | 74HC283 ×2 + 74HC86 (çıkarma) + 74HC08/32/86 (mantık işlemleri) + 74HC157/153 (sonuç seçimi) |
| Sıfır algılama | 74HC688 |
| Kod çözücü | 74HC138, 74HC154 |
| Mikrokod, font | SST39SF010A (70 ns, ucuz flash) |
| Program ROM | AT28C256 veya SST39SF010A |
| RAM / VRAM | AS6C62256 (32 KB, 55 ns) |
| Saat | 555, 74HC14 (buton titreşimini giderme ve saat tamponu), 1 MHz kristal osilatör, VGA için 25.175 MHz osilatör |

### Kritik araç-gereç

- **EEPROM/flash programlayıcı: XGecu T48 (veya TL866II Plus).** 74xx çiplerini de test edebiliyor. Her çipi breadboard'a takmadan önce test edin.
- **Lojik analizör:** 16 kanallı ucuz bir klon + PulseView. Adres yolunu izlemek için 16 kanal çok işe yarar.
- **Akım sınırlamalı ayarlı güç kaynağı:** Kısa devreyi akım sıçramasından hemen görürsünüz. (Osiloskop zaten var.)
- **Arduino Mega:** 5V ve 54 pinli olduğu için seviye dönüştürücü gerekmez. Debug kartı olarak kullanılacak.
- **Kaliteli breadboard (BB830 vb.):** Ucuz breadboard'lar bu tür projelerde 1 numaralı arıza kaynağı. ~20–25 adet gerekecek. Bazı breadboard'ların güç rayı ortadan kesiktir, kontrol edin.
- 22 AWG (0.6 mm) tek damarlı kablo, birçok renk, kablo sıyırıcı. Her çipe 100 nF, her breadboard'a 10–100 µF kondansatör.
- Sık sökülüp takılan EEPROM'lar için ZIF soket.

### Tedarik uyarıları

- AliExpress'ten gelen AT28C256 ve bazı 74xx'ler sıkça sökme ya da yeniden etiketlenmiş sahte çıkıyor. Bellek çiplerini güvenilir bir distribütörden alın.
- Yurtdışı sipariş ve gümrük haftalar sürebilir. **Toplu siparişi en geç 10. haftada verin.**
- Her çipten 1–2 yedek alın.

### Ölçek tahmini

| Modül | Entegre sayısı |
|---|---|
| Saat / reset / debug | 6–8 |
| A, B, IR, FLAGS + bus | 8–12 |
| ALU | 8–12 |
| PC/SP/X + adres yolu | 14–20 |
| Bellek + adres çözücü | 4–6 |
| Kontrol (adım sayıcı, mikrokod, latch, çözücüler) | 8–10 |
| VGA | 18–25 |
| I/O | 4–8 |
| **Toplam** | **~70–100 entegre, ~20–25 breadboard, 2000'den fazla kablo** |

---

## 9. Breadboard'da hata ayıklama stratejisi

### 9.1 Tasarıma gömülü debug donanımı

- **Saat modülü:** üç mod arasında seçim (ayarlı 555 ile 1 Hz–1 kHz, titreşimsiz tek adım butonu, 1 MHz kristal) + HALT.
- **Bus ve kontrol kelimesi LED'leri:** Her mikroadımda hangi sinyalin aktif olduğunu görürsünüz. LED'leri EEPROM'dan değil, latch'lenmiş kontrol kelimesinden sürün.
- **Manuel kontrol paneli:** Mikrokod takılmadan önce kontrol sinyallerini DIP switch'lerden verirsiniz. Böylece her modül tek başına test edilir.
- **Donanım breakpoint'i:** 2× 74HC688, adres yolu DIP switch'teki değere eşit olunca saati durdurur.
- **Arduino Mega debug kartı (en önemlisi):**
  - Her saat adımında adres, veri ve kontrol kelimesini okuyup PC'ye gönderir.
  - Python betiği bu izi emülatörün mikroadım iziyle karşılaştırır ve **farkın başladığı ilk adımı** söyler. 2000 kabloluk bir sistemde bu, saatlerce LED'e bakmaktan kurtarır.
  - BUSREQ ile CPU'yu durdurup RAM'e program yükler. Her değişiklikte EEPROM yakmanız gerekmez.
  - Test aracı olarak da çalışır: Digital'deki test vektörlerini tek bir modüle uygular. Örneğin ALU'yu tüm 65.536 giriş ve tüm işlemlerle birkaç dakikada test eder.
- **Modülleri bus'a sökülebilir bağlayın** (pin header, jumper veya ribbon kablo). Böylece bir modülü sökmeden devreden ayırabilirsiniz.

### 9.2 Yapım sırası

Her adım test edilmeden sonrakine geçmeyin.

1. Güç dağıtımı (önce çipsiz ölçün), saat, reset. Osiloskopla kontrol edin.
2. Bus, bus LED'leri, manuel kontrol paneli.
3. A ve B registerları: DIP switch'ten bus'a değer koy, yükle, geri oku.
4. ALU ve flag'ler. Arduino ile kapsamlı test.
5. PC, adres yolu, RAM, ROM, adres çözücü.
6. IR, adım sayıcı, mikrokod EEPROM'ları. CPU ilk kez kendi başına çalışır.
7. Kolaydan zora test programları: NOP döngüsü → LDI/OUT → aritmetik → JMP → koşullu dallanma → bellek erişimi → stack/CALL/RET → kendini test eden ROM.
8. **VGA'yı CPU'dan bağımsız, paralel bir iş olarak kurun.** Sıra: önce sadece sync (monitör "640×480 60Hz" diyor mu?), sonra renk çubukları, sonra önceden doldurulmuş VRAM'den sabit yazı, en son CPU bağlantısı.
9. Klavye, seri port, ses.

### 9.3 Çalışma kuralları

- Aynı anda tek değişiklik yapın. Çalışan her durumu Git'e kaydedin (mikrokod imajları dahil).
- Önce statik, sonra dinamik test: çipsiz güç ölçümü → çipleri tak, akıma bak → yavaş saat → hızlı saat.
- Tüm çiplerde 1 numaralı pin aynı yöne baksın, çiplerin üstüne pin etiketi yapıştırın.
- Renk kodu kullanın (kırmızı 5V, siyah GND, sarı veri, mavi adres, beyaz kontrol). Kablolar çiplerin üstünden geçmesin ki çip değiştirebilesiniz.
- Bir lab defteri tutun: her arızanın belirtisi, sebebi ve çözümü. Bu hem tezin "test ve doğrulama" bölümü olur hem de tekrar eden hataları gösterir.
- r/beneater forumuna bakın. Yaşayacağınız arızaların çoğu orada çözülmüş durumda.

### 9.4 Belirtiden sebebe

| Belirti | Olası sebep | Ne yapmalı |
|---|---|---|
| Rastgele davranış, bazen çalışıyor bazen çalışmıyor | Boşta CMOS girişi, gevşek kablo, eksik dekuplaj | Kullanılmayan girişleri 5V'a/GND'ye bağla, 100 nF ekle, kabloyu bastır ya da değiştir |
| Register iki kez yükleniyor, sayıcı 2 atlıyor | Saat hattında çınlama veya yavaş kenar | Saati 74HC14 ile tamponla, saat hattını kısa tut, osiloskopla bak |
| Bir bit hep 1 ya da hep 0 | Kopuk kablo, yanlış delik, ölü çip | Multimetreyle süreklilik ölç, çipi test cihazında dene |
| Çip ısınıyor, akım yüksek | Bus çakışması, ters takılmış çip | Akım sınırlamalı güç kaynağı, bus kaynağını 74HC138 ile seçmek |
| Yavaş saatte çalışıyor, hızlıda bozuluyor | Zamanlama yolu çok uzun, glitch | Lojik analizör, kontrol kelimesini latch'le, saati düşür |
| VGA'da "sinyal yok" | Sync polaritesi veya periyot hatalı | Osiloskopla ölç: 25.000 MHz osilatörle yatay 31.25 kHz, dikey 59.5 Hz olmalı (25.175 MHz'te 31.47 kHz / 59.94 Hz) |
| Görüntü kayık, ilk ya da son sütun bozuk | Pipeline gecikmesi sync ile hizalı değil | Sync'i de aynı sayıda latch'ten geçir |
| Program bir süre çalışıp çöküyor | RAM WE zamanlaması, stack taşması | WE'yi saatin ikinci yarısına sınırla, SP'yi izle |

---

## 10. 12 haftalık simülasyon planı (27 Ekim → Ocak sonu)

> **Not:** Güncel takvim [SISTEM-PLANI.md](SISTEM-PLANI.md) bölüm 13 (simülasyon, 10 hafta) ve bölüm 14'te (yapım, Ocak–Haziran); aşağıdaki tablo ilk taslak.

| Hafta | İş |
|---|---|
| 1 | Araçları kurun. Ben Eater'ın 8-bit ve VGA serilerini izleyin, Gigatron ve James Sharman'ı inceleyin. Gereksinim dokümanını yazın. Digital'de alıştırma yapın (74161 sayıcı, küçük bir VGA sync üreteci) |
| 2 | Komut seti v0, bellek haritası, blok diyagram, kontrol sinyali listesi. `isa.yaml` ve Python emülatörünün iskeleti |
| 3 | Emülatör, customasm kuralları, ilk assembly testleri. Digital'de saat/reset/register/bus modülleri ve testleri |
| 4 | Digital'de ALU, flag'ler, PC, adres yolu, bellek. **Küçük bir prototip siparişi** (birkaç breadboard, birkaç 74HC, 555) |
| 5 | Kontrol ünitesi ve mikrokod üretici. Digital'de ilk program çalışır |
| 6 | Tüm komut seti, iz karşılaştırma (emülatör ↔ Digital). **Gerçek breadboard'da saat modülü ve bir register**: breadboard'ın gerçek sorunlarını erkenden görün |
| 7 | VGA zamanlama devresi (Digital'in VGA monitörüyle), test deseni |
| 8 | Metin modu: VRAM, font ROM, kaydırma yazmacı, CPU–VRAM bağlantısı |
| 9 | C derleyici ve runtime. Emülatörde `printf` çalışır |
| 10 | Tam sistem Digital'de C programı çalıştırıp VGA'ya yazar. Arduino debug kartının tasarımı ve yazılımı. **Kalan malzemenin siparişi.** Stoğu azalan parçalar 1. haftada alınır (15. bölüm). |
| 11 | Zamanlama analizi, KiCad şemaları, breadboard yerleşim planı (hangi modül hangi kartta), malzeme listesi |
| 12 | Tasarımı dondurma, danışman incelemesi, donanım test planı, gecikmeler için tampon |

### İş bölümü (2 kişi)

| Kişi | Sorumluluk |
|---|---|
| Kişi 1 — Donanım | Veri yolu (register, ALU, PC, bellek), VGA modülü, PS/2 klavye arayüzü |
| Kişi 2 — Kontrol ve yazılım | Kontrol ünitesi, mikrokod, emülatör, assembler, C derleyici, runtime, Arduino debug kartı, Snake |

Simülasyon aşamasında Kişi 2'nin listesi daha uzun görünür. Yapım aşamasında ise kablolama yükü Kişi 1'e biner, o yüzden yapımda kablolamayı paylaşın.

---

## 11. Kaynaklar

- **Ben Eater:** "8-bit breadboard computer" serisi, "World's worst video card" (VGA), 6502 serisi (PS/2 klavye bölümleri)
- **Gigatron TTL computer:** 74xx + VGA + C'nin bir arada mümkün olduğunun kanıtı
- **James Sharman (YouTube):** breadboard'da pipeline'lı 8-bit CPU, VGA ve ses
- **Bill Buzbee, Magic-1:** ev yapımı TTL bilgisayar, LCC ile C
- ***The Elements of Computing Systems* (Nand2Tetris):** mantık kapısından derleyiciye kadar tüm katmanlar
- **Malvino & Brown, *Digital Computer Electronics*:** SAP-1/2/3 mimarileri
- **Harris & Harris, *Digital Design and Computer Architecture***
- **Nora Sandler, *Writing a C Compiler*** ve **rui314/chibicc:** derleyicinin commit commit nasıl yazıldığını gösterir
- **tinyvga.com:** VGA zamanlama tabloları

---

## 12. Açık noktalar ve sonraki adım

**Tamamlananlar**
- Komut seti v0 (TD-8): 13. bölüm.
- Bütçe: 14. bölüm.
- Doğrulama: [tasarim-taslaklari/DOGRULAMA.md](tasarim-taslaklari/DOGRULAMA.md).

**Cevaplanan sorular**
- Danışman kendi komut setimizi onayladı.
- Okulda ayarlı güç kaynağı ve EEPROM programlayıcı var.
- Üniversiteden MODEL muafiyeti yazısı alınabiliyor.

- Yapım Ocak'ta başlıyor; süre Haziran'a kadar.

**Sonraki adım**
- Simülasyona başlandı. Komut seti artık `isa.yaml` yerine [sim/td8/isa.py](sim/td8/isa.py) içinde tanımlı; ROM imajları, emülatörler ve testler hazır ([sim/README.md](sim/README.md)).
- Digital'de ilk modül: 4 fazlı saat (SISTEM-PLANI.md bölüm 12).
- Stoğu azalan parçaları alın (15. bölüm).

---

## 13. Komut seti v0: TD-8 (özet)

Ayrıntılı tasarım İngilizce olarak [tasarim-taslaklari/ISA-v0-sentez.md](tasarim-taslaklari/ISA-v0-sentez.md) dosyasında: tüm mikroadım tabloları, kontrol kelimesinin bitleri, ALU işlem kodları ve zamanlama analizleri. Üç ayrı tasarım önerisi hazırlandı (en az çip / C dostu / hata ayıklanabilir). Hata ayıklanabilir öneri temel alındı, diğer ikisinin iyi fikirleri eklendi ve bulunan hatalar düzeltildi. Düzeltmelerin ve Türkiye'deki parça durumunun ayrıntıları [tasarim-taslaklari/DOGRULAMA.md](tasarim-taslaklari/DOGRULAMA.md) dosyasında.

### 13.1 Programcının gördüğü model

| Register | Genişlik | Not |
|---|---|---|
| **A** | 8 | Akümülatör. Tüm ALU işlemlerinin hem sol girişi hem hedefi. |
| **X** | 16 | Pointer. Yalnızca yüklenir, geri okunamaz. Erişim `(X)` ve `(X+)` ile; artırma ek çevrim istemez. |
| **SP** | 8 | Stack `EF00–EFFF` sayfasında, açılışta `FF`. Yalnızca dönüş adresleri ve PHA/PLA için. |
| **PC** | 16 | Açılışta `0000`. |
| **F** | Z C N V | Yalnızca ALU işlemleri değiştirir; yükleme, saklama ve dallanma flag'lere dokunmaz. ADC/SBC/CPC'de Z zincirlenir, böylece 16-bit karşılaştırma tam doğru çıkar. |

Gizli registerlar: IR, AR (16-bit adres registerı), STEP (mikroadım sayacı).

### 13.2 Komut seti: 53 komut, 88 opcode

| Grup | Komutlar | Adresleme / opcode | Çevrim (1 MHz'de µs) |
|---|---|---|---|
| Bellek ve ALU | LDA STA ADD ADC SUB SBC AND OR XOR CMP CPC BIT | `#n`, `abs`, `(X)`, `(X+)`; opcode = `0x40 + 4·işlem + mod` | 2 / 4 / 2 / 2 |
| A üzerinde tekli | INC DEC NOT NEG SHL ROL SHR ROR ASR TST CLC SEC SEX | `80–8C` | 2 |
| X | LDX #nn, LDX abs, INX, TAXL, TAXH | `90–94` | 3 / 5 / 2 / 2 / 2 |
| 16-bit bellek | INCW abs, DECW abs | `98–99` | 7 |
| Stack ve akış | PHA PLA JMP CALL RET JMPI | `A0–A5` | 2 / 3 / 4 / 5 / 5 / 7 |
| Koşullu dallanma | BEQ BNE BCS BCC BMI BPL BVS BVC BLT BGE BGT BLE BHI BLS (mutlak adres) | `B0–BD` | 4 alınırsa / 3 alınmazsa |
| Diğer | NOP, HALT | `01`, `00` | 2 |

- **Tanımsız opcode'lar** makineyi durdurur. `FF` (silinmiş flash) ve `00` (boş RAM) de buna dahil, yani program kontrolsüz koşmaz.
- **Flag'ler mikrokodun adres bitleri** olduğu için koşullu dallanma için ayrıca devre gerekmiyor. İşaretli ve işaretsiz 14 koşulun hepsi tablo içeriğinden çıkıyor.

### 13.3 Donanım özeti

- **Saat: 4 fazlı.**
  - 4 MHz osilatörden 1 MHz CPU saati elde edilir. Tüm registerlar tek bir kenarda yüklenir.
  - Kontrol kelimesi bu kenardan çeyrek çevrim sonra değişir. RAM'in /WE sinyali yalnızca A fazında aktiftir. Bu yüzden "aynı kenar yarışı" oluşmaz.
  - Saat kaynakları: 4 MHz osilatör; 555 (0.25 Hz–1 kHz); tek adım (mikroadım ya da komut bazında); Arduino.
- **Kontrol ünitesi.**
  - 3 flash 24-bitlik kontrol kelimesini üretir. Kelime 3× 74HC273'te tutulur ve 24 LED'de görünür.
  - Manuel panel: mikrokodun çıkışı kapatılır ve 24 DIP switch ile istenen kelime elle verilir.
- **ALU.**
  - 2 flash'tan oluşan bir tablo: biri alt, biri üst nibble için. 25 işlemi var ve her biri tek çevrimde biter.
  - Tablolar, emülatörün ALU'su ile aynı Python kodundan üretilir. Bu yüzden donanım ile emülatör farklı sonuç veremez.
- **Bus.**
  - Veri yolunun kaynağını bir 74HC138, adres yolunun kaynağını bir 74HC139 seçer. İki sürücü yapısı gereği aynı anda açılamaz.
- **Bellek ve I/O.**
  - ROM: SST39SF010, 32 KB. 4 program bankı jumper ile seçilir.
  - RAM: CY62256, 28 KB görünür.
  - VRAM: ayrı bir CY62256.
  - `F800` okununca klavye byte'ı gelir, yazılınca 8 LED'e gider.
  - `F801` durum registerıdır: b7 = klavye hazır, b6 = VRAM penceresi açık, b5–b0 = DIP switch'ler.
- **VGA.**
  - Kendi 25 MHz saatiyle CPU'dan bağımsız çalışır.
  - 40×30 metin gösterir: 8×8 font iki kat büyütülür. Tek renklidir; jumper ile beyaz, yeşil ya da amber seçilir.
  - Porch ve sync değerleri zamanlama ROM'unda durur. Değiştirmek için ROM'u yeniden yazmak yeter.
  - CPU VRAM'e yalnızca dikey boşlukta yazar (kare başına ~1.3 ms). Pencere kapalıyken yazmaya çalışan CPU bekletilir, yani yazma hiç kaybolmaz.
- **PS/2 klavye.**
  - 2× 74HC164 kullanılır; start biti çerçevenin bittiğini gösteren işaret olarak çalışır.
  - Bir byte okunmayı beklerken klavye susturulur (inhibit). Bu sayede byte kaybolmaz.
- **Hata ayıklama.**
  - Donanım breakpoint'i ve watchpoint (2× 74HC688).
  - HALT komutu yazılım breakpoint'i olarak kullanılabilir.
  - MARK biti osiloskopu tetiklemek için.
  - Arduino BUSREQ ile CPU'yu durdurup inceler ve kaldığı yerden devam ettirir.
  - İz modu: saati Arduino verir ve her çevrimde adres yolunu, veri yolunu ve kontrol kelimesini emülatörle karşılaştırır.

### 13.4 Modüller ve ölçek

| Modül | Entegre | Breadboard |
|---|---|---|
| Veri yolu: PC, AR, X, SP, F, A, IR, tamponlar, ALU | 30 | 8 |
| Kontrol ünitesi | 13 | 4 |
| Saat / reset / durdurma | 14 | 3 |
| CPU yardımcı kapıları | 4 | diğer kartlarda |
| Bellek + I/O | 6 | 2 |
| PS/2 | 6 | 1 |
| VGA | 19 | 5 |
| Güç dağıtımı / LED | – | 1 |
| **Toplam** | **92** | **24** (30 alınacak) |

- Yaklaşık **1.850 kablo** gerekiyor. Bu, 120–180 kişi-saat demek.
- Saat hızı:
  - 1 MHz, datasheet'teki en kötü değerlerle bile her yolda garanti.
  - 2 MHz yalnızca tipik değerlerle tutuyor; hedef değil, olursa bonus.

### 13.5 C eşlemesi

- **Desteklenen alt küme:**
  - Tipler: `char` (işaretsiz), `int` (16-bit), pointer'lar.
  - Global diziler; ROM'da `const` tablolar; `volatile`.
  - Deyimler: if, while, for, switch.
  - Tüm operatörler. `* / %` runtime kütüphanesindedir.
  - `asm()` ile satır içi assembly.
- **v1'de olmayanlar:** recursion, struct, long, float, fonksiyon pointer'ı.
- **Çağırma kuralı: statik çerçeve.**
  - Her fonksiyonun parametreleri ve yerel değişkenleri sabit RAM adreslerinde durur. Aynı anda çalışamayacak fonksiyonların çerçeveleri, çağrı grafiğine göre aynı alanı paylaşır.
  - Stack'te yalnızca dönüş adresleri tutulur.
  - Dönüş değeri: `char` A'da, `int` `__rv`'de.
  - Seçilme sebebi: stack'e göre adresleme 16-bit bir adres toplayıcı (~6 entegre) gerektirir. Ayrıca statik değişkenler Arduino izinde adıyla okunabilir.
- **Örnek maliyetler (1 MHz'de µs):**

  | Kod | µs |
  |---|---|
  | `a = b + c` (int) | 24 |
  | `*p = x` | 11 |
  | `if (x < y)` | 19–20 |
  | 2 int parametreli çağrı + dönüş | 82 |
  | VRAM'e string yazma | 37 / karakter |
  | Ekran temizleme | ~2.700 |
- **Snake:**
  - Hamle başına ~0.6 ms sürer. Saniyede 8 hamlede CPU %99 boş kalır.
  - VRAM okunamadığı için oyun tahtasının bir kopyası RAM'de tutulur.
  - Konum `satır·64 + sütun` olarak saklanır, böylece hareket `pos += yön` olur.

### 13.6 Başlıca riskler ve daraltma sırası

| Risk | Önlem |
|---|---|
| Yapım hacmi: 92 entegre, ~1.850 kablo | Modül modül, manuel panelle test. Daraltma sırası: LED portu → breakpoint → 2 MHz → renk. |
| VGA nokta hızındaki LD yolu (80 ns'ye karşı en kötü ~85 ns) | İlk osiloskop testi bu yol. Yedek: 163'ün TC çıkışı ya da 74HCT/74AC. |
| Flash/SRAM çıkış seviyesi (VOH, yalnız 2.4 V garanti) | İlk gün ölçün. Gerekirse HCT'ye geçin (bütçede yedeği var). |
| PS/2 inhibit zamanlaması | Simülasyon döneminde gerçek klavyeyle prototip kurun. |
| Flash tedariki (DIP üretimden kalktı) | Yerli 6 adedi hemen alın, ithal ek paketi erken verin (15. bölüm). |

---

## 14. Malzeme ve bütçe (30.000 TL)

- Fiyatlar 26–27 Ekim 2026 tarihli ve KDV dahil. Kaynak: `tasarim-taslaklari/research-*.json`. Kur: USD 49.76, EUR 55.75 TL.
- Mağaza fiyatları kura bağlı, Ocak'a kadar %5–10 artış bekleyin.
- 2026'dan beri yurtdışından gelen her e-ticaret paketi tam gümrük beyanı istiyor. Haber ve şikâyet örneklerine göre paket başına ~4.000–6.000 TL ek masraf çıkıyor. **Bu yüzden ithal edilecek tek kalem flash çipleri.**

### 14.1 Stoğu azalanlar: hemen alınacaklar (yerli)

| Parça | Adet | Nereden | TL |
|---|---|---|---|
| SST39SF010-90 flash (DIP-32, eski stok) | 6 (2 lot) | n11, ackelektronik | 1.159 |
| CY62256LL-70PC SRAM | 4 (2 lot) | n11, ackelektronik | 1.850 |
| 25.000 MHz osilatör (**son lot**) | 5 | n11, ackelektronik | 463 |
| 4.000 MHz osilatör | 4 | n11, ackelektronik | 555 |
| 74HC161 (**son lot**) | 25 | n11, ackelektronik | 463 |
| 74HC163 | 25 | n11, ackelektronik | 562 |
| PC74HCT688P (**son lot**) | 6 | n11, ackelektronik | 333 |
| 74HC191 (mağazada yalnız 16 adet var) | 4 | direnc.net | 65 |
| **Ara toplam** | | | **5.450** |

### 14.2 Diğer mantık entegreleri (yedekleriyle)

| Parça | Adet | TL |
|---|---|---|
| 74HC245 | 17 | 206 |
| 74HC377 (n11'de tekil; yerine 2× 74HC163 de olur) | 5 | 611 |
| 74HC166 (n11'de tekil) | 2 | 237 |
| 74HC175 (Özdisan) | 3 | 152 |
| 74HC138 (74HC27'nin yerini de tutuyor) | 5 | 55 |
| 74HC157 | 4 | 81 |
| 74HC273 | 4 | 46 |
| 74HC74 | 7 | 65 |
| 74HC08 | 5 | 91 |
| 74HC540 | 2 | 55 |
| 74HC20 (74HC11'in yerini de tutuyor) | 3 | 52 |
| 74HC00 / 02 / 04 / 14 / 32 | 4 / 2 / 3 / 3 / 3 | 132 |
| 74HC139 / 153 / 164 | 2 / 2 / 3 | 89 |
| NE555 ×2, TLC555, 2N7000, 1N4148 | | 63 |
| HCT yedeği, VOH ölçümü kötü çıkarsa (tahmin) | | 600 |
| Kargo, 6–7 mağaza (tahmin) | | 500 |
| **Ara toplam** | | **3.035** |

### 14.3 İthal: tek paket

| Parça | TL |
|---|---|
| SST39SF010A-70 DIP ×10, AliExpress (≈17.7 €) | 986 |

- Öğrenci "MODEL" muafiyetiyle gelmesi gerekiyor: gönderi başına ≤30 €, üniversite yazısı şart.
- Muafiyet alınamazsa gümrük işlemi +4.000–6.000 TL tutar. Bu durumda para yedekten çıkar.
- Gelen her çip T48'de silinip yazılıp doğrulanır.

### 14.4 Araçlar

| Parça | TL |
|---|---|
| ~~XGecu T48 programlayıcı~~ (okulda var, alınmayacak) | 0 |
| 40 pinli ZIF soket ×4 (sık yazılan flash'lar için) | 232 |
| Arduino Mega klonu | 834 |
| 8 kanallı lojik analizör (PulseView ile) | 374 |
| Kablo sıyırıcı (Pro'sKit 6PK-223) | 580 |
| ESD cımbız, IC sökücü (tahmin) | 259 |
| **Ara toplam** | **2.279** |

**Okuldaki programlayıcı:**
- SST39SF010A ve 74xx mantık testini desteklediğini kontrol edin. T48 ya da TL866 ise destekliyor.
- Mikrokod ve ALU flash'ları yapımda onlarca kez yeniden yazılacak. Programlayıcıya düzenli erişiminiz olmalı; olmayacaksa T48 (4.359 TL) yedekten alınabilir.

### 14.5 Breadboard, kablo, pasif malzeme, konnektörler

| Parça | TL |
|---|---|
| MB-102 830 delik ×30 (24 gerekli, gerisi bozuk çıkanlar için) | 1.656 |
| 24 AWG tek damar kablo, 25 m × 6 renk | 1.706 |
| Hazır jumper seti (560 adet) | 262 |
| 3 mm LED ×300 | 174 |
| Direnç seti + SIP direnç dizileri | 347 |
| 100 nF ×200 + elektrolitik ×30 | 444 |
| DIP switch ×10, buton ×20, anahtar ×6 (anahtarlar tahmin) | 196 |
| Dupont şerit kablolar | 169 |
| Mini-DIN-6 ×2, HD15 dişi ×2 | 159 |
| **Ara toplam** | **5.113** |

### 14.6 Toplam

| Kalem | TL |
|---|---|
| 14.1 Stoğu azalanlar | 5.450 |
| 14.2 Diğer mantık entegreleri | 3.035 |
| 14.3 İthal flash | 986 |
| 14.4 Araçlar | 2.279 |
| 14.5 Breadboard / kablo / pasif | 5.113 |
| PS/2 klavye (KEEPRO, gerçek PS/2 fişli) | 640 |
| Güç kaynağı (okulda var) | 0 |
| **Toplam** | **17.503** |
| **Yedek** | **12.497 (%42)** |

Yedek para şunlar için ayrıldı:
- Aralık'a kadarki fiyat artışı (%5–10);
- gümrük muafiyetinin alınamaması (+4.000–6.000 TL);
- bozuk çıkan parçalar;
- gerekirse programlayıcı.

Yedek bunlardan sonra da kalırsa en faydalı ek: 16 kanallı lojik analizör (Kingst LA1010, 5.114 TL), çünkü 16-bit adres yolunu tek seferde izler.

---

## 15. Hemen yapılacaklar (bu hafta)

1. **14.1'deki parçaları alın (5.450 TL).** "Son lot" yazanlar tükenirse yerine konacak yerli parça yok.
2. **PS/2 klavyeyi alın (640 TL).** Gerçek PS/2 fişli olmalı; yeşil adaptörlü USB klavye olmaz. PS/2 prototipi için şimdi gerekiyor.
3. **Okuldaki programlayıcıya erişimi ayarlayın.** Flash ve ALU prototipi için simülasyon döneminde lazım. Ayrıca SST39SF010'u desteklediğini kontrol edin.
4. **Üniversiteden MODEL muafiyeti yazısını isteyin.** AliExpress flash siparişini yazı gelince, **en geç 16 Kasım'a kadar** verin, çünkü kargo 2–5 hafta sürebilir. Tek paket olsun, ≤30 €.
5. **Kalan malzemeyi 1–7 Aralık arasında sipariş edin** (14.2 ve 14.5). Böylece Ocak'tan önce gelir ve test edilir.
6. **Gelen parçaları test edin:**
   - her entegreyi programlayıcının lojik testinden geçirin;
   - her flash'ı silip yazıp doğrulayın;
   - her breadboard'un tüm şeritlerini süreklilik testinden geçirin;
   - kötü çıkanları işaretleyip ayırın.
7. **Simülasyon döneminde küçük prototipler kurun:**
   - a. 4 fazlı saat + bir 161 + bir 245, STOP/GO ile;
   - b. flash iş akışı + DIP switch'lere bağlı bir ALU ROM'u (burada VOH ölçülür);
   - c. 25 MHz → LD → 166 zinciri gerçek monitörde (ilk iş: monitör sync'i tanıyor mu?);
   - d. PS/2 alıcısı, LED'ler ve gerçek klavye;
   - e. A fazı strobe'uyla SRAM yazma.
