// Tight clip around the bottom of a selector on a page.
// Usage: node clipshot.mjs <name> <path> <selector>
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';
const [name, path, sel] = process.argv.slice(2);
const srv = spawn('npm', ['run', 'preview'], { cwd: process.cwd(), stdio: 'ignore' });
async function up(){for(let i=0;i<50;i++){try{const r=await fetch('http://localhost:4321/');if(r.status)return true;}catch{}await new Promise(r=>setTimeout(r,400));}return false;}
try{
  if(!(await up())){console.log('no server');process.exit(1);}
  const b=await chromium.launch();
  const p=await b.newPage();
  await p.setViewportSize({width:1440,height:900});
  await p.goto('http://localhost:4321'+path,{waitUntil:'networkidle'});
  await p.waitForTimeout(1500);
  const box=await p.evaluate((s)=>{const el=document.querySelector(s);const r=el.getBoundingClientRect();return {top:r.top+window.scrollY,bottom:r.bottom+window.scrollY,left:r.left};},sel);
  // scroll so the section bottom is centered
  await p.evaluate((y)=>window.scrollTo(0,y-450), box.bottom);
  await p.waitForTimeout(1200);
  await p.screenshot({path:'/tmp/clip-'+name+'.png', clip:{x:0,y:300,width:1440,height:400}});
  await b.close();
  console.log('clip saved');
}finally{srv.kill('SIGKILL');}
