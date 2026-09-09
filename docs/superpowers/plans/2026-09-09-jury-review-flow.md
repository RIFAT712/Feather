# Jury Review Flow Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the jury review workspace into a flow-first screen — four stat cards with a progress bar, article as the primary surface, queue demoted to a transient overlay drawer.

**Architecture:** All changes are in-place edits to one Vue view and its CSS file. No new routes, components, endpoints, or dependencies. The work reuses two systems already in `ReviewQueue.vue`: the `sidebarCollapsed` state and the customizable `SHORTCUT_ACTIONS` keyboard system.

**Tech Stack:** Vue 3 SFC, Vite, Wikimedia Codex. Plain CSS with the route-local `--rq-*` token set.

**Spec:** `docs/superpowers/specs/2026-09-09-jury-review-flow-design.md`

## Global Constraints

- **No test framework exists.** `CLAUDE.md` states there is no pytest/vitest config and no lint script. Do not add one. Every task's check is `npm run build` from `frontend-vue/` plus driving the running app in a browser.
- **Theme isolation is mandatory.** `/jury/review*` is the documented exception (`docs/STYLE_GUIDE.md:60`) with its own theme switch. Use only `--rq-*` tokens. Never import `ContestDashboard.css`; never copy its literals (`#fff`, `#c7d6e3`, `#20364d`, `#86a2b8`, `#22a05a`, `#d94b4b`, `#d99322`).
- **Do not alter** the review workflow, the iframe preview's structure or behaviour, the bulk banner, the bulk comment panel, or the review action bar (`STYLE_GUIDE.md:60`).
- **Both themes, every time.** The route has light and dark. Any colour change is verified in both.
- **Breakpoint is 768px** (`ReviewQueue.vue:854`). Desktop-only rules use `@media (min-width: 769px)`.
- **Servers:** backend `uvicorn main:app --reload --port 8000` from `backend/`; frontend `npm run dev` from `frontend-vue/`. Test contest code is `0ab09f`; the populated queue is `/0ab09f/jury/review-v2`.
- **`AGENTS.md` gets a Change Log row.** Repo convention, non-optional.

---

### Task 1: Stat cards and progress bar

**Files:**
- Modify: `frontend-vue/src/views/ReviewQueue.vue` (script: near `statusStats`, `:562-564`; template: inside `.rq-preview-panel`, immediately before `<header class="rq-article-header">`, `:1635`)
- Modify: `frontend-vue/src/styles/views/ReviewQueue.css` (append a new section)
- Modify: `docs/STYLE_GUIDE.md:62`

**Interfaces:**
- Consumes: `statusStats` — an existing computed returning `{ accepted, rejected, pending }` (`ReviewQueue.vue:561-565`).
- Produces: computeds `totalAssigned`, `judgedCount`, `judgedPercent` (all `number`), used by no later task but read by the template.

- [ ] **Step 1: Add the three computeds**

Insert directly after the `statusStats` computed (`ReviewQueue.vue:565`):

```js
// Card and progress-bar arithmetic. Everything here comes from statusStats,
// which is already fetched -- no extra request for the flow header.
const totalAssigned = computed(() =>
  statusStats.value.pending + statusStats.value.accepted + statusStats.value.rejected
);
const judgedCount = computed(() => statusStats.value.accepted + statusStats.value.rejected);
const judgedPercent = computed(() =>
  totalAssigned.value ? Math.round((judgedCount.value / totalAssigned.value) * 100) : 0
);
```

- [ ] **Step 2: Add the flow header markup**

Insert inside `<main class="rq-panel rq-preview-panel">`, immediately before `<header class="rq-article-header">`:

```html
<div class="rq-flow-stats">
  <div class="rq-stat-grid">
    <div class="rq-stat-card">
      <div class="rq-stat-number">{{ totalAssigned.toLocaleString() }}</div>
      <div class="rq-stat-label">Total</div>
    </div>
    <div class="rq-stat-card accent-amber">
      <div class="rq-stat-number">{{ statusStats.pending.toLocaleString() }}</div>
      <div class="rq-stat-label">Pending</div>
    </div>
    <div class="rq-stat-card accent-green">
      <div class="rq-stat-number">{{ statusStats.accepted.toLocaleString() }}</div>
      <div class="rq-stat-label">Accepted</div>
    </div>
    <div class="rq-stat-card accent-red">
      <div class="rq-stat-number">{{ statusStats.rejected.toLocaleString() }}</div>
      <div class="rq-stat-label">Rejected</div>
    </div>
  </div>
  <div
    class="rq-progress"
    role="progressbar"
    :aria-valuenow="judgedPercent"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-label="`${judgedCount} of ${totalAssigned} judged`"
  >
    <div class="rq-progress-track">
      <div class="rq-progress-fill" :style="{ width: judgedPercent + '%' }"></div>
    </div>
    <span class="rq-progress-text">
      {{ judgedCount.toLocaleString() }} of {{ totalAssigned.toLocaleString() }} judged · {{ judgedPercent }}%
    </span>
  </div>
</div>
```

- [ ] **Step 3: Add the CSS**

Append to `frontend-vue/src/styles/views/ReviewQueue.css`:

```css
/* Flow header: the four bordered tiles, restored at full main-pane width where
   there is room for real digits. Built on --rq-* tokens rather than reusing
   ContestDashboard's .stat-card, whose hard-coded light values would be
   unreadable under the review dark theme. */
.rq-flow-stats {
  padding: 12px 16px 14px;
  border-bottom: 1px solid var(--rq-border-light);
}
.rq-stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.rq-stat-card {
  position: relative;
  overflow: hidden;
  padding: 14px 16px;
  border: 1px solid var(--rq-border-light);
  border-radius: 10px;
  background: var(--rq-surface-alt);
}
.rq-stat-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: var(--rq-text-muted);
}
.rq-stat-card.accent-green::before { background: var(--rq-success); }
.rq-stat-card.accent-red::before { background: var(--rq-danger); }
.rq-stat-card.accent-amber::before { background: var(--rq-warning); }
.rq-stat-number {
  margin-bottom: 4px;
  color: var(--rq-text);
  font-size: 1.6rem;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.rq-stat-label {
  color: var(--rq-text-muted);
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.rq-progress { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
.rq-progress-track {
  flex: 1;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--rq-surface-hover);
}
.rq-progress-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--rq-accent);
  transition: width 240ms var(--ease-out);
}
.rq-progress-text {
  color: var(--rq-text-muted);
  font-size: .72rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
@media (max-width: 820px) {
  .rq-stat-grid { grid-template-columns: repeat(2, 1fr); }
}
```

- [ ] **Step 4: Correct the style guide**

`docs/STYLE_GUIDE.md:62` currently says the panel was rebuilt to "a compact header (titlebar, search, tabs, one stat line)". Replace the phrase `one stat line` with:

```
one compact stat line, with the four stat cards and progress bar moved to the
main-pane flow header (2026-09-09, second revision)
```

Leave the rest of that paragraph — the list of protected parts — untouched.

- [ ] **Step 5: Build**

Run from `frontend-vue/`: `npm run build`
Expected: completes with no errors. A Vue template syntax error fails here.

- [ ] **Step 6: Verify in the browser**

With both servers running, load `http://localhost:3000/0ab09f/jury/review-v2`.
Expected: four cards reading Total 2,664 / Pending 2,232 / Accepted 52 / Rejected 380, each with its accent bar; progress bar showing `432 of 2,664 judged · 16%`.
Toggle the theme (moon button in the panel titlebar). Expected: cards and bar legible in both. Narrow to 800px. Expected: cards reflow to 2×2.

- [ ] **Step 7: Commit**

```bash
git add frontend-vue/src/views/ReviewQueue.vue frontend-vue/src/styles/views/ReviewQueue.css docs/STYLE_GUIDE.md
git commit -m "Restore the four stat cards, in the review flow header"
```

---

### Task 2: Flow by default, with the mobile guard

**Files:**
- Modify: `frontend-vue/src/views/ReviewQueue.vue:43`
- Modify: `frontend-vue/src/styles/views/ReviewQueue.css:205-208`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `sidebarCollapsed` defaulting to `true`; Task 3 converts this state into an overlay.

- [ ] **Step 1: Flip the default**

`ReviewQueue.vue:43` becomes:

```js
// Flow-first: the article is the screen and the queue is a drawer you summon.
// Not persisted -- see the 2026-09-09 amendment in the design spec.
const sidebarCollapsed = ref(true);
```

