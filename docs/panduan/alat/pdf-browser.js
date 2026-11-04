// Peluncur Chromium untuk buat-pdf.js (tanpa perlu sandi akun).
const { chromium } = require('playwright');
module.exports.launch = () => chromium.launch({
  executablePath: process.env.PANDUAN_CHROMIUM || undefined,
  channel: process.env.PANDUAN_CHROMIUM ? undefined : 'chromium',
  args: ['--lang=id'],
  env: { ...process.env, LANG: 'id_ID.UTF-8', LANGUAGE: 'id' },
});
