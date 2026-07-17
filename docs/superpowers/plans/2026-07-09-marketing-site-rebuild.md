# Marketing Site Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `languageflipper.com` as a 1:1 pixel replica using Astro, living in this repo, so the site becomes prompt-editable instead of hand-edited in Elementor.

**Architecture:** Capture the live WordPress/Elementor site precisely (HTML, computed styles, assets, content, reference screenshots), then rebuild it as an Astro static site with reusable components under `site/`. A PHP script handles the contact form. Fidelity is enforced with an automated screenshot-diff harness comparing rebuilt pages against the captured references at desktop (1440px) and mobile (390px) widths. Hosting (Hostinger) and DNS (Cloudflare) are unchanged; only the files in `public_html` are swapped, after a full WordPress backup.

**Tech Stack:** Astro 4.x, Node 24 / npm 11, plain CSS (no framework), PHP 8.3 for the contact endpoint, Playwright + pixelmatch for the fidelity harness, Python 3.12 for helper scripts.

**Spec:** `docs/superpowers/specs/2026-07-09-marketing-site-rebuild-design.md`

---

## Conventions

- All work happens on branch `marketing-site-rebuild`.
- Capture artifacts live in `site/capture/` (git-ignored; regeneratable reference data, not source of truth for design but the ground truth for content/values).
- The Astro project lives in `site/`. Run all `npm` commands from `site/`.
- Reference screenshots (the target) live in `site/capture/ref/`. Rebuilt screenshots live in `site/capture/build/`. Diffs land in `site/capture/diff/`.
- **Fidelity gate:** a page is "done" when its diff against the reference is ≤ 1.0% mismatched pixels at BOTH widths, OR remaining differences are explained and accepted (e.g. video/animation frames) in the task's commit message.
- Pages to replicate (exact paths): `/`, `/about-us`, `/solutions`, `/flip-it`, `/contact-us`, `/terms-of-service`, `/privacy-policy`, plus the Hebrew mirror under `/he/…`.

---

## File Structure

```
site/
  package.json                     ← Astro project + scripts
  astro.config.mjs                 ← static output, site URL, trailingSlash
  tsconfig.json
  .gitignore                       ← ignores capture/, dist/, node_modules/
  src/
    layouts/
      BaseLayout.astro             ← <html> shell; sets lang + dir; head/meta/fonts
    components/
      Header.astro                 ← top nav bar + logo
      Nav.astro                    ← nav links (language-aware)
      Footer.astro                 ← footer columns + social + legal links
      LanguageSwitcher.astro       ← EN ↔ HE toggle for the current page
      Button.astro                 ← the pill CTA button
      Hero.astro                   ← home hero (bg image + gradient + headline)
      HowItWorks.astro             ← "How it works" section
      DownloadRow.astro            ← Mac/Windows/Premium icon row
      SolutionGrid.astro           ← 4-card "Our solution" grid
      SolutionCard.astro           ← one card
      HardTruth.astro              ← "The Hard Truth" section
      GetTheFeeling.astro          ← final CTA section
      TryItWidget.astro            ← wraps existing flip demo
      ContactForm.astro            ← contact fields → posts to contact.php
    i18n/
      en.json                      ← all English strings
      he.json                      ← all Hebrew strings
      ui.ts                        ← helper: t(lang, key), languages, RTL set
    pages/
      index.astro                  ← /
      about-us.astro
      solutions.astro
      flip-it.astro
      contact-us.astro
      terms-of-service.astro
      privacy-policy.astro
      he/
        index.astro                ← /he/  (Hebrew home; alias of /he/בית)
        about-us.astro … etc.
    styles/
      tokens.css                   ← colors, gradients, spacing, radii, fonts
      global.css                   ← resets + base element styles
  public/
    assets/…                       ← all downloaded images/icons/logo
    accessibility-statement-EN.pdf
  contact/
    contact.php                    ← form backend (deployed to host root)
  capture/                         ← git-ignored capture artifacts
    scripts/
      capture.mjs                  ← crawl live site → html/styles/content/screenshots
      download-assets.mjs          ← pull every referenced asset
      diff.mjs                     ← screenshot-diff harness (ref vs build)
    pages.json                     ← list of {path, lang, refUrl, name}
    ref/                           ← reference screenshots (target)
    build/                         ← rebuilt screenshots
    diff/                          ← diff images + report.json
    content/                       ← extracted per-page content + computed styles
```

---

## Phase 0 — Scaffolding

### Task 0: Astro project scaffold

**Files:**
- Create: `site/package.json`
- Create: `site/astro.config.mjs`
- Create: `site/tsconfig.json`
- Create: `site/.gitignore`

- [ ] **Step 1: Create the Astro project non-interactively**

Run from repo root:
```bash
cd site 2>/dev/null || mkdir -p site
```
Create `site/package.json`:
```json
{
  "name": "languageflipper-site",
  "type": "module",
  "version": "0.0.1",
  "private": true,
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview --host --port 4321",
    "capture": "node capture/scripts/capture.mjs",
    "assets": "node capture/scripts/download-assets.mjs",
    "diff": "node capture/scripts/diff.mjs"
  },
  "dependencies": {
    "astro": "^4.16.0"
  },
  "devDependencies": {
    "playwright": "^1.48.0",
    "pixelmatch": "^6.0.0",
    "pngjs": "^7.0.0"
  }
}
```

