import test from 'node:test';
import assert from 'node:assert/strict';
import {schoolPriorityStatus, fieldWithReviews, programEventFor} from './queue.js';

const field=(value,status='documented')=>({value:value?[value]:[],status});
const site=(id,allocation='50/50',delivery='strand')=>({site_id:id,known:{
  elementary_allocation_model:field(allocation),delivery_structure:field(delivery),
}});
const school=sites=>({school_id:'school-1',allocation_known:false,sites});
const review=(changes,extra={})=>({review_id:'review-1',school_id:'school-1',reference_year:'2025-26',
  coding_method:'explicit_source_statement',changes,...extra});

test('both priority fields retire a school even when other structural fields are missing',()=>{
  assert.equal(schoolPriorityStatus(school([site('a')])).priorityComplete,true);
  assert.equal(schoolPriorityStatus(school([site('a','','strand')])).priorityComplete,false);
  assert.equal(schoolPriorityStatus(school([site('a','50/50','')])).priorityComplete,false);
});
test('every relevant program must be complete; secondary-only allocation is excluded',()=>{
  const a=site('a'),b=site('b','80/20','');const c=school([a,b]);
  assert.equal(schoolPriorityStatus(c).priorityComplete,false);
  const saved=[review({delivery_structure:{value:'whole_school',site_ids:['b']}})];
  assert.equal(schoolPriorityStatus(c,saved).priorityComplete,true);
  b.known.elementary_allocation_model=field('','not_applicable_secondary_entry');
  assert.equal(schoolPriorityStatus(c).priorityComplete,true);
  assert.equal(schoolPriorityStatus(school([b])).priorityComplete,false);
});
test('recorded interpretations count as filled while retaining their provisional status',()=>{
  const c=school([site('a','50/50','')]);
  const saved=[review({delivery_structure:{value:'strand',site_ids:['a']}},{coding_method:'researcher_interpretation'})];
  assert.equal(schoolPriorityStatus(c,saved).priorityComplete,true);
  assert.equal(fieldWithReviews(c,c.sites[0],'delivery_structure',saved).status,'provisional');
  assert.deepEqual(c.sites[0].known.delivery_structure.value,[]);
});
test('conflicting and later-only evidence cannot complete a school',()=>{
  for(const status of ['conflicting','later_only']){
    const s=site('a');s.known.elementary_allocation_model.status=status;
    assert.equal(schoolPriorityStatus(school([s])).priorityComplete,false);
    s.known.elementary_allocation_model.status='documented';s.known.delivery_structure.status=status;
    assert.equal(schoolPriorityStatus(school([s])).priorityComplete,false);
  }
});
test('notes, another year, and an accepted old local decision do not fill current gaps',()=>{
  const c=school([site('a','50/50','')]);
  assert.equal(schoolPriorityStatus(c,[review({},{disposition:'needs_review'})]).priorityComplete,false);
  const r=review({delivery_structure:{value:'strand',site_ids:['a']}},{reference_year:'2024-25'});
  assert.equal(schoolPriorityStatus(c,[r]).priorityComplete,false);
  r.reference_year='2025-26';
  assert.equal(schoolPriorityStatus(c,[r],new Set(['review-1'])).priorityComplete,false);
});
test('a locally saved allocation becomes visible without an already-published allocation flag',()=>{
  const c=school([site('a','','strand')]);
  const saved=[review({elementary_allocation_model:{value:'90/10',site_ids:['a']}})];
  const result=schoolPriorityStatus(c,saved);
  assert.equal(result.allocation_known,true);assert.equal(result.priorityComplete,true);
});

test('ended and moved statuses retire only affected programs from the supported year',()=>{
  const a=site('a','',''),b=site('b');const c=school([a,b]);
  const event=review({}, {coded_at:'2026-11-07T01:00:00Z',program_event:{kind:'moved',first_school_year:'2025-26',site_ids:['a']}});
  assert.equal(schoolPriorityStatus(c,[event]).priorityComplete,true);
  assert.deepEqual(schoolPriorityStatus(c,[event]).active_site_ids,['b']);
  assert.equal(programEventFor(c,a,[event],new Set(),'2024-25'),null);
  event.program_event.site_ids=['a','b'];
  assert.equal(schoolPriorityStatus(c,[event]).retired,true);
  b.program_event={kind:'ended',first_school_year:'2024-25',review_id:'old',reference_year:'2025-26'};
  const reopening=review({}, {coded_at:'2026-11-08T01:00:00Z',program_event:{kind:'operating',first_school_year:'2025-26',site_ids:['b']}});
  assert.equal(programEventFor(c,b,[reopening]).kind,'operating');
});

test('a corrected local event replaces the previous date instead of competing with it',()=>{
  const a=site('a'),c=school([a]);
  const old=review({}, {review_id:'old',program_event:{kind:'ended',first_school_year:'2023-24',site_ids:['a']}});
  const corrected=review({}, {supersedes_review_id:'old',program_event:{kind:'ended',first_school_year:'2025-26',site_ids:['a']}});
  assert.equal(programEventFor(c,a,[old,corrected],new Set(),'2024-25'),null);
  assert.equal(programEventFor(c,a,[old,corrected]).first_school_year,'2025-26');
});
