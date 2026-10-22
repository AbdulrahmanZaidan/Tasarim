import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Zap, RotateCcw, Play, Pause, Plus, CornerDownRight, PenLine, BookOpen } from 'lucide-react';
import { Bits } from './ui';
import { bin, INSTRUCTIONS, controlFor, signalInfo } from '../lib/cpu';

const signed = (n: number) => (n & 0x80 ? n - 256 : n);

/** 8 bitlik değer girişi: sayı + tıklanabilir bitler */
export function ByteInput({ label, value, onChange, width = 8, id }: { label: string; value: number; onChange: (v: number) => void; width?: number; id: string }) {
  const max = (1 << width) - 1;
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-[13px] font-medium text-ink-2">{label}</label>
      <div className="flex flex-wrap items-center gap-3">
        <input id={id} type="number" min={0} max={max} value={value} className="input mono w-24"
          onChange={(e) => onChange(Math.max(0, Math.min(max, Math.floor(Number(e.target.value) || 0))))} />
        <div className="flex gap-1" role="group" aria-label={`${label} bitleri`}>
          {Array.from({ length: width }, (_, i) => {
            const bit = width - 1 - i, on = (value >> bit) & 1;
            return (
              <button key={i} type="button" onClick={() => onChange(value ^ (1 << bit))} aria-pressed={!!on} aria-label={`bit ${bit}`}
                className={`mono h-8 w-7 rounded border text-[13px] font-semibold transition-colors ${on ? 'border-brand bg-brand text-white' : 'border-brand-line bg-white text-ink-3 hover:border-brand'}`}>{on}</button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function Panel({ title, children, badge }: { title: string; children: ReactNode; badge?: string }) {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-brand-line bg-brand-mist px-4 py-2">
        <span className="text-[12px] font-semibold tracking-[0.12em] text-brand">{title}</span>
        <span className="text-[11px] text-ink-3">{badge ?? 'Eğitsel simülasyon'}</span>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

/* ---------------- İkili toplayıcı / çıkarıcı ---------------- */
export function AdderDemo() {
  const [a, setA] = useState(28);
  const [b, setB] = useState(14);
  const [sub, setSub] = useState(false);
  const bb = sub ? ~b & 0xff : b;
  const cin = sub ? 1 : 0;
  const raw = a + bb + cin;
  const sum = raw & 0xff;
  const carry = raw > 0xff;
  // bit bazlı elde zinciri
  const carries: number[] = [];
  let c = cin;
  for (let i = 0; i < 8; i++) { const s = ((a >> i) & 1) + ((bb >> i) & 1) + c; c = s >> 1; carries.unshift(c); }
  const overflow = ((a ^ sum) & (bb ^ sum) & 0x80) !== 0;
  return (
    <Panel title="İKİLİ TOPLAYICI / ÇIKARICI">
      <div className="grid gap-4 md:grid-cols-2">
        <ByteInput id="add-a" label="A yazmacı" value={a} onChange={setA} />
        <ByteInput id="add-b" label="B yazmacı" value={b} onChange={setB} />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2" role="radiogroup" aria-label="İşlem">
        {[['Toplama (SU = 0)', false], ['Çıkarma (SU = 1)', true]].map(([l, v]) => (
          <button key={String(v)} role="radio" aria-checked={sub === v} onClick={() => setSub(v as boolean)} className={sub === v ? 'btn-primary py-1.5' : 'btn-outline py-1.5'}>{l as string}</button>
        ))}
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="mono min-w-[460px] text-[14px]">
          <tbody>
            <tr className="text-[12px] text-ink-3"><td className="pr-4 font-sans">Elde zinciri</td><td className="tracking-[0.35em]">{carries.join('')}</td><td className="pl-4">C<sub>in</sub>={cin}</td></tr>
            <tr><td className="pr-4 font-sans text-[13px] text-ink-2">A</td><td className="tracking-[0.35em]">{bin(a)}</td><td className="pl-4 text-ink-3">{a}</td></tr>
            <tr><td className="pr-4 font-sans text-[13px] text-ink-2">{sub ? 'B̅ (XOR ile terslenmiş)' : 'B'}</td><td className="tracking-[0.35em]">{bin(bb)}</td><td className="pl-4 text-ink-3">{sub ? `¬${b}` : b}</td></tr>
            <tr className="border-t-2 border-brand font-semibold text-brand"><td className="pr-4 pt-1 font-sans text-[13px]">Σ</td><td className="pt-1 tracking-[0.35em]">{bin(sum)}</td><td className="pl-4 pt-1">{sum}</td></tr>
          </tbody>
        </table>
      </div>
      <div className="mt-4 grid gap-2 text-[13px] sm:grid-cols-4">
        <div className="card-soft p-2.5"><div className="text-ink-3">İşaretsiz sonuç</div><div className="mono text-[17px] font-bold">{sum}</div></div>
        <div className="card-soft p-2.5"><div className="text-ink-3">İşaretli (ikiye tümleyen)</div><div className="mono text-[17px] font-bold">{signed(sum)}</div></div>
        <div className={`rounded-[10px] p-2.5 ${carry ? 'bg-brand text-white' : 'bg-brand-mist'}`}><div className={carry ? 'text-white/80' : 'text-ink-3'}>Elde / taşma (CF)</div><div className="mono text-[17px] font-bold">{+carry}</div></div>
        <div className={`rounded-[10px] p-2.5 ${overflow ? 'bg-amber-500 text-white' : 'bg-brand-mist'}`}><div className={overflow ? 'text-white/90' : 'text-ink-3'}>İşaretli taşma (V)</div><div className="mono text-[17px] font-bold">{+overflow}</div></div>
      </div>
      <p className="mt-3 text-[12.5px] leading-5 text-ink-3">
        {sub ? `Çıkarma: A − B = A + B̅ + 1. CF = 1 ise sonuç negatif değildir (A ≥ B, işaretsiz).` : 'Toplama: 9. bite taşan değer CF bayrağına yazılır.'} Referans tasarımda yalnızca CF ve ZF bayrakları saklanır; V bilgisi burada eğitsel amaçla gösterilmektedir.
      </p>
    </Panel>
  );
}

/* ---------------- Yazmaç (74LS173 davranışı) ---------------- */
export function RegisterDemo() {
  const [bus, setBus] = useState(42);
  const [load, setLoad] = useState(true);
  const [oe, setOe] = useState(false);
  const [reg, setReg] = useState(0);
  const [flash, setFlash] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const clk = () => {
    setFlash(true); setTimeout(() => setFlash(false), 250);
    if (load) { setReg(bus); setLog((l) => [`↑CLK · AI=1 → A ← ${bin(bus)} (${bus})`, ...l].slice(0, 5)); }
    else setLog((l) => [`↑CLK · AI=0 → A değişmedi (${bin(reg)})`, ...l].slice(0, 5));
  };
  return (
    <Panel title="YAZMAÇ YÜKLEME (A YAZMACI)">
      <ByteInput id="reg-bus" label="Veri yolundaki değer" value={bus} onChange={setBus} />
      <div className="mt-4 flex flex-wrap gap-2">
        <button className={load ? 'btn-primary py-1.5' : 'btn-outline py-1.5'} onClick={() => setLoad(!load)} aria-pressed={load}>AI (yükle) = {+load}</button>
        <button className={oe ? 'btn-primary py-1.5' : 'btn-outline py-1.5'} onClick={() => setOe(!oe)} aria-pressed={oe}>AO (çıkış) = {+oe}</button>
        <button className="btn-primary py-1.5" onClick={clk}><Zap size={15} aria-hidden /> Saat darbesi</button>
        <button className="btn-ghost py-1.5" onClick={() => { setReg(0); setLog([]); }}><RotateCcw size={15} aria-hidden /> Temizle</button>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className={`rounded-lg border p-3 transition-colors ${flash ? 'border-brand bg-brand-soft' : 'border-brand-line'}`}>
          <div className="mb-2 text-[12px] text-ink-3">A yazmacı içeriği (2 × 74LS173)</div>
          <Bits value={reg} color="red" label="A yazmacı" /><div className="mono mt-1.5 text-[13px]">{bin(reg)} = {reg}</div>
        </div>
        <div className="rounded-lg border border-brand-line p-3">
          <div className="mb-2 text-[12px] text-ink-3">74LS245 çıkışı → veri yolu</div>
          {oe ? <><Bits value={reg} color="blue" label="Yazmaç çıkışı" /><div className="mono mt-1.5 text-[13px]">{bin(reg)}</div></> : <div className="mono py-1 text-[13px] text-ink-3">Z (yüksek empedans — veri yolundan ayrık)</div>}
        </div>
      </div>
      <ul className="mono mt-3 space-y-0.5 text-[12px] text-ink-3" aria-live="polite">{log.map((l, i) => <li key={i} className={i === 0 ? 'text-ink' : ''}>{l}</li>)}</ul>
    </Panel>
  );
}

/* ---------------- Program sayacı ---------------- */
export function CounterDemo() {
  const [pc, setPc] = useState(0);
  const [ce, setCe] = useState(true);
  const [jv, setJv] = useState(3);
  const [hist, setHist] = useState<number[]>([0]);
  const push = (v: number) => { setPc(v); setHist((h) => [...h, v].slice(-16)); };
  return (
    <Panel title="PROGRAM SAYACI (74LS161)">
      <div className="flex flex-wrap items-center gap-2">
        <button className={ce ? 'btn-primary py-1.5' : 'btn-outline py-1.5'} onClick={() => setCe(!ce)} aria-pressed={ce}>CE = {+ce}</button>
        <button className="btn-primary py-1.5" onClick={() => push(ce ? (pc + 1) & 15 : pc)}><Plus size={15} aria-hidden /> Saat darbesi</button>
        <button className="btn-outline py-1.5" onClick={() => push(0)}><RotateCcw size={15} aria-hidden /> Reset</button>
        <span className="mx-1 h-6 w-px bg-brand-line" />
        <label htmlFor="pc-j" className="text-[13px] text-ink-2">Atlama adresi</label>
        <input id="pc-j" type="number" min={0} max={15} value={jv} onChange={(e) => setJv(Math.max(0, Math.min(15, Number(e.target.value) || 0)))} className="input mono w-20" />
        <button className="btn-outline py-1.5" onClick={() => push(jv)}><CornerDownRight size={15} aria-hidden /> J (yükle)</button>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-6">
        <div><Bits value={pc} width={4} color="green" label="Program sayacı" size={20} /><div className="mono mt-1.5 text-[14px]">{bin(pc, 4)} = {pc}</div></div>
        <div className="flex flex-wrap gap-1" aria-label="Adres çemberi">
          {Array.from({ length: 16 }, (_, i) => (
            <span key={i} className={`mono flex h-7 w-7 items-center justify-center rounded text-[11px] transition-all ${i === pc ? 'scale-110 bg-brand font-bold text-white' : 'bg-brand-mist text-ink-3'}`}>{i}</span>
          ))}
        </div>
      </div>
      <div className="mt-3 text-[12px] text-ink-3">Geçmiş: <span className="mono">{hist.join(' → ')}</span> {pc === 15 && ce && '· sonraki darbede 15 → 0 (taşma ile sarar)'}</div>
    </Panel>
  );
}

/* ---------------- RAM okuma / yazma ---------------- */
export function RamDemo() {
  const [mem, setMem] = useState<number[]>(() => { const m = Array(16).fill(0); m[14] = 28; m[15] = 14; return m; });
  const [addr, setAddr] = useState(14);
  const [mar, setMar] = useState(14);
  const [data, setData] = useState(99);
  const [bus, setBus] = useState<number | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const add = (s: string) => setLog((l) => [s, ...l].slice(0, 6));
  return (
    <Panel title="RAM OKUMA / YAZMA ÇEVRİMİ">
      <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
        <div className="space-y-3">
          <div className="flex flex-wrap items-end gap-2">
            <div><label htmlFor="ram-a" className="mb-1 block text-[13px] text-ink-2">Adres (veri yolu alt 4 bit)</label>
              <input id="ram-a" type="number" min={0} max={15} value={addr} onChange={(e) => setAddr(Math.max(0, Math.min(15, Number(e.target.value) || 0)))} className="input mono w-24" /></div>
            <button className="btn-outline py-2" onClick={() => { setMar(addr); setBus(addr); add(`1) MI + ↑CLK → MAR ← ${bin(addr, 4)}`); }}>MI · MAR’a yükle</button>
          </div>
          <ByteInput id="ram-d" label="Yazılacak veri" value={data} onChange={setData} />
          <div className="flex flex-wrap gap-2">
            <button className="btn-primary py-1.5" onClick={() => { setMem((m) => m.map((v, i) => (i === mar ? data : v))); setBus(data); add(`2) RI + ↑CLK → RAM[${mar}] ← ${bin(data)} (${data})`); }}><PenLine size={15} aria-hidden /> RI · Yaz</button>
            <button className="btn-primary py-1.5" onClick={() => { setBus(mem[mar]); add(`2) RO → veri yolu = RAM[${mar}] = ${bin(mem[mar])} (${mem[mar]})`); }}><BookOpen size={15} aria-hidden /> RO · Oku</button>
          </div>
          <div className="rounded-lg border border-brand-line p-3">
            <div className="mb-1.5 text-[12px] text-ink-3">Veri yolu</div>
            <Bits value={bus} color="red" label="Veri yolu" /><div className="mono mt-1 text-[13px]">{bus === null ? 'boşta' : `${bin(bus)} = ${bus}`}</div>
          </div>
          <ul className="mono space-y-0.5 text-[12px] text-ink-3" aria-live="polite">{log.map((l, i) => <li key={i} className={i === 0 ? 'text-ink' : ''}>{l}</li>)}</ul>
        </div>
        <table className="mono w-full self-start text-[12px]">
          <thead><tr className="text-left text-ink-3"><th className="py-1 pl-2 font-medium">Adres</th><th className="font-medium">Veri</th><th className="pr-2 text-right font-medium">Ond.</th></tr></thead>
          <tbody>{mem.map((v, i) => (
            <tr key={i} className={`border-t border-brand-line/50 transition-colors ${i === mar ? 'bg-brand text-white' : ''}`}>
              <td className="py-0.5 pl-2">{bin(i, 4)}</td><td>{bin(v)}</td><td className="pr-2 text-right">{v}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </Panel>
  );
}

/* ---------------- Saat ---------------- */
export function ClockDemo() {
  const [auto, setAuto] = useState(true);
  const [hz, setHz] = useState(2);
  const [halt, setHalt] = useState(false);
  const [level, setLevel] = useState(0);
  const [trace, setTrace] = useState<number[]>(() => Array(32).fill(0));
  const [edges, setEdges] = useState(0);
  const lv = useRef(0);
  const set = (v: number) => { if (v && !lv.current) setEdges((e) => e + 1); lv.current = v; setLevel(v); setTrace((t) => [...t.slice(1), v]); };
  useEffect(() => {
    if (!auto || halt) return;
    const id = setInterval(() => set(lv.current ? 0 : 1), 1000 / hz / 2);
    return () => clearInterval(id);
  }, [auto, hz, halt]);
  const pulse = () => { if (halt) return; set(1); setTimeout(() => set(0), 180); };
  const Y = (v: number) => (v ? 6 : 34);
  let d = `M0 ${Y(trace[0])}`;
  trace.forEach((v, i) => { d += ` H${(i + 1) * 10}`; if (i < trace.length - 1 && trace[i + 1] !== v) d += ` V${Y(trace[i + 1])}`; });
  return (
    <Panel title="SAAT MODÜLÜ">
      <div className="flex flex-wrap items-center gap-2">
        <button className={auto ? 'btn-primary py-1.5' : 'btn-outline py-1.5'} onClick={() => setAuto(true)} aria-pressed={auto}><Play size={15} aria-hidden /> Otomatik (astable)</button>
        <button className={!auto ? 'btn-primary py-1.5' : 'btn-outline py-1.5'} onClick={() => setAuto(false)} aria-pressed={!auto}><Pause size={15} aria-hidden /> Manuel (monostable)</button>
        <button className={halt ? 'btn-primary py-1.5' : 'btn-outline py-1.5'} onClick={() => setHalt(!halt)} aria-pressed={halt}>HLT = {+halt}</button>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        {auto ? (
          <label className="flex items-center gap-3 text-[13px] text-ink-2">Frekans (potansiyometre)
            <input type="range" min={0.5} max={8} step={0.5} value={hz} onChange={(e) => setHz(Number(e.target.value))} className="accent-[#9E1B32]" />
            <span className="mono w-14">{hz} Hz</span></label>
        ) : <button className="btn-primary py-1.5" onClick={pulse} disabled={halt}><Zap size={15} aria-hidden /> Adım butonu</button>}
        <span className="ml-auto flex items-center gap-2 text-[13px] text-ink-2">CLK <span className={`h-5 w-5 rounded-full border border-black/10 transition-colors ${level ? 'bg-blue-600 shadow-[0_0_10px_rgba(37,99,235,.8)]' : 'bg-neutral-200'}`} /></span>
        <span className="mono text-[13px] text-ink-3">yükselen kenar: {edges}</span>
      </div>
      <svg viewBox="0 0 320 40" className="mt-3 h-14 w-full rounded bg-brand-mist" preserveAspectRatio="none" aria-label="Son saat örnekleri">
        <path d={d} fill="none" stroke="#9E1B32" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
      <p className="mt-2 text-[12.5px] text-ink-3">HLT = 1 iken saat sinyali kapılanır; ne otomatik ne de manuel kipte darbe oluşmaz. Gösterilen frekanslar görselleştirme içindir.</p>
    </Panel>
  );
}

/* ---------------- Komut çözme ---------------- */
export function DecodeDemo() {
  const [op, setOp] = useState(0b0010);
  const [arg, setArg] = useState(15);
  const ins = INSTRUCTIONS.find((i) => i.op === op)!;
  const byte = (op << 4) | (ins.usesArg ? arg : 0);
  return (
    <Panel title="KOMUT ÇÖZME (DECODE)">
      <div className="flex flex-wrap items-end gap-3">
        <div><label htmlFor="dec-op" className="mb-1 block text-[13px] text-ink-2">Komut</label>
          <select id="dec-op" className="input mono w-auto" value={op} onChange={(e) => setOp(Number(e.target.value))}>{INSTRUCTIONS.map((i) => <option key={i.op} value={i.op}>{i.mnemonic}</option>)}</select></div>
        <div><label htmlFor="dec-arg" className="mb-1 block text-[13px] text-ink-2">Operand</label>
          <input id="dec-arg" type="number" min={0} max={15} disabled={!ins.usesArg} value={arg} onChange={(e) => setArg(Math.max(0, Math.min(15, Number(e.target.value) || 0)))} className="input mono w-20" /></div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 mono text-[18px]">
        {bin(byte).split('').map((b, i) => (
          <span key={i} className={`flex h-10 w-8 items-center justify-center rounded border font-bold ${i < 4 ? 'border-brand bg-brand text-white' : 'border-brand-line bg-brand-soft text-brand'}`}>{b}</span>
        ))}
        <span className="ml-2 font-sans text-[13px] text-ink-3"><b className="text-brand">opcode</b> = {bin(op, 4)} · <b>operand</b> = {ins.usesArg ? bin(arg, 4) : '—'}</span>
      </div>
      <p className="mt-2 text-[14px] text-ink-2"><b className="mono">{ins.usesArg ? `${ins.mnemonic} ${arg}` : ins.mnemonic}</b> — {ins.tr}</p>
      <ol className="mt-3 grid gap-1.5 sm:grid-cols-5">
        {[0, 1, 2, 3, 4].map((t) => {
          const sg = controlFor(op, t, true, true);
          return (
            <li key={t} className={`rounded-lg border p-2 ${t < 2 ? 'border-brand-line bg-brand-mist' : 'border-brand bg-white'}`}>
              <div className="mono text-[12px] font-bold text-brand">T{t}</div>
              <div className="mono text-[12px]">{sg.length ? sg.join(' ') : '—'}</div>
              <div className="mt-0.5 text-[11px] leading-4 text-ink-3">{sg.length ? signalInfo[sg[0]].split(' (')[0] : 'boş adım'}</div>
            </li>
          );
        })}
      </ol>
      {(ins.mnemonic === 'JC' || ins.mnemonic === 'JZ') && <p className="mt-2 text-[12px] text-ink-3">Gösterim, ilgili bayrağın 1 olduğu durum içindir; bayrak 0 ise T2 boş adımdır.</p>}
    </Panel>
  );
}
