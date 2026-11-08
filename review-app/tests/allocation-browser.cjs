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
  await page.getByLabel('Kindergarten partner-language percentage',{exact:true}).waitFor({state:'visible'});
  assert.deepEqual(await page.getByLabel('Kindergarten partner-language percentage',{exact:true}).locator('option').evaluateAll(options=>options.map(o=>o.value)),['','90','80','70','60','50','other']);
  assert.ok((await page.locator('.allocation-editor').boundingBox()).y<(await page.locator('.delivery-label').boundingBox()).y);
  await page.getByLabel('Kindergarten partner-language percentage',{exact:true}).selectOption('80');
  assert.equal(await page.locator('.allocation-editor input').count(),0);
  assert.equal(await page.getByLabel('Grades described',{exact:true}).getAttribute('readonly'),'');
  await page.getByLabel('Evidence website URL',{exact:true}).fill('https://example.edu/kindergarten-model');
  await page.getByRole('button',{name:'Save & next',exact:true}).click();await waitSaved(page,1);
  const first=(await saved(page))[0];
  assert.deepEqual(Object.keys(first.changes),['elementary_allocation_model']);
  assert.equal(first.grade_scope,'K');assert.equal(first.changes.elementary_allocation_model.kindergarten_partner_language_pct,80);assert.equal(first.changes.elementary_allocation_model.value,'80/20');
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
  await page.getByLabel('Kindergarten partner-language percentage',{exact:true}).selectOption('90');
  assert.equal(await page.getByLabel('Grades described',{exact:true}).inputValue(),'K');
  await page.getByLabel('Evidence website URL',{exact:true}).fill('https://example.edu/corrected-kindergarten-model');
  await page.getByRole('button',{name:'Save & next',exact:true}).click();await waitSaved(page,2);
  const correction=(await saved(page)).find(r=>r.school_id===white.school_id);
  assert.equal(correction.changes.elementary_allocation_model.value,'90/10');
  assert.equal(correction.grade_scope,'K');assert.equal(correction.changes.elementary_allocation_model.kindergarten_partner_language_pct,90);assert.equal(correction.reference_year,data.reference_year);
  assert.deepEqual(await schedule.locator('dd strong').allTextContents(),['90/10','70/30','50/50']);
  await page.reload({waitUntil:'networkidle'});
  await page.getByRole('heading',{name:white.school_name,exact:true}).waitFor();
  assert.equal(await page.getByLabel('Review task',{exact:true}).inputValue(),'corrections');
  assert.deepEqual(await page.locator('[aria-label="Recorded allocation by grade"] dd strong').allTextContents(),['90/10','70/30','50/50']);
  await page.getByRole('button',{name:/^Publish/}).click();
  const link=page.getByRole('link',{name:'Continue on GitHub',exact:true});await link.waitFor();
  assert.ok((await page.getByRole('dialog').innerText()).includes('90% partner language · 10% English (kindergarten)'));
  const handoff=new URL(await link.getAttribute('href'));
  const token=handoff.searchParams.get('body').match(/DL_REVIEW_V1:([A-Za-z0-9_-]+)/)[1];
  const payload=JSON.parse(zlib.gunzipSync(Buffer.from(token,'base64url')).toString('utf8'));
  assert.equal(payload.records.find(r=>r.school_id===white.school_id).grade_scope,'K');
  assert.equal(payload.records.find(r=>r.school_id===white.school_id).changes.elementary_allocation_model.kindergarten_partner_language_pct,90);
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
  assert.equal(await mp.getByLabel('Kindergarten partner-language percentage',{exact:true}).isVisible(),true);
  assert.equal(await mp.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),true);
  await mp.screenshot({path:path.join(output,'allocation-grades-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  // Old drafts retain their original grade and notes until explicitly revised.
  const legacy=structuredClone(correction);legacy.review_id='00000000-0000-4000-8000-000000000001';
  legacy.grade_scope='1-5';legacy.notes='Original upper-grade evidence';
  legacy.changes.elementary_allocation_model.value='50/50';
  delete legacy.changes.elementary_allocation_model.kindergarten_partner_language_pct;
  const oldContext=await browser.newContext({viewport:{width:1500,height:1000}});
  await oldContext.route('**/data/queue.json*',route=>route.fulfill({json:data}));
  await oldContext.addInitScript(record=>localStorage.setItem('fieldnotes.workspace.v1',JSON.stringify({reviewer:'Browser test researcher',drafts:{},saved:[record],batches:[]})),legacy);
  const oldPage=await oldContext.newPage();await oldPage.goto(url,{waitUntil:'networkidle'});
  await oldPage.getByRole('button',{name:/My reviews/}).click();
  await oldPage.getByRole('button',{name:'Edit review',exact:true}).click();
  assert.equal(await oldPage.getByLabel('Kindergarten partner-language percentage',{exact:true}).inputValue(),'');
  assert.ok((await oldPage.locator('.legacy-allocation').innerText()).includes('50/50 for 1-5'));
  await oldPage.getByRole('button',{name:'Save changes',exact:true}).click();
  assert.ok((await oldPage.locator('.form-error').innerText()).includes('Choose the partner-language percentage in kindergarten'));
  await oldPage.getByRole('button',{name:'Clear allocation change',exact:true}).click();
  await oldPage.getByRole('button',{name:'Save evidence',exact:true}).click();await waitSaved(oldPage,1);
  const cleared=(await saved(oldPage))[0];
  assert.deepEqual(cleared.changes,{});assert.equal(cleared.notes,'Original upper-grade evidence');assert.equal(cleared.grade_scope,'1-5');
  await oldPage.getByRole('button',{name:'Edit review',exact:true}).click();
  await oldPage.getByLabel('Kindergarten partner-language percentage',{exact:true}).selectOption('other');
  await oldPage.getByLabel('Research notes',{exact:true}).fill('');
  await oldPage.getByRole('button',{name:'Save evidence',exact:true}).click();
  assert.ok((await oldPage.locator('.form-error').innerText()).includes('Describe the other kindergarten allocation'));
  await oldPage.getByLabel('Research notes',{exact:true}).fill('An unusual kindergarten schedule; retain for review.');
  await oldPage.getByRole('button',{name:'Save evidence',exact:true}).click();
  await oldPage.waitForFunction(()=>new Promise(resolve=>{const r=indexedDB.open('fieldnotes-research-v1',1);r.onsuccess=()=>{const q=r.result.transaction('workspace').objectStore('workspace').get('current');q.onsuccess=()=>resolve(q.result?.saved?.[0]?.allocation_other===true);};}));
  const other=(await saved(oldPage))[0];
  assert.deepEqual(other.changes,{});assert.equal(other.grade_scope,'K');
  assert.equal(other.notes,'An unusual kindergarten schedule; retain for review.');
  await oldPage.getByRole('button',{name:'Review & submit',exact:true}).click();
  const otherLink=oldPage.getByRole('link',{name:'Continue on GitHub',exact:true});await otherLink.waitFor();
  const otherToken=new URL(await otherLink.getAttribute('href')).searchParams.get('body').match(/DL_REVIEW_V1:([A-Za-z0-9_-]+)/)[1];
  const otherPayload=JSON.parse(zlib.gunzipSync(Buffer.from(otherToken,'base64url')).toString('utf8'));
  assert.equal(otherPayload.records[0].allocation_other,true);assert.deepEqual(otherPayload.records[0].changes,{});
  await oldPage.getByRole('button',{name:'Close dialog',exact:true}).click();
  await oldPage.getByRole('button',{name:'Edit review',exact:true}).click();
  assert.equal(await oldPage.getByLabel('Kindergarten partner-language percentage',{exact:true}).inputValue(),'other');
  await oldPage.getByLabel('Kindergarten partner-language percentage',{exact:true}).selectOption('80');
  await oldPage.getByRole('button',{name:'Save changes',exact:true}).click();
  await oldPage.waitForFunction(()=>new Promise(resolve=>{const r=indexedDB.open('fieldnotes-research-v1',1);r.onsuccess=()=>{const q=r.result.transaction('workspace').objectStore('workspace').get('current');q.onsuccess=()=>resolve(q.result?.saved?.[0]?.changes?.elementary_allocation_model?.kindergarten_partner_language_pct===80);};}));
  const revised=(await saved(oldPage))[0];
  assert.equal(revised.grade_scope,'K');assert.equal(revised.notes,'An unusual kindergarten schedule; retain for review.');assert.equal(revised.allocation_other,undefined);
  assert.equal(revised.changes.elementary_allocation_model.value,'80/20');
  await oldContext.close();await mobile.close();await context.close();
  console.log('PASS: kindergarten percentage menu, grade preservation, correction/reload/publish, legacy drafts, candidate leads and mobile layout');
 }finally{if(browser)await browser.close();child.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
