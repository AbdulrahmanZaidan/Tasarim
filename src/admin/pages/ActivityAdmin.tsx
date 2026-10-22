import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import { AdminPage, SearchBox, Table, Th, Td, Pager } from '../ui';
import { useAuth } from '../../auth/AuthProvider';
import { useQuery } from '../../lib/query';
import { listActivity } from '../../services/entities';
import { useProfiles } from '../data';
import { SkeletonRows, ErrorNotice, EmptyState } from '../../components/feedback';
import { fmtDateTime } from '../../lib/format';
import { actionLabel, entityLabels } from './activityLabels';
import type { Json } from '../../lib/database.types';

const PAGE = 25;
const short = (v: Json | undefined) => (v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v));

function Details({ d }: { d: Json }) {
  const obj = (d ?? {}) as Record<string, Json>;
  const changes = obj.changes as Record<string, [Json, Json]> | undefined;
  if (changes) {
    return (
      <ul className="space-y-0.5 text-[12px]">
        {Object.entries(changes).map(([k, [a, b]]) => <li key={k}><span className="mono text-ink-3">{k}</span>: <span className="text-ink-3 line-through">{short(a)}</span> → <b className="text-ink">{short(b)}</b></li>)}
      </ul>
    );
  }
  const rest = Object.entries(obj).filter(([k]) => k !== 'snapshot');
  return rest.length ? <ul className="text-[12px]">{rest.map(([k, x]) => <li key={k}><span className="mono text-ink-3">{k}</span>: {short(x)}</li>)}</ul> : <span className="text-[12px] text-ink-3">—</span>;
}

export default function ActivityAdmin() {
  const { canEdit } = useAuth();
  const people = useProfiles();
  const [page, setPage] = useState(0);
  const [type, setType] = useState('');
  const [actor, setActor] = useState('');
  const [q, setQ] = useState('');
  const [open, setOpen] = useState<number | null>(null);
  const key = canEdit ? `activity_logs:list:${page}:${type}:${actor}:${q}` : null;
  const res = useQuery(key, () => listActivity({ page, pageSize: PAGE, entityType: type || undefined, actorId: actor || undefined, search: q.trim() || undefined }), { staleMs: 10_000 });
  if (!canEdit) return <Navigate to="/admin/dashboard" replace />;
  return (
    <AdminPage title="Etkinlik Günlüğü" description="Önemli yönetim değişiklikleri veritabanı tetikleyicileri tarafından otomatik kaydedilir; istemciler günlüğe yazamaz, kayıtları değiştiremez veya silemez.">
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchBox value={q} onChange={(x) => { setQ(x); setPage(0); }} placeholder="Kayıt adında ara" />
        <select className="input w-auto" value={type} onChange={(e) => { setType(e.target.value); setPage(0); }} aria-label="Kayıt türü"><option value="">Tüm kayıt türleri</option>{Object.entries(entityLabels).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <select className="input w-auto" value={actor} onChange={(e) => { setActor(e.target.value); setPage(0); }} aria-label="Kullanıcı"><option value="">Tüm kullanıcılar</option>{(people.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name || p.email}</option>)}</select>
      </div>
      {res.error && <ErrorNotice error={res.error} onRetry={() => void res.refetch()} />}
      {!res.data ? <SkeletonRows rows={8} /> : res.data.rows.length === 0 ? <EmptyState title="Kayıt yok">Seçilen ölçütlere uyan etkinlik bulunamadı.</EmptyState> : (
        <>
          <Table minWidth={820}>
            <thead><tr><Th>Zaman</Th><Th>Eylem</Th><Th>Kayıt</Th><Th>Kullanıcı</Th><Th>Ayrıntı</Th></tr></thead>
            <tbody>{res.data.rows.map((a) => (
              <tr key={a.id} className="hover:bg-brand-mist/40">
                <Td className="whitespace-nowrap text-[12.5px]">{fmtDateTime(a.created_at)}</Td>
                <Td><b className="text-[13px]">{actionLabel(a.action)}</b></Td>
                <Td className="text-[13px]">{a.entity_label ?? '—'}<div className="text-[11.5px] text-ink-3">{entityLabels[a.entity_type] ?? a.entity_type}</div></Td>
                <Td className="text-[12.5px]">{a.actor_email ?? 'Sistem (SQL / otomatik)'}</Td>
                <Td>
                  <button className="inline-flex items-center gap-1 text-[12.5px] text-brand" onClick={() => setOpen(open === a.id ? null : a.id)} aria-expanded={open === a.id}>
                    Göster <ChevronDown size={13} className={open === a.id ? 'rotate-180' : ''} aria-hidden />
                  </button>
                  {open === a.id && <div className="mt-1"><Details d={a.details} /></div>}
                </Td>
              </tr>
            ))}</tbody>
          </Table>
          <Pager page={page} pageSize={PAGE} total={res.data.total} onPage={setPage} />
        </>
      )}
    </AdminPage>
  );
}
