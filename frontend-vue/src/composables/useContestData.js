// Shared @tanstack/vue-query wrappers for contest data that multiple views
// independently want: the dashboard, Timeline Log, and Jury Stats each want
// /stats, and Timeline Log + Jury Stats's submissions tab each want the same
// full article crawl. Replaces the old hand-rolled sessionStorage cache
// (contestDataCache.js) -- vue-query gives cache sharing across components,
// stale-while-revalidate on mount, and invalidation for free instead of
// reimplementing them by hand.
import { computed, toValue } from 'vue';
import { useQuery, useQueryClient } from '@tanstack/vue-query';
import { fetchRemainingLogPagesConcurrently, fetchAllContestLogPages } from '../utils/contestLog';

const PAGE_SIZE = 10000;

function statsKey(code) {
  return ['contest-stats', toValue(code)];
}

function logKey(code, includeReviews) {
  return ['contest-log', toValue(code), !!toValue(includeReviews)];
}

function errorLogKey(code) {
  return ['contest-log-errors', toValue(code)];
}

function submittersKey(code) {
  return ['contest-submitters', toValue(code)];
}

// Shared across Dashboard/ActivityLog/JuryStats: whichever view mounts first
// pays for the request, the rest reuse it straight from the vue-query cache.
export function useContestStats(code, options = {}) {
  return useQuery({
    queryKey: computed(() => statsKey(code)),
    queryFn: async ({ queryKey, signal }) => {
      const res = await fetch(`/api/contests/${queryKey[1]}/stats`, { signal });
      if (!res.ok) throw new Error('Could not load contest statistics.');
      return res.json();
    },
    ...options,
  });
}

// Crawls the full activity log (first page via keyset, the rest concurrently
// via offset pagination -- see contestLog.js), streaming partial progress
// into the query cache via setQueryData as pages arrive. That single queryFn
// covers both cases the old cache needed two code paths for: a first-time
// visit renders page 1 immediately while the rest streams in behind it
// (isFetching stays true until the crawl finishes), and a revisit shows the
// already-cached full list instantly while the same crawl silently
// revalidates it in the background (stale-while-revalidate).
//
// `includeReviews` toggles between ActivityLog's Timeline Log (needs review
// history per article) and JuryStats's submissions tab (cheaper crawl
// without it) -- kept as separate cache entries under separate keys rather
// than one entry with an "includesReviews" flag, since vue-query keys data
// by key, not by a payload shape.
export function useContestLog(code, includeReviews, options = {}) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: computed(() => logKey(code, includeReviews)),
    // `signal` is vue-query's own AbortSignal for this fetch -- wired through
    // to every request below so that a superseding refetch (Refresh button,
    // a delete, a second mount) actually cancels this one's in-flight
    // requests instead of letting two crawls race to write the same cache
    // entry out of order.
    queryFn: async ({ queryKey, signal }) => {
      const [, contestCode, withReviews] = queryKey;
      const reviewsParam = withReviews ? '' : '&include_reviews=false';
      const res = await fetch(`/api/contests/${contestCode}/log?page_size=${PAGE_SIZE}${reviewsParam}`, { signal });
      if (!res.ok) throw new Error('Failed to load activity log');
      const first = await res.json();
      let items = first.items;
      queryClient.setQueryData(queryKey, { items, total: first.total });
      if (first.has_more) {
        const rest = await fetchRemainingLogPagesConcurrently(contestCode, items.length, first.total, {
          includeReviews: withReviews,
          signal,
          onBatch: (batchItems) => {
            queryClient.setQueryData(queryKey, { items: [...items, ...batchItems], total: first.total });
          },
        });
        items = [...items, ...rest];
      }
      return { items, total: first.total };
    },
    ...options,
  });
}

// Errored submissions are typically a handful out of thousands and could be
// anywhere in id order -- filtered server-side, so this never has to wait on
// (or trigger) the full "All submitted" crawl above to find them.
export function useContestErrorLog(code, options = {}) {
  return useQuery({
    queryKey: computed(() => errorLogKey(code)),
    queryFn: ({ queryKey, signal }) => fetchAllContestLogPages(queryKey[1], { includeReviews: false, status: 'validation_failed', signal }),
    ...options,
  });
}

