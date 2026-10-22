/**
 * Genel sayfaların veri katmanı.
 * Supabase yapılandırılmışsa veriler veritabanından okunur; değilse (veya bağlantı kurulamazsa)
 * depodaki statik veriler aynı biçime dönüştürülerek kullanılır.
 * Genel sayfalar yalnızca YAYIMLANMIŞ kayıtları ve herkese açık depodaki dosyaları gösterir.
 */
import { useMemo } from 'react';
import { isSupabaseConfigured, db } from '../lib/supabase';
import { useQuery } from '../lib/query';
import type { AppError } from '../lib/errors';
import { unwrap } from '../services/base';
import type { Component, Material, Media, ProgressUpdate, Purchase, Simulation, TechDoc } from '../services/entities';
import { weightedProgress, phaseProgress, componentProgress, type WeightedResult } from '../lib/progress';
import type { PhaseStatus, Priority, Semester, WorkStatus } from '../lib/labels';
import { PUBLIC_BUCKET } from '../lib/files';
import { seedComponents, seedMaterials, seedPhases, seedSettings, seedTasks } from './fallback';

export interface TaskVM {
  id: string; phaseId: string; componentId: string | null; title: string; description: string | null;
  status: WorkStatus; priority: Priority; weight: number; dueDate: string | null; completedAt: string | null; updatedAt: string | null;
}
export interface PhaseVM {
  id: string; slug: string; number: string; title: string; shortTitle: string; path: string;
  semesterKey: Semester; semester: 'Tasarım I' | 'Tasarım II'; summary: string; deliverable: string;
  status: PhaseStatus; weight: number; progress: number | null; startDate: string | null; targetDate: string | null;
  lastUpdated: string | null; tasks: TaskVM[];
}
export interface ComponentVM {
  id: string; slug: string; name: string; nameEn: string | null; description: string | null; notes: string | null;
  status: WorkStatus; progress: number | null; sortOrder: number;
}
export interface SettingsVM {
  title: string; subtitle: string; description: string; university: string; course: string; supervisor: string;
  team: { name: string; studentId: string }[]; githubUrl: string; repo: { owner: string; name: string } | null;
  academicYear: string | null; projectStatus: string | null; tasarimIIActive: boolean;
  usdTryRate: number | null; rateDate: string | null; defaultCurrency: string;
}
export interface CoreData {
  source: 'db' | 'static';
  settings: SettingsVM; phases: PhaseVM[]; components: ComponentVM[]; tasks: TaskVM[];
  overall: WeightedResult; tasarim1: WeightedResult; tasarim2: WeightedResult;
}
export interface DataState<T> { data: T; loading: boolean; error?: AppError; fallback: boolean; refetch: () => void }

const semesterName = (s: Semester) => (s === 'tasarim_1' ? 'Tasarım I' : 'Tasarım II') as PhaseVM['semester'];
const parseRepo = (url: string) => {
  const m = url.match(/github\.com\/([^/]+)\/([^/]+?)(?:\.git)?\/?$/);
  return m ? { owner: m[1], name: m[2] } : null;
};

function assemble(source: CoreData['source'], settings: SettingsVM, rawPhases: Omit<PhaseVM, 'progress' | 'tasks' | 'lastUpdated' | 'number'>[], tasks: TaskVM[], comps: Omit<ComponentVM, 'progress'>[], phaseUpdated: Record<string, string | null>): CoreData {
  const ptasks = tasks.map((t) => ({ status: t.status, weight: t.weight, phase_id: t.phaseId, component_id: t.componentId }));
  const phases: PhaseVM[] = rawPhases.map((p, i) => {
    const own = tasks.filter((t) => t.phaseId === p.id);
    const dates = [phaseUpdated[p.id], ...own.map((t) => t.updatedAt)].filter(Boolean) as string[];
    return {
      ...p, number: String(i + 1).padStart(2, '0'), tasks: own, progress: phaseProgress(p.id, ptasks),
      lastUpdated: source === 'db' && dates.length ? dates.sort().at(-1)! : null,
    };
  });
  const forCalc = phases.map((p) => ({ id: p.id, weight: p.weight, semester: p.semesterKey }));
  return {
    source, settings, phases, tasks,
    components: comps.map((c) => ({ ...c, progress: componentProgress(c.id, ptasks) })),
    overall: weightedProgress(forCalc, ptasks),
    tasarim1: weightedProgress(forCalc.filter((p) => p.semester === 'tasarim_1'), ptasks),
    tasarim2: weightedProgress(forCalc.filter((p) => p.semester === 'tasarim_2'), ptasks),
  };
}