- [ ] **Step 2: Create `site/astro.config.mjs`**

```js
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://languageflipper.com',
  trailingSlash: 'always',   // WordPress URLs use trailing slashes
  build: { format: 'directory' },
  compressHTML: false,       // easier to diff / read output
});
```

- [ ] **Step 3: Create `site/tsconfig.json`**

```json
{ "extends": "astro/tsconfigs/strict" }
```

- [ ] **Step 4: Create `site/.gitignore`**

```
node_modules/
dist/
capture/ref/
capture/build/
capture/diff/
.astro/
```

- [ ] **Step 5: Install dependencies**

Run: `cd site && npm install`
Expected: installs astro + playwright + pixelmatch + pngjs with no errors.

- [ ] **Step 6: Verify dev server boots**

Run: `cd site && timeout 15 npm run dev &` then `curl -sSf http://localhost:4321/ >/dev/null && echo OK`
Expected: `OK` (Astro serves the default page). Stop the server after.

- [ ] **Step 7: Commit**

```bash
git add site/package.json site/astro.config.mjs site/tsconfig.json site/.gitignore site/package-lock.json
git commit -m "chore: scaffold Astro project for marketing site"
```

---

## Phase 1 — Capture the live site

### Task 1: Page inventory

**Files:**
- Create: `site/capture/pages.json`

- [ ] **Step 1: Enumerate every page + its Hebrew counterpart**

Create `site/capture/pages.json`:
```json
[
  { "name": "home",        "lang": "en", "path": "/",                 "url": "https://languageflipper.com/" },
  { "name": "about-us",    "lang": "en", "path": "/about-us/",        "url": "https://languageflipper.com/about-us/" },
  { "name": "solutions",   "lang": "en", "path": "/solutions/",       "url": "https://languageflipper.com/solutions/" },
  { "name": "flip-it",     "lang": "en", "path": "/flip-it/",         "url": "https://languageflipper.com/flip-it/" },
  { "name": "contact-us",  "lang": "en", "path": "/contact-us/",      "url": "https://languageflipper.com/contact-us/" },
  { "name": "terms",       "lang": "en", "path": "/terms-of-service/","url": "https://languageflipper.com/terms-of-service/" },
  { "name": "privacy",     "lang": "en", "path": "/privacy-policy/",  "url": "https://languageflipper.com/privacy-policy/" }
]
```

- [ ] **Step 2: Discover the exact Hebrew URLs**

Run:
```bash
node -e "const p=require('playwright');(async()=>{const b=await p.chromium.launch();const pg=await b.newPage();await pg.goto('https://languageflipper.com/he/%d7%91%d7%99%d7%aa/',{waitUntil:'networkidle'});const links=await pg.$$eval('a[href*=\"/he/\"]',a=>[...new Set(a.map(x=>x.href))]);console.log(links.join('\n'));await b.close();})()"
```
Expected: a list of `/he/…` URLs. Add each as a `{ "lang": "he" }` entry in `pages.json` (name suffixed `-he`, e.g. `home-he`). If a Hebrew page 404s or does not exist, omit it and note in the commit message.

- [ ] **Step 3: Commit**

```bash
git add site/capture/pages.json
git commit -m "chore: page inventory for site capture"
```

### Task 2: Capture script (HTML + computed styles + content + screenshots)

**Files:**
- Create: `site/capture/scripts/capture.mjs`

- [ ] **Step 1: Write the capture script**

Create `site/capture/scripts/capture.mjs`:
```js
import { chromium } from 'playwright';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');                 // site/capture
const pages = JSON.parse(await readFile(join(root, 'pages.json'), 'utf8'));
const widths = { desktop: 1440, mobile: 390 };

const browser = await chromium.launch();
for (const p of pages) {
  const ctx = await browser.newContext({ deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(p.url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500); // let fonts/animations settle

  // Raw rendered HTML
  const html = await page.content();
  await mkdir(join(root, 'content'), { recursive: true });
  await writeFile(join(root, 'content', `${p.name}.html`), html);

  // Visible text + heading outline + link map
  const info = await page.evaluate(() => {
    const text = document.body.innerText;
    const headings = [...document.querySelectorAll('h1,h2,h3,h4')]
      .map(h => ({ tag: h.tagName, text: h.innerText.trim() }));
    const links = [...document.querySelectorAll('a[href]')]
      .map(a => ({ text: a.innerText.trim(), href: a.href }));
    const imgs = [...document.querySelectorAll('img')].map(i => i.currentSrc || i.src);
    const bgs = [...document.querySelectorAll('*')]
      .map(el => getComputedStyle(el).backgroundImage)
      .filter(v => v && v !== 'none' && v.includes('url('));
    // Key design tokens from a few anchor elements
    const body = getComputedStyle(document.body);
    return {
      text, headings, links,
      images: [...new Set(imgs)],
      backgrounds: [...new Set(bgs)],
      fontFamily: body.fontFamily,
      color: body.color,
      background: body.backgroundColor,
    };
  });
  await writeFile(join(root, 'content', `${p.name}.json`), JSON.stringify(info, null, 2));

  // Reference screenshots at both widths
  for (const [label, w] of Object.entries(widths)) {
    await page.setViewportSize({ width: w, height: 900 });
    await page.waitForTimeout(400);
    await mkdir(join(root, 'ref'), { recursive: true });
    await page.screenshot({ path: join(root, 'ref', `${p.name}.${label}.png`), fullPage: true });
  }
  await ctx.close();
  console.log('captured', p.name);
}
await browser.close();
```

