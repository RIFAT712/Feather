// Fetches the full contest activity log in bounded pages instead of one huge
// request, so a single query/response never has to hold 10k+ joined rows at once
// and the UI can render as pages arrive.
//
// Uses keyset pagination (before_id) rather than page numbers: contests keep
// receiving new submissions while a multi-page crawl is in progress, and
// page/offset pagination silently skips or re-shuffles rows as the underlying
// result set shifts underneath it. Cursoring on the last-seen article id is
// immune to that.
export async function fetchAllContestLogPages(code, { pageSize = 500, signal, onPage, includeReviews = true, status = null } = {}) {
  const items = [];
  let beforeId = null;
  for (;;) {
    const cursor = beforeId !== null ? `&before_id=${beforeId}` : '';
    const reviewsParam = includeReviews ? '' : '&include_reviews=false';
    const statusParam = status ? `&status=${encodeURIComponent(status)}` : '';
    const res = await fetch(`/api/contests/${code}/log?page_size=${pageSize}${cursor}${reviewsParam}${statusParam}`, { signal });
    if (!res.ok) throw new Error('Failed to load activity log');
    const payload = await res.json();
    items.push(...payload.items);
    if (onPage) onPage(items, payload);
    if (!payload.has_more) break;
    beforeId = payload.next_before_id;
  }
  return items;
}
