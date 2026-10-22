import { Link } from 'react-router-dom';
import { BarChart3 } from 'lucide-react';
import { useCore } from '../data/public';
import DataNotice from '../components/DataNotice';
import { PageHeader, ProgressBar } from '../components/ui';
import Timeline from '../components/Timeline';

export default function PlanPage() {
  const core = useCore();
  const { settings, phases, overall } = core.data;
  const t1 = phases.filter((p) => p.semesterKey === 'tasarim_1').length;
  return (
    <>
      <PageHeader
        eyebrow="Tasarım I · Bitirme Projesi"
        title="Proje Planı"
        subtitle="8-Bit Breadboard Bilgisayar — Güz dönemi hazırlık planı ve aşamaları"
        crumbs={[{ label: 'Proje Planı' }]}
        right={<Link to="/proje/ilerleme" className="btn-outline shrink-0"><BarChart3 size={17} aria-hidden /> Proje İlerleme Durumu</Link>}
      />
      <div className="container-x pb-6 pt-7">
        <DataNotice state={core} className="mb-4" />
        <div className="card-soft grid gap-5 p-5 sm:p-6 md:grid-cols-[220px_1fr_260px]">
          <div>
            <div className="text-[12px] font-semibold tracking-[0.12em] text-brand">DANIŞMAN</div>
            <div className="mt-1.5 text-[17px] font-semibold">{settings.supervisor}</div>
          </div>
          <div>
            <div className="text-[12px] font-semibold tracking-[0.12em] text-brand">ÖĞRENCİLER</div>
            <ul className="mt-1.5 space-y-0.5 text-[15px]">{settings.team.map((s) => <li key={s.studentId || s.name}><b>{s.name}</b>{s.studentId && <> · <span className="mono">{s.studentId}</span></>}</li>)}</ul>
          </div>
          <div className="self-center"><ProgressBar value={core.loading ? null : overall.value} label="Genel ilerleme (görevlerden hesaplanır)" /></div>
        </div>

        <div className="mx-auto mt-6 flex w-full max-w-[345px] items-center justify-center rounded-lg bg-brand py-3 text-[15px] font-semibold text-white">
          1. Dönem · HAZIRLIK&nbsp;<span className="font-normal">(bu plan)</span>
        </div>

        <h2 className="h2 mt-10">Çalışma Şeması</h2>
        <p className="prose-body mt-1 max-w-3xl">Aşamalar sırayla birbirini besler: şemalar simülasyonla doğrulanır, tüm dosyalar depoda toplanır ve malzeme listesi simülasyon sonucuna göre kesinleştirilir. Bir aşamaya tıklayarak ayrıntılı sayfasına geçebilirsiniz.</p>
        <div className="mt-7"><Timeline /></div>

        <div className="mt-10 grid gap-3 border-t border-brand-line pt-6 text-[14px] text-ink-3 sm:grid-cols-2">
          <p>Toplam aşama: <b className="text-ink">{phases.length}</b> (Tasarım I: {t1}, Tasarım II: {phases.length - t1})</p>
          <p className="sm:text-right">Aşama durumlarının ayrıntısı için <Link to="/proje/ilerleme">İlerleme Durumu</Link> sayfasına bakınız.</p>
        </div>
      </div>
      <div className="pb-14" />
    </>
  );
}
