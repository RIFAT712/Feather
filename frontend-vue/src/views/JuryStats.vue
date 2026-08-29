<script setup>
import { ref, computed, inject, onMounted, watch, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { CdxIcon } from '@wikimedia/codex';
import { cdxIconArticleCheck, cdxIconTrash } from '@wikimedia/codex-icons';
import { useQueryClient } from '@tanstack/vue-query';
import { useContestStats, useContestLog, useContestErrorLog, removeArticlesFromLogCache, useContestArticleSearch, SEARCH_MIN_LENGTH } from '../composables/useContestData';
import { Doughnut, Bar } from 'vue-chartjs';
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

// "All submitted" tab: fetched lazily -- only once that tab is actually
// opened (`enabled` below) -- and progressively (see useContestLog), and
// shares its cache entry with any other view that has already crawled this
// contest without reviews (there is none today, but the key is shared by
// design). isLoadingMoreArticles covers both a first-time crawl's catch-up
// pages and a revisit's background revalidation -- vue-query folds both into
// the same isFetching.
const articlesQuery = useContestLog(() => route.params.code, false, {
  enabled: computed(() => isAuthorized.value && activeTab.value === 'submissions'),
});
const articles = computed(() => articlesQuery.data.value?.items || []);
const isLoadingArticles = computed(() => articlesQuery.isLoading.value);
const isLoadingMoreArticles = computed(() => articlesQuery.isFetching.value && !articlesQuery.isLoading.value);
const fetchArticles = () => articlesQuery.refetch();

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

onMounted(async () => {
  if (!isAuthorized.value) return;
  try {
    const progressRes = await fetch(`/api/jury-panel/contests/${route.params.code}/progress`);
    if (progressRes.ok) juryProgress.value = await progressRes.json();
  } catch (err) {
    console.error(err);
  }
});

const overallStats = computed(() => {
  const counts = stats.value.status_counts || {};
  const total = counts.total || 0;
  const accepted = counts.accepted || 0;
  const rejected = counts.rejected || 0;
  // "Pending" here means everything not yet decided, including validation failures.
  return { total, accepted, rejected, pending: total - accepted - rejected };
});

const acceptRate = computed(() => {
  if (!overallStats.value.total) return 0;
  return Math.round((overallStats.value.accepted / overallStats.value.total) * 100);
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
const displayedSubmissions = computed(() => activeTab.value === 'errors' ? erroredArticles.value : articles.value);
const allErrorsSelected = computed(() => erroredArticles.value.length > 0 && selectedErrorIds.value.length === erroredArticles.value.length);
// Title search over the whole contest, server-side (?q=). Filtering
// `articles` client-side would only ever search the pages crawled so far --
// this tab loads progressively, so early in a crawl a client-side filter
// silently reports "no matches" for articles it simply hasn't fetched yet.
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
// Grouping (and therefore select-all / bulk delete) operates on whatever is
// on screen, so a bulk action during a search only ever touches matches.
const submissionSource = computed(() => (isSearchingSubmissions.value ? submissionSearchResults.value : articles.value));

const groupedSubmissions = computed(() => {
  const groups = new Map();
  for (const article of submissionSource.value) {
    const username = article.submitted_by || 'Unknown user';
    if (!groups.has(username)) groups.set(username, []);
    groups.get(username).push(article);
  }
  return Array.from(groups, ([username, groupArticles]) => ({ username, articles: groupArticles }));
});
const allSubmissionIds = computed(() => groupedSubmissions.value.flatMap(group => group.articles.map(article => article.article_id)));
const allSubmissionsSelected = computed(() => allSubmissionIds.value.length > 0 && allSubmissionIds.value.every(id => selectedSubmissionIds.value.includes(id)));
const someSubmissionsSelected = computed(() => selectedSubmissionIds.value.length > 0 && !allSubmissionsSelected.value);

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
  selectedSubmissionIds.value = selectedSubmissionIds.value.length ? [] : [...allSubmissionIds.value];
};
const groupSelectedCount = (group) => group.articles.filter(article => selectedSubmissionIds.value.includes(article.article_id)).length;
const groupPartiallySelected = (group) => groupSelectedCount(group) > 0 && groupSelectedCount(group) < group.articles.length;
const toggleGroupSelection = (group) => {
  const groupIds = group.articles.map(article => article.article_id);
  const shouldClear = groupSelectedCount(group) > 0;
  selectedSubmissionIds.value = shouldClear
    ? selectedSubmissionIds.value.filter(id => !groupIds.includes(id))
    : [...new Set([...selectedSubmissionIds.value, ...groupIds])];
};
const toggleSubmitter = (username) => {
  expandedSubmitters.value = { ...expandedSubmitters.value, [username]: !expandedSubmitters.value[username] };
  if (visibleGroupCounts.value[username] === undefined) {
    visibleGroupCounts.value = { ...visibleGroupCounts.value, [username]: 100 };
  }
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
  if (activeTab.value === 'errors') refreshes.push(fetchErrorArticles());
  else refreshes.push(fetchArticles());
  return Promise.all(refreshes);
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
    await refreshCurrentTabArticles();
  } catch (err) {
    removalError.value = err.message || 'Could not remove the article.';
  } finally {
    removingArticleId.value = null;
  }
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
    const res = await fetch('/api/articles/bulk-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ article_ids: ids }),
    });
    const result = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(result.detail || 'Could not remove selected articles.');
    const failed = (result.failed || []).map(item => item.article_id);
    selectedSubmissionIds.value = selectedSubmissionIds.value.filter(id => failed.includes(id));
    if (failed.length) throw new Error(`Could not remove ${failed.length} article(s).`);
    removeArticlesFromLogCache(queryClient, route.params.code, ids.filter(id => !failed.includes(id)));
    await Promise.all([fetchArticles(), fetchStats()]);
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
    const res = await fetch('/api/articles/bulk-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ article_ids: ids }),
    });
    const result = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(result.detail || 'Could not remove selected articles.');
    const failed = (result.failed || []).map(item => item.article_id);
    selectedErrorIds.value = failed;
    if (failed.length) throw new Error(`Could not remove ${failed.length} article(s).`);
    // Errored articles are also part of the shared "all submitted" cache if
    // that tab was ever opened -- prune them there too, not just their own
    // separately-fetched list.
    removeArticlesFromLogCache(queryClient, route.params.code, ids.filter(id => !failed.includes(id)));
    await Promise.all([fetchErrorArticles(), fetchStats()]);
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
    backgroundColor: ['#22c55e', '#ef4444', '#f59e0b'],
    hoverBackgroundColor: ['#16a34a', '#dc2626', '#d97706'],
    borderWidth: 0,
    hoverOffset: 8,
  }],
}));

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '72%',
  plugins: {
    legend: {
      position: 'bottom',
      labels: {
        padding: 20,
        font: { size: 13, family: 'Inter, sans-serif' },
        color: '#47637c',
        usePointStyle: true,
        pointStyleWidth: 10,
      },
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
      backgroundColor: '#22c55e',
      borderRadius: 4,
    },
    {
      label: 'Rejected',
      data: juryStats.value.map(j => j.rejected),
      backgroundColor: '#ef4444',
      borderRadius: 4,
    },
  ],
}));

