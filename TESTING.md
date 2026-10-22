# Testler

| Tür | Komut | Ne doğrulanır | Gereken ortam |
| --- | --- | --- | --- |
| Birim | `npm test` | İlerleme ve maliyet hesapları, para birimi ayrımı, CSV okuma/yazma, CSV içe aktarma önizlemesi, eski tarayıcı verisi aktarımı, dosya doğrulama, depolama yolu, Türkçe hata iletileri, form doğrulama, başlangıç verisinin bütünlüğü (38 kalem, $172,24–$242,24) | yok |
| Veritabanı güvenliği | `npm run test:db` | RLS (ziyaretçi / izleyici / düzenleyici / yönetici), rol yükseltme engeli, son yönetici koruması, sahte “oluşturan” alanı, etkinlik günlüğünün taklit edilememesi, satın alma → adet eşitlemesi, kanıtsız “başarılı” engeli, ağırlık toplamı, belge yayın kuralları, depolama yolu kuralı | `TEST_DATABASE_URL` (Supabase şemalı PostgreSQL) |
| API (gerçek hizmetler) | `npm run test:api` | supabase-js ile giriş, hatalı parola, oturum yenileme, kayıt kapalılığı, RLS, Storage yükleme/indirme yetkileri, MIME taklidi, özel dosya imzalı bağlantıları, açık ↔ özel taşıma, eşzamanlı düzenleme koruması, RPC | `SUPABASE_TEST_URL`, `SUPABASE_TEST_ANON_KEY`, `TEST_{ADMIN,EDITOR,VIEWER}_{EMAIL,PASSWORD}` |
| Tarayıcı uçtan uca | `npm run test:e2e` | Giriş/çıkış ve yönlendirme, izleyici kısıtları, deney oluşturma–yükleme–yayımlama–genel görünüm, tam ekran görüntüleyici, medya görünürlüğü ve silme, malzeme teklifi ve satın alma, CSV içe aktarma, görev → genel ilerleme, ağırlık doğrulaması, kaydedilmemiş değişiklik uyarısı, kur ayarı, düzenleyici kısıtları ve etkinlik günlüğü, mobil görünümde taşma, JavaScript hatası olmaması | çalışan uygulama + test Supabase’i, Chromium |
| Supabase’siz derleme | `npm run test:static` | Tüm genel sayfaların statik verilerle çalışması, panelin kurulum uyarısı, eski yerel düzenleme davranışı, tarayıcı içi simülasyonlar | `npm run build && npx vite preview --port 4174` |

## Son çalıştırma (22.10.2026)

Tüm testler temiz bir başlangıç verisi üzerinde sırayla çalıştırılmıştır:

```
typecheck ............ hatasız
birim ................ 20 / 20 başarılı
veritabanı güvenliği . 17 / 17 başarılı
API .................. 11 / 11 başarılı
tarayıcı (E2E) ....... 20 / 20 adım başarılı
Supabase’siz derleme . 14 / 14 kontrol başarılı
üretim derlemesi ..... başarılı (vite build, tsc -b)
```

### Test ortamı ve sınırları

Testler, Docker kullanılamayan bir ortamda Supabase bileşenleri tek tek kurularak yapılmıştır:

- PostgreSQL **16** (barındırılan Supabase 15/17 kullanır), Supabase rolleri `tests/harness/init-roles.sql` ile oluşturuldu
- **Supabase Auth (GoTrue) v2.177.0**, **PostgREST 12.2.3**, **Supabase Storage API v1.40.0** — resmî sürümler, dosya tabanlı depolama
- Kong yerine `tests/harness/gateway.mjs` (aynı `/auth/v1`, `/rest/v1`, `/storage/v1` yönlendirmesi)

Bu nedenle şunlar **doğrudan test edilmemiştir** ve barındırılan projede elle kontrol edilmelidir:
davet ve parola sıfırlama e-postalarının gönderimi, Supabase panelindeki “Allow new users to sign up” ayarı
(testte `GOTRUE_DISABLE_SIGNUP=true` ile doğrulandı), `supabase/config.toml` ile `supabase start`, Vercel ve GitHub Pages’teki gerçek yayın.

## Testleri kendi bilgisayarınızda çalıştırma

En kolay yol Supabase CLI’dır (Docker gerekir):

```bash
npx supabase start                         # göçler ve başlangıç verisi uygulanır
export TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
npm run test:db

# API ve E2E için test kullanıcıları (yalnızca yerel ortamda):
#   Studio (http://127.0.0.1:54323) → Authentication → Add user, ardından SQL:
#   select public.set_user_role('admin@test.local','admin'); select public.set_user_role('editor@test.local','editor');
export SUPABASE_TEST_URL=http://127.0.0.1:54321 SUPABASE_TEST_ANON_KEY=<supabase start çıktısındaki anon key>
export TEST_ADMIN_EMAIL=admin@test.local TEST_ADMIN_PASSWORD=...   # editor ve viewer için de
npm run test:api

# E2E: uygulamayı yerel Supabase ile derleyip başlatın
VITE_SUPABASE_URL=$SUPABASE_TEST_URL VITE_SUPABASE_ANON_KEY=$SUPABASE_TEST_ANON_KEY npx vite build --outDir dist-e2e
npx vite preview --outDir dist-e2e --port 4173 &
psql "$TEST_DATABASE_URL" -f tests/e2e/reset-local.sql   # temiz başlangıç (yalnızca yerel!)
npx playwright install chromium   # veya CHROMIUM_PATH=/yol/chromium
npm run test:e2e
```

`tests/e2e/reset-local.sql` yalnızca yerel (127.0.0.1) ve yalnızca `@test.local` kullanıcıları olan bir veritabanında çalışır;
aksi durumda kendini durdurur. **Gerçek proje veritabanında asla çalıştırmayın.**
