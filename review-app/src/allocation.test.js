import test from 'node:test';
import assert from 'node:assert/strict';
import {allocationWithReviews,allocationSummary,allocationRows,kindergartenChoice,kindergartenReviewError,COMMON_KINDERGARTEN_PERCENTAGES} from './allocation.js';
import {matchesReviewTask,schoolPriorityStatus,fieldWithReviews} from './queue.js';

const schedule=(grade,model,shares={})=>({grade_scope:grade,model_label_normalized:model,named_language_shares:shares});
const original={value:['50/50','70/30','80/20'],status:'documented',schedules:[schedule('K','80/20',{Spanish:80,English:20}),schedule('1','70/30'),schedule('2-5','50/50')]};
const review=(grades,value,id)=>({review_id:id,school_id:'school',reference_year:'2025-26',grade_scope:grades,
  coding_method:'explicit_source_statement',changes:{elementary_allocation_model:{value,site_ids:['site']}}});

test('kindergarten menu offers the common models while historical percentages stay valid',()=>{
  assert.deepEqual(COMMON_KINDERGARTEN_PERCENTAGES,[90,80,70,60,50]);
  for(const percentage of [0,50,85,100]){
    const value=`${percentage}/${100-percentage}`;
    assert.deepEqual(kindergartenChoice({grade_scope:'K',allocation:value,kindergarten_partner_language_pct:String(percentage)}),{percentage,value});
  }
  for(const [percentage,allocation,grade_scope] of [['','80/20','K'],['80.5','80.5/19.5','K'],['101','101/0','K'],['80','20/80','K'],['80','80/20','1'],['80','80/20','K-5']]){
    assert.equal(kindergartenChoice({grade_scope,allocation,kindergarten_partner_language_pct:percentage}),null);
  }
});
test('new submission batches reject non-kindergarten and malformed allocation drafts',()=>{
  for(const [scope,value] of [['1','50/50'],['K-5','80/20'],['K','80.5/19.5'],['K','80/30']]){
    assert.match(kindergartenReviewError(review(scope,value,'a')),/kindergarten only/);
  }
  const current=review('K','80/20','a');current.changes.elementary_allocation_model.kindergarten_partner_language_pct=80;
  assert.equal(kindergartenReviewError(current),'');
  assert.equal(kindergartenReviewError(review('Kindergarten','80/20','legacy')),'');
  current.changes.elementary_allocation_model.kindergarten_partner_language_pct='80';
  assert.match(kindergartenReviewError(current),/valid kindergarten percentage/);
  assert.equal(kindergartenReviewError({changes:{delivery_structure:{value:'strand'}}}),'');
});

test('grade progression is displayed by grade with kindergarten as the summary',()=>{
  assert.equal(allocationSummary(original),'K: 80/20');
  assert.deepEqual(allocationRows(original).map(r=>[r.grade_scope,r.model]),[['K','80/20'],['1','70/30'],['2-5','50/50']]);
  assert.equal(allocationSummary({value:['50/50']}),'50/50');
});
test('pending corrections keep disjoint grades, replace only overlapping grades and retain sources',()=>{
  const changed=allocationWithReviews(original,[review('K','90/10','a'),review('1','60/40','b'),review('Kindergarten','85/15','c')]);
  assert.deepEqual(changed.schedules.map(r=>[r.grade_scope,r.model_label_normalized]),[['Kindergarten','85/15'],['1','60/40'],['2-5','50/50']]);
  assert.equal(original.schedules[0].model_label_normalized,'80/20');
  const broad={value:['50/50'],status:'documented',schedules:[schedule('K-5','50/50')]};
  const partial=allocationWithReviews(broad,[review('K-2','90/10','a'),review('K','80/20','b')]);
  assert.deepEqual(partial.schedules.map(r=>[r.grade_scope,r.model_label_normalized]),[['K','80/20'],['1-2','90/10'],['3-5','50/50']]);
  assert.equal(partial.schedules[2].source_grade_scope,'K-5');
});
test('a correction mode finds completed schools while normal missing-data queues retire them',()=>{
  const school={school_id:'school',sites:[{site_id:'site',known:{elementary_allocation_model:original,delivery_structure:{value:['strand'],status:'provisional'}}}],effectiveMissing:[]};
  Object.assign(school,schoolPriorityStatus(school));
  assert.equal(matchesReviewTask(school,'delivery_structure',true),false);
  assert.equal(matchesReviewTask(school,'corrections',true),true);
  const unknown={...school,priorityComplete:false,allocation_known:false,effectiveMissing:['elementary_allocation_model']};
  assert.equal(matchesReviewTask(unknown,'elementary_allocation_model'),true);
  assert.equal(matchesReviewTask({...unknown,research_lead:true},'elementary_allocation_model'),false);
  assert.equal(matchesReviewTask({...unknown,research_lead:true},'elementary_allocation_model',false,true),true);
  assert.equal(matchesReviewTask({...unknown,priority_site_ids:[]},'elementary_allocation_model'),false);
});
test('accepted, other-year and other-program local allocation decisions do not override current data',()=>{
  const school={school_id:'school'},site={site_id:'site',known:{elementary_allocation_model:original}};
  const accepted=review('K','90/10','a'),old={...review('K','80/20','b'),reference_year:'2024-25'};
  assert.deepEqual(fieldWithReviews(school,site,'elementary_allocation_model',[accepted,old],new Set(['a'])),original);
});
test('an unrelated kindergarten correction does not hide conflicts in upper-grade language shares',()=>{
  const source={value:['60/40'],status:'conflicting',schedules:[
    schedule('1-5','60/40',{Spanish:60,English:40}),schedule('1-5','60/40',{French:60,English:40})]};
  assert.equal(allocationWithReviews(source,[review('K','80/20','a')]).status,'conflicting');
});