- [ ] **Step 2: Run the capture**

Run: `cd site && npx playwright install chromium && npm run capture`
Expected: console prints `captured <name>` for every page; `capture/content/*.html`, `capture/content/*.json`, and `capture/ref/*.png` exist.

- [ ] **Step 3: Sanity-check the outputs**

Run: `ls site/capture/ref/ && ls site/capture/content/`
Expected: one `.html` + `.json` per page, and two `.png` (desktop+mobile) per page.

- [ ] **Step 4: Commit the script only (ref screenshots are git-ignored)**

```bash
git add site/capture/scripts/capture.mjs
git commit -m "feat: live-site capture script (html, styles, content, screenshots)"
```

### Task 3: Download all assets

**Files:**
- Create: `site/capture/scripts/download-assets.mjs`

- [ ] **Step 1: Write the asset downloader**

Create `site/capture/scripts/download-assets.mjs`:
```js
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { dirname, join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const outDir = join(here, '..', '..', 'public', 'assets');
await mkdir(outDir, { recursive: true });

const { readdir } = await import('node:fs/promises');
const files = (await readdir(join(root, 'content'))).filter(f => f.endsWith('.json'));

const urls = new Set();
for (const f of files) {
  const j = JSON.parse(await readFile(join(root, 'content', f), 'utf8'));
  (j.images || []).forEach(u => urls.add(u));
  (j.backgrounds || []).forEach(v => {
    const m = [...v.matchAll(/url\((['"]?)(.*?)\1\)/g)];
    m.forEach(x => { if (x[2].startsWith('http')) urls.add(x[2]); });
  });
}

for (const u of urls) {
  try {
    const res = await fetch(u);
    if (!res.ok) { console.warn('skip', res.status, u); continue; }
    const buf = Buffer.from(await res.arrayBuffer());
    let name = basename(new URL(u).pathname);
    if (!name) name = 'asset-' + [...urls].indexOf(u);
    await writeFile(join(outDir, name), buf);
    console.log('saved', name);
  } catch (e) { console.warn('fail', u, e.message); }
}
console.log('done:', urls.size, 'urls');
```

- [ ] **Step 2: Download the accessibility PDF explicitly**

Run:
```bash
mkdir -p site/public
curl -sSL "https://languageflipper.com/wp-content/uploads/2026/05/accessibility-statement-EN.pdf" -o site/public/accessibility-statement-EN.pdf
```
Expected: a non-empty PDF file. Verify: `file site/public/accessibility-statement-EN.pdf` → "PDF document".

- [ ] **Step 3: Run the asset downloader**

Run: `cd site && npm run assets`
Expected: `saved <name>` lines; `site/public/assets/` populated with images/icons/logo.

- [ ] **Step 4: Commit assets + script**

```bash
git add site/capture/scripts/download-assets.mjs site/public/assets site/public/accessibility-statement-EN.pdf
git commit -m "feat: download site assets + accessibility PDF"
```

### Task 4: Screenshot-diff harness

**Files:**
- Create: `site/capture/scripts/diff.mjs`

- [ ] **Step 1: Write the diff harness**

