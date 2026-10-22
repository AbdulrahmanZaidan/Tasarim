-- =====================================================================
-- 0004 · Başlangıç verisi (scripts/generate-seed.mjs tarafından üretilmiştir — elle düzenlemeyin)
-- Kaynak: src/data/fallback.ts (projectData.ts, parts.ts, architecture.ts)
-- Tekrar çalıştırılabilir: mevcut kayıtlar değiştirilmez (on conflict do nothing).
-- Simülasyon sonucu, satın alma veya kanıtsız tamamlanmış iş UYDURULMAZ.
-- =====================================================================
begin;
select set_config('app.seeding', 'on', true), set_config('app.phase_weights', 'on', true);

insert into public.project_settings (id, project_title, project_subtitle, project_description, university, course, supervisor, team_members, github_url, project_status, default_currency, tasarim_ii_active)
values (true, '8-Bit Breadboard Bilgisayar', 'Sıfırdan Tasarlanan Programlanabilir 8-Bit Bilgisayar', 'Bu bitirme projesinin amacı, yalnızca temel dijital mantık entegre devreleri kullanılarak programlanabilir bir 8-bit bilgisayarın tasarlanması ve ikinci dönemde breadboard’lar üzerinde fiziksel olarak gerçekleştirilmesidir.', 'Süleyman Demirel Üniversitesi', 'Tasarım I · Bitirme Projesi', 'Doç. Dr. Fatih Şenel',
  '[{"name":"Abdelrahman Ahmad Radwan Zidan","student_id":"2321032807"},{"name":"Taha Deniz Akgül","student_id":"2426512003"}]'::jsonb, 'https://github.com/Siiingularity/Tasarim1', 'Hazırlık aşaması', 'TRY', false)
on conflict (id) do nothing;

insert into public.project_phases (slug, title, short_title, description, deliverable, semester, status, weight, route, sort_order)
values
  ('architecture', 'Mimari ve Şema', 'Mimari', 'Bilgisayarın blok diyagramı ile saat, yazmaçlar, ALU, RAM, program sayacı, çıkış ve kontrol biriminin devre şemaları hazırlanır; komut seti ve kontrol sinyalleri belirlenir.', 'Tam devre şeması ve blok diyagram', 'tasarim_1', 'planned', 20, '/proje/mimari-sema', 1),
  ('simulation', 'Simülasyon', 'Simülasyon', 'Devre, Digital (H. Neemann) veya Proteus ortamında kurularak her modül ayrı ayrı test edilir; ardından modüller birleştirilerek örnek programlar çalıştırılır.', 'Çalışan simülasyon ve örnek programlar', 'tasarim_1', 'planned', 20, '/proje/simulasyon', 2),
  ('github', 'GitHub Deposu', 'GitHub', 'Şemalar, simülasyon dosyaları, mikrokod/EEPROM kodları ve dokümanlar GitHub deposunda toplanır; sürüm takibi ve ekip içi iş bölümü buradan yürütülür.', 'Düzenli proje deposu', 'tasarim_1', 'planned', 20, '/proje/github', 3),
  ('materials', 'Malzeme ve Maliyet Analizi', 'Malzeme', 'Malzeme listesi simülasyon sonuçlarına göre kesinleştirilir; entegreler, breadboard’lar ve diğer parçalar temin edilip test edilir. EEPROM programlayıcı hazırlanır.', 'Eksiksiz ve test edilmiş malzeme seti', 'tasarim_1', 'planned', 20, '/proje/malzeme-maliyet', 4),
  ('tasarim2', 'Tasarım II: Uygulamaya Geçiş', 'Tasarım II', 'İkinci dönemde modüller breadboard üzerinde kurulur, test edilir ve birleştirilerek çalışan 8-bit bilgisayar elde edilir.', 'Çalışan 8-bit breadboard bilgisayar', 'tasarim_2', 'not_started', 20, '/proje/tasarim-ii', 5)
on conflict (slug) do nothing;