- [ ] **Step 2: Scope the collapse rule to desktop**

This step is the whole point of the task; the default flip is unsafe without it. `ReviewQueue.css:205-208` currently reads:

```css
.rq-queue-panel.is-collapsed {
  width: 0;
  border: none;
}
```

Replace with:

```css
/* Desktop only. On mobile the panel IS the screen, governed by mobileTab, and
   an unscoped collapse rule would hand phone users a blank list. */
@media (min-width: 769px) {
  .rq-queue-panel.is-collapsed {
    width: 0;
    border: none;
  }
}
```

- [ ] **Step 3: Build**

Run from `frontend-vue/`: `npm run build`
Expected: completes with no errors.

- [ ] **Step 4: Verify desktop and mobile**

Load `/0ab09f/jury/review-v2` at desktop width. Expected: no sidebar; the hamburger button is visible in the article header; the article and the flow header from Task 1 fill the width.
Resize to 375px. Expected: the queue list is visible and usable — **not** blank. This is the regression this task exists to prevent.

- [ ] **Step 5: Commit**

```bash
git add frontend-vue/src/views/ReviewQueue.vue frontend-vue/src/styles/views/ReviewQueue.css
git commit -m "Default the review workspace to flow, guarding the mobile layout"
```

---

### Task 3: Overlay drawer and the `q` shortcut

**Files:**
- Modify: `frontend-vue/src/views/ReviewQueue.vue:1051-1058` (`SHORTCUT_ACTIONS`), `:1224` (key handler), template `.rq-queue-panel` at `:1412`
- Modify: `frontend-vue/src/styles/views/ReviewQueue.css` (the block from Task 2)

**Interfaces:**
- Consumes: `sidebarCollapsed` (Task 2), `SHORTCUT_ACTIONS` / `shortcuts` / `normalizeShortcutKey` (existing, `:1051`, `:1096`).
- Produces: a `queue` shortcut action id, resolved through the same dispatcher as `accept`/`reject`.

- [ ] **Step 1: Register the shortcut**

`/` and `?` are already bound to the help panel (`:1224`) and are in `RESERVED_SHORTCUT_KEYS` (`:1065`) — do not use them. Existing defaults are `a r s c u w`; `q` is free.

Add as the last entry of `SHORTCUT_ACTIONS` (`:1051-1058`):

```js
  { id: 'queue', label: 'Show or hide the queue drawer', default: 'q' },
```

Registering it here rather than special-casing it gives it rebinding, clash detection (`:1165`), persistence, the help panel, and the on-screen hints for free — the file already derives all of those from this array.

- [ ] **Step 2: Handle the action**

The dispatcher at `:1230-1234` resolves an action id then runs it. The existing guard `if (!currentArticle.value || isSubmitting.value) return;` sits above that resolution and would block the drawer when the queue is empty — which is exactly when someone needs it. So handle `queue` *before* that guard.

Insert immediately after the `showShortcutHelp` block ends (after `:1228`, the line `if (showShortcutHelp.value) return;`):

```js
  // Before the currentArticle guard below: the drawer has to open even when
  // there is no current article to show.
  if (normalizeShortcutKey(event.key) === shortcuts.value.queue) {
    sidebarCollapsed.value = !sidebarCollapsed.value;
    event.preventDefault();
    return;
  }
```

- [ ] **Step 3: Close on Escape**

In the same handler, immediately before the `/`/`?` block at `:1224`:

```js
  if (event.key === 'Escape' && !sidebarCollapsed.value) {
    sidebarCollapsed.value = true;
    event.preventDefault();
    return;
  }
```

- [ ] **Step 4: Close the drawer when an article is picked**

Find `selectArticle` (the handler bound to list-row clicks). Add as its last statement:

```js
  // Picking from the drawer returns you to flow without a second keystroke.
  if (window.innerWidth > 768) sidebarCollapsed.value = true;
```

- [ ] **Step 5: Add the backdrop**

Immediately before `<aside class="rq-queue-panel" ...>` (`:1412`):

```html
<div
  v-if="!sidebarCollapsed"
  class="rq-drawer-backdrop rq-desktop-only"
  @click="sidebarCollapsed = true"
></div>
```

- [ ] **Step 6: Make the open panel an overlay**

