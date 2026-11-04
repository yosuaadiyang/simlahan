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
// Setiap penanda berupa [pemilih, nomor]. Pemilih memakai sintaks Playwright
// (misalnya "text=Simpan", "#id_nama", "role=button[name='Simpan']"), atau
// "label=Teks label" untuk kolom isian berlabel. Penanda yang tidak ditemukan
// menggagalkan gambar agar nomor di teks tidak pernah menunjuk ke tempat kosong.
async function mark(p, marks, full = false) {
  for (const [sel, n] of marks) {
    const loc = sel.startsWith('label=')
      ? p.getByLabel(sel.slice(6)).filter({ visible: true }).first()
      : p.locator(sel + ' >> visible=true').first();
    let box;
    try { box = await loc.boundingBox({ timeout: 4000 }); } catch (e) { box = null; }
    if (!box) throw new Error('penanda tidak ditemukan: ' + sel);
    const vp = p.viewportSize();
    if (!full && (box.y < 0 || box.y + box.height > vp.height)) throw new Error('penanda di luar layar (gulir dulu): ' + sel);
    if (box.x < 0 || box.x + box.width > vp.width + 1) throw new Error('penanda di luar layar (geser ke samping): ' + sel);
    const field = await loc.evaluate((e) => {
      // Label di kiri kotak (formulir panel admin): nomor di kanan agar label tetap terbaca.
      const lab = e.id && document.querySelector(`label[for="${e.id}"]`);
      const labLeft = lab && lab.getBoundingClientRect().right <= e.getBoundingClientRect().left + 4;
      if (e.tagName === 'INPUT' && ['checkbox', 'radio', 'file'].includes(e.type)) return labLeft ? 'check-r' : 'check';
      if (['SELECT', 'TEXTAREA'].includes(e.tagName) || (e.tagName === 'INPUT' && !['submit', 'button', 'file'].includes(e.type)) || (/-control\b/.test(e.className) && !!e.querySelector('input'))) return labLeft ? 'field-r' : 'field';
      return '';
    });
    await p.evaluate(({ box, n, field }) => {
      const sx = window.scrollX, sy = window.scrollY;
      const r = document.createElement('div'); r.className = '__mk';
      Object.assign(r.style, { position: 'absolute', left: (box.x + sx - 4) + 'px', top: (box.y + sy - 4) + 'px', width: (box.width + 8) + 'px', height: (box.height + 8) + 'px', border: '3px solid #e11d48', borderRadius: '8px', zIndex: 2147483646, pointerEvents: 'none', boxShadow: '0 0 0 3px rgba(225,29,72,.18)' });
      document.body.appendChild(r);
      if (n) {
        const b = document.createElement('div'); b.className = '__mk'; b.textContent = n;
        // Kolom isian: nomor di sudut kanan atas kotak (menumpang garis tepi) agar
        // jelas milik kolom itu tanpa menutupi isi atau labelnya. Kotak centang: di
        // sampingnya. Tombol dan lainnya: sudut kiri atas. Bila bertabrakan dengan
        // nomor lain, dipakai posisi cadangan.
        const X = box.x + sx, Y = box.y + sy, W = box.width, H = box.height;
        const cw = document.documentElement.clientWidth;
        let cands;
        if (field === 'field' || field === 'field-r') {
          cands = [[X + W - 20, Y - 14], [X - 12, Y - 14], [X + W + 6, Y + Math.min(H / 2, 18) - 13], [X + W - 20, Y + H - 12]];
        } else if (field === 'check-r') {
          cands = [[X + W + 6, Y + H / 2 - 13], [X - 30, Y + H / 2 - 13]];
        } else if (field) {
          cands = [[X >= 36 ? X - 30 : X + W + 6, Y + H / 2 - 13], [X + W + 6, Y + H / 2 - 13]];
        } else {
          cands = W > 200
            ? [[X - 20, Y - 18], [X - 20, Y + H - 8], [X + W - 8, Y - 18], [X + W - 8, Y + H - 8]]
            : [[X - 20, Y - 18], [X + W - 8, Y - 18], [X - 20, Y + H - 8], [X + W - 8, Y + H - 8]];
        }
        const placed = (window.__mkPlaced = window.__mkPlaced || []);
        const fit = ([l, t]) => [Math.min(Math.max(2, l), cw - 30), Math.max(2, t)];
        const clash = ([l, t]) => placed.some(([a, c]) => Math.abs(a - l) < 30 && Math.abs(c - t) < 30);
        let [left, top] = fit(cands.find((c) => !clash(fit(c))) || cands[0]);
        placed.push([left, top]);
        Object.assign(b.style, { position: 'absolute', left: left + 'px', top: top + 'px', minWidth: '26px', height: '26px', borderRadius: '13px', background: '#e11d48', color: '#fff', font: '700 15px/26px Inter, Arial, sans-serif', textAlign: 'center', zIndex: 2147483647, pointerEvents: 'none', boxShadow: '0 1px 4px rgba(0,0,0,.35)' });
        document.body.appendChild(b);
      }
    }, { box, n, field });
  }
}
// Gambar satu halaman penuh: bilah yang menempel (sticky/fixed) dibuat biasa agar
// tidak muncul di tengah gambar.
async function unstick(p) {
  await p.evaluate(() => {
    document.querySelectorAll('body *').forEach((e) => {
      const pos = getComputedStyle(e).position;
      if (pos === 'sticky' || pos === 'fixed') e.style.setProperty('position', pos === 'fixed' && e.offsetHeight > window.innerHeight * 0.8 ? 'absolute' : 'static', 'important');
    });
  });
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
module.exports = { BASE, PW, clearThrottle, launch, newCtx, mark, unstick, loginSpa, loginAdmin, loginPortal, loginKomando };
