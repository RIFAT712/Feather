# Jury review workspace: flow mode + stat cards

Date: 2026-09-09
Route: `/:code/jury/review` and `/:code/jury/review-v2`
Files: `frontend-vue/src/views/ReviewQueue.vue`, `frontend-vue/src/styles/views/ReviewQueue.css`

## Problem

The review workspace was designed for a queue of ~50. At the current volume
(2,232 pending, 52 accepted, 380 rejected assigned to one judge; 10,699 pending
contest-wide) it fails in specific, measured ways:

- 37% of the sidebar's vertical space (~188px of 501px) is chrome before the
  first article row. Eight rows are visible, so 2,232 items is ~280 scroll-pages.
- Every row prints the submitter. When one person submitted the batch, "MS Sakib"
  is rendered 2,232 times and consumes roughly half the row width.
- The stat readout is three bare numbers on one wrapping line. It carries no
  sense of progress, share of total, or distance remaining.
- The article pane stretches Bengali wiki content across ~1,150px with no
  reading measure.
- Collapsing the panel sets `width: 0`, so opening it reflows the article the
  reviewer is reading.

The root problem is that the list is the primary navigation. At 2,232 items that
model does not hold.

## Decisions taken

The owner chose, explicitly:

1. **Pure flow** over batch triage. The article is the screen; the list becomes a
   drawer. Optimizes decisions-per-minute, trusting the queue order.
2. **Approach A** — reshape `ReviewQueue.vue` in place, rather than a new
   `/jury/flow` route or a composables-first refactor. The collapse state and the
   customizable keyboard-shortcut system already exist in the file; this reuses
   both.
3. **Stat cards restored**, four of them (Total, Pending, Accepted, Rejected),
   with a progress bar beneath.
4. **Cards live in the main-pane flow header**, full width. The drawer keeps a
   compact one-line readout.

## Design

### 1. Flow by default

`sidebarCollapsed` (`ReviewQueue.vue:43`) defaults to `true`.

The value persists per user in `localStorage` under
`review_queue_layout:<username>`, reusing the read/write pattern already
established for shortcuts at `ReviewQueue.vue:1097-1128` — including its
`try`/`catch`, because private windows and blocked site data throw on write. A
layout preference that fails to persist must not break the view.

First visit lands in flow. If the reviewer opens the drawer and leaves it open,
it stays open on return.

### 2. Stat cards

Four cards in the main-pane flow header, inserted above `.rq-article-header`.

| Card | Value | Accent |
|---|---|---|
| Total | `pending + accepted + rejected` | `--rq-text-muted` |
| Pending | `statusStats.pending` | `--rq-warning` |
| Accepted | `statusStats.accepted` | `--rq-success` |
| Rejected | `statusStats.rejected` | `--rq-danger` |

All values come from `statusStats` (`ReviewQueue.vue:562-564`), which is already
fetched. **No new endpoint, no new request.**

Visual form matches `ContestDashboard.css:143` — a 3px accent bar across the top
edge, number at 2rem/800, label at .72rem/700 uppercase with .06em tracking,
rounded bordered surface with a soft shadow.

**Theme isolation is mandatory.** `docs/STYLE_GUIDE.md:60` makes `/jury/review*`
an exception to the shared light theme; the route has its own theme switch and
`--rq-*` token set. The cards therefore get `rq-`-prefixed classes
(`.rq-stat-card`, `.rq-stat-number`, `.rq-stat-label`) built on `--rq-surface`,
`--rq-border`, `--rq-text`, `--rq-text-muted`, and the accent tokens above.
`ContestDashboard.css` is **not** imported and its hard-coded values (`#fff`,
`#c7d6e3`, `#20364d`) are **not** copied — they would break the review dark
theme.

Layout: 4-column grid at desktop width, collapsing to 2×2 below 820px, matching
the breakpoint ContestDashboard already uses.

### 3. Progress bar

Directly beneath the cards: `(accepted + rejected) / (pending + accepted + rejected)`,
currently 432 of 2,664 → 16%. Rendered as a filled track with the percentage as
text. Same token set as the cards.

### 4. Drawer

`.rq-queue-panel.is-collapsed` (`ReviewQueue.css:205`) changes from `width: 0`
to a fixed-position overlay that slides over the left edge. The article pane no
longer reflows when the drawer opens or closes.

**Key binding.** `/` and `?` are already taken — both toggle the shortcut help
panel (`ReviewQueue.vue:1224`) and both sit in `RESERVED_SHORTCUT_KEYS`
(`:1065`). The drawer toggle is therefore added as a seventh entry in
`SHORTCUT_ACTIONS` (`:1051-1058`):

```js
{ id: 'queue', label: 'Show or hide the queue drawer', default: 'q' },
```

`q` is free; the existing defaults are `a r s c u w`. Registering it in that
array rather than as a special case means it is rebindable, participates in the
existing clash detection (`:1165`), persists with the other shortcuts, and
appears in both the help panel and the on-screen hints automatically — the file
already wires all of that off `SHORTCUT_ACTIONS`.

`Esc` closes the drawer, consistent with the existing contract that Escape is
the way out of everything (`:1062-1065`).

The drawer header keeps a single compact line — `2,232 pending · 52 accepted ·
380 rejected` — since the full cards are in the flow header. This replaces
`.rq-stat-line` (`ReviewQueue.css:249`) and fixes its wrapped "380 rejected"
orphan.

### 5. Article reading measure

Wiki content inside `.rq-article` is constrained to ~72ch and centred, with
increased base size and line-height. The wiki HTML is injected wholesale, so this
is one scoped selector on the container, not a per-element pass.

### 6. Row density

When the queue is single-submitter
(`new Set(articles.map(a => a.submitter)).size === 1`), the submitter column is
omitted from list rows. Row padding tightens. Together these roughly double
rows-per-screen for the case where the drawer is open.

## Explicitly out of scope

- **Virtual scrolling.** The drawer is no longer the primary interface; 2,232 DOM
  rows stay until they measurably hurt.
- **Grouping and filtering.** That is the triage model, which was considered and
  not chosen.
- **A session throughput counter.** Proposed, not requested. The Pending card
  ticking down covers the need.
- **New routes, new components, backend changes.** None.

## Verification

1. `npm run build` from `frontend-vue/`.
2. Drive the running app in the browser: load `/0ab09f/jury/review-v2`, confirm
   flow is the default state, judge one article, confirm Pending decrements and
   Accepted or Rejected increments and the progress bar advances.
3. Open and close the drawer; confirm the article does not reflow.
4. Toggle the review theme switch; confirm no card, label, or bar is unreadable
   in dark mode. Grep the diff for hard-coded light values per
   `STYLE_GUIDE.md:68`.
5. Check 768px: the existing `mobileTab` two-pane model (`ReviewQueue.vue:42`,
   `:854`) must still work. Mobile is already effectively flow; this aligns
   desktop to it.
6. Confirm the cards reflow to 2×2 below 820px.

## Documentation to update

- **`docs/STYLE_GUIDE.md:62`** currently records that the panel was rebuilt on
  2026-09-09 to "a compact header (titlebar, search, tabs, one stat line)". This
  change supersedes the "one stat line" clause. The entry must be corrected, not
  left to contradict the code.
- **`AGENTS.md`** — append a Change Log row, per the repo convention.
