# Hafta 2 (3–9 Kasım 2026): Register modüllerinin Proteus simülasyonları

## Ne yapıldı

Bu hafta 8-bit breadboard bilgisayar projesinin ikinci simülasyon çalışması olan **register (yazmaç) modülü** üzerinde çalışıldı. Proteus ortamında üç ayrı devre şeması hazırlandı: **A Register**, **B Register** ve **Instruction Register**.

### 1. Schematic: A Register

- 8-bit veriyi saklamak için iki adet **74LS173** (4-bit register) kullanıldı.
- Register verisini ortak 8-bit veri yoluna (BUS_0–BUS_7) aktarmak için **74LS245** veri yolu sürücüsü kullanıldı.
- **CLK**, **CLR**, **AI** ve **AO** kontrol hatları şemaya eklendi.
- Register çıkışları **A_0–A_7** olarak adlandırıldı ve sekiz LED üzerinden görsel izleme için bağlantılar oluşturuldu.
- LED akım sınırlaması için 220 Ω dirençler ve besleme hattı için 0,1 µF bypass kondansatörü gösterildi.

![A Register Proteus şeması](A-register.png)

### 2. Schematic: B Register

- İki adet **74LS173** ile 8-bit B yazmacının şeması oluşturuldu.
- Ortak veri yolu bağlantısı için **74LS245** kullanıldı.
- **CLK**, **CLR**, **BI** ve **BO** kontrol hatları tanımlandı.
- Register çıkışları **B_0–B_7** olarak etiketlendi; sekiz LED ve 220 Ω dirençler ile gösterim bağlantıları eklendi.
- Besleme hattı için 0,1 µF bypass kondansatörü gösterildi.

![B Register Proteus şeması](B-register.png)

### 3. Schematic: Instruction Register

- Instruction Register (komut yazmacı) için iki adet **74LS173** ve bir adet **74LS245** içeren şema hazırlandı.
- **CLK**, **CLR** ve **II** kontrol hatları eklendi; komut verisinin BUS_0–BUS_7 üzerinden alınması amaçlandı.
- Şemada üst dört bit **IR_4–IR_7** olarak dış bağlantılara çıkarıldı; LED'lerle 8-bit veri hatları için görsel gösterim oluşturuldu.
- 220 Ω LED dirençleri ve 0,1 µF bypass kondansatörü eklendi.

![Instruction Register Proteus şeması](Instruction-register.png)

## Dosyalar

| Dosya | Açıklama |
|---|---|
| `A-register.png` | A Register devre şeması ekran görüntüsü |
| `B-register.png` | B Register devre şeması ekran görüntüsü |
| `Instruction-register.png` | Instruction Register devre şeması ekran görüntüsü |

**Not:** Bu klasöre henüz Proteus proje dosyaları (`.pdsprj`) eklenmedi; yalnızca paylaşılan devre şeması görselleri bulunmaktadır.

## Sonuç

A Register, B Register ve Instruction Register için üç ayrı Proteus devre şeması hazırlanmıştır. Böylece register modülünün 8-bit veri yolu, kontrol hatları ve LED gösterimi açısından tasarım aşaması belgelenmiştir. Saat kenarında veri yükleme, temizleme ve veri yoluna çıkış işlevlerinin simülasyon test sonuçları henüz paylaşılmadığı için çalıştıkları doğrulanmış olarak raporlanmamıştır.

## Sonraki adımlar / kontrol edilecek noktalar

- Proteus proje dosyalarını (`.pdsprj`) bu klasöre eklemek.
- A ve B registerlarında yükleme, temizleme ve BUS'a veri aktarma işlevlerini test etmek.
- Instruction Register'ın komut bitleri ve kontrol sinyallerini test etmek.
- Test sonuçlarını ekran görüntüleri veya ölçümlerle belgelemek.
