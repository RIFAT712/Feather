// How much of a long list to draw, and when to draw more.
//
// Every list in the tool fetches far more rows than it shows and renders a
// window of them. That window used to open at a flat 100 rows everywhere: four
// screens of DOM on a phone before the user has scrolled at all, which is the
// part that makes a profile or a queue feel slow to open. The first window is
// now measured against the viewport instead, and grows by a bigger step once
// the reader is actually scrolling -- by then the cost is paid ahead of them
// rather than in front of them.
//
// Nothing here changes what is fetched. Server page sizes were tuned upward
// deliberately (see the 2026-09-01 change log entries) to cut round trips, and
// asking for a screenful at a time over HTTP would undo that.

// Rows added per scroll, once the first screenful has been passed.
export const LIST_STEP = 200;

// Rows that fit the viewport, plus a few so the scrollbar has somewhere to go
// and the first scroll is not instantly at the end. `rowHeight` is the row's
// approximate rendered height in px -- a table row is ~44, a card ~90.
export const screenful = (rowHeight = 44) => {
  const height = (typeof window !== 'undefined' && window.innerHeight) || 800;
  return Math.max(Math.ceil(height / rowHeight) + 4, 12);
};

// Page-level infinite scroll, for views that scroll the document itself. Views
// with their own scroll container (the jury queue) listen on the element.
// Returns its own teardown, so a view can hand it straight to onBeforeUnmount.
export const onPageNearBottom = (callback, margin = 400) => {
  const handler = () => {
    const scrolled = window.innerHeight + window.scrollY;
    if (scrolled >= document.documentElement.scrollHeight - margin) callback();
  };
  window.addEventListener('scroll', handler, { passive: true });
  return () => window.removeEventListener('scroll', handler);
};
