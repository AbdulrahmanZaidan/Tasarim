import { WifiOff } from 'lucide-react';
import type { DataState } from '../data/public';

/** Veritabanına ulaşılamadığında yedek verinin gösterildiğini açıkça belirtir. */
export default function DataNotice({ state, className = '' }: { state: Pick<DataState<unknown>, 'error' | 'fallback' | 'refetch'>; className?: string }) {
  if (!state.error) return null;
  return (
    <div role="status" className={`flex flex-col gap-2 rounded-[10px] border border-amber-300 bg-amber-50/70 px-4 py-3 text-[13.5px] text-ink-2 sm:flex-row sm:items-center ${className}`}>
      <WifiOff size={16} className="shrink-0 text-amber-700" aria-hidden />
      <span className="flex-1">
        <b className="text-ink">Güncel veriler alınamadı.</b> {state.error.message}
        {state.fallback && ' Bu nedenle sitenin yayımlanan sürümündeki bilgiler gösteriliyor.'}
      </span>
      <button className="btn-outline py-1 text-[13px]" onClick={state.refetch}>Tekrar dene</button>
    </div>
  );
}
