# Kurulum Rehberi (Supabase)

Bu rehber, platformu **sıfırdan yeni bir Supabase projesine** bağlamayı adım adım anlatır. Yaklaşık 15 dakika sürer.

## 1. Gereksinimler

- Node.js 20 veya üzeri, npm
- Ücretsiz bir [Supabase](https://supabase.com) hesabı
- (İsteğe bağlı) Yerel geliştirme için Docker + Supabase CLI

## 2. Supabase projesi oluşturun

1. Supabase panelinde **New project** → ad: `tasarim1-8bit`, bölge: size yakın (ör. Frankfurt), güçlü bir veritabanı parolası.
2. Proje hazır olunca **Project Settings → API** sayfasından şunları not edin:
   - **Project URL** → `VITE_SUPABASE_URL`
   - **anon / publishable key** → `VITE_SUPABASE_ANON_KEY`
   - `service_role` / secret anahtarını **hiçbir yere yazmayın**; uygulama buna ihtiyaç duymaz.

## 3. Veritabanını kurun

1. Panelde **SQL Editor → New query** açın.
2. Depodaki `supabase/setup.sql` dosyasının tamamını yapıştırıp **Run** düğmesine basın.
   - Bu betik tabloları, güvenlik ilkelerini (RLS), tetikleyicileri, iki depolama alanını (bucket) ve başlangıç verisini
     (5 aşama, 33 görev, 12 bileşen, 40 malzeme) oluşturur.
   - Betik **tekrar çalıştırılabilir**: mevcut kayıtları silmez veya değiştirmez.
3. Kontrol: **Table Editor**’de `materials` tablosunda 40 satır, **Storage**’da `public-media` ve `private-files` depoları görünmelidir.

> Supabase CLI kullanıyorsanız: `npx supabase link --project-ref <proje-kimliği>` ardından `npx supabase db push`
> komutu `supabase/migrations/` klasöründeki dosyaları sırayla uygular.

## 4. Kimlik doğrulamayı yapılandırın

**Authentication → Providers → Email**
- *Enable Email provider*: açık
- *Confirm email*: açık

**Authentication → Sign In / Providers → User Signups**
- **Allow new users to sign up: KAPALI** (herkese açık kayıt olmamalı; hesaplar yalnızca davetle oluşturulur)

**Authentication → URL Configuration**
- *Site URL*: sitenin yayın adresi, ör. `https://tasarim1.vercel.app`
- *Redirect URLs*: aşağıdakileri ekleyin
  - `https://tasarim1.vercel.app/admin/parola`
  - `http://localhost:5173/admin/parola` (yerel geliştirme)
  - GitHub Pages kullanıyorsanız: `https://siiingularity.github.io/Tasarim1/admin/parola`

## 5. İlk yöneticiyi oluşturun

1. **Authentication → Users → Add user → Send invitation** ile kendi e-posta adresinize davet gönderin
   (veya *Create new user* ile e-posta + parola belirleyin).
2. Davet e-postasındaki bağlantıya tıklayın; site sizi **/admin/parola** sayfasına getirir, yeni parolanızı belirleyin.
3. Her yeni kullanıcı varsayılan olarak **İzleyici** rolündedir. Kendinizi yönetici yapmak için SQL Editor’da:

   ```sql
   select public.set_user_role('sizin@eposta.adresiniz', 'admin');
   ```

   Bu işlev yalnızca SQL Editor’dan (veya mevcut bir yönetici tarafından) çalıştırılabilir; istemcilere kapalıdır.
4. Diğer ekip üyelerini aynı şekilde davet edin; rollerini artık panelde **Ayarlar → Kullanıcılar ve roller** bölümünden değiştirebilirsiniz.

| Rol | Yetki |
| --- | --- |
| Yönetici (`admin`) | Her şey: proje ayarları, kullanıcı rolleri, tüm içerik |
| Düzenleyici (`editor`) | İçerik ekleme, düzenleme, silme; etkinlik günlüğünü okuma (ayarlar ve roller hariç) |
| İzleyici (`viewer`) | Paneli salt okunur görür, yayımlanmamış kayıtları okuyabilir |

## 6. Uygulamayı bağlayın

```bash
cp .env.example .env
# .env içine:
# VITE_SUPABASE_URL=https://xxxx.supabase.co
# VITE_SUPABASE_ANON_KEY=eyJhbGciOi...
npm install
npm run dev
```

`http://localhost:5173/admin` adresinden giriş yapın. Genel sayfalar artık veritabanındaki verileri gösterir.

> `.env` dosyası `.gitignore` içindedir; **depoya göndermeyin**. Anon anahtarı herkese açık olacak şekilde tasarlanmıştır
> (tarayıcıya gömülür); asıl yetki RLS ilkeleriyle sağlanır.

## 7. Önceki sürümden kalan tarayıcı verileri

Sitenin eski sürümünde malzeme düzenlemeleri yalnızca ziyaretçinin tarayıcısında saklanıyordu. Bu veriler **silinmez**.
Aynı tarayıcıda panele girip **Malzemeler** sayfasına gidin: yerel veri bulunursa “Önizle ve aktar” uyarısı çıkar;
değişiklikleri görüp onayladığınızda ortak listeye aktarılır.

## 8. Yerel geliştirme (isteğe bağlı, Docker ile)

```bash
npx supabase start      # yerel Supabase (supabase/config.toml), göçler otomatik uygulanır
# Çıktıdaki API URL ve anon key değerlerini .env dosyasına yazın
npx supabase stop
```

## 9. TypeScript türlerini güncelleme

Şemada değişiklik yaptıysanız türleri yeniden üretin:

```bash
npx supabase gen types typescript --project-id <proje-kimliği> > src/lib/database.types.ts
# veya doğrudan veritabanı bağlantısıyla:
DATABASE_URL=postgres://... npm run db:types
```

## Sorun giderme

| Belirti | Çözüm |
| --- | --- |
| Panel “Veritabanı bağlantısı yapılandırılmamış” diyor | `.env` değişkenleri eksik; değiştirdikten sonra geliştirme sunucusunu yeniden başlatın |
| Girişten sonra “Profil bulunamadı” | Kullanıcı, kurulum betiğinden önce oluşturulmuş; `setup.sql`’i tekrar çalıştırın (eksik profilleri ekler) |
| Kaydetme sırasında “Bu işlem için yetkiniz yok” | Rolünüz izleyici; bir yöneticiden rol isteyin |
| Davet bağlantısı ana sayfaya gidiyor | Redirect URLs listesine `/admin/parola` adresini ekleyin |
| Yükleme “Bu dosya türünün…” hatası veriyor | Dosya türü o depo için izinli değil; bkz. DATABASE.md → Depolama |
