# Hafta 2 (3–9 Kasım 2026): araştırma ve assembly simülasyonu

## 1. Araştırma: neyi neden seçtik

Danışmanın sorabileceği sorular ve cevapları. Kaynaklar: [PROJE-PLANI.md](../../PROJE-PLANI.md) bölüm 1, 4, 5, 6, 13 ve [tasarim-taslaklari/ISA-v0-sentez.md](../../tasarim-taslaklari/ISA-v0-sentez.md).

### Neden hazır bir işlemci (6502, Z80) kullanmıyoruz?

Hazır işlemciyle bilgisayarın geri kalanını biz kurarız ama işlemciyi biz tasarlamamış oluruz. Projenin amacı işlemcinin kendisini 74HC lojik entegrelerle kurmak.

Hazır işlemci yolu daha az riskli: 6502 için cc65, Z80 için SDCC gibi hazır C derleyicileri var. Bu yüzden yedek plan olarak duruyor. W65C02 hâlâ üretiliyor. Zilog ise bağımsız Z80'in üretimini 2024'te durdurdu.

### Piyasada hazır kitler var mı? Avantajları ne?

| Kit | Nedir | Avantajı | Neden seçmedik |
|---|---|---|---|
| Ben Eater 8-bit | Breadboard üzerinde SAP-1 tabanlı eğitim bilgisayarı | Adım adım video anlatımı, denenmiş tasarım | 4-bit adres, 16 byte RAM: C ve VGA mümkün değil. Tasarım bize ait olmaz. |
| RC2014 | Z80 tabanlı, kartları bir ana karta takılan modüler bilgisayar | BASIC ve CP/M hazır çalışır | İşlemci hazır Z80, kartlar hazır. Tasarım katkısı az. |
| Gigatron TTL | Mikroişlemcisiz, ~35 TTL entegreli bilgisayar; VGA'yı yazılımla üretir | Az entegreyle ekran ve oyun | Tasarım ve ROM hazır, kopyalamış oluruz. 6,25 MHz breadboard'da zor. |
| FPGA kartı | İşlemciyi Verilog/VHDL ile tarif edip çipe yüklemek | Hızlı, kablolama hatası yok | Proje kararı: FPGA yok, gerçek entegrelerle breadboard. |

Hazır kitlerden fikir aldık: breadboard'da modül modül kurma ve mikrokodu EEPROM'a yazma Ben Eater'dan, ekran üretme fikirleri Gigatron'dan.

Hazır parça kullandığımız yerler, tasarımın konusu olmayan kısımlar: kristal osilatörler (4 MHz CPU saati, 25 MHz VGA saati), flash ve SRAM bellek çipleri. Arduino yalnızca test ve program yükleme aracı; final demosu Arduino'suz çalışacak.

### Hangi komut setini kullanıyoruz?

Kendi tasarladığımız **TD-8** komut setini. Önce üç ayrı öneri hazırlandı ve karşılaştırıldı:

| Öneri | Entegre | Öne çıkan yanı |
|---|---|---|
| En az çip | 54 | Ucuz ve küçük, ama C için zayıf |
| C dostu | 96 | 16-bit karşılaştırmalar, INCW/DECW, 14 dallanma koşulu |
| Hata ayıklanabilir | 115 | En temiz zamanlama, en iyi hata ayıklama altyapısı |

Hata ayıklanabilir öneri temel alındı, diğer ikisinin iyi fikirleri eklendi, bulunan hatalar düzeltildi ve entegre sayısı 92'ye indirildi. Danışman onayladı.

TD-8'in özellikleri:
- 8-bit veri, 16-bit adres (64 KB).
- 53 komut, 88 opcode.
- Registerlar: A (akümülatör), X (16-bit gösterici), SP, PC; flag'ler Z C N V.
- 14 dallanma koşulu, işaretli ve işaretsiz 16-bit karşılaştırmaların hepsi doğru.
- Tanımsız opcode makineyi durdurur, boş bellekte program kontrolsüz koşmaz.

