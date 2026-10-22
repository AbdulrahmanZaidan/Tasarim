/**
 * MERKEZİ PROJE VERİLERİ
 * ------------------------------------------------------------
 * Proje durumu, ilerleme yüzdeleri, görevler ve bağlantılar bu dosyadan
 * güncellenir. Burada yalnızca GERÇEKLEŞMİŞ / DOĞRULANMIŞ bilgiler
 * "completed" olarak işaretlenmelidir.
 */

export type StageStatus = 'completed' | 'in_progress' | 'planned' | 'not_started';

export const statusLabels: Record<StageStatus, string> = {
  completed: 'Tamamlandı',
  in_progress: 'Devam Ediyor',
  planned: 'Planlandı',
  not_started: 'Henüz Başlamadı',
};

export const project = {
  university: 'Süleyman Demirel Üniversitesi',
  course: 'Tasarım I · Bitirme Projesi',
  title: '8-Bit Breadboard Bilgisayar',
  subtitle: 'Sıfırdan Tasarlanan Programlanabilir 8-Bit Bilgisayar',
  advisor: 'Doç. Dr. Fatih Şenel',
  students: [
    { name: 'Abdelrahman Ahmad Radwan Zidan', id: '2321032807' },
    { name: 'Taha Deniz Akgül', id: '2426512003' },
  ],
  links: {
    repo: 'https://github.com/Siiingularity/Tasarim1',
    repoApi: 'https://api.github.com/repos/Siiingularity/Tasarim1',
  },
};

/**
 * Tasarım II başladığında bu değeri `true` yapın.
 * Böylece Tasarım II sayfası "Yakında" görünümünden çıkar ve
 * aşama 5'in görevleri ilerleme sayfasında etkin olarak gösterilir.
 */
export const TASARIM_II_ACTIVE = false;

export interface Milestone {
  label: string;
  done: boolean;
  /** Tamamlanan kilometre taşları için kanıt bağlantısı (ör. GitHub). */
  evidence?: string;
}

export interface Stage {
  id: 'architecture' | 'simulation' | 'github' | 'materials' | 'tasarim2';
  number: string;
  title: string;
  shortTitle: string;
  path: string;
  semester: 'Tasarım I' | 'Tasarım II';
  summary: string;
  deliverable: string;
  status: StageStatus;
  /** 0–100 arası gerçek değer; bilinmiyorsa null bırakın. */
  progress: number | null;
  /** ISO tarih (YYYY-AA-GG); yalnızca gerçekten biliniyorsa doldurun. */
  lastUpdated: string | null;
  currentTasks: string[];
  nextTasks: string[];
  milestones: Milestone[];
}

