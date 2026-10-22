// Veritabanı şemasından TypeScript türleri üretir (Supabase `gen types` çıktısıyla aynı biçim).
// Kullanım: DATABASE_URL=postgres://... node scripts/gen-types.mjs
// Alternatif (Supabase CLI ile): npx supabase gen types typescript --project-id <id> > src/lib/database.types.ts
import pg from 'pg';
import { writeFileSync } from 'node:fs';

const url = process.env.DATABASE_URL;
if (!url) { console.error('DATABASE_URL gerekli'); process.exit(1); }
const c = new pg.Client({ connectionString: url });
await c.connect();

const enums = (await c.query(`
  select t.typname as name, array_agg(e.enumlabel::text order by e.enumsortorder)::text[] as vals
  from pg_type t join pg_enum e on e.enumtypid = t.oid join pg_namespace n on n.oid = t.typnamespace
  where n.nspname = 'public' group by t.typname order by t.typname`)).rows;
const enumNames = new Set(enums.map((e) => e.name));

const cols = (await c.query(`
  select c.table_name, c.column_name, c.data_type, c.udt_name, c.is_nullable = 'YES' as nullable,
         c.column_default is not null as has_default, c.is_identity = 'YES' as identity,
         c.is_generated = 'ALWAYS' as generated, c.ordinal_position, t.table_type
  from information_schema.columns c
  join information_schema.tables t on t.table_schema = c.table_schema and t.table_name = c.table_name
  where c.table_schema = 'public' order by c.table_name, c.column_name`)).rows;

const fks = (await c.query(`
  select con.conname, cl.relname as tbl, ref.relname as ref_tbl,
    array(select a.attname from unnest(con.conkey) k join pg_attribute a on a.attrelid = con.conrelid and a.attnum = k)::text[] as cols,
    array(select a.attname from unnest(con.confkey) k join pg_attribute a on a.attrelid = con.confrelid and a.attnum = k)::text[] as ref_cols,
    exists (select 1 from pg_index i where i.indrelid = con.conrelid and i.indisunique
            and (select array_agg(x order by x) from unnest(i.indkey::int2[]) x) = (select array_agg(x order by x) from unnest(con.conkey) x)) as one_to_one
  from pg_constraint con join pg_class cl on cl.oid = con.conrelid join pg_class ref on ref.oid = con.confrelid
  join pg_namespace n on n.oid = cl.relnamespace
  where con.contype = 'f' and n.nspname = 'public' and ref.relnamespace = n.oid order by cl.relname, con.conname`)).rows;

const fns = (await c.query(`
  select p.proname as name, pg_get_function_arguments(p.oid) as args, pg_get_function_result(p.oid) as ret
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public' and p.prokind = 'f' and pg_get_function_result(p.oid) <> 'trigger'
    and p.proname in ('set_phase_weights', 'current_app_role', 'is_admin', 'can_edit', 'can_view_private')
  order by p.proname`)).rows;
await c.end();

const tsType = (col) => {
  if (col.data_type === 'USER-DEFINED' && enumNames.has(col.udt_name)) return `Database["public"]["Enums"]["${col.udt_name}"]`;
  if (col.data_type === 'ARRAY') return 'string[]';
  switch (col.udt_name) {
    case 'int2': case 'int4': case 'int8': case 'numeric': case 'float4': case 'float8': return 'number';
    case 'bool': return 'boolean';
    case 'json': case 'jsonb': return 'Json';
    default: return 'string';
  }
};
const pgToTs = (t) => (t === 'jsonb' || t === 'json' ? 'Json' : t === 'boolean' ? 'boolean' : t === 'void' ? 'undefined'
  : /^(integer|bigint|numeric|smallint)/.test(t) ? 'number' : t.startsWith('app_role') || t.startsWith('public.app_role') ? 'Database["public"]["Enums"]["app_role"]' : 'string');

const byTable = {};
for (const col of cols) (byTable[col.table_name] ??= { type: col.table_type, cols: [] }).cols.push(col);

const ind = (n) => ' '.repeat(n);
let tables = '', views = '';
for (const [name, t] of Object.entries(byTable)) {
  const row = t.cols.map((c) => `${ind(10)}${c.column_name}: ${tsType(c)}${c.nullable ? ' | null' : ''}`).join('\n');
  const ins = t.cols.map((c) => c.generated ? `${ind(10)}${c.column_name}?: never`
    : `${ind(10)}${c.column_name}${c.nullable || c.has_default || c.identity ? '?' : ''}: ${tsType(c)}${c.nullable ? ' | null' : ''}`).join('\n');
  const upd = t.cols.map((c) => c.generated ? `${ind(10)}${c.column_name}?: never` : `${ind(10)}${c.column_name}?: ${tsType(c)}${c.nullable ? ' | null' : ''}`).join('\n');
  const rels = fks.filter((f) => f.tbl === name).map((f) => `${ind(10)}{
${ind(12)}foreignKeyName: "${f.conname}"
${ind(12)}columns: [${f.cols.map((x) => `"${x}"`).join(', ')}]
${ind(12)}isOneToOne: ${f.one_to_one}
${ind(12)}referencedRelation: "${f.ref_tbl}"
${ind(12)}referencedColumns: [${f.ref_cols.map((x) => `"${x}"`).join(', ')}]
${ind(10)}},`).join('\n');
  const block = `${ind(6)}${name}: {
${ind(8)}Row: {
${row}
${ind(8)}}
${t.type === 'BASE TABLE' ? `${ind(8)}Insert: {
${ins}
${ind(8)}}
${ind(8)}Update: {
${upd}
${ind(8)}}
` : ''}${ind(8)}Relationships: [${rels ? `\n${rels}\n${ind(8)}` : ''}]
${ind(6)}}
`;
  if (t.type === 'BASE TABLE') tables += block; else views += block;
}

const parseArgs = (a) => (a ? `{ ${a.split(',').map((x) => { const [n, ...ty] = x.trim().split(' '); return `${n}: ${pgToTs(ty.join(' '))}`; }).join('; ')} }` : 'never');
const functions = fns.map((f) => `${ind(6)}${f.name}: {
${ind(8)}Args: ${parseArgs(f.args)}
${ind(8)}Returns: ${pgToTs(f.ret)}
${ind(6)}}`).join('\n');

const out = `// Bu dosya scripts/gen-types.mjs ile veritabanı şemasından üretilmiştir. Elle düzenlemeyin.
export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[]

export type Database = {
  public: {
    Tables: {
${tables}    }
    Views: {
${views || `${ind(6)}[_ in never]: never\n`}    }
    Functions: {
${functions}
    }
    Enums: {
${enums.map((e) => `${ind(6)}${e.name}: ${e.vals.map((v) => `"${v}"`).join(' | ')}`).join('\n')}
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type PublicSchema = Database["public"]
export type Tables<T extends keyof PublicSchema["Tables"]> = PublicSchema["Tables"][T]["Row"]
export type TablesInsert<T extends keyof PublicSchema["Tables"]> = PublicSchema["Tables"][T]["Insert"]
export type TablesUpdate<T extends keyof PublicSchema["Tables"]> = PublicSchema["Tables"][T]["Update"]
export type Enums<T extends keyof PublicSchema["Enums"]> = PublicSchema["Enums"][T]
`;
writeFileSync(new URL('../src/lib/database.types.ts', import.meta.url), out);
console.log(`türler: ${Object.keys(byTable).length} tablo, ${enums.length} enum, ${fns.length} fonksiyon`);
