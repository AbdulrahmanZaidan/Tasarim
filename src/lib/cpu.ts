/**
 * Ben Eater SAP-1 tabanlı 8-bit bilgisayarın EĞİTSEL davranış modeli.
 * Bu bir donanım doğrulaması değildir; komut seti ve mikrokod adımları
 * Ben Eater kontrol mantığı videolarındaki yapıyı temel alır.
 */

export const SIGNALS = ['HLT', 'MI', 'RI', 'RO', 'IO', 'II', 'AI', 'AO', 'EO', 'SU', 'BI', 'OI', 'CE', 'CO', 'J', 'FI'] as const;
export type Signal = (typeof SIGNALS)[number];

export const signalInfo: Record<Signal, string> = {
  HLT: 'Saati durdurur (Halt)',
  MI: 'Bellek adres yazmacına veri yolundan yükle (MAR In)',
  RI: 'RAM’e veri yolundan yaz (RAM In)',
  RO: 'RAM içeriğini veri yoluna çıkar (RAM Out)',
  IO: 'Komut yazmacının alt 4 bitini veri yoluna çıkar (Instruction Out)',
  II: 'Komut yazmacına veri yolundan yükle (Instruction In)',
  AI: 'A yazmacına veri yolundan yükle (A In)',
  AO: 'A yazmacını veri yoluna çıkar (A Out)',
  EO: 'ALU sonucunu (Σ) veri yoluna çıkar (Sum Out)',
  SU: 'ALU’yu çıkarma kipine al (Subtract)',
  BI: 'B yazmacına veri yolundan yükle (B In)',
  OI: 'Çıkış yazmacına veri yolundan yükle (Output In)',
  CE: 'Program sayacını bir artır (Counter Enable)',
  CO: 'Program sayacını veri yoluna çıkar (Counter Out)',
  J: 'Veri yolundaki değeri program sayacına yükle (Jump)',
  FI: 'Bayrak (taşma/sıfır) yazmacını güncelle (Flags In)',
};

export interface Instr { op: number; mnemonic: string; tr: string; usesArg: boolean }
export const INSTRUCTIONS: Instr[] = [
  { op: 0b0000, mnemonic: 'NOP', tr: 'İşlem yapma', usesArg: false },
  { op: 0b0001, mnemonic: 'LDA', tr: 'Adresteki değeri A yazmacına yükle', usesArg: true },
  { op: 0b0010, mnemonic: 'ADD', tr: 'Adresteki değeri A’ya ekle', usesArg: true },
  { op: 0b0011, mnemonic: 'SUB', tr: 'Adresteki değeri A’dan çıkar', usesArg: true },
  { op: 0b0100, mnemonic: 'STA', tr: 'A yazmacını adrese kaydet', usesArg: true },
  { op: 0b0101, mnemonic: 'LDI', tr: '4-bit sabit değeri A’ya yükle', usesArg: true },
  { op: 0b0110, mnemonic: 'JMP', tr: 'Koşulsuz atla', usesArg: true },
  { op: 0b0111, mnemonic: 'JC', tr: 'Taşma bayrağı 1 ise atla', usesArg: true },
  { op: 0b1000, mnemonic: 'JZ', tr: 'Sıfır bayrağı 1 ise atla', usesArg: true },
  { op: 0b1110, mnemonic: 'OUT', tr: 'A yazmacını çıkış göstergesine yaz', usesArg: false },
  { op: 0b1111, mnemonic: 'HLT', tr: 'Saati durdur', usesArg: false },
];

const FETCH: Signal[][] = [['CO', 'MI'], ['RO', 'II', 'CE']];

/** Bir komutun T2–T4 adımlarındaki kontrol sinyalleri. */
export function microcode(op: number, cf: boolean, zf: boolean): Signal[][] {
  switch (op) {
    case 0b0001: return [['IO', 'MI'], ['RO', 'AI'], []];
    case 0b0010: return [['IO', 'MI'], ['RO', 'BI'], ['EO', 'AI', 'FI']];
    case 0b0011: return [['IO', 'MI'], ['RO', 'BI'], ['EO', 'AI', 'SU', 'FI']];
    case 0b0100: return [['IO', 'MI'], ['AO', 'RI'], []];
    case 0b0101: return [['IO', 'AI'], [], []];
    case 0b0110: return [['IO', 'J'], [], []];
    case 0b0111: return [cf ? ['IO', 'J'] : [], [], []];
    case 0b1000: return [zf ? ['IO', 'J'] : [], [], []];
    case 0b1110: return [['AO', 'OI'], [], []];
    case 0b1111: return [['HLT'], [], []];
    default: return [[], [], []];
  }
}

