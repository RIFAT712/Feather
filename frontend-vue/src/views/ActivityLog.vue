<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue';
import { useRoute } from 'vue-router';
import { CdxIcon } from '@wikimedia/codex';
import { cdxIconAlert } from '@wikimedia/codex-icons';
import { useContestStats, useContestLog, useContestSubmitters, useContestArticleSearch, SEARCH_MIN_LENGTH } from '../composables/useContestData';
import { formatDateTimeDayFirst } from '../utils/datetime';

// roles comes from ContestLayout (the shared parent for every contest route),
// which already fetches /my-role once -- this view used to independently
// re-fetch the exact same thing on every mount, one of several views doing so.
const props = defineProps({
  contest: { type: Object, default: null },
  roles: { type: Object, default: () => ({ is_jury: false, is_owner: false }) },
  // When set (embedded in the dashboard), renders a lightweight per-user
  // list instead of the full page's stats bar/toggle bar/timeline view:
  // group headers come from a cheap aggregate query (useContestSubmitters),
  // and each user's actual articles are fetched on demand only once their
  // group is expanded (see embeddedUserArticles below) -- never crawling the
  // whole contest just to show who submitted what, the way this used to.
  embedded: { type: Boolean, default: false },
});
const route = useRoute();
const viewMode = ref('per-user');
const openGroups = ref({});
const isAuthorized = computed(() => props.roles.is_jury || props.roles.is_owner);

// Embedded mode: just the per-submitter counts, not the full crawl.
const submittersQuery = useContestSubmitters(() => route.params.code, { enabled: computed(() => props.embedded) });
const submitters = computed(() => submittersQuery.data.value || []);

// One entry per expanded submitter in embedded mode: { items, isLoading,
// error, hasMore }. Plain local state (not another vue-query cache) since
// each entry is only ever read by the one row that fetched it -- nothing
// else in the app needs to share or invalidate a specific user's drill-down.
const embeddedUserArticles = ref({});

const loadEmbeddedUserArticles = async (username) => {
  const existing = embeddedUserArticles.value[username];
  if (existing && (existing.loaded || existing.isLoading)) return;
  embeddedUserArticles.value = { ...embeddedUserArticles.value, [username]: { items: [], isLoading: true, error: null, hasMore: false, loaded: false } };
  try {
    const res = await fetch(`/api/contests/${route.params.code}/log?page_size=200&submitted_by=${encodeURIComponent(username)}`);
    if (!res.ok) throw new Error('Failed to load articles for this user.');
    const data = await res.json();
    embeddedUserArticles.value = { ...embeddedUserArticles.value, [username]: { items: data.items, isLoading: false, error: null, hasMore: data.has_more, loaded: true } };
  } catch (e) {
    embeddedUserArticles.value = { ...embeddedUserArticles.value, [username]: { items: [], isLoading: false, error: e.message, hasMore: false, loaded: true } };
  }
};

const toggleEmbeddedUser = (username) => {
  openGroups.value[username] = !openGroups.value[username];
  if (openGroups.value[username]) loadEmbeddedUserArticles(username);
};

// Standalone /log page: full crawl + stats, shared with JuryStats via
// vue-query's cache. Disabled in embedded mode so the dashboard never
// triggers the full contest crawl this page needs.
const statsQuery = useContestStats(() => route.params.code, { enabled: computed(() => !props.embedded) });
const logQuery = useContestLog(() => route.params.code, true, { enabled: computed(() => !props.embedded) });

// Title search. Runs server-side (?q=) against the whole contest rather than
// filtering `log` -- `log` is only ever the pages crawled so far, so a
// client-side filter silently misses matches until the full crawl finishes,
// and on an 11k-article contest that's ~56 requests the user would be waiting
// on before search could even be correct.
const searchInput = ref('');
const debouncedSearch = ref('');
let searchDebounce;
watch(searchInput, (value) => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => { debouncedSearch.value = value.trim(); }, 250);
});
onBeforeUnmount(() => clearTimeout(searchDebounce));

const isSearching = computed(() => debouncedSearch.value.length >= SEARCH_MIN_LENGTH);
const searchQuery = useContestArticleSearch(() => route.params.code, debouncedSearch, true, {
  enabled: computed(() => !props.embedded && isSearching.value),
});
const searchResults = computed(() => searchQuery.data.value?.items || []);
const searchTotal = computed(() => searchQuery.data.value?.total ?? 0);
const searchHasMore = computed(() => !!searchQuery.data.value?.has_more);
const searchPending = computed(() => searchQuery.isFetching.value && !searchResults.value.length);
const searchError = computed(() => searchQuery.error.value?.message || null);
const clearSearch = () => { searchInput.value = ''; debouncedSearch.value = ''; };

