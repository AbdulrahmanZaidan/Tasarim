/** Yayımlanan simülasyon deneyleri: filtrelenebilir galeri ve konu/bileşen bazlı kısa listeler. */
import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { FlaskConical, ImagePlus, ArrowRight, Paperclip } from 'lucide-react';
import { useCore, useSimulationsData } from '../data/public';
import { Badge } from './ui';
import { EmptyState, Skeleton } from './feedback';
import { useMediaUrls } from './MediaGallery';
import DataNotice from './DataNotice';
import { resultLabels, resultTone, softwareOptions, type ExperimentResult } from '../lib/labels';
import { fmtDate } from '../lib/format';
import { isImage } from '../lib/files';
import type { Media, Simulation } from '../services/entities';

function ExperimentCard({ s, thumb, files, componentName, componentSlug }: { s: Simulation; thumb?: string; files: number; componentName?: string; componentSlug?: string }) {
  return (
    <article className="card group flex flex-col overflow-hidden transition-all hover:-translate-y-0.5 hover:border-brand">
      <Link to={`/proje/simulasyon/deney/${s.id}`} className="block bg-brand-mist text-ink hover:text-ink" aria-label={`${s.title} — ayrıntılar`}>
        {thumb ? <img src={thumb} alt="" loading="lazy" decoding="async" className="aspect-video w-full object-contain" />
          : <span className="flex aspect-video w-full items-center justify-center text-brand-line"><FlaskConical size={36} aria-hidden /></span>}
      </Link>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={resultTone[s.result_status]}>{resultLabels[s.result_status]}</Badge>
          <span className="chip border-brand-line bg-white text-ink-2">{s.software_used}</span>
          {componentName && componentSlug && <Link to={`/proje/bilesen/${componentSlug}`} className="chip border-brand-line bg-white text-ink-2 hover:text-brand">{componentName}</Link>}
        </div>
        <h3 className="text-[16px] font-semibold leading-snug"><Link to={`/proje/simulasyon/deney/${s.id}`} className="text-ink hover:text-brand">{s.title}</Link></h3>
        {s.experiment_objective && <p className="line-clamp-2 text-[13px] leading-5 text-ink-3">{s.experiment_objective}</p>}
        <div className="mt-auto flex items-center justify-between pt-1 text-[12px] text-ink-3">
          <span>{s.experiment_date ? fmtDate(s.experiment_date) : 'Tarih girilmedi'}</span>
          {files > 0 && <span className="inline-flex items-center gap-1"><Paperclip size={12} aria-hidden />{files} dosya</span>}
        </div>
      </div>
    </article>
  );
}

function useThumbs(sims: Simulation[], media: Media[]) {
  const firstImages = useMemo(() => sims.map((s) => media.find((m) => m.simulation_id === s.id && isImage(m.mime_type))).filter(Boolean) as Media[], [sims, media]);
  const urls = useMediaUrls(firstImages, 640);
  return (s: Simulation) => {
    const m = firstImages.find((x) => x.simulation_id === s.id);
    return m ? urls.data?.[m.id] : undefined;
  };
}