/* ---------------- Statik yedek ---------------- */
let staticCoreCache: CoreData | null = null;
export function staticCore(): CoreData {
  if (staticCoreCache) return staticCoreCache;
  const s = seedSettings;
  const settings: SettingsVM = {
    title: s.project_title, subtitle: s.project_subtitle, description: s.project_description, university: s.university, course: s.course,
    supervisor: s.supervisor, team: s.team_members.map((m) => ({ name: m.name, studentId: m.student_id })), githubUrl: s.github_url,
    repo: parseRepo(s.github_url), academicYear: null, projectStatus: s.project_status, tasarimIIActive: s.tasarim_ii_active,
    usdTryRate: null, rateDate: null, defaultCurrency: 'TRY',
  };
  const phases = seedPhases.map((p) => ({
    id: p.slug, slug: p.slug, title: p.title, shortTitle: p.short_title, path: p.route, semesterKey: p.semester, semester: semesterName(p.semester),
    summary: p.description, deliverable: p.deliverable, status: p.status, weight: p.weight, startDate: null, targetDate: null,
  }));
  const tasks: TaskVM[] = seedTasks.map((t, i) => ({
    id: `static-${i}`, phaseId: t.phase, componentId: null, title: t.title, description: t.description, status: t.status, priority: 'medium',
    weight: 1, dueDate: null, completedAt: t.completed_at, updatedAt: null,
  }));
  const comps = seedComponents.map((c) => ({ id: c.slug, slug: c.slug, name: c.name, nameEn: c.name_en, description: c.description, notes: null, status: 'not_started' as WorkStatus, sortOrder: c.sort_order }));
  staticCoreCache = assemble('static', settings, phases, tasks, comps, {});
  return staticCoreCache;
}

/* ---------------- Veritabanı ---------------- */
export async function loadCore(): Promise<CoreData> {
  const c = db();
  const [settings, phases, tasks, comps] = await Promise.all([
    unwrap(c.from('project_settings').select('*').eq('id', true).maybeSingle()),
    unwrap(c.from('project_phases').select('*').order('semester').order('sort_order')),
    unwrap(c.from('project_tasks').select('*').order('sort_order').order('created_at')),
    unwrap(c.from('project_components').select('*').order('sort_order')),
  ]);
  const st = settings ?? null;
  const fb = staticCore().settings;
  const team = Array.isArray(st?.team_members) ? (st!.team_members as { name?: string; student_id?: string }[]) : [];
  const s: SettingsVM = st ? {
    title: st.project_title, subtitle: st.project_subtitle ?? '', description: st.project_description ?? '', university: st.university ?? '',
    course: st.course ?? '', supervisor: st.supervisor ?? '', team: team.map((m) => ({ name: m.name ?? '', studentId: m.student_id ?? '' })),
    githubUrl: st.github_url ?? '', repo: st.github_url ? parseRepo(st.github_url) : null, academicYear: st.academic_year,
    projectStatus: st.project_status, tasarimIIActive: st.tasarim_ii_active, usdTryRate: st.usd_try_rate, rateDate: st.usd_try_rate_date,
    defaultCurrency: st.default_currency,
  } : fb;
  return assemble('db', s,
    phases.map((p) => ({
      id: p.id, slug: p.slug, title: p.title, shortTitle: p.short_title ?? p.title, path: p.route ?? `/proje/ilerleme#asama-${p.slug}`,
      semesterKey: p.semester, semester: semesterName(p.semester), summary: p.description ?? '', deliverable: p.deliverable ?? '',
      status: p.status, weight: Number(p.weight), startDate: p.start_date, targetDate: p.target_date,
    })),
    tasks.map((t) => ({
      id: t.id, phaseId: t.phase_id, componentId: t.component_id, title: t.title, description: t.description, status: t.status,
      priority: t.priority, weight: Number(t.weight), dueDate: t.due_date, completedAt: t.completed_at, updatedAt: t.updated_at,
    })),
    comps.map((x) => ({ id: x.id, slug: x.slug, name: x.name, nameEn: x.name_en, description: x.description, notes: x.architecture_notes, status: x.status, sortOrder: x.sort_order })),
    Object.fromEntries(phases.map((p) => [p.id, p.updated_at])),
  );
}

