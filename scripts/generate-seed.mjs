// Mevcut TypeScript veri dosyalarından (src/data/fallback.ts) başlangıç verisi SQL'i üretir.
// Kullanım: node scripts/generate-seed.mjs
// Çıktı: supabase/migrations/20261022000004_seed.sql ve supabase/setup.sql
// Veri elle yeniden yazılmaz; statik site ve veritabanı aynı kaynaktan beslenir.
import { build } from 'esbuild';
import { mkdtempSync, writeFileSync, readFileSync, readdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const tmp = mkdtempSync(join(tmpdir(), 'seed-'));
const out = join(tmp, 'data.mjs');
await build({ entryPoints: [join(root, 'src/data/fallback.ts')], bundle: true, format: 'esm', platform: 'node', outfile: out, logLevel: 'error' });
const f = await import(pathToFileURL(out).href);
rmSync(tmp, { recursive: true, force: true });

const q = (v) => (v === null || v === undefined ? 'null' : typeof v === 'number' || typeof v === 'boolean' ? String(v) : `'${String(v).replace(/'/g, "''")}'`);
const rows = (arr, cols) => arr.map((r) => `  (${cols.map((c) => q(r[c])).join(', ')})`).join(',\n');
const s = f.seedSettings;

const phaseCols = ['slug', 'title', 'short_title', 'description', 'deliverable', 'semester', 'status', 'weight', 'route', 'sort_order'];
const compCols = ['slug', 'name', 'name_en', 'description', 'sort_order'];
const taskCols = ['phase', 'title', 'description', 'status', 'completed_at', 'sort_order'];
const matCols = ['slug', 'name', 'source_name', 'category', 'notes', 'required_quantity', 'ref_quantity', 'ref_unit_price_min', 'ref_unit_price_max', 'ref_stated_total_min', 'ref_stated_total_max', 'is_programmer_extra', 'sort_order'];

const sql = `-- =====================================================================
-- 0004 · Başlangıç verisi (scripts/generate-seed.mjs tarafından üretilmiştir — elle düzenlemeyin)
-- Kaynak: src/data/fallback.ts (projectData.ts, parts.ts, architecture.ts)
-- Tekrar çalıştırılabilir: mevcut kayıtlar değiştirilmez (on conflict do nothing).
-- Simülasyon sonucu, satın alma veya kanıtsız tamamlanmış iş UYDURULMAZ.
-- =====================================================================
begin;
select set_config('app.seeding', 'on', true), set_config('app.phase_weights', 'on', true);

insert into public.project_settings (id, project_title, project_subtitle, project_description, university, course, supervisor, team_members, github_url, project_status, default_currency, tasarim_ii_active)
values (true, ${q(s.project_title)}, ${q(s.project_subtitle)}, ${q(s.project_description)}, ${q(s.university)}, ${q(s.course)}, ${q(s.supervisor)},
  ${q(JSON.stringify(s.team_members))}::jsonb, ${q(s.github_url)}, ${q(s.project_status)}, 'TRY', ${s.tasarim_ii_active})
on conflict (id) do nothing;

insert into public.project_phases (${phaseCols.join(', ')})
values
${rows(f.seedPhases, phaseCols)}
on conflict (slug) do nothing;

insert into public.project_components (${compCols.join(', ')})
values
${rows(f.seedComponents, compCols)}
on conflict (slug) do nothing;

insert into public.project_tasks (phase_id, title, description, status, completed_at, sort_order)
select p.id, v.title, v.description, v.status::public.work_status, v.completed_at::timestamptz, v.sort_order
from (values
${rows(f.seedTasks, taskCols)}
) as v(phase_slug, title, description, status, completed_at, sort_order)
join public.project_phases p on p.slug = v.phase_slug
where not exists (select 1 from public.project_tasks t where t.phase_id = p.id and t.title = v.title);

insert into public.materials (${matCols.join(', ')}, ref_currency)
select v.*, 'USD' from (values
${rows(f.seedMaterials, matCols)}
) as v(${matCols.join(', ')})
on conflict (slug) do nothing;

commit;
`;

writeFileSync(join(root, 'supabase/migrations/20261022000004_seed.sql'), sql);

const migDir = join(root, 'supabase/migrations');
const files = readdirSync(migDir).filter((x) => x.endsWith('.sql')).sort();
const setup = `-- 8-Bit Breadboard Bilgisayar · Tek dosyalık kurulum betiği
-- Bu dosya supabase/migrations/ klasöründeki dosyaların sıralı birleşimidir (node scripts/generate-seed.mjs ile üretilir).
-- Supabase panelinde SQL Editor'a yapıştırıp çalıştırın. Tekrar çalıştırmak güvenlidir; veri silinmez.

` + files.map((x) => `-- >>> ${x}\n${readFileSync(join(migDir, x), 'utf8')}\n`).join('\n');
writeFileSync(join(root, 'supabase/setup.sql'), setup);
console.log(`seed: ${f.seedPhases.length} aşama, ${f.seedTasks.length} görev, ${f.seedComponents.length} bileşen, ${f.seedMaterials.length} malzeme · ${files.length} göç dosyası birleştirildi`);
