<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { CdxIcon } from '@wikimedia/codex';
import { cdxIconArticleCheck, cdxIconTrash } from '@wikimedia/codex-icons';
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

const route = useRoute();
const router = useRouter();
const isLoading = ref(true);
const articles = ref([]);
const roles = ref({ is_jury: false, is_owner: false });
const isAuthorized = computed(() => roles.value.is_jury || roles.value.is_owner);
const activeTab = ref('overview');
const removingArticleId = ref(null);
const removalError = ref('');

const fetchArticles = async () => {
  const res = await fetch(`/api/contests/${route.params.code}/log`);
  if (!res.ok) throw new Error('Could not load submitted articles.');
  articles.value = await res.json();
};

onMounted(async () => {
  try {
    const roleRes = await fetch(`/api/contests/${route.params.code}/my-role`);
    if (roleRes.ok) roles.value = await roleRes.json();
    
    if (!isAuthorized.value) {
      isLoading.value = false;
      return;
    }

    await fetchArticles();
  } catch (err) {
    console.error(err);
  } finally {
    isLoading.value = false;
  }
});

const overallStats = computed(() => {
  const total = articles.value.length;
  let accepted = 0, rejected = 0, pending = 0;
  for (const a of articles.value) {
    if (a.status === 'accepted') accepted++;
    else if (a.status === 'rejected') rejected++;
    else pending++;
  }
  return { total, accepted, rejected, pending };
});

const acceptRate = computed(() => {
  if (!overallStats.value.total) return 0;
  return Math.round((overallStats.value.accepted / overallStats.value.total) * 100);
});

const juryStats = computed(() => {
  const stats = {};
  for (const a of articles.value) {
    for (const r of a.reviews) {
      if (!stats[r.reviewer]) stats[r.reviewer] = { articles: {} };
      const previous = stats[r.reviewer].articles[a.article_id];
      const previousTime = previous?.reviewed_at ? new Date(previous.reviewed_at).getTime() : -1;
      const reviewTime = r.reviewed_at ? new Date(r.reviewed_at).getTime() : 0;
      if (!previous || reviewTime >= previousTime) {
        stats[r.reviewer].articles[a.article_id] = r;
      }
    }
  }
  return Object.keys(stats).map(name => {
    const latestReviews = Object.values(stats[name].articles);
    return {
      name,
      total: latestReviews.length,
      accepted: latestReviews.filter(r => r.decision === 'accepted').length,
      rejected: latestReviews.filter(r => r.decision === 'rejected').length,
    };
  }).sort((a, b) => b.total - a.total);
});

const statusLabel = (status) => ({
  accepted: 'Accepted',
  rejected: 'Rejected',
  pending: 'Pending',
  validation_failed: 'Validation failed',
}[status] || status);

