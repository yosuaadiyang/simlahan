// Buat PDF buku panduan: satu buku lengkap + satu PDF per peran.
//   npm install marked@12.0.2   (sekali, di folder ini)
//   node buat-pdf.js [folder-keluaran]
// Keluaran bawaan: alat/keluaran/ (tidak disimpan di repositori).
const fs = require('fs');
const path = require('path');
const { marked } = require('marked');
const { launch } = require('./pdf-browser');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.resolve(process.argv[2] || path.join(__dirname, 'keluaran'));
const TITLE = 'Buku Panduan SimLahan';

const chapters = fs.readdirSync(ROOT).filter((f) => /^\d\d-.*\.md$/.test(f)).sort();
const roleBooks = (() => {
  // Urutan buku peran mengikuti tabel "Buku per peran" di README.md.
  const readme = fs.readFileSync(path.join(ROOT, 'README.md'), 'utf8');
  return [...readme.matchAll(/\]\(peran\/([\w-]+\.md)\)/g)].map((m) => 'peran/' + m[1]);
})();

function slug(text) {
  return text.trim().toLowerCase().replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[^\p{L}\p{N}_\- ]/gu, '').replace(/ /g, '-');
}
const fileId = (rel) => 'f-' + rel.replace(/\.md$/, '').replace(/[^\w]/g, '-');

