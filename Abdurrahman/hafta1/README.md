# Hafta 1 (27 Ekim – 2 Kasım 2026): saat modülü

## Ne yapıldı

- Saat modülü (M1) Proteus'ta simüle edildi.

<!-- Abdurrahman: devrede kullandığın entegreleri, hangi sinyalleri ölçtüğünü ve sonucu buraya yaz. -->

## Dosyalar

<!-- Proteus proje dosyasını (.pdsprj) ve osiloskop / lojik analizör ekran görüntülerini bu klasöre koy, buraya adlarını yaz. -->

## Beklenen sonuç

[SISTEM-PLANI.md bölüm 3](../../SISTEM-PLANI.md#3-saat-reset-durdurma-m1): 4 MHz MCLK, iki 74HC74 ile Johnson sayacı, her CPU çevrimi C → D → A → B fazları (CPU 1 MHz).

| Sinyal | Tanım | Yüksek olduğu fazlar |
|---|---|---|
| CLK | Q2 | C, D (B→C'de yükselir, registerlar bu kenarda yüklenir) |
| LCLK | /Q1 | D, A (C→D'de yükselir, kontrol latch'i) |
| WSTB | NOR(Q1, Q2) | yalnız A (yazma darbesi) |

Proteus çıktısı bu tabloyla karşılaştırılır. Kalan testler (STOP'ta C fazında durma, WAIT'te D fazında bekleme, GO ile tam 1 çevrim, reset'te C'ye dönme) 2. haftada.

## Sorunlar / sorular

<!-- varsa -->
