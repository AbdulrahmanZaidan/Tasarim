import { ArrowRight } from 'lucide-react';
import type { ArchModule } from '../data/architecture';

/** Modülün giriş → entegreler → çıkış yapısını gösteren etiketli blok diyagramı. */
export function ModuleDiagram({ m }: { m: ArchModule }) {
  return (
    <div className="grid items-stretch gap-3 md:grid-cols-[1fr_auto_1.1fr_auto_1fr]">
      <div className="rounded-lg border border-dashed border-brand-line p-3">
        <div className="mb-2 text-[11px] font-semibold tracking-[0.12em] text-brand">GİRİŞLER</div>
        <ul className="space-y-1.5 text-[13px] leading-5 text-ink-2">{m.inputs.map((x) => <li key={x} className="flex gap-1.5"><span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />{x}</li>)}</ul>
      </div>
      <div className="hidden items-center md:flex"><ArrowRight className="text-brand" aria-hidden /></div>
      <div className="rounded-lg border-2 border-brand bg-brand-soft p-3">
        <div className="text-center text-[14px] font-bold text-ink">{m.title}</div>
        <div className="text-center text-[11px] text-ink-3">{m.en}</div>
        <div className="mt-3 grid gap-1.5">
          {m.ics.map((ic) => (
            <div key={ic.part} className="flex items-center gap-2 rounded bg-ink px-2 py-1.5 text-white">
              <span className="relative h-3 w-3 shrink-0 rounded-sm border border-white/30"><span className="absolute left-0.5 top-0.5 h-1 w-1 rounded-full bg-white/50" /></span>
              <span className="mono text-[12px] font-semibold">{ic.part}</span>
              <span className="truncate text-[11px] text-white/70">{ic.role}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="hidden items-center md:flex"><ArrowRight className="text-brand" aria-hidden /></div>
      <div className="rounded-lg border border-dashed border-brand-line p-3">
        <div className="mb-2 text-[11px] font-semibold tracking-[0.12em] text-brand">ÇIKIŞLAR</div>
        <ul className="space-y-1.5 text-[13px] leading-5 text-ink-2">{m.outputs.map((x) => <li key={x} className="flex gap-1.5"><span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-ink-3" />{x}</li>)}</ul>
      </div>
    </div>
  );
}

/** Saat sinyali zamanlama diyagramı. */
export function ClockWave() {
  const periods = 5, pw = 120, x0 = 70;
  const sq = (y: number, inv = false) => {
    let d = `M${x0} ${inv ? y : y + 30}`;
    for (let i = 0; i < periods; i++) {
      const x = x0 + i * pw;
      d += inv ? ` H${x + pw / 2} V${y + 30} H${x + pw} V${y}` : ` H${x} V${y} H${x + pw / 2} V${y + 30} H${x + pw}`;
    }
    return d;
  };
  return (
    <svg viewBox="0 0 700 220" className="h-auto w-full" role="img" aria-label="CLK ve terslenmiş CLK sinyallerinin zamanlama diyagramı">
      <g fontSize="11" fontFamily="IBM Plex Mono" fill="#1C1B1F">
        <text x="10" y="50">CLK</text><text x="10" y="120">CLK̅</text><text x="10" y="186">Adım</text>
      </g>
      <path d={sq(30)} fill="none" stroke="#9E1B32" strokeWidth="2.4" />
      <path d={sq(100, true)} fill="none" stroke="#4A4850" strokeWidth="2" />
      {Array.from({ length: periods }, (_, i) => {
        const x = x0 + i * pw;
        return (
          <g key={i}>
            <line x1={x} x2={x} y1="20" y2="200" stroke="#E2B4BD" strokeDasharray="3 4" />
            <path d={`M${x - 5} 46 L${x} 38 L${x + 5} 46`} fill="none" stroke="#9E1B32" strokeWidth="1.8" />
            <rect x={x + pw / 2 + 4} y="170" width={pw - 8} height="24" rx="4" fill="#FBEFF1" stroke="#E2B4BD" />
            <text x={x + pw} y="186" textAnchor="middle" fontSize="11" fontFamily="IBM Plex Mono" fill="#9E1B32">T{i}</text>
          </g>
        );
      })}
      <circle r="5" fill="#9E1B32"><animateMotion dur="5s" repeatCount="indefinite" path={sq(30)} /></circle>
      <text x={x0 + 4} y="16" fontSize="10.5" fill="#4A4850">↑ yükselen kenar: yazmaçlar veri yolundaki değeri alır</text>
      <text x={x0 + pw / 2 + 4} y="160" fontSize="10.5" fill="#4A4850">CLK̅ yükselen kenarı (CLK düşen kenarı): mikro adım sayacı ilerler, kontrol sinyalleri değişir</text>
    </svg>
  );
}

/** Ortak veri yolu kavramsal gösterimi: tek yazan, çok okuyan. */
export function BusConcept() {
  const mods = ['PC', 'RAM', 'IR', 'A', 'ALU'];
  const readers = ['MAR', 'IR', 'A', 'B', 'OUT'];
  return (
    <svg viewBox="0 0 680 230" className="h-auto w-full" role="img" aria-label="Üç-durumlu tamponlarla ortak veri yolu kavramı">
      <rect x="20" y="100" width="640" height="34" rx="6" fill="#FBEFF1" stroke="#9E1B32" />
      <text x="340" y="122" textAnchor="middle" fontSize="12" fontWeight="700" fill="#9E1B32">8-BIT ORTAK VERİ YOLU</text>
      {mods.map((m, i) => {
        const x = 40 + i * 128, on = m === 'RAM';
        return (
          <g key={m}>
            <rect x={x} y="12" width="100" height="36" rx="6" fill={on ? '#9E1B32' : '#fff'} stroke="#9E1B32" />
            <text x={x + 50} y="35" textAnchor="middle" fontSize="12" fontWeight="600" fill={on ? '#fff' : '#1C1B1F'}>{m}</text>
            <path d={`M${x + 38} 58 L${x + 62} 58 L${x + 50} 76 Z`} fill={on ? '#9E1B32' : '#fff'} stroke="#9E1B32" />
            <line x1={x + 50} x2={x + 50} y1="48" y2="58" stroke="#9E1B32" />
            <line x1={x + 50} x2={x + 50} y1="76" y2="100" stroke={on ? '#9E1B32' : '#E2B4BD'} strokeWidth={on ? 2.5 : 1.2} strokeDasharray={on ? undefined : '3 3'} />
            <text x={x + 68} y="70" fontSize="9" fontFamily="IBM Plex Mono" fill="#4A4850">{on ? 'OE=1' : 'Z'}</text>
          </g>
        );
      })}
      {readers.map((m, i) => {
        const x = 40 + i * 128, on = m === 'IR';
        return (
          <g key={m}>
            <line x1={x + 50} x2={x + 50} y1="134" y2="178" stroke={on ? '#9E1B32' : '#E2B4BD'} strokeWidth={on ? 2.5 : 1.2} markerEnd="" />
            <rect x={x} y="178" width="100" height="36" rx="6" fill={on ? '#FBEFF1' : '#fff'} stroke={on ? '#9E1B32' : '#E2B4BD'} strokeWidth={on ? 2 : 1} />
            <text x={x + 50} y="201" textAnchor="middle" fontSize="12" fontWeight="600" fill="#1C1B1F">{m}{on ? ' ← yükle' : ''}</text>
          </g>
        );
      })}
    </svg>
  );
}

/** Fetch–decode–execute döngüsü. */
export function CycleDiagram() {
  const steps = [
    { t: 'T0', a: 'CO · MI', d: 'PC → MAR' },
    { t: 'T1', a: 'RO · II · CE', d: 'RAM → IR, PC + 1' },
    { t: 'T2', a: 'komuta göre', d: 'Yürütme 1' },
    { t: 'T3', a: 'komuta göre', d: 'Yürütme 2' },
    { t: 'T4', a: 'komuta göre', d: 'Yürütme 3' },
  ];
  return (
    <div className="grid gap-2 sm:grid-cols-5">
      {steps.map((s, i) => (
        <div key={s.t} className={`relative rounded-lg border p-3 ${i < 2 ? 'border-brand bg-brand-soft' : 'border-brand-line bg-white'}`}>
          <div className="mono text-[13px] font-bold text-brand">{s.t}</div>
          <div className="mt-1 text-[14px] font-semibold">{s.d}</div>
          <div className="mono mt-0.5 text-[12px] text-ink-3">{s.a}</div>
          <div className="mt-2 text-[11px] font-semibold tracking-[0.1em] text-ink-3">{i < 2 ? 'KOMUT ALMA (FETCH)' : 'YÜRÜTME (EXECUTE)'}</div>
        </div>
      ))}
    </div>
  );
}
