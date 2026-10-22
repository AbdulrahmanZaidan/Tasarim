import type { ReactNode } from 'react';
import { CheckSquare } from 'lucide-react';
import { useCore } from '../data/public';
import { ExperimentGallery, TopicExperiments } from '../components/ExperimentArchive';
import { PageHeader, Section, Figure, Callout, Disclosure, StageNav, StatusBadge } from '../components/ui';
import { AdderDemo, RegisterDemo, CounterDemo, RamDemo, ClockDemo, DecodeDemo } from '../components/sims';
import { ClockWave, BusConcept } from '../components/diagrams';
import CpuRunner from '../components/CpuRunner';
import SystemDiagram from '../components/SystemDiagram';

/** Test senaryosu → ilgili bilgisayar bileşenleri (deney kayıtlarını eşleştirmek için) */
const topicComponents: Record<string, string[]> = {
  saat: ['clock'], yazmac: ['registers'], toplama: ['alu'], cikarma: ['alu'], ram: ['ram'], pc: ['pc'],
  decode: ['ir', 'control', 'isa'], kontrol: ['control', 'eeprom'], bus: ['bus'], program: ['integration', 'isa'],
};

interface SimTopic {
  id: string; title: string; text: string; inputs: string[]; expected: string[]; objectives: string[]; example: string;
  demo?: ReactNode; figure?: { node: ReactNode; caption: string };
}