const removeArticle = async (article) => {
  if (!confirm(`Remove "${article.title}" permanently from this contest?`)) return;

  removingArticleId.value = article.article_id;
  removalError.value = '';
  try {
    const res = await fetch(`/api/articles/${article.article_id}`, { method: 'DELETE' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Could not remove the article.');
    await fetchArticles();
  } catch (err) {
    removalError.value = err.message || 'Could not remove the article.';
  } finally {
    removingArticleId.value = null;
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
        color: '#9ca3af',
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
        color: '#9ca3af',
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
      ticks: { font: { size: 12 }, color: '#6b7280', stepSize: 1 },
      border: { display: false },
    },
    y: {
      stacked: true,
      grid: { display: false },
      ticks: { font: { size: 13 }, color: '#9ca3af' },
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
        >All submitted <span>{{ articles.length }}</span></button>
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
          <button class="judge-hero-btn" @click="router.push(`/${route.params.code}/jury/review`)">
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
      </template>

      <section v-else class="submissions-panel">
        <div class="submissions-header">
          <div>
            <h2>All Submitted Articles</h2>
            <p>Review every submission, including validation failures, and remove entries when needed.</p>
          </div>
          <button type="button" class="refresh-submissions" @click="fetchArticles">Refresh</button>
        </div>

        <p v-if="removalError" class="removal-error">{{ removalError }}</p>

        <div class="submissions-table-wrap">
          <table class="submissions-table">
            <thead>
              <tr>
                <th>Article</th>
                <th>Submitted by</th>
                <th>Status</th>
                <th>Details</th>
                <th><span class="visually-hidden">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="article in articles" :key="article.article_id">
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
              <tr v-if="!articles.length">
                <td colspan="5" class="empty-state">No articles have been submitted yet.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* Unauthorized Banner */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.unauthorized-banner {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 60px 20px;
}
.unauthorized-content {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 40px;
  max-width: 480px;
  text-align: center;
}
.unauthorized-content .icon { font-size: 2.5rem; display: block; margin-bottom: 12px; }
.unauthorized-content h2 { color: #f3f4f6; font-size: 1.25rem; font-weight: 700; margin: 0 0 8px; }
.unauthorized-content p { color: #9ca3af; margin: 0; font-size: 0.95rem; line-height: 1.5; }

.stats-page { min-height: 100vh; background: #0a0a0a; }

.stats-layout {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  background: #0a0a0a;
  font-family: 'Inter', sans-serif;
}

.jury-tabs {
  display: flex;
  gap: 2px;
  padding: 16px 32px 0;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.jury-tab {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  padding: 10px 14px;
}
.jury-tab:hover { color: #e2e8f0; background: rgba(255,255,255,0.04); }
.jury-tab.active { color: #ffffff; border-bottom-color: #ffffff; }
.jury-tab span { margin-left: 5px; color: #9ca3af; font-size: 0.75rem; }

.submissions-panel { padding: 28px 32px 32px; }
.submissions-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.submissions-header h2 { margin: 0 0 4px; color: #e2e8f0; font-size: 1.4rem; }
.submissions-header p { margin: 0; color: #9ca3af; font-size: 0.875rem; }
.refresh-submissions,
.remove-submission {
  border: 1px solid rgba(255,255,255,0.14);
  border-radius: 4px;
  background: transparent;
  color: #e2e8f0;
  cursor: pointer;
  font: inherit;
}
.refresh-submissions { padding: 7px 12px; font-size: 0.8rem; }
.refresh-submissions:hover { background: rgba(255,255,255,0.08); }
.removal-error { margin: 0 0 16px; color: #f87171; font-size: 0.875rem; }
.submissions-table-wrap { overflow-x: auto; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; }
.submissions-table { width: 100%; min-width: 760px; border-collapse: collapse; }
.submissions-table th,
.submissions-table td { padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.06); text-align: left; vertical-align: middle; }
.submissions-table th { color: #9ca3af; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }
.submissions-table td { color: #e2e8f0; font-size: 0.875rem; }
.submissions-table tr:last-child td { border-bottom: 0; }
.submission-title { font-weight: 600; }
.submission-details { max-width: 320px; color: #9ca3af !important; line-height: 1.4; }
.submission-status { display: inline-block; border: 1px solid rgba(255,255,255,0.14); border-radius: 4px; color: #d1d5db; font-size: 0.72rem; padding: 3px 6px; white-space: nowrap; }
.submission-status.status-validation_failed { color: #f87171; border-color: rgba(248,113,113,0.45); }
.submission-action { width: 48px; text-align: right !important; }
.remove-submission { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; color: #9ca3af; }
.remove-submission:hover:not(:disabled) { color: #f87171; border-color: #f87171; }
.remove-submission:disabled { cursor: wait; opacity: 0.5; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

/* Loading */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 16px;
  padding: 64px;
  color: #6b7280;
  font-size: 0.95rem;
}
.spinner {
  width: 32px; height: 32px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Page Header */
.page-header {
  padding: 28px 32px 0;
}
.page-header h2 {
  margin: 0 0 4px;
  font-size: 1.5rem;
  font-weight: 800;
  color: #e2e8f0;
}
.page-header p { margin: 0; color: #64748b; font-size: 0.875rem; }

/* KPI Cards */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 16px;
  padding: 24px 32px;
}
.kpi-card {
  background: #1a1a1a;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.07);
  padding: 20px 20px 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  overflow: hidden;
  transition: box-shadow 0.15s, transform 0.15s;
}
.kpi-card:hover { box-shadow: 0 6px 20px rgba(0,0,0,0.4); transform: translateY(-2px); }
.kpi-inner { padding-bottom: 16px; }
.kpi-value {
  font-size: 2rem;
  font-weight: 800;
  color: #e2e8f0;
  line-height: 1;
}
.kpi-unit { font-size: 1.1rem; font-weight: 600; }
.kpi-label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #9ca3af;
  margin-top: 4px;
}
.kpi-bar-bg {
  height: 4px;
  background: rgba(255,255,255,0.06);
}
.kpi-bar-fill {
  height: 100%;
  transition: width 0.9s cubic-bezier(0.4,0,0.2,1);
}
.kpi-blue .kpi-value { color: #60a5fa; }
.kpi-green .kpi-value { color: #4ade80; }
.kpi-red .kpi-value { color: #f87171; }
.kpi-amber .kpi-value { color: #fbbf24; }
.kpi-purple .kpi-value { color: #a78bfa; }

/* Mobile layout adjustments */
@media (max-width: 768px) {
  .jury-tabs { padding: 10px 16px 0; overflow-x: auto; }
  .jury-tab { flex: 0 0 auto; }
  .page-header { padding: 16px 16px 0; flex-direction: column; align-items: flex-start !important; gap: 12px; }
  .kpi-grid { padding: 16px; grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .charts-row { padding: 0 16px 16px; }
  .jury-section { margin: 0 16px 24px; }
  .judge-hero-banner { margin: 16px 16px 0; padding: 24px 20px; }
  .judge-hero-inner { flex-direction: column; align-items: flex-start; }
  .judge-hero-btn { width: 100%; justify-content: center; }
  .submissions-panel { padding: 20px 16px 24px; }
  .submissions-header { flex-direction: column; }
}

.chart-card {
  background: #1a1a1a;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.07);
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  padding: 20px 24px 24px;
}

.chart-card-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 20px;
}
.chart-title {
  font-size: 0.9rem;
  font-weight: 700;
  color: #e2e8f0;
}
.chart-subtitle {
  font-size: 0.75rem;
  color: #9ca3af;
}

/* Doughnut */
.doughnut-wrap {
  position: relative;
  height: 240px;
}
.doughnut-center-label {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -62%);
  text-align: center;
  pointer-events: none;
}
.dcl-val {
  font-size: 1.8rem;
  font-weight: 800;
  color: #e2e8f0;
  line-height: 1;
}
.dcl-sub {
  font-size: 0.7rem;
  color: #9ca3af;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Bar */
.bar-wrap {
  position: relative;
}
.empty-chart {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #9ca3af;
  font-style: italic;
  font-size: 0.9rem;
}

/* Jury Table */
.jury-section {
  margin: 0 32px 32px;
  background: #1a1a1a;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.07);
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}
.section-title {
  padding: 16px 20px;
  font-size: 0.875rem;
  font-weight: 700;
  color: #e2e8f0;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  background: rgba(255,255,255,0.03);
}
.jury-table {
  width: 100%;
  border-collapse: collapse;
}
.jury-table th, .jury-table td {
  padding: 12px 20px;
  text-align: left;
  font-size: 0.875rem;
}
.jury-table th {
  background: rgba(255,255,255,0.04);
  color: #64748b;
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  border-bottom: 1px solid rgba(255,255,255,0.07);
}
.jury-table td { border-bottom: 1px solid rgba(255,255,255,0.05); color: #e2e8f0; }
.jury-table tr:last-child td { border-bottom: none; }
.jury-table tr:hover td { background: rgba(255,255,255,0.03); }
.jury-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  transition: color 0.15s;
}
.jury-name-link {
  text-decoration: none;
  color: inherit;
}
.jury-name-link:hover .jury-name-cell {
  color: #ffffff;
}
.jury-avatar {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f46e5, #2563eb);
  color: white;
  font-size: 0.75rem;
  font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.text-green { color: #22c55e; font-weight: 600; }
.text-red { color: #ef4444; font-weight: 600; }
.mini-bar-wrap { display: flex; align-items: center; gap: 8px; }
.mini-bar {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.08);
  border-radius: 6px;
  overflow: hidden;
  min-width: 60px;
}
.mini-bar-fill { height: 100%; background: #22c55e; border-radius: 6px; transition: width 0.4s; }
.mini-bar-pct { font-size: 0.78rem; color: #6b7280; font-weight: 600; white-space: nowrap; }
.empty-state { text-align: center; color: #9ca3af; font-style: italic; padding: 32px !important; }

/* Judge Hero Banner */
.judge-hero-banner {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  margin: 24px 32px 8px;
  padding: 36px 40px;
  background: #111111;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.judge-hero-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 20% 50%, rgba(255,255,255,0.05) 0%, transparent 60%),
    radial-gradient(ellipse at 80% 50%, rgba(255,255,255,0.03) 0%, transparent 60%);
  pointer-events: none;
}
.judge-hero-inner {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}
.judge-hero-left {
  display: flex;
  align-items: center;
  gap: 20px;
}
.judge-hero-icon {
  font-size: 3rem;
  line-height: 1;
  filter: drop-shadow(0 0 16px rgba(99,102,241,0.6));
}
.judge-hero-text {}
.judge-hero-title {
  font-size: 1.6rem;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}
.judge-hero-sub {
  font-size: 1rem;
  color: rgba(255,255,255,0.65);
  line-height: 1.4;
}
.judge-hero-count {
  font-size: 1.2rem;
  font-weight: 800;
  color: #a5b4fc;
}
.judge-hero-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #2563eb;
  color: #fff;
  border: none;
  padding: 14px 32px;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 4px 20px rgba(37,99,235,0.5);
  transition: background 0.15s, transform 0.12s, box-shadow 0.15s;
  letter-spacing: 0.01em;
}
.judge-hero-btn:hover {
  background: #1d4ed8;
  transform: translateY(-2px);
  box-shadow: 0 8px 28px rgba(37,99,235,0.6);
}
.judge-hero-btn:active { transform: translateY(0); }
</style>
