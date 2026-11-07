export const DAY = 86400000;
export function freshGarden(now = Date.now()) {
  return { moisture: 82, webs: 0, updatedAt: now, lastWateredAt: null, reviews: 0, wateredIds: [] };
}
export function gardenState(saved, now = Date.now()) {
  const base = saved || freshGarden(now);
  const days = Math.max(0, (now - base.updatedAt) / DAY);
  const moisture = Math.max(0, Math.min(100, base.moisture - days * 7));
  const webs = Math.min(1, Math.max(0, (base.webs || 0) + Math.max(0, days - 6) * 0.18));
  const leaves = moisture > 65 ? 6 : moisture > 45 ? 5 : moisture > 28 ? 4 : moisture > 13 ? 2 : moisture > 2 ? 1 : 0;
  const label = moisture > 65 ? 'Looking lovely' : moisture > 45 ? 'A little thirsty' : moisture > 20 ? 'Ready for a drink' : webs > .2 ? 'A little neglected' : 'Waiting for some water';
  return { ...base, moisture, webs, leaves, label, droop: 1 - moisture / 100 };
}
export function waterGarden(saved, reviewId, now = Date.now()) {
  const old = saved || freshGarden(now);
  if (old.wateredIds?.includes(reviewId)) return old;
  const current = gardenState(old, now);
  return { moisture: Math.min(100, current.moisture + 12), webs: Math.max(0, current.webs - .25),
    updatedAt: now, lastWateredAt: now, reviews: old.reviews + 1, wateredIds: [...(old.wateredIds || []), reviewId] };
}