const topics: SimTopic[] = [
  {
    id: 'saat', title: 'Saat üretimi ve testi',
    text: 'Simülatörde 555 zamanlayıcının analog davranışı yerine genellikle ayarlanabilir frekanslı bir saat kaynağı ve tek darbe üreten bir buton kullanılır. Digital programında “Clock” bileşeni ve buton; Proteus’ta ise 555 modeli doğrudan kullanılabilir.',
    inputs: ['Kip seçimi (otomatik / manuel)', 'Frekans', 'Manuel adım butonu', 'HLT sinyali'],
    expected: ['Otomatik kipte düzenli kare dalga', 'Manuel kipte her basışta tek darbe', 'HLT = 1 iken saat çıkışının sabit kalması'],
    objectives: ['Kip değiştirme sırasında istenmeyen darbe oluşmaması', 'HLT kapılamasının doğrulanması'],
    example: 'Manuel kipte üç kez butona basılarak program sayacının üç kez arttığının izlenmesi.',
    demo: <ClockDemo />, figure: { node: <ClockWave />, caption: 'Beklenen saat ve terslenmiş saat dalga biçimleri.' },
  },
  {
    id: 'yazmac', title: 'Yazmaç yükleme ve çıkış davranışı',
    text: '74LS173 yazmacı, yükleme girişi aktifken saatin yükselen kenarında veriyi alır. 74LS245 tamponu ise yalnızca çıkış sinyali aktifken yazmaç değerini veri yoluna aktarır; aksi hâlde yüksek empedansta (Z) kalır.',
    inputs: ['Veri yolu değeri (8 bit)', 'Yükleme (AI / BI)', 'Çıkış (AO)', 'CLK'],
    expected: ['AI = 1 ve ↑CLK → yazmaç = veri yolu', 'AI = 0 → yazmaç değişmez', 'AO = 0 → veri yolu sürülmez'],
    objectives: ['Saat kenarı dışında yazmacın değişmediğinin gösterilmesi', 'Çıkış tamponunun üç-durumlu davranışının doğrulanması'],
    example: 'Veri yoluna 00101010 verilip AI etkinken tek saat darbesi uygulanması ve A yazmacı LED’lerinde 42 değerinin okunması.',
    demo: <RegisterDemo />,
  },
  {
    id: 'toplama', title: 'İkili toplama',
    text: 'İki adet 74LS283 4-bit tam toplayıcı, alt nibble’ın elde çıkışı üst nibble’ın elde girişine bağlanarak 8-bit toplayıcı oluşturur. Sonucun 255’i aşması durumunda 9. bit elde (carry) olarak dışarı çıkar.',
    inputs: ['A (8 bit)', 'B (8 bit)', 'SU = 0'],
    expected: ['Σ = (A + B) mod 256', 'CF = 1 ise A + B > 255'],
    objectives: ['Sınır değerlerinin (0, 127, 128, 255) sınanması', 'Nibble’lar arası elde aktarımının doğrulanması'],
    example: '28 + 14 = 42 (CF = 0); 200 + 100 = 44 (CF = 1).',
    demo: <AdderDemo />,
  },
  {
    id: 'cikarma', title: 'İkiye tümleyen ile çıkarma',
    text: 'Çıkarma için ayrı bir devre kullanılmaz: B’nin her biti SU sinyaliyle 74LS86 XOR kapılarından geçirilerek terslenir ve SU aynı zamanda toplayıcının elde girişine 1 olarak verilir. Böylece A − B = A + B̅ + 1 elde edilir.',
    inputs: ['A (8 bit)', 'B (8 bit)', 'SU = 1'],
    expected: ['Σ = (A − B) mod 256', 'A ≥ B iken CF = 1', 'Negatif sonuçlar ikiye tümleyen gösterimiyle'],
    objectives: ['A = B için Σ = 0 ve ZF = 1 olması', 'A < B için sonucun ikiye tümleyen gösteriminin doğrulanması'],
    example: '30 − 12 = 18; 5 − 9 = 252 (işaretli yorumda −4). Yukarıdaki toplayıcıda “Çıkarma” seçeneğiyle denenebilir.',
  },
  {
    id: 'ram', title: 'RAM okuma / yazma',
    text: 'Yazma iki adımda yapılır: önce adres MI ile MAR’a alınır, ardından veri yolundaki değer RI ile belleğe yazılır. Okumada adres yine MAR’dan gelir; RO etkinleştiğinde seçili adresin içeriği veri yoluna çıkar.',
    inputs: ['Adres (4 bit)', 'Veri (8 bit)', 'MI, RI, RO', 'CLK'],
    expected: ['Yazılan değerin aynı adresten değişmeden okunması', 'Diğer adreslerin etkilenmemesi'],
    objectives: ['74189’un ters çıkışlarının 74LS04 ile düzeltildiğinin gösterilmesi', 'Programlama kipinde DIP anahtarlarla yazmanın sınanması'],
    example: 'Adres 0110’a 01010101 yazılıp ardından aynı adresten okunması.',
    demo: <RamDemo />,
  },
  {
    id: 'pc', title: 'Program sayacının artırılması',
    text: '74LS161, CE (count enable) aktifken her saat kenarında bir artar; 15’ten sonra 0’a döner. J sinyali, veri yolundaki adresin sayıcıya paralel yüklenmesini sağlar.',
    inputs: ['CE', 'J ve atlama adresi', 'CLK', 'Reset'],
    expected: ['0 → 1 → … → 15 → 0 sayımı', 'J ile istenen adrese atlama', 'Reset ile 0'],
    objectives: ['Sayım ve yükleme işlemlerinin aynı anda etkin olmadığı durumların sınanması'],
    example: 'PC = 5 iken J etkinleştirilerek veri yolundaki 3 değerinin yüklenmesi.',
    demo: <CounterDemo />,
  },
  {
    id: 'decode', title: 'Komut çözme',
    text: 'Komut yazmacının üst 4 biti (opcode) ve mikro adım sayacının değeri, kontrol EEPROM’larının adres girişlerini oluşturur. EEPROM, bu adreste saklanan kontrol kelimesini çıkışa verir.',
    inputs: ['Opcode (4 bit)', 'Mikro adım (T0–T4)', 'CF, ZF'],
    expected: ['Her opcode / adım için doğru kontrol kelimesi'],
    objectives: ['Mikrokod tablosunun tüm komutlar için satır satır doğrulanması'],
    example: 'ADD 15 komutunun T2–T4 adımlarında sırasıyla IO MI · RO BI · EO AI FI üretmesi.',
    demo: <DecodeDemo />,
  },
  {
    id: 'kontrol', title: 'Kontrol sinyalleri',
    text: 'Kontrol sinyalleri saatin düşen kenarında değişir ve yükselen kenarda kullanılır. Böylece sinyaller ve veri yolu, yazmaçların yükleme anından önce kararlı hâle gelir. Simülasyonda bu zamanlama ilişkisi zamanlama (timing) penceresinde incelenmelidir.',
    inputs: ['CLK̅ ile sürülen adım sayacı', 'EEPROM çıkışları'],
    expected: ['Aynı adımda veri yoluna yalnızca bir çıkış sinyalinin (CO, RO, IO, AO, EO) etkin olması'],
    objectives: ['Veri yolu çakışmalarının (bus contention) olmadığının mikrokod üzerinden kontrol edilmesi'],
    example: 'Tüm mikrokod satırlarında çıkış sinyallerinin aynı anda birden fazla etkin olmadığının taranması.',
  },
  {
    id: 'bus', title: 'Ortak veri yolu davranışı',
    text: 'Simülatörde veri yolu tek bir 8-bit hat olarak modellenir. Birden fazla sürücünün aynı anda etkin olması, Digital programında çakışma hatası olarak raporlanır; bu özellik mikrokod hatalarının erken tespitinde kullanılabilir.',
    inputs: ['Modüllerin çıkış etkinleştirme sinyalleri'],
    expected: ['Her adımda en fazla bir sürücü', 'Sürücü yokken okuma yapılmaması'],
    objectives: ['Her mikro adımdaki veri yolu değerinin beklenen tabloyla karşılaştırılması'],
    example: 'T1 adımında RAM sürücü, komut yazmacı alıcı olarak gözlenir.',
    figure: { node: <BusConcept />, caption: 'Veri yolunda tek sürücü – çok alıcı yapısı.' },
  },
];

