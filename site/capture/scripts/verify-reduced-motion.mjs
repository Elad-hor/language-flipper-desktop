// verify-reduced.mjs — build + preview + probe the flip animation in ONE
// foreground process (the sandbox reaps backgrounded servers).
// Checks BOTH motion modes on BOTH the EN and HE home pages.
import { spawn, execSync } from 'node:child_process';
import { chromium } from 'playwright';

// this file lives at site/capture/scripts/ — the site root is three levels up
const siteDir = new URL('../../', import.meta.url).pathname;

console.log('building…');
execSync('npm run build', { cwd: siteDir, stdio: 'inherit' });

const srv = spawn('npm', ['run', 'preview'], { cwd: siteDir, stdio: 'ignore' });
const waitUp = async () => {
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch('http://localhost:4321/'); if (r.status) return true; } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
};

let code = 0;
try {
  if (!(await waitUp())) throw new Error('preview server did not come up');

  const browser = await chromium.launch();
  const targets = [
    ['EN /', 'http://localhost:4321/'],
    ['HE /he/בית/', 'http://localhost:4321/he/בית/'],
  ];

  for (const [name, url] of targets) {
    for (const [mode, reducedMotion] of [['motion-ok', 'no-preference'], ['REDUCED', 'reduce']]) {
      const ctx = await browser.newContext({ viewport: { width: 1366, height: 658 }, reducedMotion });
      const page = await ctx.newPage();
      const errs = [];
      page.on('pageerror', (e) => errs.push(e.message));
      page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
      await page.goto(url, { waitUntil: 'load', timeout: 30000 });

      const seen = [];
      for (let i = 0; i < 30; i++) {
        seen.push(await page.evaluate(() => {
          const el = document.querySelector('.hero-h1 .h1-flip[data-correct]');
          return el ? el.textContent : '<<MISSING>>';
        }));
        await page.waitForTimeout(200);
      }
      const uniq = [...new Set(seen)];
      const final = seen[seen.length - 1];
      const correct = await page.evaluate(() => {
        const el = document.querySelector('.hero-h1 .h1-flip[data-correct]');
        return el?.getAttribute('data-correct');
      });

      const ok = mode === 'REDUCED'
        ? uniq.length >= 2 && final === correct   // changed at least once, ended correct
        : uniq.length > 3;                        // full loop
      if (!ok) code = 1;

      console.log(`\n[${name}] ${mode}: ${ok ? 'PASS' : 'FAIL'}`);
      console.log(`   distinct states: ${uniq.length}  |  final: ${JSON.stringify(final)}  |  expected final: ${JSON.stringify(correct)}`);
      console.log(`   states: ${uniq.slice(0, 6).map((s) => JSON.stringify(s)).join(' ')}${uniq.length > 6 ? ' …' : ''}`);
      if (errs.length) { code = 1; console.log('   JS ERRORS: ' + errs.join(' | ')); }
      await ctx.close();
    }
  }
  await browser.close();
} catch (e) {
  console.error('ERROR:', e.message);
  code = 1;
} finally {
  srv.kill('SIGTERM');
}
console.log(`\n=== ${code === 0 ? 'ALL PASS' : 'FAILURES PRESENT'} ===`);
process.exit(code);
