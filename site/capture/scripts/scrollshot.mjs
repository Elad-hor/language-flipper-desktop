// Screenshot a section on a given page, scrolled into view.
// Usage: node scrollshot.mjs <name> <path> <selector> [<name2> <path2> <selector2> ...]
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';
const args = process.argv.slice(2);
const srv = spawn('npm', ['run', 'preview'], { cwd: process.cwd(), stdio: 'ignore' });
async function up(){for(let i=0;i<50;i++){try{const r=await fetch('http://localhost:4321/');if(r.status)return true;}catch{}await new Promise(r=>setTimeout(r,400));}return false;}
try{
  if(!(await up())){console.log('no server');process.exit(1);}
  const b=await chromium.launch();
  for(let i=0;i<args.length;i+=3){
    const [name,path,sel]=[args[i],args[i+1],args[i+2]];
    const p=await b.newPage();
    await p.setViewportSize({width:1440,height:900});
    await p.goto('http://localhost:4321'+path,{waitUntil:'networkidle'});
    await p.evaluate((s)=>document.querySelector(s)?.scrollIntoView({block:'center'}), sel);
    await p.waitForTimeout(2000);
    const el=await p.$(sel);
    if(el) await el.screenshot({path:'/tmp/scroll-'+name+'.png'});
    await p.close();
  }
  await b.close();
  console.log('scroll shots saved');
}finally{srv.kill('SIGKILL');}
