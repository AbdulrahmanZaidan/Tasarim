/**
 * Statik yedek veri: Supabase yapılandırılmamışsa (ör. GitHub Pages önizlemesi) site bu verilerle çalışır.
 * Aynı dönüşüm `scripts/generate-seed.mjs` tarafından veritabanı başlangıç verisi üretmek için de kullanılır;
 * böylece statik site ile veritabanı içeriği birbirinden ayrışmaz.
 */
import { project, projectStages, tasarimIIRoadmap, TASARIM_II_ACTIVE } from './projectData';
import { modules } from './architecture';
import { parts, programmerParts } from './parts';
import type { PhaseStatus, Semester, WorkStatus } from '../lib/labels';

export interface SeedPhase {
  slug: string; title: string; short_title: string; description: string; deliverable: string;
  semester: Semester; status: PhaseStatus; weight: number; route: string; sort_order: number;
}
export interface SeedTask { phase: string; title: string; description: string | null; status: WorkStatus; completed_at: string | null; sort_order: number }
export interface SeedComponent { slug: string; name: string; name_en: string; description: string; sort_order: number }
export interface SeedMaterial {
  slug: string; name: string; source_name: string | null; category: string; notes: string | null; required_quantity: number;
  ref_quantity: number; ref_unit_price_min: number | null; ref_unit_price_max: number | null;
  ref_stated_total_min: number | null; ref_stated_total_max: number | null; is_programmer_extra: boolean; sort_order: number;
}

export const seedSettings = {
  project_title: project.title,
  project_subtitle: project.subtitle,
  project_description: 'Bu bitirme projesinin amacı, yalnızca temel dijital mantık entegre devreleri kullanılarak programlanabilir bir 8-bit bilgisayarın tasarlanması ve ikinci dönemde breadboard’lar üzerinde fiziksel olarak gerçekleştirilmesidir.',
  university: project.university,
  course: project.course,
  supervisor: project.advisor,
  team_members: project.students.map((s) => ({ name: s.name, student_id: s.id })),
  github_url: project.links.repo,
  project_status: 'Hazırlık aşaması',
  tasarim_ii_active: TASARIM_II_ACTIVE,
};

export const seedPhases: SeedPhase[] = projectStages.map((s, i) => ({
  slug: s.id,
  title: s.title,
  short_title: s.shortTitle,
  description: s.summary,
  deliverable: s.deliverable,
  semester: s.semester === 'Tasarım I' ? 'tasarim_1' : 'tasarim_2',
  status: s.status,
  weight: 20,
  route: s.path,
  sort_order: i + 1,
}));

/** Yalnızca planlanan işler; tek "tamamlandı" kaydı, doğrulanabilir olan depo oluşturulmasıdır. */
export const seedTasks: SeedTask[] = (() => {
  const out: SeedTask[] = [];
  for (const s of projectStages) {
    const seen = new Set<string>();
    const add = (title: string, extra: Partial<SeedTask> = {}) => {
      const key = title.toLocaleLowerCase('tr-TR');
      if (seen.has(key)) return;
      seen.add(key);
      out.push({ phase: s.id, title, description: null, status: 'not_started', completed_at: null, sort_order: seen.size, ...extra });
    };
    if (s.id === 'tasarim2') {
      tasarimIIRoadmap.forEach((r) => add(r.title, { description: r.text }));
      continue;
    }
    s.currentTasks.forEach((t) => add(t));
    s.nextTasks.forEach((t) => add(t));
    s.milestones.forEach((m) => {
      if (m.done && s.id === 'github') {
        add('GitHub deposunun oluşturulması', {
          status: 'completed',
          description: 'Depo github.com/Siiingularity/Tasarim1 adresinde oluşturulmuştur. Tamamlanma tarihi olarak deponun mevcut olduğunun ilk doğrulandığı tarih girilmiştir.',
          completed_at: '2026-10-20T00:00:00+03:00',
        });
      } else add(m.label);
    });
  }
  return out;
})();

const extraComponents: Record<string, Omit<SeedComponent, 'slug' | 'sort_order'>> = {
  eeprom: { name: 'EEPROM ve Mikrokod', name_en: 'EEPROM & Microcode', description: 'Kontrol birimi ve çıkış modülünde kullanılan 28C16 EEPROM’ların içeriği (mikrokod ve 7 segment tabloları) ile bu EEPROM’ları programlamak için kullanılan programlayıcı.' },
  isa: { name: 'Komut Seti Mimarisi', name_en: 'Instruction Set Architecture', description: 'Bilgisayarın desteklediği komutlar, işlem kodları (opcode) ve her komutun mikro adımları.' },
  integration: { name: 'Bilgisayarın Bütünleştirilmesi', name_en: 'Complete Computer Integration', description: 'Tüm modüllerin ortak veri yolu ve kontrol birimi üzerinden birleştirilerek tek bir bilgisayar olarak çalıştırılması.' },
};
export const componentSlugs = ['clock', 'registers', 'alu', 'ram', 'pc', 'ir', 'control', 'bus', 'output', 'eeprom', 'isa', 'integration'] as const;
export const seedComponents: SeedComponent[] = componentSlugs.map((slug, i) => {
  const m = modules.find((x) => x.id === slug);
  const extra = extraComponents[slug];
  return { slug, name: m?.title ?? extra.name, name_en: m?.en ?? extra.name_en, description: m?.what ?? extra.description, sort_order: i + 1 };
});

export const seedMaterials: SeedMaterial[] = [
  ...parts.map((p, i) => ({
    slug: p.id, name: p.name, source_name: p.source, category: p.category, notes: p.note ?? null, required_quantity: p.qty,
    ref_quantity: p.qty, ref_unit_price_min: p.unit.min, ref_unit_price_max: p.unit.max,
    ref_stated_total_min: p.statedTotal.min, ref_stated_total_max: p.statedTotal.max, is_programmer_extra: false, sort_order: (i + 1) * 10,
  })),
  ...programmerParts.map((x, i) => ({
    slug: x.id, name: x.name, source_name: null, category: 'EEPROM programlayıcı', notes: x.note ?? null, required_quantity: x.qty,
    ref_quantity: x.qty, ref_unit_price_min: null, ref_unit_price_max: null, ref_stated_total_min: null, ref_stated_total_max: null,
    is_programmer_extra: true, sort_order: 1000 + i * 10,
  })),
];