Create `site/capture/scripts/diff.mjs`. It screenshots the locally-built site (via `npm run preview` on port 4321) and compares each page to its reference, writing a report.
```js
import { chromium } from 'playwright';
import { PNG } from 'pngjs';
import pixelmatch from 'pixelmatch';
import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const pages = JSON.parse(await readFile(join(root, 'pages.json'), 'utf8'));
const base = process.env.PREVIEW_URL || 'http://localhost:4321';
const widths = { desktop: 1440, mobile: 390 };
const only = process.argv[2]; // optional: diff a single page name

await mkdir(join(root, 'build'), { recursive: true });
await mkdir(join(root, 'diff'), { recursive: true });

const browser = await chromium.launch();
const report = [];
for (const p of pages) {
  if (only && p.name !== only) continue;
  const ctx = await browser.newContext({ deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(base + p.path, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  for (const [label, w] of Object.entries(widths)) {
    await page.setViewportSize({ width: w, height: 900 });
    await page.waitForTimeout(300);
    const buildPath = join(root, 'build', `${p.name}.${label}.png`);
    await page.screenshot({ path: buildPath, fullPage: true });

    const refPath = join(root, 'ref', `${p.name}.${label}.png`);
    try {
      const ref = PNG.sync.read(await readFile(refPath));
      const got = PNG.sync.read(await readFile(buildPath));
      const width = Math.min(ref.width, got.width);
      const height = Math.min(ref.height, got.height);
      const diff = new PNG({ width, height });
      // crop both to common size
      const crop = (src) => {
        const out = new PNG({ width, height });
        for (let y = 0; y < height; y++)
          src.data.copy(out.data, y*width*4, y*src.width*4, y*src.width*4 + width*4);
        return out;
      };
      const a = crop(ref), b = crop(got);
      const mismatch = pixelmatch(a.data, b.data, diff.data, width, height, { threshold: 0.1 });
      await writeFile(join(root, 'diff', `${p.name}.${label}.png`), PNG.sync.write(diff));
      const pct = (mismatch / (width*height) * 100);
      report.push({ page: p.name, label, mismatchPct: +pct.toFixed(3),
        sizeMismatch: ref.width!==got.width || ref.height!==got.height });
      console.log(`${p.name}.${label}: ${pct.toFixed(2)}% ${ref.height!==got.height?'(height differs)':''}`);
    } catch (e) {
      console.warn('no ref for', p.name, label, e.message);
    }
  }
  await ctx.close();
}
await writeFile(join(root, 'diff', 'report.json'), JSON.stringify(report, null, 2));
await browser.close();
```

- [ ] **Step 2: Verify the harness runs (against empty build it should report high mismatch)**

Run: `cd site && npm run build && (npm run preview & sleep 3) && npm run diff; kill %1 2>/dev/null || true`
Expected: it prints per-page mismatch percentages and writes `capture/diff/report.json`. (High mismatch now is fine — nothing is built yet.)

- [ ] **Step 3: Commit**

```bash
git add site/capture/scripts/diff.mjs
git commit -m "feat: screenshot-diff fidelity harness"
```

---

## Phase 2 — Foundation (tokens, layout, i18n)

### Task 5: Design tokens + global CSS

**Files:**
- Create: `site/src/styles/tokens.css`
- Create: `site/src/styles/global.css`

- [ ] **Step 1: Extract exact values from capture**

Read `site/capture/content/home.json` (and open a couple `ref/*.png`) to read the exact `fontFamily`, text `color`, and background colors. Identify the purple palette + gradients from the captured HTML's inline styles / stylesheet (grep the captured HTML):
```bash
grep -oiE '#[0-9a-f]{6}|rgba?\([0-9. ,]+\)|linear-gradient\([^;]+' site/capture/content/home.html | sort | uniq -c | sort -rn | head -40
```

- [ ] **Step 2: Write `site/src/styles/tokens.css` with the captured values**

Populate CSS custom properties with the ACTUAL captured colors/gradients/fonts (example structure — fill with real values from Step 1):
```css
:root {
  --lf-bg-deep: #2a0a54;          /* replace with captured deep purple */
  --lf-bg-panel: #ffffff;
  --lf-text: #ffffff;
  --lf-text-muted: #cbb8e6;
  --lf-accent: #b14cff;           /* replace with captured accent */
  --lf-cta: #c65cff;
  --lf-gold: #f5c518;             /* download headings */
  --lf-hero-gradient: linear-gradient(/* captured */);
  --lf-font: /* captured font stack */;
  --lf-radius: 12px;
  --lf-maxw: 1140px;
}
```

- [ ] **Step 3: Write `site/src/styles/global.css`**

```css
*,*::before,*::after { box-sizing: border-box; }
html,body { margin: 0; padding: 0; }
body { font-family: var(--lf-font); color: var(--lf-text); background: var(--lf-bg-deep); line-height: 1.6; }
img { max-width: 100%; display: block; }
a { color: inherit; text-decoration: none; }
.container { max-width: var(--lf-maxw); margin: 0 auto; padding: 0 20px; }
[dir="rtl"] { text-align: right; }
```

- [ ] **Step 4: Commit**

```bash
git add site/src/styles
git commit -m "feat: design tokens + global styles from captured site"
```

### Task 6: i18n scaffolding

**Files:**
- Create: `site/src/i18n/ui.ts`
- Create: `site/src/i18n/en.json`
- Create: `site/src/i18n/he.json`

- [ ] **Step 1: Write `site/src/i18n/ui.ts`**

```ts
export const languages = { en: 'English', he: 'עברית' } as const;
export type Lang = keyof typeof languages;
export const rtl = new Set<Lang>(['he']);
export const defaultLang: Lang = 'en';

import en from './en.json';
import he from './he.json';
const dict: Record<Lang, Record<string, string>> = { en, he };

export function t(lang: Lang, key: string): string {
  return dict[lang][key] ?? dict[defaultLang][key] ?? key;
}
export function dir(lang: Lang): 'ltr' | 'rtl' { return rtl.has(lang) ? 'rtl' : 'ltr'; }
```

- [ ] **Step 2: Seed `en.json` with captured English strings**

