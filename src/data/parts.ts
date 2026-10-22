/**
 * BEN EATER 8-BIT BREADBOARD BİLGİSAYAR — TAM MALZEME LİSTESİ
 *
 * Fiyatlar, kaynak sayfada "Approx. cost" olarak verilen TARİHSEL / REFERANS
 * USD değerleridir; güncel Türkiye piyasa fiyatı değildir.
 * `statedTotal` kaynakta yazan satır toplamıdır ve değiştirilmeden korunur.
 * Kaynakta yazan toplam ile adet × birim fiyat çarpımı farklıysa bu fark
 * sayfada ayrıca gösterilir.
 */

export type Category =
  | 'Breadboard ve bağlantı malzemeleri'
  | 'Dirençler'
  | 'Kondansatörler'
  | 'Zamanlayıcı entegreler'
  | 'Mantık kapıları'
  | 'Yazmaç ve sayaç entegreleri'
  | 'Bellek ve EEPROM'
  | 'Anahtarlar ve kontrol elemanları'
  | 'LED ve göstergeler';

export const categories: Category[] = [
  'Breadboard ve bağlantı malzemeleri',
  'Dirençler',
  'Kondansatörler',
  'Zamanlayıcı entegreler',
  'Mantık kapıları',
  'Yazmaç ve sayaç entegreleri',
  'Bellek ve EEPROM',
  'Anahtarlar ve kontrol elemanları',
  'LED ve göstergeler',
];

export interface Range { min: number; max: number }

export interface Part {
  id: string;
  /** Kaynaktaki özgün İngilizce tanım */
  source: string;
  /** Türkçe açıklama */
  name: string;
  category: Category;
  qty: number;
  unit: Range;
  statedTotal: Range;
  note?: string;
}

const r = (min: number, max = min): Range => ({ min, max });

