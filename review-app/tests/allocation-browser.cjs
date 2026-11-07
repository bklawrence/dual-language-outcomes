const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const zlib=require('node:zlib');
const root=path.resolve(__dirname,'..');
const output=process.env.FIELDNOTES_TEST_OUTPUT||'/tmp/fieldnotes-allocation-browser';
fs.mkdirSync(output,{recursive:true});
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function saved(page){return page.evaluate(()=>new Promise(resolve=>{const r=indexedDB.open('fieldnotes-research-v1',1);r.onsuccess=()=>{const q=r.result.transaction('workspace').objectStore('workspace').get('current');q.onsuccess=()=>resolve(q.result.saved);};}));}
async function waitSaved(page,n){await page.waitForFunction(n=>new Promise(resolve=>{const r=indexedDB.open('fieldnotes-research-v1',1);r.onsuccess=()=>{const q=r.result.transaction('workspace').objectStore('workspace').get('current');q.onsuccess=()=>resolve(q.result?.saved?.length===n);};}),n);}
async function chooseSchool(page,school){
 await page.getByLabel('State',{exact:true}).selectOption(school.state_code);
 await page.getByLabel('District',{exact:true}).selectOption(school.district_name);
 await page.getByLabel('Search schools or districts',{exact:true}).fill(school.school_name);
 await page.locator('.school-row').filter({hasText:school.school_name}).first().click();
 await page.getByRole('heading',{name:school.school_name,exact:true}).waitFor();
}
(async()=>{
 const child=spawn(process.execPath,[path.join(root,'node_modules/vite/bin/vite.js'),'preview','--host','127.0.0.1','--port','4177','--strictPort'],{cwd:root,stdio:'ignore'});
 const url='http://127.0.0.1:4177/';let browser;
 try{
  for(let n=0;n<80;n++){try{if((await fetch(url)).ok)break;}catch{}await pause(100);}
  const executable=process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||(fs.existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined);
  browser=await chromium.launch({executablePath:executable,headless:true,args:['--no-sandbox']});
  const data=JSON.parse(fs.readFileSync(path.join(root,'public/data/queue.json'),'utf8'));
  const white=data.cases.find(c=>c.school_id==='NE5-MA-S-c7cf93db6bc0');
  // Fixed browser fixtures stay independent of future real coding progress.
  white.sites[0].known.elementary_allocation_model={value:['80/20','70/30','50/50'],status:'documented',schedules:[
    {grade_scope:'K',model_label_normalized:'80/20',named_language_shares:{Spanish:80,English:20}},
    {grade_scope:'1',model_label_normalized:'70/30',named_language_shares:{Spanish:70,English:30}},
    {grade_scope:'2-5',model_label_normalized:'50/50',named_language_shares:{Spanish:50,English:50}}]};
  function fixture(id,name,researchLead){
    const c=structuredClone(data.cases[0]);Object.assign(c,{school_id:id,school_name:name,state_code:'MA',district_name:'Allocation Test District',research_lead:researchLead,dl_status:researchLead?'needs_confirmation':'confirmed',allocation_known:false,missing:['elementary_allocation_model'],references:[]});
    c.sites=[c.sites[0]];c.sites[0].site_id=id+'-site';c.sites[0].program_event=null;
    c.sites[0].known.elementary_allocation_model={value:[],status:'not_reported',schedules:[]};
    c.sites[0].known.delivery_structure={value:['strand'],status:'documented'};data.cases.push(c);return c;
  }
  const missing=fixture('test-missing-allocation','Allocation-only test school',false);
  const lead=fixture('test-research-lead','Unconfirmed allocation research lead',true);
  assert.ok(white&&missing);
  const context=await browser.newContext({viewport:{width:1500,height:1000}});
  await context.route('**/data/queue.json*',route=>route.fulfill({json:data}));
  await context.addInitScript(()=>localStorage.setItem('fieldnotes.workspace.v1',JSON.stringify({reviewer:'Browser test researcher',drafts:{},saved:[],batches:[]})));
  await context.route('https://github.com/**',route=>route.fulfill({contentType:'text/html',body:'<h1>Test handoff; no submission</h1>'}));
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url,{waitUntil:'networkidle'});
  await page.getByLabel('Review task',{exact:true}).selectOption('elementary_allocation_model');
  assert.equal(await page.getByLabel('Allocation already recorded',{exact:true}).count(),0);
  await chooseSchool(page,missing);
  await page.getByLabel('Allocation model',{exact:true}).waitFor({state:'visible'});
  assert.ok((await page.locator('.allocation-editor').boundingBox()).y<(await page.locator('.delivery-label').boundingBox()).y);
  await page.getByLabel('Allocation model',{exact:true}).fill('80/20');
  await page.getByLabel('Grades described',{exact:true}).fill('K');
  await page.getByLabel('Evidence website URL',{exact:true}).fill('https://example.edu/kindergarten-model');
  await page.getByRole('button',{name:'Save & next',exact:true}).click();await waitSaved(page,1);
  const first=(await saved(page))[0];
  assert.deepEqual(Object.keys(first.changes),['elementary_allocation_model']);
  assert.equal(first.grade_scope,'K');assert.equal(first.changes.elementary_allocation_model.value,'80/20');
  // Corrections remain reachable even when the two priority fields are filled.
  await page.getByLabel('Review task',{exact:true}).selectOption('corrections');
  await chooseSchool(page,white);
  // Use the semantic label directly across browser accessibility implementations.
  const schedule=page.locator('[aria-label="Recorded allocation by grade"]');
  assert.ok((await schedule.innerText()).includes('Kindergarten'));
  assert.deepEqual(await schedule.locator('dd strong').allTextContents(),['80/20','70/30','50/50']);
  assert.ok((await schedule.innerText()).replace(/\s+/g,' ').includes('80% Spanish'));
  assert.equal(await page.locator('.known-strip').getByText('K: 80/20',{exact:true}).count(),1);
  await page.locator('.allocation-editor').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(output,'allocation-grades-desktop.png'),fullPage:true});
  await page.getByLabel('Allocation model',{exact:true}).fill('90/10');
  await page.getByLabel('Grades described',{exact:true}).fill('Kindergarten');
  await page.getByLabel('Evidence website URL',{exact:true}).fill('https://example.edu/corrected-kindergarten-model');
  await page.getByRole('button',{name:'Save & next',exact:true}).click();await waitSaved(page,2);
  const correction=(await saved(page)).find(r=>r.school_id===white.school_id);
  assert.equal(correction.changes.elementary_allocation_model.value,'90/10');
  assert.equal(correction.grade_scope,'Kindergarten');assert.equal(correction.reference_year,data.reference_year);
  assert.deepEqual(await schedule.locator('dd strong').allTextContents(),['90/10','70/30','50/50']);
  await page.reload({waitUntil:'networkidle'});
  await page.getByRole('heading',{name:white.school_name,exact:true}).waitFor();
  assert.equal(await page.getByLabel('Review task',{exact:true}).inputValue(),'corrections');
  assert.deepEqual(await page.locator('[aria-label="Recorded allocation by grade"] dd strong').allTextContents(),['90/10','70/30','50/50']);
  await page.getByRole('button',{name:/^Publish/}).click();
  const link=page.getByRole('link',{name:'Continue on GitHub',exact:true});await link.waitFor();
  const handoff=new URL(await link.getAttribute('href'));
  const token=handoff.searchParams.get('body').match(/DL_REVIEW_V1:([A-Za-z0-9_-]+)/)[1];
  const payload=JSON.parse(zlib.gunzipSync(Buffer.from(token,'base64url')).toString('utf8'));
  assert.equal(payload.records.find(r=>r.school_id===white.school_id).grade_scope,'Kindergarten');
  await page.getByRole('button',{name:'Close dialog',exact:true}).click();
  assert.ok(lead.research_lead);
  await page.getByLabel('Review task',{exact:true}).selectOption('elementary_allocation_model');
  await page.getByLabel('State',{exact:true}).selectOption(lead.state_code);
  await page.getByLabel('District',{exact:true}).selectOption(lead.district_name);
  await page.getByLabel('Search schools or districts',{exact:true}).fill(lead.school_name);
  assert.equal(await page.locator('.school-row').count(),0);
  await page.getByLabel('Include unconfirmed DL leads',{exact:true}).check();
  await page.locator('.school-row').filter({hasText:lead.school_name}).first().click();
  assert.ok((await page.locator('.case-status-note').innerText()).includes('not yet confirmed'));
  const mobile=await browser.newContext({viewport:{width:390,height:844}});
  await mobile.route('**/data/queue.json*',route=>route.fulfill({json:data}));
  const mp=await mobile.newPage();await mp.goto(url,{waitUntil:'networkidle'});
  await mp.getByRole('button',{name:'Choose a school',exact:true}).click();
  await mp.getByLabel('Review task',{exact:true}).selectOption('corrections');
  await chooseSchool(mp,white);
  await mp.locator('.allocation-editor').scrollIntoViewIfNeeded();
  assert.equal(await mp.getByLabel('Allocation model',{exact:true}).isVisible(),true);
  assert.equal(await mp.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),true);
  await mp.screenshot({path:path.join(output,'allocation-grades-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  await mobile.close();await context.close();
  console.log('PASS: allocation-only coding, grade progression, correction/reload/publish, candidate leads and mobile layout');
 }finally{if(browser)await browser.close();child.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
