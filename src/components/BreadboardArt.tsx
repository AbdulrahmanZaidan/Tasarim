/**
 * Ben Eater bilgisayarının breadboard yerleşimini temsil eden KAVRAMSAL illüstrasyon.
 * Gerçek kablolama veya bacak bağlantısı göstermez.
 */
const leds: Record<string, string> = { r: '#dc2626', g: '#10b981', b: '#2563eb', y: '#f59e0b' };

type Board = { label: string; chips: number; led?: { n: number; c: string }; seg?: boolean };
const left: Board[] = [
  { label: 'SAAT', chips: 4, led: { n: 1, c: 'b' } },
  { label: 'PROGRAM SAYACI', chips: 2, led: { n: 4, c: 'g' } },
  { label: 'MAR + RAM', chips: 5, led: { n: 8, c: 'r' } },
  { label: 'KOMUT YAZMACI', chips: 3, led: { n: 8, c: 'b' } },
  { label: 'KONTROL BİRİMİ', chips: 4, led: { n: 8, c: 'b' } },
];
const right: Board[] = [
  { label: 'A YAZMACI', chips: 3, led: { n: 8, c: 'r' } },
  { label: 'ALU', chips: 5, led: { n: 8, c: 'r' } },
  { label: 'B YAZMACI', chips: 3, led: { n: 8, c: 'r' } },
  { label: 'ÇIKIŞ', chips: 4, seg: true },
  { label: 'BAYRAKLAR', chips: 2, led: { n: 2, c: 'y' } },
];

function BoardG({ b, x, y, w, h, i }: { b: Board; x: number; y: number; w: number; h: number; i: number }) {
  const chipW = 26, gap = (w - 24 - b.chips * chipW) / Math.max(1, b.chips - 1);
  return (
    <g style={{ animation: `rise .5s ease-out ${i * 60}ms both` }}>
      <rect x={x} y={y} width={w} height={h} rx="4" fill="#F5F2EC" stroke="#D9D2C5" />
      <line x1={x + 6} x2={x + w - 6} y1={y + 6} y2={y + 6} stroke="#E8B6BF" strokeWidth="1.5" />
      <line x1={x + 6} x2={x + w - 6} y1={y + h - 6} y2={y + h - 6} stroke="#9EB8DC" strokeWidth="1.5" />
      {Array.from({ length: b.chips }, (_, k) => {
        const cx = x + 12 + k * (chipW + gap);
        return (
          <g key={k}>
            <rect x={cx} y={y + 16} width={chipW} height={18} rx="2" fill="#1C1B1F" />
            <circle cx={cx + 4} cy={y + 20} r="1.3" fill="#555" />
          </g>
        );
      })}
      {b.led && Array.from({ length: b.led.n }, (_, k) => (
        <circle key={k} cx={x + w - 14 - k * 9} cy={y + 44} r="3" fill={leds[b.led!.c]} opacity={(k * 7 + i) % 3 ? 0.95 : 0.25}>
          {(k + i) % 3 === 0 && <animate attributeName="opacity" values="0.25;1;0.25" dur={`${1.2 + (k % 3) * 0.4}s`} repeatCount="indefinite" />}
        </circle>
      ))}
      {b.seg && Array.from({ length: 4 }, (_, k) => (
        <g key={k} transform={`translate(${x + w - 24 - k * 18} ${y + 36})`}>
          <rect width="14" height="18" rx="1.5" fill="#2a0a10" />
          <text x="7" y="14" textAnchor="middle" fontSize="13" fontFamily="IBM Plex Mono" fill="#ff3b3b">{['2', '4', ' ', ' '][k]}</text>
        </g>
      ))}
      <text x={x + 10} y={y + 47} fontSize="9.5" fontWeight="600" letterSpacing=".6" fill="#4A4850">{b.label}</text>
    </g>
  );
}

export default function BreadboardArt() {
  const W = 640, bw = 270, bh = 58, gapY = 10, top = 34;
  return (
    <svg viewBox={`0 0 ${W} 360`} className="h-auto w-full" role="img" aria-labelledby="bbtitle">
      <title id="bbtitle">8-bit breadboard bilgisayarın modül yerleşimini gösteren kavramsal illüstrasyon</title>
      <rect x="0" y="0" width={W} height="360" rx="10" fill="#FBEFF1" />
      <text x="20" y="22" fontSize="11" fontWeight="600" letterSpacing="1.5" fill="#9E1B32">MODÜL YERLEŞİMİ · KAVRAMSAL</text>
      {left.map((b, i) => <BoardG key={b.label} b={b} i={i} x={20} y={top + i * (bh + gapY)} w={bw} h={bh} />)}
      {right.map((b, i) => <BoardG key={b.label} b={b} i={i + 5} x={W - 20 - bw} y={top + i * (bh + gapY)} w={bw} h={bh} />)}
      {/* 8-bit veri yolu */}
      <g>
        <rect x={W / 2 - 22} y={top} width="44" height={5 * (bh + gapY) - gapY} rx="4" fill="#F5F2EC" stroke="#D9D2C5" />
        {Array.from({ length: 8 }, (_, k) => (
          <line key={k} x1={W / 2 - 15 + k * 4.3} x2={W / 2 - 15 + k * 4.3} y1={top + 8} y2={top + 5 * (bh + gapY) - gapY - 8}
            stroke="#9E1B32" strokeWidth="1.3" strokeDasharray="6 4" style={{ animation: `flow ${0.8 + k * 0.07}s linear infinite` }} />
        ))}
        <text x={W / 2} y={top + 5 * (bh + gapY) + 8} textAnchor="middle" fontSize="10" fontWeight="600" fill="#9E1B32">8-BIT VERİ YOLU</text>
      </g>
    </svg>
  );
}