export const parts: Part[] = [
  { id: 'breadboard', source: 'Breadboard', name: 'Breadboard (delikli deney tahtası)', category: 'Breadboard ve bağlantı malzemeleri', qty: 14, unit: r(4, 9), statedTotal: r(56, 126), note: 'Kaynak, en iyi kalite olarak BusBoard BB830 modelini önermektedir.' },
  { id: 'wire', source: '22 AWG Solid Tinned-Copper Hook-Up Wire', name: '22 AWG tek damarlı kalaylı bakır bağlantı teli (set)', category: 'Breadboard ve bağlantı malzemeleri', qty: 1, unit: r(16), statedTotal: r(16) },

  { id: 'r1k', source: '1kΩ resistor', name: '1 kΩ direnç', category: 'Dirençler', qty: 10, unit: r(0.06), statedTotal: r(0.6) },
  { id: 'r10k', source: '10kΩ resistor', name: '10 kΩ direnç', category: 'Dirençler', qty: 9, unit: r(0.06), statedTotal: r(0.6) },
  { id: 'r100k', source: '100kΩ resistor', name: '100 kΩ direnç', category: 'Dirençler', qty: 1, unit: r(0.06), statedTotal: r(0.6) },
  { id: 'r470', source: '470Ω resistor', name: '470 Ω direnç', category: 'Dirençler', qty: 24, unit: r(0.06), statedTotal: r(1.8) },
  { id: 'r1m', source: '1MΩ resistor', name: '1 MΩ direnç', category: 'Dirençler', qty: 1, unit: r(0.06), statedTotal: r(0.6) },
  { id: 'pot1m', source: '1MΩ potentiometer', name: '1 MΩ potansiyometre', category: 'Dirençler', qty: 1, unit: r(1.39), statedTotal: r(1.39) },

  { id: 'c001', source: '0.01µF capacitor', name: '0,01 µF kondansatör', category: 'Kondansatörler', qty: 6, unit: r(0.12), statedTotal: r(1.2) },
  { id: 'c01', source: '0.1µF capacitor', name: '0,1 µF kondansatör', category: 'Kondansatörler', qty: 16, unit: r(0.15), statedTotal: r(3) },
  { id: 'c1', source: '1µF capacitor', name: '1 µF kondansatör', category: 'Kondansatörler', qty: 1, unit: r(0.15), statedTotal: r(0.15) },

  { id: 'ne555', source: '555 timer IC', name: '555 zamanlayıcı entegresi', category: 'Zamanlayıcı entegreler', qty: 4, unit: r(0.35), statedTotal: r(1.4) },

  { id: 'ls00', source: '74LS00 (Quad NAND gate)', name: '74LS00 — dörtlü NAND kapısı', category: 'Mantık kapıları', qty: 2, unit: r(0.79), statedTotal: r(1.58) },
  { id: 'ls02', source: '74LS02 (Quad NOR gate)', name: '74LS02 — dörtlü NOR kapısı', category: 'Mantık kapıları', qty: 1, unit: r(0.55), statedTotal: r(0.55) },
  { id: 'ls04', source: '74LS04 (Hex inverter)', name: '74LS04 — altılı tersleyici (NOT)', category: 'Mantık kapıları', qty: 5, unit: r(0.59), statedTotal: r(2.95) },
  { id: 'ls08', source: '74LS08 (Quad AND gate)', name: '74LS08 — dörtlü AND kapısı', category: 'Mantık kapıları', qty: 3, unit: r(0.69), statedTotal: r(2.07) },
  { id: 'ls32', source: '74LS32 (Quad OR gate)', name: '74LS32 — dörtlü OR kapısı', category: 'Mantık kapıları', qty: 1, unit: r(0.49), statedTotal: r(0.49) },
  { id: 'ls107', source: '74LS107 (Dual JK flip-flop)', name: '74LS107 — çift JK flip-flop', category: 'Yazmaç ve sayaç entegreleri', qty: 1, unit: r(1.75), statedTotal: r(1.75), note: 'Videolarda kullanılan 74LS76 zor bulunur; 74LS107 işlevsel olarak eşdeğerdir ancak bacak dizilimi (pinout) farklıdır.' },
  { id: 'ls86', source: '74LS86 (Quad XOR gate)', name: '74LS86 — dörtlü XOR kapısı', category: 'Mantık kapıları', qty: 2, unit: r(0.55), statedTotal: r(1.1) },
  { id: 'ls138', source: '74LS138 (3-to-8 line decoder)', name: '74LS138 — 3’ten 8’e kod çözücü', category: 'Mantık kapıları', qty: 1, unit: r(0.69), statedTotal: r(0.69) },
  { id: 'ls139', source: '74LS139 (Dual 2-line to 4-line decoder)', name: '74LS139 — çift 2’den 4’e kod çözücü', category: 'Mantık kapıları', qty: 1, unit: r(0.69), statedTotal: r(0.69) },
  { id: 'ls157', source: '74LS157 (Quad 2-to-1 line data selector)', name: '74LS157 — dörtlü 2’den 1’e veri seçici (multiplexer)', category: 'Mantık kapıları', qty: 4, unit: r(0.69), statedTotal: r(2.76) },
  { id: 'ls161', source: '74LS161 (4-bit synchronous binary counter)', name: '74LS161 — 4-bit senkron ikili sayıcı', category: 'Yazmaç ve sayaç entegreleri', qty: 2, unit: r(0.79), statedTotal: r(1.58) },
  { id: 'ls173', source: '74LS173 (4-bit D-type register)', name: '74LS173 — 4-bit D tipi yazmaç', category: 'Yazmaç ve sayaç entegreleri', qty: 8, unit: r(1.39), statedTotal: r(11.12) },
  { id: 'ls189', source: '74189 (64-bit random access memory)', name: '74189 — 64-bit (16 × 4) RAM', category: 'Bellek ve EEPROM', qty: 2, unit: r(4.95), statedTotal: r(9.9) },
  { id: 'ls245', source: '74LS245 (Octal bus transceiver)', name: '74LS245 — sekizli veri yolu alıcı-vericisi', category: 'Mantık kapıları', qty: 6, unit: r(0.79), statedTotal: r(4.74) },
  { id: 'ls273', source: '74LS273 (Octal D flip-flop)', name: '74LS273 — sekizli D flip-flop', category: 'Yazmaç ve sayaç entegreleri', qty: 1, unit: r(0.75), statedTotal: r(0.75) },
  { id: 'ls283', source: '74LS283 (4-bit binary full adder)', name: '74LS283 — 4-bit ikili tam toplayıcı', category: 'Mantık kapıları', qty: 2, unit: r(1.49), statedTotal: r(2.98) },
  { id: 'eeprom', source: '28C16 EEPROM', name: '28C16 EEPROM (2K × 8)', category: 'Bellek ve EEPROM', qty: 3, unit: r(3.95), statedTotal: r(11.85) },

  { id: 'toggle', source: 'Double-throw toggle switch', name: 'Çift konumlu (double-throw) toggle anahtar', category: 'Anahtarlar ve kontrol elemanları', qty: 3, unit: r(0.99), statedTotal: r(2.97) },
  { id: 'tact', source: 'Momentary 6mm tact switch', name: '6 mm anlık (momentary) buton', category: 'Anahtarlar ve kontrol elemanları', qty: 3, unit: r(0.35), statedTotal: r(1.05) },
  { id: 'dip8', source: '8-position DIP switch', name: '8 konumlu DIP anahtar', category: 'Anahtarlar ve kontrol elemanları', qty: 1, unit: r(0.79), statedTotal: r(0.79) },
  { id: 'dip4', source: '4-position DIP switch', name: '4 konumlu DIP anahtar', category: 'Anahtarlar ve kontrol elemanları', qty: 1, unit: r(0.89), statedTotal: r(0.89) },

  { id: 'led-r', source: 'Red LED', name: 'Kırmızı LED', category: 'LED ve göstergeler', qty: 44, unit: r(0.12), statedTotal: r(6) },
  { id: 'led-y', source: 'Yellow LED', name: 'Sarı LED', category: 'LED ve göstergeler', qty: 8, unit: r(0.09), statedTotal: r(0.9) },
  { id: 'led-g', source: 'Green LED', name: 'Yeşil LED', category: 'LED ve göstergeler', qty: 12, unit: r(0.1), statedTotal: r(2) },
  { id: 'led-b', source: 'Blue LED', name: 'Mavi LED', category: 'LED ve göstergeler', qty: 21, unit: r(0.59), statedTotal: r(12.39) },
  { id: 'seg7', source: 'Common cathode 7-segment display', name: 'Ortak katotlu 7 segment gösterge', category: 'LED ve göstergeler', qty: 4, unit: r(1.09), statedTotal: r(4.36) },
];

