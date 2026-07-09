import { readFile, mkdir, writeFile, readdir } from 'node:fs/promises';
import { dirname, join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');                              // site/capture
const outDir = join(here, '..', '..', 'public', 'assets');  // site/public/assets
await mkdir(outDir, { recursive: true });

const files = (await readdir(join(root, 'content'))).filter(f => f.endsWith('.json'));

const urls = new Set();
for (const f of files) {
  const j = JSON.parse(await readFile(join(root, 'content', f), 'utf8'));
  (j.images || []).forEach(u => { if (u && u.startsWith('http')) urls.add(u); });
  (j.backgrounds || []).forEach(v => {
    for (const m of v.matchAll(/url\((['"]?)(.*?)\1\)/g)) {
      if (m[2].startsWith('http')) urls.add(m[2]);
    }
  });
}

let saved = 0;
for (const u of urls) {
  try {
    const res = await fetch(u);
    if (!res.ok) { console.warn('skip', res.status, u); continue; }
    const buf = Buffer.from(await res.arrayBuffer());
    let name = basename(new URL(u).pathname) || ('asset-' + saved);
    await writeFile(join(outDir, name), buf);
    saved++;
    console.log('saved', name);
  } catch (e) { console.warn('fail', u, e.message); }
}
console.log('done:', saved, 'saved of', urls.size, 'urls');