function Meta({ t }: { t: SimTopic }) {
  const box = (title: string, items: string[]) => (
    <div className="card-soft p-3.5">
      <div className="text-[11px] font-semibold tracking-[0.12em] text-brand">{title}</div>
      <ul className="mt-1.5 space-y-1 text-[13.5px] leading-5 text-ink-2">{items.map((x) => <li key={x}>• {x}</li>)}</ul>
    </div>
  );
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {box('GİRİŞ DEĞERLERİ', t.inputs)}
      {box('BEKLENEN ÇIKIŞ', t.expected)}
      {box('TEST HEDEFLERİ', t.objectives)}
    </div>
  );
}

function FutureSlot({ id }: { id: string }) {
  return <TopicExperiments components={topicComponents[id] ?? []} label="Bu alt bölüme ait gerçek simülasyon kaydı henüz eklenmemiştir." />;
}

export default function SimulationPage() {
  const stage = useCore().data.phases.find((p) => p.slug === 'simulation');
  return (
    <>
      <PageHeader eyebrow={`Aşama ${stage?.number ?? '02'} · Tasarım I`} title="Simülasyon"
        subtitle="8-bit mimarinin dijital mantık simülatörlerinde modül modül doğrulanması için plan, test senaryoları ve etkileşimli eğitsel örnekler."
        crumbs={[{ label: 'Proje Planı', to: '/proje' }, { label: 'Simülasyon' }]} right={stage && <StatusBadge status={stage.status} size="md" />} />

      <div className="container-x pt-6">
        <Callout tone="warn" title="Önemli not">
          Bu sayfadaki etkileşimli örnekler <b>tarayıcıda çalışan eğitsel simülasyonlardır</b>; Digital veya Proteus simülasyonlarının ya da donanım testlerinin sonucu değildir.
          Ekibin gerçek simülasyon çalışmaları (ekran görüntüleri, giriş–çıkış değerleri, kaynak dosyalar) ayrı olarak <a href="#deneyler">deney kayıtları</a> bölümünde yayımlanır.
        </Callout>
      </div>

      <Section eyebrow="Araçlar" title="Simülasyon ortamları" intro="Dönem planında iki araç öngörülmüştür. Modül bazlı mantıksal doğrulama için Digital, analog davranışın da önemli olduğu bölümler (ör. 555 saat devresi) için Proteus tercih edilebilir.">
        <div className="grid gap-4 md:grid-cols-2">
          {[
            { name: 'Digital', by: 'Helmut Neemann', pts: ['Ücretsiz ve açık kaynaklı (Java tabanlı)', '74xx entegre kütüphanesi ve EEPROM bileşeni', 'EEPROM içeriğinin dosyadan yüklenebilmesi (mikrokod)', 'Veri yolu çakışmalarının otomatik algılanması', 'Testbench ile tablo tabanlı otomatik test'] },
            { name: 'Proteus', by: 'Labcenter Electronics', pts: ['Ticari yazılım (lisans gerektirir)', 'Gerçek 555 ve 74LS modelleriyle karma (analog/dijital) simülasyon', 'Sanal osiloskop ve mantık analizörü', 'Şema çizimi ile PCB tasarımının aynı ortamda yapılabilmesi'] },
          ].map((t) => (
            <div key={t.name} className="card p-5">
              <div className="flex items-baseline justify-between gap-2"><h3 className="text-[19px] font-bold">{t.name}</h3><span className="text-[13px] text-ink-3">{t.by}</span></div>
              <ul className="mt-3 space-y-1.5 text-[14px] text-ink-2">{t.pts.map((p) => <li key={p} className="flex gap-2"><CheckSquare size={16} className="mt-0.5 shrink-0 text-brand" aria-hidden />{p}</li>)}</ul>
            </div>
          ))}
        </div>
        <div className="mt-6">
          <Figure n="3" kind="kavramsal" caption="Simülasyonda kurulacak sistem; modüller önce ayrı ayrı, ardından bu yapıda birleştirilerek test edilecektir.">
            <SystemDiagram />
          </Figure>
        </div>
      </Section>

      <Section eyebrow="Test senaryoları" title="Modül bazlı simülasyon planı" intro="Her alt bölüm; teknik açıklamayı, giriş değerlerini, beklenen çıkışları, test hedeflerini ve ilgili etkileşimli örneği içerir.">
        <div className="space-y-3">
          {topics.map((t, i) => (
            <Disclosure key={t.id} id={`sim-${t.id}`} defaultOpen={i === 2}
              title={<><span className="mono text-[14px] text-brand">{String(i + 1).padStart(2, '0')}</span> {t.title}</>}
              badge={t.demo ? <span className="chip border-brand-line bg-brand-soft text-brand">Etkileşimli</span> : undefined}>
              <div className="space-y-5">
                <p className="prose-body">{t.text}</p>
                <Meta t={t} />
                {t.demo && <Figure n={`3.${i + 1}`} kind="simulasyon" caption={`${t.title} — etkileşimli eğitsel örnek.`}>{t.demo}</Figure>}
                {t.figure && <Figure n={`3.${i + 1}${t.demo ? 'b' : ''}`} kind="kavramsal" caption={t.figure.caption}>{t.figure.node}</Figure>}
                <p className="text-[14px] text-ink-2"><b className="text-brand">Örnek kullanım:</b> {t.example}</p>
                <FutureSlot id={t.id} />
              </div>
            </Disclosure>
          ))}
          <Disclosure id="sim-program" title={<><span className="mono text-[14px] text-brand">10</span> Basit bir örnek programın yürütülmesi</>} badge={<span className="chip border-brand-line bg-brand-soft text-brand">Etkileşimli</span>}>
            <div className="space-y-5">
              <p className="prose-body">Tüm modüller birleştirildikten sonra RAM’e programlama kipinde bir program yazılır ve bilgisayar çalıştırılır. Aşağıdaki model, Ben Eater komut seti ile çalışan örnek programları mikro adım düzeyinde yürütür. Simülatördeki sonuçlar bu tabloyla karşılaştırılabilir.</p>
              <Meta t={{ id: 'p', title: '', text: '', example: '', inputs: ['RAM’e yüklenmiş program ve veri', 'Saat'], expected: ['28 + 14 programında çıkış = 42', 'HLT ile saatin durması'], objectives: ['Her komutun beklenen çevrim sayısında tamamlanması', 'Döngü programında JMP’nin doğru çalışması'] }} />
              <Figure n="3.10" kind="simulasyon" caption="Örnek programların mikro adım düzeyinde eğitsel yürütülmesi."><CpuRunner /></Figure>
              <FutureSlot id="program" />
            </div>
          </Disclosure>
        </div>
      </Section>

      <Section eyebrow="Deney kayıtları" title="Simülasyon deneyleri ve ekran görüntüleri" intro="Ekibin Digital, Logisim Evolution veya Proteus ile yaptığı deneyler; amaç, giriş değerleri, beklenen ve gözlenen çıktılar, ekran görüntüleri ve indirilebilir dosyalarıyla. Sonuç durumu yalnızca kaydedilmiş gözlemlere dayanır.">
        <ExperimentGallery />
      </Section>

      <StageNav current="simulation" />
    </>
  );
}
