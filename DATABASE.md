# Veritabanı Tasarımı

Göç dosyaları: `supabase/migrations/` (0001 şema · 0002 güvenlik · 0003 depolama · 0004 başlangıç verisi).
Tümü tekrar çalıştırılabilir; hiçbiri veri silmez. `supabase/setup.sql` bunların birleşimidir.

## Tablolar

| Tablo | Amaç | Önemli alanlar |
| --- | --- | --- |
| `profiles` | Auth kullanıcısının uygulama profili (1:1 `auth.users`) | `role` (admin / editor / viewer) |
| `project_settings` | Tek satırlık proje ayarları | başlık, danışman, ekip (`team_members` jsonb), GitHub adresi, `usd_try_rate` + tarih, `tasarim_ii_active` |
| `project_phases` | Tasarım I / II aşamaları | `semester`, `status`, `weight` (toplam 100), `start_date`, `target_date`, `route` |
| `project_tasks` | Aşama görevleri | `phase_id`, `component_id`, `status`, `priority`, `weight`, `assigned_to`, `due_date`, `completed_at` |
| `project_components` | Bilgisayar modülleri (12 adet) | `slug`, `status`, `architecture_notes` |
| `simulations` | Simülasyon deneyleri | amaç, yöntem, giriş, işlem, beklenen/gözlenen çıktı, `result_status`, `experiment_date`, `is_published` |
| `progress_updates` | Kilometre taşları / gelişmeler | `update_date`, `status`, `progress_value` (yalnızca bilgi), `is_published` |
| `media_files` | Storage dosyalarının meta verisi | `bucket_name`, `storage_path`, `category`, bağlantılar (bileşen, deney, ilerleme kaydı) |
| `technical_documents` | Teknik belgeler | `document_type`, `file_id` → `media_files`, `version`, `is_published` |
| `materials` | Malzeme listesi | gerekli/satın alınan adet, yerel `unit_price` + `currency`, değişmez `ref_*` referans değerleri |
| `purchases` | Gerçek satın almalar | `material_id`, adet, birim fiyat, para birimi, tarih, tedarikçi, `receipt_file_id` |
| `activity_logs` | Değişiklik geçmişi | eylem, kullanıcı, kayıt, değişen alanlar (eski → yeni) |

### İlişkiler ve silme kuralları

- Aşama silinirse **görevleri de silinir** (cascade); ilerleme kayıtları korunur (`set null`).
- Bileşen, deney veya ilerleme kaydı silinirse bağlı dosyalar **silinmez**, yalnızca bağlantı kaldırılır.
- Bir belgede veya satın alma makbuzunda kullanılan dosya **silinemez** (`restrict`); önce belge/satın alma silinmelidir.
- Satın alma kaydı olan malzeme **silinemez** (mali kayıt kaybını önler).

## Güvenlik (Row Level Security)

Tüm tablolarda RLS açıktır. Ayrıca tablo yetkileri (GRANT) RLS’e ek bir savunma katmanı olarak kısıtlanmıştır.

| Tablo | Ziyaretçi (anon) | İzleyici | Düzenleyici | Yönetici |
| --- | --- | --- | --- | --- |
| aşama, görev, bileşen, malzeme, satın alma | okur | okur | okur/yazar/siler | okur/yazar/siler |
| deney, ilerleme kaydı, belge | yalnızca yayımlananı okur | tümünü okur | okur/yazar/siler | okur/yazar/siler |
| medya | yalnızca açık depodakileri | tümünü | okur/yazar/siler | okur/yazar/siler |
| proje ayarları | okur | okur | okur | okur/günceller |
| profiller | — | ekibi okur, kendi adını değiştirir | aynı | rolleri değiştirir |
| etkinlik günlüğü | — | — | okur | okur |

Rol denetimi `public.current_app_role()`, `is_admin()`, `can_edit()`, `can_view_private()` işlevleriyle yapılır
(`security definer`, sabit `search_path`).