Replace the whole media block from Task 2 with:

```css
/* Desktop only. On mobile the panel IS the screen, governed by mobileTab, and
   an unscoped collapse rule would hand phone users a blank list. */
@media (min-width: 769px) {
  /* The panel overlays the article instead of sitting in the flex row, so
     opening the drawer never reflows the text being read. */
  .rq-queue-panel {
    position: absolute;
    z-index: 30;
    top: 0;
    bottom: 0;
    left: 0;
    box-shadow: 0 12px 40px rgb(0 0 0 / .28);
    transition: transform 200ms var(--ease-out);
  }
  .rq-queue-panel.is-collapsed {
    transform: translateX(-100%);
    box-shadow: none;
    pointer-events: none;
  }
  .rq-drawer-backdrop {
    position: absolute;
    z-index: 29;
    inset: 0;
    background: rgb(0 0 0 / .28);
  }
}
```

Then confirm the panel's positioning ancestor establishes a containing block: the element wrapping `.rq-queue-panel` and `.rq-preview-panel` must have `position: relative`. If it does not, add it to that wrapper's rule.

- [ ] **Step 7: Build**

Run from `frontend-vue/`: `npm run build`
Expected: completes with no errors.

- [ ] **Step 8: Verify**

At `/0ab09f/jury/review-v2`, desktop width:
- Press `q`. Expected: drawer slides in over the article; the article does **not** shift.
- Press `q` again, then `Esc` from an open drawer, then click the backdrop. Expected: closes each way.
- Open the drawer, click an article. Expected: article loads and the drawer closes.
- Press `?`. Expected: the help panel lists "Show or hide the queue drawer — Q".
- Open the shortcut settings (gear), rebind `queue` to `a`. Expected: rejected with the existing clash message naming Accept.
- At 375px: `q` does nothing harmful and the list remains the primary screen.

- [ ] **Step 9: Commit**

```bash
git add frontend-vue/src/views/ReviewQueue.vue frontend-vue/src/styles/views/ReviewQueue.css
git commit -m "Make the review queue a transient overlay drawer on Q"
```

---

### Task 4: Article reading measure

**Files:**
- Modify: `frontend-vue/src/views/ReviewQueue.vue:121` (`DARK_CSS`) and `:342` (`LIGHT_CSS`)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Edit both srcdoc stylesheets**

The article is an `<iframe :srcdoc="previewSrcdoc">` (`:1716`); parent CSS cannot reach into it. `previewSrcdoc` is assembled at `:385-390` and injects `LIGHT_CSS` or `DARK_CSS` by theme. Both sheets contain an `html, body` rule — `:121` in `DARK_CSS`, `:342` in `LIGHT_CSS`.

Add these three declarations to the `html, body` rule in **each** sheet, preserving every declaration already there:

```css
    max-width: 72ch;
    margin: 0 auto;
    line-height: 1.75;
```

Editing only one sheet leaves the other theme unchanged — a failure mode invisible unless both are checked.

- [ ] **Step 2: Build**

Run from `frontend-vue/`: `npm run build`
Expected: completes with no errors.

- [ ] **Step 3: Verify in both themes**

Load `/0ab09f/jury/review-v2` and select an article with body text (e.g. জুডো).
Expected: text is centred in a column roughly 72 characters wide, with looser leading, instead of spanning the full pane. Toggle the theme and confirm the same in the other. Confirm collapsible sections, the TOC, and tables still render — the preview's structure must be unchanged.

- [ ] **Step 4: Commit**

```bash
git add frontend-vue/src/views/ReviewQueue.vue
git commit -m "Give the article preview a reading measure in both themes"
```

---

### Task 5: Drawer row density

**Files:**
- Modify: `frontend-vue/src/views/ReviewQueue.vue:1559` (the submitter cell) and its script
- Modify: `frontend-vue/src/styles/views/ReviewQueue.css` (list-item padding)

**Interfaces:**
- Consumes: `articles` (existing ref), `activeTab` (existing computed).
- Produces: computed `isSingleSubmitter` (`boolean`).

- [ ] **Step 1: Add the computed**

Place it next to `statusStats` in the script:

```js
// With one submitter behind the whole batch, the column prints the same name on
// every row and buys nothing but width.
const isSingleSubmitter = computed(() =>
  new Set(articles.value.map(a => a.submitted_by)).size <= 1
);
```

