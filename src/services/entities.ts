/** Tablo başına servisler. Önbellek anahtarı ön ekleri tablo adlarıyla aynıdır. */
import type { Tables, TablesUpdate } from '../lib/database.types';
import { db } from '../lib/supabase';
import { AppError } from '../lib/errors';
import { invalidate } from '../lib/query';
import { table, unwrap } from './base';

export type Settings = Tables<'project_settings'>;
export type Phase = Tables<'project_phases'>;
export type Task = Tables<'project_tasks'>;
export type Component = Tables<'project_components'>;
export type Simulation = Tables<'simulations'>;
export type Media = Tables<'media_files'>;
export type TechDoc = Tables<'technical_documents'>;
export type Material = Tables<'materials'>;
export type Purchase = Tables<'purchases'>;
export type ProgressUpdate = Tables<'progress_updates'>;
export type Profile = Tables<'profiles'>;
export type Activity = Tables<'activity_logs'>;

export const phases = table('project_phases', ['project_phases', 'core']);
export const tasks = table('project_tasks', ['project_tasks', 'core']);
export const components = table('project_components', ['project_components', 'core']);
export const simulations = table('simulations', ['simulations']);
export const mediaRows = table('media_files', ['media_files', 'simulations', 'progress_updates', 'technical_documents']);
export const documents = table('technical_documents', ['technical_documents']);
export const materials = table('materials', ['materials']);
export const purchases = table('purchases', ['purchases', 'materials']);
export const progressUpdates = table('progress_updates', ['progress_updates']);
export const profiles = table('profiles', ['profiles']);

/* ---------- Proje ayarları (tek satır) ---------- */
export async function getSettings(): Promise<Settings | null> {
  return unwrap(db().from('project_settings').select('*').eq('id', true).maybeSingle());
}
export async function updateSettings(patch: TablesUpdate<'project_settings'>, expectedUpdatedAt?: string): Promise<Settings> {
  let q = db().from('project_settings').update(patch).eq('id', true);
  if (expectedUpdatedAt) q = q.eq('updated_at', expectedUpdatedAt);
  const rows = await unwrap(q.select('*'));
  if (!rows || rows.length === 0) {
    throw new AppError(expectedUpdatedAt ? 'Ayarlar siz düzenlerken değiştirildi. Sayfayı yenileyip tekrar deneyin.' : 'Ayarları yalnızca yönetici değiştirebilir.', 'conflict');
  }
  invalidate('project_settings', 'core');
  return rows[0];
}

/* ---------- Aşama ağırlıkları (toplam 100, sunucuda doğrulanır) ---------- */
export async function setPhaseWeights(weights: Record<string, number>) {
  await unwrap(db().rpc('set_phase_weights', { weights }));
  invalidate('project_phases', 'core');
}

/* ---------- Etkinlik günlüğü ---------- */
export async function listActivity(opts: { page: number; pageSize: number; entityType?: string; actorId?: string; search?: string }) {
  let q = db().from('activity_logs').select('*', { count: 'exact' }).order('created_at', { ascending: false });
  if (opts.entityType) q = q.eq('entity_type', opts.entityType);
  if (opts.actorId) q = q.eq('actor_id', opts.actorId);
  if (opts.search) q = q.ilike('entity_label', `%${opts.search.replace(/[%_]/g, '')}%`);
  const from = opts.page * opts.pageSize;
  const { data, error, count } = await q.range(from, from + opts.pageSize - 1);
  if (error) throw error;
  return { rows: data ?? [], total: count ?? 0 };
}
