// 非headless(weston/wayland) 浏览器逆向测试脚本: 抓 汇联易 发票生成费用→识别→选类型→保存 全请求
// 用途: 渲染比 headless 稳定得多(报表模块/antd 组件正常渲染)。仅逆向/测试用, 不进纯API流程。
// 运行: export WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/961 (先起 weston)
const { chromium } = require('playwright');
const fs=require('fs');
// 可改: 目标 PDF + 目标类别
const DIR='/vol1/@appdata/trim.hermes/workspace/hly_invoices/clean';
const PDF=DIR+'/小杨生煎B_26312000005245285261.pdf';
const LOG='/tmp/hly_js/wl_capture.jsonl';
const KEEP=/upload|ocr|verify|expense|invoice|report|save|draft|group|tax|apportion|bind|import|bag|detail|generate|custom\/form|proxy/i;
const reqs=[];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
// 真点击(playwright locator.click) - antd 受控组件必须用真点击, evaluate b.click() 是合成点击会被免疫
async function clickReal(page,reStr,skip=0){
  const idx=await page.evaluate(({re,skip})=>{const re2=new RegExp(re);const bs=[...document.querySelectorAll('button')].filter(b=>b.offsetParent!==null);let c=0;return bs.findIndex(b=>{if(b.disabled)return false;if(!re2.test((b.textContent||'').replace(/\s/g,'')))return false;return c++>=skip;});},{re:reStr,skip});
  if(idx>=0){try{await page.locator('button').nth(idx).click();return true;}catch(e){return false;}}
  return false;
}
(async()=>{
 const browser=await chromium.launch({headless:false,args:['--no-sandbox','--disable-dev-shm-usage','--ozone-platform=wayland','--disable-gpu','--lang=zh-CN','--window-size=1440,900']});
 const ctx=await browser.newContext({viewport:{width:1440,height:900},locale:'zh-CN'});
 const page=await ctx.newPage();
 page.on('request',r=>{const u=r.url();if(/custom\/form\/draft/.test(u)){reqs.push({m:r.method(),url:u,body:(r.postData()||''),res:null});}else if(KEEP.test(u))reqs.push({m:r.method(),url:u,body:(r.postData()||'').slice(0,20000),res:null});});
 page.on('response',resp=>{const r=reqs.find(x=>x.url===resp.url()&&!x.res);if(r){r.res={status:resp.status()};resp.text().then(t=>{if(r.res)r.res.body=t.slice(0,40000)}).catch(()=>{});fs.writeFileSync(LOG,JSON.stringify(reqs,null,1));}});
 await page.goto('https://console-a2.huilianyi.com/',{waitUntil:'domcontentloaded',timeout:90000});
 await sleep(2000);
 for(const sel of ['text=Account Login','text=账号登录']){const t=page.locator(sel).first();if(await t.count()){await t.click().catch(()=>{});break;}}
 await sleep(1200);
 await page.locator('input[placeholder="请输入手机号/邮箱"],input[placeholder*="手机号"]').first().fill('138xxxxxxxx').catch(()=>{});
 await page.locator('input[placeholder="密码"],input[type=password]').first().fill('Yale549319').catch(()=>{});
 const cbx=page.locator('input[type=checkbox]').first();
 if(await cbx.count()&&!(await cbx.isChecked().catch(()=>false))){await page.locator('label:has(input[type=checkbox]),.ant-checkbox').first().click().catch(()=>{});}
 await sleep(400);
 let clicked=false;
 for(const sel of ['button:has-text("登录")','.ant-btn-primary']){const l=page.locator(sel).first();if(await l.count()){try{await l.click();clicked=true;break;}catch(e){}}}
 if(!clicked)await page.evaluate(()=>{const b=[...document.querySelectorAll('button')].find(x=>/登录|Log ?In/i.test((x.textContent||'').replace(/\s/g,'')));if(b)b.click();});
 await page.waitForTimeout(6000);
 for(let i=0;i<40;i++){if(page.url().includes('main'))break;await sleep(800);}
 await sleep(3000);
 // nav to 报销单列表
 await page.evaluate(()=>{const el=[...document.querySelectorAll('[role=menuitem],[class*=menu-item],span')].find(e=>/报销单/.test((e.textContent||'').replace(/\s/g,''))&&e.children.length===0);if(el)el.click();}).catch(()=>{});
 await page.waitForTimeout(4000);
 for(let i=0;i<25;i++){if(await page.locator('text=ERxxxxx').count().catch(()=>0))break;await sleep(1200);}
 if(await page.locator('text=ERxxxxx').count()){await page.locator('text=ERxxxxx').first().click();await page.waitForTimeout(4000);}
 // 进编辑模式(保存按钮只在编辑态出现)
 await page.evaluate(()=>{const b=[...document.querySelectorAll('button')].find(x=>/^编辑$/.test((x.textContent||'').replace(/\s/g,'')));if(b)b.click();}).catch(()=>{});
 await sleep(2500);
 await page.evaluate(()=>{const b=[...document.querySelectorAll('button')].find(x=>/发票生成费用/.test((x.textContent||'').replace(/\s/g,'')));if(b)b.click();}).catch(()=>{});
 await sleep(3000);
 const fi=page.locator('input[type=file]');
 for(let i=0;i<10;i++){if(await fi.count())break;await sleep(1000);}
 if(await fi.count()){await fi.first().setInputFiles(PDF);console.log('UPLOADED');}
 await sleep(20000);
 // 生成费用(真点击) -> 类别列表出现
 const g1=await clickReal(page,'^生成费用$|分别生成费用'); console.log('gen:',g1); await sleep(4000);
 // 选类别(真点击 .category-list-item)
 const cli=page.locator('.category-list-item:has-text("其他招待费用")').first();
 if(await cli.count()){await cli.click({timeout:10000}).catch(()=>{});}
 await sleep(1500);
 // dump 当前按钮(看向导弹窗状态)
 console.log('wizbtns:',JSON.stringify(await page.evaluate(()=>[...document.querySelectorAll('button')].filter(x=>x.offsetParent!==null).map(x=>({t:(x.textContent||'').replace(/\s/g,''),dis:x.disabled})).filter(x=>x.t.length<14)).catch(()=>[])));
 // 向导 保存 (真点击) -> 继续保存
 let sv=await clickReal(page,'^保存'); console.log('wizard save:',sv); await sleep(2500);
 let cont=await clickReal(page,'继续保存'); console.log('continue:',cont); await sleep(4000);
 await clickReal(page,'^保存$'); await sleep(6000);
 fs.writeFileSync(LOG,JSON.stringify(reqs,null,1));
 console.log('== POSTs ==');for(const x of reqs){if(x.m==='POST')console.log('POST',x.url.split('?')[0]);}
 await browser.close();
})().catch(e=>{console.error('ERR',e.message);fs.writeFileSync(LOG,JSON.stringify(reqs,null,1));process.exit(1)});