// Cheap per-submitter counts (username + article count) -- backs the
// dashboard's "Submissions by User" panel's group headers without crawling
// every article in the contest just to group them client-side.
export function useContestSubmitters(code, options = {}) {
  return useQuery({
    queryKey: computed(() => submittersKey(code)),
    queryFn: async ({ queryKey, signal }) => {
      const res = await fetch(`/api/contests/${queryKey[1]}/submitters`, { signal });
      if (!res.ok) throw new Error('Could not load submitters.');
      return (await res.json()).submitters;
    },
    ...options,
  });
}

// Minimum term length before a search actually hits the server -- one
// character matches thousands of titles and is never what someone means.
export const SEARCH_MIN_LENGTH = 2;

// Server-side title search (?q=), as opposed to filtering an
// already-crawled list in JavaScript. Finding one article among 11k used to
// require the full ~56-page crawl to have finished first; this is a single
// indexed page request that returns only matches, so it works immediately on
// a cold page load and stays cheap regardless of contest size.
//
// Kept deliberately to one page: this answers "find me this article", not
// "enumerate everything matching" -- `total` tells the caller when a term is
// too broad to be useful, and refining it is faster than paginating.
export function useContestArticleSearch(code, term, includeReviews = true, options = {}) {
  return useQuery({
    queryKey: computed(() => [
      'contest-article-search',
      toValue(code),
      (toValue(term) || '').trim(),
      !!toValue(includeReviews),
    ]),
    queryFn: async ({ queryKey, signal }) => {
      const [, contestCode, searchTerm, withReviews] = queryKey;
      const reviewsParam = withReviews ? '' : '&include_reviews=false';
      const res = await fetch(
        `/api/contests/${contestCode}/log?q=${encodeURIComponent(searchTerm)}&page_size=200${reviewsParam}`,
        { signal },
      );
      if (!res.ok) throw new Error('Search failed.');
      return res.json();
    },
    // Results for a given term don't change often enough to justify
    // re-querying on every keystroke that lands back on a previous term.
    staleTime: 30_000,
    ...options,
  });
}

// Called after anything that changes a contest's article list outside the
// normal revalidation flow (a new submission) so the next read anywhere
// fetches for real instead of reusing what existed before that change.
// Partial-matches on ['contest-log', code] to invalidate both the
// with-reviews and without-reviews variants in one call.
export function invalidateContestData(queryClient, code) {
  const c = toValue(code);
  queryClient.invalidateQueries({ queryKey: ['contest-stats', c] });
  queryClient.invalidateQueries({ queryKey: ['contest-log', c] });
  queryClient.invalidateQueries({ queryKey: errorLogKey(c) });
  queryClient.invalidateQueries({ queryKey: submittersKey(c) });
  queryClient.invalidateQueries({ queryKey: ['contest-user-log', c] });
  queryClient.invalidateQueries({ queryKey: ['contest-article-search', c] });
}

// Called right after a successful delete so a subsequent cache-first read
// (e.g. re-opening a tab moments later) doesn't briefly show articles that
// were just removed, before the next background revalidation catches up.
// Updates every cached log variant (with/without reviews, plus the errors
// list) in one call via setQueriesData's partial key matching.
export function removeArticlesFromLogCache(queryClient, code, articleIds) {
  const c = toValue(code);
  const idSet = new Set(articleIds);
  queryClient.setQueriesData({ queryKey: ['contest-log', c] }, (old) => {
    if (!old) return old;
    return {
      items: old.items.filter(item => !idSet.has(item.article_id)),
      total: Math.max(0, old.total - articleIds.length),
    };
  });
  queryClient.setQueryData(errorLogKey(c), (old) => {
    if (!old) return old;
    return old.filter(item => !idSet.has(item.article_id));
  });
  queryClient.setQueriesData({ queryKey: ['contest-article-search', c] }, (old) => {
    if (!old) return old;
    const items = old.items.filter(item => !idSet.has(item.article_id));
    return { ...old, items, total: Math.max(0, old.total - (old.items.length - items.length)) };
  });
  // Which submitter(s) these belonged to isn't known here, so the per-user
  // drill-down caches and submitter counts are invalidated wholesale rather
  // than patched -- correctness over optimization for what's a rare action.
  queryClient.invalidateQueries({ queryKey: submittersKey(c) });
  queryClient.invalidateQueries({ queryKey: ['contest-user-log', c] });
}
