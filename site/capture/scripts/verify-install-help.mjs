// verify-install-help.mjs — build + preview + assert the install-warning
// collapsible and per-OS modals behave, in BOTH languages, in ONE foreground
// process (the sandbox reaps backgrounded servers).
//
// The critical assertion is DOWNLOAD_FIRES: the modal must never gate the
// download. Release URLs are intercepted so nothing actually hits the network.
import { spawn, execSync } from 'node:child_process';
import { chromium } from 'playwright';

const siteDir = new URL('../../', import.meta.url).pathname;

console.log('building…');
execSync('npm run build', { cwd: siteDir, stdio: 'ignore' });

const srv = spawn('npm', ['run', 'preview'], { cwd: siteDir, stdio: 'ignore' });
const waitUp = async () => {
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch('http://localhost:4321/'); if (r.status) return true; } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
};

const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail });
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  — ${detail}` : ''}`);
};

const TARGETS = [
  { lang: 'EN', url: 'http://localhost:4321/',        toggle: "Your computer hasn't met us yet (it'll get over it)", rtl: false },
  { lang: 'HE', url: 'http://localhost:4321/he/בית/', toggle: 'המחשב שלך עוד לא מכיר אותנו (זה יעבור לו)',            rtl: true  },
];

let code = 0;
try {
  if (!(await waitUp())) throw new Error('preview server did not come up');
  const browser = await chromium.launch();

  for (const target of TARGETS) {
    console.log(`\n=== ${target.lang}  ${target.url} ===`);
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 800 }, acceptDownloads: true });
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push('JS: ' + e.message));
    page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });

    // Don't let the real release binaries download.
    await page.route('**/releases/download/**', (route) =>
      route.fulfill({
        status: 200,
        headers: { 'content-disposition': 'attachment; filename="stub.bin"' },
        body: 'stub',
      }));

    await page.goto(target.url, { waitUntil: 'load', timeout: 30000 });
    await page.waitForTimeout(400);

    // --- collapsible ---
    const details = page.locator('details.dl-help');
    check(`${target.lang} collapsible exists`, (await details.count()) === 1, `count=${await details.count()}`);
    check(`${target.lang} collapsible starts closed`, !(await details.evaluate((d) => d.open)));
    const summaryText = (await page.locator('.dl-help-summary').innerText()).trim();
    check(`${target.lang} heading copy`, summaryText === target.toggle, JSON.stringify(summaryText));

    // Content must be in the DOM even while collapsed (JS-free reachability).
    const blocksClosed = await page.locator('details.dl-help .ih-block').count();
    check(`${target.lang} both OS blocks present while collapsed`, blocksClosed === 2, `blocks=${blocksClosed}`);

    await page.locator('.dl-help-summary').click();
    await page.waitForTimeout(250);
    check(`${target.lang} collapsible opens`, await details.evaluate((d) => d.open));
    const stepsVisible = await page.locator('details.dl-help .ih-steps li').count();
    check(`${target.lang} 8 steps render (4 mac + 4 win)`, stepsVisible === 8, `steps=${stepsVisible}`);
    await page.locator('.dl-help-summary').click();
    await page.waitForTimeout(200);

    // --- modal: windows, and the download must still fire ---
    for (const os of ['win', 'mac']) {
      const sel = `.dl-title a[data-install-os="${os}"]`;
      const dlgSel = `#install-dlg-${os}`;

      const dlPromise = page.waitForEvent('download', { timeout: 8000 }).catch(() => null);
      await page.locator(sel).click();
      await page.waitForTimeout(400);

      const isOpen = await page.locator(dlgSel).evaluate((d) => d.open);
      check(`${target.lang} ${os}: modal opens on click`, isOpen === true);

      const dl = await dlPromise;
      check(`${target.lang} ${os}: DOWNLOAD_FIRES (modal does not gate it)`, dl !== null,
        dl ? `file=${dl.suggestedFilename()}` : 'no download event');

      // Only this OS's block appears in the modal.
      const modalBlocks = await page.locator(`${dlgSel} .ih-block`).count();
      check(`${target.lang} ${os}: modal shows exactly one OS block`, modalBlocks === 1, `blocks=${modalBlocks}`);

      // Focus should be inside the dialog (native showModal behaviour).
      const focusInside = await page.evaluate((s) => {
        const d = document.querySelector(s);
        return !!d && d.contains(document.activeElement);
      }, dlgSel);
      check(`${target.lang} ${os}: focus moves into dialog`, focusInside);

      // Escape closes.
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);
      check(`${target.lang} ${os}: Escape closes`, !(await page.locator(dlgSel).evaluate((d) => d.open)));
    }

    // --- close affordances on the win dialog ---
    await page.locator('.dl-title a[data-install-os="win"]').click();
    await page.waitForTimeout(350);
    await page.locator('#install-dlg-win .im-ok').click();
    await page.waitForTimeout(300);
    check(`${target.lang} "Got it" closes`, !(await page.locator('#install-dlg-win').evaluate((d) => d.open)));

    await page.locator('.dl-title a[data-install-os="win"]').click();
    await page.waitForTimeout(350);
    // Click the far top-left of the viewport — outside .im-inner, on the backdrop.
    await page.mouse.click(8, 8);
    await page.waitForTimeout(300);
    check(`${target.lang} backdrop click closes`, !(await page.locator('#install-dlg-win').evaluate((d) => d.open)));

    // --- RTL ---
    const pageDir = await page.evaluate(() => document.documentElement.getAttribute('dir'));
    check(`${target.lang} page dir`, pageDir === (target.rtl ? 'rtl' : 'ltr'), `dir=${pageDir}`);

    if (target.rtl) {
      await page.locator('.dl-title a[data-install-os="win"]').click();
      await page.waitForTimeout(350);
      // The close X should sit on the LEFT half of the dialog in RTL.
      const onLeft = await page.evaluate(() => {
        const d = document.querySelector('#install-dlg-win');
        const x = d.querySelector('.im-x');
        const dr = d.getBoundingClientRect();
        const xr = x.getBoundingClientRect();
        return xr.left + xr.width / 2 < dr.left + dr.width / 2;
      });
      check('HE close button mirrors to the left', onLeft);
      await page.keyboard.press('Escape');
    }

    check(`${target.lang} no JS errors`, errs.length === 0, errs.slice(0, 3).join(' | '));
    await ctx.close();

    // --- phone: the card must NOT navigate (no stray iOS tab), must show the
    //     desktop-app note, and must still offer an explicit way out ---
    const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, acceptDownloads: true });
    const mp = await mctx.newPage();
    await mp.route('**/releases/download/**', (route) =>
      route.fulfill({ status: 200, headers: { 'content-disposition': 'attachment; filename="stub.bin"' }, body: 'stub' }));
    await mp.goto(target.url, { waitUntil: 'load', timeout: 30000 });
    await mp.waitForTimeout(400);

    const mDl = mp.waitForEvent('download', { timeout: 4000 }).catch(() => null);
    await mp.locator('.dl-title a[data-install-os="win"]').click();
    await mp.waitForTimeout(500);
    check(`${target.lang} phone: modal opens`, await mp.locator('#install-dlg-win').evaluate((d) => d.open));
    check(`${target.lang} phone: NO navigation/download (no stray tab)`, (await mDl) === null);
    check(`${target.lang} phone: still on the page`, mp.url().includes('languageflipper') || mp.url().includes('localhost'));
    check(`${target.lang} phone: desktop-app note visible`,
      await mp.locator('#install-dlg-win .im-mobile-note').isVisible());
    const anyway = mp.locator('#install-dlg-win .im-anyway');
    check(`${target.lang} phone: "download anyway" offered`, await anyway.isVisible());
    check(`${target.lang} phone: "download anyway" points at the release`,
      ((await anyway.getAttribute('href')) || '').includes('releases/download'));
    await mctx.close();

    // --- desktop must be unaffected: the note stays hidden ---
    const dctx = await browser.newContext({ viewport: { width: 1366, height: 800 } });
    const dp = await dctx.newPage();
    await dp.goto(target.url, { waitUntil: 'load', timeout: 30000 });
    await dp.waitForTimeout(300);
    check(`${target.lang} desktop: mobile note hidden`,
      !(await dp.locator('#install-dlg-win .im-mobile-note').isVisible()));
    check(`${target.lang} desktop: "download anyway" hidden`,
      !(await dp.locator('#install-dlg-win .im-anyway').isVisible()));
    await dctx.close();
  }
  await browser.close();
} catch (e) {
  console.error('FATAL', e);
  code = 1;
} finally {
  srv.kill('SIGTERM');
}

const failed = results.filter((r) => !r.ok);
console.log(`\n================ ${results.length - failed.length}/${results.length} passed ================`);
if (failed.length) {
  console.log('FAILURES:');
  for (const f of failed) console.log(`  - ${f.name}  ${f.detail}`);
  code = 1;
}
process.exit(code);
