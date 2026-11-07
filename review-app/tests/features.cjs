const assert=require('node:assert/strict');
const path=require('node:path');

// Isolated fixtures exercise queue retirement and status events without sending
// synthetic research to GitHub or depending on the next real review batch.
module.exports=async function({browser,url,data,output,workspace,waitSaved}){
  const fixture=structuredClone(data);
  const template=data.cases.find(c=>c.sites.length===1);
  function school(id,name,count=1,complete=false){
    const c=structuredClone(template);
    Object.assign(c,{school_id:id,school_name:name,district_name:'Test District',allocation_known:true,research_lead:false,dl_status:'confirmed',
      missing:['delivery_structure','population_model']});
    c.sites=Array.from({length:count},(_,i)=>{
      const s=structuredClone(template.sites[0]);
      Object.assign(s,{site_id:id+'-'+i,program_id:id+'-program-'+i,label:i?'English + Mandarin':'English + Spanish',program_event:null});
      s.known.elementary_allocation_model={value:['50/50'],status:'documented'};
      s.known.delivery_structure={value:complete?['strand']:[],status:complete?'documented':'not_reported'};
      s.known.population_model={value:[],status:'not_reported'};
      return s;
    });return c;
  }
  fixture.cases=[school('complete','Already Complete',1,true),school('finish','Complete After Coding'),
    school('multi','Multiple Programs',2),school('end','Program Ended'),school('move','Program Moved')];
  const known=school('known','Recorded Whole School',1,true);
  known.allocation_known=false;known.missing=['elementary_allocation_model','population_model'];
  known.sites[0].known.elementary_allocation_model={value:[],status:'not_reported'};
  known.sites[0].known.delivery_structure.status='provisional';
  known.sites[0].known.delivery_structure.value=['whole_school'];
  fixture.cases.push(known);
  fixture.accepted_review_ids=[];fixture.accepted_batch_ids=[];
  fixture.destination_schools=[{school_id:'destination',school_name:'New Campus',district_name:'Test District',state_code:'TX'}];
  fixture.leaderboard=[{reviewer:'Researcher',reviews:12,schools:10,submissions:3,states:3,evidence_only:5},
    {reviewer:'Reviewer Two',reviews:1,schools:1,submissions:1,states:1,evidence_only:0}];
  const context=await browser.newContext({viewport:{width:1500,height:1000}});
  await context.addInitScript(()=>localStorage.setItem('fieldnotes.workspace.v1',JSON.stringify({reviewer:'Researcher',saved:[],drafts:{},batches:[]})));
  await context.route('**/data/queue.json*',route=>route.fulfill({json:fixture}));
  await context.route('https://github.com/**',route=>route.abort());
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const otherContext=await browser.newContext({viewport:{width:1500,height:1000}});
  await otherContext.route('**/data/queue.json*',route=>route.fulfill({json:fixture}));
  const otherPage=await otherContext.newPage();
  try{
    await otherPage.goto(url,{waitUntil:'networkidle'});
    await otherPage.getByLabel('Review task',{exact:true}).selectOption('');
    await otherPage.getByLabel('Search schools or districts').fill('Complete After Coding');
    assert.equal(await otherPage.locator('.school-row').count(),1);
    await page.goto(url,{waitUntil:'networkidle'});
    await page.getByRole('heading',{name:'Review queue',exact:true}).waitFor();
    const rows=()=>page.locator('.school-row');
    async function choose(name){
      await page.getByRole('button',{name:/Review queue/}).click();
      await page.getByLabel('Review task',{exact:true}).selectOption('');
      await page.getByLabel('Search schools or districts').fill(name);
      await rows().filter({hasText:name}).click();
      await page.locator('.case-page-header h1').filter({hasText:name}).waitFor();
    }
    await page.getByLabel('Review task',{exact:true}).selectOption('');
    assert.equal(await rows().count(),5);
    await page.getByLabel('Search schools or districts').fill('Already Complete');
    assert.equal(await rows().count(),0);
    await choose('Complete After Coding');
    await page.getByRole('radio',{name:/Strand DL runs/}).check();
    await page.getByLabel('Evidence website URL').fill('https://example.edu/completion');
    await page.getByRole('button',{name:'Save & next',exact:true}).click();await waitSaved(page,1);
    assert.equal(await rows().count(),0);
    assert.equal(await page.locator('.case-page-header h1').count(),0);
    // History remains editable, but leaving its editor returns to active work.
    await page.getByRole('button',{name:/My reviews/}).click();
    await page.getByRole('button',{name:'Edit review',exact:true}).click();
    assert.equal(await page.locator('.case-page-header h1').innerText(),'Complete After Coding');
    await page.getByRole('button',{name:/Review queue/}).click();
    assert.equal(await page.locator('.case-page-header h1').count(),0);
    // A publication refresh switches to canonical facts and still hides it.
    const first=(await workspace(page)).saved[0];
    fixture.accepted_review_ids.push(first.review_id);
    fixture.cases[1].sites[0].known.delivery_structure={value:['strand'],status:'documented'};
    await otherPage.evaluate(()=>window.dispatchEvent(new Event('focus')));
    await otherPage.locator('.school-row').waitFor({state:'hidden'});
    assert.equal((await workspace(otherPage)).saved.length,0);
    await page.getByRole('button',{name:/Leaderboard/}).click();
    await page.getByRole('heading',{name:'Leaderboard',exact:true}).waitFor();
    const table=page.getByRole('table');
    assert.equal(await table.getByRole('row').count(),3);
    const myRow=table.getByRole('row').filter({hasText:'Researcher'});
    assert.equal(await myRow.locator('td').nth(1).innerText(),'12');
    assert.equal(await myRow.getByLabel('Ten reviews badge: 10 published reviews').count(),1);
    assert.equal(await myRow.getByLabel('Source scout badge: 5 evidence-only reviews').count(),1);
    await page.getByRole('button',{name:'Refresh totals',exact:true}).click();
    await page.screenshot({path:path.join(output,'leaderboard.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),true);
    await page.screenshot({path:path.join(output,'leaderboard-mobile.png'),fullPage:true});
    await page.setViewportSize({width:1500,height:1000});
    await page.getByRole('button',{name:/Review queue/}).click();
    assert.equal(await rows().count(),0);
    // One program's status cannot retire a different language at the campus.
    await choose('Multiple Programs');
    await page.getByLabel('Program operating status').selectOption('ended');
    assert.equal(await page.getByRole('checkbox',{name:/Apply this status to all/}).isChecked(),false);
    await page.getByLabel('Status school year').selectOption('2024-25');
    await page.getByLabel('Evidence website URL').fill('https://example.edu/one-program-ended');
    await page.getByRole('button',{name:'Save & next',exact:true}).click();await waitSaved(page,2);
    assert.equal(await rows().count(),1);
    let latest=(await workspace(page)).saved.at(-1);
    assert.deepEqual(latest.changes,{});assert.deepEqual(latest.program_event.site_ids,['multi-0']);
    await rows().click();
    assert.equal(await page.locator('.program-picker select').inputValue(),'multi-1');
    await page.getByRole('radio',{name:/Strand DL runs/}).check();
    await page.getByRole('checkbox',{name:/Apply this delivery finding to all/}).uncheck();
    await page.getByLabel('Evidence website URL').fill('https://example.edu/remaining-program');
    await page.getByRole('button',{name:'Save & next',exact:true}).click();await waitSaved(page,3);
    assert.equal(await rows().count(),0);
    // Ended/moved findings require a dated source and may omit all four codes.
    await choose('Program Ended');
    await page.getByLabel('Program operating status').selectOption('ended');
    await page.getByLabel('Status school year').selectOption('2026-27');
    await page.getByRole('button',{name:'Save & next',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'status year cannot be later'}).waitFor();
    await page.getByLabel('Status school year').selectOption('2024-25');
    await page.getByRole('button',{name:'Save & next',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'website URL'}).waitFor();
    await page.getByLabel('Evidence website URL').fill('https://example.edu/ended');
    await page.getByRole('button',{name:'Save & next',exact:true}).click();await waitSaved(page,4);
    assert.equal(await rows().count(),0);
    latest=(await workspace(page)).saved.at(-1);
    assert.equal(latest.program_event.kind,'ended');assert.equal(latest.program_event.first_school_year,'2024-25');
    await choose('Program Moved');
    await page.getByLabel('Program operating status').selectOption('moved');
    await page.getByLabel('Destination school',{exact:true}).fill('New Campus · Test District · TX');
    await page.getByLabel('Destination school URL',{exact:true}).fill('https://example.edu/destination');
    await page.getByLabel('Evidence website URL').fill('https://example.edu/move-announcement');
    await page.getByRole('button',{name:'Save & next',exact:true}).click();await waitSaved(page,5);
    latest=(await workspace(page)).saved.at(-1);
    assert.equal(latest.program_event.kind,'moved');assert.equal(latest.program_event.destination_school_id,'destination');
    assert.equal(latest.program_event.destination_school_name,'New Campus');assert.deepEqual(latest.changes,{});
    await page.getByRole('button',{name:/My reviews/}).click();
    await page.locator('.log-card').filter({hasText:'Program Moved'}).getByRole('button',{name:'Edit review',exact:true}).click();
    assert.equal(await page.getByLabel('Program operating status').inputValue(),'moved');
    assert.equal(await page.getByLabel('Destination school',{exact:true}).inputValue(),'New Campus');
    await page.getByRole('button',{name:'Save changes',exact:true}).click();
    await page.getByRole('heading',{name:'Review and revise',exact:true}).waitFor();
    const revised=(await workspace(page)).saved.find(r=>r.school_id==='move');
    assert.equal(revised.program_event.destination_school_id,'destination');
    await page.locator('.log-card').filter({hasText:'Program Moved'}).locator('.program-event-summary').waitFor();
    // A blank new finding must not conceal or automatically re-save an
    // existing delivery value while another variable is still missing.
    await page.getByRole('button',{name:/Review queue/}).click();
    await choose('Recorded Whole School');
    const recorded=page.getByLabel('Recorded delivery model',{exact:true});
    assert.ok((await recorded.innerText()).includes('Whole school'));
    assert.ok((await recorded.innerText()).includes('Provisional'));
    assert.equal(await page.getByRole('radio',{name:/Whole school All students/}).isChecked(),false);
    await page.getByLabel('Evidence website URL').fill('https://example.edu/research-only');
    await page.getByRole('button',{name:'Save evidence & next',exact:true}).click();await waitSaved(page,6);
    assert.deepEqual((await workspace(page)).saved.at(-1).changes,{});
    assert.deepEqual(errors,[]);
    console.log('PASS: completed-school removal after save and publication, history editing, multi-program scope, dated ended/moved findings, leaderboard credit and badges, responsive layout.');
  }finally{await otherContext.close();await context.close();}
};