/** Kaynakta fiyatı verilmeyen, EEPROM programlayıcı için ek malzemeler. */
export const programmerParts = [
  { id: 'nano', name: 'Arduino Nano', qty: 1, note: 'Kaynakta fiyat belirtilmemiştir.' },
  { id: 'hc595', name: '74HC595 — 8-bit seri giriş / paralel çıkış kaydırmalı yazmaç', qty: 2, note: 'Kaynakta fiyat belirtilmemiştir.' },
];

export const sourceEstimate = { min: 250, max: 300, note: 'Kargo ücretine bağlı olarak yaklaşık toplam (kaynak beyanı)' };

/* ---------------- Hesaplama yardımcıları ---------------- */

export const round2 = (n: number) => Math.round(n * 100) / 100;

export function calcTotal(p: Pick<Part, 'qty' | 'unit'>): Range {
  return { min: round2(p.qty * p.unit.min), max: round2(p.qty * p.unit.max) };
}

export function hasMismatch(p: Part) {
  const c = calcTotal(p);
  return Math.abs(c.min - p.statedTotal.min) > 0.004 || Math.abs(c.max - p.statedTotal.max) > 0.004;
}

export function sumRanges(rs: Range[]): Range {
  return rs.reduce((a, b) => ({ min: round2(a.min + b.min), max: round2(a.max + b.max) }), { min: 0, max: 0 });
}
