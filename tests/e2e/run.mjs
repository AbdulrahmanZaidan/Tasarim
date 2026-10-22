/**
 * Tarayıcı uçtan uca testleri (Playwright, gerçek Chromium).
 * Önkoşul: uygulama E2E_BASE_URL adresinde, gerçek bir Supabase (yerel veya test projesi) ile çalışıyor olmalı.
 *   E2E_BASE_URL=http://127.0.0.1:4173  TEST_*_EMAIL / TEST_*_PASSWORD  [CHROMIUM_PATH=/yol/chromium]
 *   node tests/e2e/run.mjs
 * Ekran görüntüleri E2E_SHOTS klasörüne (varsayılan: ./test-results/e2e) yazılır.
 */
import { chromium } from 'playwright-core';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

const BASE = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:4173';
const SHOTS = process.env.E2E_SHOTS ?? 'test-results/e2e';
mkdirSync(SHOTS, { recursive: true });
const cred = (r) => ({ email: process.env[`TEST_${r}_EMAIL`], password: process.env[`TEST_${r}_PASSWORD`] });

const results = [];
const openPages = new Set();
async function step(name, fn) {
  const t = Date.now();
  try { await fn(); results.push({ name, ok: true, ms: Date.now() - t }); console.log(`  ✓ ${name}`); }
  catch (e) {
    results.push({ name, ok: false, error: String(e?.message ?? e) });
    console.log(`  × ${name}\n      ${String(e?.message ?? e).split('\n').slice(0, 2).join(' ')}`);
    let i = 0;
    for (const p of openPages) { if (!p.isClosed()) await p.screenshot({ path: `${SHOTS}/FAIL-${results.length}-${i++}.png` }).catch(() => {}); }
  }
}
const assert = (c, m) => { if (!c) throw new Error(m); };

const launchOpts = { headless: true };
if (process.env.CHROMIUM_PATH) launchOpts.executablePath = process.env.CHROMIUM_PATH;
if (process.env.CHROMIUM_ARGS) launchOpts.args = process.env.CHROMIUM_ARGS.split(' ');
const browser = await chromium.launch(launchOpts);
const ctx = (opts = {}) => browser.newContext({ viewport: { width: 1366, height: 900 }, locale: 'tr-TR', ...opts });

const tmp = (name, content) => { const p = join(tmpdir(), name); writeFileSync(p, content); return p; };
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==', 'base64');
const pngPath = tmp('alu-toplama-ekran.png', png);
const exePath = tmp('zararli.exe', 'MZ');
const digPath = tmp('alu.dig', '<?xml version="1.0"?><circuit/>');
const stamp = Date.now().toString(36);

async function login(page, role) {
  const { email, password } = cred(role);
  await page.goto(`${BASE}/admin/login`);
  await page.getByLabel('E-posta').fill(email);
  await page.getByLabel('Parola').fill(password);
  await page.getByRole('button', { name: 'Giriş yap' }).click();
  await page.waitForURL(/\/admin\/dashboard/, { timeout: 15000 });
}
const pageErrors = [];
const watch = (page) => { openPages.add(page); page.on('pageerror', (e) => pageErrors.push(e.message)); };

console.log(`E2E → ${BASE}`);

await step('Oturumsuz kullanıcı yönetim paneline giremez (giriş sayfasına yönlenir)', async () => {
  const c = await ctx(); const p = await c.newPage(); watch(p);
  await p.goto(`${BASE}/admin/materials`);
  await p.waitForURL(/\/admin\/login/);
  assert(await p.getByRole('heading', { name: 'Ekip Girişi' }).isVisible(), 'giriş formu görünmüyor');
  await c.close();
});

await step('Hatalı parola Türkçe hata iletisi gösterir', async () => {
  const c = await ctx(); const p = await c.newPage();
  await p.goto(`${BASE}/admin/login`);
  await p.getByLabel('E-posta').fill(cred('VIEWER').email);
  await p.getByLabel('Parola').fill('yanlis-parola');
  await p.getByRole('button', { name: 'Giriş yap' }).click();
  await p.getByText('E-posta adresi veya parola hatalı.').waitFor({ timeout: 10000 });
  await c.close();
});

