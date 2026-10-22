import { useEffect, useMemo, useState } from 'react';
import { Play, Pause, StepForward, SkipForward, RotateCcw } from 'lucide-react';
import { SIGNALS, initCpu, tick, samplePrograms, disasm, bin, signalInfo, type CpuState, type Signal } from '../lib/cpu';
import SystemDiagram from './SystemDiagram';
import { Bits } from './ui';

const names: Partial<Record<Signal, string>> = { CO: 'Program sayacı', RO: 'RAM', IO: 'Komut yazmacı (operand)', AO: 'A yazmacı', EO: 'ALU' };
const dstNames: Partial<Record<Signal, string>> = { MI: 'MAR', RI: 'RAM', II: 'komut yazmacı', AI: 'A yazmacı', BI: 'B yazmacı', OI: 'çıkış yazmacı', J: 'program sayacı' };

function describe(sig: Signal[], s: CpuState) {
  if (sig.includes('HLT')) return 'HLT: saat durduruldu, program sona erdi.';
  const src = sig.find((x) => names[x]);
  const dst = sig.filter((x) => dstNames[x]).map((x) => dstNames[x]);
  const parts: string[] = [];
  if (src && dst.length) parts.push(`${names[src]} veri yoluna ${bin(s.bus ?? 0)} değerini yazdı; ${dst.join(' ve ')} bu değeri yükledi.`);
  if (sig.includes('CE')) parts.push('Program sayacı bir artırıldı.');
  if (sig.includes('SU')) parts.push('ALU çıkarma kipinde (A + B̅ + 1).');
  if (sig.includes('FI')) parts.push(`Bayraklar güncellendi: CF=${+s.cf}, ZF=${+s.zf}.`);
  if (!parts.length) parts.push('Bu adımda kontrol sinyali yok (boş adım).');
  return parts.join(' ');
}

