// Both bulk endpoints cap a single request at 500 ids and reject anything
// larger outright instead of silently dropping the overflow, so send the
// selection in chunks and merge the per-chunk results.
const BULK_CHUNK = 200;

export const postBulkInChunks = async (url, ids, extraBody = {}) => {
  const succeeded = [];
  const failed = [];
  for (let start = 0; start < ids.length; start += BULK_CHUNK) {
    const chunk = ids.slice(start, start + BULK_CHUNK);
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...extraBody, article_ids: chunk }),
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(result.detail || `Request failed (${res.status})`);
      succeeded.push(...(result.succeeded || []));
      failed.push(...(result.failed || []));
    } catch (err) {
      // Keep the chunks that already committed rather than losing the run.
      failed.push(...chunk.map(id => ({ article_id: id, detail: err.message || 'Request failed' })));
    }
  }
  return { succeeded, failed };
};