Pull the real strings from `site/capture/content/*.json` (`headings` + `text`). Create `site/src/i18n/en.json` with keys for nav + shared chrome first (page-body strings get added per page task):
```json
{
  "nav.about": "About",
  "nav.contact": "Contact Us",
  "nav.flipit": "Flip It",
  "footer.about": "About",
  "footer.aboutUs": "About us",
  "footer.home": "home",
  "footer.contact": "Contact",
  "footer.letsTalk": "Lets talk",
  "footer.flipIt": "Flip it",
  "footer.madeWith": "Made with ♡ by Language flipper",
  "footer.accessibility": "Accessibility Statement",
  "footer.terms": "Terms Of Service",
  "footer.privacy": "Privacy Policy"
}
```
(Use the EXACT casing/spelling captured, including "Lets talk" and "Dont flip out…" typos — this is a replica.)

- [ ] **Step 3: Seed `he.json` with captured Hebrew strings**

Create `site/src/i18n/he.json` with the same keys, values taken from the captured Hebrew pages (`*-he.json`). If a Hebrew page did not exist in capture, mirror only what exists and leave English fallbacks (the `t()` helper falls back automatically).

- [ ] **Step 4: Verify JSON parses**

Run: `cd site && node -e "console.log(Object.keys(require('./src/i18n/en.json')).length, Object.keys(require('./src/i18n/he.json')).length)"`
Expected: two equal (or he ≤ en) counts, no parse error.

- [ ] **Step 5: Commit**

```bash
git add site/src/i18n
git commit -m "feat: i18n scaffolding + shared EN/HE strings"
```

### Task 7: BaseLayout

**Files:**
- Create: `site/src/layouts/BaseLayout.astro`

- [ ] **Step 1: Write `BaseLayout.astro`**

```astro
---
import '../styles/tokens.css';
import '../styles/global.css';
import { dir as dirOf, type Lang } from '../i18n/ui';
interface Props { title: string; description?: string; lang?: Lang; }
const { title, description = '', lang = 'en' as Lang } = Astro.props;
---
<!doctype html>
<html lang={lang === 'he' ? 'he' : 'en-US'} dir={dirOf(lang)}>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    {description && <meta name="description" content={description} />}
    <link rel="icon" href="/assets/favicon.ico" />
    <slot name="head" />
  </head>
  <body>
    <slot />
  </body>
</html>
```

- [ ] **Step 2: Verify it type-checks/builds**

Run: `cd site && npx astro check 2>&1 | tail -5 || true`
Expected: no errors referencing BaseLayout (missing favicon is fine; replace with the captured favicon filename if different).

- [ ] **Step 3: Commit**

```bash
git add site/src/layouts/BaseLayout.astro
git commit -m "feat: BaseLayout with lang/dir handling"
```

---

## Phase 3 — Shared chrome

### Task 8: Header + Nav + LanguageSwitcher

**Files:**
- Create: `site/src/components/Nav.astro`
- Create: `site/src/components/LanguageSwitcher.astro`
- Create: `site/src/components/Header.astro`

- [ ] **Step 1: Build `Nav.astro`** — replicate the captured top nav (logo left, links right). Read `capture/content/home.json` `links` for exact labels/targets. Use `t(lang, 'nav.*')`. Prefix internal hrefs with `/he` when `lang === 'he'`.

- [ ] **Step 2: Build `LanguageSwitcher.astro`** — the EN↔HE toggle exactly as captured (the "אָ" / language control in the nav). It links the current page to its counterpart path.

- [ ] **Step 3: Build `Header.astro`** — composes logo + `Nav` + `LanguageSwitcher`, matching captured spacing/background.

- [ ] **Step 4: Commit**

```bash
git add site/src/components/Nav.astro site/src/components/LanguageSwitcher.astro site/src/components/Header.astro
git commit -m "feat: header, nav, language switcher components"
```

### Task 9: Footer

**Files:**
- Create: `site/src/components/Footer.astro`

- [ ] **Step 1: Build `Footer.astro`** — replicate the captured footer: brand, social icons (Facebook, X, YouTube, LinkedIn — use exact hrefs from capture), the About/Contact columns, "Made with ♡…" line, and the legal row (Accessibility Statement → `/accessibility-statement-EN.pdf`, Terms, Privacy). All labels via `t(lang, 'footer.*')`.

- [ ] **Step 2: Commit**

```bash
git add site/src/components/Footer.astro
git commit -m "feat: footer component"
```

### Task 10: Button

**Files:**
- Create: `site/src/components/Button.astro`

- [ ] **Step 1: Build the pill CTA `Button.astro`** — props `href`, `label`; replicate the captured gradient/rounded "Try now" button style. Add its styles to `tokens.css`/scoped `<style>`.

- [ ] **Step 2: Commit**

```bash
git add site/src/components/Button.astro
git commit -m "feat: CTA button component"
```

---

## Phase 4 — Home page

### Task 11: Home section components