const log = computed(() => logQuery.data.value?.items || []);
// Both the Per-User and Timeline views render from this, so search narrows
// whichever one the user is already looking at instead of forcing a mode switch.
const displayedLog = computed(() => (isSearching.value ? searchResults.value : log.value));
const isLoading = computed(() => (props.embedded ? submittersQuery.isLoading.value : logQuery.isLoading.value));
// True only once the initial page is already showing and a crawl (first
// load's catch-up pages, or a revisit's background revalidation) is still
// running behind it -- both cases vue-query folds into the same isFetching.
const isLoadingMore = computed(() => !props.embedded && logQuery.isFetching.value && !logQuery.isLoading.value);
const error = computed(() => (props.embedded
  ? submittersQuery.error.value?.message || null
  : logQuery.error.value?.message || statsQuery.error.value?.message || null));
// Server-computed totals, independent of how many rows are actually loaded --
// loading only a page at a time means log.value is never "everything", so
// these can't be derived by counting log.value client-side.
const statusCounts = computed(() => statsQuery.data.value?.status_counts || { total: 0, accepted: 0, rejected: 0, pending: 0, validation_failed: 0 });

// Timestamps arrive as naive UTC with no trailing 'Z'; `new Date(iso)` read
// them as local time and shifted every row by the viewer's UTC offset.
const fmt = (iso) => formatDateTimeDayFirst(iso);

const statusClass = (s) => ({
  accepted: 'badge-accepted',
  rejected: 'badge-rejected',
  pending:  'badge-pending',
  skipped:  'badge-skipped',
  validation_failed: 'badge-failed',
}[s] || '');

const statusLabel = (s) => ({
  accepted: 'Accepted',
  rejected: 'Rejected',
  pending:  'Pending',
  skipped:  'Skipped',
  validation_failed: 'Validation Error',
}[s] || s);

const groupedByUser = computed(() => {
  const map = {};
  displayedLog.value.forEach((entry, idx) => {
    const user = entry.submitted_by;
    if (!map[user]) map[user] = { user, entries: [], isOpen: false };
    map[user].entries.push(entry);
  });
  return Object.values(map);
});

const toggleUser = (group) => {
  openGroups.value[group.user] = !openGroups.value[group.user];
};

const reviewComments = (entry) => (entry.reviews || [])
  .filter(review => review.comment && review.comment.trim())
  .map(review => ({ reviewer: review.reviewer, comment: review.comment.trim() }));
</script>

