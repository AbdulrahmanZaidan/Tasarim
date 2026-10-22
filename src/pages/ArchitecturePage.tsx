import { useState } from 'react';
import { MousePointerClick, X } from 'lucide-react';
import { modules, type ModuleId, type ArchModule } from '../data/architecture';
import { Link } from 'react-router-dom';
import { useCore } from '../data/public';
import { workStatusLabels, workTone } from '../lib/labels';
import { INSTRUCTIONS, SIGNALS, signalInfo, microcode, bin } from '../lib/cpu';
import { PageHeader, Section, Figure, Callout, Disclosure, StageNav, StatusBadge, Badge } from '../components/ui';
import SystemDiagram from '../components/SystemDiagram';
import CpuRunner from '../components/CpuRunner';
import { ModuleDiagram, ClockWave, BusConcept, CycleDiagram } from '../components/diagrams';

/** Bileşenin güncel durumu ve ilgili sayfalara bağlantılar (mimari → simülasyon → kanıt → ilerleme) */
function ComponentLinks({ slugs }: { slugs: string[] }) {
  const { data } = useCore();
  const comps = data.components.filter((c) => slugs.includes(c.slug));
  if (!comps.length) return null;
  return (
    <div className="flex flex-col gap-2 rounded-[10px] border border-brand-line bg-white p-3 text-[13.5px]">
      {comps.map((c) => (
        <div key={c.slug} className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
          <b className="text-ink">{c.name}</b>
          <Badge tone={workTone[c.status]}>{workStatusLabels[c.status]}</Badge>
          {c.progress !== null && <span className="mono text-ink-3">%{c.progress.toLocaleString('tr-TR')} görev</span>}
          <span className="ml-auto flex flex-wrap gap-x-4 gap-y-1">
            <Link to={`/proje/bilesen/${c.slug}`}>Bileşen sayfası</Link>
            <Link to={`/proje/simulasyon?bilesen=${c.slug}#deneyler`}>Simülasyonlar</Link>
            <Link to={`/proje/bilesen/${c.slug}#gorseller`}>Görseller ve belgeler</Link>
          </span>
        </div>
      ))}
    </div>
  );
}

