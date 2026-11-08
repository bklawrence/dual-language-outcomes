import test from 'node:test';
import assert from 'node:assert/strict';
import {draftFromReview, targetsForDraft, sourceLink, hasReviewEdits} from './reviews.js';

const school={sites:[{site_id:'spanish'},{site_id:'mandarin'},{site_id:'french'}]};
const empty={all_delivery:true};
const record={review_id:'review-1',reference_year:'2025-26',coding_method:'explicit_source_statement',
  evidence_url:'https://example.edu/overview',notes:'Source context',changes:{
    delivery_structure:{value:'strand',site_ids:['spanish','mandarin','french']},
    population_model:{value:'one_way',site_ids:['mandarin']},
    instruction_languages:{value:['English','Mandarin'],site_ids:['mandarin']},
  }};

test('old campus-wide reviews restore the specific program without moving its other variables',()=>{
  const before=structuredClone(record);
  const draft=draftFromReview(record,school,empty);
  assert.equal(draft.site_id,'mandarin');
  assert.equal(draft.all_delivery,true);
  assert.equal(draft.languages,'English, Mandarin');
  const selected=school.sites[1];
  assert.deepEqual(targetsForDraft(draft,'delivery_structure',selected,school),['spanish','mandarin','french']);
  assert.deepEqual(targetsForDraft(draft,'population_model',selected,school),['mandarin']);
  assert.deepEqual(targetsForDraft(draft,'instruction_languages',selected,school),['mandarin']);
  assert.deepEqual(targetsForDraft(draft,'elementary_allocation_model',selected,school),['mandarin']);
  draft.original_targets.population_model.push('french');
  assert.deepEqual(record,before);
});

test('editing preserves a delivery subset until its scope is explicitly changed',()=>{
  const partial=structuredClone(record);
  partial.selected_site_id='french';
  partial.changes.delivery_structure.site_ids=['spanish','mandarin'];
  const draft=draftFromReview(partial,school,empty);
  const selected=school.sites[2];
  assert.equal(draft.site_id,'french');
  assert.equal(draft.all_delivery,false);
  assert.deepEqual(targetsForDraft(draft,'delivery_structure',selected,school),['spanish','mandarin']);
  draft.all_delivery=true;
  assert.deepEqual(targetsForDraft(draft,'delivery_structure',selected,school),school.sites.map(s=>s.site_id));
  draft.all_delivery=false;draft.delivery_site_ids=['french'];
  assert.deepEqual(targetsForDraft(draft,'delivery_structure',selected,school),['french']);
});

test('parked reviews can be resumed without inventing structural values',()=>{
  const draft=draftFromReview({...record,changes:{},disposition:'needs_review'},school,empty);
  assert.equal(draft.site_id,'spanish');
  assert.equal(draft.delivery,'');assert.equal(draft.languages,'');
  assert.equal(draft.notes,'Source context');
});

test('kindergarten percentages restore exactly, including zero, while old scopes remain explicit',()=>{
  for(const percentage of [0,80,100]){
    const current={...record,grade_scope:'K',changes:{elementary_allocation_model:{value:`${percentage}/${100-percentage}`,kindergarten_partner_language_pct:percentage,site_ids:['mandarin']}}};
    const draft=draftFromReview(current,school,empty);
    assert.equal(draft.kindergarten_partner_language_pct,percentage);
    assert.equal(hasReviewEdits(current,draft,school),false);
    draft.kindergarten_partner_language_pct='';
    assert.equal(hasReviewEdits(current,draft,school),true);
  }
  const legacy={...record,grade_scope:'1-5',changes:{elementary_allocation_model:{value:'50/50',site_ids:['mandarin']}}};
  const draft=draftFromReview(legacy,school,empty);
  assert.equal(draft.allocation,'50/50');
  assert.equal(draft.grade_scope,'1-5');
  assert.equal(draft.kindergarten_partner_language_pct,'');
  assert.equal(draft.notes,'Source context');
  assert.equal(hasReviewEdits(legacy,draft,school),false);
});

