import test from 'node:test';
import assert from 'node:assert/strict';
import {HOUR,freshGarden,gardenState,waterGarden} from './garden.js';

test('three idle hours leave even a fully watered plant rough, with faded leaves and webs',()=>{
  const start=Date.UTC(2026,10,6);const garden=freshGarden(start);
  assert.equal(gardenState(garden,start).leaves,6);
  const firstHour=gardenState(garden,start+HOUR), secondHour=gardenState(garden,start+2*HOUR);
  assert.ok(firstHour.leaves<6);assert.ok(secondHour.leaves<firstHour.leaves);
  const rough=gardenState({...garden,moisture:100},start+3*HOUR);
  assert.equal(rough.moisture,10);assert.equal(rough.leaves,1);assert.equal(rough.webs,1);assert.equal(rough.droop,.9);
  const bare=gardenState(garden,start+3*HOUR);
  assert.equal(bare.leaves,0);assert.equal(bare.webs,1);
});
test('each distinct saved decision adds a little water and revives the plant gradually',()=>{
  const start=Date.UTC(2026,10,6), now=start+3*HOUR;const original=freshGarden(start);
  const once=waterGarden(original,'one',now);assert.equal(once.moisture,12);assert.equal(once.reviews,1);
  assert.equal(once.webs,.75);assert.equal(gardenState(once,now).leaves,1);
  assert.deepEqual(waterGarden(once,'one',now),once);
  let state=once;for(let n=0;n<8;n++)state=waterGarden(state,'next-'+n,now);
  assert.equal(state.moisture,100);assert.equal(state.webs,0);assert.equal(gardenState(state,now).leaves,6);
});
test('loading a persisted plant does not refill it, age it twice, or use negative elapsed time',()=>{
  const start=Date.UTC(2026,10,6), saved=waterGarden(freshGarden(start),'r',start);
  const restored=JSON.parse(JSON.stringify(saved));
  assert.equal(gardenState(restored,start+HOUR).moisture,64);
  assert.equal(gardenState(restored,start+HOUR).moisture,64);
  assert.equal(gardenState(restored,start-HOUR).moisture,94);
});

test('distinct entries grow the plant and unlock flowers and butterflies; edits only water',()=>{
  const now=Date.UTC(2026,10,7);let garden=freshGarden(now);
  const starter=gardenState(garden,now);
  for(let i=0;i<60;i++)garden=waterGarden(garden,'review-'+i,now);
  const mature=gardenState(garden,now);
  assert.equal(mature.entries,60);assert.equal(mature.growth,1);
  assert.equal(mature.maxLeaves,14);assert.equal(mature.flowers,3);assert.equal(mature.butterflies,3);
  assert.ok(mature.growth>starter.growth);
  const edited=waterGarden(garden,'review-0:2026-11-07T01:00:00Z',now);
  assert.equal(edited.reviews,garden.reviews+1);assert.equal(edited.entryCount,60);
  assert.equal(gardenState(JSON.parse(JSON.stringify(edited)),now).growth,1);
  const rough=gardenState(garden,now+3*HOUR);
  assert.equal(rough.leaves,1);assert.equal(rough.flowers,0);assert.equal(rough.butterflies,0);
  assert.equal(rough.webs,1);assert.equal(rough.growth,1);
});

test('old saved plants keep their progress and do not count previous edits as new entries',()=>{
  const now=Date.UTC(2026,10,7);
  const old={moisture:82,webs:0,updatedAt:now,reviews:3,wateredIds:['first','first:timestamp','second']};
  assert.equal(gardenState(old,now).entries,2);
  assert.equal(waterGarden(old,'third',now).entryCount,3);
  const legacy={...old,reviews:30,wateredIds:[]};
  assert.equal(gardenState(legacy,now).entries,30);
  assert.equal(waterGarden(legacy,'next',now).entryCount,31);
});
