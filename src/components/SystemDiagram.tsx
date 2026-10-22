import { blocks, type Block, type ModuleId } from '../data/architecture';
import type { Signal } from '../lib/cpu';
import { bin } from '../lib/cpu';

export const signalBlock: Partial<Record<Signal, { key: string; dir: 'in' | 'out' | 'ctl' }>> = {
  CO: { key: 'pc', dir: 'out' }, J: { key: 'pc', dir: 'in' }, CE: { key: 'pc', dir: 'ctl' },
  MI: { key: 'mar', dir: 'in' }, RI: { key: 'ram', dir: 'in' }, RO: { key: 'ram', dir: 'out' },
  II: { key: 'ir', dir: 'in' }, IO: { key: 'ir', dir: 'out' }, AI: { key: 'a', dir: 'in' }, AO: { key: 'a', dir: 'out' },
  EO: { key: 'alu', dir: 'out' }, SU: { key: 'alu', dir: 'ctl' }, BI: { key: 'b', dir: 'in' }, OI: { key: 'out', dir: 'in' },
  FI: { key: 'flags', dir: 'ctl' }, HLT: { key: 'clock', dir: 'ctl' },
};

const BUS_L = 330, BUS_R = 390, BUS_T = 20, BUS_B = 392;

interface Props {
  selected?: ModuleId | null;
  onSelect?: (m: ModuleId) => void;
  /** Komut yürütme görünümü: aktif kontrol sinyalleri ve veri yolu değeri */
  active?: Signal[];
  busValue?: number | null;
}

