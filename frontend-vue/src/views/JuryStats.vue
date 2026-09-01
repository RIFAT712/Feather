<script setup>
import { ref, computed, inject, onMounted, watch, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { CdxIcon } from '@wikimedia/codex';
import { cdxIconArticleCheck, cdxIconTrash } from '@wikimedia/codex-icons';
import { useQueryClient } from '@tanstack/vue-query';
import { useContestStats, useContestErrorLog, useContestSubmitters, removeArticlesFromLogCache, useContestArticleSearch, SEARCH_MIN_LENGTH } from '../composables/useContestData';
import { fetchAllContestLogPages } from '../utils/contestLog';
import { Doughnut, Bar } from 'vue-chartjs';
import GlobalLoader from '../components/ui/GlobalLoader.vue';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
} from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title);

// roles comes from ContestLayout (the shared parent for every contest route),
// which already fetches /my-role once -- this view used to independently
// re-fetch the exact same thing on every mount, one of several views doing so.
const props = defineProps({
  roles: { type: Object, default: () => ({ is_jury: false, is_owner: false }) },
});
const route = useRoute();
const router = useRouter();
const user = inject('user');
const queryClient = useQueryClient();
const juryProgress = ref([]);
const isAuthorized = computed(() => props.roles.is_jury || props.roles.is_owner);
const activeTab = ref('overview');
const removingArticleId = ref(null);
const removalError = ref('');
const selectedErrorIds = ref([]);
const selectedSubmissionIds = ref([]);
const expandedSubmitters = ref({});
const visibleGroupCounts = ref({});
const isBulkRemoving = ref(false);

// Overview KPIs/charts come from grouped SQL counts, not the full article list —
// the "All submitted"/"Errored" tabs are the only place that need per-article
// detail. Shared across Dashboard/ActivityLog/JuryStats via vue-query's
// cache, so navigating between them doesn't re-fetch what another view just
// loaded seconds ago.
const statsQuery = useContestStats(() => route.params.code, { enabled: isAuthorized });
const stats = computed(() => statsQuery.data.value || { status_counts: {}, jury_stats: [] });
const isLoading = computed(() => isAuthorized.value && statsQuery.isLoading.value);
const fetchStats = () => statsQuery.refetch();

// "All submitted" tab, submitter-first. This used to crawl every article in
// the contest (~150 pages at 30k articles) purely so it could group them by
// submitter in JavaScript -- reading each article to find out who submitted
// it. The grouping is the whole point of the tab, so it's done the other way
// round now: one cheap GROUP BY gives the user rows and their counts, and an
// individual user's articles are fetched, server-filtered, only when their
// group is actually opened. Same panel, one small query instead of the whole
// contest.
const submittersQuery = useContestSubmitters(() => route.params.code, {
  enabled: computed(() => isAuthorized.value && activeTab.value === 'submissions'),
});
const submitters = computed(() => submittersQuery.data.value || []);
const isLoadingArticles = computed(() => submittersQuery.isLoading.value);
const fetchArticles = async () => {
  // Counts changed, so anything already pulled per user is suspect too --
  // dropped, then re-pulled for whichever groups are actually open, so a
  // manual Refresh doesn't leave an expanded group sitting over an empty body.
  const openUsers = Object.entries(expandedSubmitters.value)
    .filter(([, isOpen]) => isOpen)
    .map(([username]) => username);
  submitterArticles.value = {};
  const result = await submittersQuery.refetch();
  if (!isSearchingSubmissions.value) {
    await Promise.all(openUsers.map(username => loadSubmitterArticles(username)));
  }
  return result;
};

// One entry per submitter whose articles have been pulled:
// { items, isLoading, error, loaded }. Plain local state rather than more
// vue-query entries -- useQuery can't be called per row in a v-for, and this
// tab mutates the lists in place on delete.
const submitterArticles = ref({});

const setSubmitterEntry = (username, patch) => {
  const previous = submitterArticles.value[username] || { items: [], isLoading: false, error: null, loaded: false };
  submitterArticles.value = { ...submitterArticles.value, [username]: { ...previous, ...patch } };
};

// Crawls one submitter's articles to completion. Bounded by that user's own
// submission count, not the contest's -- server-side ?submitted_by= hits the
// indexed submitter_id column directly.
const loadSubmitterArticles = async (username, { force = false } = {}) => {
  const existing = submitterArticles.value[username];
  if (existing?.isLoading) return existing.items;
  if (existing?.loaded && !force) return existing.items;
  setSubmitterEntry(username, { isLoading: true, error: null });
  try {
    const items = await fetchAllContestLogPages(route.params.code, {
      includeReviews: false,
      submittedBy: username,
      pageSize: 500,
    });
    setSubmitterEntry(username, { items, isLoading: false, error: null, loaded: true });
    return items;
  } catch (err) {
    setSubmitterEntry(username, { isLoading: false, error: err.message || 'Could not load this user’s articles.', loaded: false });
    return [];
  }
};

// Errored submissions are typically a handful out of thousands, and could be
// anywhere in the id order -- filtering server-side means this tab never has
// to wait on (or trigger) the full "All submitted" crawl to find them.
// Fetched lazily, only once the Errored tab is opened.
const errorArticlesQuery = useContestErrorLog(() => route.params.code, {
  enabled: computed(() => isAuthorized.value && activeTab.value === 'errors'),
});
const errorArticles = computed(() => errorArticlesQuery.data.value || []);
const isLoadingErrorArticles = computed(() => errorArticlesQuery.isLoading.value);
const fetchErrorArticles = () => errorArticlesQuery.refetch();