<template>
  <div class="log-root" :class="{ 'log-root--embedded': embedded }">

    <div v-if="!isLoading && !isAuthorized" class="unauthorized-banner">
      <div class="unauthorized-content">
        <span class="icon">⛔</span>
        <h2>Access Denied</h2>
        <p>You are not authorized to view this page. This area is restricted to Contest Jury and Owners.</p>
      </div>
    </div>

        <div v-else-if="isLoading" class="state-center">
      <div class="spinner" :class="{ 'spinner-dark': embedded }" />
      <p>Loading activity log…</p>
    </div>

        <div v-else-if="error" class="state-center error-box">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:8px; display:block;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      <p>{{ error }}</p>
    </div>

    <div v-else-if="embedded" class="user-activity-panel">
      <div class="user-activity-header">
        <h3>Submissions by User</h3>
        <router-link :to="`/${route.params.code}/log`" class="view-full-log-link">View full activity log →</router-link>
      </div>
      <div v-if="submitters.length === 0" class="state-center">
        <p>No activity recorded yet.</p>
      </div>
      <div v-for="s in submitters" :key="s.username" class="embedded-user-group">
        <button
          type="button"
          class="embedded-user-header"
          @click="toggleEmbeddedUser(s.username)"
          :aria-expanded="!!openGroups[s.username]"
        >
          <span class="embedded-user-left">
            <span class="embedded-avatar-circle">{{ s.username.charAt(0).toUpperCase() }}</span>
            <router-link :to="`/${route.params.code}/user/${encodeURIComponent(s.username)}`" class="profile-link" @click.stop>{{ s.username }}</router-link>
            <span class="embedded-count-badge">{{ s.count.toLocaleString() }}</span>
          </span>
          <span class="embedded-chevron" :class="{ open: openGroups[s.username] }">›</span>
        </button>

        <div v-if="openGroups[s.username]" class="embedded-user-table-wrap">
          <div v-if="embeddedUserArticles[s.username]?.isLoading" class="embedded-load-more-note">
            <div class="spinner spinner-small spinner-dark" />
            <span>Loading {{ s.username }}'s articles…</span>
          </div>
          <p v-else-if="embeddedUserArticles[s.username]?.error" class="embedded-more-note">{{ embeddedUserArticles[s.username].error }}</p>
          <template v-else-if="embeddedUserArticles[s.username]">
            <table class="embedded-user-table">
              <thead>
                <tr>
                  <th>Article</th>
                  <th>Status</th>
                  <th>Reviewed by</th>
                  <th>Jury Comment</th>
                  <th>Submitted</th>
                  <th>Reviewed</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(entry, idx) in embeddedUserArticles[s.username].items"
                  :key="entry.article_id"
                  :class="idx % 2 === 0 ? 'row-even' : 'row-odd'"
                >
                  <td class="td-article">
                    <a :href="`https://bn.wiktionary.org/wiki/${encodeURIComponent(entry.title)}`" target="_blank" class="article-link">{{ entry.title }}</a>
                    <div v-if="entry.validation_error" class="error-subtext">
                      <CdxIcon :icon="cdxIconAlert" class="err-icon" /> {{ entry.validation_error }}
                    </div>
                  </td>
                  <td><span :class="['badge', statusClass(entry.status)]">{{ statusLabel(entry.status) }}</span></td>
                  <td class="td-reviewer">{{ entry.reviews && entry.reviews.length ? entry.reviews[0].reviewer : '—' }}</td>
                  <td class="td-comment">
                    <template v-if="reviewComments(entry).length">
                      <div v-for="(review, reviewIndex) in reviewComments(entry)" :key="`${review.reviewer}-${reviewIndex}`" class="comment-item">
                        {{ review.comment }}
                      </div>
                    </template>
                    <span v-else>—</span>
                  </td>
                  <td class="td-date">{{ fmt(entry.submitted_at) }}</td>
                  <td class="td-date">{{ entry.reviews && entry.reviews.length ? fmt(entry.reviews[0].reviewed_at) : '—' }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="embeddedUserArticles[s.username].hasMore" class="embedded-more-note">
              Showing the {{ embeddedUserArticles[s.username].items.length }} most recent —
              <router-link :to="`/${route.params.code}/user/${encodeURIComponent(s.username)}`">view all on their profile</router-link>.
            </p>
          </template>
        </div>
      </div>
    </div>

    <template v-else>
            <div class="stats-bar">
        <div class="stat-chip chip-total">
          <span class="chip-label">Total</span>
          <span class="chip-val">{{ statusCounts.total }}</span>
        </div>
        <div class="stat-chip chip-accepted">
          <span class="chip-label">Accepted</span>
          <span class="chip-val">{{ statusCounts.accepted }}</span>
        </div>
        <div class="stat-chip chip-rejected">
          <span class="chip-label">Rejected</span>
          <span class="chip-val">{{ statusCounts.rejected }}</span>
        </div>
        <div class="stat-chip chip-pending">
          <span class="chip-label">Pending</span>
          <span class="chip-val">{{ statusCounts.pending }}</span>
        </div>
        <div class="stat-chip chip-failed">
          <span class="chip-label">Errors</span>
          <span class="chip-val">{{ statusCounts.validation_failed }}</span>
        </div>
      </div>
      <div class="log-search-bar">
        <span class="log-search-icon" aria-hidden="true">🔍</span>
        <input
          v-model="searchInput"
          type="search"
          class="log-search-input"
          placeholder="Search article titles across the whole contest…"
          aria-label="Search article titles"
          @keydown.esc="clearSearch"
        />
        <button
          v-if="searchInput"
          type="button"
          class="log-search-clear"
          aria-label="Clear search"
          @click="clearSearch"
        >×</button>
      </div>

      <p v-if="isSearching" class="loaded-so-far-note">
        <template v-if="searchPending">Searching…</template>
        <template v-else-if="searchError">{{ searchError }}</template>
        <template v-else-if="!searchTotal">No articles match “{{ debouncedSearch }}”.</template>
        <template v-else>
          {{ searchTotal.toLocaleString() }} article{{ searchTotal === 1 ? '' : 's' }} match “{{ debouncedSearch }}”<template v-if="searchHasMore">, showing the {{ searchResults.length }} most recent — narrow the search to see fewer</template>.
        </template>
        <button type="button" class="log-search-reset" @click="clearSearch">Clear</button>
      </p>
      <p v-else-if="searchInput.trim()" class="loaded-so-far-note">Type at least {{ SEARCH_MIN_LENGTH }} characters to search.</p>
      <p v-else class="loaded-so-far-note">Showing {{ log.length }} of {{ statusCounts.total }} articles, newest first.</p>

            <div class="toggle-bar">
        <div class="segmented-control">
          <button
            class="seg-btn"
            :class="{ active: viewMode === 'per-user' }"
            @click="viewMode = 'per-user'"
          >
            Per-User Table
          </button>
          <button
            class="seg-btn"
            :class="{ active: viewMode === 'timeline' }"
            @click="viewMode = 'timeline'"
          >
            Timeline Log
          </button>
        </div>
      </div>

            <div v-if="viewMode === 'per-user'" class="view-section">
        <div
          v-for="group in groupedByUser"
          :key="group.user"
          class="user-card"
        >
                    <button
            class="user-header"
            @click="toggleUser(group)"
            :aria-expanded="!!openGroups[group.user]"
          >
            <div class="user-header-left">
              <div class="avatar-circle">{{ group.user.charAt(0).toUpperCase() }}</div>
              <router-link :to="`/${route.params.code}/user/${encodeURIComponent(group.user)}`" class="user-name profile-link" @click.stop>{{ group.user }}</router-link>
              <span class="count-badge">{{ group.entries.length }}</span>
            </div>
            <span class="chevron" :class="{ open: openGroups[group.user] }">›</span>
          </button>

                    <div v-if="openGroups[group.user]" class="user-table-wrap">
            <table class="user-table">
              <thead>
                <tr>
                  <th>Article</th>
                  <th>Status</th>
                  <th>Reviewed by</th>
                  <th>Jury Comment</th>
                  <th>Submitted</th>
                  <th>Reviewed</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(entry, idx) in group.entries"
                  :key="entry.id || idx"
                  :class="idx % 2 === 0 ? 'row-even' : 'row-odd'"
                >
                  <td class="td-article">
                    <a :href="`https://bn.wiktionary.org/wiki/${encodeURIComponent(entry.title)}`" target="_blank" class="article-link">{{ entry.title }}</a>
                    <div v-if="entry.validation_error" class="error-subtext">
                      <CdxIcon :icon="cdxIconAlert" class="err-icon" /> {{ entry.validation_error }}
                    </div>
                  </td>
                  <td><span :class="['badge', statusClass(entry.status)]">{{ statusLabel(entry.status) }}</span></td>
                  <td class="td-reviewer">{{ entry.reviews && entry.reviews.length ? entry.reviews[0].reviewer : '—' }}</td>
                  <td class="td-comment">
                    <template v-if="reviewComments(entry).length">
                      <div v-for="(review, reviewIndex) in reviewComments(entry)" :key="`${review.reviewer}-${reviewIndex}`" class="comment-item">
                        {{ review.comment }}
                      </div>
                    </template>
                    <span v-else>—</span>
                  </td>
                  <td class="td-date">{{ fmt(entry.submitted_at) }}</td>
                  <td class="td-date">{{ entry.reviews && entry.reviews.length ? fmt(entry.reviews[0].reviewed_at) : '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

            <div v-if="viewMode === 'timeline'" class="view-section">
        <div
          v-for="(entry, idx) in displayedLog"
          :key="entry.id || idx"
          class="timeline-card"
          :class="`tl-${entry.status}`"
        >
          <div class="tl-header">
            <a :href="`https://bn.wiktionary.org/wiki/${encodeURIComponent(entry.title)}`" target="_blank" class="tl-title article-link">{{ entry.title }}</a>
            <span :class="['badge', statusClass(entry.status)]">{{ statusLabel(entry.status) }}</span>
          </div>
          <div class="tl-meta">
            <span class="tl-meta-item">
              <span class="tl-label">Submitted by</span>
              <strong><router-link :to="`/${route.params.code}/user/${encodeURIComponent(entry.submitted_by)}`" class="profile-link">{{ entry.submitted_by }}</router-link></strong>
            </span>
            <span class="tl-sep">·</span>
            <span class="tl-meta-item">
              <span class="tl-label">at</span>
              {{ fmt(entry.submitted_at) }}
            </span>
          </div>

                    <div v-if="entry.validation_error" class="tl-error-banner">
            <CdxIcon :icon="cdxIconAlert" class="err-icon" />
            <span class="err-msg"><strong>Error:</strong> {{ entry.validation_error }}</span>
          </div>

                    <div v-if="entry.reviews && entry.reviews.length" class="mini-timeline">
            <div v-for="rev in entry.reviews" :key="rev.reviewer" class="mini-tl-item">
              <div class="mini-tl-dot" :class="`dot-${rev.decision}`" />
              <div class="mini-tl-line" />
              <div class="mini-tl-event">
                <span class="tl-label">Reviewed by</span>
                <strong><router-link :to="`/${route.params.code}/user/${encodeURIComponent(rev.reviewer)}`" class="profile-link">{{ rev.reviewer }}</router-link></strong>
                <span class="tl-sep">·</span>
                {{ fmt(rev.reviewed_at) }}
              </div>
            </div>
          </div>
        </div>

        <div v-if="log.length === 0" class="state-center">
          <p>No activity recorded yet.</p>
        </div>
      </div>

            <div v-if="isLoadingMore" class="load-more-log">
        <div class="spinner spinner-small" />
        <span>Refreshing in the background…</span>
      </div>
    </template>
  </div>
</template>

<style scoped src="../styles/views/ActivityLog.css"></style>