export default function CpuRunner({ initialProgram = 'add' }: { initialProgram?: string }) {
  const [progId, setProgId] = useState(initialProgram);
  const prog = samplePrograms.find((p) => p.id === progId)!;
  const [s, setS] = useState<CpuState>(() => initCpu(prog.ram));
  const [running, setRunning] = useState(false);

  useEffect(() => { setS(initCpu(prog.ram)); setRunning(false); }, [prog]);

  const step = () => setS((cur) => tick(cur));
  const instr = () => setS((cur) => { let n = tick(cur); while (n.step !== 0 && !n.halted) n = tick(n); return n; });

  useEffect(() => {
    if (!running) return;
    if (s.halted) { setRunning(false); return; }
    const id = setTimeout(step, 650);
    return () => clearTimeout(id);
  }, [running, s]);

  const started = s.cycles > 0;
  const lastStep = s.lastStep;
  const text = useMemo(() => (started ? describe(s.lastSignals, s) : 'Başlamak için “Mikro Adım” düğmesine basın. Her basış bir saat darbesine karşılık gelir.'), [s, started]);

  return (
    <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-[13px] font-medium text-ink-2" htmlFor="prog">Örnek program</label>
          <select id="prog" className="input w-auto" value={progId} onChange={(e) => setProgId(e.target.value)}>
            {samplePrograms.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
          </select>
        </div>
        <p className="text-[13px] text-ink-3">{prog.text}</p>
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" onClick={step} disabled={s.halted || running}><StepForward size={16} aria-hidden /> Mikro Adım</button>
          <button className="btn-outline" onClick={instr} disabled={s.halted || running}><SkipForward size={16} aria-hidden /> Komut Adımı</button>
          <button className="btn-outline" onClick={() => setRunning(!running)} disabled={s.halted}>{running ? <Pause size={16} aria-hidden /> : <Play size={16} aria-hidden />}{running ? 'Duraklat' : 'Otomatik'}</button>
          <button className="btn-ghost" onClick={() => { setS(initCpu(prog.ram)); setRunning(false); }}><RotateCcw size={16} aria-hidden /> Sıfırla</button>
        </div>
        <div className="card p-2 sm:p-3"><SystemDiagram active={started ? s.lastSignals : []} busValue={started ? s.bus : null} /></div>
        <div aria-live="polite" className="rounded-lg border-l-4 border-brand bg-brand-mist px-4 py-3 text-[14px] leading-6">
          {lastStep !== null && <b className="mono text-brand">T{lastStep} · </b>}{text}
        </div>
        <div className="card overflow-x-auto p-3">
          <div className="mb-2 text-[11px] font-semibold tracking-[0.12em] text-brand">KONTROL KELİMESİ</div>
          <div className="flex min-w-[560px] gap-1">
            {SIGNALS.map((sg) => {
              const on = started && s.lastSignals.includes(sg);
              return (
                <div key={sg} title={signalInfo[sg]} className={`flex-1 rounded border py-1 text-center mono text-[11px] font-semibold transition-colors ${on ? 'border-brand bg-brand text-white' : 'border-brand-line text-ink-3'}`}>
                  {sg}<div className="text-[10px] font-normal">{on ? 1 : 0}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-[11px] font-semibold tracking-[0.12em] text-brand">YAZMAÇLAR</div>
            <div className="mono text-[12px] text-ink-3">Çevrim: {s.cycles} {s.halted && <span className="ml-1 rounded bg-ink px-1.5 py-0.5 text-white">HLT</span>}</div>
          </div>
          <div className="space-y-2.5 text-[13px]">
            {([
              ['Veri yolu', s.bus, 8, 'red'],
              ['Program sayacı', s.pc, 4, 'green'],
              ['MAR', s.mar, 4, 'yellow'],
              ['Komut yazmacı', s.ir, 8, 'blue'],
              ['A yazmacı', s.a, 8, 'red'],
              ['B yazmacı', s.b, 8, 'red'],
            ] as const).map(([l, v, w, c]) => (
              <div key={l} className="flex items-center justify-between gap-2">
                <span className="w-28 shrink-0 text-ink-2">{l}</span>
                <Bits value={v} width={w} color={c} label={l} size={12} />
                <span className="mono w-14 text-right text-ink">{v ?? '—'}</span>
              </div>
            ))}
            <div className="flex items-center justify-between gap-2"><span className="w-28 text-ink-2">Bayraklar</span><span className="mono">CF={+s.cf} · ZF={+s.zf}</span></div>
            <div className="flex items-center justify-between gap-2"><span className="w-28 text-ink-2">Adım sayacı</span><span className="mono">T{s.step}</span></div>
          </div>
          <div className="mt-4 rounded-lg bg-[#1a0508] p-3 text-center">
            <div className="text-[10px] font-semibold tracking-[0.14em] text-white/50">ÇIKIŞ GÖSTERGESİ</div>
            <div className="mono text-[34px] leading-tight tracking-[0.2em] text-[#ff3b3b]" style={{ textShadow: '0 0 10px rgba(255,59,59,.6)' }}>{s.out === null ? '----' : String(s.out).padStart(4, ' ')}</div>
          </div>
        </div>
        <div className="card overflow-hidden">
          <div className="border-b border-brand-line bg-brand-mist px-4 py-2 text-[11px] font-semibold tracking-[0.12em] text-brand">RAM İÇERİĞİ (16 BAYT)</div>
          <table className="w-full text-[12.5px]">
            <thead><tr className="text-left text-ink-3"><th className="px-3 py-1.5 font-medium">Adr.</th><th className="px-2 font-medium">İkili</th><th className="px-2 font-medium">Anlamı</th></tr></thead>
            <tbody>
              {s.ram.map((v, a) => {
                const isPc = a === s.pc, isMar = a === s.mar && started;
                const data = prog.dataAddrs.includes(a);
                return (
                  <tr key={a} className={`border-t border-brand-line/50 ${isPc ? 'bg-emerald-50' : ''} ${isMar ? 'outline outline-1 -outline-offset-1 outline-amber-400' : ''}`}>
                    <td className="mono px-3 py-1">{a.toString().padStart(2, '0')}{isPc && <span className="ml-1 text-[10px] text-emerald-700">PC</span>}</td>
                    <td className="mono px-2">{bin(v)}</td>
                    <td className="mono px-2 text-ink-3">{data ? `veri: ${v}` : v === 0 ? '·' : disasm(v)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