Akümülatörlü yapıyı seçtik çünkü ALU'ya tek register bağlanıyor, entegre sayısı düşüyor. C derleyicisi de statik çerçeveyle basit kalıyor.

### Kontrol ünitesi neden mikrokodlu?

Kablolu (hardwired) kontrolde her hata kablo değişikliği demek. Mikrokodlu kontrolde komutların adımları flash çiplerde duruyor; bir hatayı düzeltmek için Python'dan yeni imaj üretip çipe yazmak yetiyor.

Flag'ler mikrokod adresinin parçası olduğu için koşullu dallanma ek devre istemiyor. Bir jumper ile denenmiş ve deneysel iki mikrokod arasında geçiş yapılabiliyor.

### ALU neden flash tablosu?

74HC181 ALU entegresinin üretimi bitti. Toplayıcı (74HC283) ve kapılarla 25 işlem yapmak çok entegre ister. ALU'yu 2 flash çipte hazır sonuç tablosu olarak tutuyoruz: işlem eklemek ya da düzeltmek yeni tablo üretmek demek. Tablo, 8 milyon girişin hepsinde Python'daki referans ALU ile karşılaştırıldı.

### Neden 74HC, 74LS değil?

92 entegrede 74LS ailesi 1–2 A çeker ve ısınır, 74HC bunun çok altında kalır. 74HC'de dikkat edilecek tek nokta: CMOS girişleri boşta bırakılamaz.

### Hangi programlama dilini kullanıyoruz?

| Ne | Dil | Neden |
|---|---|---|
| Araçlar (ROM üreticileri, assembler, emülatörler, testler) | Python 3.12 | Hızlı geliştirme, ek paket gerekmiyor, test yazmak kolay. Hız sorun değil: emülatör saniyede 0,36–1,7 milyon çevrim çalıştırıyor, gerçek makine 1 milyon. |
| TD-8 programları, şimdi | TD-8 assembly | Derleyici gelene kadar programlar ve kütüphane assembly ile yazılıyor. |
| TD-8 programları, yapım döneminde | C'nin bir alt kümesi | Kendi derleyicimiz (`tdcc`, Python ile). Snake demosu C ile yazılacak. |

GCC ya da LLVM'i yeni bir 8-bit akümülatörlü işlemciye uyarlamak aylar sürer, bu proje için gerçekçi değil. Small-C ve LCC uyarlamaları da incelendi. Kendi küçük derleyicimizi seçtik çünkü statik çerçeve sayesinde kod üretimi basit kalıyor ve tezde ayrı bir katkı oluyor.

### Hangi assembler'ı kullanıyoruz?

Kendi yazdığımız assembler'ı: `sim/td8/asm.py` (~400 satır, iki geçişli).

Plan, kuralları bir dosyada tanımlanan genel amaçlı **customasm**'i öneriyordu. Kendi assembler'ımızı seçme nedenlerimiz:
- Opcode tablosunu doğrudan `isa.py`'den okuyor. Komut seti değişince assembler kendiliğinden güncelleniyor, iki yerde tutulan tablo birbirinden kaymıyor.
- Emülatör ve testlerle aynı Python kodunun içinde, ek kurulum yok.
- Hata mesajları Türkçe; `.include` ile kütüphane dosyası eklenebiliyor (bu hafta eklendi).
- C derleyicisinin çıktısını doğrudan alacak.

ca65, vasm, sjasmplus gibi hazır assembler'lar 6502 ve Z80 gibi var olan işlemciler için yazılmış, bizim komut setimizi bilmiyorlar.

### Simülasyonu nasıl yapıyoruz?

İki katman var:
- **Python emülatörü:** Programın "doğru cevabını" veriyor. Biri devredeki gibi mikroadım mikroadım, diğeri komut komut çalışıyor ve birbirini kontrol ediyor.
- **Devre simülasyonu:** Kablolamayı doğruluyor. Abdurrahman saat modülünü Proteus'ta kurdu.

Devre, aynı programda emülatörden farklı davranırsa hata devrededir.

## 2. Assembly simülasyonu: çalışma zamanı kütüphanesi

