import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, FileText, GitBranch, Users, CircuitBoard, Activity, Cpu, LineChart, ClipboardCheck, Folder, File, Inbox, RefreshCw, GitCommitHorizontal, CalendarCheck } from 'lucide-react';
import { useCore, useDocumentsData, useTimeline } from '../data/public';
import { PageHeader, Section, Callout, StageNav, StatusBadge, Stat } from '../components/ui';
import { EmptyState, ErrorNotice, Skeleton } from '../components/feedback';
import { useQuery } from '../lib/query';
import { fetchRepo, importantFiles, topDirectories } from '../services/github';
import { fmtDate, fmtDateTime, fmtRelative } from '../lib/format';
import { documentTypeLabels } from '../lib/labels';
import { DownloadButton } from '../components/MediaGallery';

const reasons = [
  { icon: FileText, t: 'Proje dokümantasyonu', d: 'Rapor, toplantı notları ve teknik açıklamaların tek yerde tutulması.' },
  { icon: GitBranch, t: 'Sürüm kontrolü', d: 'Her değişikliğin geçmişiyle saklanması; gerektiğinde önceki sürüme dönülebilmesi.' },
  { icon: Users, t: 'Ekip çalışması', d: 'İki kişilik ekip arasında iş bölümü, issue ve pull request ile koordinasyon.' },
  { icon: CircuitBoard, t: 'Mimari diyagramlar ve şemalar', d: 'Blok diyagramlar ile modül devre şemalarının sürümlenmesi.' },
  { icon: Activity, t: 'Simülasyon kaynak dosyaları', d: 'Digital (.dig) ve Proteus proje dosyalarının paylaşılması.' },
  { icon: Cpu, t: 'EEPROM ve mikrokod geliştirme', d: 'Mikrokod tablolarının ve EEPROM programlayıcı kodunun geliştirilmesi.' },
  { icon: LineChart, t: 'Geliştirme sürecinin izlenmesi', d: 'Aşamaların ve kilometre taşlarının depo üzerinden takibi.' },
  { icon: ClipboardCheck, t: 'Test sonuçlarının saklanması', d: 'Simülasyon ve donanım testlerine ait kayıtların arşivlenmesi.' },
];

const proposed: [string, string][] = [
  ['README.md', 'Proje özeti ve klasör rehberi'],
  ['docs', 'Raporlar ve teknik dokümanlar'],
  ['architecture', 'Blok diyagramlar, komut seti'],
  ['schematics', 'Modül devre şemaları'],
  ['simulations', 'Digital / Proteus dosyaları'],
  ['microcode', 'Mikrokod tabloları, EEPROM kodları'],
  ['components', 'Malzeme listesi, veri sayfaları'],
  ['images', 'Fotoğraf ve ekran görüntüleri'],
  ['reports', 'Dönem raporları, test sonuçları'],
];

