# ISA v0 (TD-8) doğrulama notları

> 27 Ekim 2026 · Kaynak: [ISA-v0-sentez.md](ISA-v0-sentez.md) (İngilizce, ayrıntılı tasarım)
> Bu dosyada sentezin kontrolü var: neye bakıldı, ne doğru çıktı, ne düzeltilmeli, simülasyonda ne doğrulanacak.

## 1. Kontrol edilip doğru bulunanlar

- **4 fazlı saat (Johnson sayıcı).** Geçişler A→B→C→D. STOP makineyi C'de, WAIT ise D'de tutuyor. CLK (=Q2) B→C'de yükseliyor: tek "commit" kenarı bu. LCLK C→D'de kontrol kelimesini yüklüyor. WSTB yalnız A fazında aktif. Sonraki durum mantığı 4 NAND kapısına sığıyor.
- **Mikrokod.** Adım adım izlenen komutlar: FETCH, CALL, RET, PHA, PLA, JMP, JMPI, INCW/DECW, Bcc, LDX abs, STA abs.
  - Stack boş-azalan çalışıyor. CALL'dan sonra PCH [SP0]'da, PCL [SP0−1]'de ve SP = SP0−2. RET bunu tam tersine çeviriyor.
  - Çevrim sayıları tablolarla tutarlı.
- **Kontrol kelimesi.** 24 bit, 3 flash'ta. Tümü sıfır kelime gerçekten NOP. Öneri 1'deki /FL kutup hatası giderilmiş.
- **Flash adres sığması.** Mikrokod adresi 17 bit: adım 4 + IR 8 + flag 4 + bank 1. ALU tabloları da 17'şer bit. SST39SF010A'ya tam sığıyorlar.
- **ALU nibble bölmesi.** SHL/ROL/ROR/ASR/SEX/NEG ve V için gereken her giriş adres pinlerinde var: A4, A7, c4, Zlo, Z.
- **Zincirli Z.** `LDA lo; CMP lo; LDA hi; CPC hi; Bcc` dizisi 16-bit karşılaştırmaların altısını da doğru veriyor. Bunun sebebi yükleme komutlarının flag'lere dokunmaması.
- **C kod dizileri.** Bölüm 9.3'teki dizilerin çevrimleri tek tek sayıldı: 24, 11, 19–20, 82 ve karakter başına 37. Hepsi tutarlı.
- **PS/2 alıcısı.** 11. yükselen kenarda start biti SR2.Q2'ye (KRDY) geliyor ve veri bitlerinin yerleri doğru. Okuma sonrası temizleme tek çevrim sürüyor ve A byte'ı aldıktan sonra yapılıyor.
- **VGA zamanlaması.** Yatayda 50 karakter × 8 nokta = 400 nokta, dikeyde 525 satır. VRAM adresi {V8..V4, H5..H0}, `F000 + 64·satır + sütun` ile uyumlu.
- **74HC191 (SP).** /CE ve U/D yalnızca CLK yüksekken değişiyor. Datasheet kuralı sağlanıyor.
- **Snake yükü.** Hamle başına yaklaşık 0.6 ms. Tahmin 5 kat yanlış olsa bile hamle aralığının (125 ms) yanında önemsiz.

## 2. Düzeltmeler

Sentezde yanlış olan ya da Türkiye'de uygulanamayan noktalar:

