# Abdurrahman'dan Taha'ya: Sorular, İstekler ve Donanım Notları

Selam Taha, donanım ve Proteus simülasyonu tarafında ilerlerken senden (yazılım / ROM imajları / kontrol sinyalleri tarafında) istediğim şeyleri, sorularımı ve tamamlanan testleri buraya yazacağım.

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

- [ ] **M1 Saat Modülü:** 4 fazlı saat (`CLK`, `LCLK`, `WSTB`) kuruldu; `STOP`, `WAIT`, `GO` ve `/RESET_s` testleri eklenecek.
- [ ] **M4 Registerlar (`A`, `IR`, `F`):** Şemalar SAP-1 (`74LS173` + `B registerı`) yapısından TD-8 planına (`74HC377` + B registersız + `R` girişli `A` + `74HC161` `F`) güncellenecek.
- [ ] **M3 Adres Registerları (`PC`, `AR`, `X`, `SP`):** 3. hafta içinde Proteus şemaları çizilecek.