export default function SystemDiagram({ selected, onSelect, active, busValue }: Props) {
  const exec = !!active;
  const role = (b: Block): 'src' | 'dst' | 'ctl' | 'sel' | null => {
    if (exec) {
      const hits = active!.map((s) => signalBlock[s]).filter((x) => x && x.key === b.key);
      if (hits.some((h) => h!.dir === 'out')) return 'src';
      if (hits.some((h) => h!.dir === 'in')) return 'dst';
      if (hits.length) return 'ctl';
      if (b.key === 'control' && active!.length) return 'ctl';
      return null;
    }
    return selected && (b.module === selected || selected === 'bus' && b.bus !== 'none') ? 'sel' : null;
  };
  const busActive = exec ? busValue !== null && busValue !== undefined : selected === 'bus';

  return (
    <svg viewBox="0 0 740 480" className="h-auto w-full select-none" role="group" aria-label="8-bit bilgisayar sistem blok diyagramı">
      <defs>
        <marker id="ah" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L8 4 L0 8 Z" fill="#9E1B32" /></marker>
        <marker id="ahg" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L8 4 L0 8 Z" fill="#B9AEB1" /></marker>
      </defs>

      {/* Veri yolu */}
      <g onClick={() => onSelect?.('bus')} className={onSelect ? 'cursor-pointer' : ''} role={onSelect ? 'button' : undefined} tabIndex={onSelect ? 0 : undefined}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect?.('bus')} aria-label="Ortak veri yolu (8 bit)">
        <rect x={BUS_L} y={BUS_T} width={BUS_R - BUS_L} height={BUS_B - BUS_T} rx="6" fill={busActive ? '#FBEFF1' : '#F7F3F3'} stroke={busActive ? '#9E1B32' : '#E2B4BD'} strokeWidth={busActive ? 2 : 1} />
        {Array.from({ length: 8 }, (_, k) => {
          const bit = busValue != null ? (busValue >> (7 - k)) & 1 : 0;
          return <line key={k} x1={BUS_L + 9 + k * 6} x2={BUS_L + 9 + k * 6} y1={BUS_T + 34} y2={BUS_B - 12} stroke={exec ? (bit ? '#9E1B32' : '#E2B4BD') : busActive ? '#9E1B32' : '#E2B4BD'} strokeWidth={exec && bit ? 2.2 : 1.4}
            strokeDasharray={busActive ? '6 4' : undefined} style={busActive ? { animation: 'flow .9s linear infinite' } : undefined} />;
        })}
        <text x={(BUS_L + BUS_R) / 2} y={BUS_T + 14} textAnchor="middle" fontSize="10" fontWeight="700" fill="#9E1B32">VERİ YOLU</text>
        <text x={(BUS_L + BUS_R) / 2} y={BUS_T + 26} textAnchor="middle" fontSize="9" fill="#4A4850">8 bit</text>
      </g>
      {exec && (
        <g>
          <rect x={BUS_L - 26} y={BUS_B + 4} width={112} height={20} rx="4" fill="#1C1B1F" />
          <text x={(BUS_L + BUS_R) / 2} y={BUS_B + 18} textAnchor="middle" fontSize="11" fontFamily="IBM Plex Mono" fill="#fff">{busValue == null ? 'boşta' : bin(busValue)}</text>
        </g>
      )}

      {/* Doğrudan bağlantılar */}
      <g fontSize="9" fill="#4A4850">
        <line x1="155" y1="234" x2="155" y2="251" stroke="#9E1B32" strokeWidth="1.6" markerEnd="url(#ah)" /><text x="162" y="246">4-bit adres</text>
        <line x1="155" y1="382" x2="155" y2="409" stroke="#9E1B32" strokeWidth="1.6" markerEnd="url(#ah)" /><text x="162" y="399">opcode (4 bit)</text>
        <line x1="565" y1="160" x2="565" y2="177" stroke="#9E1B32" strokeWidth="1.6" markerEnd="url(#ah)" />
        <line x1="565" y1="252" x2="565" y2="235" stroke="#9E1B32" strokeWidth="1.6" markerEnd="url(#ah)" />
        <path d="M680 206 H708 V58 H681" fill="none" stroke="#9E1B32" strokeWidth="1.4" markerEnd="url(#ah)" />
        <path d="M680 44 H722 V438 H681" fill="none" stroke="#B9AEB1" strokeWidth="1.4" markerEnd="url(#ahg)" />
        <text x="714" y="300" transform="rotate(90 714 300)">CF · ZF → kontrol</text>
        <path d="M110 86 V96" stroke="#B9AEB1" strokeWidth="1.2" />
        <text x="46" y="99" fill="#4A4850">CLK → tüm modüller</text>
        <text x="360" y="472" textAnchor="middle" fontSize="9.5">16 kontrol sinyali → tüm modüller</text>
      </g>

      {/* Modül–veri yolu bağlantıları */}
      {blocks.filter((b) => b.bus !== 'none').map((b) => {
        const r = role(b);
        const hot = r === 'src' || r === 'dst' || r === 'sel';
        const cy = b.y + b.h / 2;
        const [x1, x2] = b.side === 'L' ? [b.x + b.w, BUS_L] : [b.x, BUS_R];
        const toBus = b.bus === 'out' || b.bus === 'both';
        const fromBus = b.bus === 'in' || b.bus === 'both';
        const color = hot ? '#9E1B32' : '#B9AEB1';
        const m = hot ? 'url(#ah)' : 'url(#ahg)';
        const showEnd = exec ? r === 'src' : toBus;
        const showStart = exec ? r === 'dst' : fromBus;
        return (
          <line key={b.key} x1={x1} y1={cy} x2={x2} y2={cy} stroke={color} strokeWidth={hot ? 3 : 1.6}
            markerEnd={showEnd ? m : undefined} markerStart={showStart ? m : undefined}
            strokeDasharray={exec && hot ? '6 4' : undefined} style={exec && hot ? { animation: 'flow .8s linear infinite' } : undefined} />
        );
      })}

      {/* Bloklar */}
      {blocks.map((b) => {
        const r = role(b);
        const fill = r === 'src' ? '#9E1B32' : r === 'dst' || r === 'sel' ? '#FBEFF1' : r === 'ctl' ? '#F7F3F3' : '#FFFFFF';
        const stroke = r ? '#9E1B32' : '#E2B4BD';
        const txt = r === 'src' ? '#FFFFFF' : '#1C1B1F';
        const sub = r === 'src' ? 'rgba(255,255,255,.8)' : '#4A4850';
        return (
          <g key={b.key} onClick={() => onSelect?.(b.module)} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect?.(b.module)}
            role={onSelect ? 'button' : undefined} tabIndex={onSelect ? 0 : undefined} aria-label={b.label} aria-pressed={onSelect ? r === 'sel' : undefined}
            className={onSelect ? 'cursor-pointer [&:hover>rect]:stroke-[#9E1B32] focus:outline-none [&:focus-visible>rect]:stroke-[3px]' : ''}>
            <rect x={b.x} y={b.y} width={b.w} height={b.h} rx="8" fill={fill} stroke={stroke} strokeWidth={r ? 2 : 1.2} style={{ transition: 'fill .25s, stroke .25s' }} />
            <text x={b.x + 14} y={b.y + 24} fontSize="14" fontWeight="600" fill={txt}>{b.label}</text>
            <text x={b.x + 14} y={b.y + 42} fontSize="10.5" fill={sub} fontFamily="IBM Plex Mono">{b.sub}</text>
            {b.signals.length > 0 && b.key !== 'control' && (
              <text x={b.x + b.w - 10} y={b.y + 42} textAnchor="end" fontSize="9.5" fontFamily="IBM Plex Mono" fill={sub}>{b.signals.join(' ')}</text>
            )}
            {b.key === 'control' && (
              <text x={b.x + b.w - 12} y={b.y + 34} textAnchor="end" fontSize="10" fontFamily="IBM Plex Mono" fill={sub}>
                {exec && active!.length ? active!.join(' · ') : 'HLT MI RI RO IO II AI AO EO SU BI OI CE CO J FI'}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
