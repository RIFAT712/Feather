<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { CdxTable } from '@wikimedia/codex';
import { Bar } from 'vue-chartjs';
import {
  Chart as ChartJS,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
} from 'chart.js';
import { useContestStats } from '../composables/useContestData';
import { formatDate, formatDateLong, parseApiDate } from '../utils/datetime';
import GlobalLoader from '../components/ui/GlobalLoader.vue';

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip);

// Public page: everything here comes from /api/contests/{code}/stats, which
// serves counts and the daily curve to anyone and withholds the per-jury
// tallies unless the caller is the owner or one of this contest's jury.
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

// One series, so no legend -- the heading names it. The bar colour is the
// app's accent rather than a categorical hue: nothing here is identified by
// colour, the x position carries the meaning.
const chartData = computed(() => ({
  labels: daily.value.map(d => formatDate(d.date)),
  datasets: [{
    data: daily.value.map(d => d.count),
    backgroundColor: '#355b80',
    hoverBackgroundColor: '#274d70',
    borderRadius: 4,
    borderSkipped: false,
    categoryPercentage: 0.9,
    barPercentage: 0.86,
  }],
}));

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#20364d',
      padding: 10,
      displayColors: false,
      callbacks: {
        label: ctx => `${ctx.parsed.y.toLocaleString()} submitted`,
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      border: { color: '#c7d6e3' },
      ticks: { color: '#47637c', font: { size: 11 }, maxRotation: 0, autoSkipPadding: 18 },
    },
    y: {
      beginAtZero: true,
      grid: { color: '#eef4f8' },
      border: { display: false },
      ticks: { color: '#47637c', font: { size: 11 }, precision: 0 },
    },
  },
};

const dayColumns = [
  { id: 'date', label: 'Day', minWidth: '160px' },
  { id: 'count', label: 'Submitted', textAlign: 'number' },
];
const dayRows = computed(() => daily.value.map(d => ({
  date: parseApiDate(d.date)?.format('ddd, MMM D, YYYY') || d.date,
  count: d.count.toLocaleString(),
})));
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
          <Bar :data="chartData" :options="chartOptions" aria-label="Articles submitted per day" />
        </div>
        <p v-else class="chart-empty">No submissions yet.</p>
      </section>

      <details v-if="daily.length" class="day-table">
        <summary>View the daily numbers as a table</summary>
        <cdx-table caption="Submissions per day" hide-caption :columns="dayColumns" :data="dayRows" />
      </details>
    </template>
  </div>
</template>

<style scoped src="../styles/views/ContestStats.css"></style>