insert into public.project_components (slug, name, name_en, description, sort_order)
values
  ('clock', 'Saat Devresi', 'Clock Module', 'Bilgisayardaki tüm senkron işlemleri zamanlayan kare dalga üreteci.', 1),
  ('registers', 'A ve B Yazmaçları', 'Registers', 'Her biri 8 bit veri saklayan, ALU’nun iki işlenenini tutan yazmaçlar.', 2),
  ('alu', 'Aritmetik Mantık Birimi', 'ALU', 'A ve B yazmaçlarındaki değerleri toplayan veya çıkaran kombinasyonel devre.', 3),
  ('ram', 'RAM Bellek Modülü', 'RAM & Memory Address Register', '16 adres × 8 bit kapasiteli rastgele erişimli bellek ve onu adresleyen 4-bit bellek adres yazmacı (MAR).', 4),
  ('pc', 'Program Sayacı', 'Program Counter', 'Bir sonraki çalıştırılacak komutun bellek adresini tutan 4-bit sayıcı.', 5),
  ('ir', 'Komut Yazmacı', 'Instruction Register', 'Bellekten okunan geçerli komutu saklayan 8-bit yazmaç.', 6),
  ('control', 'Kontrol Birimi', 'Control Unit', 'Opcode, mikro adım ve bayraklara göre 16 kontrol sinyalini üreten birim.', 7),
  ('bus', 'Ortak Veri Yolu', '8-Bit Bus', 'Tüm modülleri birbirine bağlayan 8 hatlı ortak iletişim yolu.', 8),
  ('output', 'Çıkış Yazmacı', 'Output Register', 'Veri yolundaki 8-bit değeri saklayıp dört adet 7 segment göstergede ondalık olarak gösteren modül.', 9),
  ('eeprom', 'EEPROM ve Mikrokod', 'EEPROM & Microcode', 'Kontrol birimi ve çıkış modülünde kullanılan 28C16 EEPROM’ların içeriği (mikrokod ve 7 segment tabloları) ile bu EEPROM’ları programlamak için kullanılan programlayıcı.', 10),
  ('isa', 'Komut Seti Mimarisi', 'Instruction Set Architecture', 'Bilgisayarın desteklediği komutlar, işlem kodları (opcode) ve her komutun mikro adımları.', 11),
  ('integration', 'Bilgisayarın Bütünleştirilmesi', 'Complete Computer Integration', 'Tüm modüllerin ortak veri yolu ve kontrol birimi üzerinden birleştirilerek tek bir bilgisayar olarak çalıştırılması.', 12)
on conflict (slug) do nothing;

