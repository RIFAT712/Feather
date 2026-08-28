// Shared, session-scoped cache for contest data that multiple views independently
// fetch: the dashboard, Timeline Log, and Jury Stats each want /stats, and Timeline
// Log + Jury Stats's submissions tab each want the same full article crawl. Without
// this, navigating Dashboard -> Jury -> back re-fetches the same data from scratch
// every time, even seconds later. A plain module-level object is enough: it lives
// for the SPA session (survives route/component changes, since ES modules are
// singletons) and resets on a real page reload, which is the right boundary here --
// no need for localStorage/IndexedDB persistence across browser sessions.
//
// This is intentionally simple (no TTL/expiry): within one browsing session the
// data is treated as good until something explicitly refreshes it (e.g. after a
// delete). A stale view for the length of one session is an acceptable trade for
// never re-paying a fetch that already happened; a real page reload always starts
// clean.

const statsCache = new Map(); // code -> stats payload
const logCache = new Map();   // code -> { items, total }

export function getCachedStats(code) {
  return statsCache.get(code) || null;
}

export function setCachedStats(code, stats) {
  statsCache.set(code, stats);
}

// includesReviews matters because ActivityLog's Timeline Log needs review
// history per article, but JuryStats's submissions tab fetches without it
// (include_reviews=false) to keep its crawl cheaper. A cache entry written by
// JuryStats is a valid subset for JuryStats itself, but not enough for
// ActivityLog -- callers that need reviews should treat a cached entry
// without them as a miss and fetch fresh instead.
export function getCachedLog(code) {
  return logCache.get(code) || null;
}

export function setCachedLog(code, items, total, includesReviews) {
  const existing = logCache.get(code);
  // Never let a leaner fetch (no reviews) silently downgrade a cache entry
  // that already has reviews -- that would break it for a future ActivityLog
  // visit that needs them. The writer's own in-memory state is unaffected;
  // this only decides what's left behind for the next view to reuse.
  if (existing && existing.includesReviews && !includesReviews) return;
  logCache.set(code, { items, total, includesReviews });
}

// Called right after a successful delete so a subsequent cache-first read
// (e.g. re-opening a tab moments later) doesn't briefly show articles that
// were just removed, before the next background revalidation catches up.
export function removeCachedLogItems(code, articleIds) {
  const existing = logCache.get(code);
  if (!existing) return;
  const idSet = new Set(articleIds);
  logCache.set(code, {
    ...existing,
    items: existing.items.filter(item => !idSet.has(item.article_id)),
    total: Math.max(0, existing.total - articleIds.length),
  });
}

export function clearContestCache(code) {
  statsCache.delete(code);
  logCache.delete(code);
}
