// Fetches the full contest activity log in bounded pages instead of one huge
// request, so a single query/response never has to hold 10k+ joined rows at once
// and the UI can render as pages arrive.
export async function fetchAllContestLogPages(code, { pageSize = 500, signal, onPage } = {}) {
  const items = [];
  let page = 1;
  for (;;) {
    const res = await fetch(`/api/contests/${code}/log?page=${page}&page_size=${pageSize}`, { signal });
    if (!res.ok) throw new Error('Failed to load activity log');
    const payload = await res.json();
    items.push(...payload.items);
    if (onPage) onPage(items, payload);
    if (!payload.has_more) break;
    page += 1;
  }
  return items;
}
