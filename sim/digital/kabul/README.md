# Kabul testleri: Digital'de açılıp denenecek dosyalar

Her `.dig` dosyasında bir modülün entegreleri ve test tablosu birlikte durur (SISTEM-PLANI bölüm 12.3).

| Dosya | Ne | Satır |
|---|---|---|
| `m2_urom.dig` | M2: 3 mikrokod ROM'u + kontrol latch'i | 1.000 vektör |
| `m2_cs.dig` | M2: kod çözücüler | 512 (tam tablo) |
| `m4_alu_tablo.dig` | M4: iki ALU flash'ı + 74HC32 | 10.000 vektör |
| `m5_cozme.dig` | M5: adres çözme | 1.096 vektör |

`TD8_SST39SF010_*.dig` dosyaları flash'ların içeriği; aynı klasörde durmaları gerekiyor.

**Digital'de:** dosyayı aç → araç çubuğunun en sağındaki yeşil tikli düğme (testleri çalıştır). Açılan pencerede satırlar yeşilse test geçmiş demektir.

**Komut satırında:** `araclar\digital-cli.cmd test -circ m2_cs.dig` → `m2_cs: passed`

**Yeniden üretmek:** `cd sim` → `py -3 digital/kabul/uret.py`. Tablolar `tests/test_hw_digital.py`'deki kabul testleriyle aynı.
