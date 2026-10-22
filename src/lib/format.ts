const dateFmt = new Intl.DateTimeFormat('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' });
const dateShort = new Intl.DateTimeFormat('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric' });
const dateTimeFmt = new Intl.DateTimeFormat('tr-TR', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });

/** "2026-10-22" gibi tarih dizgelerini yerel saat dilimi kaymasından etkilenmeden biçimlendirir. */
function parse(d: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? new Date(`${d}T12:00:00`) : new Date(d);
}
export const fmtDate = (d?: string | null) => (d ? dateFmt.format(parse(d)) : '—');
export const fmtDateShort = (d?: string | null) => (d ? dateShort.format(parse(d)) : '—');
export const fmtDateTime = (d?: string | null) => (d ? dateTimeFmt.format(new Date(d)) : '—');

export function fmtRelative(d: string) {
  const diff = (Date.now() - new Date(d).getTime()) / 1000;
  if (diff < 60) return 'az önce';
  if (diff < 3600) return `${Math.floor(diff / 60)} dk önce`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} sa önce`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} gün önce`;
  return fmtDateShort(d);
}

const moneyCache = new Map<string, Intl.NumberFormat>();
export function fmtMoney(n: number, currency = 'TRY', digits = 2) {
  const k = `${currency}:${digits}`;
  let f = moneyCache.get(k);
  if (!f) {
    try {
      f = new Intl.NumberFormat('tr-TR', { style: 'currency', currency, minimumFractionDigits: digits, maximumFractionDigits: digits });
    } catch {
      f = new Intl.NumberFormat('tr-TR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    }
    moneyCache.set(k, f);
  }
  return f.format(n);
}
export function fmtMoneyRange(min: number, max: number, currency: string, digits = 2) {
  return Math.abs(min - max) < 0.005 ? fmtMoney(min, currency, digits) : `${fmtMoney(min, currency, digits)} – ${fmtMoney(max, currency, digits)}`;
}

export function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toLocaleString('tr-TR', { maximumFractionDigits: 1 })} KB`;
  return `${(n / 1024 / 1024).toLocaleString('tr-TR', { maximumFractionDigits: 1 })} MB`;
}

export const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/** Türkçe karakterleri koruyarak arama için normalleştirme */
export const norm = (s: string) => s.toLocaleLowerCase('tr-TR').normalize('NFC');
