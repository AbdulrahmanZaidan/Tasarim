import { useEffect, useState } from 'react';

/** localStorage ile kalıcı durum. Depolama kullanılamazsa bellek içinde çalışır. */
export function useLocalState<T>(key: string, initial: T) {
  const [v, setV] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? { ...initial, ...JSON.parse(raw) } : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* depolama devre dışı */ }
  }, [key, v]);
  return [v, setV] as const;
}