function useBacked<T>(key: string, load: () => Promise<T>, fallback: () => T): DataState<T> {
  const q = useQuery<T>(isSupabaseConfigured ? key : null, load);
  return useMemo(() => {
    if (!isSupabaseConfigured) return { data: fallback(), loading: false, fallback: true, refetch: () => undefined };
    if (q.data !== undefined) return { data: q.data, loading: false, error: q.error, fallback: false, refetch: () => void q.refetch() };
    return { data: fallback(), loading: !q.error, error: q.error, fallback: true, refetch: () => void q.refetch() };
  }, [q.data, q.error, q.refetch]);
}

export function useCore(): DataState<CoreData> {
  return useBacked('core:public', loadCore, staticCore);
}

/* ---------------- Malzemeler ---------------- */
export interface MaterialsData { materials: Material[]; purchases: Purchase[] }
let staticMaterialsCache: MaterialsData | null = null;
export function staticMaterials(): MaterialsData {
  if (!staticMaterialsCache) {
    staticMaterialsCache = {
      purchases: [],
      materials: seedMaterials.map((m) => ({
        ...m, id: m.slug, description: null, purchased_quantity: 0, ref_currency: 'USD', unit_price: null, currency: 'TRY', supplier: null,
        product_url: null, purchase_status: 'not_purchased', created_at: '', updated_at: '', updated_by: null,
      })),
    };
  }
  return staticMaterialsCache;
}
export function useMaterialsData(): DataState<MaterialsData> {
  return useBacked('materials:public', async () => {
    const [materials, purchases] = await Promise.all([
      unwrap(db().from('materials').select('*').order('sort_order').order('name')),
      unwrap(db().from('purchases').select('*').order('purchase_date', { ascending: false })),
    ]);
    return { materials, purchases };
  }, staticMaterials);
}

/* ---------------- Simülasyon deneyleri ---------------- */
export interface SimulationsData { simulations: Simulation[]; media: Media[] }
const emptySims: SimulationsData = { simulations: [], media: [] };
export function useSimulationsData(): DataState<SimulationsData> {
  return useBacked('simulations:public', async () => {
    const sims = await unwrap(db().from('simulations').select('*').eq('is_published', true).order('experiment_date', { ascending: false, nullsFirst: false }));
    const ids = sims.map((s) => s.id);
    const media = ids.length
      ? await unwrap(db().from('media_files').select('*').in('simulation_id', ids).eq('bucket_name', PUBLIC_BUCKET).order('created_at'))
      : [];
    return { simulations: sims, media };
  }, () => emptySims);
}

/* ---------------- İlerleme zaman çizelgesi ---------------- */
export interface TimelineData { updates: ProgressUpdate[]; media: Media[] }
const emptyTimeline: TimelineData = { updates: [], media: [] };
export function useTimeline(): DataState<TimelineData> {
  return useBacked('progress_updates:public', async () => {
    const updates = await unwrap(db().from('progress_updates').select('*').eq('is_published', true).order('update_date', { ascending: false }).order('created_at', { ascending: false }));
    const ids = updates.map((u) => u.id);
    const media = ids.length ? await unwrap(db().from('media_files').select('*').in('progress_update_id', ids).eq('bucket_name', PUBLIC_BUCKET)) : [];
    return { updates, media };
  }, () => emptyTimeline);
}

/* ---------------- Yayımlanan teknik belgeler ---------------- */
export interface DocumentsData { documents: TechDoc[]; files: Media[] }
const emptyDocs: DocumentsData = { documents: [], files: [] };
export function useDocumentsData(): DataState<DocumentsData> {
  return useBacked('technical_documents:public', async () => {
    const docs = await unwrap(db().from('technical_documents').select('*').eq('is_published', true).order('updated_at', { ascending: false }));
    const ids = docs.map((d) => d.file_id);
    const files = ids.length ? await unwrap(db().from('media_files').select('*').in('id', ids).eq('bucket_name', PUBLIC_BUCKET)) : [];
    return { documents: docs, files };
  }, () => emptyDocs);
}

/* ---------------- Bileşen kanıtları (görseller) ---------------- */
export function useComponentMedia(componentId: string | null): DataState<Media[]> {
  return useBacked(`media_files:component:${componentId ?? 'none'}`, async () => {
    if (!componentId) return [];
    return unwrap(db().from('media_files').select('*').eq('component_id', componentId).eq('bucket_name', PUBLIC_BUCKET).order('created_at', { ascending: false }));
  }, () => [] as Media[]);
}

export type { Component };