test('Other allocation notes reopen with their choice and do not invent a numeric model',()=>{
  const other={...record,grade_scope:'K',changes:{},allocation_other:true,disposition:'needs_review'};
  const draft=draftFromReview(other,school,empty);
  assert.equal(draft.allocation_other,true);assert.equal(draft.allocation,'');
  assert.equal(draft.notes,'Source context');assert.equal(hasReviewEdits(other,draft,school),false);
  draft.allocation_other=false;
  assert.equal(hasReviewEdits(other,draft,school),true);
});

test('a cleared coding basis stays unselected when an entry is edited again',()=>{
  assert.equal(draftFromReview({...record,coding_method:'not_recorded'},school,empty).coding_method,'');
  assert.equal(draftFromReview({...record,coding_method:'researcher_interpretation'},school,empty).coding_method,'researcher_interpretation');
});

test('opening a saved review without changing it does not block submission',()=>{
  assert.equal(hasReviewEdits(record,undefined,school),false);
  assert.equal(hasReviewEdits(record,draftFromReview(record,school,empty),school),false);
  const cleared={...record,coding_method:'not_recorded'};
  assert.equal(hasReviewEdits(cleared,draftFromReview(cleared,school,empty),school),false);
  const note={...cleared,changes:{},disposition:'needs_review'};
  assert.equal(hasReviewEdits(note,draftFromReview(note,school,empty),school),false);
});

test('edited evidence, values, year, or program scope must be saved or discarded',()=>{
  for(const [key,value] of [['notes','Revised evidence'],['delivery','whole_school'],['reference_year','2024-25'],['coding_method','']]){
    const draft=draftFromReview(record,school,empty);draft[key]=value;
    assert.equal(hasReviewEdits(record,draft,school),true,key);
  }
  const scope=draftFromReview(record,school,empty);scope.all_delivery=false;scope.delivery_site_ids=['mandarin'];
  assert.equal(hasReviewEdits(record,scope,school),true);
  const draft=draftFromReview(record,school,empty);draft.original_targets.population_model=['french'];
  assert.equal(hasReviewEdits(record,draft,school),true);
  assert.equal(hasReviewEdits(record,draft,undefined),true);
});

test('a review outside the campus inventory cannot silently be retargeted',()=>{
  const foreign=structuredClone(record);
  foreign.changes.population_model.site_ids=['other-campus'];
  assert.throws(()=>draftFromReview(foreign,school,empty),/outside the current inventory/);
});

test('review previews link only to ordinary web sources',()=>{
  assert.equal(sourceLink('https://example.edu/page?q=1'),'https://example.edu/page?q=1');
  for(const value of ['javascript:alert(1)','https://name:secret@example.edu','file:///tmp/test','bad url'])assert.equal(sourceLink(value),'');
});

test('status-only reviews preserve the date, destination and selected-program scope when edited',()=>{
  const moved={...record,changes:{},program_event:{kind:'moved',first_school_year:'2024-25',site_ids:['mandarin'],
    destination_school_id:'other',destination_school_name:'New Campus',destination_url:'https://example.edu/new'}};
  const draft=draftFromReview(moved,school,empty);
  assert.equal(draft.site_id,'mandarin');assert.equal(draft.program_status,'moved');
  assert.equal(draft.status_year,'2024-25');assert.equal(draft.destination_id,'other');
  assert.equal(hasReviewEdits(moved,draft,school),false);
  assert.deepEqual(targetsForDraft(draft,'program_event',school.sites[1],school),['mandarin']);
  draft.all_status=true;assert.equal(hasReviewEdits(moved,draft,school),true);
  assert.deepEqual(targetsForDraft(draft,'program_event',school.sites[1],school),['spanish','mandarin','french']);
});
