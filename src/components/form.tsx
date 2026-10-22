/** Erişilebilir form alanları ve basit, bağımlılıksız doğrulama. */
import { useEffect, useId, useState, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react';
import { useBlocker } from 'react-router-dom';
import { useConfirm } from './feedback';

export function Field({ label, error, hint, required, children, className = '', id }: {
  label: ReactNode; error?: string | null; hint?: ReactNode; required?: boolean; children: (id: string, describedBy?: string) => ReactNode; className?: string; id?: string;
}) {
  const auto = useId();
  const fid = id ?? auto;
  const hintId = hint ? `${fid}-hint` : undefined;
  const errId = error ? `${fid}-err` : undefined;
  return (
    <div className={className}>
      <label htmlFor={fid} className="mb-1 block text-[13px] font-medium text-ink-2">
        {label}{required && <span className="text-brand" aria-hidden> *</span>}
      </label>
      {children(fid, [hintId, errId].filter(Boolean).join(' ') || undefined)}
      {hint && !error && <p id={hintId} className="mt-1 text-[12px] text-ink-3">{hint}</p>}
      {error && <p id={errId} className="mt-1 text-[12px] font-medium text-red-700">{error}</p>}
    </div>
  );
}

type Base = { label: ReactNode; error?: string | null; hint?: ReactNode; required?: boolean; className?: string };

export function TextInput({ label, error, hint, required, className, ...rest }: Base & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <Field label={label} error={error} hint={hint} required={required} className={className}>
      {(id, d) => <input id={id} aria-describedby={d} aria-invalid={!!error} required={required} className={`input ${error ? 'border-red-400' : ''}`} {...rest} />}
    </Field>
  );
}
export function TextArea({ label, error, hint, required, className, ...rest }: Base & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <Field label={label} error={error} hint={hint} required={required} className={className}>
      {(id, d) => <textarea id={id} aria-describedby={d} aria-invalid={!!error} required={required} rows={rest.rows ?? 3} className={`input resize-y ${error ? 'border-red-400' : ''}`} {...rest} />}
    </Field>
  );
}
export function Select({ label, error, hint, required, className, options, placeholder, ...rest }: Base & SelectHTMLAttributes<HTMLSelectElement> & {
  options: { value: string; label: string }[]; placeholder?: string;
}) {
  return (
    <Field label={label} error={error} hint={hint} required={required} className={className}>
      {(id, d) => (
        <select id={id} aria-describedby={d} aria-invalid={!!error} required={required} className={`input ${error ? 'border-red-400' : ''}`} {...rest}>
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      )}
    </Field>
  );
}
export function Checkbox({ label, hint, checked, onChange, disabled }: { label: ReactNode; hint?: ReactNode; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  const id = useId();
  return (
    <div className="flex items-start gap-2.5">
      <input id={id} type="checkbox" className="mt-0.5 h-4 w-4 accent-[#9E1B32]" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <label htmlFor={id} className="text-[14px] text-ink-2">{label}{hint && <span className="block text-[12px] text-ink-3">{hint}</span>}</label>
    </div>
  );
}

/* ---------------- Doğrulama ---------------- */
export type Rule<T> = (value: T[keyof T], all: T) => string | null;
export type Rules<T> = Partial<Record<keyof T, Rule<T>[]>>;

export const v = {
  required: <T,>(msg = 'Bu alan zorunludur.'): Rule<T> => (x) => (x === null || x === undefined || String(x).trim() === '' ? msg : null),
  max: <T,>(n: number): Rule<T> => (x) => (x && String(x).length > n ? `En fazla ${n} karakter olabilir.` : null),
  min: <T,>(n: number): Rule<T> => (x) => (x && String(x).trim().length < n ? `En az ${n} karakter olmalıdır.` : null),
  number: <T,>(opts: { min?: number; max?: number; integer?: boolean } = {}): Rule<T> => (x) => {
    if (x === null || x === undefined || x === '') return null;
    // Türkçe ondalık virgülü kabul edilir (18,50)
    const n = Number(String(x).trim().replace(/\s/g, '').replace(',', '.'));
    if (!Number.isFinite(n)) return 'Geçerli bir sayı girin.';
    if (opts.integer && !Number.isInteger(n)) return 'Tam sayı girin.';
    if (opts.min !== undefined && n < opts.min) return `En az ${opts.min} olmalıdır.`;
    if (opts.max !== undefined && n > opts.max) return `En fazla ${opts.max} olabilir.`;
    return null;
  },
  url: <T,>(): Rule<T> => (x) => (x && !/^https?:\/\/[^\s]+$/i.test(String(x)) ? 'http:// veya https:// ile başlayan geçerli bir adres girin.' : null),
  pattern: <T,>(re: RegExp, msg: string): Rule<T> => (x) => (x && !re.test(String(x)) ? msg : null),
};

export function validate<T>(values: T, rules: Rules<T>): Partial<Record<keyof T, string>> {
  const errors: Partial<Record<keyof T, string>> = {};
  for (const k of Object.keys(rules) as (keyof T)[]) {
    for (const rule of rules[k] ?? []) {
      const e = rule(values[k], values);
      if (e) { errors[k] = e; break; }
    }
  }
  return errors;
}

/** Form durumu: değerler, hatalar, "kaydedilmemiş değişiklik" bilgisi */
export function useForm<T extends Record<string, unknown>>(initial: T, rules: Rules<T> = {}) {
  const [values, setValues] = useState<T>(initial);
  const [initialValues, setInitial] = useState<T>(initial);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});
  const dirty = JSON.stringify(values) !== JSON.stringify(initialValues);
  return {
    values, errors, dirty,
    set: <K extends keyof T>(k: K, val: T[K]) => { setValues((s) => ({ ...s, [k]: val })); setErrors((e) => ({ ...e, [k]: undefined })); },
    reset: (next: T) => { setValues(next); setInitial(next); setErrors({}); },
    check: () => { const e = validate(values, rules); setErrors(e); return Object.keys(e).length === 0; },
    setErrors,
    markSaved: () => setInitial(values),
  };
}

/**
 * Kaydedilmemiş değişiklik uyarısı: uygulama içi gezinmede onay sorar, sekme kapatılırken tarayıcı uyarısı gösterir.
 */
export function useUnsavedChanges(dirty: boolean) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty && currentLocation.pathname !== nextLocation.pathname);
  const confirm = useConfirm();
  useEffect(() => {
    if (blocker.state !== 'blocked') return;
    void confirm({
      title: 'Kaydedilmemiş değişiklikler',
      message: 'Bu sayfada kaydetmediğiniz değişiklikler var. Sayfadan ayrılırsanız bu değişiklikler kaybolacak.',
      confirmLabel: 'Değişiklikleri at ve ayrıl', tone: 'danger',
    }).then((ok) => (ok ? blocker.proceed() : blocker.reset()));
  }, [blocker, confirm]);
  useEffect(() => {
    if (!dirty) return;
    const h = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', h);
    return () => window.removeEventListener('beforeunload', h);
  }, [dirty]);
}

/** Boş dizgeyi null'a çevirir (isteğe bağlı metin alanları için) */
export const nn = (s: string | null | undefined) => (s === undefined || s === null || s.trim() === '' ? null : s.trim());
export const numOrNull = (s: string | number | null | undefined) => (s === '' || s === null || s === undefined ? null : Number(s));
