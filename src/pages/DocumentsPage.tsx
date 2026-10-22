import { useState } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Eye } from 'lucide-react';
import { useCore, useDocumentsData } from '../data/public';
import { PageHeader, Section } from '../components/ui';
import { EmptyState, Modal, SkeletonRows } from '../components/feedback';
import { DownloadButton, useMediaUrls } from '../components/MediaGallery';
import DataNotice from '../components/DataNotice';
import { documentTypeLabels, type DocumentType } from '../lib/labels';
import { fmtBytes, fmtDate } from '../lib/format';
import { isPdf } from '../lib/files';
import type { Media } from '../services/entities';

function PdfPreview({ media, onClose }: { media: Media; onClose: () => void }) {
  const urls = useMediaUrls([media]);
  return (
    <Modal open onClose={onClose} title={media.title} size="xl">
      {urls.data?.[media.id] ? <iframe title={media.title} src={urls.data[media.id]} className="h-[75vh] w-full rounded border border-brand-line" /> : <SkeletonRows rows={6} />}
    </Modal>
  );
}

export default function DocumentsPage() {
  const docs = useDocumentsData();
  const { data: core } = useCore();
  const [type, setType] = useState<'' | DocumentType>('');
  const [preview, setPreview] = useState<Media | null>(null);
  const list = docs.data.documents.filter((d) => !type || d.document_type === type);
  return (
    <>
      <PageHeader eyebrow="Dokümantasyon" title="Teknik Belgeler" subtitle="Proje raporları, devre şemaları, simülasyon ve test raporları ile bitirme projesi teslimleri. Yalnızca yayımlanmış belgeler listelenir."
        crumbs={[{ label: 'Proje Planı', to: '/proje' }, { label: 'Teknik Belgeler' }]} />
      <Section>
        <DataNotice state={docs} className="mb-4" />
        <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Belge türüne göre süz">
          <button className={!type ? 'btn-primary py-1.5' : 'btn-outline py-1.5'} onClick={() => setType('')}>Tümü</button>
          {(Object.keys(documentTypeLabels) as DocumentType[]).filter((t) => docs.data.documents.some((d) => d.document_type === t)).map((t) => (
            <button key={t} className={type === t ? 'btn-primary py-1.5' : 'btn-outline py-1.5'} onClick={() => setType(t)}>{documentTypeLabels[t]}</button>
          ))}
        </div>
        {docs.loading ? <SkeletonRows rows={4} /> : list.length === 0 ? (
          <EmptyState icon={<FileText size={30} aria-hidden />} title="Henüz yayımlanmış teknik belge yok">Raporlar, şemalar ve test belgeleri hazırlandıkça burada yayımlanacaktır.</EmptyState>
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[720px] text-[14px]">
              <thead className="border-b-2 border-brand bg-brand-mist text-left text-[12px] uppercase tracking-[0.06em] text-brand">
                <tr><th className="px-4 py-2.5">Belge</th><th className="px-3">Tür</th><th className="px-3">Bileşen</th><th className="px-3">Sürüm</th><th className="px-3">Güncelleme</th><th className="px-3" /></tr>
              </thead>
              <tbody>
                {list.map((d) => {
                  const f = docs.data.files.find((x) => x.id === d.file_id);
                  const comp = core.components.find((c) => c.id === d.component_id);
                  return (
                    <tr key={d.id} className="border-b border-brand-line/50 align-top">
                      <td className="px-4 py-3"><b>{d.title}</b>{d.description && <div className="text-[13px] text-ink-3">{d.description}</div>}{f && <div className="text-[12px] text-ink-3">{f.original_file_name} · {fmtBytes(f.file_size)}</div>}</td>
                      <td className="px-3 py-3 text-[13px]">{documentTypeLabels[d.document_type]}</td>
                      <td className="px-3 py-3 text-[13px]">{comp ? <Link to={`/proje/bilesen/${comp.slug}`}>{comp.name}</Link> : '—'}</td>
                      <td className="mono px-3 py-3">{d.version}</td>
                      <td className="px-3 py-3 text-[13px]">{fmtDate(d.updated_at)}</td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-right">
                        {f && isPdf(f.mime_type) && <button className="btn-ghost px-2 py-1 text-[13px]" onClick={() => setPreview(f)}><Eye size={15} aria-hidden /> Önizle</button>}
                        {f && <DownloadButton media={f} />}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>
      {preview && <PdfPreview media={preview} onClose={() => setPreview(null)} />}
    </>
  );
}
