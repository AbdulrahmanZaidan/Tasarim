/**
 * Bileşen sayfası: bir modülün mimari açıklaması, ilerlemesi, görevleri, deneyleri, görselleri ve belgeleri tek yerde.
 * Eğitsel içerik statik (src/data/architecture.ts); ilerleme ve kanıtlar veritabanından gelir.
 */
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Cpu, ArrowRight, FileText } from 'lucide-react';
import { useCore, useComponentMedia, useDocumentsData } from '../data/public';
import { modules } from '../data/architecture';
import { PageHeader, Section, Figure, ProgressBar, Badge } from '../components/ui';
import { ModuleDiagram } from '../components/diagrams';
import { EmptyState } from '../components/feedback';
import { MediaGallery, DownloadButton } from '../components/MediaGallery';
import { TopicExperiments } from '../components/ExperimentArchive';
import DataNotice from '../components/DataNotice';
import { documentTypeLabels, mediaCategoryLabels, workStatusLabels, workTone, type MediaCategory } from '../lib/labels';
import { fmtDate } from '../lib/format';

const archAnchor: Record<string, string> = { eeprom: 'modul-isa', isa: 'modul-isa', integration: 'modul-cycle' };

export default function ComponentPage() {
  const { slug = '' } = useParams();
  const core = useCore();
  const c = core.data.components.find((x) => x.slug === slug);
  const m = modules.find((x) => x.id === slug);
  const media = useComponentMedia(core.data.source === 'db' ? c?.id ?? null : null);
  const docs = useDocumentsData();
  const tasks = core.data.tasks.filter((t) => t.componentId && t.componentId === c?.id);
  const myDocs = docs.data.documents.filter((d) => d.component_id && d.component_id === c?.id);
  const idx = core.data.components.findIndex((x) => x.slug === slug);
  const prev = core.data.components[idx - 1];
  const next = core.data.components[idx + 1];

  if (!c) {
    return (
      <div className="container-x py-16">
        <EmptyState icon={<Cpu size={30} aria-hidden />} title="Bileşen bulunamadı" action={<Link to="/proje/mimari-sema" className="btn-outline">Mimari ve Şema</Link>}>Aradığınız bileşen kaldırılmış olabilir.</EmptyState>
      </div>
    );
  }
  const groups: MediaCategory[] = ['architecture_diagram', 'circuit_schematic', 'simulation_screenshot', 'breadboard_photo', 'component_photo', 'testing_evidence'];
  return (
    <>
      <PageHeader eyebrow={`Bileşen · ${c.nameEn ?? ''}`} title={c.name} subtitle={c.description ?? undefined}
        crumbs={[{ label: 'Mimari ve Şema', to: '/proje/mimari-sema' }, { label: c.name }]}
        right={<Badge tone={workTone[c.status]}>{workStatusLabels[c.status]}</Badge>} />

      <div className="container-x pt-6"><DataNotice state={core} /></div>

      <Section>
        <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
          <div className="space-y-4">
            {m ? (
              <>
                <p className="prose-body"><b>Neden gereklidir?</b> {m.why}</p>
                <Figure n="B.1" kind="kavramsal" caption={`${m.title} — girişler, kullanılan entegreler ve çıkışlar.`}><ModuleDiagram m={m} /></Figure>
                <Link to={`/proje/mimari-sema#modul-${m.id}`} className="inline-flex items-center gap-1.5 text-[14px] font-semibold">Ayrıntılı mimari açıklamaya git <ArrowRight size={15} aria-hidden /></Link>
              </>
            ) : (
              <Link to={`/proje/mimari-sema#${archAnchor[slug] ?? ''}`} className="inline-flex items-center gap-1.5 text-[14px] font-semibold">Mimari sayfasındaki ilgili bölüme git <ArrowRight size={15} aria-hidden /></Link>
            )}
            {c.notes && <div className="card-soft whitespace-pre-line p-4 text-[14px] leading-6 text-ink-2"><div className="mb-1 text-[11px] font-semibold tracking-[0.12em] text-brand">MİMARİ NOTLARI</div>{c.notes}</div>}
          </div>
          <aside className="card self-start p-5">
            <div className="eyebrow">İlerleme</div>
            <div className="mt-3"><ProgressBar value={tasks.length ? c.progress : null} label={tasks.length ? `${tasks.filter((t) => t.status === 'completed').length}/${tasks.length} görev` : 'Bu bileşene bağlı görev yok'} /></div>
            <div className="mt-4 text-[11px] font-semibold tracking-[0.12em] text-brand">İLGİLİ GÖREVLER</div>
            {tasks.length ? (
              <ul className="mt-1.5 space-y-1.5 text-[13.5px]">{tasks.map((t) => <li key={t.id} className="flex items-start justify-between gap-2"><span>{t.title}</span><Badge tone={workTone[t.status]} dot={false}>{workStatusLabels[t.status]}</Badge></li>)}</ul>
            ) : <p className="mt-1.5 text-[13px] text-ink-3">Henüz görev bağlanmadı.</p>}
            <div className="mt-4 flex flex-col gap-1.5 text-[14px]">
              <Link to={`/proje/simulasyon?bilesen=${slug}#deneyler`}>Bu bileşenin simülasyonları →</Link>
              <Link to="/proje/ilerleme">Proje ilerlemesi →</Link>
            </div>
          </aside>
        </div>
      </Section>

      <Section eyebrow="Deneyler" title={`${c.name} simülasyonları`}>
        <TopicExperiments components={[slug]} />
      </Section>

      <Section id="gorseller" eyebrow="Görseller" title="Şemalar, ekran görüntüleri ve fotoğraflar">
        {media.data.length === 0 ? (
          <EmptyState title="Henüz görsel eklenmedi.">Bu bileşene ait blok diyagramı, devre şeması, simülasyon ekran görüntüsü veya breadboard fotoğrafı yayımlandıkça burada gösterilecektir.</EmptyState>
        ) : (
          <div className="space-y-6">
            {groups.map((g) => {
              const items = media.data.filter((x) => x.category === g);
              if (!items.length) return null;
              return <div key={g}><h3 className="h3 mb-3">{mediaCategoryLabels[g]}</h3><MediaGallery items={items} /></div>;
            })}
            {(() => {
              const other = media.data.filter((x) => !groups.includes(x.category));
              return other.length ? <div><h3 className="h3 mb-3">Diğer dosyalar</h3><MediaGallery items={other} /></div> : null;
            })()}
          </div>
        )}
      </Section>

      <Section eyebrow="Belgeler" title="İlgili teknik belgeler">
        {myDocs.length === 0 ? <p className="text-[14px] text-ink-3">Bu bileşene bağlı yayımlanmış teknik belge yok.</p> : (
          <ul className="divide-y divide-brand-line/60 rounded-[10px] border border-brand-line">
            {myDocs.map((d) => {
              const f = docs.data.files.find((x) => x.id === d.file_id);
              return (
                <li key={d.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-[14px]">
                  <FileText size={18} className="text-brand" aria-hidden />
                  <span className="min-w-0 flex-1"><b>{d.title}</b><span className="block text-[12px] text-ink-3">{documentTypeLabels[d.document_type]} · sürüm {d.version} · {fmtDate(d.updated_at)}</span></span>
                  {f && <DownloadButton media={f} />}
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      <nav aria-label="Bileşenler arası gezinme" className="container-x flex flex-wrap justify-between gap-3 pb-14">
        {prev ? <Link to={`/proje/bilesen/${prev.slug}`} className="btn-outline"><ArrowLeft size={16} aria-hidden /> {prev.name}</Link> : <span />}
        {next && <Link to={`/proje/bilesen/${next.slug}`} className="btn-outline">{next.name} <ArrowRight size={16} aria-hidden /></Link>}
      </nav>
    </>
  );
}
