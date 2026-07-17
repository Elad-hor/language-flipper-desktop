// verify.mjs — runs the whole preview+diff cycle inside ONE foreground process.
// It spawns `astro preview` as a child, waits for it, runs diff.mjs, then kills it.
// This avoids leaving a backgrounded server that the environment reaps (exit 144).
import { spawn, execSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const siteDir = join(here, '..', '..');   // site/
const pages = process.argv.slice(2);        // page names to diff (empty = all)

const srv = spawn('npm', ['run', 'preview'], { cwd: siteDir, stdio: 'ignore' });

async function waitUp(timeoutMs = 25000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try { const r = await fetch('http://localhost:4321/'); if (r.status) return true; } catch {}
    await new Promise(r => setTimeout(r, 500));
  }
  return false;
}

let code = 0;
try {
  if (!(await waitUp())) { console.error('preview server did not come up'); code = 1; }
  else {
    execSync('node capture/scripts/diff.mjs ' + pages.join(' '), { cwd: siteDir, stdio: 'inherit' });
  }
} catch (e) {
  console.error('verify failed:', e.message);
  code = 1;
} finally {
  try { srv.kill('SIGKILL'); } catch {}
}
process.exit(code);
