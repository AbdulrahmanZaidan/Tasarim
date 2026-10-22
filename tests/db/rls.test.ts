/**
 * Veritabanı güvenlik testleri (RLS, tetikleyiciler, kısıtlar).
 * Gerçek bir PostgreSQL + Supabase Auth şeması üzerinde çalışır; her test bir işlem
 * (transaction) içinde yürütülüp geri alınır, veri kalıcı olarak değişmez.
 *
 * Çalıştırma:  TEST_DATABASE_URL=postgres://postgres:postgres@127.0.0.1:54322/postgres npm run test:db
 * (Yerel Supabase için: `supabase start` sonrası aynı adres kullanılabilir.)
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import pg from 'pg';
import { randomUUID } from 'node:crypto';

const url = process.env.TEST_DATABASE_URL;
const d = url ? describe : describe.skip;

type Role = 'anon' | 'viewer' | 'editor' | 'admin';

d('Veritabanı güvenliği', () => {
  const client = new pg.Client({ connectionString: url });
  const ids: Record<Exclude<Role, 'anon'>, string> = { viewer: randomUUID(), editor: randomUUID(), admin: randomUUID() };

  beforeAll(async () => {
    await client.connect();
    // Test kullanıcıları (Auth tablosuna doğrudan; tetikleyici profil oluşturur)
    for (const [role, id] of Object.entries(ids)) {
      await client.query(
        `insert into auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
         values ('00000000-0000-0000-0000-000000000000', $1, 'authenticated', 'authenticated', $2, '', now(), '{}', $3, now(), now())`,
        [id, `${role}-${id.slice(0, 8)}@test.local`, JSON.stringify({ full_name: `Test ${role}` })],
      );
      if (role !== 'viewer') await client.query(`select public.set_user_role($1, $2)`, [`${role}-${id.slice(0, 8)}@test.local`, role]);
    }
  });

  afterAll(async () => {
    await client.query(`delete from auth.users where id = any($1::uuid[])`, [Object.values(ids)]);
    // Test kullanıcılarının oluşturduğu günlük satırlarını temizle (yalnızca süper kullanıcı yapabilir)
    await client.query(`delete from activity_logs where entity_id = any($1::text[]) or actor_email like '%@test.local'`, [Object.values(ids)]);
    await client.end();
  });

  /** PostgREST'in yaptığı gibi rol ve JWT iddialarını ayarlayıp bir işlem içinde çalıştırır. */
  async function as<T>(who: Role, fn: (q: (sql: string, params?: unknown[]) => Promise<pg.QueryResult>) => Promise<T>): Promise<T> {
    await client.query('begin');
    try {
      if (who === 'anon') {
        await client.query(`select set_config('request.jwt.claims', '{"role":"anon"}', true)`);
        await client.query('set local role anon');
      } else {
        const claims = JSON.stringify({ sub: ids[who], role: 'authenticated', aud: 'authenticated' });
        await client.query(`select set_config('request.jwt.claims', $1, true), set_config('request.jwt.claim.sub', $2, true)`, [claims, ids[who]]);
        await client.query('set local role authenticated');
      }
      // Her sorgu bir kayıt noktası (savepoint) içinde çalışır; beklenen hatalar işlemi bozmaz.
      return await fn(async (sql, params) => {
        await client.query('savepoint q');
        try {
          const r = await client.query(sql, params as never[]);
          await client.query('release savepoint q');
          return r;
        } catch (e) {
          await client.query('rollback to savepoint q');
          throw e;
        }
      });
    } finally {
      await client.query('rollback');
    }
  }
  const expectError = async (p: Promise<unknown>, pattern: RegExp) => {
    await expect(p).rejects.toThrow(pattern);
  };

  it('ziyaretçi herkese açık verileri okuyabilir', async () => {
    await as('anon', async (q) => {
      expect((await q('select count(*)::int n from project_phases')).rows[0].n).toBeGreaterThanOrEqual(5);
      expect((await q('select count(*)::int n from materials')).rows[0].n).toBeGreaterThanOrEqual(40);
      expect((await q('select project_title from project_settings')).rows).toHaveLength(1);
    });
  });

  it('ziyaretçi profil ve etkinlik günlüğünü okuyamaz, yazma yapamaz', async () => {
    await as('anon', (q) => expectError(q('select * from profiles'), /permission denied/));
    await as('anon', (q) => expectError(q('select * from activity_logs'), /permission denied/));
    await as('anon', (q) => expectError(q(`insert into materials (slug, name, category) values ('x-anon', 'X', 'Y')`), /permission denied/));
    await as('anon', (q) => expectError(q(`update project_settings set project_title = 'hack'`), /permission denied/));
    await as('anon', (q) => expectError(q(`select public.set_user_role('a@b.c', 'admin')`), /permission denied/));
  });

  it('yayımlanmamış deney yalnızca ekibe görünür', async () => {
    const id = randomUUID();
    await client.query('begin');
    await client.query(`insert into simulations (id, title, is_published) values ($1, 'Gizli deney', false)`, [id]);
    await client.query(`insert into simulations (title, is_published) values ('Açık deney', true)`);
    // aynı işlem içinde rolleri değiştirerek kontrol
    await client.query(`select set_config('request.jwt.claims', '{"role":"anon"}', true)`);
    await client.query('set local role anon');
    const anon = await client.query(`select title from simulations where title in ('Gizli deney', 'Açık deney')`);
    await client.query('reset role');
    await client.query(`select set_config('request.jwt.claims', $1, true)`, [JSON.stringify({ sub: ids.viewer, role: 'authenticated' })]);
    await client.query('set local role authenticated');
    const viewer = await client.query(`select title from simulations where title in ('Gizli deney', 'Açık deney')`);
    await client.query('rollback');
    expect(anon.rows.map((r) => r.title)).toEqual(['Açık deney']);
    expect(viewer.rows.map((r) => r.title).sort()).toEqual(['Açık deney', 'Gizli deney']);
  });

  it('izleyici (viewer) içerik ekleyemez, ayarları değiştiremez, kendi rolünü yükseltemez', async () => {
    await as('viewer', (q) => expectError(q(`insert into materials (slug, name, category) values ('x-viewer', 'X', 'Y')`), /row-level security/));
    await as('viewer', async (q) => {
      const r = await q(`update project_settings set project_title = 'hack'`);
      expect(r.rowCount).toBe(0);
    });
    await as('viewer', (q) => expectError(q(`update profiles set role = 'admin' where id = $1`, [ids.viewer]), /Rol değiştirme yetkiniz yok/));
    await as('viewer', async (q) => {
      const r = await q(`update profiles set full_name = 'Yeni Ad' where id = $1 returning full_name`, [ids.viewer]);
      expect(r.rows[0].full_name).toBe('Yeni Ad');
    });
  });

  it('düzenleyici içerik ekler; oluşturan bilgisi sunucuda atanır ve günlüğe yazılır', async () => {
    await as('editor', async (q) => {
      const r = await q(`insert into simulations (title, created_by) values ('ALU toplama deneyi', $1) returning id, created_by`, [ids.admin]);
      expect(r.rows[0].created_by).toBe(ids.editor); // sahte "created_by" yok sayılır
      const log = await q(`select action, actor_id, entity_label from activity_logs where entity_id = $1`, [r.rows[0].id]);
      expect(log.rows[0]).toMatchObject({ action: 'simulation.created', actor_id: ids.editor, entity_label: 'ALU toplama deneyi' });
    });
  });

  it('kimse etkinlik günlüğüne doğrudan yazamaz veya silemez', async () => {
    await as('admin', (q) => expectError(q(`insert into activity_logs (action, entity_type) values ('sahte', 'x')`), /permission denied/));
    await as('admin', (q) => expectError(q(`delete from activity_logs`), /permission denied/));
    await as('viewer', async (q) => {
      expect((await q('select count(*)::int n from activity_logs')).rows[0].n).toBe(0); // izleyici günlüğü görmez
    });
  });

  it('düzenleyici proje ayarlarını değiştiremez, yönetici değiştirebilir', async () => {
    await as('editor', async (q) => expect((await q(`update project_settings set academic_year = '2026–2027'`)).rowCount).toBe(0));
    await as('admin', async (q) => {
      const r = await q(`update project_settings set academic_year = '2026–2027' returning updated_by`);
      expect(r.rowCount).toBe(1);
      expect(r.rows[0].updated_by).toBe(ids.admin);
    });
  });

  it('yönetici rol değiştirebilir; düzenleyici değiştiremez', async () => {
    await as('editor', (q) => expectError(q(`update profiles set role = 'admin' where id = $1`, [ids.editor]), /Rol değiştirme yetkiniz yok/));
    await as('admin', async (q) => {
      const r = await q(`update profiles set role = 'editor' where id = $1 returning role`, [ids.viewer]);
      expect(r.rows[0].role).toBe('editor');
      const log = await q(`select action from activity_logs where entity_id = $1`, [ids.viewer]);
      expect(log.rows.map((x) => x.action)).toContain('profile.role_changed');
    });
  });

  it('son yönetici düşürülemez', async () => {
    // Bu testte sistemdeki tek yönetici test yöneticisidir; başka yönetici varsa test atlanır.
    const admins = (await client.query(`select count(*)::int n from profiles where role = 'admin'`)).rows[0].n;
    if (admins !== 1) return;
    await as('admin', (q) => expectError(q(`update profiles set role = 'viewer' where id = $1`, [ids.admin]), /en az bir yönetici/));
  });

  it('satın almalar satın alınan adedi günceller; doğrudan değiştirilemez', async () => {
    await as('editor', async (q) => {
      const m = (await q(`select id from materials where slug = 'ls00'`)).rows[0].id;
      await q(`insert into purchases (material_id, quantity, unit_price, currency, purchase_date) values ($1, 2, 18.5, 'TRY', '2026-10-21')`, [m]);
      await q(`insert into purchases (material_id, quantity, purchase_date) values ($1, 3, '2026-10-22')`, [m]);
      expect((await q(`select purchased_quantity from materials where id = $1`, [m])).rows[0].purchased_quantity).toBe(5);
      await q(`update materials set purchased_quantity = 999 where id = $1`, [m]);
      expect((await q(`select purchased_quantity from materials where id = $1`, [m])).rows[0].purchased_quantity).toBe(5);
      await q(`delete from purchases where material_id = $1 and quantity = 3`, [m]);
      expect((await q(`select purchased_quantity from materials where id = $1`, [m])).rows[0].purchased_quantity).toBe(2);
      await expectError(q(`delete from materials where id = $1`, [m]), /violates foreign key/);
    });
  });

  it('satın alma kaydı izleyicinin adına sahte olarak giriliyor olsa bile eylem günlüğü gerçek kullanıcıyı yazar', async () => {
    await as('editor', async (q) => {
      const m = (await q(`select id from materials where slug = 'ls04'`)).rows[0].id;
      const p = await q(`insert into purchases (material_id, quantity, purchase_date, purchased_by) values ($1, 1, '2026-10-22', $2) returning id`, [m, ids.viewer]);
      const log = await q(`select actor_id, action from activity_logs where entity_id = $1`, [p.rows[0].id]);
      expect(log.rows[0]).toMatchObject({ actor_id: ids.editor, action: 'purchase.recorded' });
    });
  });

  it('kanıt olmadan deney “Başarılı” işaretlenemez', async () => {
    await as('editor', (q) => expectError(q(`insert into simulations (title, result_status) values ('Kanıtsız', 'passed')`), /result_needs_evidence/));
    await as('editor', async (q) => {
      const r = await q(`insert into simulations (title, result_status, actual_output, experiment_date) values ('Kanıtlı', 'passed', '00001000', '2026-10-22') returning result_status`);
      expect(r.rows[0].result_status).toBe('passed');
    });
  });

  it('aşama ağırlıkları yalnızca toplamı 100 olacak biçimde topluca değişir', async () => {
    await as('editor', (q) => expectError(q(`update project_phases set weight = 50 where slug = 'github'`), /Ağırlıkları kaydet/));
    await as('editor', async (q) => {
      const phases = (await q(`select id from project_phases order by sort_order`)).rows;
      const bad = Object.fromEntries(phases.map((p) => [p.id, 10]));
      await expectError(q(`select public.set_phase_weights($1::jsonb)`, [JSON.stringify(bad)]), /toplamı 100/);
    });
    await as('editor', async (q) => {
      const phases = (await q(`select id from project_phases order by sort_order`)).rows;
      const ok = Object.fromEntries(phases.map((p, i) => [p.id, i === 0 ? 100 - 15 * (phases.length - 1) : 15]));
      await q(`select public.set_phase_weights($1::jsonb)`, [JSON.stringify(ok)]);
      expect((await q(`select sum(weight)::numeric s from project_phases`)).rows[0].s).toBe('100.00');
    });
    await as('viewer', async (q) => {
      const phases = (await q(`select id from project_phases`)).rows;
      const ok = Object.fromEntries(phases.map((p) => [p.id, 100 / phases.length]));
      await expectError(q(`select public.set_phase_weights($1::jsonb)`, [JSON.stringify(ok)]), /düzenleme yetkisi/);
    });
  });

  it('görev tamamlanınca tarih atanır, geri alınınca temizlenir', async () => {
    await as('editor', async (q) => {
      const ph = (await q(`select id from project_phases where slug = 'architecture'`)).rows[0].id;
      const t = (await q(`insert into project_tasks (phase_id, title) values ($1, 'Test görevi') returning id, completed_at`, [ph])).rows[0];
      expect(t.completed_at).toBeNull();
      const c = (await q(`update project_tasks set status = 'completed' where id = $1 returning completed_at`, [t.id])).rows[0];
      expect(c.completed_at).not.toBeNull();
      const log = await q(`select action from activity_logs where entity_id = $1 order by id`, [t.id]);
      expect(log.rows.map((x) => x.action)).toEqual(['task.created', 'task.completed']);
      const u = (await q(`update project_tasks set status = 'in_progress' where id = $1 returning completed_at`, [t.id])).rows[0];
      expect(u.completed_at).toBeNull();
    });
  });

  it('yayımlanan belgenin dosyası herkese açık olmalı; kullanılan dosya silinemez', async () => {
    await as('editor', async (q) => {
      const ins = (bucket: string) => q(
        `insert into media_files (file_name, original_file_name, storage_path, bucket_name, mime_type, file_size, title, category)
         values ($1, 'rapor.pdf', $2, $3, 'application/pdf', 1000, 'Rapor', 'report') returning id`,
        [`${randomUUID()}.pdf`.replace(/^/, ''), `report/2026/${randomUUID()}.pdf`, bucket],
      );
      // file_name ile storage_path aynı uuid'yi taşımak zorunda değildir; biçim kontrolü yeterli
      const priv = (await ins('private-files')).rows[0].id;
      const pub = (await ins('public-media')).rows[0].id;
      await expectError(q(`insert into technical_documents (title, document_type, file_id, is_published) values ('Gizli', 'project_report', $1, true)`, [priv]), /herkese açık medya/);
      const doc = (await q(`insert into technical_documents (title, document_type, file_id, is_published) values ('Açık', 'project_report', $1, true) returning id`, [pub])).rows[0].id;
      await expectError(q(`update media_files set bucket_name = 'private-files' where id = $1`, [pub]), /yayımlanmış bir belgede/);
      await expectError(q(`delete from media_files where id = $1`, [pub]), /violates foreign key/);
      await q(`delete from technical_documents where id = $1`, [doc]);
      expect((await q(`delete from media_files where id = $1`, [pub])).rowCount).toBe(1);
    });
  });

  it('medya kayıtlarında yol ve boyut kuralları uygulanır', async () => {
    await as('editor', (q) => expectError(q(
      `insert into media_files (file_name, original_file_name, storage_path, bucket_name, mime_type, file_size, title, category)
       values ('x.png', 'x.png', '../etc/passwd', 'public-media', 'image/png', 10, 'x', 'report')`), /check constraint/));
    await as('editor', (q) => expectError(q(
      `insert into media_files (file_name, original_file_name, storage_path, bucket_name, mime_type, file_size, title, category)
       values ($1, 'x.png', $2, 'public-media', 'image/png', 60000000, 'x', 'report')`, [`${randomUUID()}.png`, `report/2026/${randomUUID()}.png`]), /check constraint/));
  });

  it('depolama yolu kuralı kategori klasörü ve uzantıyı denetler', async () => {
    const ok = (b: string, n: string) => client.query(`select public.storage_path_allowed($1, $2) ok`, [b, n]).then((r) => r.rows[0].ok);
    const u = randomUUID();
    expect(await ok('public-media', `simulation_screenshot/2026/${u}.png`)).toBe(true);
    expect(await ok('public-media', `technical_file/2026/${u}.dig`)).toBe(true); // indirilebilir simülasyon dosyası
    expect(await ok('public-media', `technical_file/2026/${u}.xml`)).toBe(false); // tarayıcıda yorumlanabilen tür açık depoya giremez
    expect(await ok('public-media', `report/2026/${u}.html`)).toBe(false);
    expect(await ok('private-files', `technical_file/2026/${u}.dig`)).toBe(true);
    expect(await ok('private-files', `technical_file/2026/${u}.exe`)).toBe(false);
    expect(await ok('private-files', `baska_klasor/2026/${u}.pdf`)).toBe(false);
    expect(await ok('public-media', `report/2026/../${u}.pdf`)).toBe(false);
  });
});
