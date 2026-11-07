import test from 'node:test';
import assert from 'node:assert/strict';
import {DAY,freshGarden,gardenState,waterGarden} from './garden.js';

test('the plant slowly droops, sheds leaves and gains webs across real breaks',()=>{
  const start=Date.UTC(2026,10,6);const garden=freshGarden(start);
  assert.equal(gardenState(garden,start).leaves,6);
  const week=gardenState(garden,start+7*DAY), fortnight=gardenState(garden,start+14*DAY);
  assert.ok(week.moisture<garden.moisture);assert.ok(week.leaves<6);
  assert.equal(fortnight.moisture,0);assert.equal(fortnight.leaves,0);assert.equal(fortnight.webs,1);
});
test('each distinct saved decision adds a little water and revives the plant gradually',()=>{
  const start=Date.UTC(2026,10,6), now=start+14*DAY;const original=freshGarden(start);
  const once=waterGarden(original,'one',now);assert.equal(once.moisture,12);assert.equal(once.reviews,1);
  assert.equal(once.webs,.75);assert.equal(gardenState(once,now).leaves,1);
  assert.deepEqual(waterGarden(once,'one',now),once);
  let state=once;for(let n=0;n<8;n++)state=waterGarden(state,'next-'+n,now);
  assert.equal(state.moisture,100);assert.equal(state.webs,0);assert.equal(gardenState(state,now).leaves,6);
});
test('loading a persisted plant does not refill it, age it twice, or use negative elapsed time',()=>{
  const start=Date.UTC(2026,10,6), saved=waterGarden(freshGarden(start),'r',start);
  const restored=JSON.parse(JSON.stringify(saved));
  assert.equal(gardenState(restored,start+DAY).moisture,87);
  assert.equal(gardenState(restored,start+DAY).moisture,87);
  assert.equal(gardenState(restored,start-DAY).moisture,94);
});
