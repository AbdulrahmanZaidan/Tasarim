# Yönetim Paneli Kullanım Kılavuzu

Panel adresi: `https://<siteniz>/admin` · Giriş: davetle oluşturulan e-posta + parola.
Sitenin alt kısmındaki **Ekip girişi** bağlantısı da panele götürür.

## Genel bakış

İlk ekran projenin özetidir: genel / Tasarım I / Tasarım II ilerlemesi, aşama çubukları, deney sonuç dağılımı,
bekleyen ve gecikmiş görevler, malzeme adetleri, tahmini maliyet ve kayıtlı harcama, yaklaşan hedefler, son yüklemeler
ve son etkinlikler. Tüm değerler kayıtlı verilerden hesaplanır.

## Simülasyon deneyi ekleme

1. **Simülasyonlar → Yeni deney**.
2. Başlık, ilgili bileşen (ör. *Aritmetik Mantık Birimi*), yazılım (Digital / Logisim Evolution / Proteus) ve sürüm.
3. Amaç, yöntem, **giriş değerleri**, yapılan işlem, **beklenen çıktı** alanlarını doldurun.
   *ALU toplama şablonu* düğmesi örnek değerleri (A = 00000101, B = 00000011, beklenen 00001000) doldurur; gözlenen çıktıyı doldurmaz.
4. Deneyi simülatörde gerçekten çalıştırdıktan sonra **gözlenen (gerçek) çıktıyı** ve **deney tarihini** girin.
   Sonuç durumunu “Başarılı” veya “Başarısız” yapmak için bu iki alan zorunludur.
5. **Kaydet** → aynı pencerede ekran görüntüsü ve dosya yükleme alanı açılır.
6. Hazır olduğunda **Genel sitede yayımla** kutusunu işaretleyip kaydedin. Özel depodaki ekler için
   **Ekleri herkese açık yap** düğmesini kullanın; ancak o zaman ziyaretçiler görüntüleri görebilir.

Yayımlanan deneyler **Simülasyon** sayfasındaki “Deney kayıtları” galerisinde, ilgili bileşen sayfasında ve
test senaryosunun altında görünür. Tarayıcı içi eğitsel demolar bu kayıtlardan bağımsızdır ve değişmeden kalır.

## Ekran görüntüsü ve dosya yükleme

**Medya → Dosya yükle**
- Dosyaları sürükleyip bırakın veya *Dosya seç* ile birden çok dosya seçin. Her dosyanın yükleme ilerlemesi ayrı gösterilir.
- **Kategori** (simülasyon ekran görüntüsü, devre şeması, breadboard fotoğrafı, …), **görünürlük** (özel / herkese açık) ve **bileşen** seçin.
- Desteklenmeyen tür veya fazla büyük dosya yüklenmeden reddedilir; sunucu da aynı kuralları uygular.

Medya kartlarındaki düğmeler: indir · düzenle (başlık, açıklama, kategori, bileşen, deney, ilerleme kaydı) ·
**dosyayı değiştir** (bilgiler korunur) · görünürlüğü değiştir · sil. Görsele tıklayınca tam ekran görüntüleyici açılır
(← → tuşlarıyla gezinme, Esc ile kapatma). Arama, kategori/görünürlük/bileşen süzgeci ve tarih sıralaması vardır.

## Görevler ve ilerleme

- **Görevler**: her görev bir aşamaya (isteğe bağlı olarak bir bileşene) bağlıdır. Durumu tablodan doğrudan değiştirebilir,
  ✓ düğmesiyle tamamlandı olarak işaretleyebilirsiniz; tamamlanma tarihi otomatik kaydedilir. Gecikmiş görevler kırmızı görünür.
- **Aşamalar**: durum, tarih, açıklama ve **ağırlık**. Ağırlıkların toplamı 100 olmalıdır; “Eşit dağıt” yardımcı olur.
  Tasarım II aşamasını yalnızca gerçekten başladığında “Devam Ediyor” yapın.
- **İlerleme Kayıtları**: tamamlanan bir çalışmayı (ör. “Saat modülü breadboard’a kuruldu”) tarih, açıklama ve
  fotoğraflarla kaydedin. Yayımlanan kayıtlar İlerleme Durumu sayfasındaki zaman çizelgesinde görünür.
- **Bileşenler**: her modülün durumu ve mimari notları; bileşen sayfasında görev, deney, görsel ve belgeler birleşir.

## Malzemeler ve satın almalar

- **Malzemeler**: ad, kategori, gerekli adet, yerel birim fiyat (varsayılan TL), tedarikçi, ürün bağlantısı, durum, notlar.
  Referans liste değerleri değiştirilemez ve karşılaştırma için saklanır.
- **CSV dışa aktar / içe aktar**: dışa aktarılan dosyayı Excel’de düzenleyip geri yükleyebilirsiniz. İçe aktarmada önce
  önizleme gösterilir (yeni / güncellenecek / değişmeyen / hatalı satırlar, dosya içi yinelenen kodlar); onayladığınızda uygulanır. Hiçbir kalem silinmez.
- **Satın Almalar → Satın alma kaydet**: malzeme, adet, birim fiyat, para birimi, tarih, tedarikçi ve isteğe bağlı makbuz
  (özel depoda saklanır). Kayıt, malzemenin “satın alınan adet” değerini otomatik günceller.
- Döviz kuru **Ayarlar** sayfasından tarihiyle kaydedilir; o zaman USD ve TL tutarları birleşik tahminde toplanır.

## Teknik belgeler

**Belgeler → Yeni belge**: başlık, tür (proje raporu, devre şeması, test raporu, …), bileşen, sürüm ve dosya.
“Herkese açık yayımla” işaretlenirse dosya açık depoya konur ve **Teknik Belgeler** sayfasında listelenir; yayından
kaldırınca dosya özel depoya alınır. Dosyayı değiştirirken sürüm numarasını artırın. PDF’ler panelde ve sitede önizlenebilir.

## Ayarlar (yalnızca yönetici)

Proje başlığı/açıklaması, üniversite, ders, danışman, akademik yıl, GitHub adresi, ekip listesi, varsayılan para birimi,
döviz kuru ve **Tasarım II başladı** anahtarı. Altta kullanıcı listesi ve rol değiştirme bulunur.
Yeni ekip üyesi Supabase panelinden davet edilir (SETUP.md §5).

## Etkinlik günlüğü (yönetici ve düzenleyici)

Kim, ne zaman, hangi kaydı değiştirdi; güncellemelerde eski → yeni değerler. Tür, kullanıcı ve ada göre süzülebilir.
Kayıtlar veritabanı tarafından yazılır; panelden değiştirilemez veya silinemez.

## İpuçları

- Formlarda kaydedilmemiş değişiklik varken sayfadan ayrılmak isterseniz uyarı çıkar.
- Aynı kaydı iki kişi aynı anda düzenlerse ikinci kayıt reddedilir ve sayfayı yenilemeniz istenir (veri kaybı olmaz).
- Panel telefonda da kullanılabilir; menü sağ üstteki düğmededir.
