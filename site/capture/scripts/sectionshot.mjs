// Screenshot a given section (by selector) scrolled into view, EN + HE.
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';
const sel = process.argv[2] || '.how-section';
const srv = spawn('npm', ['run', 'preview'], { cwd: process.cwd(), stdio: 'ignore' });
async function up(){for(let i=0;i<50;i++){try{const r=await fetch('http://localhost:4321/');if(r.status)return true;}catch{}await new Promise(r=>setTimeout(r,400));}return false;}
try{
  if(!(await up())){console.log('no server');process.exit(1);}
  const b=await chromium.launch();
  for(const [name,path] of [['en','/'],['he','/he/%D7%91%D7%99%D7%AA/']]){
    const p=await b.newPage();
    await p.setViewportSize({width:1440,height:900});
    await p.goto('http://localhost:4321'+path,{waitUntil:'networkidle'});
    await p.evaluate((s)=>document.querySelector(s)?.scrollIntoView({block:'start'}), sel);
    await p.waitForTimeout(2000); // let the line rise animation finish
    const el=await p.$(sel);
    if(el) await el.screenshot({path:'/tmp/section-'+name+'.png'});
    await p.close();
  }
  await b.close();
  console.log('section shots saved');
}finally{srv.kill('SIGKILL');}
