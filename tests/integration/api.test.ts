/**
 * Uçtan uca API testleri: gerçek Supabase hizmetleri (Auth, PostgREST, Storage) üzerinden,
 * uygulamanın kullandığı supabase-js istemcisiyle. Yetki kontrolleri RLS ve Storage ilkeleri tarafından yapılır.
 *
 * Gerekli ortam değişkenleri:
 *   SUPABASE_TEST_URL, SUPABASE_TEST_ANON_KEY
 *   TEST_ADMIN_EMAIL / TEST_ADMIN_PASSWORD, TEST_EDITOR_EMAIL / ..., TEST_VIEWER_EMAIL / ...
 * Yerel kurulum için TESTING.md dosyasına bakın.
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import type { Database } from '../../src/lib/database.types';
import { randomUUID } from 'node:crypto';

const url = process.env.SUPABASE_TEST_URL;
const key = process.env.SUPABASE_TEST_ANON_KEY;
const d = url && key ? describe : describe.skip;
type C = SupabaseClient<Database>;

const mk = () => createClient<Database>(url!, key!, { auth: { persistSession: false, autoRefreshToken: false } });
async function login(role: 'ADMIN' | 'EDITOR' | 'VIEWER'): Promise<C> {
  const c = mk();
  const { error } = await c.auth.signInWithPassword({ email: process.env[`TEST_${role}_EMAIL`]!, password: process.env[`TEST_${role}_PASSWORD`]! });
  if (error) throw error;
  return c;
}
// 1×1 piksel PNG
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==', 'base64');

d('Supabase API (gerçek hizmetler)', () => {
  let anon: C, viewer: C, editor: C, admin: C;
  const cleanup: (() => Promise<unknown>)[] = [];

  beforeAll(async () => {
    anon = mk();
    [viewer, editor, admin] = await Promise.all([login('VIEWER'), login('EDITOR'), login('ADMIN')]);
  });
  afterAll(async () => { for (const f of cleanup.reverse()) await Promise.resolve(f()).catch(() => undefined); });

  it('kimlik doğrulama: hatalı parola reddedilir, oturum yenilenebilir, kayıt kapalıdır', async () => {
    const c = mk();
    const bad = await c.auth.signInWithPassword({ email: process.env.TEST_VIEWER_EMAIL!, password: 'yanlis-parola' });
    expect(bad.error?.message).toMatch(/Invalid login credentials/);
    const s1 = (await viewer.auth.getSession()).data.session!;
    const r = await viewer.auth.refreshSession();
    expect(r.error).toBeNull();
    expect(r.data.session!.refresh_token).not.toBe(s1.refresh_token); // yenileme belirteci döndürülür
    expect((await viewer.auth.getUser()).data.user?.email).toBe(process.env.TEST_VIEWER_EMAIL);
    const signup = await c.auth.signUp({ email: `yabanci-${randomUUID().slice(0, 6)}@test.local`, password: 'Uzun-Parola-123' });
    expect(signup.error).not.toBeNull(); // GOTRUE_DISABLE_SIGNUP
  });

  it('ziyaretçi herkese açık verileri okur ama yazamaz', async () => {
    const { data } = await anon.from('materials').select('id').limit(1);
    expect(data?.length).toBe(1);
    const ins = await anon.from('materials').insert({ slug: 'anon-x', name: 'X', category: 'Y' });
    expect(ins.error?.code).toBe('42501');
    const prof = await anon.from('profiles').select('*');
    expect(prof.error?.code).toBe('42501');
  });

  it('izleyici yazamaz; güncelleme sessizce 0 satır etkiler', async () => {
    const ins = await viewer.from('project_tasks').insert({ phase_id: randomUUID(), title: 'izinsiz' });
    expect(ins.error?.message).toMatch(/row-level security/);
    const up = await viewer.from('project_settings').update({ project_status: 'hack' }).eq('id', true).select();
    expect(up.data).toEqual([]);
  });

  it('düzenleyici deney oluşturur; kanıtsız “başarılı” reddedilir; yayın durumu ziyaretçi görünürlüğünü belirler', async () => {
    const comp = (await editor.from('project_components').select('id').eq('slug', 'alu').single()).data!;
    const bad = await editor.from('simulations').insert({ title: 'Kanıtsız deney', result_status: 'passed', component_id: comp.id });
    expect(bad.error?.message).toMatch(/result_needs_evidence/);
    const { data: sim, error } = await editor.from('simulations').insert({
      title: `API testi ${randomUUID().slice(0, 6)}`, component_id: comp.id, input_values: 'A=00000101 B=00000011', expected_output: '00001000',
    }).select().single();
    expect(error).toBeNull();
    cleanup.push(() => admin.from('simulations').delete().eq('id', sim!.id));
    expect((await anon.from('simulations').select('id').eq('id', sim!.id)).data).toEqual([]);
    await editor.from('simulations').update({ is_published: true }).eq('id', sim!.id);
    expect((await anon.from('simulations').select('id').eq('id', sim!.id)).data).toHaveLength(1);
  });

  it('depolama: düzenleyici yükler; izleyici ve ziyaretçi yükleyemez; yol ve tür kuralları uygulanır', async () => {
    const path = `simulation_screenshot/2026/${randomUUID()}.png`;
    const up = await editor.storage.from('public-media').upload(path, png, { contentType: 'image/png' });
    expect(up.error).toBeNull();
    cleanup.push(() => editor.storage.from('public-media').remove([path]));
    const pub = editor.storage.from('public-media').getPublicUrl(path).data.publicUrl;
    expect((await fetch(pub)).status).toBe(200);

    const v = await viewer.storage.from('public-media').upload(`simulation_screenshot/2026/${randomUUID()}.png`, png, { contentType: 'image/png' });
    expect(v.error).not.toBeNull();
    const a = await anon.storage.from('public-media').upload(`simulation_screenshot/2026/${randomUUID()}.png`, png, { contentType: 'image/png' });
    expect(a.error).not.toBeNull();
    const badPath = await editor.storage.from('public-media').upload('rastgele/klasor/resim.png', png, { contentType: 'image/png' });
    expect(badPath.error).not.toBeNull();
    const html = await editor.storage.from('public-media').upload(`report/2026/${randomUUID()}.html`, Buffer.from('<script>alert(1)</script>'), { contentType: 'text/html' });
    expect(html.error).not.toBeNull();
    const mimeSpoof = await editor.storage.from('public-media').upload(`report/2026/${randomUUID()}.pdf`, Buffer.from('<script>'), { contentType: 'text/html' });
    expect(mimeSpoof.error).not.toBeNull();
  });

  it('depolama: özel dosyalar ziyaretçiye kapalı, ekibe imzalı bağlantıyla açıktır', async () => {
    const path = `technical_file/2026/${randomUUID()}.dig`;
    const up = await editor.storage.from('private-files').upload(path, Buffer.from('<circuit/>'), { contentType: 'application/octet-stream' });
    expect(up.error).toBeNull();
    cleanup.push(() => editor.storage.from('private-files').remove([path]));
    const anonDl = await anon.storage.from('private-files').download(path);
    expect(anonDl.error).not.toBeNull();
    const anonSigned = await anon.storage.from('private-files').createSignedUrl(path, 60);
    expect(anonSigned.error).not.toBeNull();
    const signed = await viewer.storage.from('private-files').createSignedUrl(path, 60);
    expect(signed.error).toBeNull();
    expect((await fetch(signed.data!.signedUrl)).status).toBe(200);
    const del = await viewer.storage.from('private-files').remove([path]);
    expect(del.data ?? []).toEqual([]); // izleyici silemez
    expect((await editor.storage.from('private-files').download(path)).error).toBeNull();
  });

  it('depolama: açık ↔ özel taşıma (kopyala + sil) çalışır', async () => {
    const path = `breadboard_photo/2026/${randomUUID()}.png`;
    await editor.storage.from('private-files').upload(path, png, { contentType: 'image/png' });
    const cp = await editor.storage.from('private-files').copy(path, path, { destinationBucket: 'public-media' });
    expect(cp.error).toBeNull();
    await editor.storage.from('private-files').remove([path]);
    cleanup.push(() => editor.storage.from('public-media').remove([path]));
    expect((await fetch(editor.storage.from('public-media').getPublicUrl(path).data.publicUrl)).status).toBe(200);
  });

  it('satın alma kaydı malzeme adedini günceller ve etkinlik günlüğüne düşer', async () => {
    const m = (await editor.from('materials').select('id, purchased_quantity').eq('slug', 'ls02').single()).data!;
    const { data: p } = await editor.from('purchases').insert({ material_id: m.id, quantity: 2, unit_price: 21.4, currency: 'TRY', purchase_date: '2026-10-21', supplier: 'Test' }).select().single();
    cleanup.push(() => editor.from('purchases').delete().eq('id', p!.id));
    const after = (await anon.from('materials').select('purchased_quantity').eq('id', m.id).single()).data!;
    expect(after.purchased_quantity).toBe(m.purchased_quantity + 2);
    const log = await editor.from('activity_logs').select('action, actor_email').eq('entity_id', p!.id);
    expect(log.data?.[0]).toMatchObject({ action: 'purchase.recorded', actor_email: process.env.TEST_EDITOR_EMAIL });
    expect((await viewer.from('activity_logs').select('id').limit(1)).data).toEqual([]);
  });

  it('rol yönetimi: yönetici değiştirir, düzenleyici değiştiremez', async () => {
    const vid = (await viewer.auth.getUser()).data.user!.id;
    const e = await editor.from('profiles').update({ role: 'admin' }).eq('id', vid).select();
    expect(e.error?.message ?? (e.data?.length === 0 ? 'no rows' : '')).toBeTruthy();
    const a = await admin.from('profiles').update({ role: 'editor' }).eq('id', vid).select().single();
    expect(a.data?.role).toBe('editor');
    await admin.from('profiles').update({ role: 'viewer' }).eq('id', vid);
  });

  it('eşzamanlı düzenleme: eski sürüme dayanan güncelleme hiçbir satırı değiştirmez', async () => {
    const m = (await editor.from('materials').select('id, notes, updated_at').eq('slug', 'ls08').single()).data!;
    const first = await admin.from('materials').update({ notes: 'yönetici notu' }).eq('id', m.id).eq('updated_at', m.updated_at).select();
    expect(first.data).toHaveLength(1);
    const stale = await editor.from('materials').update({ notes: 'eski sürümden' }).eq('id', m.id).eq('updated_at', m.updated_at).select();
    expect(stale.data).toEqual([]); // istemci bunu "başka biri değiştirdi" hatasına çevirir
    await admin.from('materials').update({ notes: m.notes }).eq('id', m.id);
  });

  it('aşama ağırlıkları RPC ile toplam 100 olacak şekilde değişir', async () => {
    const phases = (await editor.from('project_phases').select('id, weight')).data!;
    const bad = await editor.rpc('set_phase_weights', { weights: Object.fromEntries(phases.map((p) => [p.id, 1])) });
    expect(bad.error?.message).toMatch(/toplamı 100/);
    const same = await editor.rpc('set_phase_weights', { weights: Object.fromEntries(phases.map((p) => [p.id, p.weight])) });
    expect(same.error).toBeNull();
  });
});
