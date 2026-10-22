import { useEffect, useState } from 'react';
import { Plus, Trash2, Save, ShieldCheck, UserPlus } from 'lucide-react';
import { AdminPage, ReadOnlyNotice, Table, Th, Td } from '../ui';
import { useSettings, usePhases, useProfiles } from '../data';
import { useAuth } from '../../auth/AuthProvider';
import { useToast, SkeletonRows, ErrorNotice } from '../../components/feedback';
import { Select, TextArea, TextInput, Checkbox, useForm, v, nn, useUnsavedChanges } from '../../components/form';
import { Callout, Badge } from '../../components/ui';
import { updateSettings, profiles as profileSvc, type Settings } from '../../services/entities';
import { roleHints, roleLabels, options, type AppRole } from '../../lib/labels';
import { fmtDate, todayISO } from '../../lib/format';
import { errorMessage } from '../../lib/errors';

type Vals = {
  project_title: string; project_subtitle: string; project_description: string; university: string; course: string; supervisor: string;
  academic_year: string; github_url: string; project_status: string; current_phase_id: string; default_currency: string;
  usd_try_rate: string; usd_try_rate_date: string; tasarim_ii_active: boolean; team: { name: string; student_id: string }[];
};
const toVals = (s: Settings): Vals => ({
  project_title: s.project_title, project_subtitle: s.project_subtitle ?? '', project_description: s.project_description ?? '', university: s.university ?? '',
  course: s.course ?? '', supervisor: s.supervisor ?? '', academic_year: s.academic_year ?? '', github_url: s.github_url ?? '', project_status: s.project_status ?? '',
  current_phase_id: s.current_phase_id ?? '', default_currency: s.default_currency, usd_try_rate: s.usd_try_rate === null ? '' : String(s.usd_try_rate),
  usd_try_rate_date: s.usd_try_rate_date ?? '', tasarim_ii_active: s.tasarim_ii_active,
  team: Array.isArray(s.team_members) ? (s.team_members as { name: string; student_id: string }[]).map((m) => ({ name: m.name ?? '', student_id: m.student_id ?? '' })) : [],
});

