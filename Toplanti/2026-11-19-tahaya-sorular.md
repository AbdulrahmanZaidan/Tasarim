# Taha'ya sorular (19 Kasım 2026)

**Abdurrahman ve asistanı yazar, Taha cevaplar.** Her soruyu aşağıdaki biçimde ekleyin. Taha'nın asistanı cevapları "Cevap:" satırına yazar.

Sorulabilecekler: ne yapacağız, nasıl gidiyor, kim neyi bekliyor, bir şeyin nasıl çalıştığı, araçların kullanımı, raporlar, siparişler.

> Abdurrahman'ın cevaplarından ([2026-11-19-abdurrahmana-sorular.md](2026-11-19-abdurrahmana-sorular.md)) asistanı çıkardı. Cevaplar 19 Kasım toplantısında, Taha'nın asistanı tarafından yazıldı. "Öneri" yazanlar henüz karar değil; onaylanınca gündemdeki karar tablosuna geçer.

---

**1.** Parçaları Türkiye'den almak zor ya da pahalı olursa Abdurrahman Çin'den Arabistan'a sipariş verip getirebilir. Hangi kalemler için bu daha mantıklı (ör. 10 flash, breadboard'lar, kablo)? Fiyat karşılaştırmasını kim yapsın?

Cevap: **Hepsi Arabistan'dan**, senin BOM'undaki gibi ([Abdurrahman/hafta6/BOM.md](../Abdurrahman/hafta6/BOM.md)):
- Entegreler, osilatörler, pasifler, konnektörler: LCSC, tek paket.
- Arduino Mega, PLCC adaptörleri, ZIF, lojik analizör: AliExpress, aynı adrese.
- Türkiye'den yalnız ağır/ucuz olanlar: breadboard, kablo, jumper; PS/2 klavye.

Fiyat: n11'deki son lotlar yalnız acil kısım için ~7.260 TL tutuyordu. LCSC'de bütün entegre ve pasifler ~160–210 $ + kargo 25–40 $. Yani Arabistan daha ucuz ve hepsini kapsıyor. Kesin rakamı BOM'u LCSC'ye yüklerken sen görürsün; karşılaştırmayı orada sen yap. Türkiye'deki n11/direnc listesi iptal. Tek istisna: LCSC'de 25 MHz DIP osilatör yoksa n11'deki son lot (464 TL) alınır (soru 21).

**2.** MODEL muafiyet yazısı gerçekten işe yarıyor mu (≤ 30 € gönderi, öğrenci)? Sürecini biliyor musun, kime başvuruluyor, kim başvursun? Yaramayacaksa flash'lar Arabistan'dan gelecek.

Cevap: Gerek kalmadı. Flash'lar da LCSC paketinde Arabistan'a geliyor, Türkiye'ye ithalat yok, başvurmuyoruz. Planda bildiğimiz yalnız şu kadar: öğrenci "MODEL" muafiyeti, gönderi başına ≤ 30 €, üniversite yazısı şart. Ayrıntılı süreci bilmiyoruz.

**3.** Masraflar yarı yarıya. 1. siparişi (~7.260 TL, son lotlar) kim, ne zaman veriyor, kimin kartıyla? Fatura kimin adına olsun?

Cevap: Masraf **yarı yarıya** (karar). n11 siparişi Arabistan planıyla iptal. **Öneri:** LCSC ve AliExpress siparişlerini Arabistan adresine sen verirsin, fatura senin adına olur, Taha tutarın yarısını sana öder. Türkiye'deki küçük alımları (breadboard, kablo, klavye) Taha yapar, yarısını sen ödersin. Onaylarsan gündemdeki karar tablosuna geçer.

**4.** Prototip a parçaları (74HC74, 00, 32, 08, 02, 175, 138, 245, 2–3 breadboard, jumper, LED) 1. siparişe eklensin dedik. Asistan ayrıca birkaç **74AC74** eklenmesini öneriyor (74HC74 ÷2 riski için, prototip c'de ölçülecek). Uygun mu?

Cevap: Evet. 74AC74 (3 adet) zaten BOM'unda. Prototip a'nın entegreleri de LCSC paketinde, breadboard'lar Türkiye alımında; ayrı bir sipariş gerekmiyor.

**5.** M7 PS/2 Abdurrahman'da kalıyor. M7 için hazır olanlar neler (test tezgâhındaki taklit, emülatördeki klavye modeli, ilgili testler)? Taha M7 yerine hangi işi alıyor (ör. KiCad'in bir kısmı)?

Cevap: Hazır olanlar:

| Ne | Nerede |
|---|---|
| Devre tasarımı: 2× 74HC164, 74HC540, 74HC14, KCLR flip-flop'u (74HC74), 74HC08, 2N7000, 3× 1N4148, zaman aşımı 22k/10nF | [SISTEM-PLANI bölüm 9](../SISTEM-PLANI.md) |
| Emülatördeki klavye modeli: `press()`, `krdy`, `kbd_byte`, `tick()`; F800 okununca KRDY sıfırlanır, byte'lar arası süre | `sim/ta8/bus.py` |
| Test tezgâhı taklidi: X2 (74HC540 okuma tamponu, /OE1 = /KBD_RD), KRDY ve KSR0–7 girişleri; harness bunları bus.py modeliyle sürüyor | `sim/ta8/hw/cpu.py` `stubs()`, `sim/ta8/hw/harness.py` |
| KSTAT b7 = KRDY | `cpu.py` U606 |
| Program ve test: `klavye.asm` (3 scan code, sıfır fark); Snake'in tuş çözümü | `sim/examples/klavye.asm`, `tests/test_hw_cpu.py` `test_klavye`, `examples/snake.c` |
| Çip modelleri: 74HC164, 74HC540, 74HC14, 74HC74, 74HC08 | `sim/ta8/hw/chips.py` (2N7000, diyot ve RC modeli yok; test tezgâhından verilebilir) |

