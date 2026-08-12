// verify-worker.mjs — build, run the Worker locally, and check that the
// Cloudflare setup reproduces what Hostinger/Apache was doing: static pages,
// the ported 301s, the cache headers, and the contact route.
//
// Foreground child process on purpose — the sandbox reaps backgrounded servers.
import { spawn, execSync } from 'node:child_process';

const siteDir = new URL('../../', import.meta.url).pathname;
const BASE = 'http://127.0.0.1:8788';

console.log('building…');
execSync('npm run build', { cwd: siteDir, stdio: 'ignore' });

const srv = spawn(
  'npx',
  ['wrangler', 'dev', '--port', '8788', '--ip', '127.0.0.1', '--local'],
  { cwd: siteDir, stdio: 'ignore', env: { ...process.env, WRANGLER_SEND_METRICS: 'false' } },
);

const waitUp = async () => {
  for (let i = 0; i < 90; i++) {
    try {
      const r = await fetch(`${BASE}/`, { redirect: 'manual' });
      if (r.status) return true;
    } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
};

const results = [];
const check = (name, ok, detail = '') => {
  results.push(ok);
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  — ${detail}` : ''}`);
};

let code = 0;
try {
  if (!(await waitUp())) throw new Error('wrangler dev did not come up');

  // --- pages -------------------------------------------------------------
  for (const [name, path] of [
    ['EN home', '/'],
    ['about', '/about-us/'],
    ['flip-it', '/flip-it/'],
    ['FAQ', '/solutions/'],
    ['contact page', '/contact-us/'],
    ['HE home', '/he/%D7%91%D7%99%D7%AA/'],
    ['HE flip', '/he/%D7%AA%D7%A4%D7%9C%D7%99%D7%A4%D7%95/'],
    ['sitemap', '/sitemap-index.xml'],
    ['robots', '/robots.txt'],
    ['llms.txt', '/llms.txt'],
    ['favicon', '/favicon.svg'],
    ['accessibility PDF', '/accessibility-statement-EN.pdf'],
  ]) {
    const r = await fetch(BASE + path);
    check(`serves ${name}`, r.status === 200, `HTTP ${r.status}`);
  }

  // Hebrew page must still be RTL after the move.
  const he = await (await fetch(`${BASE}/he/%D7%91%D7%99%D7%AA/`)).text();
  check('HE page is RTL', he.includes('dir="rtl"'));
  check('install section present', he.includes('dl-help'));

  // --- redirects ported from .htaccess ------------------------------------
  for (const [from, to] of [
    ['/attributes', '/'],
    ['/attributes/', '/'],
    ['/category/uncategorized', '/'],
    ['/category/uncategorized/', '/'],
    ['/sitemap_index.xml', '/sitemap-index.xml'],
  ]) {
    const r = await fetch(BASE + from, { redirect: 'manual' });
    const loc = r.headers.get('location');
    check(`301 ${from} -> ${to}`, r.status === 301 && loc === to, `HTTP ${r.status} -> ${loc}`);
  }

  // --- cache headers ported from .htaccess --------------------------------
  // Exact-match, not "contains". Cloudflare COMBINES every matching _headers
  // rule instead of letting the most specific win, so a stray catch-all
  // silently produces "max-age=0, must-revalidate, max-age=31536000,
  // immutable" — which browsers read as max-age=0. A `.includes('immutable')`
  // assertion passes happily against that broken header; this one doesn't.
  const html = await fetch(`${BASE}/`);
  check('HTML revalidates',
    html.headers.get('cache-control') === 'public, max-age=0, must-revalidate',
    html.headers.get('cache-control'));

  const asset = (await (await fetch(`${BASE}/`)).text()).match(/\/_astro\/[^"]+\.js/)?.[0];
  if (asset) {
    const a = await fetch(BASE + asset);
    check('hashed asset immutable (and ONLY that)',
      a.headers.get('cache-control') === 'public, max-age=31536000, immutable',
      a.headers.get('cache-control'));
  } else {
    check('found a hashed asset to check', false);
  }

  // --- contact route reaches the Worker -----------------------------------
  for (const path of ['/contact', '/contact.php']) {
    const get = await fetch(BASE + path, { redirect: 'manual' });
    check(`${path} rejects GET (Worker is handling it)`, get.status === 405, `HTTP ${get.status}`);

    // No API key configured locally, so a valid POST should fail loudly with
    // 500 rather than silently pretending to succeed.
    const fd = new FormData();
    fd.append('email', 'a@b.com');
    fd.append('company', 'Test');
    fd.append('redirect', '/contact-us/');
    const post = await fetch(BASE + path, { method: 'POST', body: fd, redirect: 'manual' });
    check(`${path} POST reaches the handler`, post.status === 500, `HTTP ${post.status}`);

    // Validation still applies through the real Worker, not just in unit tests.
    const bad = new FormData();
    bad.append('email', 'nope');
    bad.append('company', 'Test');
    const badRes = await fetch(BASE + path, { method: 'POST', body: bad, redirect: 'manual' });
    check(`${path} rejects a bad email`, badRes.status === 422, `HTTP ${badRes.status}`);
  }

  // --- 404 ----------------------------------------------------------------
  const missing = await fetch(`${BASE}/definitely-not-a-page/`, { redirect: 'manual' });
  check('unknown path 404s', missing.status === 404, `HTTP ${missing.status}`);
} catch (e) {
  console.error('FATAL', e);
  code = 1;
} finally {
  srv.kill('SIGTERM');
}

const passed = results.filter(Boolean).length;
console.log(`\n================ ${passed}/${results.length} passed ================`);
if (passed !== results.length) code = 1;
process.exit(code);
