/**
 * Küçük, bağımlılıksız sorgu önbelleği.
 * - Aynı anahtar için eş zamanlı istekleri tekilleştirir (gereksiz tekrar istek olmaz).
 * - `invalidate` ile değişiklikten sonra ilgili sorgular yeniden çekilir.
 * - Pencere yeniden odaklandığında eskimiş (stale) veriler sessizce tazelenir.
 */
import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react';
import { toAppError, type AppError } from './errors';

interface Entry<T = unknown> {
  data?: T;
  error?: AppError;
  promise?: Promise<void>;
  updatedAt: number;
  stale: boolean;
  fetcher?: () => Promise<T>;
  subs: Set<() => void>;
  version: number;
}

const store = new Map<string, Entry>();
const DEFAULT_STALE_MS = 60_000;

function entry(key: string): Entry {
  let e = store.get(key);
  if (!e) {
    e = { updatedAt: 0, stale: true, subs: new Set(), version: 0 };
    store.set(key, e);
  }
  return e;
}

function notify(e: Entry) {
  e.version++;
  e.subs.forEach((s) => s());
}

function run<T>(key: string, fetcher: () => Promise<T>): Promise<void> {
  const e = entry(key) as Entry<T>;
  if (e.promise) return e.promise;
  e.fetcher = fetcher;
  e.promise = fetcher()
    .then((data) => { e.data = data; e.error = undefined; e.updatedAt = Date.now(); e.stale = false; })
    .catch((err) => { e.error = toAppError(err); e.stale = false; })
    .finally(() => { e.promise = undefined; notify(e); });
  notify(e);
  return e.promise;
}

/** Önbelleği geçersiz kılar. Ön ek eşleşmesi: invalidate('materials') → 'materials', 'materials:public' … */
export function invalidate(...prefixes: string[]) {
  for (const [key, e] of store) {
    if (prefixes.some((p) => key === p || key.startsWith(p + ':'))) {
      e.stale = true;
      if (e.subs.size && e.fetcher) void run(key, e.fetcher);
    }
  }
}

export function getCached<T>(key: string): T | undefined {
  return store.get(key)?.data as T | undefined;
}

export interface QueryResult<T> {
  data: T | undefined;
  error: AppError | undefined;
  loading: boolean;
  refetch: () => Promise<void>;
}

export function useQuery<T>(key: string | null, fetcher: () => Promise<T>, opts: { staleMs?: number } = {}): QueryResult<T> {
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const staleMs = opts.staleMs ?? DEFAULT_STALE_MS;

  const subscribe = useCallback((cb: () => void) => {
    if (!key) return () => {};
    const e = entry(key);
    e.subs.add(cb);
    return () => { e.subs.delete(cb); };
  }, [key]);
  const version = useSyncExternalStore(subscribe, () => (key ? entry(key).version : -1), () => -1);

  useEffect(() => {
    if (!key) return;
    const e = entry(key);
    if (e.stale || Date.now() - e.updatedAt > staleMs) void run(key, () => fetcherRef.current());
  }, [key, staleMs]);

  useEffect(() => {
    if (!key) return;
    const onFocus = () => {
      const e = entry(key);
      if (document.visibilityState === 'visible' && Date.now() - e.updatedAt > staleMs) void run(key, () => fetcherRef.current());
    };
    document.addEventListener('visibilitychange', onFocus);
    return () => document.removeEventListener('visibilitychange', onFocus);
  }, [key, staleMs]);

  void version;
  const e = key ? entry(key) : undefined;
  return {
    data: e?.data as T | undefined,
    error: e?.error,
    loading: Boolean(key) && (!!e?.promise || (e?.data === undefined && !e?.error)),
    refetch: () => (key ? run(key, () => fetcherRef.current()) : Promise.resolve()),
  };
}

/** Testler için */
export function __resetQueryCache() {
  store.clear();
}
