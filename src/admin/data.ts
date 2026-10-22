/** Yönetim paneli veri kancaları (ortak önbellek; değişikliklerde ilgili anahtarlar yenilenir). */
import { useQuery } from '../lib/query';
import { db } from '../lib/supabase';
import { unwrap } from '../services/base';
import { getSettings } from '../services/entities';

export const usePhases = () => useQuery('project_phases:admin', async () => unwrap(db().from('project_phases').select('*').order('semester').order('sort_order')));
export const useTasks = () => useQuery('project_tasks:admin', async () => unwrap(db().from('project_tasks').select('*').order('sort_order').order('created_at')));
export const useComponents = () => useQuery('project_components:admin', async () => unwrap(db().from('project_components').select('*').order('sort_order')));
export const useSimulations = () => useQuery('simulations:admin', async () => unwrap(db().from('simulations').select('*').order('updated_at', { ascending: false })));
export const useMediaList = () => useQuery('media_files:admin', async () => unwrap(db().from('media_files').select('*').order('created_at', { ascending: false })));
export const useDocuments = () => useQuery('technical_documents:admin', async () => unwrap(db().from('technical_documents').select('*').order('updated_at', { ascending: false })));
export const useMaterials = () => useQuery('materials:admin', async () => unwrap(db().from('materials').select('*').order('sort_order').order('name')));
export const usePurchases = () => useQuery('purchases:admin', async () => unwrap(db().from('purchases').select('*').order('purchase_date', { ascending: false }).order('created_at', { ascending: false })));
export const useProgressUpdates = () => useQuery('progress_updates:admin', async () => unwrap(db().from('progress_updates').select('*').order('update_date', { ascending: false })));
export const useProfiles = () => useQuery('profiles:admin', async () => unwrap(db().from('profiles').select('*').order('full_name')));
export const useSettings = () => useQuery('project_settings:admin', getSettings);
export const useRecentActivity = (enabled: boolean, limit = 8) =>
  useQuery(enabled ? `activity_logs:recent:${limit}` : null, async () => unwrap(db().from('activity_logs').select('*').order('created_at', { ascending: false }).limit(limit)), { staleMs: 15_000 });