function SettingsForm({ s }: { s: Settings }) {
  const { isAdmin } = useAuth();
  const toast = useToast();
  const ph = usePhases();
  const [busy, setBusy] = useState(false);
  const [base, setBase] = useState(s);
  const f = useForm<Vals>(toVals(s), {
    project_title: [v.required(), v.max(160)], github_url: [v.pattern(/^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/, 'https://github.com/kullanici/depo biçiminde olmalı.')],
    usd_try_rate: [v.number({ min: 0.0001 })],
    usd_try_rate_date: [(x, all) => (all.usd_try_rate && !x ? 'Kur girildiğinde tarih zorunludur.' : null), (x) => (x && String(x) > todayISO() ? 'Gelecek tarih olamaz.' : null)],
    project_description: [v.max(4000)],
    team: [(x) => ((x as Vals['team']).some((m) => !m.name.trim()) ? 'Her ekip üyesinin adı girilmelidir.' : null)],
  });
  useUnsavedChanges(f.dirty);
  useEffect(() => { if (s.updated_at !== base.updated_at && !f.dirty) { setBase(s); f.reset(toVals(s)); } }, [s]); // eslint-disable-line react-hooks/exhaustive-deps
  const x = f.values;
  const save = async () => {
    if (!f.check()) { toast.error('Lütfen işaretli alanları düzeltin.'); return; }
    setBusy(true);
    try {
      const updated = await updateSettings({
        project_title: x.project_title.trim(), project_subtitle: nn(x.project_subtitle), project_description: nn(x.project_description), university: nn(x.university),
        course: nn(x.course), supervisor: nn(x.supervisor), academic_year: nn(x.academic_year), github_url: nn(x.github_url), project_status: nn(x.project_status),
        current_phase_id: x.current_phase_id || null, default_currency: x.default_currency,
        usd_try_rate: x.usd_try_rate === '' ? null : Number(x.usd_try_rate.replace(',', '.')), usd_try_rate_date: x.usd_try_rate ? x.usd_try_rate_date : null,
        tasarim_ii_active: x.tasarim_ii_active, team_members: x.team.map((m) => ({ name: m.name.trim(), student_id: m.student_id.trim() })),
      }, base.updated_at);
      setBase(updated); f.reset(toVals(updated));
      toast.success('Proje ayarları kaydedildi.');
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  const dis = !isAdmin || busy;
  return (
    <section className="card p-5" aria-labelledby="ayarlar">
      <h2 id="ayarlar" className="mb-4 text-[17px] font-semibold">Proje bilgileri</h2>
      <fieldset disabled={dis} className="grid gap-4 sm:grid-cols-2">
        <TextInput label="Proje başlığı" required value={x.project_title} error={f.errors.project_title} onChange={(e) => f.set('project_title', e.target.value)} />
        <TextInput label="Alt başlık" value={x.project_subtitle} onChange={(e) => f.set('project_subtitle', e.target.value)} />
        <TextArea className="sm:col-span-2" label="Proje açıklaması" value={x.project_description} error={f.errors.project_description} onChange={(e) => f.set('project_description', e.target.value)} hint="Ana sayfadaki tanıtım paragrafı." />
        <TextInput label="Üniversite" value={x.university} onChange={(e) => f.set('university', e.target.value)} />
        <TextInput label="Ders" value={x.course} onChange={(e) => f.set('course', e.target.value)} />
        <TextInput label="Danışman" value={x.supervisor} onChange={(e) => f.set('supervisor', e.target.value)} />
        <TextInput label="Akademik yıl" value={x.academic_year} onChange={(e) => f.set('academic_year', e.target.value)} placeholder="ör. 2026–2027" />
        <TextInput label="GitHub deposu" value={x.github_url} error={f.errors.github_url} onChange={(e) => f.set('github_url', e.target.value)} />
        <TextInput label="Proje durumu (kısa metin)" value={x.project_status} onChange={(e) => f.set('project_status', e.target.value)} placeholder="ör. Hazırlık aşaması" />
        <Select label="Güncel aşama" value={x.current_phase_id} onChange={(e) => f.set('current_phase_id', e.target.value)} placeholder="— Belirtilmedi —" options={(ph.data ?? []).map((p) => ({ value: p.id, label: p.title }))} />
        <Select label="Varsayılan para birimi" value={x.default_currency} onChange={(e) => f.set('default_currency', e.target.value)} options={['TRY', 'USD', 'EUR'].map((c) => ({ value: c, label: c }))} />
      </fieldset>

      <h3 className="mb-2 mt-6 text-[15px] font-semibold">Proje ekibi</h3>
      <fieldset disabled={dis} className="space-y-2">
        {x.team.map((m, i) => (
          <div key={i} className="grid grid-cols-[1fr_160px_auto] gap-2">
            <input className="input" aria-label={`Ekip üyesi ${i + 1} adı`} value={m.name} onChange={(e) => f.set('team', x.team.map((t, j) => (j === i ? { ...t, name: e.target.value } : t)))} placeholder="Ad Soyad" />
            <input className="input mono" aria-label={`Ekip üyesi ${i + 1} öğrenci no`} value={m.student_id} onChange={(e) => f.set('team', x.team.map((t, j) => (j === i ? { ...t, student_id: e.target.value } : t)))} placeholder="Öğrenci no" />
            <button type="button" className="btn-ghost px-2 text-red-700" onClick={() => f.set('team', x.team.filter((_, j) => j !== i))} aria-label="Üyeyi kaldır"><Trash2 size={15} /></button>
          </div>
        ))}
        {f.errors.team && <p className="text-[12px] text-red-700">{f.errors.team}</p>}
        <button type="button" className="btn-ghost text-[13px]" onClick={() => f.set('team', [...x.team, { name: '', student_id: '' }])}><Plus size={14} aria-hidden /> Üye ekle</button>
      </fieldset>

      <h3 className="mb-2 mt-6 text-[15px] font-semibold">Döviz kuru</h3>
      <p className="mb-3 text-[13px] text-ink-3">Kur girildiğinde USD referans fiyatları ile TL teklifleri birleşik tahminde toplanabilir. Canlı kur kullanılmaz; kaydedilen değer tarihiyle birlikte gösterilir.</p>
      <fieldset disabled={dis} className="grid gap-4 sm:grid-cols-2">
        <TextInput label="1 USD = ? TL" inputMode="decimal" value={x.usd_try_rate} error={f.errors.usd_try_rate} onChange={(e) => f.set('usd_try_rate', e.target.value)} />
        <TextInput label="Kur tarihi" type="date" max={todayISO()} value={x.usd_try_rate_date} error={f.errors.usd_try_rate_date} onChange={(e) => f.set('usd_try_rate_date', e.target.value)} />
      </fieldset>

      <h3 className="mb-2 mt-6 text-[15px] font-semibold">Tasarım II</h3>
      <fieldset disabled={dis}>
        <Checkbox label="Tasarım II başladı" hint="İşaretlenince Tasarım II sayfası “Yakında” görünümünden çıkar. Yalnızca dönem fiilen başladığında işaretleyin." checked={x.tasarim_ii_active} onChange={(b) => f.set('tasarim_ii_active', b)} />
      </fieldset>

      <div className="mt-6 flex items-center justify-between border-t border-brand-line pt-4">
        <span className="text-[12.5px] text-ink-3">Son güncelleme: {fmtDate(base.updated_at)}</span>
        {isAdmin && <button className="btn-primary" disabled={busy || !f.dirty} onClick={() => void save()}><Save size={16} aria-hidden /> {busy ? 'Kaydediliyor…' : 'Ayarları kaydet'}</button>}
      </div>
    </section>
  );
}

function Users() {
  const { isAdmin, user, refreshProfile } = useAuth();
  const toast = useToast();
  const people = useProfiles();
  const [names, setNames] = useState<Record<string, string>>({});
  const me = people.data?.find((p) => p.id === user?.id);
  const setRole = async (id: string, role: AppRole) => {
    try { const p = people.data!.find((x) => x.id === id)!; await profileSvc.update(id, { role }, p.updated_at); toast.success('Rol güncellendi.'); if (id === user?.id) void refreshProfile(); }
    catch (e) { toast.error(errorMessage(e)); }
  };
  const saveName = async (id: string) => {
    const p = people.data!.find((x) => x.id === id)!;
    try { await profileSvc.update(id, { full_name: (names[id] ?? '').trim() || null }, p.updated_at); toast.success('Ad güncellendi.'); setNames((n) => { const c = { ...n }; delete c[id]; return c; }); void refreshProfile(); }
    catch (e) { toast.error(errorMessage(e)); }
  };
  return (
    <section className="card p-5" aria-labelledby="kullanicilar">
      <h2 id="kullanicilar" className="mb-1 flex items-center gap-2 text-[17px] font-semibold"><ShieldCheck size={18} className="text-brand" aria-hidden /> Kullanıcılar ve roller</h2>
      <p className="mb-4 text-[13px] text-ink-3">Roller veritabanında zorlanır (Row Level Security). Arayüzdeki seçimler yalnızca kolaylık içindir.</p>
      <ul className="mb-4 grid gap-2 sm:grid-cols-3 text-[12.5px]">{(Object.keys(roleLabels) as AppRole[]).map((r) => <li key={r} className="card-soft p-3"><b className="text-ink">{roleLabels[r]}</b><div className="text-ink-3">{roleHints[r]}</div></li>)}</ul>
      {people.error && <ErrorNotice error={people.error} />}
      {!people.data ? <SkeletonRows rows={2} /> : (
        <Table minWidth={620}>
          <thead><tr><Th>Ad</Th><Th>E-posta</Th><Th>Rol</Th><Th>Katılım</Th></tr></thead>
          <tbody>{people.data.map((p) => {
            const editable = p.id === user?.id || isAdmin;
            const editingName = names[p.id] !== undefined;
            return (
              <tr key={p.id}>
                <Td>{editable ? (
                  <div className="flex gap-1">
                    <input className="input py-1" aria-label="Ad soyad" value={editingName ? names[p.id] : p.full_name ?? ''} onChange={(e) => setNames((n) => ({ ...n, [p.id]: e.target.value }))} />
                    {editingName && <button className="btn-outline px-2 py-1 text-[12.5px]" onClick={() => void saveName(p.id)}>Kaydet</button>}
                  </div>) : (p.full_name ?? '—')}</Td>
                <Td className="text-[12.5px]">{p.email}{p.id === user?.id && <Badge tone="brand" dot={false}>siz</Badge>}</Td>
                <Td>{isAdmin ? (
                  <select className="input w-auto py-1" aria-label={`${p.email} rolü`} value={p.role} onChange={(e) => void setRole(p.id, e.target.value as AppRole)}>
                    {options(roleLabels).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>) : roleLabels[p.role]}</Td>
                <Td className="text-[12.5px]">{fmtDate(p.created_at)}</Td>
              </tr>
            );
          })}</tbody>
        </Table>
      )}
      <div className="mt-4"><Callout title="Yeni ekip üyesi ekleme">
        <span className="inline-flex items-start gap-1.5"><UserPlus size={15} className="mt-0.5 shrink-0" aria-hidden />
          Herkese açık kayıt kapalıdır. Supabase panelinde <b>Authentication → Users → Invite user</b> ile davet gönderin. Davet edilen kişi bağlantıya tıklayınca parolasını belirler ve “İzleyici” rolüyle bu listede görünür; ardından yönetici rolünü buradan değiştirir.</span>
      </Callout></div>
      {me && !isAdmin && <p className="mt-3 text-[12.5px] text-ink-3">Rolünüz: {roleLabels[me.role]}. Rol değişikliği için yöneticiye başvurun.</p>}
    </section>
  );
}

export default function SettingsAdmin() {
  const settings = useSettings();
  return (
    <AdminPage title="Ayarlar" description="Proje genelindeki bilgiler, döviz kuru, Tasarım II durumu ile kullanıcılar ve roller.">
      <ReadOnlyNotice need="admin" />
      <div className="space-y-6">
        {settings.error && <ErrorNotice error={settings.error} onRetry={() => void settings.refetch()} />}
        {settings.data ? <SettingsForm s={settings.data} /> : settings.data === null ? <ErrorNotice error={{ message: 'Proje ayarları satırı bulunamadı. supabase/setup.sql dosyasını çalıştırın.' }} /> : <SkeletonRows rows={6} />}
        <Users />
      </div>
    </AdminPage>
  );
}