insert into public.project_tasks (phase_id, title, description, status, completed_at, sort_order)
select p.id, v.title, v.description, v.status::public.work_status, v.completed_at::timestamptz, v.sort_order
from (values
  ('architecture', 'Ben Eater referans mimarisinin modül modül incelenmesi', null, 'not_started', null, 1),
  ('architecture', 'Blok diyagramın proje ekibince çizilmesi', null, 'not_started', null, 2),
  ('architecture', 'Modül devre şemalarının hazırlanması', null, 'not_started', null, 3),
  ('architecture', 'Komut seti ve kontrol kelimesinin kesinleştirilmesi', null, 'not_started', null, 4),
  ('architecture', 'Genel blok diyagram', null, 'not_started', null, 5),
  ('architecture', 'Modül devre şemaları', null, 'not_started', null, 6),
  ('architecture', 'Komut seti ve mikrokod tablosu', null, 'not_started', null, 7),
  ('simulation', 'Simülasyon aracının seçilmesi (Digital / Proteus)', null, 'not_started', null, 1),
  ('simulation', 'Saat ve yazmaç modüllerinin simülasyonu', null, 'not_started', null, 2),
  ('simulation', 'ALU, RAM ve program sayacı simülasyonu', null, 'not_started', null, 3),
  ('simulation', 'Kontrol birimi ve tam sistem simülasyonu', null, 'not_started', null, 4),
  ('simulation', 'Modül bazlı simülasyonlar', null, 'not_started', null, 5),
  ('simulation', 'Bütünleşik sistem simülasyonu', null, 'not_started', null, 6),
  ('simulation', 'Örnek programların çalıştırılması', null, 'not_started', null, 7),
  ('github', 'Depo klasör yapısının belirlenmesi', null, 'not_started', null, 1),
  ('github', 'README ve dokümantasyonun eklenmesi', null, 'not_started', null, 2),
  ('github', 'Şema ve simülasyon dosyalarının yüklenmesi', null, 'not_started', null, 3),
  ('github', 'GitHub deposunun oluşturulması', 'Depo github.com/Siiingularity/Tasarim1 adresinde oluşturulmuştur. Tamamlanma tarihi olarak deponun mevcut olduğunun ilk doğrulandığı tarih girilmiştir.', 'completed', '2026-10-20T00:00:00+03:00', 4),
  ('github', 'README ve klasör yapısı', null, 'not_started', null, 5),
  ('github', 'Teknik dosyaların düzenli eklenmesi', null, 'not_started', null, 6),
  ('materials', 'Referans malzeme listesinin çıkarılması', null, 'not_started', null, 1),
  ('materials', 'Türkiye tedarikçilerinden fiyat alınması', null, 'not_started', null, 2),
  ('materials', 'Siparişlerin verilmesi', null, 'not_started', null, 3),
  ('materials', 'Gelen parçaların test edilmesi', null, 'not_started', null, 4),
  ('materials', 'Referans malzeme listesi', null, 'not_started', null, 5),
  ('materials', 'Yerel fiyat teklifleri', null, 'not_started', null, 6),
  ('materials', 'Satın alma ve parça testleri', null, 'not_started', null, 7),
  ('tasarim2', 'Modüllerin Breadboard Üzerinde Kurulması', 'Saat, yazmaçlar, ALU, RAM, program sayacı, çıkış ve kontrol modüllerinin ayrı breadboard’lar üzerinde kurulması.', 'not_started', null, 1),
  ('tasarim2', 'Devrelerin Test Edilmesi', 'Her modülün LED göstergeler ve manuel saat adımlarıyla bağımsız olarak doğrulanması.', 'not_started', null, 2),
  ('tasarim2', 'Veri Yolunun Birleştirilmesi', 'Modüllerin 8-bit ortak veri yoluna 74LS245 üç-durumlu tamponlar üzerinden bağlanması.', 'not_started', null, 3),
  ('tasarim2', 'Kontrol Biriminin Entegrasyonu', 'EEPROM tabanlı mikrokodun programlanması ve kontrol sinyallerinin modüllere dağıtılması.', 'not_started', null, 4),
  ('tasarim2', 'Programların Çalıştırılması', 'Toplama, çıkarma ve döngü içeren örnek programların RAM’e yüklenip çalıştırılması.', 'not_started', null, 5),
  ('tasarim2', 'Nihai Sistem Testleri', 'Tüm komut setinin, bayrakların ve koşullu atlamaların bütünleşik sistemde sınanması.', 'not_started', null, 6)
) as v(phase_slug, title, description, status, completed_at, sort_order)
join public.project_phases p on p.slug = v.phase_slug
where not exists (select 1 from public.project_tasks t where t.phase_id = p.id and t.title = v.title);

