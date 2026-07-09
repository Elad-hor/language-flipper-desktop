import { chromium } from 'playwright';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');                 // site/capture
const pages = JSON.parse(await readFile(join(root, 'pages.json'), 'utf8'));
const widths = { desktop: 1440, mobile: 390 };
const only = process.argv[2]; // optional: capture a single page name

const browser = await chromium.launch();
for (const p of pages) {
  if (only && p.name !== only) continue;
  const ctx = await browser.newContext({ deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(p.url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500); // let fonts/animations settle

  // Raw rendered HTML
  const html = await page.content();
  await mkdir(join(root, 'content'), { recursive: true });
  await writeFile(join(root, 'content', `${p.name}.html`), html);

  // Visible text + heading outline + link map + design anchors
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