**Ek korumalar (tetikleyiciler):**
- Rol yalnızca yönetici tarafından değiştirilebilir; son yönetici düşürülemez.
- `created_by`, `uploaded_by`, `updated_by`, `created_at` sunucuda atanır; istemcinin gönderdiği değer yok sayılır.
- `materials.purchased_quantity` her zaman satın alma kayıtlarının toplamıdır; doğrudan değiştirilemez.
- “Başarılı / Başarısız” deney sonucu, gözlenen çıktı ve deney tarihi olmadan kaydedilemez (`result_needs_evidence`).
- Yayımlanan belgenin dosyası herkese açık depoda olmalıdır; yayımlanmış belgenin dosyası özel depoya taşınamaz.
- Aşama ağırlıkları yalnızca `set_phase_weights(jsonb)` işleviyle, toplamı 100 olacak şekilde topluca değişir.

### Etkinlik günlüğü

`tg_log_activity` tetikleyicisi 11 tabloda ekleme/güncelleme/silme işlemlerini kaydeder. Güncellemelerde yalnızca değişen
alanlar (eski → yeni) saklanır. Günlüğe **hiçbir istemci yazamaz, güncelleyemez veya silemez**; kullanıcı bilgisi
oturumun JWT’sinden (`auth.uid()`) alınır, istemci tarafından taklit edilemez. SQL Editor’dan yapılan değişiklikler
“Sistem” olarak görünür.

## Depolama (Storage)

| Depo | Görünürlük | Boyut sınırı | İzin verilen uzantılar |
| --- | --- | --- | --- |
| `public-media` | herkese açık okuma | 20 MB | png, jpg, jpeg, webp, gif, pdf, zip, txt, csv, dig, circ, pdsprj, hex, bin, asm, ino |
| `private-files` | yalnızca ekip (imzalı bağlantı, 1 saat) | 50 MB | yukarıdakiler + xml, docx, xlsx, pptx |

- Yol biçimi `<kategori>/<yıl>/<uuid>.<uzantı>`; özgün dosya adı yolda kullanılmaz (meta veride saklanır).
- HTML, SVG ve XML gibi tarayıcıda çalışabilen türler herkese açık depoya yüklenemez. Simülasyon kaynak dosyaları
  `application/octet-stream` olarak saklanır, yani her zaman **indirilir**, tarayıcıda çalıştırılmaz.
- Yükleme/güncelleme/silme yalnızca düzenleyici ve yöneticiye açıktır; yol ve uzantı kuralı `storage_path_allowed()` ile sunucuda denetlenir.

## İlerleme hesabı

Tek ve belgelenmiş yöntem (`src/lib/progress.ts`):

1. **Aşama ilerlemesi** = tamamlanan görevlerin ağırlıkları ÷ tüm görevlerin ağırlıkları × 100
2. **Genel ilerleme** = Σ (aşama ağırlığı × aşama ilerlemesi) ÷ Σ aşama ağırlıkları (ağırlıkların toplamı 100 olmalıdır)
3. **Dönem ilerlemesi** = (2) yalnızca o dönemin aşamalarıyla
4. **Bileşen ilerlemesi** = bileşene bağlı görevlerden (1) ile aynı yöntem

Elle girilen yüzde yoktur. `progress_updates.progress_value` yalnızca tarihsel bir not olup hesaba katılmaz.
Başlangıçta her aşamanın ağırlığı 20’dir.

## Maliyet hesabı

`src/lib/costs.ts`:
- Birim fiyat önceliği: **yerel teklif** (`unit_price`, varsayılan TL) → yoksa **referans** fiyat (`ref_unit_price_min/max`, USD, tarihsel).
- Toplamlar **para birimine göre ayrı** tutulur; birleşik TL tahmini yalnızca `project_settings.usd_try_rate` (veya ziyaretçinin girdiği kur) varsa gösterilir.
- Kalan maliyet: (gerekli − satın alınan) adet × birim fiyat. Kayıtlı harcama: satın alma kayıtlarından; fiyatsız kayıtlar sayılır ama toplanmaz.
- Referans listedeki satır toplamları (`ref_stated_total_*`) değiştirilmeden saklanır; adet × birim fiyattan farklı olan 9 satır sitede ayrıca gösterilir.

## Başlangıç verisi

`scripts/generate-seed.mjs`, `src/data/fallback.ts` modülünü kullanarak 0004 göçünü üretir; statik site ile veritabanı aynı kaynaktan beslenir.
İçerik: proje ayarları, 5 aşama, 33 planlanan görev (yalnızca “GitHub deposunun oluşturulması” tamamlanmış), 12 bileşen,
38 referans malzeme + 2 EEPROM programlayıcı malzemesi. Deney, satın alma, fotoğraf veya ilerleme kaydı **eklenmez**.