insert into public.materials (slug, name, source_name, category, notes, required_quantity, ref_quantity, ref_unit_price_min, ref_unit_price_max, ref_stated_total_min, ref_stated_total_max, is_programmer_extra, sort_order, ref_currency)
select v.*, 'USD' from (values
  ('breadboard', 'Breadboard (delikli deney tahtası)', 'Breadboard', 'Breadboard ve bağlantı malzemeleri', 'Kaynak, en iyi kalite olarak BusBoard BB830 modelini önermektedir.', 14, 14, 4, 9, 56, 126, false, 10),
  ('wire', '22 AWG tek damarlı kalaylı bakır bağlantı teli (set)', '22 AWG Solid Tinned-Copper Hook-Up Wire', 'Breadboard ve bağlantı malzemeleri', null, 1, 1, 16, 16, 16, 16, false, 20),
  ('r1k', '1 kΩ direnç', '1kΩ resistor', 'Dirençler', null, 10, 10, 0.06, 0.06, 0.6, 0.6, false, 30),
  ('r10k', '10 kΩ direnç', '10kΩ resistor', 'Dirençler', null, 9, 9, 0.06, 0.06, 0.6, 0.6, false, 40),
  ('r100k', '100 kΩ direnç', '100kΩ resistor', 'Dirençler', null, 1, 1, 0.06, 0.06, 0.6, 0.6, false, 50),
  ('r470', '470 Ω direnç', '470Ω resistor', 'Dirençler', null, 24, 24, 0.06, 0.06, 1.8, 1.8, false, 60),
  ('r1m', '1 MΩ direnç', '1MΩ resistor', 'Dirençler', null, 1, 1, 0.06, 0.06, 0.6, 0.6, false, 70),
  ('pot1m', '1 MΩ potansiyometre', '1MΩ potentiometer', 'Dirençler', null, 1, 1, 1.39, 1.39, 1.39, 1.39, false, 80),
  ('c001', '0,01 µF kondansatör', '0.01µF capacitor', 'Kondansatörler', null, 6, 6, 0.12, 0.12, 1.2, 1.2, false, 90),
  ('c01', '0,1 µF kondansatör', '0.1µF capacitor', 'Kondansatörler', null, 16, 16, 0.15, 0.15, 3, 3, false, 100),
  ('c1', '1 µF kondansatör', '1µF capacitor', 'Kondansatörler', null, 1, 1, 0.15, 0.15, 0.15, 0.15, false, 110),
  ('ne555', '555 zamanlayıcı entegresi', '555 timer IC', 'Zamanlayıcı entegreler', null, 4, 4, 0.35, 0.35, 1.4, 1.4, false, 120),
  ('ls00', '74LS00 — dörtlü NAND kapısı', '74LS00 (Quad NAND gate)', 'Mantık kapıları', null, 2, 2, 0.79, 0.79, 1.58, 1.58, false, 130),
  ('ls02', '74LS02 — dörtlü NOR kapısı', '74LS02 (Quad NOR gate)', 'Mantık kapıları', null, 1, 1, 0.55, 0.55, 0.55, 0.55, false, 140),
  ('ls04', '74LS04 — altılı tersleyici (NOT)', '74LS04 (Hex inverter)', 'Mantık kapıları', null, 5, 5, 0.59, 0.59, 2.95, 2.95, false, 150),
  ('ls08', '74LS08 — dörtlü AND kapısı', '74LS08 (Quad AND gate)', 'Mantık kapıları', null, 3, 3, 0.69, 0.69, 2.07, 2.07, false, 160),
  ('ls32', '74LS32 — dörtlü OR kapısı', '74LS32 (Quad OR gate)', 'Mantık kapıları', null, 1, 1, 0.49, 0.49, 0.49, 0.49, false, 170),
  ('ls107', '74LS107 — çift JK flip-flop', '74LS107 (Dual JK flip-flop)', 'Yazmaç ve sayaç entegreleri', 'Videolarda kullanılan 74LS76 zor bulunur; 74LS107 işlevsel olarak eşdeğerdir ancak bacak dizilimi (pinout) farklıdır.', 1, 1, 1.75, 1.75, 1.75, 1.75, false, 180),
  ('ls86', '74LS86 — dörtlü XOR kapısı', '74LS86 (Quad XOR gate)', 'Mantık kapıları', null, 2, 2, 0.55, 0.55, 1.1, 1.1, false, 190),
  ('ls138', '74LS138 — 3’ten 8’e kod çözücü', '74LS138 (3-to-8 line decoder)', 'Mantık kapıları', null, 1, 1, 0.69, 0.69, 0.69, 0.69, false, 200),
  ('ls139', '74LS139 — çift 2’den 4’e kod çözücü', '74LS139 (Dual 2-line to 4-line decoder)', 'Mantık kapıları', null, 1, 1, 0.69, 0.69, 0.69, 0.69, false, 210),
  ('ls157', '74LS157 — dörtlü 2’den 1’e veri seçici (multiplexer)', '74LS157 (Quad 2-to-1 line data selector)', 'Mantık kapıları', null, 4, 4, 0.69, 0.69, 2.76, 2.76, false, 220),
  ('ls161', '74LS161 — 4-bit senkron ikili sayıcı', '74LS161 (4-bit synchronous binary counter)', 'Yazmaç ve sayaç entegreleri', null, 2, 2, 0.79, 0.79, 1.58, 1.58, false, 230),
  ('ls173', '74LS173 — 4-bit D tipi yazmaç', '74LS173 (4-bit D-type register)', 'Yazmaç ve sayaç entegreleri', null, 8, 8, 1.39, 1.39, 11.12, 11.12, false, 240),
  ('ls189', '74189 — 64-bit (16 × 4) RAM', '74189 (64-bit random access memory)', 'Bellek ve EEPROM', null, 2, 2, 4.95, 4.95, 9.9, 9.9, false, 250),
  ('ls245', '74LS245 — sekizli veri yolu alıcı-vericisi', '74LS245 (Octal bus transceiver)', 'Mantık kapıları', null, 6, 6, 0.79, 0.79, 4.74, 4.74, false, 260),
  ('ls273', '74LS273 — sekizli D flip-flop', '74LS273 (Octal D flip-flop)', 'Yazmaç ve sayaç entegreleri', null, 1, 1, 0.75, 0.75, 0.75, 0.75, false, 270),
  ('ls283', '74LS283 — 4-bit ikili tam toplayıcı', '74LS283 (4-bit binary full adder)', 'Mantık kapıları', null, 2, 2, 1.49, 1.49, 2.98, 2.98, false, 280),
  ('eeprom', '28C16 EEPROM (2K × 8)', '28C16 EEPROM', 'Bellek ve EEPROM', null, 3, 3, 3.95, 3.95, 11.85, 11.85, false, 290),
  ('toggle', 'Çift konumlu (double-throw) toggle anahtar', 'Double-throw toggle switch', 'Anahtarlar ve kontrol elemanları', null, 3, 3, 0.99, 0.99, 2.97, 2.97, false, 300),
  ('tact', '6 mm anlık (momentary) buton', 'Momentary 6mm tact switch', 'Anahtarlar ve kontrol elemanları', null, 3, 3, 0.35, 0.35, 1.05, 1.05, false, 310),
  ('dip8', '8 konumlu DIP anahtar', '8-position DIP switch', 'Anahtarlar ve kontrol elemanları', null, 1, 1, 0.79, 0.79, 0.79, 0.79, false, 320),
  ('dip4', '4 konumlu DIP anahtar', '4-position DIP switch', 'Anahtarlar ve kontrol elemanları', null, 1, 1, 0.89, 0.89, 0.89, 0.89, false, 330),
  ('led-r', 'Kırmızı LED', 'Red LED', 'LED ve göstergeler', null, 44, 44, 0.12, 0.12, 6, 6, false, 340),
  ('led-y', 'Sarı LED', 'Yellow LED', 'LED ve göstergeler', null, 8, 8, 0.09, 0.09, 0.9, 0.9, false, 350),
  ('led-g', 'Yeşil LED', 'Green LED', 'LED ve göstergeler', null, 12, 12, 0.1, 0.1, 2, 2, false, 360),
  ('led-b', 'Mavi LED', 'Blue LED', 'LED ve göstergeler', null, 21, 21, 0.59, 0.59, 12.39, 12.39, false, 370),
  ('seg7', 'Ortak katotlu 7 segment gösterge', 'Common cathode 7-segment display', 'LED ve göstergeler', null, 4, 4, 1.09, 1.09, 4.36, 4.36, false, 380),
  ('nano', 'Arduino Nano', null, 'EEPROM programlayıcı', 'Kaynakta fiyat belirtilmemiştir.', 1, 1, null, null, null, null, true, 1000),
  ('hc595', '74HC595 — 8-bit seri giriş / paralel çıkış kaydırmalı yazmaç', null, 'EEPROM programlayıcı', 'Kaynakta fiyat belirtilmemiştir.', 2, 2, null, null, null, null, true, 1010)
) as v(slug, name, source_name, category, notes, required_quantity, ref_quantity, ref_unit_price_min, ref_unit_price_max, ref_stated_total_min, ref_stated_total_max, is_programmer_extra, sort_order)
on conflict (slug) do nothing;

commit;