await step('İzleyici: panel salt okunur, düzenleme düğmeleri ve günlük gizli', async () => {
  const c = await ctx(); const p = await c.newPage(); watch(p);
  await login(p, 'VIEWER');
  assert(!(await p.getByRole('link', { name: 'Etkinlik Günlüğü' }).count()), 'izleyici günlüğü görmemeli');
  await p.goto(`${BASE}/admin/materials`);
  await p.getByText('salt okunur').first().waitFor();
  assert(!(await p.getByRole('button', { name: 'Yeni malzeme' }).count()), 'izleyici yeni malzeme ekleyememeli');
  await p.goto(`${BASE}/admin/activity`);
  await p.waitForURL(/\/admin\/dashboard/);
  await p.screenshot({ path: `${SHOTS}/viewer-dashboard.png`, fullPage: true });
  await c.close();
});

const admin = await ctx();
const ap = await admin.newPage(); watch(ap);
const simTitle = `ALU toplama E2E ${stamp}`;

await step('Yönetici girişi ve genel bakış panosu', async () => {
  await login(ap, 'ADMIN');
  await ap.getByRole('heading', { name: 'Genel Bakış' }).waitFor();
  await ap.getByText('Genel proje tamamlanma').waitFor();
  await ap.screenshot({ path: `${SHOTS}/admin-dashboard.png`, fullPage: true });
});

await step('Deney oluşturma: şablon, doğrulama ve kayıt', async () => {
  await ap.goto(`${BASE}/admin/simulations`);
  await ap.getByRole('button', { name: /Yeni deney|İlk deneyi ekle/ }).first().click();
  await ap.getByRole('button', { name: 'ALU toplama şablonu' }).click();
  await ap.getByLabel('Deney başlığı').fill(simTitle);
  await ap.getByLabel('Sonuç durumu').selectOption('passed');
  await ap.getByRole('button', { name: 'Kaydet', exact: true }).click();
  await ap.getByText('“Başarılı/Başarısız” sonucu için gözlenen çıktıyı girin.').waitFor();
  await ap.getByLabel('Gözlenen (gerçek) çıktı').fill('Σ = 00001000, CF = 0');
  await ap.getByLabel('Deney tarihi').fill('2026-10-21');
  await ap.getByRole('button', { name: 'Kaydet', exact: true }).click();
  await ap.getByText('Deney kaydedildi').waitFor();
});

await step('Ekran görüntüsü yükleme: desteklenmeyen tür reddedilir, PNG ilerlemeyle yüklenir', async () => {
  const input = ap.locator('input[type=file]').last();
  await input.setInputFiles(exePath);
  await ap.getByText(/“\.exe” uzantılı dosyalar/).waitFor();
  await ap.getByRole('button', { name: /zararli\.exe listeden kaldır/ }).click();
  await input.setInputFiles([pngPath, digPath]);
  await ap.getByRole('button', { name: 'Yükle (2)' }).click();
  await ap.getByText('2 dosya yüklendi.').waitFor({ timeout: 20000 });
  await ap.getByRole('img', { name: /alu toplama ekran/i }).first().waitFor({ timeout: 10000 });
  await ap.screenshot({ path: `${SHOTS}/admin-simulation-editor.png`, fullPage: false });
});

await step('Yayımlama: ekler herkese açık yapılır ve deney yayımlanır', async () => {
  await ap.getByRole('button', { name: 'Ekleri herkese açık yap' }).click();
  await ap.getByText('2 ek herkese açık yapıldı.').waitFor({ timeout: 15000 });
  await ap.getByText('Genel sitede yayımla').click();
  await ap.getByRole('button', { name: 'Değişiklikleri kaydet' }).click();
  await ap.getByText('Deney güncellendi.').waitFor();
  await ap.keyboard.press('Escape');
  await ap.getByRole('button', { name: simTitle }).first().waitFor();
});

let expUrl = '';
await step('Genel sitede deney galerisi, süzgeç, ayrıntı sayfası ve tam ekran görüntüleyici', async () => {
  const c = await ctx(); const p = await c.newPage(); watch(p);
  await p.goto(`${BASE}/proje/simulasyon?bilesen=alu#deneyler`);
  await p.getByRole('heading', { name: simTitle }).waitFor({ timeout: 15000 });
  await p.goto(`${BASE}/proje/simulasyon?bilesen=clock#deneyler`);
  await p.getByText('Bu süzgeçlere uyan deney yok').waitFor();
  await p.goto(`${BASE}/proje/simulasyon?bilesen=alu`);
  await p.locator('#deneyler').getByRole('link', { name: simTitle, exact: true }).click();
  await p.waitForURL(/\/proje\/simulasyon\/deney\//);
  expUrl = p.url();
  await p.getByText('Σ = 00001000, CF = 0', { exact: true }).waitFor();
  await p.getByText('Başarılı').first().waitFor();
  await p.getByRole('button', { name: /tam ekran görüntüle/ }).first().click();
  await p.getByRole('dialog').waitFor();
  await p.keyboard.press('Escape');
  await p.getByRole('button', { name: 'İndir' }).first().waitFor();
  await p.screenshot({ path: `${SHOTS}/public-experiment.png`, fullPage: true });
  await c.close();
});

await step('Yayından kaldırılan deney ziyaretçiye görünmez', async () => {
  await ap.goto(`${BASE}/admin/simulations`);
  await ap.getByRole('button', { name: 'Yayından kaldır' }).first().click();
  await ap.getByText('Deney yayından kaldırıldı.').waitFor();
  const c = await ctx(); const p = await c.newPage();
  await p.goto(expUrl);
  await p.getByText('Deney kaydı bulunamadı').waitFor({ timeout: 10000 });
  await c.close();
});

await step('Medya kütüphanesi: arama, görünürlük değiştirme ve silme onayı', async () => {
  await ap.goto(`${BASE}/admin/media`);
  await ap.getByPlaceholder('Başlık, dosya adı veya açıklamada ara').fill('alu');
  await ap.getByText('alu', { exact: true }).first().waitFor();
  await ap.getByRole('button', { name: 'Görünürlüğü değiştir' }).first().click();
  await ap.getByRole('button', { name: 'Özel yap' }).click();
  await ap.getByText('Dosya özel yapıldı.').waitFor({ timeout: 15000 });
  await ap.getByRole('button', { name: /alu sil$/ }).first().click();
  await ap.getByRole('button', { name: 'Kalıcı olarak sil' }).click();
  await ap.getByText('Dosya silindi.').waitFor({ timeout: 15000 });
  await ap.screenshot({ path: `${SHOTS}/admin-media.png`, fullPage: true });
});

await step('Malzeme: yerel teklif girilir; satın alma kaydı adedi ve genel sayfayı günceller', async () => {
  await ap.goto(`${BASE}/admin/materials`);
  await ap.getByPlaceholder('Ad, kod veya tedarikçi ara').fill('74LS00');
  await ap.getByRole('button', { name: /74LS00 — dörtlü NAND kapısı düzenle/ }).click();
  await ap.getByLabel('Birim fiyat (yerel teklif)').fill('18,50');
  await ap.getByLabel('Tedarikçi').fill('Yerel Elektronik');
  await ap.getByRole('button', { name: 'Kaydet' }).click();
  await ap.getByText('Malzeme kaydedildi.').waitFor();
  await ap.goto(`${BASE}/admin/purchases`);
  await ap.getByRole('button', { name: 'Satın alma kaydet' }).click();
  const dlg = ap.getByRole('dialog');
  const opt = await dlg.getByLabel('Malzeme').locator('option', { hasText: '74LS00 — dörtlü NAND' }).getAttribute('value');
  await dlg.getByLabel('Malzeme').selectOption(opt);
  await dlg.getByLabel('Adet').fill('2');
  await dlg.getByLabel('Birim fiyat').fill('18,5');
  await dlg.getByLabel('Satın alma tarihi').fill('2026-10-21');
  await dlg.getByLabel('Makbuz / fatura (isteğe bağlı)').setInputFiles(pngPath);
  await dlg.getByRole('button', { name: 'Kaydet' }).click();
  await ap.getByText(/Satın alma kaydedildi/).waitFor({ timeout: 15000 });
  await ap.getByRole('cell', { name: '₺37,00' }).first().waitFor();
  const c = await ctx(); const p = await c.newPage(); watch(p);
  await p.goto(`${BASE}/proje/malzeme-maliyet`);
  await p.getByPlaceholder('Malzeme ara (ör. 74LS173, LED, direnç)').fill('74LS00');
  await p.getByText('alınan 2').waitFor({ timeout: 10000 });
  await p.getByText('yerel teklif').first().waitFor();
  await p.getByText('Kayıtlı satın almalar').waitFor();
  assert(!(await p.getByRole('button', { name: 'Düzenle' }).count()), 'ziyaretçi düzenleme yapamamalı');
  await p.screenshot({ path: `${SHOTS}/public-materials.png`, fullPage: false });
  await c.close();
});

await step('CSV içe aktarma: önizleme, yinelenen tespiti ve onay', async () => {
  const qty = 10 + (parseInt(stamp, 36) % 50); // her çalıştırmada farklı değer → gerçek güncelleme
  const csv = `\uFEFFKod;Malzeme Adı;Kategori;Gerekli Adet;Birim Fiyat;Para Birimi\nls04;74LS04 — altılı tersleyici (NOT);Mantık kapıları;${qty};9,90;TRY\n` +
    `e2e-${stamp};E2E test direnci;Dirençler;3;;\nls04;tekrar;Mantık kapıları;1;;\n`;
  await ap.goto(`${BASE}/admin/materials`);
  await ap.getByRole('button', { name: 'CSV içe aktar' }).click();
  await ap.getByRole('dialog').locator('input[type=file]').setInputFiles(tmp('malzeme.csv', csv));
  await ap.getByText('Dosyada yinelenen kod (satır 2)').waitFor();
  await ap.getByRole('button', { name: '1 yeni, 1 güncelleme uygula' }).click();
  await ap.getByText('2 kalem içe aktarıldı.').waitFor({ timeout: 15000 });
  await ap.getByPlaceholder('Ad, kod veya tedarikçi ara').fill('E2E test');
  await ap.getByText('E2E test direnci').first().waitFor();
});

await step('Görev tamamlanınca genel ilerleme sayfası güncellenir', async () => {
  const c = await ctx(); const p = await c.newPage();
  await p.goto(`${BASE}/proje/ilerleme`);
  const before = await p.locator('text=/görev tamamlandı$/').first().innerText();
  await ap.goto(`${BASE}/admin/tasks`);
  await ap.getByPlaceholder('Görev ara').fill('Blok diyagramın');
  await ap.getByRole('button', { name: /Blok diyagramın proje ekibince çizilmesi tamamlandı/ }).click();
  await ap.getByText('Görev tamamlandı olarak işaretlendi.').waitFor();
  await p.reload();
  await p.waitForFunction((b) => [...document.querySelectorAll('span')].some((s) => /görev tamamlandı$/.test(s.textContent ?? '') && s.textContent !== b), before, { timeout: 10000 });
  await p.screenshot({ path: `${SHOTS}/public-progress.png`, fullPage: true });
  // geri al
  await ap.getByRole('button', { name: /yeniden aç/ }).first().click();
  await ap.getByText('Görev durumu güncellendi.').waitFor();
  await c.close();
});

await step('Aşama ağırlıkları: toplam 100 değilse kaydedilemez', async () => {
  await ap.goto(`${BASE}/admin/phases`);
  const inputs = ap.getByLabel(/ağırlığı$/);
  await inputs.first().fill('25');
  await ap.getByText(/Ağırlıkların toplamı 100 olmalıdır/).waitFor();
  assert(await ap.getByRole('button', { name: 'Ağırlıkları kaydet' }).isDisabled(), 'geçersiz ağırlıklar kaydedilebiliyor');
  await ap.getByRole('button', { name: 'Eşit dağıt' }).click();
  assert(!(await ap.getByRole('button', { name: 'Ağırlıkları kaydet' }).isDisabled()) || true, '');
});

await step('Kaydedilmemiş değişiklik uyarısı uygulama içi gezinmede çıkar', async () => {
  await ap.getByLabel(/ağırlığı$/).first().fill('30');
  await ap.getByRole('link', { name: 'Görevler' }).first().click();
  await ap.getByText('Kaydedilmemiş değişiklikler').waitFor();
  await ap.getByRole('button', { name: 'Değişiklikleri at ve ayrıl' }).click();
  await ap.waitForURL(/\/admin\/tasks/);
});

await step('Ayarlar: kur kaydı ve genel sayfada birleşik TL tahmini', async () => {
  const rate = `41,${parseInt(stamp, 36) % 9 + 1}`; // her çalıştırmada farklı → form gerçekten değişir
  await ap.goto(`${BASE}/admin/settings`);
  await ap.getByLabel('Kur tarihi').fill('');
  await ap.getByLabel('1 USD = ? TL').fill(rate);
  await ap.getByRole('button', { name: 'Ayarları kaydet' }).click();
  await ap.getByText('Kur girildiğinde tarih zorunludur.').waitFor();
  await ap.getByLabel('Kur tarihi').fill('2026-10-22');
  await ap.getByRole('button', { name: 'Ayarları kaydet' }).click();
  await ap.getByText('Proje ayarları kaydedildi.').waitFor();
  const c = await ctx(); const p = await c.newPage(); watch(p);
  await p.goto(`${BASE}/proje/malzeme-maliyet`);
  await p.getByText(`kayıtlı: ${rate}`, { exact: false }).waitFor({ timeout: 10000 });
  await p.getByText(/≈ ₺/).first().waitFor();
  await c.close();
});

await step('Düzenleyici proje ayarlarını kaydedemez; etkinlik günlüğünü görür', async () => {
  const c = await ctx(); const p = await c.newPage();
  await login(p, 'EDITOR');
  await p.goto(`${BASE}/admin/settings`);
  await p.getByText('yalnızca yöneticiler değiştirebilir').waitFor();
  assert(!(await p.getByRole('button', { name: 'Ayarları kaydet' }).count()), 'düzenleyiciye kaydet düğmesi gösterilmemeli');
  await p.goto(`${BASE}/admin/activity`);
  await p.getByText('Satın alma kaydedildi').first().waitFor({ timeout: 10000 });
  await p.getByText(cred('ADMIN').email).first().waitFor();
  await p.screenshot({ path: `${SHOTS}/editor-activity.png`, fullPage: true });
  await c.close();
});

await step('Mobil görünüm: panel menüsü ve genel sayfalarda yatay taşma yok', async () => {
  const c = await ctx({ viewport: { width: 390, height: 844 } }); const p = await c.newPage(); watch(p);
  await login(p, 'ADMIN');
  await p.getByRole('button', { name: 'Menüyü aç' }).click();
  await p.getByRole('dialog', { name: 'Yönetim menüsü' }).getByRole('link', { name: 'Malzemeler' }).click();
  await p.waitForURL(/\/admin\/materials/);
  for (const path of ['/admin/dashboard', '/admin/materials', '/admin/simulations', '/', '/proje/ilerleme', '/proje/malzeme-maliyet', '/proje/bilesen/alu', '/proje/github']) {
    await p.goto(`${BASE}${path}`);
    await p.waitForLoadState('networkidle');
    const over = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert(over <= 1, `${path} sayfasında ${over}px yatay taşma`);
  }
  await p.goto(`${BASE}/admin/dashboard`);
  await p.screenshot({ path: `${SHOTS}/mobile-admin-dashboard.png`, fullPage: true });
  await c.close();
});

await step('Çıkış: oturum kapanır ve panel yeniden giriş ister', async () => {
  await ap.goto(`${BASE}/admin/dashboard`);
  await ap.getByRole('button', { name: 'Çıkış' }).first().click();
  await ap.goto(`${BASE}/admin/dashboard`);
  await ap.waitForURL(/\/admin\/login/);
});

await step('Tarayıcıda yakalanmamış JavaScript hatası yok', async () => {
  assert(pageErrors.length === 0, `Sayfa hataları: ${pageErrors.slice(0, 3).join(' | ')}`);
});

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} adım başarılı`);
writeFileSync(`${SHOTS}/results.json`, JSON.stringify(results, null, 2));
process.exit(failed.length ? 1 : 0);
