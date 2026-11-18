# Abdurrahman'dan Taha'ya: Sorular, İstekler ve Donanım Notları

Selam Taha, donanım ve Proteus simülasyonu tarafında ilerlerken senden (yazılım / ROM imajları / kontrol sinyalleri tarafında) istediğim şeyleri, sorularımı ve tamamlanan testleri buraya yazacağım.

---

## YENİ (18 Kasım): Bütün simülasyonlar Digital'de yeniden yapıldı

Proteus'taki M1 dosyam silindi. Sen de Digital kullandığın için Proteus yerine **Digital'e geçtim**. SAP-1 şemaları (74LS173, B registerı, 74LS283 ALU, 16 baytlık RAM, MAR) ve eski görseller kaldırıldı; her hafta klasöründe artık `.dig` dosyaları, Digital'de geçen testler, dalga şekilleri ve ekran görüntüleri var.

**Açıkça yazayım: devreleri elle çizmedim.** `.dig` dosyaları senin netlist'inden (`sim/td8/hw/cpu.py`) senin aracınla (`sim/td8/hw/digital.py`: `sub_board` / `module_board` / `export`) üretildi; yani devreler `sim/digital/` altındaki dosyalarınla aynı bağlantılar. Benim eklediklerim:

- Taha'nın istediği testlere göre **Digital test case'leri** (M1'in 4 testi, A/IR/F'nin 4 testi, ALU'da seçilmiş 16 işlem, M3'ün 4 testi). M1 ve M3 senaryoları `tests/test_hw_digital.py`'deki senaryolarına benziyor; ALU'nun 10 ve 10.000 satırlık tabloları `vectors alu` çıktısı.
- Her test için *verilen / beklenen / görülen* tablolu raporlar, dalga şekli görselleri ve Digital ekran görüntüleri.
- 4. hafta: bütün işlemciyi (`td8.dig` ile aynı) senin `digital_trace` / `compare_run` aracınla `merhaba`, `komut_testi`, `fibonacci` için yeniden koşturdum. Bunu sen zaten yapmıştın (`sim/README.md`); yeni bir şey değil, yalnız benim klasörümde belgeli.

Bundan sonra en azından M1'i ve A/IR/F registerlarını bağlantı tablosundan **Digital'de elle çizmeyi** ve aynı testleri onlarda koşturmayı düşünüyorum. Sence gerekli mi, yoksa bu haliyle yeterli mi?

**Dosyaların yeri:** sen hepsini `Abdurrahman/hafta4/` içinde istemiştin; ben her modülü planda ait olduğu haftaya koydum (aşağıdaki tablo). `hafta4`'te yalnız bütün işlemci var.

| Hafta | Ne | Test | Sonuç |
|---|---|---|---|
| [hafta1](../Abdurrahman/hafta1/README.md) | M1 saat modülü (U101–U111 + U503) | Normal çalışma, STOP, WAIT (G1 = CLK düzeltmesiyle), GO ve /RESET_s | 4/4 geçti: **K1** |
| [hafta2](../Abdurrahman/hafta2/README.md) | A, IR (74HC377), F (74HC161), A'nın DB tamponu (U401–U404) | A yükleme, IR yükleme, A → DB → IR, F bayrakları ve asenkron reset | 4/4 geçti |
| [hafta3](../Abdurrahman/hafta3/README.md) | ALU (2 flash + 74HC32) ve M3 (PC, AR, X, SP + #AS) | ALU: senin istediğin 10 vektör, seçilmiş işlemler, 10.000 vektör. M3: PC sayma/yükleme, AR/X bayt yükleme, SP push/pop, adres yolu seçimi | 7/7 geçti |
| [hafta4](../Abdurrahman/hafta4/README.md) | Bütün işlemci (63 entegre + M6/M7 taklitleri), senin `td8.dig`'inle aynı | `merhaba`, `komut_testi`, `fibonacci` Digital'de, MicroEmu ile çevrim çevrim (senin aracınla, yeniden koşu) | 3/3 sıfır fark |

Notlar:
- Testler Digital'in kendi test aracıyla (`CLI test`) çalıştırıldı.
- Senin istediğin "Proteus'ta çalışırken ekran görüntüsü" yerine Digital ekran görüntüleri var. Bu senin için uygun mu?
- ROM için `.bin` / `.hex` denemesini yapmadım: Digital'de ROM içerikleri `.dig` dosyalarına gömülü olduğu için gerekmiyor diye düşündüm. Proteus'a dönmeyeceksek gerekmez, değil mi?
- **Henüz yapılmayan:** prototip a (saat modülü breadboard'da, osiloskopla WAIT zamanlaması), parçalar gelince.
- 4. hafta raporunda "Saat modülü Proteus'ta kuruldu" ve "Devre modüllerini Proteus'ta kuruyor" yazıyor; Proteus dosyası silindiği için bunları düzeltebilir misin?

---

## 1. Taha'dan İstenenler / Sorular

<!-- Abdurrahman: Taha'dan istediğin ROM imajı (.bin/.hex), test vektörü veya sinyallerle ilgili soruları buraya madde madde yazabilirsin. -->

- [x] Proteus'taki ROM bileşenlerine `urom0..2` ve `alu_lo / alu_hi` dosyalarını yüklerken `.bin` mi yoksa `.hex` mi kullanacağımızı birlikte netleştirelim.
  - **Taha'nın cevabı (12 Kasım):** `.bin`, ama `sim/build/proteus/` klasöründeki 64 KB'lık dosyalar. Ayrıntı: [Tahadan-Abdurrahmana, bölüm 0](../Tahadan-Abdurrahmana/README.md). Proteus'ta deneyip sonucu buraya yazar mısın?
- [x] M2 Kontrol Ünitesi ve M5 Bellek/Adres Çözme modüllerini birleştirirken sinyal isimlerinin (`ASRC`, `DSRC`, `DDST`, `ALUOP`, `/MRD`, `/MWR`) şemadaki etiketlerle bire bir aynı olmasını kontrol edelim.
  - **Taha'nın cevabı (12 Kasım):** Bütün sinyal adları ve her entegrenin bacak bacak bağlantısı: [TD8-baglanti-tablosu.md](../Tahadan-Abdurrahmana/TD8-baglanti-tablosu.md).

---

## 2. Donanım Tarafında Tamamlananlar / Güncel Durum

<!-- Abdurrahman: Tamamladığın Proteus dosyalarını ve test sonuçlarını buraya not düşebilirsin. -->

Devreler senin netlist'inden üretildi (elle çizilmedi); testler ve raporlar benim.

- [x] **M1 Saat Modülü:** Digital'de; `STOP`, `WAIT`, `GO` ve `/RESET_s` testleri geçti (hafta1).
- [x] **M4 Registerlar (`A`, `IR`, `F`):** TD-8 planına göre (`74HC377` A ve IR, B registersız, `74HC161` F) Digital'de; testler geçti (hafta2).
- [x] **M4 ALU:** 2 flash + 74HC32, Digital'de; 10.000 vektör geçti (hafta3).
- [x] **M3 Adres Registerları (`PC`, `AR`, `X`, `SP`):** Digital'de; testler geçti (hafta3).
- [x] **Bütün işlemci:** Digital'de 3 program, MicroEmu ile sıfır fark (hafta4; senin daha önce yaptığının yeniden koşusu).
- [ ] **Prototip a:** saat modülü breadboard'da, osiloskopla WAIT zamanlaması (parçalar gelince).
