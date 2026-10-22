/**
 * Tablo erişimi için ortak yardımcılar.
 * - Tüm hatalar Türkçe AppError'a dönüştürülür.
 * - RLS nedeniyle sessizce 0 satır etkilenen güncelleme/silmeler hata olarak bildirilir.
 * - İsteğe bağlı iyimser eşzamanlılık: kayıt başka biri tarafından değiştirilmişse üzerine yazılmaz.
 */
import type { Database, Tables, TablesInsert, TablesUpdate } from '../lib/database.types';
import { db } from '../lib/supabase';
import { AppError, toAppError } from '../lib/errors';
import { invalidate } from '../lib/query';

export type TableName = keyof Database['public']['Tables'];

/** Supabase yanıtını açar: hata varsa Türkçe AppError fırlatır, yoksa başarı dalındaki veriyi döndürür. */
type Success<R> = Extract<R, { error: null }> extends never ? R : Extract<R, { error: null }>;
export async function unwrap<R extends { data: unknown; error: unknown }>(p: PromiseLike<R>): Promise<Success<R>['data']> {
  const { data, error } = await p;
  if (error) throw toAppError(error);
  return data as Success<R>['data'];
}

/** `any` türlü (dinamik tablo) sorgular için açık dönüş türlü sürüm */
export async function unwrapAs<T>(p: PromiseLike<{ data: unknown; error: unknown }>): Promise<T> {
  const { data, error } = await p;
  if (error) throw toAppError(error);
  return data as T;
}

export const conflictError = () =>
  new AppError('Bu kayıt siz düzenlerken başka bir ekip üyesi tarafından değiştirildi. Güncel hâlini görmek için sayfayı yenileyip değişikliğinizi tekrar uygulayın.', 'conflict');

/* eslint-disable @typescript-eslint/no-explicit-any */
// supabase-js'in genel tablo türleri, dinamik tablo adıyla kullanıldığında TypeScript'i çok yavaşlattığı için
// iç sorgu nesnesi `any` olarak tutulur; dışa açılan imzalar üretilmiş veritabanı türleriyle tam türlüdür.
export function table<N extends TableName>(name: N, invalidates: string[] = [name]) {
  const from = () => db().from(name) as any;
  const done = () => invalidate(...invalidates, 'activity_logs');
  return {
    name,
    async list(build?: (q: any) => any): Promise<Tables<N>[]> {
      let q = from().select('*');
      if (build) q = build(q);
      return unwrapAs<Tables<N>[]>(q);
    },
    async get(id: string): Promise<Tables<N>> {
      return unwrapAs<Tables<N>>(from().select('*').eq('id', id).single());
    },
    async insert(values: TablesInsert<N>): Promise<Tables<N>> {
      const row = await unwrapAs<Tables<N>>(from().insert(values).select('*').single());
      done();
      return row;
    },
    async insertMany(values: TablesInsert<N>[]): Promise<Tables<N>[]> {
      if (values.length === 0) return [];
      const rows = await unwrapAs<Tables<N>[]>(from().insert(values).select('*'));
      done();
      return rows;
    },
    /** `expectedUpdatedAt` verilirse, kayıt o andan sonra değişmişse güncelleme reddedilir. */
    async update(id: string, patch: TablesUpdate<N>, expectedUpdatedAt?: string): Promise<Tables<N>> {
      let q = from().update(patch).eq('id', id);
      if (expectedUpdatedAt) q = q.eq('updated_at', expectedUpdatedAt);
      const rows = await unwrapAs<Tables<N>[]>(q.select('*'));
      if (rows.length === 0) {
        if (expectedUpdatedAt) {
          const { data } = await from().select('id').eq('id', id).maybeSingle();
          if (data) throw conflictError();
        }
        throw new AppError('Kayıt bulunamadı veya bu işlem için yetkiniz yok.', 'not_found');
      }
      done();
      return rows[0];
    },
    async remove(id: string): Promise<void> {
      const rows = await unwrapAs<{ id: string }[]>(from().delete().eq('id', id).select('id'));
      if (rows.length === 0) throw new AppError('Kayıt silinemedi: bulunamadı veya bu işlem için yetkiniz yok.', 'not_found');
      done();
    },
  };
}
/* eslint-enable @typescript-eslint/no-explicit-any */