export function controlFor(op: number, step: number, cf: boolean, zf: boolean): Signal[] {
  return step < 2 ? FETCH[step] : microcode(op, cf, zf)[step - 2];
}

export interface CpuState {
  pc: number; mar: number; ir: number; a: number; b: number; out: number | null;
  cf: boolean; zf: boolean; step: number; halted: boolean; bus: number | null;
  ram: number[]; lastSignals: Signal[]; cycles: number; lastStep: number | null;
}

export function alu(a: number, b: number, sub: boolean) {
  const bb = sub ? (~b & 0xff) : b;
  const raw = a + bb + (sub ? 1 : 0);
  return { value: raw & 0xff, carry: raw > 0xff };
}

export function initCpu(ram: number[]): CpuState {
  return { pc: 0, mar: 0, ir: 0, a: 0, b: 0, out: null, cf: false, zf: false, step: 0, halted: false, bus: null, ram: [...ram], lastSignals: [], cycles: 0, lastStep: null };
}

/** Tek bir saat çevrimi (bir mikro adım). */
export function tick(s: CpuState): CpuState {
  if (s.halted) return s;
  const sig = controlFor(s.ir >> 4, s.step, s.cf, s.zf);
  const has = (x: Signal) => sig.includes(x);
  const sum = alu(s.a, s.b, has('SU'));
  let bus: number | null = null;
  if (has('CO')) bus = s.pc;
  if (has('RO')) bus = s.ram[s.mar];
  if (has('IO')) bus = s.ir & 0x0f;
  if (has('AO')) bus = s.a;
  if (has('EO')) bus = sum.value;
  const v = bus ?? 0;
  const n: CpuState = { ...s, ram: [...s.ram], bus, lastSignals: sig, cycles: s.cycles + 1, lastStep: s.step };
  if (has('MI')) n.mar = v & 0x0f;
  if (has('RI')) n.ram[s.mar] = v;
  if (has('II')) n.ir = v;
  if (has('AI')) n.a = v;
  if (has('BI')) n.b = v;
  if (has('OI')) n.out = v;
  if (has('CE')) n.pc = (s.pc + 1) & 0x0f;
  if (has('J')) n.pc = v & 0x0f;
  if (has('FI')) { n.cf = sum.carry; n.zf = sum.value === 0; }
  if (has('HLT')) n.halted = true;
  n.step = s.step >= 4 ? 0 : s.step + 1;
  return n;
}

export const enc = (mn: string, arg = 0) => {
  const i = INSTRUCTIONS.find((x) => x.mnemonic === mn)!;
  return ((i.op << 4) | (arg & 0x0f)) & 0xff;
};

export function disasm(byte: number) {
  const i = INSTRUCTIONS.find((x) => x.op === byte >> 4);
  if (!i) return '—';
  return i.usesArg ? `${i.mnemonic} ${byte & 0x0f}` : i.mnemonic;
}

const pad = (arr: number[]) => [...arr, ...Array(16 - arr.length).fill(0)];

export const samplePrograms = [
  {
    id: 'add',
    title: '28 + 14 toplaması',
    text: 'RAM’in 14. ve 15. adreslerindeki iki sayıyı toplar, sonucu çıkışa yazar ve durur.',
    ram: (() => { const m = pad([enc('LDA', 14), enc('ADD', 15), enc('OUT'), enc('HLT')]); m[14] = 28; m[15] = 14; return m; })(),
    dataAddrs: [14, 15],
  },
  {
    id: 'sub',
    title: '30 − 12 çıkarması',
    text: 'İkiye tümleyen yöntemiyle çıkarma yapar: A + (¬B) + 1.',
    ram: (() => { const m = pad([enc('LDA', 14), enc('SUB', 15), enc('OUT'), enc('HLT')]); m[14] = 30; m[15] = 12; return m; })(),
    dataAddrs: [14, 15],
  },
  {
    id: 'count',
    title: '3’er artan sayaç (döngü)',
    text: 'A yazmacına sürekli 3 ekleyip çıkışa yazar; JMP ile döngü kurar (durmaz).',
    ram: pad([enc('LDI', 3), enc('STA', 15), enc('LDI', 0), enc('ADD', 15), enc('OUT'), enc('JMP', 3)]),
    dataAddrs: [15],
  },
];

export const bin = (n: number, w = 8) => (n >>> 0).toString(2).padStart(w, '0').slice(-w);
export const hex = (n: number, w = 2) => n.toString(16).toUpperCase().padStart(w, '0');
