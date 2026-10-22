# Sürüm Notları

## 2.0.0 — 22.10.2026 · Veritabanı destekli proje platformu

### Eklendi
- **Supabase arka ucu**: 12 tablo, Row Level Security, rol işlevleri, tetikleyiciler, iki depolama alanı ve tekrar çalıştırılabilir göçler (`supabase/`).
- **Kimlik doğrulama**: e-posta + parola girişi, davetle hesap, parola sıfırlama/belirleme (`/admin/parola`), oturum yenileme; herkese açık kayıt kapalı.
- **Yönetim paneli** (`/admin`): genel bakış panosu, simülasyonlar, medya, bileşenler, aşamalar (ağırlık düzenleyici), görevler, ilerleme kayıtları, malzemeler, satın almalar, belgeler, ayarlar (kullanıcı rolleri), etkinlik günlüğü.
- **Medya yönetimi**: sürükle-bırak çoklu yükleme, dosya başına ilerleme, tür/boyut doğrulama, açık/özel depo, dosya değiştirme, tam ekran görüntüleyici, indirme.
- **Deney kayıtları**: kanıta dayalı sonuç (gözlenen çıktı + tarih zorunlu), ekran görüntüleri ve `.dig`/`.circ` dosyaları, genel galeri (bileşen/yazılım/sonuç süzgeci), deney ayrıntı sayfası.
- **Bileşen sayfaları** (`/proje/bilesen/:slug`) ve **Teknik Belgeler** sayfası (`/proje/belgeler`); mimari modüllerden simülasyon, görsel ve ilerlemeye bağlantılar.
- **İlerleme**: görev tabanlı tek hesap yöntemi, dönem ilerlemesi, fotoğraflı proje günlüğü (zaman çizelgesi).
- **Malzeme ve maliyet**: ortak liste, satın alma kayıtları ve makbuzlar, para birimine göre ayrı toplamlar, kayıtlı kurla birleşik TL tahmini, önizlemeli CSV içe aktarma, eski tarayıcı verilerinin onaylı aktarımı.
- **GitHub sayfası**: son commit’ler, ana dizinler, önemli dosyalar, önerilen klasörlerin gerçek durumu, istek sınırı yönetimi ve önbellek.
- Testler: birim, veritabanı güvenliği (RLS), gerçek Supabase hizmetleriyle API ve tarayıcı uçtan uca testleri; CI iş akışı.
- Belgeler: SETUP, DATABASE, ADMIN_GUIDE, DEPLOYMENT, TESTING, AUDIT.

### Değişti
- Yönlendirici veri yönlendiricisine (`createBrowserRouter`) geçirildi; adresler aynı kaldı. Sayfalar ayrı paketlere bölündü.
- Aşama yüzdeleri artık elle girilmez; tamamlanan görevlerden hesaplanır. “Engellendi” durumu eklendi.
- Genel sayfalar, Supabase yapılandırılmışsa veritabanından okur; yapılandırılmamışsa veya bağlantı kurulamazsa statik veriler gösterilir ve bu durum açıkça belirtilir.

### Korundu
- Görsel kimlik, tüm genel sayfalar, tarayıcı içi simülasyonlar, CPU yürütücüsü, diyagramlar, CSV dışa aktarma ve 38 kalemlik referans liste (kaynak satır toplamları dâhil).

## 1.0.0 — 20.10.2026
- Tasarım I tanıtım sitesi: proje planı, mimari ve şema, simülasyon, GitHub, malzeme ve maliyet, ilerleme, Tasarım II.