const loadJuryProgress = async () => {
  try {
    const progressRes = await fetch(`/api/jury-panel/contests/${route.params.code}/progress`);
    if (progressRes.ok) juryProgress.value = await progressRes.json();
  } catch (err) {
    console.error(err);
  }
};

onMounted(() => {
  if (!isAuthorized.value) return;
  loadJuryProgress();
});

// Re-level the queues. Needed because a jury member cannot judge their own
// submissions (nor can anyone restricted against them), so a large batch from
// one of them leaves the others carrying it and that member permanently light.
const isRedistributing = ref(false);
const redistributeMessage = ref('');
const redistributeFailed = ref(false);
const redistributeQueues = async () => {
  if (isRedistributing.value) return;
  isRedistributing.value = true;
  redistributeMessage.value = '';
  redistributeFailed.value = false;
  try {
    const res = await fetch(`/api/admin/contests/${route.params.code}/redistribute`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Redistribution failed.');
    redistributeMessage.value = data.moved
      ? `Reassigned ${data.moved.toLocaleString()} article${data.moved === 1 ? '' : 's'}.`
      : 'Queues are already as balanced as the restrictions allow.';
    await loadJuryProgress();
  } catch (err) {
    redistributeFailed.value = true;
    redistributeMessage.value = err.message || 'Redistribution failed.';
  } finally {
    isRedistributing.value = false;
  }
};

const overallStats = computed(() => {
  const counts = stats.value.status_counts || {};
  const total = counts.total || 0;
  const accepted = counts.accepted || 0;
  const rejected = counts.rejected || 0;
  // "Pending" here means everything not yet decided, including validation failures.
  return { total, accepted, rejected, pending: total - accepted - rejected };
});

const juryStats = computed(() => {
  const rows = stats.value.jury_stats || [];
  if (props.roles.is_owner) return rows;
  const mine = user?.value?.wiki_username;
  return rows.filter(row => row.name === mine);
});

const juryProgressRows = computed(() => juryProgress.value.map(row => ({
  name: row.username,
  assigned: row.assigned,
  judged: row.judged,
  remaining: row.remaining,
  accepted: row.accepted,
  rejected: row.rejected,
  progress: row.progress_percent,
})));

const statusLabel = (status) => ({
  accepted: 'Accepted',
  rejected: 'Rejected',
  pending: 'Pending',
  validation_failed: 'Validation failed',
}[status] || status);

const erroredArticles = computed(() => errorArticles.value);
const displayedSubmissions = computed(() => erroredArticles.value);
const allErrorsSelected = computed(() => erroredArticles.value.length > 0 && erroredArticles.value.every(article => selectedErrorIds.value.includes(article.article_id)));
// Title search over the whole contest, server-side (?q=). There is no
// client-side list to filter here at all any more: the tab only holds the
// submitters whose groups have been opened, so a JS filter would report "no
// matches" for every article in every group still collapsed.
const submissionSearch = ref('');
const debouncedSubmissionSearch = ref('');
let submissionSearchDebounce;
watch(submissionSearch, (value) => {
  clearTimeout(submissionSearchDebounce);
  submissionSearchDebounce = setTimeout(() => { debouncedSubmissionSearch.value = value.trim(); }, 250);
});
onBeforeUnmount(() => clearTimeout(submissionSearchDebounce));

const isSearchingSubmissions = computed(() => debouncedSubmissionSearch.value.length >= SEARCH_MIN_LENGTH);
const submissionSearchQuery = useContestArticleSearch(() => route.params.code, debouncedSubmissionSearch, false, {
  enabled: computed(() => isAuthorized.value && activeTab.value === 'submissions' && isSearchingSubmissions.value),
});
const submissionSearchResults = computed(() => submissionSearchQuery.data.value?.items || []);
const submissionSearchTotal = computed(() => submissionSearchQuery.data.value?.total ?? 0);
const submissionSearchHasMore = computed(() => !!submissionSearchQuery.data.value?.has_more);
const submissionSearchPending = computed(() => submissionSearchQuery.isFetching.value && !submissionSearchResults.value.length);
const submissionSearchError = computed(() => submissionSearchQuery.error.value?.message || null);
const clearSubmissionSearch = () => { submissionSearch.value = ''; debouncedSubmissionSearch.value = ''; };
// Two shapes feed the same group list. A search is already answered
// server-side as a flat result set, so those still get grouped in JS (it's
// one bounded page, not the contest). Everything else is submitter-first:
// rows come from the aggregate, and `articles` fills in per group on expand.
// `count` is authoritative either way -- it's what the header shows, so a
// collapsed group states its real size without having fetched anything.
const groupedSubmissions = computed(() => {
  if (isSearchingSubmissions.value) {
    const groups = new Map();
    for (const article of submissionSearchResults.value) {
      const username = article.submitted_by || 'Unknown user';
      if (!groups.has(username)) groups.set(username, []);
      groups.get(username).push(article);
    }
    return Array.from(groups, ([username, groupArticles]) => ({
      username, articles: groupArticles, count: groupArticles.length, loaded: true, isLoading: false, error: null,
    }));
  }
  return submitters.value.map(({ username, count }) => {
    const entry = submitterArticles.value[username];
    return {
      username,
      count,
      articles: entry?.items || [],
      loaded: !!entry?.loaded,
      isLoading: !!entry?.isLoading,
      error: entry?.error || null,
    };
  });
});

// Search results carry their own articles, so an expanded group during a
// search never fetched anything. Dropping back to the full list would leave
// those groups open over an empty body -- pull them for real instead.
watch(isSearchingSubmissions, (searching) => {
  if (searching) return;
  for (const [username, isOpen] of Object.entries(expandedSubmitters.value)) {
    if (isOpen) loadSubmitterArticles(username);
  }
});

const totalSubmissionCount = computed(() => (isSearchingSubmissions.value
  ? submissionSearchResults.value.length
  : submitters.value.reduce((sum, entry) => sum + entry.count, 0)));

// Selection can only ever cover articles actually in hand. In submitter-first
// mode that's the opened groups -- "Select all" no longer means "all 30k
// articles in the contest", because they are deliberately not loaded.
const loadedSubmissionIds = computed(() => groupedSubmissions.value.flatMap(group => group.articles.map(article => article.article_id)));
const allSubmissionsSelected = computed(() => loadedSubmissionIds.value.length > 0 && loadedSubmissionIds.value.every(id => selectedSubmissionIds.value.includes(id)));
const someSubmissionsSelected = computed(() => selectedSubmissionIds.value.length > 0 && !allSubmissionsSelected.value);
const hasUnloadedGroups = computed(() => !isSearchingSubmissions.value && groupedSubmissions.value.some(group => !group.loaded));

const toggleErrorSelection = (articleId) => {
  selectedErrorIds.value = selectedErrorIds.value.includes(articleId)
    ? selectedErrorIds.value.filter(id => id !== articleId)
    : [...selectedErrorIds.value, articleId];
};

const toggleAllErrors = () => {
  selectedErrorIds.value = allErrorsSelected.value ? [] : erroredArticles.value.map(article => article.article_id);
};
const toggleSubmissionSelection = (articleId) => {
  selectedSubmissionIds.value = selectedSubmissionIds.value.includes(articleId)
    ? selectedSubmissionIds.value.filter(id => id !== articleId)
    : [...selectedSubmissionIds.value, articleId];
};
const toggleAllSubmissions = () => {
  selectedSubmissionIds.value = selectedSubmissionIds.value.length ? [] : [...loadedSubmissionIds.value];
};
const groupSelectedCount = (group) => group.articles.filter(article => selectedSubmissionIds.value.includes(article.article_id)).length;
const groupFullySelected = (group) => group.loaded && group.articles.length > 0 && groupSelectedCount(group) === group.articles.length;
const groupPartiallySelected = (group) => groupSelectedCount(group) > 0 && !groupFullySelected(group);

// Ticking a collapsed group has to fetch it first -- otherwise "select all by
// this user" would select the zero articles currently in hand and then arm a
// Delete button next to a header reading a count of 40.
const toggleGroupSelection = async (group) => {
  if (groupSelectedCount(group) > 0) {
    const groupIds = new Set(group.articles.map(article => article.article_id));
    selectedSubmissionIds.value = selectedSubmissionIds.value.filter(id => !groupIds.has(id));
    return;
  }
  const items = group.loaded ? group.articles : await loadSubmitterArticles(group.username);
  selectedSubmissionIds.value = [...new Set([...selectedSubmissionIds.value, ...items.map(article => article.article_id)])];
};

const toggleSubmitter = (username) => {
  const opening = !expandedSubmitters.value[username];
  expandedSubmitters.value = { ...expandedSubmitters.value, [username]: opening };
  if (visibleGroupCounts.value[username] === undefined) {
    visibleGroupCounts.value = { ...visibleGroupCounts.value, [username]: 100 };
  }
  if (opening && !isSearchingSubmissions.value) loadSubmitterArticles(username);
};
const visibleGroupArticles = (group) => group.articles.slice(0, visibleGroupCounts.value[group.username] || 100);
const groupHasMore = (group) => visibleGroupArticles(group).length < group.articles.length;
const loadMoreGroupArticles = (group) => {
  visibleGroupCounts.value = {
    ...visibleGroupCounts.value,
    [group.username]: Math.min((visibleGroupCounts.value[group.username] || 100) + 100, group.articles.length),
  };
};

// Refresh whichever detail list the current tab actually shows, rather than
// always re-crawling the full "All submitted" list (slow) even when the
// user is looking at the small, separately-fetched Errored tab.
const refreshCurrentTabArticles = () => {
  const refreshes = [fetchStats()];
  // Submitter counts only -- the per-user lists on screen were already patched
  // in place, and re-pulling them would collapse the group the user is in.
  if (activeTab.value === 'errors') refreshes.push(fetchErrorArticles());
  else refreshes.push(submittersQuery.refetch());
  return Promise.all(refreshes);
};

// Deleted ids have to leave the per-submitter lists too -- those are local
// state, so removeArticlesFromLogCache (which only knows about vue-query
// caches) can't reach them.
const dropFromSubmitterArticles = (articleIds) => {
  if (!articleIds.length) return;
  const idSet = new Set(articleIds);
  const next = {};
  for (const [username, entry] of Object.entries(submitterArticles.value)) {
    next[username] = { ...entry, items: entry.items.filter(item => !idSet.has(item.article_id)) };
  }
  submitterArticles.value = next;
};

const removeArticle = async (article) => {
  if (!confirm(`Remove "${article.title}" from this contest?`)) return;

  removingArticleId.value = article.article_id;
  removalError.value = '';
  try {
    const res = await fetch(`/api/articles/${article.article_id}`, { method: 'DELETE' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Could not remove the article.');
    selectedErrorIds.value = selectedErrorIds.value.filter(id => id !== article.article_id);
    selectedSubmissionIds.value = selectedSubmissionIds.value.filter(id => id !== article.article_id);
    removeArticlesFromLogCache(queryClient, route.params.code, [article.article_id]);
    dropFromSubmitterArticles([article.article_id]);
    await refreshCurrentTabArticles();
  } catch (err) {
    removalError.value = err.message || 'Could not remove the article.';
  } finally {
    removingArticleId.value = null;
  }
};
// The API rejects batches over 500 ids, and one huge transaction is exactly
// what risked timing out partway through a delete. Send the selection in
// chunks so each request stays small, a failure only costs its own chunk,
// and the button can report real progress.
const BULK_DELETE_CHUNK = 200;
const bulkProgress = ref(null);

// This used to guard against a subtler hazard: the tab streamed the whole
// contest in progressively, so a group's list kept growing after it rendered
// and select-all could scoop up thousands more than the header showed. Groups
// now load atomically per user, so the only moment selection is meaningless
// is before the submitter rows themselves exist.
const selectionLocked = computed(() => activeTab.value === 'submissions' && !isSearchingSubmissions.value && isLoadingArticles.value);

const bulkRemoveLabel = (count) => {
  if (!isBulkRemoving.value) return `Delete selected${count ? ` (${count})` : ''}`;
  const progress = bulkProgress.value;
  return progress && progress.total ? `Removing ${progress.done}/${progress.total}…` : 'Removing…';
};

const bulkDeleteIds = async (ids) => {
  const succeeded = [];
  const failed = [];
  bulkProgress.value = { done: 0, total: ids.length };
  try {
    for (let start = 0; start < ids.length; start += BULK_DELETE_CHUNK) {
      const chunk = ids.slice(start, start + BULK_DELETE_CHUNK);
      try {
        const res = await fetch('/api/articles/bulk-delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ article_ids: chunk }),
        });
        const result = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(result.detail || `Request failed (${res.status})`);
        succeeded.push(...(result.succeeded || []));
        failed.push(...(result.failed || []));
      } catch (err) {
        // A dead chunk must not discard the chunks that already committed --
        // record it and keep going so the caller can say exactly what survived.
        failed.push(...chunk.map(id => ({ article_id: id, detail: err.message || 'Request failed' })));
      }
      bulkProgress.value = { done: Math.min(start + chunk.length, ids.length), total: ids.length };
    }
  } finally {
    bulkProgress.value = null;
  }
  return { succeeded, failed };
};

const removeSelectedSubmissions = async (group = null) => {
  if (isBulkRemoving.value) return;
  const ids = group
    ? group.articles.map(article => article.article_id).filter(id => selectedSubmissionIds.value.includes(id))
    : [...selectedSubmissionIds.value];
  if (!ids.length) return;
  if (!confirm(`Remove ${ids.length} submitted article(s) from this contest?`)) return;
  isBulkRemoving.value = true;
  removalError.value = '';
  try {
    const { succeeded, failed } = await bulkDeleteIds(ids);
    const failedIds = failed.map(item => item.article_id);
    selectedSubmissionIds.value = selectedSubmissionIds.value.filter(id => failedIds.includes(id));
    removeArticlesFromLogCache(queryClient, route.params.code, succeeded);
    dropFromSubmitterArticles(succeeded);
    // Refresh the submitter counts before surfacing any partial failure, so
    // the list on screen always reflects what actually got removed.
    await Promise.all([submittersQuery.refetch(), fetchStats()]);
    if (failed.length) {
      removalError.value = `Removed ${succeeded.length} of ${ids.length}. ${failed.length} could not be removed — ${failed[0].detail}`;
    }
  } catch (err) {
    removalError.value = err.message || 'Could not remove selected articles.';
  } finally {
    isBulkRemoving.value = false;
  }
};
// Only ever called from the Errored tab, so it always refreshes that
// separately-fetched list rather than the full submissions crawl.
const removeSelectedErrors = async () => {
  if (!selectedErrorIds.value.length || isBulkRemoving.value) return;
  const ids = [...selectedErrorIds.value];
  if (!confirm(`Remove ${ids.length} errored article(s) from this contest?`)) return;
  isBulkRemoving.value = true;
  removalError.value = '';
  try {
    const { succeeded, failed } = await bulkDeleteIds(ids);
    selectedErrorIds.value = failed.map(item => item.article_id);
    // Errored articles are also part of the shared "all submitted" cache if
    // that tab was ever opened -- prune them there too, not just their own
    // separately-fetched list.
    removeArticlesFromLogCache(queryClient, route.params.code, succeeded);
    await Promise.all([fetchErrorArticles(), fetchStats()]);
    if (failed.length) {
      removalError.value = `Removed ${succeeded.length} of ${ids.length}. ${failed.length} could not be removed — ${failed[0].detail}`;
    }
  } catch (err) {
    removalError.value = err.message || 'Could not remove selected articles.';
  } finally {
    isBulkRemoving.value = false;
  }
};
const doughnutData = computed(() => ({
  labels: ['Accepted', 'Rejected', 'Pending'],
  datasets: [{
    data: [overallStats.value.accepted, overallStats.value.rejected, overallStats.value.pending],
    backgroundColor: ['#355b80', '#6f95b2', '#a9c3d5'],
    hoverBackgroundColor: ['#274866', '#527d9f', '#8eafc5'],
    borderWidth: 3,
    borderColor: '#ffffff',
    hoverOffset: 4,
  }],
}));

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '72%',
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      callbacks: {
        label: (ctx) => ` ${ctx.label}: ${ctx.parsed} articles`,
      },
    },
  },
  animation: { animateRotate: true, duration: 900 },
};
const barData = computed(() => ({
  labels: juryStats.value.map(j => j.name),
  datasets: [
    {
      label: 'Accepted',
      data: juryStats.value.map(j => j.accepted),
      backgroundColor: '#4f7fa3',
      borderRadius: 5,
    },
    {
      label: 'Rejected',
      data: juryStats.value.map(j => j.rejected),
      backgroundColor: '#a9c3d5',
      borderRadius: 5,
    },
  ],
}));

