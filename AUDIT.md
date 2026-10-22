# Kod Tabanı Denetimi (Supabase geçişi öncesi)

Tarih: 22.10.2026 · Kapsam: `Siiingularity/Tasarim1` deposunun `main` dalındaki React uygulaması.

## 1. Mevcut yapı

| Katman | Durum |
| --- | --- |
| Teknoloji | React 18, TypeScript 5 (strict), Vite 5, Tailwind 3, React Router 6 (`BrowserRouter` / tek dosya derlemesinde `HashRouter`), Lucide |
| Rotalar | `/`, `/proje`, `/proje/mimari-sema`, `/proje/simulasyon`, `/proje/github`, `/proje/malzeme-maliyet`, `/proje/tasarim-ii`, `/proje/ilerleme`, `*` (404) |
| Tasarım sistemi | `src/index.css` (`.card`, `.btn-*`, `.eyebrow`, `.rule` …) + `tailwind.config.js` renk belirteçleri (`brand`, `ink`) + `components/ui.tsx` |
| Dağıtım | `vercel.json` (SPA yönlendirmesi), GitHub Pages iş akışı (`build:gh`, `404.html` kopyası), tek dosyalık önizleme modu (`--mode single`) |
| Test | Yok |

## 2. Uygulanmış özellikler

- Ana sayfa, proje planı (numaralı zaman çizelgesi), Tasarım II “Yakında” sayfası.
- Mimari sayfası: etkileşimli blok diyagramı (`SystemDiagram`), 9 modül + komut seti/mikrokod + çalışma döngüsü açıklamaları, `CpuRunner` mikro adım yürütücüsü.
- Simülasyon sayfası: 9 test senaryosu ve 6 tarayıcı içi eğitsel demo (`sims.tsx`: toplayıcı, yazmaç, program sayacı, RAM, saat, komut çözme) + örnek program yürütücüsü; boş galeri.
- GitHub sayfası: GitHub REST API ile depo meta verisi ve kök içerik listesi; hata ve boş durumları.
- Malzeme ve maliyet: 38 kalemlik referans liste, arama/filtre/sıralama, düzenleme kipi, durum takibi, kur ile TL tahmini, CSV dışa aktarma, tutarsız satır tablosu, kategori grafiği, EEPROM programlayıcı ek malzemeleri.
- İlerleme sayfası: aşama durumları, görevler, kilometre taşları, genel ilerleme ortalaması.

## 3. Sabit (hardcoded) veriler

| Dosya | İçerik | Geçiş kararı |
| --- | --- | --- |
| `src/data/projectData.ts` | Proje bilgileri, 5 aşama (durum, yüzde, görevler, kilometre taşları), Tasarım II yol haritası, `simulationGallery`, `TASARIM_II_ACTIVE` | Supabase’e taşınır (`project_settings`, `project_phases`, `project_tasks`, `progress_updates`). Dosya, **Supabase yapılandırılmamışsa yedek veri** olarak korunur. |
| `src/data/parts.ts` | 38 malzeme, referans fiyat aralıkları, kaynak satır toplamları, 2 ek programlayıcı malzemesi | `materials` tablosuna tohumlanır (referans alanlar değiştirilmeden). Dosya yedek veri olarak kalır. |
| `src/data/architecture.ts` | Modül eğitsel açıklamaları ve diyagram yerleşimi | **Statik kalır** (eğitsel içerik, kod ile birlikte sürümlenir). Bileşen ilerlemesi/kanıtları `project_components` ve ilişkili tablolardan gelir. |
| `src/lib/cpu.ts` | Komut seti, mikrokod, CPU modeli | Statik kalır. |

## 4. localStorage bağımlılıkları

- `sdu8bit.materials.v1` (`MaterialsPage` → `useLocalState`): ziyaretçinin adet, birim fiyat (USD), satın alma durumu, kargo, kur, “ek malzemeleri dâhil et” seçimleri.
- Risk: Bu veriler yalnızca ilgili tarayıcıdadır; ekip üyeleri arasında paylaşılmaz.
- Karar: Supabase yapılandırıldığında genel sayfada düzenleme kapatılır, veriler veritabanından okunur. Yerel veriler **silinmez**; yönetici panelinde (`/admin/materials` → “Tarayıcı verilerini içe aktar”) önizlemeli ve onaylı içe aktarma sunulur. Kur ve kargo alanları ziyaretçi kolaylığı olarak sayfada kalır.

## 5. Dinamik çizime hazır bölümler

`Timeline`, `ProgressPage`, `PlanPage`, `HomePage` aşama listesini `projectStages` dizisinden çizer → aynı şekle dönüştürülen veritabanı verisiyle doğrudan çalışabilir. `MaterialsPage` satırları dizi üzerinden üretir. `GithubPage` zaten uzak veri kullanır.

## 6. Yeniden kullanılacak bileşenler

`PageHeader`, `Section`, `Figure`, `Callout`, `Disclosure`, `StatusBadge`, `Stat`, `ProgressBar`, `Bits`, `Breadcrumbs`, `StageNav`, `Timeline`, `SystemDiagram`, tüm `sims.tsx` demoları, `CpuRunner`, CSS bileşen sınıfları.

## 7. Supabase’e taşınacak durum

Proje ayarları, aşamalar, görevler, bileşen durumu, simülasyon deneyleri, medya ve belgeler (Storage + meta veri), malzemeler, satın almalar, ilerleme kayıtları, etkinlik günlüğü, kullanıcı rolleri.

## 8. Statik kalacak içerik

Eğitsel açıklamalar (modüller, simülasyon senaryo metinleri), diyagramlar, tarayıcı içi simülasyonlar, komut seti, tasarım belirteçleri.

## 9. Geçişte bozulabilecek işlevler

- GitHub Pages derlemesi ve tek dosya önizleme: Supabase ortam değişkenleri olmadan da çalışmalı → **yedek veri modu**.
- `StatusBadge` yalnızca 4 durum biliyor → `blocked` (Engellendi) eklenmeli.
- `ProgressPage` yüzdeleri elle girilmiş değerlerin ortalaması → görev tamamlanma oranına dayalı tek ve belgelenmiş hesaba geçilecek.
- `BrowserRouter` kaydedilmemiş değişiklik uyarısı (`useBlocker`) desteklemez → veri yönlendiricisine (`createBrowserRouter`) geçilecek; rotalar aynı kalacak.
- Malzeme sayfasındaki yerel düzenlemeler, veritabanı modunda gizlenecek; kullanıcı verisi silinmeyecek.

## 10. Korunması zorunlu davranışlar

Tüm genel rotalar ve görünüm; tarayıcı içi simülasyonlar; CSV dışa aktarma; kaynak satır toplamları ile hesaplanan toplamların ayrı gösterimi; “kanıt olmadan tamamlandı sayılmaz” ilkesi; Türkçe arayüz; Vercel ve GitHub Pages dağıtımı.
