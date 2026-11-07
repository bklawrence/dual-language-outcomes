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
