// verify-download-events.mjs — the GA4 download events (Seo.astro).
// Builds, serves dist/ in-process (the sandbox reaps backgrounded servers) and
// clicks the real download links: each started download must emit exactly one
// download_mac / download_windows with the right version and page language,
// the phone card click that InstallModal cancels must emit nothing, and its
// "download anyway" link must count.
//
//   node capture/scripts/verify-download-events.mjs
//
// Offline: LF_ALLOW_STALE_DOWNLOADS=1 (the pinned URLs have the same shape).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { chromium } from 'playwright';

// this file lives at site/capture/scripts/ — the site root is three levels up
const siteDir = new URL('../../', import.meta.url).pathname;

console.log('building…');
execSync('npm run build', { cwd: siteDir, stdio: 'inherit' });

const root = path.join(siteDir, 'dist');
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  let f = path.join(root, p);
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
  if (!fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  const ext = path.extname(f);
  res.writeHead(200, { 'content-type': ext === '.html' ? 'text/html; charset=utf-8' : ext === '.js' ? 'text/javascript' : ext === '.css' ? 'text/css' : 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(0, r));
const base = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch();
let pass = 0, fail = 0;
const check = (name, ok, extra = '') => { ok ? pass++ : fail++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`); };

// A download (or a 204) leaves the page in place, as a real click does; aborting
// the request would swap in Chromium's error page and take dataLayer with it.
async function open(url, viewport) {
  const ctx = await browser.newContext({ viewport, hasTouch: viewport.width < 768 });
  const page = await ctx.newPage();
  await page.route(/googletagmanager\.com|clarity\.ms|google-analytics\.com/, (r) => r.fulfill({ status: 200, contentType: 'text/javascript', body: '' }));
  await page.route(/github\.com|githubusercontent\.com/, (r) => r.fulfill({ status: 200, headers: { 'content-type': 'application/octet-stream', 'content-disposition': 'attachment; filename=x.bin' }, body: 'x' }));
  await page.goto(base + url, { waitUntil: 'load' });
  return { ctx, page };
}
const events = (page) => page.evaluate(() =>
  (window.dataLayer || []).map((a) => Array.from(a)).filter((a) => a[0] === 'event').map(([, n, p]) => ({ n, v: p.app_version, l: p.site_lang })));

const desk = { width: 1280, height: 800 }, phone = { width: 390, height: 844 };

// 1. Desktop, EN: Mac icon link
{ const { ctx, page } = await open('/', desk);
  await page.locator('.dl-icon-link[data-install-os="mac"]').click();
  let ev = await events(page);
  check('desktop EN mac icon -> download_mac 0.1.111 en', ev.length === 1 && ev[0].n === 'download_mac' && ev[0].v === '0.1.111' && ev[0].l === 'en', JSON.stringify(ev));
  check('install modal still opens on desktop', await page.locator('#install-dlg-mac').evaluate((d) => d.open));
  await page.keyboard.press('Escape');
  // 2. Windows title link
  await page.locator('.dl-title a[data-install-os="win"]').click();
  ev = await events(page);
  check('desktop EN windows title -> download_windows 0.1.105', ev.length === 2 && ev[1].n === 'download_windows' && ev[1].v === '0.1.105', JSON.stringify(ev));
  await page.keyboard.press('Escape');
  // 3. Premium card does not count
  await page.route(/gumroad\.com/, (r) => r.fulfill({ status: 204 }));
  await page.locator('.dl-title a[href*="gumroad"]').click();
  ev = await events(page);
  check('premium link fires nothing', ev.length === 2, JSON.stringify(ev));
  await ctx.close(); }

// 4. Hebrew page
{ const { ctx, page } = await open('/he/' + encodeURIComponent('בית') + '/', desk);
  await page.locator('.dl-title a[data-install-os="mac"]').click();
  const ev = await events(page);
  check('desktop HE mac -> download_mac lang he', ev.length === 1 && ev[0].n === 'download_mac' && ev[0].l === 'he', JSON.stringify(ev));
  await ctx.close(); }

// 5. Phone: card click is cancelled (modal only) and must not count; "download anyway" must
{ const { ctx, page } = await open('/', phone);
  await page.locator('.dl-icon-link[data-install-os="mac"]').click();
  let ev = await events(page);
  check('phone mac card (cancelled) fires nothing', ev.length === 0, JSON.stringify(ev));
  check('phone modal opened', await page.locator('#install-dlg-mac').evaluate((d) => d.open));
  await page.locator('#install-dlg-mac .im-anyway').click();
  ev = await events(page);
  check('phone "download anyway" -> download_mac', ev.length === 1 && ev[0].n === 'download_mac', JSON.stringify(ev));
  await ctx.close(); }

await browser.close();
server.close();
console.log(`\n${pass}/${pass + fail} passed`);
process.exit(fail ? 1 : 0);