**Files:**
- Create: `site/src/components/Hero.astro`
- Create: `site/src/components/HowItWorks.astro`
- Create: `site/src/components/DownloadRow.astro`
- Create: `site/src/components/SolutionCard.astro`
- Create: `site/src/components/SolutionGrid.astro`
- Create: `site/src/components/HardTruth.astro`
- Create: `site/src/components/GetTheFeeling.astro`
- Modify: `site/src/i18n/en.json` (add home-page keys)

- [ ] **Step 1: Add home-page strings to `en.json`**

Add keys for every home string captured in `capture/content/home.json` (hero headline "Dont flip out…" + Hebrew subline, hero body, "How it works" heading + paragraph, "Download Now" + 3 icon labels/sublabels, "Our solution" heading + subtitle, the 4 card titles + bodies, "The Hard Truth", "Get the feeling" + CTA). Use EXACT captured text.

- [ ] **Step 2: Build each section component** to match the captured markup/styles, pulling copy via `t(lang, …)` and images from `/assets/…`. One component at a time; keep each focused.

- [ ] **Step 3: Commit**

```bash
git add site/src/components site/src/i18n/en.json
git commit -m "feat: home page section components"
```

### Task 12: Assemble + verify home page

**Files:**
- Create: `site/src/pages/index.astro`

- [ ] **Step 1: Compose the home page**

```astro
---
import BaseLayout from '../layouts/BaseLayout.astro';
import Header from '../components/Header.astro';
import Hero from '../components/Hero.astro';
import HowItWorks from '../components/HowItWorks.astro';
import DownloadRow from '../components/DownloadRow.astro';
import SolutionGrid from '../components/SolutionGrid.astro';
import HardTruth from '../components/HardTruth.astro';
import GetTheFeeling from '../components/GetTheFeeling.astro';
import Footer from '../components/Footer.astro';
const lang = 'en';
---
<BaseLayout title="Language Flipper | Fix Keyboard Layout Typing Mistakes Instantly"
  description="Stop wasting time retyping gibberish. Language Flipper fixes text typed in the wrong keyboard layout across all your apps. Download now and get 40 free flips!"
  lang={lang}>
  <Header lang={lang} />
  <Hero lang={lang} />
  <HowItWorks lang={lang} />
  <DownloadRow lang={lang} />
  <SolutionGrid lang={lang} />
  <HardTruth lang={lang} />
  <GetTheFeeling lang={lang} />
  <Footer lang={lang} />
</BaseLayout>
```
(Use the EXACT captured `<title>`/meta from `capture/content/home.json`.)

- [ ] **Step 2: Build + diff the home page**

Run:
```bash
cd site && npm run build && (npm run preview & sleep 3) && npm run diff home; kill %1 2>/dev/null || true
```
Expected: `home.desktop` and `home.mobile` mismatch printed.

- [ ] **Step 3: Iterate to the fidelity gate**

Open `site/capture/diff/home.desktop.png` (highlighted diff) and `ref` vs `build` side by side. Adjust components/tokens until `report.json` shows ≤ 1.0% mismatch at both widths (or document accepted differences, e.g. animated hero background frame).

- [ ] **Step 4: Commit**

```bash
git add site/src/pages/index.astro site/src/components site/src/styles site/src/i18n
git commit -m "feat: home page assembled + fidelity-matched"
```

---

## Phase 5 — Remaining English pages

### Task 13: About, Solutions, Terms, Privacy pages

**Files:**
- Create: `site/src/pages/about-us.astro`
- Create: `site/src/pages/solutions.astro`
- Create: `site/src/pages/terms-of-service.astro`
- Create: `site/src/pages/privacy-policy.astro`
- Modify: `site/src/i18n/en.json`

- [ ] **Step 1: For each page** — add its captured strings to `en.json`, build the page reusing `Header`/`Footer` + section components (create small page-specific components only where the layout is unique, e.g. a `LegalText.astro` for terms/privacy long-form text).

- [ ] **Step 2: Build + diff each page** to the fidelity gate:
```bash
cd site && npm run build && (npm run preview & sleep 3) && for pg in about-us solutions terms privacy; do npm run diff $pg; done; kill %1 2>/dev/null || true
```
Expected: each ≤ 1.0% mismatch (or documented).

- [ ] **Step 3: Commit** (one commit per page is fine)

```bash
git add site/src/pages site/src/components site/src/i18n
git commit -m "feat: about, solutions, terms, privacy pages fidelity-matched"
```

### Task 14: Flip-it page (Try-It widget)

**Files:**
- Create: `site/src/components/TryItWidget.astro`
- Create: `site/src/pages/flip-it.astro`

- [ ] **Step 1: Port the existing widget into a component**

Wrap the existing `marketing-site/try-it-widget.html` markup/CSS/JS into `TryItWidget.astro` (its styles are already scoped to `.lf-widget`). Keep the inlined character map. Add a comment noting the map is copied from `flipper_daemon/layouts/en_he_map.json` and can drift.

- [ ] **Step 2: Build `flip-it.astro`** — `Header` + page intro (captured copy) + `TryItWidget` + `Footer`.

