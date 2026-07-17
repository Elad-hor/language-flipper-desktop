// Screenshot the top viewport of arbitrary paths. Usage: node pageshot.mjs <name> <path> [<name2> <path2> ...]
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';
const args = process.argv.slice(2);
const srv = spawn('npm', ['run', 'preview'], { cwd: process.cwd(), stdio: 'ignore' });
async function up(){for(let i=0;i<50;i++){try{const r=await fetch('http://localhost:4321/');if(r.status)return true;}catch{}await new Promise(r=>setTimeout(r,400));}return false;}
try{
  if(!(await up())){console.log('no server');process.exit(1);}
  const b=await chromium.launch();
  for(let i=0;i<args.length;i+=2){
    const name=args[i], path=args[i+1];
    const p=await b.newPage();
    await p.setViewportSize({width:1440,height:900});
    await p.goto('http://localhost:4321'+path,{waitUntil:'networkidle'});
    await p.waitForTimeout(1200);
    await p.screenshot({path:'/tmp/page-'+name+'.png'}); // viewport
    await p.close();
  }
  await b.close();
  console.log('page shots saved:', args.filter((_,i)=>i%2===0).join(','));
}finally{srv.kill('SIGKILL');}
