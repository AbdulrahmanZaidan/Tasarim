/**
 * Mimari modül açıklamaları.
 * Entegre listeleri referans tasarımdaki modül sayfalarına dayanır; proje
 * ekibinin kendi şemaları tamamlandığında bu dosya güncellenmelidir.
 */
import type { Signal } from '../lib/cpu';

export type ModuleId = 'clock' | 'registers' | 'alu' | 'ram' | 'pc' | 'ir' | 'control' | 'output' | 'bus';

export interface ArchModule {
  id: ModuleId;
  index: number;
  title: string;
  en: string;
  what: string;
  why: string;
  how: string[];
  inputs: string[];
  outputs: string[];
  interacts: string;
  ics: { part: string; role: string }[];
  example: string;
  role: string;
  signals: Signal[];
}

export const modules: ArchModule[] = [
  {
    id: 'clock', index: 1, title: 'Saat Devresi', en: 'Clock Module',
    what: 'Bilgisayardaki tüm senkron işlemleri zamanlayan kare dalga üreteci.',
    why: 'Yazmaçlar, sayaçlar ve kontrol birimi değerlerini yalnızca saat sinyalinin yükselen kenarında günceller. Saat olmadan veri hareketi düzenli ve öngörülebilir olamaz.',
    how: [
      'Kararsız (astable) modda çalışan 555, potansiyometre ile ayarlanabilen frekansta sürekli kare dalga üretir.',
      'Tek kararlı (monostable) moddaki 555, butona her basışta tek ve sıçramasız (debounced) bir darbe üretir; böylece bilgisayar adım adım çalıştırılabilir.',
      'Çift kararlı (bistable) moddaki 555, otomatik / manuel kip seçim anahtarının sıçramasını giderir.',
      'AND, OR ve NOT kapıları seçilen kaynağı çıkışa aktarır; HLT sinyali aktif olduğunda saat durdurulur.',
    ],
    inputs: ['Kip seçim anahtarı (otomatik / manuel)', 'Manuel adım butonu', 'Frekans ayar potansiyometresi', 'HLT kontrol sinyali'],
    outputs: ['CLK — tüm modüllere giden saat sinyali', 'CLK̅ — kontrol biriminin adım sayacı için terslenmiş saat'],
    interacts: 'Veri yoluna bağlanmaz; saat hattı üzerinden tüm yazmaçları, program sayacını ve kontrol birimini sürer.',
    ics: [
      { part: '3 × 555', role: 'Kararsız, tek kararlı ve çift kararlı çalışma kipleri' },
      { part: '74LS04', role: 'Sinyal tersleme' },
      { part: '74LS08', role: 'Kaynak seçimi ve HLT kapılama' },
      { part: '74LS32', role: 'Otomatik ve manuel kaynakların birleştirilmesi' },
    ],
    example: 'Manuel kipte butona bir kez basıldığında tek bir saat darbesi oluşur; program sayacı yalnızca bir kez artar ve LED’lerde bu değişim gözlenebilir.',
    role: 'Hata ayıklama sürecinde bilgisayarın adım adım çalıştırılmasını sağlayan temel modüldür.',
    signals: ['HLT'],
  },
  {
    id: 'registers', index: 2, title: 'A ve B Yazmaçları', en: 'Registers',
    what: 'Her biri 8 bit veri saklayan, ALU’nun iki işlenenini tutan yazmaçlar.',
    why: 'İşlemci aritmetik işlem yapabilmek için işlenenleri geçici olarak saklamak zorundadır. A yazmacı aynı zamanda sonuçların toplandığı birikeç (accumulator) işlevi görür.',
    how: [
      'Her yazmaç iki adet 4-bit 74LS173 D tipi yazmaçtan oluşur.',
      'Yükleme (load) sinyali aktifken saatin yükselen kenarında veri yolundaki değer yazmaca alınır.',
      'Yazmaç içeriği sürekli olarak ALU’ya ve LED’lere aktarılır.',
      'Veri yoluna çıkış, üç-durumlu (tri-state) 74LS245 tamponu üzerinden yalnızca çıkış sinyali aktifken yapılır.',
    ],
    inputs: ['8-bit veri yolu', 'AI / BI yükleme sinyalleri', 'AO çıkış sinyali (A yazmacı)', 'CLK'],
    outputs: ['ALU’ya doğrudan 8-bit veri', 'A yazmacı için veri yoluna 8-bit çıkış'],
    interacts: 'Veri yolu, ALU ve kontrol birimi ile etkileşir. Referans tasarımın son kontrol kelimesinde B yazmacı yalnızca okuma (BI) sinyaline sahiptir.',
    ics: [
      { part: '2 × 74LS173 (her yazmaç)', role: '4 + 4 bit veri saklama' },
      { part: '74LS245', role: 'Veri yoluna üç-durumlu çıkış' },
    ],
    example: 'ADD komutunda RAM’den okunan değer BI sinyali ile B yazmacına alınır; ALU A + B toplamını anında hesaplar.',
    role: 'Bilgisayarın tüm aritmetik işlemlerinin işlenenlerini sağlar.',
    signals: ['AI', 'AO', 'BI'],
  },
  {
    id: 'alu', index: 3, title: 'Aritmetik Mantık Birimi', en: 'ALU',
    what: 'A ve B yazmaçlarındaki değerleri toplayan veya çıkaran kombinasyonel devre.',
    why: 'Bilgisayarın hesaplama yeteneği bu birimden gelir; ayrıca koşullu atlamalar için taşma ve sıfır bayraklarını üretir.',
    how: [
      'İki adet 74LS283 4-bit tam toplayıcı zincirlenerek 8-bit toplayıcı oluşturulur.',
      'Çıkarma için B’nin bitleri 74LS86 XOR kapılarıyla terslenir ve SU sinyali elde girişine (carry-in) 1 olarak verilir: A − B = A + B̅ + 1 (ikiye tümleyen).',
      'Sonuç 74LS245 üzerinden EO sinyali ile veri yoluna aktarılır.',
      'Son tasarımda taşma (CF) ve sıfır (ZF) bayrakları FI sinyali ile bir bayrak yazmacında saklanır.',
    ],
    inputs: ['A yazmacı (8 bit)', 'B yazmacı (8 bit)', 'SU çıkarma sinyali'],
    outputs: ['Σ — 8-bit sonuç (EO ile veri yoluna)', 'Elde/taşma (carry) çıkışı', 'Sıfır bilgisi'],
    interacts: 'A ve B yazmaçlarından doğrudan beslenir; sonucu veri yoluna, bayrakları kontrol birimine iletir.',
    ics: [
      { part: '2 × 74LS283', role: '8-bit ikili toplama' },
      { part: '2 × 74LS86', role: 'Çıkarma için koşullu tersleme' },
      { part: '74LS245', role: 'Sonucun veri yoluna aktarılması' },
      { part: '74LS173', role: 'Bayrak yazmacı (CF, ZF)' },
    ],
    example: 'A = 00011100 (28), B = 00001110 (14) iken Σ = 00101010 (42). SU = 1 iken Σ = 00001110 (14) olur.',
    role: 'Toplama, çıkarma ve koşullu dallanma (JC, JZ) yeteneğinin temelidir.',
    signals: ['EO', 'SU', 'FI'],
  },
  {
    id: 'ram', index: 4, title: 'RAM Bellek Modülü', en: 'RAM & Memory Address Register',
    what: '16 adres × 8 bit kapasiteli rastgele erişimli bellek ve onu adresleyen 4-bit bellek adres yazmacı (MAR).',
    why: 'Program komutları ve veriler aynı bellekte saklanır (von Neumann yapısı); işlemci her komutu buradan okur.',
    how: [
      'İki adet 74189 (her biri 16 × 4 bit) yan yana kullanılarak 16 bayt bellek elde edilir; 74189 çıkışları ters olduğundan 74LS04 ile düzeltilir.',
      'MAR (74LS173), MI sinyaliyle veri yolunun alt 4 bitini adres olarak saklar.',
      '74LS157 veri seçicileri, programlama kipinde adresin ve verinin DIP anahtarlardan; çalışma kipinde ise MAR ve veri yolundan gelmesini sağlar.',
      'RI ile veri yolundaki değer belleğe yazılır, RO ile seçili adresteki değer 74LS245 üzerinden veri yoluna çıkarılır.',
    ],
    inputs: ['Veri yolu (adres için alt 4 bit, veri için 8 bit)', 'MI, RI, RO sinyalleri', 'Program/çalışma kip anahtarı', '4 ve 8 konumlu DIP anahtarlar', 'Yazma butonu'],
    outputs: ['Seçili adresteki 8-bit veri (RO ile veri yoluna)'],
    interacts: 'Komut alma (fetch) aşamasında program sayacı adres verir; komut yürütme aşamasında komut yazmacı adres bilgisini sağlar.',
    ics: [
      { part: '2 × 74189', role: '16 × 8 bit bellek' },
      { part: '74LS173', role: 'Bellek adres yazmacı (MAR)' },
      { part: '4 × 74LS157', role: 'Programlama / çalışma kipi seçimi' },
      { part: '74LS04', role: '74189 çıkışlarının terslenmesi' },
      { part: '74LS245', role: 'Veri yoluna çıkış' },
    ],
    example: 'Adres 0110’a 00101010 yazmak için: MAR ← 0110 (MI), ardından veri yolu = 00101010 iken RI aktif edilir.',
    role: 'Programın ve verinin saklandığı tek bellektir; 16 baytlık kapasite programların boyutunu sınırlar.',
    signals: ['MI', 'RI', 'RO'],
  },
  {
    id: 'pc', index: 5, title: 'Program Sayacı', en: 'Program Counter',
    what: 'Bir sonraki çalıştırılacak komutun bellek adresini tutan 4-bit sayıcı.',
    why: 'Komutların sırayla çalıştırılmasını ve atlama komutlarıyla akışın değiştirilmesini sağlar.',
    how: [
      '74LS161 4-bit senkron sayıcı, CE aktifken her saat kenarında bir artar.',
      'CO sinyali ile değeri 74LS245 üzerinden veri yoluna çıkarılır.',
      'J sinyali ile veri yolundaki değer sayıcıya paralel olarak yüklenir (atlama).',
      'Reset ile sayıcı 0000’a döner.',
    ],
    inputs: ['CE, CO, J sinyalleri', 'Veri yolu (atlama adresi için alt 4 bit)', 'CLK', 'Reset'],
    outputs: ['4-bit adres (CO ile veri yoluna)'],
    interacts: 'Her komut alma çevriminin ilk adımında değerini MAR’a gönderir.',
    ics: [
      { part: '74LS161', role: '4-bit senkron sayıcı' },
      { part: '74LS245', role: 'Veri yoluna çıkış' },
    ],
    example: 'PC = 0011 iken CE ile bir saat darbesi uygulanırsa PC = 0100 olur; JMP 3 komutu PC’yi yeniden 0011’e yükler.',
    role: 'Program akışını yöneten modüldür; döngüler JMP / JC / JZ komutlarıyla bu sayıcı üzerinden kurulur.',
    signals: ['CE', 'CO', 'J'],
  },
  {
    id: 'ir', index: 6, title: 'Komut Yazmacı', en: 'Instruction Register',
    what: 'Bellekten okunan geçerli komutu saklayan 8-bit yazmaç.',
    why: 'Komutun işlem kodu (opcode) kontrol biriminin hangi sinyalleri üreteceğini belirler; işlenen (operand) kısmı ise adres ya da sabit değer olarak kullanılır.',
    how: [
      'II sinyaliyle veri yolundaki 8-bit komut iki adet 74LS173’e yüklenir.',
      'Üst 4 bit (opcode) doğrudan kontrol birimine gider.',
      'Alt 4 bit (operand), IO sinyaliyle 74LS245 üzerinden veri yoluna çıkarılabilir.',
    ],
    inputs: ['Veri yolu (8 bit)', 'II, IO sinyalleri', 'CLK'],
    outputs: ['Opcode (4 bit) → kontrol birimi', 'Operand (4 bit) → veri yolu'],
    interacts: 'RAM’den beslenir; kontrol birimini ve dolaylı olarak MAR, A yazmacı ve PC’yi yönlendirir.',
    ics: [
      { part: '2 × 74LS173', role: '8-bit komut saklama' },
      { part: '74LS245', role: 'Operandın veri yoluna aktarılması' },
    ],
    example: 'Komut 0001 1110 (LDA 14): opcode 0001 = LDA, operand 1110 = 14 numaralı adres.',
    role: 'Bellekteki bir baytı, donanımın anlayacağı bir işleme dönüştüren köprüdür.',
    signals: ['II', 'IO'],
  },
  {
    id: 'control', index: 7, title: 'Kontrol Birimi', en: 'Control Unit',
    what: 'Opcode, mikro adım ve bayraklara göre 16 kontrol sinyalini üreten birim.',
    why: 'Hangi modülün veri yoluna yazacağını ve hangisinin okuyacağını her saat adımında belirler; işlemcinin “beyni”dir.',
    how: [
      '74LS161 sayıcı, terslenmiş saatle (CLK̅) çalışarak T0–T4 mikro adımlarını sayar; 74LS138 bu adımları kod çözerek LED’lerde gösterir ve son adımda sayacı sıfırlar.',
      'İki adet 28C16 EEPROM bir arama tablosu (mikrokod) olarak kullanılır: adres = opcode + adım + bayraklar; veri = kontrol kelimesi.',
      'Her EEPROM 8 kontrol sinyali üretir; toplam 16 sinyal elde edilir.',
      'Sinyaller saatin düşen kenarında değişip yükselen kenarda kullanıldığından veri kararlı hâldeyken yazmaçlara alınır.',
    ],
    inputs: ['Opcode (komut yazmacından 4 bit)', 'Mikro adım sayacı (3 bit)', 'CF ve ZF bayrakları', 'CLK̅'],
    outputs: ['16-bit kontrol kelimesi: HLT MI RI RO IO II AI AO EO SU BI OI CE CO J FI'],
    interacts: 'Saat hariç tüm modüllerin yükleme ve çıkış sinyallerini sürer.',
    ics: [
      { part: '2 × 28C16 EEPROM', role: 'Mikrokod arama tablosu' },
      { part: '74LS161', role: 'Mikro adım sayacı' },
      { part: '74LS138', role: 'Adım kod çözücü' },
      { part: '74LS04', role: 'Ters mantıklı sinyallerin düzeltilmesi' },
    ],
    example: 'T0 adımında kontrol kelimesi yalnızca CO ve MI bitleri 1 olacak şekilde üretilir; PC değeri MAR’a kopyalanır.',
    role: 'Komut setini donanımda tanımlayan birimdir; yeni komutlar yalnızca EEPROM yeniden programlanarak eklenebilir.',
    signals: ['HLT', 'MI', 'RI', 'RO', 'IO', 'II', 'AI', 'AO', 'EO', 'SU', 'BI', 'OI', 'CE', 'CO', 'J', 'FI'],
  },
  {
    id: 'output', index: 8, title: 'Çıkış Yazmacı', en: 'Output Register',
    what: 'Veri yolundaki 8-bit değeri saklayıp dört adet 7 segment göstergede ondalık olarak gösteren modül.',
    why: 'Sonuçların ikili LED’ler yerine okunabilir ondalık biçimde gösterilmesini sağlar.',
    how: [
      'OI sinyaliyle değer 74LS273 sekizli D flip-flop’a alınır.',
      'Bir 28C16 EEPROM, 8-bit değeri ve basamak numarasını adres olarak alıp ilgili basamağın segment desenini verir.',
      'Ayrı bir 555 saat ile sürülen 2-bit sayıcı (74LS107 JK flip-flop) ve 74LS139 kod çözücü, dört göstergeyi sırayla çok hızlı yakar (çoğullama).',
      'İşaretli (ikiye tümleyen) ve işaretsiz gösterim kipleri EEPROM içeriğiyle desteklenebilir.',
    ],
    inputs: ['Veri yolu (8 bit)', 'OI sinyali', 'CLK'],
    outputs: ['4 × 7 segment gösterge'],
    interacts: 'Yalnızca veri yolundan okur; OUT komutuyla A yazmacının içeriğini alır.',
    ics: [
      { part: '74LS273', role: 'Çıkış değerinin saklanması' },
      { part: '28C16 EEPROM', role: 'İkili → 7 segment dönüşüm tablosu' },
      { part: '555', role: 'Çoğullama saati' },
      { part: '74LS107', role: '2-bit basamak sayacı' },
      { part: '74LS139', role: 'Basamak seçimi' },
    ],
    example: 'Veri yolu = 00101010 iken OI aktif edilirse göstergede “ 42” görüntülenir.',
    role: 'Programların sonuçlarının kullanıcıya sunulduğu tek çıktı birimidir.',
    signals: ['OI'],
  },
  {
    id: 'bus', index: 9, title: 'Ortak Veri Yolu', en: '8-Bit Bus',
    what: 'Tüm modülleri birbirine bağlayan 8 hatlı ortak iletişim yolu.',
    why: 'Her modülün diğer tüm modüllerle ayrı ayrı bağlanması yerine tek bir ortak yol kullanmak kablo sayısını ve karmaşıklığı azaltır.',
    how: [
      'Herhangi bir anda yalnızca bir modül veri yoluna yazabilir; bu, 74LS245 üç-durumlu tamponların yalnızca birinin etkin olmasıyla sağlanır.',
      'Birden fazla modül aynı anda veri yolundan okuyabilir.',
      'Veri yolu hatları LED’lerle izlenir; hiçbir modül yazmadığında hatların değeri tanımsız kabul edilmeli ve bu adımlarda veri yolundan okuma yapılmamalıdır.',
    ],
    inputs: ['Çıkışı etkin olan tek modülün verisi'],
    outputs: ['Yükleme sinyali etkin olan tüm modüllere aynı veri'],
    interacts: 'PC, MAR, RAM, IR, A, B, ALU ve çıkış yazmacı veri yoluna bağlıdır.',
    ics: [{ part: '6 × 74LS245', role: 'Modül çıkışlarının yola bağlanması' }],
    example: 'T1 adımında RAM, RO ile veri yoluna komutu yazar; aynı adımda komut yazmacı II ile bu değeri okur.',
    role: 'Bilgisayarın omurgasıdır; mimarinin anlaşılır ve modüler olmasını sağlar.',
    signals: ['CO', 'RO', 'IO', 'AO', 'EO'],
  },
];

