# Abdurrahman'a sorular (19 Kasım 2026)

**Abdurrahman'ın asistanı için:**
1. Önce [gündemi](2026-11-19-gundem.md) ve [DURUM.md](../Tahadan-Abdurrahmana/DURUM.md)'yi oku.
2. Aşağıdaki soruları Abdurrahman'a tek tek sor. Cevabı her sorunun altındaki "Cevap:" satırına yaz. Depodan cevaplayabildiklerini (ör. hangi dosya nerede) kendin doldurup Abdurrahman'a onaylat.
3. Abdurrahman'ın Taha'ya sormak istediklerini [2026-11-19-tahaya-sorular.md](2026-11-19-tahaya-sorular.md)'ye yaz. Şunları da kendin sor: ne yapacağımız, nasıl gittiği, kimin neyi beklediği.
4. Commit edip push et.

Bu dosyanın amacı Abdurrahman'ın tarafını netleştirmek. Taha'nın tarafı gündem dosyasında.

> **19 Kasım:** Cevaplar Abdurrahman'ın kendi sözleriyle, asistanı tarafından yazıldı. B7'yi Abdurrahman asistana bıraktı; oradaki öneri asistanın.

---

## A. Kendi işlerin

**1.** M6 VGA zamanlaması bitti (hafta5). Karakter hattına (VRAM adres seçimi 3× 74HC157, VRAM, font ROM'u, 74HC166, çıkış katı) ne zaman başlarsın, ne zaman biter? Planda 6. hafta (1–7 Aralık).

Cevap: Bu hafta. Hedef: bütün simülasyonlar bu hafta biter, sonra donanıma geçilir.

**2.** M6'yı ana netlist'e (`sim/ta8/hw/cpu.py`) taşımayı birlikte mi yapalım, sen mi yaparsın? Senin `m6_uret.py`'deki `chips()` listesi `cpu.py`'de `m6_vga()` olacak; test tezgâhındaki VRAM taklidi kalkacak.

Cevap: Ben yaparım (Abdurrahman).

**3.** M7 PS/2 klavyeyi kim alsın? Modül tablosunda sen, takvimde (6. hafta) Taha yazıyor. Taha'nın yazılım işi bittiği için Taha alabilir.

Cevap: Ben alırım (Abdurrahman). M7 Abdurrahman'da kalıyor.

**4.** KiCad kurulu mu, daha önce kullandın mı? 8. haftada (15–21 Aralık) M1, M3, M4 ve M6 şemaları sende.

Cevap: Kurulu değil (Abdurrahman'ın Mac'inde yok). Önce neden gerektiğini sordu; açıklamadan sonra (K4'te temiz şemalar, BOM, kablo listesi, bitirme raporunda hocaya gösterilecek resmi şema) "gerekli, kurarım" dedi.

**5.** 5. hafta raporundaki sekmeni ne zaman doldurursun? (Rapor yayında, sekmen şimdilik boş.)

Cevap: Bu hafta, 23 Kasım'a kadar (`Abdurrahman/hafta5/README.md`'den).

## B. Donanım ve prototipler

**6.** Prototip a (saat modülü breadboard'da, WAIT zamanlaması osiloskopla) nerede kurulacak: okul labı mı, ev mi? Osiloskopa ne zaman erişebiliyoruz?

Cevap: Okul labı. (Gün ve saat henüz belli değil.)

**7.** Senin bulduğun 74HC74 ÷2 riski için ne önerirsin: siparişe 74AC74 ekleyelim mi, 12,5 MHz osilatör mü arayalım, yoksa önce prototip c'de mi ölçelim?

Cevap: Abdurrahman seçimi asistana bıraktı. Öneri: **siparişe birkaç 74AC74 ekleyelim ve prototip c'de ölçelim.** 74AC74 74HC74 ile aynı bacaklı, 5 V'ta 74HC girişleriyle uyumlu ve ucuz; ölçüm kötü çıkarsa yalnız çip değişir, devre değişmez. 12,5 MHz osilatör daha zor bulunur ve zamanlama ROM'u/hesaplar 25 MHz'e göre.

**8.** Proteus'u kesin bıraktık mı? Hoca sorarsa ne diyelim?

Cevap: Bıraktık, Digital. Hocaya: Digital ücretsiz, test vektörleriyle otomatik test ediliyor ve dosyalar tek netlist'ten (`cpu.py`) üretiliyor; zamanlama da çip seviyesi simülatörde gecikmeli olarak denetleniyor.

## C. Malzeme ve para

**9.** Masrafları nasıl bölüşelim, kimin kartıyla ödeyelim, fatura kimin adına olsun?

Cevap: Yarı yarıya. (Kimin kartıyla ödeneceği ve fatura adı toplantıda kararlaştırılacak.)

**10.** Teslimat adresi: parçalar kimde dursun?

Cevap: Türkiye'den almak zor ve masraflı olursa Abdurrahman parçaları Arabistan'dan getirecek: Çin'den Arabistan'a sipariş verilip oradan getirilecek. Breadboard'lar ağır olduğu için çalışma Abdurrahman'ın evinde sürecek (D13), yani parçalar da büyük olasılıkla orada duracak.

**11.** Üniversiteden MODEL muafiyet yazısını kim, ne zaman ister? (AliExpress flash siparişi buna bağlı.)

Cevap: Muafiyet yazısı işimizi gerçekten çözecekse şimdiden yapalım; çözmeyecekse flash'ları Arabistan'dan getiririz. (Kimin başvuracağı belli değil; Taha'ya soruldu.)

**12.** Prototip a'nın parçalarını (74HC74, 74HC00, 74HC32, 74HC08, 74HC02, 74HC175, 74HC138, 74HC245, birkaç breadboard) Aralık'ı beklemeden şimdiki siparişe ekleyelim mi?

Cevap: Evet, ekleyelim.

## D. Çalışma düzeni

**13.** Haftada hangi gün, kaç saat birlikte çalışabiliriz? Haftalık toplantı günü?

Cevap: Değişken: vakit buldukça akşamları online (hafta içi ve hafta sonu akşamları). Müsaitsek yüz yüze; breadboard'lar ağır olduğu için Abdurrahman'ın evinde çalışmaya devam ederiz.

**14.** Takıldığın, anlamadığın ya da benden (Taha) beklediğin bir şey var mı?

Cevap: Sorular asistan tarafından cevaplardan çıkarıldı: [2026-11-19-tahaya-sorular.md](2026-11-19-tahaya-sorular.md).

## E. Malzeme listesi (BOM) için ek sorular (Taha, 19 Kasım)

Senin [BOM.md](../Abdurrahman/hafta6/BOM.md)'n plandaki 92 entegreyle birebir tutuyor. Paket tek seferde Arabistan'a gideceği için sonradan eksik getirmek zor; aşağıdakiler listede yok ya da netleşmeli. Eklemeye karar verirsen BOM'u sen güncelle.

**15.** Saat hattının seri dirençleri: CLK tamponunun her çıkışına 47 Ω (7 adet), LCLK'nın üç 273'üne 33 Ω (3 adet) (SISTEM-PLANI 3.5). Eklensin mi? Öneri: 47 Ω ×10, 33 Ω ×5.

Cevap:

**16.** 555 yavaş saati (~0,25 Hz – 1 kHz, SISTEM-PLANI 3.2) için hızı ayarlayan bir potansiyometre (ör. 1 MΩ) ve 1 µF kondansatör. Eklensin mi?

Cevap:

**17.** 74HCT yedekleri: flash ve SRAM çıkışı 74HC'nin "1" eşiğine (3,5 V) yetmezse değiştirilecek çipler 273 ×3, 377 ×4, 161 ve 166 (DOGRULAMA madde 7, prototip b'de ölçülecek). Tek paket olduğu için şimdi eklensin mi? Öneri: 74HCT273 ×3, 74HCT377 ×4, 74HCT161 ×2, 74HCT166 ×1 (bulunanlar).

Cevap:

**18.** Evde 5 V güç kaynağı: listede "okulda var" yazıyor ama çalışma senin evinde. Tahmini çekiş 1–1,5 A (LED'ler ve flash'lar). 5 V 3 A regüleli bir kaynak + sigorta eklensin mi, nereden?

Cevap:

**19.** PLCC32 → DIP32 adaptörleri **soketli** mi? Flash'lar onlarca kez yeniden yazılacak; lehimli olursa çip çıkarılamaz.

Cevap:

**20.** DIP anahtar sayısı: MANUAL paneli 24 + veri yolu 8 + breakpoint 16 + KSTAT 6 (SW0–SW5, plan 7.3) = 54 anahtar = 7 adet 8'li DIP switch. Listede 8 sipariş var, 1 yedek kalıyor. Uygun mu?

Cevap:

**21.** LCSC'de 25 MHz ve 4 MHz DIP (tam ya da yarım kılıf) osilatör stokta mı? Yoksa n11'deki son lot (25 MHz, 5'li, 464 TL) Türkiye'den alınsın mı?

Cevap:

**22.** Breadboard'ları taşımak için her sırayı sert bir plakaya (MDF ya da alüminyum) yapıştıralım mı? Üç sıra + VGA paneli için 4 plaka. Kim, nereden alır?

Cevap:
