/** Supabase yapılandırılmamış derlemenin (GitHub Pages / önizleme) çalıştığını doğrular. */
import { chromium } from 'playwright-core';
const BASE = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:4174';
const o = { headless: true }; if (process.env.CHROMIUM_PATH) o.executablePath = process.env.CHROMIUM_PATH; if (process.env.CHROMIUM_ARGS) o.args = process.env.CHROMIUM_ARGS.split(' ');
const b = await chromium.launch(o); const p = await b.newPage(); const errs = []; p.on('pageerror', (e) => errs.push(e.message));
let ok = 0, fail = 0;
const check = async (name, fn) => { try { await fn(); ok++; console.log('  ✓', name); } catch (e) { fail++; console.log('  ×', name, String(e.message).split('\n')[0]); } };
for (const [path, text] of [['/', 'Projeyi İncele'], ['/proje', 'Çalışma Şeması'], ['/proje/mimari-sema', '8-Bit Bilgisayarın Genel Mimarisi'], ['/proje/simulasyon', 'Henüz simülasyon görüntüsü eklenmedi.'],
  ['/proje/malzeme-maliyet', 'Tam referans malzeme listesi'], ['/proje/ilerleme', 'Bu aşama için henüz ilerleme kaydedilmedi.'], ['/proje/tasarim-ii', 'Yakında'], ['/proje/bilesen/alu', 'Aritmetik Mantık Birimi'],
  ['/proje/belgeler', 'Henüz yayımlanmış teknik belge yok'], ['/admin/login', 'Veritabanı bağlantısı yapılandırılmamış'], ['/yok-boyle-sayfa', 'Sayfa bulunamadı']]) {
  await check(`${path} → “${text}”`, async () => { await p.goto(BASE + path); await p.getByText(text).first().waitFor({ timeout: 10000 }); });
}
await check('Malzeme sayfasında yerel düzenleme (önceki davranış) korunuyor', async () => {
  await p.goto(BASE + '/proje/malzeme-maliyet'); await p.getByRole('button', { name: 'Düzenle', exact: true }).click(); await p.getByLabel(/74LS00 .* adet/).fill('3');
  await p.reload(); await p.getByRole('button', { name: 'Düzenle', exact: true }).click(); if ((await p.getByLabel(/74LS00 .* adet/).inputValue()) !== '3') throw new Error('localStorage kalıcılığı bozuk');
});
await check('Tarayıcı içi ALU simülasyonu çalışıyor', async () => {
  await p.goto(BASE + '/proje/simulasyon'); await p.getByText('İkili toplama').first().waitFor(); await p.getByText('00101010').first().waitFor();
});
await check('JavaScript hatası yok', async () => { if (errs.length) throw new Error(errs.join(' | ')); });
await b.close(); console.log(`\n${ok}/${ok + fail} kontrol başarılı`); process.exit(fail ? 1 : 0);
