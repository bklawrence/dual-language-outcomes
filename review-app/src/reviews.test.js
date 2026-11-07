import test from 'node:test';
import assert from 'node:assert/strict';
import {draftFromReview, targetsForDraft, sourceLink} from './reviews.js';

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

test('a review outside the campus inventory cannot silently be retargeted',()=>{
  const foreign=structuredClone(record);
  foreign.changes.population_model.site_ids=['other-campus'];
  assert.throws(()=>draftFromReview(foreign,school,empty),/outside the current inventory/);
});

test('review previews link only to ordinary web sources',()=>{
  assert.equal(sourceLink('https://example.edu/page?q=1'),'https://example.edu/page?q=1');
  for(const value of ['javascript:alert(1)','https://name:secret@example.edu','file:///tmp/test','bad url'])assert.equal(sourceLink(value),'');
});