function AluExample() {
  const a = 28, b = 14;
  const rows = [['A', a], ['B', b], ['Σ = A + B', a + b], ['B̅ + 1 (−B)', (~b + 1) & 0xff], ['Σ = A − B', (a - b) & 0xff]] as const;
  return (
    <div className="overflow-x-auto">
      <table className="mono w-full min-w-[420px] text-[14px]">
        <tbody>
          {rows.map(([l, v], i) => (
            <tr key={l} className={i === 2 || i === 4 ? 'border-t-2 border-brand font-semibold text-brand' : ''}>
              <td className="py-1 pr-4 font-sans text-[13px] text-ink-2">{l}</td>
              <td className="py-1 pr-4 tracking-[0.25em]">{bin(v)}</td>
              <td className="py-1 text-right text-ink-3">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RamVisual() {
  const cells = [0b00011110, 0b00101111, 0b11100000, 0b11110000];
  return (
    <svg viewBox="0 0 640 210" className="h-auto w-full" role="img" aria-label="MAR, adres çözümü ve 16 x 8 bellek dizisi">
      <rect x="20" y="78" width="110" height="50" rx="6" fill="#FBEFF1" stroke="#9E1B32" />
      <text x="75" y="100" textAnchor="middle" fontSize="13" fontWeight="600">MAR</text>
      <text x="75" y="117" textAnchor="middle" fontSize="11" fontFamily="IBM Plex Mono" fill="#4A4850">0001</text>
      <line x1="130" y1="103" x2="196" y2="103" stroke="#9E1B32" strokeWidth="2" />
      <text x="140" y="96" fontSize="10" fill="#4A4850">A3–A0</text>
      {Array.from({ length: 6 }, (_, i) => {
        const y = 20 + i * 28, sel = i === 1;
        return (
          <g key={i}>
            <rect x="200" y={y} width="300" height="24" rx="3" fill={sel ? '#9E1B32' : '#fff'} stroke="#E2B4BD" />
            <text x="212" y={y + 16} fontSize="11" fontFamily="IBM Plex Mono" fill={sel ? '#fff' : '#4A4850'}>{i < 4 ? i.toString(2).padStart(4, '0') : i === 4 ? '····' : '1111'}</text>
            <text x="300" y={y + 16} fontSize="11.5" fontFamily="IBM Plex Mono" letterSpacing="2" fill={sel ? '#fff' : '#1C1B1F'}>{i < 4 ? bin(cells[i]) : i === 4 ? '' : bin(14)}</text>
          </g>
        );
      })}
      <line x1="500" y1="62" x2="560" y2="62" stroke="#9E1B32" strokeWidth="2" />
      <rect x="560" y="44" width="70" height="36" rx="6" fill="#9E1B32" />
      <text x="595" y="67" textAnchor="middle" fontSize="12" fontWeight="600" fill="#fff">RO →</text>
      <text x="350" y="200" textAnchor="middle" fontSize="11" fill="#4A4850">16 adres × 8 bit (2 × 74189) — seçili adres 0001: ADD 15</text>
    </svg>
  );
}

const extras: Partial<Record<ModuleId, { node: JSX.Element; caption: string }>> = {
  clock: { node: <ClockWave />, caption: 'Saat (CLK) ve terslenmiş saat (CLK̅) sinyalleri; yazmaçlar yükselen kenarda yükler, mikro adım sayacı CLK̅ ile ilerler.' },
  alu: { node: <AluExample />, caption: 'ALU ile 8-bit toplama ve ikiye tümleyen yöntemiyle çıkarma örneği (A = 28, B = 14).' },
  ram: { node: <RamVisual />, caption: 'MAR’daki 4-bit adres ile 16 baytlık bellekte tek bir satırın seçilmesi ve RO ile veri yoluna çıkarılması.' },
  bus: { node: <BusConcept />, caption: 'Ortak veri yolunda aynı anda yalnızca bir modül yazar (üç-durumlu tampon etkin), bir veya daha fazla modül okur.' },
};

function ModuleBody({ m }: { m: ArchModule }) {
  const ex = extras[m.id];
  return (
    <div className="space-y-6">
      <ComponentLinks slugs={[m.id]} />
      <div className="grid gap-5 md:grid-cols-2">
        <div><div className="eyebrow">Nedir?</div><p className="prose-body mt-1">{m.what}</p></div>
        <div><div className="eyebrow">Neden gereklidir?</div><p className="prose-body mt-1">{m.why}</p></div>
      </div>
      <div>
        <div className="eyebrow">Nasıl çalışır?</div>
        <ol className="mt-2 space-y-2">{m.how.map((h, i) => (
          <li key={i} className="flex gap-3 text-[15px] leading-6 text-ink-2"><span className="mono mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-soft text-[12px] font-semibold text-brand">{i + 1}</span>{h}</li>
        ))}</ol>
      </div>
      <Figure n={`2.${m.index}a`} kind="kavramsal" caption={`${m.title} — girişler, kullanılan entegreler ve çıkışlar.`}>
        <ModuleDiagram m={m} />
      </Figure>
      {ex && <Figure n={`2.${m.index}b`} kind="kavramsal" caption={ex.caption}>{ex.node}</Figure>}
      <div className="grid gap-5 md:grid-cols-2">
        <div><div className="eyebrow">Diğer modüllerle etkileşim</div><p className="prose-body mt-1">{m.interacts}</p></div>
        <div><div className="eyebrow">Örnek</div><p className="prose-body mt-1">{m.example}</p></div>
      </div>
      <div className="card-soft p-4">
        <div className="eyebrow">Nihai bilgisayardaki rolü</div>
        <p className="prose-body mt-1">{m.role}</p>
        {m.signals.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {m.signals.map((s) => <span key={s} title={signalInfo[s]} className="chip mono border-brand-line bg-white text-brand">{s}</span>)}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ArchitecturePage() {
  const stage = useCore().data.phases.find((p) => p.slug === 'architecture');
  const [sel, setSel] = useState<ModuleId | null>('control');
  const [open, setOpen] = useState<Set<string>>(new Set());
  const m = modules.find((x) => x.id === sel);
  const toggle = (id: string, v: boolean) => setOpen((o) => { const n = new Set(o); v ? n.add(id) : n.delete(id); return n; });
  const goTo = (id: string) => { toggle(id, true); setTimeout(() => document.getElementById(`modul-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60); };

  return (
    <>
      <PageHeader eyebrow={`Aşama ${stage?.number ?? '01'} · Tasarım I`} title="Mimari ve Şema"
        subtitle="Ben Eater referans mimarisine dayanan 8-bit bilgisayarın modülleri, veri yolu, kontrol sinyalleri ve komut seti."
        crumbs={[{ label: 'Proje Planı', to: '/proje' }, { label: 'Mimari ve Şema' }]}
        right={stage && <StatusBadge status={stage.status} size="md" />} />

      <div className="container-x pt-6">
        <Callout title="Kavramsal diyagramlar ve doğrulanmış şemalar">
          Bu sayfadaki tüm diyagramlar <b>kavramsal blok diyagramlarıdır</b>; bacak (pin) bağlantısı içermez ve test edilmiş elektrik şeması değildir.
          Proje ekibinin kendi şemaları hazırlandığında GitHub deposunda yayımlanacaktır.
        </Callout>
      </div>

      <Section eyebrow="Genel bakış" title="8-Bit Bilgisayarın Genel Mimarisi"
        intro={<>Bilgisayar, 8-bit ortak veri yoluna bağlı modüllerden oluşur. Her saat adımında kontrol birimi, veri yoluna <b>hangi modülün yazacağını</b> ve <b>hangi modüllerin okuyacağını</b> belirleyen 16 kontrol sinyali üretir. Bir modüle tıklayarak bağlantılarını ve açıklamasını görüntüleyebilirsiniz.</>}>
        <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
          <Figure n="2" kind="kavramsal" caption="Sistem blok diyagramı: modüller, 8-bit veri yolu, doğrudan bağlantılar ve kontrol birimi. Oklar veri yoluna yazma / okuma yönünü gösterir.">
            <SystemDiagram selected={sel} onSelect={setSel} />
            <p className="mt-2 flex items-center gap-1.5 text-[12px] text-ink-3"><MousePointerClick size={14} aria-hidden /> Modüller klavye ile de seçilebilir (Tab + Enter).</p>
          </Figure>
          <aside className="card self-start p-5 lg:sticky lg:top-24" aria-live="polite">
            {m ? (
              <div key={m.id} className="animate-rise">
                <div className="flex items-start justify-between gap-2">
                  <div><div className="eyebrow">Modül {m.index}</div><h3 className="mt-1 text-[20px] font-bold">{m.title}</h3><div className="text-[13px] text-ink-3">{m.en}</div></div>
                  <button className="btn-ghost -mr-2 -mt-1 p-1.5" onClick={() => setSel(null)} aria-label="Paneli kapat"><X size={18} /></button>
                </div>
                <p className="prose-body mt-3">{m.what}</p>
                <div className="mt-4 text-[12px] font-semibold tracking-[0.1em] text-ink-3">ENTEGRELER</div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">{m.ics.map((ic) => <span key={ic.part} className="chip mono border-ink/15 bg-ink text-white">{ic.part}</span>)}</div>
                {m.signals.length > 0 && <>
                  <div className="mt-4 text-[12px] font-semibold tracking-[0.1em] text-ink-3">KONTROL SİNYALLERİ</div>
                  <ul className="mt-1.5 space-y-1 text-[13px]">{m.signals.slice(0, 6).map((s) => <li key={s}><b className="mono text-brand">{s}</b> — {signalInfo[s]}</li>)}{m.signals.length > 6 && <li className="text-ink-3">… ve {m.signals.length - 6} sinyal daha</li>}</ul>
                </>}
                <button className="btn-primary mt-5 w-full" onClick={() => goTo(m.id)}>Ayrıntılı açıklamaya git</button>
              </div>
            ) : (
              <div className="py-6 text-center text-[14px] text-ink-3"><MousePointerClick className="mx-auto mb-2 text-brand" aria-hidden />Ayrıntıları görmek için diyagramda bir modül seçin.</div>
            )}
          </aside>
        </div>
      </Section>

      <Section eyebrow="Modüller" title="Donanım modüllerinin ayrıntılı açıklaması" intro="Her başlık; modülün ne olduğunu, neden gerekli olduğunu, çalışma ilkesini, giriş/çıkışlarını, kullanılan entegreleri ve nihai bilgisayardaki rolünü içerir.">
        <div className="space-y-3">
          {modules.map((mod) => (
            <Disclosure key={mod.id} id={`modul-${mod.id}`} open={open.has(mod.id)} onToggle={(v) => toggle(mod.id, v)}
              title={<><span className="mono text-[14px] text-brand">{String(mod.index).padStart(2, '0')}</span> {mod.title} <span className="text-[13px] font-normal text-ink-3">({mod.en})</span></>}>
              <ModuleBody m={mod} />
            </Disclosure>
          ))}

          <Disclosure id="modul-isa" open={open.has('isa')} onToggle={(v) => toggle('isa', v)} title={<><span className="mono text-[14px] text-brand">10</span> Komut Seti ve Mikrokod <span className="text-[13px] font-normal text-ink-3">(Instruction Set & Microcode)</span></>}>
            <div className="space-y-6">
              <ComponentLinks slugs={['isa', 'eeprom']} />
              <p className="prose-body">Her komut 8 bittir: üst 4 bit <b>işlem kodu (opcode)</b>, alt 4 bit <b>işlenen (operand)</b>. Kontrol birimi EEPROM’larında her opcode için T0–T4 adımlarında üretilecek kontrol kelimeleri saklanır. Aşağıdaki komut seti Ben Eater’ın kontrol mantığı bölümündeki son hâle dayanmaktadır; proje ekibi gerektiğinde komut ekleyebilir.</p>
              <Figure n="2.10a" kind="referans" caption="Komut seti tablosu.">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[520px] text-[14px]">
                    <thead><tr className="border-b-2 border-brand text-left"><th className="py-2 pr-3">Komut</th><th className="pr-3">Opcode</th><th className="pr-3">Operand</th><th>Açıklama</th></tr></thead>
                    <tbody>{INSTRUCTIONS.map((i) => (
                      <tr key={i.mnemonic} className="border-b border-brand-line/60"><td className="mono py-1.5 pr-3 font-semibold text-brand">{i.mnemonic}</td><td className="mono pr-3">{i.op.toString(2).padStart(4, '0')}</td><td className="mono pr-3 text-ink-3">{i.usesArg ? 'aaaa' : '—'}</td><td className="text-ink-2">{i.tr}</td></tr>
                    ))}</tbody>
                  </table>
                </div>
              </Figure>
              <Figure n="2.10b" kind="kavramsal" caption="Mikrokod tablosu: her komutun adım adım kontrol sinyalleri. T0–T1 tüm komutlar için ortak komut alma (fetch) adımlarıdır. JC/JZ için atlama sinyali yalnızca ilgili bayrak 1 iken üretilir.">
                <div className="overflow-x-auto">
                  <table className="mono w-full min-w-[640px] text-[12.5px]">
                    <thead><tr className="border-b-2 border-brand text-left font-sans text-[13px]"><th className="py-2 pr-2">Komut</th>{['T0', 'T1', 'T2', 'T3', 'T4'].map((t) => <th key={t} className="pr-2">{t}</th>)}</tr></thead>
                    <tbody>{INSTRUCTIONS.map((i) => {
                      const ex = microcode(i.op, true, true);
                      return (
                        <tr key={i.mnemonic} className="border-b border-brand-line/60">
                          <td className="py-1.5 pr-2 font-semibold text-brand">{i.mnemonic}</td>
                          <td className="pr-2 text-ink-3">CO MI</td><td className="pr-2 text-ink-3">RO II CE</td>
                          {ex.map((sg, k) => <td key={k} className="pr-2">{sg.length ? sg.join(' ') : '—'}{(i.mnemonic === 'JC' || i.mnemonic === 'JZ') && k === 0 ? '*' : ''}</td>)}
                        </tr>
                      );
                    })}</tbody>
                  </table>
                </div>
              </Figure>
              <div>
                <div className="eyebrow mb-2">16-bit kontrol kelimesi</div>
                <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-8">
                  {SIGNALS.map((s, i) => (
                    <div key={s} title={signalInfo[s]} className="rounded border border-brand-line p-2 text-center">
                      <div className="mono text-[10px] text-ink-3">bit {15 - i}</div>
                      <div className="mono text-[13px] font-bold text-brand">{s}</div>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-[13px] text-ink-3">Bir sinyalin açıklamasını görmek için üzerine gelin. Bit sıralaması gösterim amaçlıdır; EEPROM’lardaki fiziksel bit yerleşimi şemalarla birlikte kesinleştirilecektir.</p>
              </div>
            </div>
          </Disclosure>

          <Disclosure id="modul-cycle" open={open.has('cycle')} onToggle={(v) => toggle('cycle', v)} title={<><span className="mono text-[14px] text-brand">11</span> Sistemin Genel Çalışma Döngüsü <span className="text-[13px] font-normal text-ink-3">(Fetch – Execute)</span></>}>
            <div className="space-y-5">
              <ComponentLinks slugs={['integration']} />
              <p className="prose-body">Her komut beş mikro adımda (T0–T4) yürütülür. İlk iki adım bütün komutlar için aynıdır: program sayacındaki adres MAR’a aktarılır, ardından bu adresteki komut komut yazmacına yüklenir ve program sayacı artırılır. Kalan adımlar komutun opcode’una göre kontrol biriminin mikrokodu tarafından belirlenir.</p>
              <Figure n="2.11a" kind="kavramsal" caption="Komut alma (T0–T1) ve yürütme (T2–T4) mikro adımları."><CycleDiagram /></Figure>
              <Callout title="Komut yürütme örneği">Aşağıdaki etkileşimli örnekte <b>LDA 14 → ADD 15 → OUT → HLT</b> programı adım adım yürütülür. Her adımda veri yoluna yazan modül <b className="text-brand">bordo</b>, okuyan modüller <b>açık pembe</b> ile vurgulanır. Bu bir web tabanlı eğitsel modeldir.</Callout>
              <Figure n="2.11b" kind="simulasyon" caption="Örnek programın mikro adım düzeyinde yürütülmesi: veri yolu değeri, aktif kontrol sinyalleri, yazmaç içerikleri ve RAM.">
                <CpuRunner />
              </Figure>
            </div>
          </Disclosure>
        </div>
      </Section>

      <StageNav current="architecture" />
    </>
  );
}
