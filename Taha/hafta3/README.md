# Hafta 3 (10–16 Kasım 2026): simülasyon programları ve test vektörleri

## Özet

| İş | Sonuç |
|---|---|
| Simülasyon programlarının kurulumu | Java (Temurin JDK 21) ve Digital v0.31 kuruldu, komut satırından örnek devrelerle çalıştığı doğrulandı |
| Devre test vektörü üreticisi | 5 çeşit vektör: ALU, mikrokod, kod çözücüler, adres çözme, bütün işlemcinin çevrim çevrim izi |
| Proteus için ROM dosyaları | `sim/build/proteus/` altında 64 KB'lık `.bin` ve Intel HEX |
| Abdurrahman'ın soruları | İkisi de cevaplandı: ROM dosyası biçimi ve sinyal adları |
| C derleyicisi `tdcc` | Üzerinde çalışılıyor; 6. hafta notunda anlatılacak |
| Otomatik testler | 34'ten 54'e çıktı, hepsi geçiyor |

## 1. İndirilen programlar

Kurulum yeri: `Desktop\bitirme ödevi\araclar\` (deponun dışında). Yönetici izni gerekmedi, sistem ayarlarına dokunulmadı.

| Program | Sürüm | Ne için |
|---|---|---|
| Eclipse Temurin JDK | 21.0.13 | Digital'in çalışması için Java |
| Digital (hneemann) | 0.31 | Devre simülatörü: 74xx kütüphanesi, test bileşeni |

- Masaüstündeki **"Digital (TD-8)"** kısayolu Digital'i açar.
- Komut satırından örnek devrelerle çalıştığı doğrulandı: `araclar\digital-cli.cmd test -circ devre.dig`.
- Plandaki açık soru kapandı: kullandığımız 23 çeşit 74HC entegresinin hepsi Digital'in kütüphanesinde var (191, 166, 540 ve 688 dahil).
- Abdurrahman Proteus kullanıyor. Proteus ücretli olduğu için buraya kurulmadı; onun için Proteus'a uygun ROM dosyaları hazırlandı (bölüm 3).

## 2. Test vektörleri

**Test vektörü nedir?** "Bu girişleri verirsen şu çıkışları görmelisin" diyen satırlardan oluşan bir tablo. Devre simülatörü (Digital ya da Proteus) tabloyu satır satır dener; bir satır tutmazsa devrede hata vardır. Doğru cevapları emülatör üretiyor.

```
py cli.py vectors alu -n 10000 -o alu.txt        ALU: 10.000 rastgele işlem
py cli.py vectors urom -n 1000                   mikrokod: adım + komut + flag → kontrol kelimesi
py cli.py vectors cs                             kod çözücüler: tam tablo (512 satır)
py cli.py vectors decode                         adres çözme: her bölgenin ilk ve son adresi
py cli.py vectors trace examples/merhaba.asm     bütün işlemci: her çevrimde adres, veri, kontrol kelimesi
```

Örnek çıktı:

```
> py cli.py vectors alu -n 3
# M4 ALU testi: girişler OP A B Cin Zin, çıkışlar R Z C N V
OP A B Cin Zin R Z C N V
4 0x20 0x82 0 1 0x9D 0 0 1 1
24 0xE6 0xF1 1 0 0xF1 0 1 1 0
3 0xF9 0x0E 1 1 0xEB 0 1 1 0
```

Her satır bir deneme: soldaki beşi giriş (işlem kodu, A, B, gelen elde ve Z bayrağı), sağdaki beşi beklenen çıkış (sonuç ve Z, C, N, V bayrakları).

- `--format csv` ile Excel'de açılabilen tablo da üretir.
- **İz** (trace): bir programın her çevriminde adres yolunda, veri yolunda ve kontrol hatlarında ne olduğunun kaydı. İki izi karşılaştırıp **farkın başladığı ilk çevrimi** söyleyen bir fonksiyon da var (`td8/vectors.py`, `compare_traces`); breadboard'da Arduino'nun kaydettiği iz de bununla karşılaştırılacak.

## 3. Proteus için ROM dosyaları

`py cli.py roms` artık `sim/build/proteus/` klasörünü de dolduruyor:

- Eski `build/*.hex` dosyaları Digital biçiminde. Proteus bunları okuyamaz.
- Yeni `build/proteus/*.bin` ve `*.hex` (Intel HEX) Proteus içindir.
- Dosyalar 64 KB. Proteus'ta 128 KB'lık flash modeli büyük olasılıkla yok, 27C512 (64 KB) kullanılabilir. Bizim devrede flash'ların en üst adres pini (A16) zaten 0'a bağlı, yani yalnız alt 64 KB kullanılıyor.

| Proteus'taki ROM | Yüklenecek dosya |
|---|---|
| Mikrokod ROM'ları (3 adet) | `build/proteus/urom0.bin`, `urom1.bin`, `urom2.bin` |
| ALU ROM'ları (2 adet) | `build/proteus/alu_lo.bin`, `alu_hi.bin` |
| Program ROM'u | `py cli.py asm examples/merhaba.asm --ihex` → `merhaba.bin` (32 KB) ve `merhaba.hex` |

Proteus tarafı henüz denenmedi (Proteus bende kurulu değil; bilgi forumlardan). Abdurrahman deneyip sonucu yazacak.

## 4. Abdurrahman'ın soruları

- **Proteus'ta ROM'lara `.bin` mi `.hex` mi?** `sim/build/proteus/` klasöründeki `.bin`; olmazsa aynı adlı `.hex` (bölüm 3).
- **Sinyal adları şemadaki etiketlerle aynı olsun:** bunun için sinyal adları ve bacak bağlantıları listesi iletildi (`Tahadan-Abdurrahmana/TD8-baglanti-tablosu.md`).

## 5. C derleyicisi: `tdcc`

Üzerinde çalışılıyor; 6. hafta notunda anlatılacak.

## 6. Testler

| Test dosyası | Test | Neyi denetliyor |
|---|---:|---|
| Önceki haftalar (6 dosya) | 34 | ALU, mikrokod, assembler, emülatörler, runtime, VGA |
| `test_vectors.py` | 20 | vektör üreticisi, Intel HEX |
| **Toplam** | **54** | |

## Gelecek hafta

- Kontrol ünitesi (M2) ve bellek (M5) modüllerini Digital'de test etmek.
- C derleyicisine devam.

## Kullanılan araçlar

Python 3.12 (yalnızca standart kütüphane), unittest, Java (Temurin JDK 21), Digital v0.31, Git/GitHub.