/** Blok diyagramındaki kutular ve veri yolu bağlantı yönleri. */
export type BusDir = 'in' | 'out' | 'both' | 'none';
export interface Block {
  key: string; label: string; sub: string; module: ModuleId;
  x: number; y: number; w: number; h: number; side: 'L' | 'R' | 'C'; bus: BusDir; signals: Signal[];
}
export const blocks: Block[] = [
  { key: 'clock', label: 'Saat', sub: '555 × 3', module: 'clock', x: 40, y: 30, w: 230, h: 56, side: 'L', bus: 'none', signals: ['HLT'] },
  { key: 'pc', label: 'Program Sayacı', sub: '74LS161', module: 'pc', x: 40, y: 104, w: 230, h: 56, side: 'L', bus: 'both', signals: ['CE', 'CO', 'J'] },
  { key: 'mar', label: 'Bellek Adres Yazmacı', sub: 'MAR · 74LS173', module: 'ram', x: 40, y: 178, w: 230, h: 56, side: 'L', bus: 'in', signals: ['MI'] },
  { key: 'ram', label: 'RAM (16 bayt)', sub: '2 × 74189', module: 'ram', x: 40, y: 252, w: 230, h: 56, side: 'L', bus: 'both', signals: ['RI', 'RO'] },
  { key: 'ir', label: 'Komut Yazmacı', sub: '2 × 74LS173', module: 'ir', x: 40, y: 326, w: 230, h: 56, side: 'L', bus: 'both', signals: ['II', 'IO'] },
  { key: 'a', label: 'A Yazmacı', sub: '2 × 74LS173', module: 'registers', x: 450, y: 104, w: 230, h: 56, side: 'R', bus: 'both', signals: ['AI', 'AO'] },
  { key: 'alu', label: 'ALU (Σ)', sub: '2 × 74LS283', module: 'alu', x: 450, y: 178, w: 230, h: 56, side: 'R', bus: 'out', signals: ['EO', 'SU'] },
  { key: 'b', label: 'B Yazmacı', sub: '2 × 74LS173', module: 'registers', x: 450, y: 252, w: 230, h: 56, side: 'R', bus: 'in', signals: ['BI'] },
  { key: 'out', label: 'Çıkış Yazmacı', sub: '74LS273 · 7 segment', module: 'output', x: 450, y: 326, w: 230, h: 56, side: 'R', bus: 'in', signals: ['OI'] },
  { key: 'flags', label: 'Bayraklar', sub: 'CF · ZF', module: 'alu', x: 572, y: 30, w: 108, h: 56, side: 'R', bus: 'none', signals: ['FI'] },
  { key: 'control', label: 'Kontrol Birimi', sub: '2 × 28C16 · mikrokod', module: 'control', x: 40, y: 410, w: 640, h: 56, side: 'C', bus: 'none', signals: [] },
];
