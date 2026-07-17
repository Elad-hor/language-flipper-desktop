// One-off: capture phone-viewport (not full-page) shots of the hero, EN + HE.
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';

const srv = spawn('npm', ['run', 'preview'], { cwd: process.cwd(), stdio: 'ignore' });
async function up() {
  for (let i = 0; i < 50; i++) {
    try { const r = await fetch('http://localhost:4321/'); if (r.status) return true; } catch {}
    await new Promise((r) => setTimeout(r, 400));
  }
  return false;
}
try {
  if (!(await up())) { console.log('no server'); process.exit(1); }
  const b = await chromium.launch();
  const pages = [['en', '/'], ['he', '/he/%D7%91%D7%99%D7%AA/']];
  for (const [name, path] of pages) {
    const p = await b.newPage();
    await p.setViewportSize({ width: 390, height: 844 });
    await p.goto('http://localhost:4321' + path, { waitUntil: 'networkidle' });
    await p.waitForTimeout(1500);
    await p.screenshot({ path: '/tmp/hero-' + name + '.png' }); // viewport only
    await p.close();
  }
  await b.close();
  console.log('shots saved');
} finally {
  srv.kill('SIGKILL');
}
