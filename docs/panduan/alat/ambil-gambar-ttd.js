// Gambar halaman tanda tangan (Bab 15.3). Butuh token penerima yang masih menunggu
// tanda tangan pemohon contoh (lihat README.md).
//   node ambil-gambar-ttd.js <token>
const L = require('./lib');
const path = require('path');

const OUT = path.join(__dirname, '..', 'gambar', 'portal', 'pemohon-ttd-tanda-tangan.png');
const TOKEN = process.argv[2];
if (!TOKEN) { console.error('Pakai: node ambil-gambar-ttd.js <token>'); process.exit(1); }

(async () => {
  const browser = await L.launch();
  const ctx = await L.newCtx(browser, false);
  const p = await ctx.newPage();
  await L.loginPortal(p, 'pemohon@contoh.simlahan.invalid');
  await p.goto(`${L.BASE}/portal/dokumen/ttd/${TOKEN}/`, { waitUntil: 'networkidle' });
  await p.waitForTimeout(1000);
  await L.mark(p, [['#tindakan', '1'], ['#dk-sign-form button[type=submit]', '2'], ['#tindakan details > summary', '3']]);
  await p.screenshot({ path: OUT, fullPage: true });
  await browser.close();
  console.log('ok', OUT);
})().catch((e) => { console.error(e); process.exit(1); });
