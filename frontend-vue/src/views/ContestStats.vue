<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { CdxTable } from '@wikimedia/codex';
import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  Filler,
  CategoryScale,
  LinearScale,
  Tooltip,
} from 'chart.js';
import { useContestStats } from '../composables/useContestData';
import { formatDate, formatDateLong } from '../utils/datetime';
import GlobalLoader from '../components/ui/GlobalLoader.vue';

ChartJS.register(LineElement, PointElement, Filler, CategoryScale, LinearScale, Tooltip);

// Public page. Both sources are open: /stats serves counts and the daily curve
// to anyone (it withholds only the per-jury tallies), and /results serves the
// submitter standings -- the same endpoint the Results page uses, rather than a
// second public-only route returning the same rows.
const props = defineProps({
  contest: { type: Object, default: null },
});
const route = useRoute();
const statsQuery = useContestStats(() => route.params.code);

const counts = computed(() => statsQuery.data.value?.status_counts || {});
const daily = computed(() => statsQuery.data.value?.daily || []);
const reviewed = computed(() => (counts.value.accepted || 0) + (counts.value.rejected || 0));
const busiest = computed(() => daily.value.reduce(
  (best, day) => (best && best.count >= day.count ? best : day), null));

const summary = computed(() => [
  { label: 'Submitted', value: counts.value.total || 0 },
  { label: 'Reviewed', value: reviewed.value },
  { label: 'Accepted', value: counts.value.accepted || 0, tone: 'green' },
  { label: 'Rejected', value: counts.value.rejected || 0, tone: 'red' },
  { label: 'Pending', value: counts.value.pending || 0, tone: 'amber' },
]);

// One series, so no legend -- the heading names it. The line is the app's
// accent rather than a categorical hue: nothing here is identified by colour,
// the x position carries the meaning.
const ACCENT = '#355b80';
const chartData = computed(() => ({
  labels: daily.value.map(d => d.date),
  datasets: [{
    data: daily.value.map(d => d.count),
    borderColor: ACCENT,
    borderWidth: 2,
    // Monotone rather than a plain tension: cubic smoothing overshoots around
    // a spike and draws the curve below zero between two real points, which
    // for a count is a value that never happened.
    cubicInterpolationMode: 'monotone',
    fill: true,
    backgroundColor: (ctx) => {
      const { ctx: canvas, chartArea } = ctx.chart;
      if (!chartArea) return 'rgba(53,91,128,.10)';
      const gradient = canvas.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
      gradient.addColorStop(0, 'rgba(53,91,128,.22)');
      gradient.addColorStop(1, 'rgba(53,91,128,.02)');
      return gradient;
    },
    pointRadius: 2.5,
    pointHoverRadius: 5,
    pointBackgroundColor: ACCENT,
    pointBorderColor: '#ffffff',
    pointBorderWidth: 1.5,
  }],
}));

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  // Follows the cursor across the whole column rather than needing a hit on
  // the 2.5px dot itself.
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#ffffff',
      titleColor: '#20364d',
      bodyColor: '#47637c',
      borderColor: '#c7d6e3',
      borderWidth: 1,
      padding: 10,
      displayColors: false,
      callbacks: {
        title: items => formatDateLong(items[0].label),
        label: ctx => `${ctx.parsed.y.toLocaleString()} ${ctx.parsed.y === 1 ? 'submission' : 'submissions'}`,
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      border: { color: '#c7d6e3' },
      ticks: {
        color: '#47637c',
        font: { size: 11 },
        maxRotation: 0,
        autoSkipPadding: 24,
        callback(value) { return formatDate(this.getLabelForValue(value)); },
      },
    },
    y: {
      beginAtZero: true,
      grid: { color: '#eef4f8' },
      border: { display: false },
      ticks: { color: '#47637c', font: { size: 11 }, precision: 0 },
    },
  },
};

// Standings come from /api/contests/{code}/results, same as the Results page.
// Sorted here for the same reason it sorts there: the endpoint returns rows
// grouped by submitter, not ranked.
const submitters = ref([]);
const submitterColumns = [
  { id: 'rank', label: 'Rank', width: '70px' },
  { id: 'username', label: 'Username', minWidth: '160px' },
  { id: 'total', label: 'Submitted', textAlign: 'number' },
  { id: 'accepted', label: 'Accepted', textAlign: 'number' },
  { id: 'rejected', label: 'Rejected', textAlign: 'number' },
  { id: 'pending', label: 'Pending', textAlign: 'number' },
];
const rankedSubmitters = computed(() => submitters.value.map((s, i) => ({ ...s, rank: i + 1 })));

onMounted(async () => {
  try {
    const res = await fetch(`/api/contests/${route.params.code}/results`);
    if (!res.ok) return;
    const data = await res.json();
    submitters.value = (data.submitters || []).sort((a, b) =>
      (b.accepted !== a.accepted ? b.accepted - a.accepted : b.total - a.total));
  } catch (err) {
    console.error('Failed to load results', err);
  }
});
</script>

<template>
  <div class="stats-page">
    <header class="stats-head">
      <h1>Statistics</h1>
      <p v-if="contest">
        {{ formatDateLong(contest.start_date) }} &ndash; {{ formatDateLong(contest.end_date) }}
      </p>
    </header>

    <GlobalLoader v-if="statsQuery.isLoading.value" label="Loading statistics…" />
    <div v-else-if="statsQuery.error.value" class="stats-error">
      Statistics could not be loaded. Reload the page to try again.
    </div>

    <template v-else>
      <div class="summary-strip">
        <div v-for="item in summary" :key="item.label" class="summary-item" :class="item.tone && `tone-${item.tone}`">
          <span class="summary-value">{{ item.value.toLocaleString() }}</span>
          <span class="summary-label">{{ item.label }}</span>
        </div>
      </div>

      <section class="chart-panel">
        <div class="chart-head">
          <h2>Submissions per day</h2>
          <p v-if="busiest">
            Busiest day: {{ formatDate(busiest.date) }}, {{ busiest.count.toLocaleString() }} articles
          </p>
        </div>
        <div v-if="daily.length" class="chart-frame">
          <Line :data="chartData" :options="chartOptions" aria-label="Articles submitted per day" />
        </div>
        <p v-else class="chart-empty">No submissions yet.</p>
      </section>

      <section class="standings">
        <div class="standings-head">
          <h2>Results</h2>
          <router-link :to="`/${route.params.code}/result`">Full results page</router-link>
        </div>
        <cdx-table
          caption="Submitter standings"
          hide-caption
          :columns="submitterColumns"
          :data="rankedSubmitters"
        >
          <template #item-username="{ item }">
            <router-link :to="`/${route.params.code}/user/${encodeURIComponent(item)}`">{{ item }}</router-link>
          </template>
          <template #item-accepted="{ item }"><span :class="item ? 'tone-accepted' : 'tone-zero'">{{ item.toLocaleString() }}</span></template>
          <template #item-rejected="{ item }"><span :class="item ? 'tone-rejected' : 'tone-zero'">{{ item.toLocaleString() }}</span></template>
          <template #empty-state>No submissions yet.</template>
        </cdx-table>
      </section>
    </template>
  </div>
</template>

<style scoped src="../styles/views/ContestStats.css"></style>