- [ ] **Step 3: Functional check** — load `/flip-it/`, type `akuo`, trigger the flip (button on mobile, hotkey on desktop), confirm it becomes the mapped Hebrew. Then diff:
```bash
cd site && npm run build && (npm run preview & sleep 3) && npm run diff flip-it; kill %1 2>/dev/null || true
```
Expected: widget flips text correctly; diff ≤ 1.0% (allow for textarea placeholder blinking).

- [ ] **Step 4: Commit**

```bash
git add site/src/components/TryItWidget.astro site/src/pages/flip-it.astro
git commit -m "feat: flip-it page with Try-It widget"
```

---

## Phase 6 — Contact page + backend

### Task 15: Contact form component + PHP backend

**Files:**
- Create: `site/src/components/ContactForm.astro`
- Create: `site/src/pages/contact-us.astro`
- Create: `site/contact/contact.php`

- [ ] **Step 1: Build `ContactForm.astro`** — fields First Name, Last Name, Email (required), Company (required), Message → Submit, matching captured layout. Form `method="post" action="/contact.php"`. Field `name`s: `first_name`, `last_name`, `email`, `company`, `message`.

- [ ] **Step 2: Write `site/contact/contact.php`**

```php
<?php
// contact.php — receives the Language Flipper contact form and emails it.
declare(strict_types=1);

const TO = 'falafeltikikunim@gmail.com';

function fail(int $code, string $msg): never {
  http_response_code($code);
  header('Content-Type: text/plain; charset=utf-8');
  echo $msg;
  exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') fail(405, 'Method not allowed');

// Honeypot (add a hidden 'website' field in the form; bots fill it)
if (!empty($_POST['website'] ?? '')) fail(200, 'OK');

$first   = trim($_POST['first_name'] ?? '');
$last    = trim($_POST['last_name'] ?? '');
$email   = trim($_POST['email'] ?? '');
$company = trim($_POST['company'] ?? '');
$message = trim($_POST['message'] ?? '');

if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) fail(422, 'Valid email required');
if ($company === '') fail(422, 'Company required');

$subject = 'Language Flipper contact from ' . ($first ?: 'website');
$body = "Name: $first $last\nEmail: $email\nCompany: $company\n\nMessage:\n$message\n";
$headers = 'From: Language Flipper <no-reply@languageflipper.com>' . "\r\n"
         . 'Reply-To: ' . $email . "\r\n"
         . 'Content-Type: text/plain; charset=utf-8';

// Basic header-injection guard
foreach ([$first,$last,$email,$company] as $v) {
  if (preg_match('/[\r\n]/', $v)) fail(422, 'Invalid input');
}

$ok = mail(TO, $subject, $body, $headers);
if (!$ok) fail(500, 'Send failed');

header('Location: /contact-us/?sent=1');
exit;
```
Note: `mail()` is the baseline. If the host's `mail()` has poor Gmail deliverability, swap the send for SMTP with app-password creds during deploy (Task 18) — the component/action stays the same.

- [ ] **Step 3: Add a hidden honeypot + a `?sent=1` success message** to `ContactForm.astro` so the redirect shows a "Thanks, we'll be in touch" confirmation.

- [ ] **Step 4: Build `contact-us.astro`** — `Header` + captured office-info column (US/Israel addresses + socials) + `ContactForm` + `Footer`.

- [ ] **Step 5: Lint the PHP**

Run: `php -l site/contact/contact.php` (if PHP CLI available) — Expected: "No syntax errors detected". If PHP CLI is absent, skip and note.

- [ ] **Step 6: Diff the contact page**

```bash
cd site && npm run build && (npm run preview & sleep 3) && npm run diff contact-us; kill %1 2>/dev/null || true
```
Expected: ≤ 1.0% mismatch.

- [ ] **Step 7: Commit**

```bash
git add site/src/components/ContactForm.astro site/src/pages/contact-us.astro site/contact/contact.php
git commit -m "feat: contact page + PHP mail backend"
```

---

## Phase 7 — Hebrew mirror

### Task 16: Hebrew pages + RTL

**Files:**
- Create: `site/src/pages/he/index.astro`
- Create: `site/src/pages/he/about-us.astro` … (one per page that exists in Hebrew capture)
- Modify: `site/src/i18n/he.json`

- [ ] **Step 1: Fill `he.json`** with all Hebrew strings captured from the `/he/…` pages (keys mirror the English ones).

- [ ] **Step 2: Create each Hebrew page** as a thin wrapper that renders the same components with `lang="he"` (which flips `dir` to RTL via `BaseLayout`). Match the captured Hebrew URL paths exactly (Astro supports non-ASCII filenames; if the live path is `/he/בית/`, create `src/pages/he/בית.astro`, and add a `/he/index.astro` that renders the same home so `/he/` also resolves).

- [ ] **Step 3: Verify RTL + diff each Hebrew page**

```bash
cd site && npm run build && (npm run preview & sleep 3) && for pg in home-he about-us-he solutions-he flip-it-he contact-us-he; do npm run diff $pg; done; kill %1 2>/dev/null || true
```
Expected: RTL layout matches; each ≤ 1.0% mismatch (or documented). Skip names that don't exist in capture.

- [ ] **Step 4: Commit**

