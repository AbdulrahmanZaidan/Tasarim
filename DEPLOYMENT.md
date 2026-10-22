# Yayımlama

Önerilen yapı: **Ön yüz → Vercel**, **Arka uç → Supabase**, **Kaynak kodu → GitHub**.
Gizli anahtar gerekmez; yalnızca herkese açık anon anahtarı kullanılır.

## Ortam değişkenleri

| Değişken | Zorunlu | Açıklama |
| --- | --- | --- |
| `VITE_SUPABASE_URL` | evet* | `https://<proje>.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | evet* | Supabase “anon / publishable” anahtarı |
| `VITE_SUPABASE_IMAGE_TRANSFORM` | hayır | `true` ise küçük resimler Supabase görüntü dönüştürmeyle üretilir (Pro plan) |
| `VITE_BASE` | hayır | Alt dizin (GitHub Pages için varsayılan `/Tasarim1/`) |

\* Tanımlanmazsa site statik yedek verilerle çalışır, yönetim paneli kurulum yönergesi gösterir.

`service_role` anahtarını **asla** bir `VITE_` değişkenine koymayın; `VITE_` ile başlayan her değer tarayıcıya gömülür.

## Vercel

1. vercel.com → **Add New → Project** → GitHub’daki `Siiingularity/Tasarim1` deposunu seçin.
2. Framework: **Vite** (otomatik). Build: `npm run build`, Output: `dist`.
3. **Environment Variables**: `VITE_SUPABASE_URL` ve `VITE_SUPABASE_ANON_KEY` (Production + Preview).
4. Deploy. `vercel.json` tüm yolları `index.html`’e yönlendirir; `/admin/...` ve `/proje/...` adresleri doğrudan açılabilir.
5. Supabase → **Authentication → URL Configuration**: Site URL’yi Vercel adresiniz yapın ve
   `https://<vercel-adresi>/admin/parola` adresini Redirect URLs listesine ekleyin.

Her `main` gönderiminde Vercel otomatik yayımlar; dal (branch) gönderimleri önizleme adresi alır.

## GitHub Pages (alternatif)

1. Depo → **Settings → Pages → Source: GitHub Actions**.
2. (İsteğe bağlı) **Settings → Secrets and variables → Actions → Variables**: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.
3. `main` dalına gönderim → `.github/workflows/deploy.yml` tür denetimi ve birim testlerini çalıştırır, ardından
   `https://siiingularity.github.io/Tasarim1/` adresine yayımlar (`404.html` ile doğrudan alt sayfa erişimi).
4. Supabase Redirect URLs listesine `https://siiingularity.github.io/Tasarim1/admin/parola` ekleyin.

## Veritabanı değişiklikleri

- Şema değişikliklerini yeni bir göç dosyası olarak ekleyin (`supabase/migrations/<zaman>_<ad>.sql`), ardından
  `npm run db:seed:generate` ile `setup.sql`’i güncelleyin.
- Üretim veritabanına uygulamadan önce yerel ortamda veya bir test projesinde deneyin (`npm run test:db`).
- Göçler tekrar çalıştırılabilir yazılmıştır; yine de üretimde çalıştırmadan önce **Database → Backups** bölümünden yedeği kontrol edin.

## Yayın öncesi kontrol listesi

- [ ] `npm run typecheck && npm test && npm run build` başarılı
- [ ] Supabase’de herkese açık kayıt **kapalı**
- [ ] Redirect URLs yayın adresini içeriyor
- [ ] En az bir yönetici var; test hesapları silindi
- [ ] Storage’da `public-media` herkese açık, `private-files` özel
- [ ] `.env` dosyası depoda yok (`git status` ile kontrol edin)