- [ ] **Step 2: Guard the cell**

`:1559` currently renders the submitter unconditionally. The `others` tab shows reviewer names there instead and must keep them. Add to that element:

```html
v-if="activeTab.id === 'others' || !isSingleSubmitter"
```

- [ ] **Step 3: Tighten rows**

In `ReviewQueue.css`, find the `.rq-list-item` rule and reduce its vertical padding by 4px on each side. Do not change its horizontal padding, border, or hover treatment.

- [ ] **Step 4: Build**

Run from `frontend-vue/`: `npm run build`
Expected: completes with no errors.

- [ ] **Step 5: Verify**

Open the drawer at `/0ab09f/jury/review-v2`. Expected: rows show titles only — no repeated "MS Sakib" — and more rows fit per screen than before. Switch to the "Other judges" tab. Expected: reviewer names still shown.

- [ ] **Step 6: Commit**

```bash
git add frontend-vue/src/views/ReviewQueue.vue frontend-vue/src/styles/views/ReviewQueue.css
git commit -m "Drop the repeated submitter column and tighten queue rows"
```

---

### Task 6: Documentation and bundle

**Files:**
- Modify: `AGENTS.md` (Change Log table)
- Modify: `frontend-vue/dist/**` (build output, committed per repo workflow)

- [ ] **Step 1: Append the change log row**

Add one row to the `AGENTS.md` Change Log table dated `2026-09-09`, covering: flow-first default, four stat cards plus progress bar in the main-pane flow header, overlay drawer on `Q`, reading measure in both iframe stylesheets, submitter column dropped when single-submitter. Match the table's existing column shape.

Also update the sections describing the review workspace so they no longer describe the queue panel as the primary navigation.

- [ ] **Step 2: Rebuild the bundle**

Run from `frontend-vue/`: `npm run build`

`frontend-vue/dist` is gitignored inside `frontend-vue/.gitignore` but is committed at the repo root for Toolforge to serve (`STYLE_GUIDE.md` step 6, and the 2026-07-29 `AGENTS.md` entry). Stage it with an explicit force-add:

```bash
git add -f frontend-vue/dist
```

Content-hashed filenames change every build, so old asset files must be removed in the same commit — confirm `git status` shows deletions for the previous hashed bundles alongside the new ones.

- [ ] **Step 3: Final verification pass**

With both servers running, walk the whole feature once at `/0ab09f/jury/review-v2`:
1. Lands in flow, four cards and progress bar visible.
2. Judge one article. Expected: Pending decrements, Accepted or Rejected increments, progress bar advances.
3. `q` opens the drawer without shifting the article; picking a row closes it.
4. Both themes legible.
5. 375px: list still primary and usable.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git add -f frontend-vue/dist
git commit -m "Update AGENTS.md and rebuild the SPA bundle for review flow mode"
```

---

## Self-Review

**Spec coverage.** §1 flow default → Task 2. §2 stat cards → Task 1. §3 progress bar → Task 1. §4 drawer, `q` binding, mobile guard → Tasks 2 and 3. §5 reading measure → Task 4. §6 row density → Task 5. "Documentation to update" → Task 1 step 4 (STYLE_GUIDE) and Task 6 (AGENTS.md). No gaps.

**Placeholder scan.** Every code step carries literal code. Two steps are deliberately descriptive rather than literal, because each depends on a value that must be read from the file first: Task 3 step 6's containing-block check, and Task 5 step 3's padding reduction. Both name the exact rule and the exact change.

**Type consistency.** `statusStats` is read as `.pending` / `.accepted` / `.rejected` throughout, matching `:562-564`. `totalAssigned`, `judgedCount`, `judgedPercent` are defined in Task 1 and used only there. `isSingleSubmitter` is defined and used in Task 5. The shortcut id `queue` is registered in Task 3 step 1 and read as `shortcuts.value.queue` in step 2. `sidebarCollapsed` keeps its existing name throughout.

**Ordering risk.** Task 2 flips the default to collapsed while the panel is still `width: 0` rather than an overlay; Task 3 converts it. Between those commits the app is coherent — flow works, the hamburger reopens the panel, and reopening reflows the article as it does today. No task leaves the tree broken.