function render(rel, included) {
  const src = fs.readFileSync(path.join(ROOT, rel), 'utf8');
  const dir = path.dirname(path.join(ROOT, rel));
  const id = fileId(rel);
  const seen = {};
  const renderer = new marked.Renderer();
  renderer.heading = (text, level, raw) => {
    let s = slug(raw.replace(/[*`]/g, ''));
    const n = seen[s] || 0; seen[s] = n + 1; if (n) s += '-' + n;
    const attr = level === 1 ? ` id="${id}" class="bab"` : ` id="${id}--${s}"`;
    return `<h${level}${attr}>${text}</h${level}>\n`;
  };
  renderer.image = (href, title, text) => {
    const file = path.resolve(dir, decodeURIComponent(href));
    return `<figure><img src="file://${file}" alt="${text}"><figcaption>${text}</figcaption></figure>`;
  };
  renderer.link = (href, title, text) => {
    if (/^[a-z]+:/.test(href)) return `<a href="${href}">${text}</a>`;
    const [file, frag] = href.split('#');
    const target = file ? path.relative(ROOT, path.resolve(dir, file)) : rel;
    if (!included.has(target)) return `<span class="xref">${text}</span>`;
    const tid = fileId(target);
    return `<a href="#${frag ? tid + '--' + frag : tid}">${text}</a>`;
  };
  const html = marked.parse(src, { renderer, gfm: true });
  return `<section class="berkas" data-file="${rel}">${html}</section>`;
}

const CSS = `
@page { size: A4; margin: 18mm 16mm 20mm; }
* { box-sizing: border-box; }
body { font: 10.5pt/1.55 "Inter", "Segoe UI", Arial, sans-serif; color: #1f2937; }
h1 { font-size: 22pt; color: #0b5fcc; border-bottom: 3px solid #1d82f5; padding-bottom: 6px; margin: 0 0 14px; }
section.berkas { break-before: page; }
h2 { font-size: 15pt; color: #0b5fcc; margin: 22px 0 8px; break-after: avoid; }
h3 { font-size: 12pt; margin: 16px 0 6px; break-after: avoid; }
h4 { font-size: 11pt; margin: 12px 0 4px; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
a { color: #0b5fcc; text-decoration: none; }
code { font: 9.5pt "DejaVu Sans Mono", monospace; background: #f1f5f9; padding: 1px 4px; border-radius: 4px; }
pre { background: #f1f5f9; padding: 8px 10px; border-radius: 6px; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9.5pt; }
th, td { border: 1px solid #cbd5e1; padding: 4px 6px; text-align: left; vertical-align: top; }
th { background: #e8f1fe; }
tr { break-inside: avoid; }
blockquote { margin: 10px 0; padding: 6px 12px; border-left: 4px solid #1d82f5; background: #f0f7ff; }
figure { margin: 10px 0 14px; break-inside: avoid; text-align: center; }
figure img { max-width: 100%; max-height: 225mm; border: 1px solid #cbd5e1; border-radius: 6px; }
figcaption { font-size: 8.5pt; color: #64748b; margin-top: 3px; }
.sampul { height: 250mm; display: flex; flex-direction: column; justify-content: center; }
.sampul .judul { font-size: 34pt; font-weight: 700; color: #0b5fcc; }
.sampul .sub { font-size: 15pt; margin-top: 8px; }
.sampul .ket { margin-top: 40px; color: #64748b; }
`;

function cover(subtitle) {
  const tgl = new Date().toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Jakarta' });
  return `<div class="sampul"><div class="judul">${TITLE}</div><div class="sub">${subtitle}</div>
<div class="ket">Sistem Informasi Manajemen Lahan · ${tgl}<br>Semua gambar memakai data contoh fiktif.</div></div>`;
}

async function pdf(page, files, subtitle, out) {
  const included = new Set(files);
  const body = cover(subtitle) + files.map((f) => render(f, included)).join('\n');
  const html = `<!doctype html><html lang="id"><head><meta charset="utf-8"><title>${TITLE}</title><style>${CSS}</style></head><body>${body}</body></html>`;
  const tmp = path.join(OUT, '.sementara.html');
  fs.writeFileSync(tmp, html);
  await page.goto('file://' + tmp, { waitUntil: 'load' });
  await page.pdf({
    path: out, format: 'A4', printBackground: true, displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate: `<div style="font:8pt Arial,sans-serif;color:#64748b;width:100%;padding:0 16mm;display:flex;justify-content:space-between"><span>${TITLE} · ${subtitle}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
    margin: { top: '18mm', bottom: '20mm', left: '16mm', right: '16mm' },
  });
  fs.unlinkSync(tmp);
  console.log('ok', path.relative(process.cwd(), out));
}

// Bab yang ditautkan buku peran ikut masuk PDF perannya. Isi sisipan (langkah yang
// sudah disalin dari bab) tidak dihitung agar bab yang sama tidak tercetak dua kali.
function linkedChapters(rel) {
  const src = fs.readFileSync(path.join(ROOT, rel), 'utf8')
    .replace(/<!-- sisip: [^>]*-->[\s\S]*?<!-- akhir sisip -->/g, '');
  const dir = path.dirname(path.join(ROOT, rel));
  const found = new Set();
  for (const m of src.matchAll(/\]\(([^)#\s]+\.md)(#[^)]*)?\)/g)) {
    const t = path.relative(ROOT, path.resolve(dir, m[1]));
    if (chapters.includes(t)) found.add(t);
  }
  return chapters.filter((c) => found.has(c));
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await launch();
  const page = await browser.newPage();
  // Buku peran berisi salinan langkah dari bab, jadi tidak ikut buku lengkap
  // (masing-masing punya PDF sendiri di folder peran/).
  await pdf(page, ['README.md', ...chapters], 'Buku lengkap', path.join(OUT, 'panduan-simlahan-lengkap.pdf'));
  for (const book of roleBooks) {
    const name = fs.readFileSync(path.join(ROOT, book), 'utf8').match(/^# Buku peran: (.+)$/m)[1];
    const files = [book, ...new Set(['01-mengenal-simlahan.md', '02-dasar-penggunaan.md', ...linkedChapters(book)])];
    await pdf(page, files, `Peran ${name}`, path.join(OUT, 'peran', path.basename(book, '.md') + '.pdf'));
  }
  await pdf(page, ['01-mengenal-simlahan.md', '02-dasar-penggunaan.md', '60-superuser.md'], 'Superuser', path.join(OUT, 'peran', 'superuser.pdf'));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
