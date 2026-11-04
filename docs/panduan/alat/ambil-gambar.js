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
    if (a.open) await p.locator(a.open + ' >> visible=true').first().evaluate((d) => { d.open = true; });
    if (a.goto) await p.goto(L.BASE + a.goto, { waitUntil: 'networkidle' });
    if (a.js) await p.evaluate(a.js);
  }
}

// Potongan elemen + sedikit tepi, agar nomor penanda di luar tepi elemen tidak terpotong.
async function shotWithMargin(p, sel, out) {
  const el = p.locator(sel).first();
  await el.scrollIntoViewIfNeeded();
  const b = await el.boundingBox();
  const vp = p.viewportSize();
  if (!b || b.height > vp.height) return el.screenshot({ path: out });
  const pad = 34;
  const x = Math.max(0, b.x - pad), y = Math.max(0, b.y - pad);
  const clip = { x, y, width: Math.min(vp.width, b.x + b.width + pad) - x, height: Math.min(vp.height, b.y + b.height + pad) - y };
  await p.screenshot({ path: out, clip });
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
      // PANDUAN_HANYA=nama1,nama2 mengambil gambar tertentu saja (nama tanpa .png).
      const only = (process.env.PANDUAN_HANYA || '').split(',').filter(Boolean);
      if (only.length && !grp.items.some((it) => only.includes(`${grp.prefix || ''}${it.name}`))) continue;
      // "tautan": alamat yang baru diketahui setelah masuk sebagai pengguna lain (misalnya
      // tautan verifikasi dokumen contoh). {NAMA} di "url" diganti dengan href elemennya.
      const vars = {};
      for (const [k, v] of Object.entries(grp.tautan || {})) {
        const c2 = await L.newCtx(browser);
        const p2 = await c2.newPage();
        await LOGIN[v.login](p2, v.user);
        await p2.goto(L.BASE + v.url, { waitUntil: 'networkidle' });
        const href = await p2.locator(v.ambil).first().getAttribute('href');
        vars[k] = new URL(href, L.BASE).pathname;
        await c2.close();
      }
      const ctx = await L.newCtx(browser, grp.phone);
      const p = await ctx.newPage();
      if (LOGIN[grp.login]) await LOGIN[grp.login](p, grp.user); // "none" = tanpa masuk
      for (const it of grp.items) {
        if (only.length && !it.tanpa_gambar && !only.includes(`${grp.prefix || ''}${it.name}`)) continue;
        const vp0 = p.viewportSize();
        if (it.url) it.url = it.url.replace(/\{(\w+)\}/g, (m, k) => vars[k] || m);
        try {
          // "tinggi": layar dibuat lebih tinggi agar formulir panjang (modal) tampil utuh.
          if (it.tinggi) await p.setViewportSize({ width: vp0.width, height: it.tinggi });
          await runItem(p, it);
          if (it.tanpa_gambar) continue; // langkah navigasi saja
          await p.waitForTimeout(it.delay || 1200);
          if (it.full) await L.unstick(p);
          if (it.mark) await L.mark(p, it.mark, !!(it.full || it.el));
          const out = path.join(outDir, `${grp.prefix || ''}${it.name}.png`);
          if (it.el && it.mark) await shotWithMargin(p, it.el, out);
          else if (it.el) await p.locator(it.el).first().screenshot({ path: out });
          else await p.screenshot({ path: out, fullPage: !!it.full });
          await p.evaluate(() => { document.querySelectorAll('.__mk').forEach((e) => e.remove()); window.__mkPlaced = []; });
          ok += 1;
          console.log('ok', path.relative(process.cwd(), out));
        } catch (e) {
          failed += 1;
          console.log('GAGAL', it.name, e.message.split('\n')[0]);
        }
        if (it.tinggi) await p.setViewportSize(vp0);
      }
      await ctx.close();
    }
  }
  await browser.close();
  console.log(`Selesai: ${ok} gambar, ${failed} gagal.`);
  process.exit(failed ? 1 : 0);
})();
