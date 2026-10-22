import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, FlaskConical, CalendarDays, Cpu, Wrench } from 'lucide-react';
import { useCore, useSimulationsData } from '../data/public';
import { PageHeader, Section, Badge, Callout } from '../components/ui';
import { EmptyState, Skeleton } from '../components/feedback';
import { MediaGallery } from '../components/MediaGallery';
import DataNotice from '../components/DataNotice';
import { resultLabels, resultTone } from '../lib/labels';
import { fmtDate } from '../lib/format';

function Block({ title, children, mono = false }: { title: string; children?: string | null; mono?: boolean }) {
  if (!children) return null;
  return (
    <div className="card-soft p-4">
      <div className="text-[11px] font-semibold tracking-[0.12em] text-brand">{title}</div>
      <div className={`mt-1.5 whitespace-pre-wrap text-[14.5px] leading-6 text-ink-2 ${mono ? 'mono' : ''}`}>{children}</div>
    </div>
  );
}

export default function ExperimentPage() {
  const { id } = useParams();
  const sims = useSimulationsData();
  const { data: core } = useCore();
  const s = sims.data.simulations.find((x) => x.id === id);
  const comp = core.components.find((c) => c.id === s?.component_id);
  const media = sims.data.media.filter((m) => m.simulation_id === id);

  if (sims.loading) return <div className="container-x space-y-4 py-12"><Skeleton className="h-10 w-2/3" /><Skeleton className="h-64 w-full" /></div>;
  if (!s) {
    return (
      <div className="container-x py-16">
        <DataNotice state={sims} className="mb-4" />
        <EmptyState icon={<FlaskConical size={30} aria-hidden />} title="Deney kaydı bulunamadı" action={<Link to="/proje/simulasyon#deneyler" className="btn-outline">Tüm deneyler</Link>}>
          Bu kayıt kaldırılmış veya henüz yayımlanmamış olabilir.
        </EmptyState>
      </div>
    );
  }
  return (
    <>
      <PageHeader eyebrow={comp ? `${comp.name} · Simülasyon deneyi` : 'Simülasyon deneyi'} title={s.title}
        subtitle={s.description ?? undefined}
        crumbs={[{ label: 'Proje Planı', to: '/proje' }, { label: 'Simülasyon', to: '/proje/simulasyon' }, { label: 'Deney' }]}
        right={<Badge tone={resultTone[s.result_status]}>{resultLabels[s.result_status]}</Badge>} />

      <Section>
        <div className="mb-6 flex flex-wrap gap-x-6 gap-y-2 text-[14px] text-ink-2">
          <span className="inline-flex items-center gap-1.5"><Wrench size={15} className="text-brand" aria-hidden />{s.software_used}{s.software_version ? ` ${s.software_version}` : ''}</span>
          <span className="inline-flex items-center gap-1.5"><CalendarDays size={15} className="text-brand" aria-hidden />{s.experiment_date ? fmtDate(s.experiment_date) : 'Deney tarihi girilmedi'}</span>
          {comp && <Link to={`/proje/bilesen/${comp.slug}`} className="inline-flex items-center gap-1.5"><Cpu size={15} aria-hidden />{comp.name}</Link>}
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Block title="DENEYİN AMACI">{s.experiment_objective}</Block>
          <Block title="YÖNTEM">{s.methodology}</Block>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <Block title="GİRİŞ DEĞERLERİ" mono>{s.input_values}</Block>
          <Block title="YAPILAN İŞLEM">{s.operation}</Block>
          <Block title="BEKLENEN ÇIKTI" mono>{s.expected_output}</Block>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_auto]">
          <div className={`rounded-[10px] border-2 p-4 ${s.actual_output ? 'border-brand bg-white' : 'border-dashed border-brand-line'}`}>
            <div className="text-[11px] font-semibold tracking-[0.12em] text-brand">GÖZLENEN (GERÇEK) ÇIKTI</div>
            <div className="mono mt-1.5 whitespace-pre-wrap text-[15px] text-ink">{s.actual_output || 'Henüz kaydedilmedi.'}</div>
          </div>
          <div className="card flex flex-col justify-center p-4 text-center">
            <div className="text-[11px] font-semibold tracking-[0.12em] text-brand">SONUÇ</div>
            <div className="mt-2"><Badge tone={resultTone[s.result_status]}>{resultLabels[s.result_status]}</Badge></div>
          </div>
        </div>
        {(s.notes || s.conclusion) && (
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Block title="NOTLAR">{s.notes}</Block>
            <Block title="SONUÇ VE DEĞERLENDİRME">{s.conclusion}</Block>
          </div>
        )}
        <div className="mt-6"><Callout title="Kanıt ilkesi">Sonuç durumu, ekibin kaydettiği gözlemlere ve aşağıdaki ekran görüntüleri ile dosyalara dayanır. “Başarılı” veya “Başarısız” sonucu, gözlenen çıktı ve deney tarihi girilmeden kaydedilemez.</Callout></div>
      </Section>

      <Section eyebrow="Kanıtlar" title="Ekran görüntüleri ve dosyalar">
        <MediaGallery items={media} empty={<EmptyState title="Henüz simülasyon görüntüsü eklenmedi.">Bu deneye ait ekran görüntüsü veya kaynak dosya yayımlanmamıştır.</EmptyState>} />
        <Link to="/proje/simulasyon#deneyler" className="btn-ghost mt-6"><ArrowLeft size={16} aria-hidden /> Tüm deneyler</Link>
      </Section>
    </>
  );
}