```bash
git add site/src/pages/he site/src/i18n/he.json
git commit -m "feat: Hebrew (RTL) page mirror fidelity-matched"
```

---

## Phase 8 — Full-site verification

### Task 17: Whole-site fidelity pass + link/asset audit

**Files:**
- Modify: none (verification task); may touch components to fix regressions.

- [ ] **Step 1: Full diff run**

```bash
cd site && npm run build && (npm run preview & sleep 3) && npm run diff; kill %1 2>/dev/null || true
cat site/capture/diff/report.json
```
Expected: every page ≤ 1.0% at both widths (or each exception explained).

- [ ] **Step 2: Link audit** — crawl the built site and confirm no broken internal links and that external links (downloads, Gumroad, socials, PDF) match the captured targets:
```bash
cd site && (npm run preview & sleep 3) && node -e "const p=require('playwright');(async()=>{const b=await p.chromium.launch();const pg=await b.newPage();await pg.goto('http://localhost:4321/',{waitUntil:'networkidle'});const links=await pg.\$\$eval('a[href]',a=>a.map(x=>x.href));for(const l of [...new Set(links)]){try{const r=await fetch(l,{method:'HEAD'});if(!r.ok)console.log('BAD',r.status,l)}catch(e){console.log('ERR',l)}}await b.close()})()"; kill %1 2>/dev/null || true
```
Expected: no `BAD`/`ERR` for internal links. (External sites that block HEAD can be spot-checked manually.)

- [ ] **Step 3: Fix any regressions, re-diff, commit**

```bash
git add -A site
git commit -m "fix: whole-site fidelity + link audit pass"
```

---

## Phase 9 — Deploy (gated on host access)

> Requires the owner to confirm host access (FTP/SSH/hPanel). Do not execute the swap until the built site is verified and a WordPress backup exists.

### Task 18: Backup, deploy, verify, rollback-ready

**Files:**
- Create: `site/DEPLOY.md` (runbook)

- [ ] **Step 1: Write `site/DEPLOY.md`** documenting: how to build (`npm run build` → `dist/`), where files go (`public_html`), that `contact/contact.php` deploys to web root as `/contact.php`, the SMTP-vs-mail() decision, and the Cloudflare cache-purge step.

- [ ] **Step 2: Full backup of current site** — via host File Manager/hPanel: export the WordPress database and download a zip of `public_html`. Store off-host. Confirm the backup opens.

- [ ] **Step 3: Stage** — upload `dist/` to a temporary subpath (e.g. `public_html/_new/`) or a staging subdomain and load it directly to sanity-check on the real host (fonts, form POST to `contact.php`).

- [ ] **Step 4: Configure mail** — if `mail()` deliverability is poor, set the PHP to send via the host SMTP (or a Gmail app password). Send a test submission; confirm it arrives at falafeltikikunim@gmail.com.

- [ ] **Step 5: Swap** — replace `public_html` contents with `dist/` + `contact.php`. Keep the WordPress backup for rollback.

- [ ] **Step 6: Purge Cloudflare cache** and verify the live site at all URLs (EN + HE), including a real contact-form submission.

- [ ] **Step 7: Commit the runbook**

```bash
git add site/DEPLOY.md
git commit -m "docs: deployment runbook for static site"
```

---

## Phase 10 — Finish

### Task 19: Docs + finalize

- [ ] **Step 1: Update `CLAUDE.md`** — add a "Marketing Site" section: it lives in `site/` (Astro), how to build/preview/diff, how to deploy, and that it replaced the WordPress/Elementor site. Note the Try-It widget map drift caveat.
- [ ] **Step 2: Update memory** — record that the marketing site is now code in `site/`, host is Hostinger behind Cloudflare, deploy = swap `public_html`.
- [ ] **Step 3: Open a PR** from `marketing-site-rebuild` → `main` summarizing the rebuild, with before/after screenshots.

```bash
git add CLAUDE.md
git commit -m "docs: document marketing site rebuild in CLAUDE.md"
```

---

## Self-Review Notes

- **Spec coverage:** goal/non-goals (Tasks 11–17 replicate; no redesign), all 7 pages + Hebrew mirror (Tasks 12–16), contact form → Gmail (Task 15), 1:1 fidelity (diff harness Task 4 + gates throughout), hosting/DNS unchanged (Phase 9 swaps files only), backup + rollback (Task 18), Try-It widget port (Task 14), asset/link preservation (Tasks 3, 17), future editing workflow (documented Task 19). ✅
- **Placeholders:** content-replication steps intentionally source exact copy/values from the Phase-1 capture artifacts rather than hardcoding un-captured markup; every such step names the artifact to read and the objective gate (≤1% diff). Fully-determinable code (scaffold, harness, `contact.php`, `BaseLayout`, i18n helper) is written in full.
- **Type consistency:** `t(lang, key)` / `dir(lang)` from `ui.ts` used consistently; form field names (`first_name`,`last_name`,`email`,`company`,`message`) match between `ContactForm.astro` and `contact.php`; diff harness page names key off `pages.json`.
