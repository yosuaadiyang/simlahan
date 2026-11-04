// Ambil ulang gambar buku panduan.
//   node ambil-gambar.js spesifikasi/sewa.json [spesifikasi/....json ...]
//   node ambil-gambar.js            (semua berkas di spesifikasi/)
const L = require('./lib');
const fs = require('fs');
const path = require('path');

const LOGIN = { spa: L.loginSpa, admin: L.loginAdmin, portal: L.loginPortal, komando: L.loginKomando };
const ORDER = ['dasar', 'sewa', 'pengadaan', 'alokasi', 'dokumen', 'aset', 'lapangan', 'komando', 'peran', 'portal'];

function specFiles() {
  if (process.argv.length > 2) return process.argv.slice(2);
  return ORDER.map((n) => path.join(__dirname, 'spesifikasi', n + '.json'));
}

async function runItem(p, it) {
  if (it.url) await p.goto(L.BASE + it.url, { waitUntil: 'networkidle', timeout: 30000 }).catch(() => p.waitForTimeout(500));
  if (it.js) await p.evaluate(it.js);
  for (const a of it.actions || []) {
    if (a.click) await p.locator(a.click + ' >> visible=true').first().click({ timeout: 8000 });
    if (a.fill) await p.fill(a.fill, a.value);
    if (a.select) await p.selectOption(a.select, a.value);
    if (a.wait) await p.waitForTimeout(a.wait);
    if (a.waitFor) await p.waitForSelector(a.waitFor, { timeout: 10000 });
    if (a.hover) await p.hover(a.hover, { timeout: 8000 });
    if (a.press) await p.keyboard.press(a.press);
    if (a.scroll) await p.locator(a.scroll).first().scrollIntoViewIfNeeded();
    if (a.scrollY !== undefined) await p.evaluate((y) => window.scrollTo(0, y), a.scrollY);
    if (a.check) await p.check(a.check);
    if (a.goto) await p.goto(L.BASE + a.goto, { waitUntil: 'networkidle' });
  }
}

(async () => {
  const browser = await L.launch();
  let ok = 0, failed = 0;
  for (const file of specFiles()) {
    const spec = JSON.parse(fs.readFileSync(file, 'utf8'));
    // PANDUAN_GAMBAR_KE=<folder> menyimpan ke folder lain (untuk membandingkan dulu).
    const outDir = process.env.PANDUAN_GAMBAR_KE
      ? path.join(path.resolve(process.env.PANDUAN_GAMBAR_KE), path.basename(spec.out))
      : path.resolve(path.dirname(file), spec.out);
    fs.mkdirSync(outDir, { recursive: true });
    console.log('==', path.basename(file));
    for (const grp of spec.groups) {
      const ctx = await L.newCtx(browser, grp.phone);
      const p = await ctx.newPage();
      if (LOGIN[grp.login]) await LOGIN[grp.login](p, grp.user); // "none" = tanpa masuk
      for (const it of grp.items) {
        try {
          await runItem(p, it);
          if (it.tanpa_gambar) continue; // langkah navigasi saja
          await p.waitForTimeout(it.delay || 1200);
          if (it.mark) await L.mark(p, it.mark);
          const out = path.join(outDir, `${grp.prefix || ''}${it.name}.png`);
          if (it.el) await p.locator(it.el).first().screenshot({ path: out });
          else await p.screenshot({ path: out, fullPage: !!it.full });
          await p.evaluate(() => document.querySelectorAll('.__mk').forEach((e) => e.remove()));
          ok += 1;
          console.log('ok', path.relative(process.cwd(), out));
        } catch (e) {
          failed += 1;
          console.log('GAGAL', it.name, e.message.split('\n')[0]);
        }
      }
      await ctx.close();
    }
  }
  await browser.close();
  console.log(`Selesai: ${ok} gambar, ${failed} gagal.`);
  process.exit(failed ? 1 : 0);
})();