M7 netlist'e girince `stubs()`'taki X2 ile KRDY/KSR girişleri kalkar, yerine PS/2 çerçevesi üreten bir test tezgâhı (KCLK, KDATA) gelir.

Taha'nın aldığı işler: MANUAL paneli ve saat kaynağı seçici (74HC153, 555, 74HC14), netlist'ten KiCad'e otomatik aktarım aracı (soru 8) ve kendi şemaları (M2, M5, Arduino kartı), gelen parçaların giriş testleri, M6 ve M7 netlist'e girerken gözden geçirme.

**6.** Abdurrahman M6'yı `cpu.py`'ye kendisi taşıyacak. Dikkat etmesi gerekenler: VRAM taklidi (X1) ve `VWR_s` kalkınca hangi testler etkilenir, `py cli.py hw digital` dışında neyi yeniden üretmeli? Taşıdıktan sonra gözden geçirir misin?

Cevap:
- **Kalkacaklar:** `stubs()`'taki X1 (VRAM taklidi). `VWR_s` artık test tezgâhı girişi olmayacak: U111'in boş iki flip-flop'u (şu an D2 = D3 = GND) VWR'yi iki MCLK ile senkronlayıp `VWR_s`'i üretir (plan 3.6 ve 10).
- **Etkilenen dosyalar:**
  - `ta8/hw/harness.py`: `VWR_s`'i sürüyor, `/VRAM_WE`'yi izliyor, `vram()` X1'den okuyor.
  - `tests/test_hw_cpu.py`: `window_pattern`, `windowed_run`, `TestWait` (`VWR_s`'i elle sürüyor).
  - `tests/test_hw_digital.py`: `m1_board`'daki `VWR_s` girişi, K2 testlerinde X1 dökümü.
  - `ta8/hw/digital_cpu.py`: `INPUTS`'ta `VWR_s`, `digital_trace`'te `X1` dökümü.
  - `ta8/hw/wiring.py`: `PLAN_COUNTS`'a M6 (19 entegre).
  - `cli.py`: `hw run --wait`.
- **Hız:** 25 MHz saat, CPU saatinden 25 kat fazla olay demek; CPU testleri çok yavaşlar. Öneri: `build(vga='taklit' | 'netlist')` seçeneği. Sıfır fark testleri taklitle sürsün, M6 ayrı testlerle denensin.
- **Yeniden üretilecekler:** `py cli.py hw digital`, `py -3 -m tests.test_hw_digital --yaz`, `py -3 digital_kabul/uret.py` (değişirse), `py cli.py hw wiring -o ../Tahadan-Abdurrahmana/TA8-baglanti-tablosu.md`, en sonda `py -3 -m unittest` (şu an 305 test, hepsi geçiyor).
- **Gözden geçirme:** evet. Ayrı bir dalda (`git switch -c m6-netlist`) çalışıp push edersen birleştirmeden önce bakarım.

**7.** Abdurrahman'ın hedefi bütün simülasyonları (M6 karakter hattı, VRAM penceresi, M7) bu hafta bitirip donanıma geçmek. Bu hedefle takvimi (K3 14 Aralık, K4 3 Ocak) nasıl güncelleyelim?

Cevap: **Öneri:** hedef tutarsa K3 (Digital'de ekranda yazı) 14 Aralık yerine ~7 Aralık, K4 (tasarım dondurma) 3 Ocak yerine ~20 Aralık. Aradaki zaman KiCad şemaları, breadboard yerleşim planı ve parçalar geldikçe prototipler için. Kablolama yine Ocak'ta başlar. Plandaki takvimi (SISTEM-PLANI bölüm 13) K3 gerçekleşince güncelleriz.

**8.** KiCad: hangi sürüm, ortak bir kütüphane/şablon kullanacak mıyız? Netlist'ten (`cpu.py`) KiCad'e otomatik aktarım düşünüyor musun, yoksa elle mi çizilecek?

Cevap: **Öneri:**
- **Sürüm:** ikimiz de aynı, en güncel kararlı KiCad. Kurunca sürüm numarasını buraya yazalım.
- **Kütüphane:** KiCad'in kendi 74xx kütüphanesi (74HC parçaları var). Flash ve SRAM için ortak bir proje kütüphanesi.
- **Aktarım otomatik**, Digital'e yaptığımız gibi. Taha bir `ta8/hw/kicad.py` yazar: netlist'ten her modül için bir `.kicad_sch` üretir, her çip bacağına sinyal etiketi koyar (tel yok, aynı adlı etiketler bağlı). Biz yalnız yerleşimi düzenleriz. Şema netlist'le aynı kalır, elle çizim hatası olmaz.

**9.** Prototip a okul labında. Osiloskop ve lab için kime başvuruluyor, ne zaman müsait?

Cevap: Danışmana (Fatih Şenel) ya da bölümün lab sorumlusuna. Taha bu hafta sorup cevabı buraya yazacak.
