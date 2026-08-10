// responsive-audit.mjs — build + preview + measure layout defects across all
// pages × viewports in ONE foreground process (sandbox reaps backgrounded servers).
import { spawn, execSync } from 'node:child_process';
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

// this file lives at site/capture/scripts/ — the site root is two levels up
const siteDir = new URL('../../', import.meta.url).pathname;
const shotDir = process.env.SHOT_DIR || `${siteDir}capture/responsive/`;
mkdirSync(shotDir, { recursive: true });

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

const PAGES = [
  ['home',        '/'],
  ['about',       '/about-us/'],
  ['flip-it',     '/flip-it/'],
  ['contact',     '/contact-us/'],
  ['faq',         '/solutions/'],
  ['terms',       '/terms-of-service/'],
  ['privacy',     '/privacy-policy/'],
  ['he-home',     '/he/בית/'],
  ['he-about',    '/he/עלינו/'],
  ['he-flip',     '/he/תפליפו/'],
  ['he-contact',  '/he/צור-קשר/'],
  ['he-terms',    '/he/תנאי-שימוש/'],
  ['he-privacy',  '/he/פרטיות/'],
];

const VIEWPORTS = [
  ['phone',   390,  844],
  ['laptop', 1366,  658],   // Elad's 13" — the viewport that caught the hero CTA bug
  ['desk',   1920, 1080],
];

let code = 0;
const findings = [];

try {
  if (!(await waitUp())) throw new Error('preview server did not come up');
  const browser = await chromium.launch();

  for (const [pname, path] of PAGES) {
    for (const [vname, width, height] of VIEWPORTS) {
      const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
      const page = await ctx.newPage();
      const errs = [];
      page.on('pageerror', (e) => errs.push('JS: ' + e.message));
      page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });

      let resp;
      try {
        resp = await page.goto('http://localhost:4321' + path, { waitUntil: 'load', timeout: 30000 });
      } catch (e) {
        findings.push({ page: pname, vp: vname, kind: 'NAV_FAIL', detail: e.message });
        await ctx.close();
        continue;
      }
      if (resp && resp.status() >= 400) {
        findings.push({ page: pname, vp: vname, kind: 'HTTP', detail: String(resp.status()) });
      }
      await page.waitForTimeout(700);

      const res = await page.evaluate(() => {
        const out = { hScroll: null, overflow: [], overlaps: [], tiny: [], clipped: [] };
        const vw = window.innerWidth;
        const de = document.documentElement;

        if (de.scrollWidth > vw + 1) {
          out.hScroll = { scrollWidth: de.scrollWidth, viewport: vw };
        }

        const desc = (el) => {
          const id = el.id ? '#' + el.id : '';
          const cls = (typeof el.className === 'string' && el.className)
            ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.')
            : '';
          const txt = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 32);
          return `${el.tagName.toLowerCase()}${id}${cls}${txt ? ` "${txt}"` : ''}`;
        };
        const visible = (el) => {
          const s = getComputedStyle(el);
          if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return false;
          const r = el.getBoundingClientRect();
          return r.width > 0 && r.height > 0;
        };

        const all = [...document.querySelectorAll('body *')].filter(visible);

        // 1. Elements pushing past the right edge (or left, for RTL)
        for (const el of all) {
          const r = el.getBoundingClientRect();
          if (r.width > vw + 2) continue;              // full-bleed wrappers: not the culprit
          if (r.right > vw + 2) {
            out.overflow.push({ el: desc(el), right: Math.round(r.right), vw });
          } else if (r.left < -2) {
            out.overflow.push({ el: desc(el), left: Math.round(r.left), vw });
          }
        }

        // 2. Content clipped by an ancestor's overflow:hidden (text cut off)
        for (const el of all) {
          if (!el.children.length && (el.textContent || '').trim()) {
            if (el.scrollHeight > el.clientHeight + 4 && getComputedStyle(el).overflowY === 'hidden') {
              out.clipped.push({ el: desc(el), scrollH: el.scrollHeight, clientH: el.clientHeight });
            }
          }
        }

        // 3. Interactive elements overlapped by a later sibling section
        //    (the hero-CTA-under-next-section bug class)
        const interactive = [...document.querySelectorAll('a[href], button, input, textarea, select')].filter(visible);
        for (const el of interactive) {
          const r = el.getBoundingClientRect();
          const cx = r.left + r.width / 2;
          const cy = r.top + r.height / 2;
          if (cy < 0 || cy > window.innerHeight || cx < 0 || cx > vw) continue; // offscreen: can scroll to it
          const hit = document.elementFromPoint(cx, cy);
          if (hit && hit !== el && !el.contains(hit) && !hit.contains(el)) {
            out.overlaps.push({ el: desc(el), coveredBy: desc(hit) });
          }
        }

        // 4. Tap targets below 44px (mobile only — caller filters)
        for (const el of interactive) {
          const r = el.getBoundingClientRect();
          const insideNav = el.closest('nav, footer');
          if ((r.height < 32 || r.width < 32) && !insideNav) {
            out.tiny.push({ el: desc(el), w: Math.round(r.width), h: Math.round(r.height) });
          }
        }
        return out;
      });

      if (res.hScroll) {
        findings.push({ page: pname, vp: vname, kind: 'H_SCROLL',
          detail: `page scrolls sideways: ${res.hScroll.scrollWidth}px content in ${res.hScroll.viewport}px viewport` });
      }
      for (const o of res.overflow.slice(0, 4)) {
        findings.push({ page: pname, vp: vname, kind: 'OVERFLOW',
          detail: `${o.el} → ${o.right !== undefined ? `right ${o.right} > vw ${o.vw}` : `left ${o.left} < 0`}` });
      }
      for (const o of res.overlaps.slice(0, 4)) {
        findings.push({ page: pname, vp: vname, kind: 'COVERED',
          detail: `${o.el}  ←covered by→  ${o.coveredBy}` });
      }
      for (const o of res.clipped.slice(0, 3)) {
        findings.push({ page: pname, vp: vname, kind: 'CLIPPED',
          detail: `${o.el} (${o.scrollH}px content in ${o.clientH}px box)` });
      }
      if (vname === 'phone') {
        for (const o of res.tiny.slice(0, 3)) {
          findings.push({ page: pname, vp: vname, kind: 'TAP_TARGET', detail: `${o.el} is ${o.w}×${o.h}` });
        }
      }
      for (const e of errs.slice(0, 3)) {
        findings.push({ page: pname, vp: vname, kind: 'JS_ERROR', detail: e });
      }

      await page.screenshot({ path: `${shotDir}${pname}.${vname}.png`, fullPage: true });
      await ctx.close();
    }
    process.stdout.write('.');
  }
  await browser.close();
} catch (e) {
  console.error('FATAL', e);
  code = 1;
} finally {
  srv.kill('SIGTERM');
}

console.log('\n\n================ RESPONSIVE AUDIT ================');
if (!findings.length) {
  console.log('No layout defects detected.');
} else {
  const byKind = {};
  for (const f of findings) (byKind[f.kind] ||= []).push(f);
  for (const kind of Object.keys(byKind)) {
    console.log(`\n### ${kind}  (${byKind[kind].length})`);
    for (const f of byKind[kind]) console.log(`  [${f.page} / ${f.vp}] ${f.detail}`);
  }
}
console.log(`\nshots: ${shotDir}`);
process.exit(code);