const barOptions = {
  indexAxis: 'y',
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'top',
      labels: {
        font: { size: 12, family: 'Inter, sans-serif' },
        color: '#47637c',
        usePointStyle: true,
      },
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
      grid: { color: 'rgba(255,255,255,0.05)' },
      ticks: { font: { size: 12 }, color: '#47637c', stepSize: 1 },
      border: { display: false },
    },
    y: {
      stacked: true,
      grid: { display: false },
      ticks: { font: { size: 13 }, color: '#47637c' },
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

    <div v-else-if="isLoading" class="loading-state">
      <div class="spinner"></div>
      <p>Crunching the numbers...</p>
    </div>

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
          <div class="kpi-bar-bg">
            <div class="kpi-bar-fill" style="width:100%; background:#2563eb;"></div>
          </div>
        </div>
        <div class="kpi-card kpi-green">
          <div class="kpi-inner">
            <div class="kpi-value">{{ overallStats.accepted }}</div>
            <div class="kpi-label">গৃহীত (Accepted)</div>
          </div>
          <div class="kpi-bar-bg">
            <div class="kpi-bar-fill" :style="{ width: overallStats.total ? `${(overallStats.accepted/overallStats.total)*100}%` : '0%', background: '#22c55e' }"></div>
          </div>
        </div>
        <div class="kpi-card kpi-red">
          <div class="kpi-inner">
            <div class="kpi-value">{{ overallStats.rejected }}</div>
            <div class="kpi-label">প্রত্যাখ্যাত (Rejected)</div>
          </div>
          <div class="kpi-bar-bg">
            <div class="kpi-bar-fill" :style="{ width: overallStats.total ? `${(overallStats.rejected/overallStats.total)*100}%` : '0%', background: '#ef4444' }"></div>
          </div>
        </div>
        <div class="kpi-card kpi-amber">
          <div class="kpi-inner">
            <div class="kpi-value">{{ overallStats.pending }}</div>
            <div class="kpi-label">অপেক্ষমাণ (Pending Review)</div>
          </div>
          <div class="kpi-bar-bg">
            <div class="kpi-bar-fill" :style="{ width: overallStats.total ? `${(overallStats.pending/overallStats.total)*100}%` : '0%', background: '#f59e0b' }"></div>
          </div>
        </div>
        <div class="kpi-card kpi-purple">
          <div class="kpi-inner">
            <div class="kpi-value">{{ acceptRate }}<span class="kpi-unit">%</span></div>
            <div class="kpi-label">Acceptance Rate</div>
          </div>
          <div class="kpi-bar-bg">
            <div class="kpi-bar-fill" :style="{ width: `${acceptRate}%`, background: '#818cf8' }"></div>
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
        <div class="section-title">Jury Progress</div>
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

      <section v-else-if="activeTab === 'errors'" class="submissions-panel">
        <div class="submissions-header">
          <div>
            <h2>{{ activeTab === 'errors' ? 'Errored Articles' : 'All Submitted Articles' }}</h2>
            <p>{{ activeTab === 'errors' ? 'Validation-failed submissions that can be removed in bulk.' : 'Review every submission, including validation failures, and remove entries when needed.' }}</p>
          </div>
          <div class="submission-toolbar">
            <button v-if="activeTab === 'errors' && erroredArticles.length" type="button" class="bulk-remove-submissions" :disabled="!selectedErrorIds.length || isBulkRemoving" @click="removeSelectedErrors">
              {{ isBulkRemoving ? 'Removing…' : `Delete selected (${selectedErrorIds.length})` }}
            </button>
            <button type="button" class="refresh-submissions" @click="fetchErrorArticles(); fetchStats()">Refresh</button>
          </div>
        </div>

        <p v-if="removalError" class="removal-error">{{ removalError }}</p>

        <div class="submissions-table-wrap">
          <table class="submissions-table">
            <thead>
              <tr>
                <th class="selection-column"><input type="checkbox" :checked="allErrorsSelected" @change="toggleAllErrors" aria-label="Select all errored articles" /></th>
                <th>Article</th>
                <th>Submitted by</th>
                <th>Status</th>
                <th>Details</th>
                <th><span class="visually-hidden">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="article in displayedSubmissions" :key="article.article_id">
                <td class="selection-column"><input type="checkbox" :checked="selectedErrorIds.includes(article.article_id)" @change="toggleErrorSelection(article.article_id)" :aria-label="`Select ${article.title}`" /></td>
                <td class="submission-title">{{ article.title }}</td>
                <td>
                  <router-link :to="`/${route.params.code}/user/${encodeURIComponent(article.submitted_by)}`" class="jury-name-link">
                    {{ article.submitted_by }}
                  </router-link>
                </td>
                <td><span class="submission-status" :class="`status-${article.status}`">{{ statusLabel(article.status) }}</span></td>
                <td class="submission-details">{{ article.validation_error || '—' }}</td>
                <td class="submission-action">
                  <button
                    type="button"
                    class="remove-submission"
                    :disabled="removingArticleId === article.article_id"
                    title="Remove article from contest"
                    @click="removeArticle(article)"
                  ><CdxIcon :icon="cdxIconTrash" /></button>
                </td>
              </tr>
              <tr v-if="isLoadingErrorArticles && !errorArticles.length">
                <td colspan="6" class="empty-state">Loading errored articles…</td>
              </tr>
              <tr v-else-if="!errorArticles.length">
                <td colspan="6" class="empty-state">No errored articles.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <section v-else class="submissions-panel submission-groups">
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
                <span>Showing <strong>{{ articles.length.toLocaleString() }}</strong> of <strong>{{ (stats.status_counts.total || 0).toLocaleString() }}</strong> articles</span>
              </template>
              <span><strong>{{ groupedSubmissions.length.toLocaleString() }}</strong> users loaded</span>
              <span v-if="selectedSubmissionIds.length"><strong>{{ selectedSubmissionIds.length.toLocaleString() }}</strong> selected</span>
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
            <label class="select-all-submissions">
              <input type="checkbox" :checked="allSubmissionsSelected" :indeterminate="someSubmissionsSelected" @change="toggleAllSubmissions" aria-label="Select all submitted articles" />
              Select all
            </label>
            <button type="button" class="bulk-remove-submissions" :disabled="!selectedSubmissionIds.length || isBulkRemoving" @click="removeSelectedSubmissions()">
              {{ isBulkRemoving ? 'Removing…' : `Delete selected (${selectedSubmissionIds.length})` }}
            </button>
            <button type="button" class="refresh-submissions" @click="fetchArticles(); fetchStats()">Refresh</button>
          </div>
        </div>
        <p v-if="removalError" class="removal-error">{{ removalError }}</p>
        <div v-if="isSearchingSubmissions && submissionSearchPending" class="empty-state group-empty">Searching…</div>
        <div v-else-if="isSearchingSubmissions && !groupedSubmissions.length" class="empty-state group-empty">No articles match “{{ debouncedSubmissionSearch }}”.</div>
        <div v-else-if="!isSearchingSubmissions && isLoadingArticles && !groupedSubmissions.length" class="empty-state group-empty">Loading submissions…</div>
        <div v-else-if="!groupedSubmissions.length" class="empty-state group-empty">No articles have been submitted yet.</div>
        <div v-else class="submitter-groups">
          <article v-for="group in groupedSubmissions" :key="group.username" class="submitter-group">
            <header class="submitter-group-header">
              <button type="button" class="submitter-toggle" :aria-expanded="!!expandedSubmitters[group.username]" @click="toggleSubmitter(group.username)">
                <span class="group-chevron" :class="{ open: expandedSubmitters[group.username] }">›</span>
                <span class="group-user">{{ group.username }}</span>
                <span class="group-count">{{ group.articles.length }}</span>
              </button>
              <label class="group-select">
                <input type="checkbox" :checked="groupSelectedCount(group) === group.articles.length" :indeterminate="groupPartiallySelected(group)" @change="toggleGroupSelection(group)" :aria-label="`Select all articles by ${group.username}`" />
                Select all
              </label>
              <button type="button" class="group-delete" :disabled="!groupSelectedCount(group) || isBulkRemoving" @click="removeSelectedSubmissions(group)">Delete selected</button>
            </header>
            <div v-if="expandedSubmitters[group.username]" class="submitter-articles">
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
          <div v-if="isLoadingMoreArticles" class="loading-more-note">
            Loading the rest in the background…
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped src="../styles/views/JuryStatsFresh.css"></style>
