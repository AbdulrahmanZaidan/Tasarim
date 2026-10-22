# 8-Bit Breadboard Bilgisayar — Proje Platformu

Süleyman Demirel Üniversitesi · Tasarım I / Tasarım II Bitirme Projesi
Danışman: Doç. Dr. Fatih Şenel · Ekip: Abdelrahman Ahmad Radwan Zidan (2321032807), Taha Deniz Akgül (2426512003)

Bu depo, projenin genel tanıtım sitesini ve ekibin projeyi yönettiği **yönetim panelini** içerir:
mimari açıklamalar, tarayıcı içi eğitsel simülasyonlar, simülasyon deney kayıtları, ekran görüntüsü ve belge arşivi,
malzeme/maliyet ve satın alma takibi, görev tabanlı ilerleme ve etkinlik günlüğü.

## Mimari

```
Tarayıcı (React 18 + TypeScript + Vite + Tailwind + React Router)
   │  genel sayfalar ─── yalnızca yayımlanmış veriyi okur
   │  /admin ─────────── giriş yapmış ekip (yönetici / düzenleyici / izleyici)
   ▼
Supabase
   ├─ Auth ............ e-posta + parola, davetle hesap, kayıt kapalı
   ├─ PostgreSQL ...... 12 tablo, Row Level Security, tetikleyicilerle etkinlik günlüğü
   └─ Storage ......... public-media (yayımlanan) · private-files (yalnızca ekip)
GitHub ................ kaynak kodu ve sürümlü teknik dosyalar (REST API ile okunur)
```

- **Güvenlik sınırı veritabanıdır.** Arayüzdeki rol kontrolleri yalnızca kolaylık içindir; tüm yetkiler RLS ve Storage ilkeleriyle zorlanır.
- **Supabase yapılandırılmamışsa** site, `src/data/` içindeki statik verilerle eskisi gibi çalışır (ör. GitHub Pages önizlemesi).
- Eğitsel içerik (modül açıklamaları, simülasyon senaryoları, CPU modeli) kodla birlikte sürümlenir; değişen proje verileri veritabanındadır.

## Hızlı başlangıç

```bash
npm install
cp .env.example .env      # Supabase adresini ve anon anahtarını girin (boş bırakılırsa statik mod)
npm run dev               # http://localhost:5173  ·  panel: /admin
```

İlk kurulum (Supabase projesi, tablolar, depolar, ilk yönetici) için **[SETUP.md](SETUP.md)**.

## Belgeler

| Dosya | İçerik |
| --- | --- |
| [SETUP.md](SETUP.md) | Supabase projesinin sıfırdan kurulumu, ilk yönetici, davet akışı |
| [DATABASE.md](DATABASE.md) | Tablolar, ilişkiler, RLS ilkeleri, depolama kuralları, ilerleme ve maliyet hesapları |
| [ADMIN_GUIDE.md](ADMIN_GUIDE.md) | Panelin kullanımı: deney ekleme, ekran görüntüsü yükleme, malzeme ve ilerleme yönetimi |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Vercel ve GitHub Pages’e yayımlama, ortam değişkenleri, yönlendirme ayarları |
| [TESTING.md](TESTING.md) | Test türleri, nasıl çalıştırılacakları ve son çalıştırma sonuçları |
| [AUDIT.md](AUDIT.md) | Geçiş öncesi kod tabanı denetimi |
| [CHANGELOG.md](CHANGELOG.md) | Sürüm notları |

## Komutlar

| Komut | Açıklama |
| --- | --- |
| `npm run dev` / `build` / `preview` | Geliştirme sunucusu, üretim derlemesi, derleme önizlemesi |
| `npm run build:gh` | GitHub Pages derlemesi (`/Tasarim1/` alt dizini) |
| `npm run typecheck` | TypeScript denetimi |
| `npm test` | Birim testleri (hesaplamalar, CSV, doğrulama) |
| `npm run test:db` | Veritabanı güvenlik testleri (`TEST_DATABASE_URL` gerekir) |
| `npm run test:api` | Gerçek Supabase hizmetleriyle API testleri |
| `npm run test:e2e` / `test:static` | Tarayıcı uçtan uca testleri / Supabase’siz derleme testi |
| `npm run db:seed:generate` | `src/data` dosyalarından başlangıç verisi SQL’i ve `supabase/setup.sql` üretir |
| `npm run db:types` | Veritabanı şemasından `src/lib/database.types.ts` üretir |

## Klasör yapısı

```
src/
  pages/            genel sayfalar (mevcut tasarım korunmuştur)
  admin/            yönetim paneli (düzen, sayfalar, yükleme kuyruğu)
  components/       ortak bileşenler, simülasyonlar, diyagramlar, galeri
  services/         Supabase erişimi (tablolar, medya, belgeler, GitHub)
  data/             statik içerik + public.ts (genel sayfaların veri katmanı)
  lib/              istemci, hata çevirisi, sorgu önbelleği, ilerleme/maliyet/CSV hesapları
  auth/             oturum ve rol bağlamı
supabase/
  migrations/       0001 şema · 0002 güvenlik · 0003 depolama · 0004 başlangıç verisi
  setup.sql         tüm göçlerin tek dosyası (SQL Editor için)
tests/              unit · db · integration · e2e
scripts/            başlangıç verisi ve tür üreticileri
```

## İçerik ilkeleri

Hiçbir deney sonucu, satın alma, fotoğraf veya tamamlanmış iş uydurulmaz. “Başarılı” deney sonucu, gözlenen çıktı ve tarih
girilmeden veritabanı tarafından reddedilir; ilerleme yüzdeleri yalnızca tamamlanan görevlerden hesaplanır.
Başlangıç verisinde tamamlanmış görünen tek iş, doğrulanabilir olan GitHub deposunun oluşturulmasıdır.