const barOptions = {
  indexAxis: 'y',
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      callbacks: {
        label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.x}`,
      },
    },
  },
  scales: {
    x: {
      stacked: true,
      grid: { color: '#e4edf3', drawBorder: false },
      ticks: { font: { size: 11 }, color: '#6c899c', stepSize: 1 },
      border: { display: false },
    },
    y: {
      stacked: true,
      grid: { display: false },
      ticks: { font: { size: 11, weight: '600' }, color: '#47637c' },
      border: { display: false },
    },
  },
  animation: { duration: 700 },
};

const handleExportCSV = () => {
  const headers = ['Jury Member', 'Articles Judged', 'Accepted Articles', 'Rejected Articles', 'Acceptance Rate'];
  const rows = juryStats.value.map(j => [
    j.name, j.total, j.accepted, j.rejected, j.total ? Math.round((j.accepted/j.total)*100) + '%' : '0%'
  ]);
  const csvContent = [headers, ...rows].map(e => e.join(',')).join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `jury_stats_${route.params.code}.csv`;
  a.click();
};

const handleExportJSON = () => {
  const blob = new Blob([JSON.stringify(juryStats.value, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `jury_stats_${route.params.code}.json`;
  a.click();
};

const handleExportWikitable = () => {
  let wt = '{| class="wikitable sortable"\\n! Jury Member !! Articles Judged !! Accepted Articles !! Rejected Articles !! Acceptance Rate\\n';
  juryStats.value.forEach(j => {
    wt += `|-\\n| ${j.name} || ${j.total} || ${j.accepted} || ${j.rejected} || ${j.total ? Math.round((j.accepted/j.total)*100) : 0}%\\n`;
  });
  wt += '|}';
  const blob = new Blob([wt], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `jury_stats_${route.params.code}.txt`;
  a.click();
};
</script>

<template>
  <div class="stats-page">
    <div v-if="!isLoading && !isAuthorized" class="unauthorized-banner">
      <div class="unauthorized-content">
        <span class="icon">⛔</span>
        <h2>Access Denied</h2>
        <p>You are not authorized to view this page. This area is restricted to Contest Jury and Owners.</p>
      </div>
    </div>

    <GlobalLoader v-else-if="isLoading" label="Crunching the numbers…" />

    <div v-else class="stats-layout">
      <nav class="jury-tabs" aria-label="Jury sections">
        <button
          type="button"
          class="jury-tab"
          :class="{ active: activeTab === 'overview' }"
          @click="activeTab = 'overview'"
        >Overview</button>
        <button
          type="button"
          class="jury-tab"
          :class="{ active: activeTab === 'submissions' }"
          @click="activeTab = 'submissions'"
        >All submitted <span>{{ (stats.status_counts.total || 0).toLocaleString() }}</span></button>
        <button
          type="button"
          class="jury-tab jury-tab-errors"
          :class="{ active: activeTab === 'errors' }"
          @click="activeTab = 'errors'"
        >Errored <span>{{ (stats.status_counts.validation_failed || 0).toLocaleString() }}</span></button>
      </nav>

      <template v-if="activeTab === 'overview'">
            <div class="judge-hero-banner">
        <div class="judge-hero-bg"></div>
        <div class="judge-hero-inner">
          <div class="judge-hero-left">
            <CdxIcon :icon="cdxIconArticleCheck" class="judge-hero-icon" />
            <div class="judge-hero-text">
              <div class="judge-hero-title">Ready to Judge?</div>
              <div class="judge-hero-sub">
                <span class="judge-hero-count">{{ overallStats.pending }}</span>
                article{{ overallStats.pending !== 1 ? 's' : '' }} are waiting for your review
              </div>
            </div>
          </div>
          <button class="judge-hero-btn" @click="router.push(`/${route.params.code}/jury/review-v2`)">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
            Start Judging
          </button>
        </div>
      </div>

            <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h2>Jury Statistics</h2>
          <p>Real-time overview of article submissions and jury activity.</p>
        </div>
        <div v-if="roles.is_owner" class="export-actions" style="display: flex; gap: 8px; align-items: center;">
          <button @click="handleExportJSON" style="padding: 6px 12px; border-radius: 6px; border: none; background: rgba(255,255,255,0.1); color: #e2e8f0; cursor: pointer;">JSON</button>
          <button @click="handleExportCSV" style="padding: 6px 12px; border-radius: 6px; border: none; background: rgba(255,255,255,0.1); color: #e2e8f0; cursor: pointer;">CSV</button>
          <button @click="handleExportWikitable" style="padding: 6px 12px; border-radius: 6px; border: none; background: #2563eb; color: #fff; font-weight: 600; cursor: pointer;">Wikitable</button>
        </div>
      </div>

      <div class="kpi-grid">
        <div class="kpi-card kpi-blue">
          <div class="kpi-inner">
            <div class="kpi-value">{{ overallStats.total }}</div>
            <div class="kpi-label">Total Submitted</div>
          </div>
        </div>
        <div class="kpi-card kpi-green">
          <div class="kpi-inner">
            <div class="kpi-value">{{ overallStats.accepted }}</div>
            <div class="kpi-label">Accepted</div>
          </div>
        </div>
        <div class="kpi-card kpi-red">
          <div class="kpi-inner">
            <div class="kpi-value">{{ overallStats.rejected }}</div>
            <div class="kpi-label">Rejected</div>
          </div>
        </div>
        <div class="kpi-card kpi-amber">
          <div class="kpi-inner">
            <div class="kpi-value">{{ overallStats.pending }}</div>
            <div class="kpi-label">Pending Review</div>
          </div>
        </div>
      </div>

            <div class="charts-row">
                <div class="chart-card">
          <div class="chart-card-header">
            <span class="chart-title">Submission Breakdown</span>
            <span class="chart-subtitle">By status</span>
          </div>
          <div class="doughnut-wrap">
            <Doughnut :data="doughnutData" :options="doughnutOptions" />
            <div class="doughnut-center-label">
              <div class="dcl-val">{{ overallStats.total }}</div>
              <div class="dcl-sub">articles</div>
            </div>
          </div>
          <div class="chart-key" aria-label="Submission status totals">
            <span class="chart-key-item"><i class="chart-key-dot chart-key-accepted"></i><span>Accepted</span><strong>{{ overallStats.accepted }}</strong></span>
            <span class="chart-key-item"><i class="chart-key-dot chart-key-rejected"></i><span>Rejected</span><strong>{{ overallStats.rejected }}</strong></span>
            <span class="chart-key-item"><i class="chart-key-dot chart-key-pending"></i><span>Pending</span><strong>{{ overallStats.pending }}</strong></span>
          </div>
        </div>

        <div class="chart-card chart-card-wide">
          <div class="chart-card-header">
            <span class="chart-title">Jury Activity</span>
          <span class="chart-subtitle">Articles judged per member</span>
          </div>
          <div class="bar-wrap" :style="{ height: `${Math.max(200, juryStats.length * 52 + 60)}px` }">
            <Bar v-if="juryStats.length" :data="barData" :options="barOptions" />
            <div v-else class="empty-chart">No jury reviews recorded yet.</div>
          </div>
          <div class="chart-key chart-key-inline" aria-label="Jury activity statuses">
            <span class="chart-key-item"><i class="chart-key-dot chart-key-accepted"></i><span>Accepted</span></span>
            <span class="chart-key-item"><i class="chart-key-dot chart-key-rejected"></i><span>Rejected</span></span>
          </div>
        </div>

      </div>

            <div class="jury-section">
        <div class="section-title">Jury Activity Breakdown</div>
        <table class="jury-table">
          <thead>
            <tr>
              <th>Jury Member</th>
              <th>Articles Judged</th>
              <th>Accepted Articles</th>
              <th>Rejected Articles</th>
              <th>Acceptance Rate</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="jury in juryStats" :key="jury.name">
              <td>
                <router-link :to="`/${route.params.code}/user/${encodeURIComponent(jury.name)}`" class="jury-name-link">
                  <div class="jury-name-cell">
                    <div class="jury-avatar">{{ jury.name[0].toUpperCase() }}</div>
                    {{ jury.name }}
                  </div>
                </router-link>
              </td>
              <td><strong>{{ jury.total }}</strong></td>
              <td class="text-green">{{ jury.accepted }}</td>
              <td class="text-red">{{ jury.rejected }}</td>
              <td>
                <div class="mini-bar-wrap">
                  <div class="mini-bar">
                    <div class="mini-bar-fill" :style="{ width: jury.total ? `${Math.round((jury.accepted/jury.total)*100)}%` : '0%' }"></div>
                  </div>
                  <span class="mini-bar-pct">{{ jury.total ? Math.round((jury.accepted / jury.total) * 100) : 0 }}%</span>
                </div>
              </td>
            </tr>
            <tr v-if="juryStats.length === 0">
              <td colspan="5" class="empty-state">No jury activity recorded yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="jury-section jury-progress-section">
        <div class="section-title section-title-row">
          <span>Jury Progress</span>
          <div v-if="roles.is_owner" class="redistribute-controls">
            <span v-if="redistributeMessage" class="redistribute-note" :class="{ 'is-error': redistributeFailed }">{{ redistributeMessage }}</span>
            <button class="redistribute-btn" :disabled="isRedistributing" @click="redistributeQueues">
              {{ isRedistributing ? 'Rebalancing…' : 'Rebalance queues' }}
            </button>
          </div>
        </div>
        <table class="jury-table">
          <thead>
            <tr>
              <th>Jury Member</th>
              <th>Assigned</th>
              <th>Judged</th>
              <th>Remaining</th>
              <th>Progress</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="jury in juryProgressRows" :key="`progress-${jury.name}`">
              <td>
                <div class="jury-name-cell">
                  <div class="jury-avatar">{{ jury.name[0].toUpperCase() }}</div>
                  {{ jury.name }}
                </div>
              </td>
              <td><strong>{{ jury.assigned }}</strong></td>
              <td class="text-green">{{ jury.judged }}</td>
              <td>{{ jury.remaining }}</td>
              <td>
                <div class="mini-bar-wrap">
                  <div class="mini-bar"><div class="mini-bar-fill" :style="{ width: `${jury.progress}%` }"></div></div>
                  <span class="jury-progress-count">{{ jury.judged.toLocaleString() }} / {{ jury.assigned.toLocaleString() }}</span>
                </div>
              </td>
            </tr>
            <tr v-if="juryProgressRows.length === 0">
              <td colspan="5" class="empty-state">No jury assignment data available yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
      </template>

      <section v-else-if="activeTab === 'errors'" class="errors-workspace">
        <header class="errors-hero">
          <div><span class="errors-eyebrow">Validation queue</span><h1>Errored articles</h1><p>These submissions did not pass the contest rules. Remove them individually or clean up the queue in one action.</p></div>
          <div class="errors-count-card"><strong>{{ erroredArticles.length.toLocaleString() }}</strong><span>validation failures</span></div>
        </header>
        <div class="errors-toolbar">
          <label class="errors-select-all"><input type="checkbox" :checked="allErrorsSelected" @change="toggleAllErrors" aria-label="Select all errored articles" /><span>Select all</span><small v-if="selectedErrorIds.length">{{ selectedErrorIds.length }} selected</small></label>
          <div class="errors-toolbar-actions"><button v-if="erroredArticles.length" type="button" class="bulk-remove-submissions errors-delete-button" :disabled="!selectedErrorIds.length || isBulkRemoving" @click="removeSelectedErrors"><CdxIcon :icon="cdxIconTrash" />{{ bulkRemoveLabel(selectedErrorIds.length) }}</button><button type="button" class="refresh-submissions errors-refresh-button" @click="fetchErrorArticles(); fetchStats()">Refresh list</button></div>
        </div>
        <p v-if="removalError" class="removal-error">{{ removalError }}</p>
        <div v-if="isLoadingErrorArticles && !errorArticles.length" class="errors-empty-state"><span class="errors-empty-icon">…</span><strong>Loading validation failures</strong><span>Checking the latest submissions.</span></div>
        <div v-else-if="!errorArticles.length" class="errors-empty-state errors-empty-success"><span class="errors-empty-icon">✓</span><strong>All clear</strong><span>There are no validation-failed submissions in this contest.</span></div>
        <div v-else class="error-article-list">
          <article v-for="article in displayedSubmissions" :key="article.article_id" class="error-article-card" :class="{ selected: selectedErrorIds.includes(article.article_id) }">
            <label class="error-card-check"><input type="checkbox" :checked="selectedErrorIds.includes(article.article_id)" @change="toggleErrorSelection(article.article_id)" :aria-label="`Select ${article.title}`" /></label>
            <div class="error-card-main"><div class="error-card-heading"><h2>{{ article.title }}</h2><span class="submission-status status-validation_failed">Validation failed</span></div><div class="error-card-meta">Submitted by <router-link :to="`/${route.params.code}/user/${encodeURIComponent(article.submitted_by)}`" class="jury-name-link">{{ article.submitted_by }}</router-link></div><div class="error-reason"><span class="error-reason-label">Why it failed</span><span>{{ article.validation_error || 'No validation details were recorded.' }}</span></div></div>
            <button type="button" class="remove-submission error-card-delete" :disabled="removingArticleId === article.article_id" title="Remove article from contest" @click="removeArticle(article)"><CdxIcon :icon="cdxIconTrash" /><span>Remove</span></button>
          </article>
        </div>
      </section>      <section v-else class="submissions-panel submission-groups">
        <div class="submissions-header">
          <div class="submission-heading-copy">
            <span class="submission-eyebrow">Contest submissions</span>
            <h2>All Submitted Articles</h2>
            <p>Submissions are grouped by user. Expand a user to select individual articles or manage the whole group.</p>
            <div class="submission-heading-meta" aria-label="Submission summary">
              <template v-if="isSearchingSubmissions">
                <span v-if="submissionSearchPending">Searching…</span>
                <span v-else-if="submissionSearchError">{{ submissionSearchError }}</span>
                <span v-else><strong>{{ submissionSearchTotal.toLocaleString() }}</strong> match “{{ debouncedSubmissionSearch }}”<template v-if="submissionSearchHasMore">, showing the {{ submissionSearchResults.length }} most recent</template></span>
              </template>
              <template v-else>
                <span><strong>{{ totalSubmissionCount.toLocaleString() }}</strong> articles from <strong>{{ groupedSubmissions.length.toLocaleString() }}</strong> users</span>
              </template>
              <span v-if="selectedSubmissionIds.length"><strong>{{ selectedSubmissionIds.length.toLocaleString() }}</strong> selected</span>
              <span v-if="selectionLocked" class="selection-locked-note">Loading submitters…</span>
            </div>
            <div class="submission-search">
              <span class="submission-search-icon" aria-hidden="true">🔍</span>
              <input
                v-model="submissionSearch"
                type="search"
                class="submission-search-input"
                placeholder="Search article titles across the whole contest…"
                aria-label="Search submitted article titles"
                @keydown.esc="clearSubmissionSearch"
              />
              <button
                v-if="submissionSearch"
                type="button"
                class="submission-search-clear"
                aria-label="Clear search"
                @click="clearSubmissionSearch"
              >×</button>
            </div>
          </div>
          <div class="submission-toolbar">
            <label class="select-all-submissions" :class="{ 'is-disabled': selectionLocked }">
              <input type="checkbox" :checked="allSubmissionsSelected" :indeterminate="someSubmissionsSelected" :disabled="selectionLocked" @change="toggleAllSubmissions" aria-label="Select all submitted articles" />
              Select all
            </label>
            <button type="button" class="bulk-remove-submissions" :disabled="!selectedSubmissionIds.length || isBulkRemoving || selectionLocked" @click="removeSelectedSubmissions()">
              {{ bulkRemoveLabel(selectedSubmissionIds.length) }}
            </button>
            <button type="button" class="refresh-submissions" @click="fetchArticles(); fetchStats()">Refresh</button>
          </div>
        </div>
        <p v-if="removalError" class="removal-error">{{ removalError }}</p>
        <div v-if="isSearchingSubmissions && submissionSearchPending" class="empty-state group-empty">Searching…</div>
        <div v-else-if="isSearchingSubmissions && !groupedSubmissions.length" class="empty-state group-empty">No articles match “{{ debouncedSubmissionSearch }}”.</div>
        <div v-else-if="!isSearchingSubmissions && isLoadingArticles && !groupedSubmissions.length" class="empty-state group-empty">Loading submitters…</div>
        <div v-else-if="!groupedSubmissions.length" class="empty-state group-empty">No articles have been submitted yet.</div>
        <div v-else class="submitter-groups">
          <article v-for="group in groupedSubmissions" :key="group.username" class="submitter-group">
            <header class="submitter-group-header">
              <button type="button" class="submitter-toggle" :aria-expanded="!!expandedSubmitters[group.username]" @click="toggleSubmitter(group.username)">
                <span class="group-chevron" :class="{ open: expandedSubmitters[group.username] }">›</span>
                <span class="group-user">{{ group.username }}</span>
                <span class="group-count">{{ group.count }}</span>
              </button>
              <label class="group-select" :class="{ 'is-disabled': selectionLocked }">
                <input type="checkbox" :checked="groupFullySelected(group)" :indeterminate="groupPartiallySelected(group)" :disabled="selectionLocked || group.isLoading" @change="toggleGroupSelection(group)" :aria-label="`Select all articles by ${group.username}`" />
                Select all
              </label>
              <button type="button" class="group-delete" :disabled="!groupSelectedCount(group) || isBulkRemoving || selectionLocked" @click="removeSelectedSubmissions(group)">Delete selected</button>
            </header>
            <div v-if="expandedSubmitters[group.username]" class="submitter-articles">
              <p v-if="group.isLoading" class="group-inline-note">Loading {{ group.count }} article{{ group.count === 1 ? '' : 's' }}…</p>
              <p v-else-if="group.error" class="group-inline-note group-inline-error">{{ group.error }} <button type="button" class="load-more-group" @click="loadSubmitterArticles(group.username, { force: true })">Retry</button></p>
              <label v-for="article in visibleGroupArticles(group)" :key="article.article_id" class="submitter-article">
                <input type="checkbox" :checked="selectedSubmissionIds.includes(article.article_id)" @change="toggleSubmissionSelection(article.article_id)" :aria-label="`Select ${article.title}`" />
                <span class="submitter-article-copy">
                  <strong>{{ article.title }}</strong>
                  <small>{{ statusLabel(article.status) }} · {{ article.validation_error || 'No validation error' }}</small>
                </span>
                <button type="button" class="remove-submission" :disabled="removingArticleId === article.article_id" title="Remove article from contest" @click.stop="removeArticle(article)"><CdxIcon :icon="cdxIconTrash" /></button>
              </label>
              <button v-if="groupHasMore(group)" type="button" class="load-more-group" @click="loadMoreGroupArticles(group)">
                Load 100 more
              </button>
            </div>
          </article>
          <div v-if="hasUnloadedGroups" class="loading-more-note">
            Articles load when you open a user — nothing else is fetched up front.
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped src="../styles/views/JuryStatsFresh.css"></style>