/** Tam galeri: bileşen, yazılım ve sonuç durumuna göre süzülebilir. Süzgeçler adres çubuğunda tutulur. */
export function ExperimentGallery() {
  const sims = useSimulationsData();
  const { data: core } = useCore();
  const [params, setParams] = useSearchParams();
  const comp = params.get('bilesen') ?? '';
  const sw = params.get('yazilim') ?? '';
  const res = (params.get('sonuc') ?? '') as ExperimentResult | '';
  const setParam = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v); else p.delete(k);
    setParams(p, { replace: true, preventScrollReset: true });
  };
  const compBySlug = new Map(core.components.map((c) => [c.slug, c]));
  const compById = new Map(core.components.map((c) => [c.id, c]));
  const filtered = sims.data.simulations.filter((s) =>
    (!comp || compById.get(s.component_id ?? '')?.slug === comp) && (!sw || s.software_used === sw) && (!res || s.result_status === res));
  const thumb = useThumbs(filtered, sims.data.media);
  const softwares = [...new Set([...softwareOptions, ...sims.data.simulations.map((s) => s.software_used)])];

  return (
    <div id="deneyler" className="scroll-mt-24">
      <DataNotice state={sims} className="mb-4" />
      <div className="mb-4 grid gap-2 sm:grid-cols-3">
        <select className="input" value={comp} onChange={(e) => setParam('bilesen', e.target.value)} aria-label="Bileşene göre süz">
          <option value="">Tüm bileşenler</option>{core.components.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
        </select>
        <select className="input" value={sw} onChange={(e) => setParam('yazilim', e.target.value)} aria-label="Yazılıma göre süz">
          <option value="">Tüm yazılımlar</option>{softwares.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input" value={res} onChange={(e) => setParam('sonuc', e.target.value)} aria-label="Sonuca göre süz">
          <option value="">Tüm sonuçlar</option>{(Object.keys(resultLabels) as ExperimentResult[]).map((k) => <option key={k} value={k}>{resultLabels[k]}</option>)}
        </select>
      </div>
      {sims.loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-72" />)}</div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={<ImagePlus size={32} aria-hidden />} title={sims.data.simulations.length ? 'Bu süzgeçlere uyan deney yok' : 'Henüz simülasyon görüntüsü eklenmedi.'}
          action={(comp || sw || res) ? <button className="btn-outline" onClick={() => setParams(new URLSearchParams(), { replace: true })}>Süzgeçleri temizle</button> : undefined}>
          {sims.data.simulations.length ? 'Farklı bir bileşen, yazılım veya sonuç seçin.' : 'Ekibin Digital / Proteus çalışmaları kaydedildikçe ekran görüntüleri, giriş–çıkış değerleri ve dosyalarıyla birlikte burada yayımlanacaktır.'}
        </EmptyState>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((s) => {
            const c = compById.get(s.component_id ?? '');
            return <ExperimentCard key={s.id} s={s} thumb={thumb(s)} files={sims.data.media.filter((m) => m.simulation_id === s.id).length} componentName={c?.name} componentSlug={c?.slug} />;
          })}
        </div>
      )}
      {comp && compBySlug.get(comp) && (
        <p className="mt-3 text-[13px] text-ink-3"><Link to={`/proje/bilesen/${comp}`}>{compBySlug.get(comp)!.name} bileşen sayfasına git →</Link></p>
      )}
    </div>
  );
}

/** Bir test senaryosu veya bileşen altında ilgili yayımlanmış deneyleri listeler. */
export function TopicExperiments({ components, label }: { components: string[]; label?: string }) {
  const sims = useSimulationsData();
  const { data: core } = useCore();
  const ids = core.components.filter((c) => components.includes(c.slug)).map((c) => c.id);
  const list = sims.data.simulations.filter((s) => s.component_id && ids.includes(s.component_id));
  if (sims.loading) return <Skeleton className="h-14 w-full" />;
  if (!list.length) {
    return (
      <div className="flex flex-col gap-2 rounded-lg border border-dashed border-brand-line p-4 text-[13px] text-ink-3 sm:flex-row sm:items-center">
        <ImagePlus size={20} className="shrink-0 text-brand" aria-hidden />
        <span>{label ?? 'Bu bileşen için henüz test sonucu bulunmuyor.'} Gerçek simülasyon kayıtları eklendikçe burada listelenecektir.</span>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-brand-line">
      <div className="border-b border-brand-line bg-brand-mist px-4 py-2 text-[11px] font-semibold tracking-[0.12em] text-brand">KAYITLI DENEYLER ({list.length})</div>
      <ul className="divide-y divide-brand-line/60">
        {list.map((s) => (
          <li key={s.id}>
            <Link to={`/proje/simulasyon/deney/${s.id}`} className="flex flex-wrap items-center gap-2 px-4 py-2.5 text-[14px] text-ink hover:bg-brand-mist/50 hover:text-ink">
              <Badge tone={resultTone[s.result_status]}>{resultLabels[s.result_status]}</Badge>
              <span className="flex-1 font-medium">{s.title}</span>
              <span className="text-[12px] text-ink-3">{s.software_used} · {s.experiment_date ? fmtDate(s.experiment_date) : 'tarih yok'}</span>
              <ArrowRight size={15} className="text-brand" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
