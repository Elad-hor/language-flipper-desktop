import { chromium } from 'playwright';
import { PNG } from 'pngjs';
import pixelmatch from 'pixelmatch';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const pages = JSON.parse(await readFile(join(root, 'pages.json'), 'utf8'));
const base = process.env.PREVIEW_URL || 'http://localhost:4321';
const widths = { desktop: 1440, mobile: 390 };
const only = process.argv.slice(2); // optional: diff only these page name(s)

await mkdir(join(root, 'build'), { recursive: true });
await mkdir(join(root, 'diff'), { recursive: true });

// Crop a PNG to a given width/height (top-left origin)
function crop(src, width, height) {
  const out = new PNG({ width, height });
  for (let y = 0; y < height; y++) {
    src.data.copy(out.data, y * width * 4, y * src.width * 4, y * src.width * 4 + width * 4);
  }
  return out;
}

const browser = await chromium.launch();
const report = [];
for (const p of pages) {
  if (only.length && !only.includes(p.name)) continue;
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
      const a = crop(ref, width, height);
      const b = crop(got, width, height);
      const diff = new PNG({ width, height });
      const mismatch = pixelmatch(a.data, b.data, diff.data, width, height, { threshold: 0.1 });
      await writeFile(join(root, 'diff', `${p.name}.${label}.png`), PNG.sync.write(diff));
      const pct = (mismatch / (width * height) * 100);
      report.push({
        page: p.name, label,
        mismatchPct: +pct.toFixed(3),
        sizeMismatch: ref.width !== got.width || ref.height !== got.height,
        refSize: [ref.width, ref.height], buildSize: [got.width, got.height],
      });
      console.log(`${p.name}.${label}: ${pct.toFixed(2)}% ${ref.height !== got.height ? '(height differs ref=' + ref.height + ' build=' + got.height + ')' : ''}`);
    } catch (e) {
      console.warn('no ref for', p.name, label, e.message);
    }
  }
  await ctx.close();
}
await writeFile(join(root, 'diff', 'report.json'), JSON.stringify(report, null, 2));
await browser.close();