export const projectStages: Stage[] = [
  {
    id: 'architecture',
    number: '01',
    title: 'Mimari ve Şema',
    shortTitle: 'Mimari',
    path: '/proje/mimari-sema',
    semester: 'Tasarım I',
    summary:
      "Bilgisayarın blok diyagramı ile saat, yazmaçlar, ALU, RAM, program sayacı, çıkış ve kontrol biriminin devre şemaları hazırlanır; komut seti ve kontrol sinyalleri belirlenir.",
    deliverable: 'Tam devre şeması ve blok diyagram',
    status: 'planned',
    progress: 0,
    lastUpdated: null,
    currentTasks: ['Ben Eater referans mimarisinin modül modül incelenmesi'],
    nextTasks: [
      'Blok diyagramın proje ekibince çizilmesi',
      'Modül devre şemalarının hazırlanması',
      'Komut seti ve kontrol kelimesinin kesinleştirilmesi',
    ],
    milestones: [
      { label: 'Genel blok diyagram', done: false },
      { label: 'Modül devre şemaları', done: false },
      { label: 'Komut seti ve mikrokod tablosu', done: false },
    ],
  },
  {
    id: 'simulation',
    number: '02',
    title: 'Simülasyon',
    shortTitle: 'Simülasyon',
    path: '/proje/simulasyon',
    semester: 'Tasarım I',
    summary:
      'Devre, Digital (H. Neemann) veya Proteus ortamında kurularak her modül ayrı ayrı test edilir; ardından modüller birleştirilerek örnek programlar çalıştırılır.',
    deliverable: 'Çalışan simülasyon ve örnek programlar',
    status: 'planned',
    progress: 0,
    lastUpdated: null,
    currentTasks: ['Simülasyon aracının seçilmesi (Digital / Proteus)'],
    nextTasks: [
      'Saat ve yazmaç modüllerinin simülasyonu',
      'ALU, RAM ve program sayacı simülasyonu',
      'Kontrol birimi ve tam sistem simülasyonu',
    ],
    milestones: [
      { label: 'Modül bazlı simülasyonlar', done: false },
      { label: 'Bütünleşik sistem simülasyonu', done: false },
      { label: 'Örnek programların çalıştırılması', done: false },
    ],
  },
  {
    id: 'github',
    number: '03',
    title: 'GitHub Deposu',
    shortTitle: 'GitHub',
    path: '/proje/github',
    semester: 'Tasarım I',
    summary:
      'Şemalar, simülasyon dosyaları, mikrokod/EEPROM kodları ve dokümanlar GitHub deposunda toplanır; sürüm takibi ve ekip içi iş bölümü buradan yürütülür.',
    deliverable: 'Düzenli proje deposu',
    status: 'planned',
    progress: 0,
    lastUpdated: null,
    currentTasks: ['Depo klasör yapısının belirlenmesi'],
    nextTasks: ['README ve dokümantasyonun eklenmesi', 'Şema ve simülasyon dosyalarının yüklenmesi'],
    milestones: [
      // Depo oluşturulmuştur (github.com/Siiingularity/Tasarim1). Bu, aşamanın
      // tamamlandığı anlamına gelmez; yalnızca ilk kilometre taşıdır.
      { label: 'Depo oluşturuldu (henüz boş)', done: true, evidence: 'https://github.com/Siiingularity/Tasarim1' },
      { label: 'README ve klasör yapısı', done: false },
      { label: 'Teknik dosyaların düzenli eklenmesi', done: false },
    ],
  },
  {
    id: 'materials',
    number: '04',
    title: 'Malzeme ve Maliyet Analizi',
    shortTitle: 'Malzeme',
    path: '/proje/malzeme-maliyet',
    semester: 'Tasarım I',
    summary:
      'Malzeme listesi simülasyon sonuçlarına göre kesinleştirilir; entegreler, breadboard’lar ve diğer parçalar temin edilip test edilir. EEPROM programlayıcı hazırlanır.',
    deliverable: 'Eksiksiz ve test edilmiş malzeme seti',
    status: 'planned',
    progress: 0,
    lastUpdated: null,
    currentTasks: ['Referans malzeme listesinin çıkarılması'],
    nextTasks: ['Türkiye tedarikçilerinden fiyat alınması', 'Siparişlerin verilmesi', 'Gelen parçaların test edilmesi'],
    milestones: [
      { label: 'Referans malzeme listesi', done: false },
      { label: 'Yerel fiyat teklifleri', done: false },
      { label: 'Satın alma ve parça testleri', done: false },
    ],
  },
  {
    id: 'tasarim2',
    number: '05',
    title: 'Tasarım II: Uygulamaya Geçiş',
    shortTitle: 'Tasarım II',
    path: '/proje/tasarim-ii',
    semester: 'Tasarım II',
    summary:
      'İkinci dönemde modüller breadboard üzerinde kurulur, test edilir ve birleştirilerek çalışan 8-bit bilgisayar elde edilir.',
    deliverable: 'Çalışan 8-bit breadboard bilgisayar',
    status: 'not_started',
    progress: 0,
    lastUpdated: null,
    currentTasks: [],
    nextTasks: ['Tasarım I çıktılarının tamamlanması'],
    milestones: [],
  },
];

/** Tasarım II için planlanan yol haritası (henüz başlamamıştır). */
export const tasarimIIRoadmap = [
  { title: 'Modüllerin Breadboard Üzerinde Kurulması', text: 'Saat, yazmaçlar, ALU, RAM, program sayacı, çıkış ve kontrol modüllerinin ayrı breadboard’lar üzerinde kurulması.' },
  { title: 'Devrelerin Test Edilmesi', text: 'Her modülün LED göstergeler ve manuel saat adımlarıyla bağımsız olarak doğrulanması.' },
  { title: 'Veri Yolunun Birleştirilmesi', text: 'Modüllerin 8-bit ortak veri yoluna 74LS245 üç-durumlu tamponlar üzerinden bağlanması.' },
  { title: 'Kontrol Biriminin Entegrasyonu', text: 'EEPROM tabanlı mikrokodun programlanması ve kontrol sinyallerinin modüllere dağıtılması.' },
  { title: 'Programların Çalıştırılması', text: 'Toplama, çıkarma ve döngü içeren örnek programların RAM’e yüklenip çalıştırılması.' },
  { title: 'Nihai Sistem Testleri', text: 'Tüm komut setinin, bayrakların ve koşullu atlamaların bütünleşik sistemde sınanması.' },
];

/**
 * Simülasyon ekran görüntüleri galerisi.
 * Kendi görüntülerinizi `public/simulasyon/` klasörüne ekleyip burada listeleyin.
 * Örnek:
 *   { src: 'simulasyon/saat-modulu.png', title: 'Saat modülü — Digital', date: '2026-11-02', tool: 'Digital' }
 */
export interface GalleryItem {
  src: string;
  title: string;
  tool: 'Digital' | 'Proteus' | 'Diğer';
  date?: string;
  file?: string; // ilgili .dig / .pdsprj dosyasının depo bağlantısı
}
export const simulationGallery: GalleryItem[] = [];

export function overallProgress(stages: Stage[] = projectStages) {
  const known = stages.filter((s) => typeof s.progress === 'number') as (Stage & { progress: number })[];
  if (known.length === 0) return null;
  return Math.round(known.reduce((a, s) => a + s.progress, 0) / known.length);
}
