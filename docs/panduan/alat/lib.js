// Fungsi bersama untuk skrip pengambil gambar buku panduan.
// Lihat README.md di folder ini untuk cara pakai.
const { chromium, devices } = require('playwright');
const { execSync } = require('child_process');

const BASE = (process.env.PANDUAN_URL || 'http://localhost:8080').replace(/\/$/, '');
const PW = process.env.PANDUAN_SANDI;
if (!PW) {
  console.error('Setel PANDUAN_SANDI dengan sandi akun contoh (lihat README.md).');
  process.exit(1);
}
// Sistem membatasi percobaan masuk beruntun. Perintah ini (opsional) mengosongkan
// cache sebelum setiap masuk, misalnya:
//   PANDUAN_BERSIHKAN_CACHE='psql -h localhost -U simlahan simlahan -qc "delete from simlahan_cache"'
const CLEAR = process.env.PANDUAN_BERSIHKAN_CACHE;
function clearThrottle() {
  if (CLEAR) execSync(CLEAR, { stdio: 'ignore' });
}
// Ubin peta dari internet diblokir agar gambar tidak bergantung pada jaringan.
const TILE = /tile\.openstreetmap|arcgisonline|cartocdn|opentopomap|google\.com\/vt|virtualearth|tiles?\./;

async function newCtx(browser, phone = false) {
  const opts = phone
    ? { ...devices['iPhone 13'], locale: 'id-ID' }
    : { viewport: { width: 1366, height: 860 }, locale: 'id-ID', deviceScaleFactor: 1 };
  const ctx = await browser.newContext({
    ...opts,
    timezoneId: 'Asia/Jakarta',
    geolocation: { latitude: 0.985, longitude: 104.07 },
    permissions: ['geolocation'],
  });
  await ctx.route(TILE, (r) => r.abort());
  return ctx;
}
async function loginSpa(page, user) {
  clearThrottle();
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  await page.fill('#login-username', user);
  await page.fill('#login-password', PW);
  await page.click('button[type=submit]');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);
}
async function loginAdmin(page, user) {
  clearThrottle();
  await page.goto(BASE + '/admin/login/', { waitUntil: 'networkidle' });
  await page.fill('#id_username', user);
  await page.fill('#id_password', PW);
  await Promise.all([page.waitForNavigation(), page.click('[type=submit]')]);
}
async function loginPortal(page, email) {
  clearThrottle();
  await page.goto(BASE + '/portal/masuk/', { waitUntil: 'networkidle' });
  const u = (await page.$('input[name=username]')) ? 'input[name=username]' : 'input[type=email]';
  await page.fill(u, email);
  await page.fill('input[type=password]', PW);
  await Promise.all([page.waitForNavigation(), page.click('form [type=submit]')]);
}
async function loginKomando(page, user) {
  clearThrottle();
  await page.goto(BASE + '/komando/masuk/', { waitUntil: 'networkidle' });
  await page.fill('input[name=username]', user);
  await page.fill('input[type=password]', PW);
  await Promise.all([page.waitForNavigation(), page.click('form [type=submit]')]);
}
// Kotak merah bernomor untuk menunjuk tombol atau kolom di gambar.
async function mark(p, marks) {
  for (const [sel, n] of marks) {
    const loc = p.locator(sel + ' >> visible=true').first();
    let box;
    try { box = await loc.boundingBox({ timeout: 4000 }); } catch (e) { box = null; }
    if (!box) { console.log('  penanda tidak ditemukan:', sel); continue; }
    await p.evaluate(({ box, n }) => {
      const sx = window.scrollX, sy = window.scrollY;
      const r = document.createElement('div'); r.className = '__mk';
      Object.assign(r.style, { position: 'absolute', left: (box.x + sx - 4) + 'px', top: (box.y + sy - 4) + 'px', width: (box.width + 8) + 'px', height: (box.height + 8) + 'px', border: '3px solid #e11d48', borderRadius: '8px', zIndex: 2147483646, pointerEvents: 'none', boxShadow: '0 0 0 3px rgba(225,29,72,.18)' });
      document.body.appendChild(r);
      if (n) {
        const b = document.createElement('div'); b.className = '__mk'; b.textContent = n;
        Object.assign(b.style, { position: 'absolute', left: Math.max(2, box.x + sx - 16) + 'px', top: Math.max(2, box.y + sy - 16) + 'px', minWidth: '26px', height: '26px', borderRadius: '13px', background: '#e11d48', color: '#fff', font: '700 15px/26px Inter, Arial, sans-serif', textAlign: 'center', zIndex: 2147483647, pointerEvents: 'none', boxShadow: '0 1px 4px rgba(0,0,0,.35)' });
        document.body.appendChild(b);
      }
    }, { box, n });
  }
}
// Chromium penuh (bukan headless shell) dengan LANG Indonesia agar tombol bawaan
// peramban (Pilih File, format tanggal hh/bb/tttt) ikut berbahasa Indonesia.
async function launch() {
  const executablePath = process.env.PANDUAN_CHROMIUM || undefined;
  return chromium.launch({
    executablePath,
    channel: executablePath ? undefined : 'chromium',
    args: ['--lang=id'],
    env: { ...process.env, LANG: 'id_ID.UTF-8', LANGUAGE: 'id' },
  });
}
module.exports = { BASE, PW, clearThrottle, launch, newCtx, mark, loginSpa, loginAdmin, loginPortal, loginKomando };
