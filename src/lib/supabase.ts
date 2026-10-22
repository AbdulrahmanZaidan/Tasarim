import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import type { Database } from './database.types';
import { AppError } from './errors';

const url = import.meta.env.VITE_SUPABASE_URL?.trim();
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();

/**
 * Supabase yapılandırılmamışsa site, depodaki statik verilerle (src/data) çalışmaya devam eder.
 * Yönetim paneli bu durumda kurulum yönergesini gösterir.
 */
export const isSupabaseConfigured = Boolean(url && anonKey);
export const supabaseUrl = url ?? '';
export const supabaseAnonKey = anonKey ?? '';

export type DB = SupabaseClient<Database>;

export const supabase: DB | null = isSupabaseConfigured
  ? createClient<Database>(url!, anonKey!, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, storageKey: 'sdu8bit.auth' },
    })
  : null;

export function db(): DB {
  if (!supabase) throw new AppError('Veritabanı bağlantısı yapılandırılmamış (VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY).', 'not_configured');
  return supabase;
}

export const imageTransformEnabled = import.meta.env.VITE_SUPABASE_IMAGE_TRANSFORM === 'true';
