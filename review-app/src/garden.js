export const HOUR = 3600000;
export function freshGarden(now = Date.now()) {
  return { moisture: 82, webs: 0, updatedAt: now, lastWateredAt: null, reviews: 0, entryCount: 0, wateredIds: [] };
}

// Revision watering IDs have a timestamp after the review UUID. They give
// water, but growth rewards distinct entries rather than repeated edits.
function entryIds(garden) {
  return new Set((garden.wateredIds || []).map(id => id.split(':')[0]));
}
function entryCount(garden) {
  const ids = entryIds(garden);
  return Math.max(ids.size, garden.entryCount ?? (ids.size || garden.reviews || 0));
}
export function gardenState(saved, now = Date.now()) {
  const base = saved || freshGarden(now);
  const hours = Math.max(0, (now - base.updatedAt) / HOUR);
  // A fully watered plant has one faded leaf and full cobwebs after three
  // hours without a saved entry. The existing timer redraws it each minute.
  const moisture = Math.max(0, Math.min(100, base.moisture - hours * 30));
  const webs = Math.min(1, Math.max(0, (base.webs || 0) + Math.max(0, hours - 1.5) * 0.75));
  const entries = entryCount(base);
  const growth = Math.min(1, entries / 60);
  const maxLeaves = 6 + 2 * Math.min(4, Math.floor(entries / 15));
  const leaves = moisture > 65 ? maxLeaves : moisture > 45 ? Math.ceil(maxLeaves * .8) : moisture > 28 ? Math.ceil(maxLeaves * .6) : moisture > 13 ? 2 : moisture > 2 ? 1 : 0;
  const flowers = moisture > 45 ? [8, 20, 40].filter(n => entries >= n).length : 0;
  const butterflies = moisture > 65 && webs < .25 ? [12, 30, 60].filter(n => entries >= n).length : 0;
  const label = moisture > 65 ? 'Looking lovely' : moisture > 45 ? 'A little thirsty' : moisture > 20 ? 'Ready for a drink' : webs > .2 ? 'A little neglected' : 'Waiting for some water';
  return { ...base, moisture, webs, leaves, label, droop: 1 - moisture / 100,
    entries, growth, maxLeaves, flowers, butterflies };
}
export function waterGarden(saved, reviewId, now = Date.now()) {
  const old = saved || freshGarden(now);
  if (old.wateredIds?.includes(reviewId)) return old;
  const current = gardenState(old, now);
  return { moisture: Math.min(100, current.moisture + 12), webs: Math.max(0, current.webs - .25),
    updatedAt: now, lastWateredAt: now, reviews: old.reviews + 1,
    entryCount: entryCount(old) + (entryIds(old).has(reviewId.split(':')[0]) ? 0 : 1),
    wateredIds: [...(old.wateredIds || []), reviewId] };
}