export default function GithubPage() {
  const core = useCore();
  const { settings, phases } = core.data;
  const stage = phases.find((p) => p.slug === 'github');
  const repo = settings.repo;
  const [force, setForce] = useState(0);
  const q = useQuery(repo ? `github:${repo.owner}/${repo.name}:${force}` : null, () => fetchRepo(repo!.owner, repo!.name, force > 0), { staleMs: 10 * 60_000 });
  const snap = q.data;
  const dirs = snap ? topDirectories(snap.tree) : [];
  const files = snap ? importantFiles(snap.tree) : [];
  const rootNames = new Set(snap?.tree.filter((t) => !t.path.includes('/')).map((t) => t.path.toLowerCase()) ?? []);
  const timeline = useTimeline();
  const docs = useDocumentsData();
  const repoUrl = settings.githubUrl;
  const blob = (path: string) => (snap ? `${snap.meta.html_url}/blob/${snap.meta.default_branch}/${path}` : '#');

  return (
    <>
      <PageHeader eyebrow={`Aşama ${stage?.number ?? '03'} · Tasarım I`} title="Proje Kaynak Kodları ve Sürüm Yönetimi"
        subtitle="Projeye ait şema, simülasyon, mikrokod, doküman dosyaları ve bu sitenin kaynak kodu GitHub deposunda tutulur."
        crumbs={[{ label: 'Proje Planı', to: '/proje' }, { label: 'GitHub Deposu' }]} right={stage && <StatusBadge status={stage.status} size="md" />} />

      <Section>
        <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr] lg:items-start">
          <div className="rounded-[10px] bg-brand p-6 text-white">
            <div className="text-[12px] font-semibold tracking-[0.14em] text-white/80">RESMİ PROJE DEPOSU</div>
            <div className="mono mt-2 break-all text-[20px] font-semibold">{repoUrl.replace(/^https:\/\//, '')}</div>
            <p className="mt-2 text-[14px] leading-6 text-white/90">
              {snap?.meta.description ?? 'Teknik dokümanlar, devre şemaları ve simülasyon dosyaları geliştirme süreci boyunca bu depoya eklenir.'}
            </p>
            <a href={repoUrl} target="_blank" rel="noreferrer" className="btn mt-5 bg-white text-brand hover:bg-brand-soft hover:text-brand-dark">GitHub Deposunu Aç → <ExternalLink size={15} aria-hidden /></a>
          </div>

          <div className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-brand-line bg-brand-mist px-4 py-2.5">
              <span className="text-[12px] font-semibold tracking-[0.12em] text-brand">DEPO BİLGİLERİ · GITHUB API</span>
              <button className="btn-ghost px-2 py-1 text-[13px]" onClick={() => setForce((n) => n + 1)} disabled={q.loading}><RefreshCw size={14} aria-hidden className={q.loading ? 'animate-spin' : ''} /> Yenile</button>
            </div>
            <div className="p-5" aria-live="polite">
              {!repo && <p className="text-[14px] text-ink-3">Proje ayarlarında geçerli bir GitHub adresi tanımlı değil.</p>}
              {q.loading && !snap && <div className="space-y-2"><Skeleton className="h-5 w-2/3" /><Skeleton className="h-16 w-full" /></div>}
              {q.error && !snap && <ErrorNotice title="Depo bilgileri şu anda alınamadı" error={{ message: `${q.error.message} Depoyu doğrudan GitHub üzerinden görüntüleyebilirsiniz.` }} onRetry={() => setForce((n) => n + 1)} />}
              {snap && (
                <>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <Stat label="Dal" value={<span className="text-[16px]">{snap.meta.default_branch}</span>} />
                    <Stat label="Dosya" value={snap.tree.filter((t) => t.type === 'blob').length} />
                    <Stat label="Son commit" value={<span className="text-[15px]">{snap.commits[0] ? fmtRelative(snap.commits[0].commit.author?.date ?? snap.meta.pushed_at) : '—'}</span>} />
                    <Stat label="Açık konu" value={snap.meta.open_issues_count} />
                  </div>
                  <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[13px]">
                    <div><dt className="inline text-ink-3">Oluşturulma: </dt><dd className="inline font-medium">{fmtDate(snap.meta.created_at)}</dd></div>
                    <div><dt className="inline text-ink-3">Son gönderim: </dt><dd className="inline font-medium">{fmtDateTime(snap.meta.pushed_at)}</dd></div>
                    {snap.meta.language && <div><dt className="inline text-ink-3">Ana dil: </dt><dd className="inline font-medium">{snap.meta.language}</dd></div>}
                  </dl>
                  {snap.empty && (
                    <div className="mt-4 flex gap-3"><Inbox size={22} className="shrink-0 text-brand" aria-hidden />
                      <p className="text-[14px] text-ink-2">Depo şu anda boştur. Proje deposu oluşturulmuştur; teknik dosyalar geliştirme süreci boyunca eklenecektir.</p></div>
                  )}
                  <p className="mt-3 text-[11.5px] text-ink-3">Veriler {fmtDateTime(new Date(snap.fetchedAt).toISOString())} itibarıyla GitHub’dan alınmıştır (10 dk önbellek).</p>
                </>
              )}
            </div>
          </div>
        </div>
        <div className="mt-4">
          <Callout title="Deponun oluşturulması ≠ aşamanın tamamlanması">Deponun açılmış olması bu aşamanın yalnızca ilk kilometre taşıdır. Aşama; README, klasör yapısı ve teknik dosyalar düzenli olarak eklendiğinde tamamlanmış sayılacaktır.</Callout>
        </div>
      </Section>

      {snap && !snap.empty && (
        <Section eyebrow="Depo etkinliği" title="Son commit’ler ve dosya yapısı">
          <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
            <div className="card overflow-hidden">
              <div className="border-b border-brand-line bg-brand-mist px-4 py-2 text-[12px] font-semibold tracking-[0.12em] text-brand">SON COMMIT’LER</div>
              <ul className="divide-y divide-brand-line/60">
                {snap.commits.map((c) => (
                  <li key={c.sha} className="flex gap-3 px-4 py-2.5 text-[14px]">
                    <GitCommitHorizontal size={18} className="mt-0.5 shrink-0 text-brand" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <a href={c.html_url} target="_blank" rel="noreferrer" className="block truncate font-medium text-ink hover:text-brand">{c.commit.message.split('\n')[0]}</a>
                      <span className="text-[12px] text-ink-3">{c.author?.login ?? c.commit.author?.name ?? 'bilinmiyor'} · {fmtDateTime(c.commit.author?.date)} · <span className="mono">{c.sha.slice(0, 7)}</span></span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            <div className="space-y-5">
              <div className="card overflow-hidden">
                <div className="border-b border-brand-line bg-brand-mist px-4 py-2 text-[12px] font-semibold tracking-[0.12em] text-brand">ANA DİZİNLER</div>
                <ul className="grid gap-x-4 px-4 py-2 sm:grid-cols-2">
                  {dirs.map((d) => (
                    <li key={d.name}><a href={`${snap.meta.html_url}/tree/${snap.meta.default_branch}/${d.name}`} target="_blank" rel="noreferrer" className="flex items-center gap-2 py-1.5 text-[14px] text-ink hover:text-brand">
                      <Folder size={15} className="text-brand" aria-hidden />{d.name}<span className="ml-auto text-[12px] text-ink-3">{d.files} dosya</span></a></li>
                  ))}
                  {dirs.length === 0 && <li className="py-2 text-[13px] text-ink-3">Kök dizinde klasör yok.</li>}
                </ul>
              </div>
              <div className="card overflow-hidden">
                <div className="border-b border-brand-line bg-brand-mist px-4 py-2 text-[12px] font-semibold tracking-[0.12em] text-brand">ÖNEMLİ DOSYALAR</div>
                <ul className="px-4 py-2">
                  {files.map((f) => (
                    <li key={f.path}><a href={blob(f.path)} target="_blank" rel="noreferrer" className="flex items-center gap-2 py-1 text-[13.5px] text-ink hover:text-brand">
                      <File size={14} className="shrink-0 text-ink-3" aria-hidden /><span className="mono truncate">{f.path}</span></a></li>
                  ))}
                  {files.length === 0 && <li className="py-2 text-[13px] text-ink-3">Belge, şema veya simülasyon dosyası henüz eklenmedi.</li>}
                </ul>
                {snap.treeTruncated && <p className="px-4 pb-2 text-[11.5px] text-ink-3">Depo çok büyük olduğu için dosya listesi kısaltılmıştır.</p>}
              </div>
            </div>
          </div>
        </Section>
      )}

      <Section eyebrow="Bağlantılar" title="Proje güncellemeleri ve teknik kaynaklar">
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <div className="mb-2 text-[12px] font-semibold tracking-[0.12em] text-brand">SON PROJE GÜNCELLEMELERİ</div>
            {timeline.data.updates.length === 0 ? <p className="text-[14px] text-ink-3">Henüz kayıtlı gelişme yok.</p> : (
              <ul className="space-y-2">
                {timeline.data.updates.slice(0, 5).map((u) => (
                  <li key={u.id} className="flex gap-2 text-[14px]"><CalendarCheck size={16} className="mt-0.5 shrink-0 text-brand" aria-hidden />
                    <span><b>{u.title}</b> <span className="text-[12px] text-ink-3">· {fmtDate(u.update_date)}</span></span></li>
                ))}
              </ul>
            )}
            <Link to="/proje/ilerleme#zaman-cizelgesi" className="mt-3 inline-block text-[14px] font-semibold">Tüm proje günlüğü →</Link>
          </div>
          <div className="card p-4">
            <div className="mb-2 text-[12px] font-semibold tracking-[0.12em] text-brand">YAYIMLANAN TEKNİK BELGELER</div>
            {docs.data.documents.length === 0 ? <p className="text-[14px] text-ink-3">Henüz yayımlanmış teknik belge yok.</p> : (
              <ul className="space-y-1.5">
                {docs.data.documents.slice(0, 6).map((d) => {
                  const f = docs.data.files.find((x) => x.id === d.file_id);
                  return (
                    <li key={d.id} className="flex flex-wrap items-center gap-2 text-[14px]">
                      <FileText size={15} className="text-brand" aria-hidden /><b className="flex-1">{d.title}</b>
                      <span className="text-[12px] text-ink-3">{documentTypeLabels[d.document_type]} · s{d.version}</span>
                      {f && <DownloadButton media={f} />}
                    </li>
                  );
                })}
              </ul>
            )}
            <Link to="/proje/belgeler" className="mt-3 inline-block text-[14px] font-semibold">Tüm teknik belgeler →</Link>
          </div>
        </div>
      </Section>

      <Section eyebrow="Gerekçe" title="Neden GitHub kullanılıyor?">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {reasons.map(({ icon: I, t, d }) => (
            <div key={t} className="card p-4 transition-colors hover:border-brand">
              <I size={20} className="text-brand" aria-hidden />
              <div className="mt-2 font-semibold">{t}</div>
              <p className="mt-1 text-[13px] leading-5 text-ink-3">{d}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section eyebrow="Öneri" title="Önerilen depo yapısı" intro="Teknik dosyalar için önerilen klasör düzeni. Her satırın yanında klasörün depoda şu anda bulunup bulunmadığı GitHub verisine göre gösterilir.">
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-brand-line bg-brand-mist px-4 py-2">
            <span className="text-[12px] font-semibold tracking-[0.12em] text-brand">ÖNERİLEN YAPI</span>
          </div>
          <div className="overflow-x-auto p-4">
            <table className="min-w-[560px] text-[14px]">
              <tbody>
                <tr><td className="mono whitespace-pre py-0.5 pr-8 text-brand">{settings.repo?.name ?? 'Tasarim1'}/</td><td /><td /></tr>
                {proposed.map(([name, desc], i) => {
                  const exists = rootNames.has(name.toLowerCase());
                  return (
                    <tr key={name}>
                      <td className={`mono whitespace-pre py-0.5 pr-8 ${name.includes('.') ? 'text-ink' : 'text-brand'}`}>{i === proposed.length - 1 ? '└── ' : '├── '}{name}{name.includes('.') ? '' : '/'}</td>
                      <td className="pr-6 text-[13px] text-ink-3">{desc}</td>
                      <td>{snap ? (exists ? <span className="chip border-emerald-300 bg-emerald-50 text-emerald-800">Mevcut</span> : <span className="chip border-amber-300 bg-amber-50 text-amber-800">Henüz oluşturulmadı</span>) : null}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
        {!snap && !q.loading && <div className="mt-4"><EmptyState title="Klasör durumu doğrulanamadı">GitHub verisi alınamadığı için klasörlerin depoda bulunup bulunmadığı gösterilemiyor.</EmptyState></div>}
      </Section>

      <StageNav current="github" />
    </>
  );
}