C derleyicisinin ileride ihtiyaç duyacağı rutinler şimdiden TD-8 assembly'sinde yazıldı ve emülatörde test edildi: [sim/lib/runtime.asm](../../sim/lib/runtime.asm).

| Rutin | Ne yapar | Ortalama çevrim | En kötü | Plandaki tahmin |
|---|---|---|---|---|
| `__mul16` | 16-bit çarpma (kaydır-topla) | ~1.070 | ~1.240 | 250–400 |
| `__mul16`, çarpan < 256 | | ~500 | ~630 | |
| `__divmod16` | 16-bit bölme ve kalan | ~1.250–1.380 | ~1.590 | 600–900 |
| `print_u16` | Sayıyı ekrana ondalık yazar | ~1.200 | ~2.050 | |
| `puts` | Metni ekrana yazar | | | |

1 MHz'de 1 çevrim = 1 µs. Ölçümler 400'er rastgele girişle, CALL ve RET dahil.

**Bulgu:** Plandaki çarpma ve bölme tahminleri 2–3 kat iyimserdi. Sonuçları:
- C derleyicisi sabitle çarpma ve bölmeyi kaydırmaya çevirecek. Örneğin Snake'teki `satır*64` 6 kaydırma ile yapılır.
- Döngülerde `* / %` kullanmaktan kaçınılacak.
- Snake'in tasarımı zaten bölme kullanmıyor: skor ondalık karakter olarak tutuluyor.

**Test sırasında bulunan gereksiz kod:** Bölme rutinine kalanın 17 bite taşması için bir kontrol koymuştum. Testlerin bu satırı silince hiçbir şey yakalamadığını gördüm. Hesap: k. turda kalan 2^k'den küçük olduğu için 16-bit bölmede taşma hiç olmuyor. Satır kaldırıldı, bölme her çağrıda 48 çevrim kısaldı.

### Demo programları

**`examples/fibonacci.asm`:** 16-bit Fibonacci sayıları, F0'dan F24 = 46368'e kadar (16 bite sığan son terim). 33.170 çevrim = 33 ms.

```
> py cli.py run examples/fibonacci.asm
 FIBONACCI SAYILARI (16-BIT)

 F0  =     0
 F1  =     1
 ...
 F23 = 28657
 F24 = 46368
```

**`examples/asal.asm`:** 1000'den küçük asal sayılar, deneme bölmesiyle. 168 asalın hepsi doğru bulunuyor. 3.748.290 çevrim, yani gerçek makinede 1 MHz'de ~3,7 saniye.

```
> py cli.py run examples/asal.asm --ref --cycles 20000000
 1000'DEN KUCUK ASAL SAYILAR

    2    3    5    7   11   13   17   19
   23   29   31   37   41   43   47   53
 ...
  947  953  967  971  977  983  991  997

 TOPLAM ASAL SAYISI: 168
```

### Testler

34 otomatik test, hepsi geçiyor (geçen hafta 27). Yeni testler:
- `__mul16` ve `__divmod16`: 400'er girişte Python'un sonucuyla aynı. Bölen 0 olduğunda da makine kilitlenmiyor.
- İki emülatör (mikroadım ve komut seviyesi) aynı sonucu ve aynı çevrim sayısını veriyor.
- `print_u16`: sınır değerlerde ve 100 rastgele sayıda doğru.
- İki demo, beklenen ekranı üretiyor.
- Assembler'ın `.include` yönergesi.

Testlerin gerçekten hata yakaladığı denendi: çarpmada ADC yerine ADD yazınca 200 girişin 153'ünde, yazdırmada TST silinince 55'inde hata çıkıyor.

## Kullanılan araçlar

Python 3.12 (yalnızca standart kütüphane), unittest, Git/GitHub. Bu hafta yeni program indirmek gerekmedi.

## Gelecek hafta

- C derleyicisine (`tdcc`) başlamak: lexer ve parser. Emülatör ve runtime hazır olduğu için plandaki Ocak tarihini beklemeye gerek yok.
- İlk hedef: C ile yazılmış "MERHABA" programının emülatörde çalışması.