| # | Sentezde | Sorun | Düzeltme |
|---|---|---|---|
| 1 | VGA için 25.175 MHz osilatör | Türkiye'de yok, yalnız DigiKey'de var | **25.000 MHz** (n11 ackelektronik, son 1 lot). Nokta saati 12.5 MHz (80 ns), yatay 31.25 kHz, dikey 59.5 Hz. Monitörler genelde kabul ediyor, yine de **demo monitöründe ilk hafta test edin**. |
| 2 | 8× SST39SF010A, "10 adet DigiKey/AliExpress'ten" | DIP kılıf üretimden kalktı, DigiKey'de stok yok. Yurt içinde yalnızca 6 adet eski stok SST39SF010-90 var. | 6 yerli + en az 2 ithal (öneri: 10). İki yol var: (a) tek AliExpress paketi, 10 adet ≈ 986 TL ≈ 17.7 €; öğrenci "MODEL" muafiyetiyle (≤30 €/gönderi, üniversite yazısı gerekir). (b) DigiKey'den PLCC kılıf + direnc'ten PLCC32-DIP32 adaptör (58 TL/adet). Gelen her çip T48'de silinip yazılıp doğrulanmadan kullanılmaz. |
| 2b | Flash yerleşimi | Bir şey belirtilmemiş | Hızlı (-70) çipler mikrokod ×3 ve ALU ×2 soketlerine, -90'lar program, font ve zamanlama ROM'una. 1 MHz'de -90 her yerde çalışır: yol 1 ~463/750 ns, yol 2 ~172/250 ns. 1.5 MHz için mikrokod çiplerinin -70 olması gerekir. |
| 3 | SRAM: AS6C62256-55 | Yurt içinde yok | **CY62256LL-70PC** (n11, 2'li lot; 2 lot = 4 adet). 70 ns, 1 MHz'de sorun değil. /WE için rahat pay var: 50 ns gerekiyor, 250 ns veriliyor. |
| 4 | "DigiKey'den 377/166/175/688/27/11/20/153" | Bunlar için ithalat gerekmiyor | 377: n11'de tekil (122 TL) ya da 2× 74HC163 ile kurulur. 166: n11. 175: Özdisan. 688: PC74HCT688P (n11, 6'lı lot). 153: robotistan. 20: direnc. 27 ve 11 için 5. ve 6. satıra bakın. |
| 5 | WAIT kapısı 74HC27 | Yurt içinde stok yok (direnc'te tükendi, motorobit ve robotistan'da yok) | 4. bir **74HC138** kullanın: /G2A = /FPAGE, /G2B = A11, G1 = VCC, A = /MEMW, B = VWR_s, C = GND. Y0 = /WAIT olur. Johnson tarafı: `Q2' = NAND(/Q1, OR(/WAIT, /Q2))`, OR için boşta kalan 74HC32 kapısı. Gecikme yaklaşık +13 ns artar, en kötü durum ~236 ns < 250 ns. Digital'de ve osiloskopta doğrulanacak. |
| 6 | 74HC11 ×2 | Yurt içinde yok | **VGA LD çözümü:** 74HC20'nin bir NAND4 kapısı (4. giriş VCC) + LD flip-flop'unun /Q çıkışı. Aynı gecikme, tek kapı. **PS/2:** /CLR164 = iki 74HC08 kapısı, KCLR D = bir 74HC08 kapısı. Bunlar zaman açısından kritik değil. Toplam entegre sayısı değişmiyor: 92. |
| 7 | VOH: "74HC VIH 4.5 V'ta 3.15 V" | Flash ve SRAM yalnızca 2.4 V garanti ediyor, 5 V'ta 74HC'nin eşiği 3.5 V | "İlk gün ölç" planı doğru. Ölçüm kötü çıkarsa HCT'ye geçecek çipler: 273 ×3 (mikrokod latch'i), 377 (A, IR, T1), 161 (F, AR, X), 166. Özdisan'da HCT çeşitleri var. Bütçede bunun için yedek ayrıldı. |
| 8 | Kablolama "~75 kişi-saat (kablo başına 2.5 dk)" | İyimser | Ölçülü, düzgün kablolama ve hata ayıklamayla kablo başına 4–6 dk sürer. 1.850 kablo için **120–180 kişi-saat** planlayın: kişi başı haftada 6–8 saat, 16 haftaya sığar. |
| 9 | Bütçe "≈21.7k TL, 5k ithalat, breadboard 110 TL" | Breadboard aslında 55 TL. Güç kaynağı, kablo sıyırıcı, lojik analizör eksik. Fiyatlar Ocak'a kadar %5–10 artar. | Yeniden hesaplandı: [PROJE-PLANI.md](../PROJE-PLANI.md) bölüm 14. |

## 3. Simülasyonda (Digital) ve prototipte doğrulanacaklar

Önem sırasıyla:

1. **Zamanlama yolları.**
   - WAIT (yeni 138'li çözüm): ~236/250 ns.
   - Mikrokod araması: ~172/250 ns.
   - Nokta hızındaki LD yolu: 80 ns'lik periyotta en kötü ~85 ns. **İlk osiloskop testi bu.** Yedek çözüm: 163'ün TC çıkışıyla çözmek ya da sayıcıda 74HCT/74AC kullanmak.
2. **VOH.** SST39SF010-90 ve CY62256 çıkışını gerçek yük altında ölçün. 4 V'un üstündeyse HC ile devam, değilse 2. bölüm madde 7.
3. **PS/2.**
   - 11. kenardan hemen sonra gelen inhibit klavyede yeniden gönderime yol açıyor mu? Gerçek klavyeyle prototip kurun.
   - RC zaman aşımı (~190 µs) çalışıyor mu?
   - Açılıştaki AA byte'ı ve F0/E0 işleme.
4. **VRAM penceresi.** MCLK/DCLK fazını rastgele seçip pencerenin ilk ve son anında verilen yazmaları deneyin.
   - SLOW modu kuralı ("yalnız dururken değiştir") panelde etiketlensin.
5. **C→D bus devir-teslimi.** Flash tDF 25 ns, 245 açılması 18 ns, yani kısa ve düşük akımlı bir çakışma var. Osiloskopta bakın.
6. **74HC191 SP.** x0/xF ve FF/00 sınırlarında push/pop.
7. **Derleyici kuralları:**
   - yüklemeden sonra test için TST;
   - zincirli Z'den önce ADD/SUB/CMP gelmeli;
   - CLC/SEC Z ve N'yi bozar;
   - INCW/DECW/JMPI A'yı bozar.
8. **Programlayıcı desteği.** T48 cihaz listesinde A'sız SST39SF010 (-90) var mı, kontrol edin. Liste SST39SF010A'yı kesin içeriyor.

## 4. Sonuç

- **Tasarım tutarlı ve yapılabilir.** 1 MHz, datasheet'teki en kötü değerlerle bile tüm yollarda sağlanıyor. En sıkışık yol WAIT: yaklaşık 236/250 ns.
- **2 MHz hedef değil.** Yalnızca tipik değerlerle tutuyor; tutarsa bonus.
- **Ölçek:** 92 entegre, 24 breadboard, yaklaşık 1.850 kablo. 2 kişi ve 16 haftalık yapım için büyük ama sığıyor. Daraltma sırası belli: LED portu → breakpoint → 2 MHz → renk.
