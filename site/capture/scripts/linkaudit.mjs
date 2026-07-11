// linkaudit.mjs — spawns preview (as a child, foreground) and checks every
// internal link + asset on all pages returns a good status. Reports broken ones.
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const siteDir = join(here, '..', '..');
const pages = JSON.parse(await readFile(join(here, '..', 'pages.json'), 'utf8'));
const base = 'http://localhost:4321';

const srv = spawn('npm', ['run', 'preview'], { cwd: siteDir, stdio: 'ignore' });
async function waitUp(t = 25000) {
  const s = Date.now();
  while (Date.now() - s < t) { try { const r = await fetch(base + '/'); if (r.status) return true; } catch {} await new Promise(r => setTimeout(r, 400)); }
  return false;
}

let code = 0;
try {
  if (!(await waitUp())) throw new Error('preview did not start');
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const seen = new Map(); // url -> status
  const brokenBy = {};    // page -> [ {url,status} ]

  for (const p of pages) {
    await page.goto(base + p.path, { waitUntil: 'networkidle' });
    const refs = await page.evaluate(() => {
      const out = [];
      document.querySelectorAll('a[href]').forEach(a => { const h = a.getAttribute('href'); if (h && !h.startsWith('#') && !h.startsWith('mailto:') && !h.startsWith('tel:')) out.push(a.href); });
      document.querySelectorAll('img[src]').forEach(i => out.push(i.src));
      document.querySelectorAll('link[rel="stylesheet"][href]').forEach(l => out.push(l.href));
      // background images
      [...document.querySelectorAll('*')].forEach(el => { const b = getComputedStyle(el).backgroundImage; const m = b && b.match(/url\(["']?([^"')]+)["']?\)/); if (m && m[1].startsWith('http')) out.push(m[1]); });
      return [...new Set(out)];
    });
    for (const u of refs) {
      // Only check same-origin (our own site); skip external (github/gumroad/fonts/social)
      if (!u.startsWith(base)) continue;
      let status = seen.get(u);
      if (status === undefined) {
        try { const r = await fetch(u, { method: 'GET' }); status = r.status; } catch { status = 0; }
        seen.set(u, status);
      }
      if (status >= 400 || status === 0) { (brokenBy[p.name] ||= []).push({ url: u.replace(base, ''), status }); }
    }
  }
  await browser.close();

  const pagesWithBroken = Object.keys(brokenBy);
  if (pagesWithBroken.length === 0) {
    console.log('LINK AUDIT: OK — no broken internal links/assets across', pages.length, 'pages.');
  } else {
    console.log('LINK AUDIT: BROKEN internal refs found:');
    for (const pg of pagesWithBroken) { console.log('  [' + pg + ']'); brokenBy[pg].forEach(x => console.log('    ' + x.status + '  ' + x.url)); }
    code = 2;
  }
  console.log('Checked', seen.size, 'unique internal URLs.');
} catch (e) { console.error('linkaudit failed:', e.message); code = 1; }
finally { try { srv.kill('SIGKILL'); } catch {} }
process.exit(code);
