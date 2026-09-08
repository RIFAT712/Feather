<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { CdxTable, CdxProgressBar } from '@wikimedia/codex';
import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  Filler,
  CategoryScale,
  LinearScale,
  LogarithmicScale,
  Tooltip,
} from 'chart.js';
import { useContestStats } from '../composables/useContestData';
import { formatDate, formatDateLong } from '../utils/datetime';
import GlobalLoader from '../components/ui/GlobalLoader.vue';

ChartJS.register(LineElement, PointElement, Filler, CategoryScale, LinearScale, LogarithmicScale, Tooltip);

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
// Judging progress excludes validation_failed: those articles were never
// eligible for a jury, so counting them as outstanding work would leave the
// bar permanently short of 100% on any contest with rejected submissions.
const judgeable = computed(() => reviewed.value + (counts.value.pending || 0));
const progress = computed(() => (judgeable.value ? Math.round((reviewed.value / judgeable.value) * 100) : 0));

const summary = computed(() => [
  { label: 'Submitted', value: counts.value.total || 0 },
  { label: 'Reviewed', value: reviewed.value },
  { label: 'Accepted', value: counts.value.accepted || 0, tone: 'green' },
  { label: 'Rejected', value: counts.value.rejected || 0, tone: 'red' },
  { label: 'Pending', value: counts.value.pending || 0, tone: 'amber' },
]);

// Two series, so colour now carries identity and the legend is mandatory.
// Submissions keep the app accent; judgments get a teal that clears the
// colourblind-separation floor against it (deutan dE 19.3, tritan 20.9) and
// stays clear of the green/red/amber the style guide reserves for status.
// The dashed stroke is deliberate redundancy so the two never rely on hue.
const ACCENT = '#355b80';
const TEAL = '#17a2a8';
// The legend doubles as the series filter, so it is two real buttons in the
// chart head rather than chart.js's canvas legend: that one is clickable too,
// but a canvas-drawn label offers no hover state, no focus ring and no pressed
// state, so nobody discovers the toggle. Datasets are hidden in place rather
// than filtered out of the array -- the tooltip picks its noun by
// datasetIndex, which would shift if a series disappeared from it.
const SERIES = [
  { key: 'submitted', label: 'Submitted', color: ACCENT, dash: false },
  { key: 'judged', label: 'Judged', color: TEAL, dash: true },
];
const shown = ref({ submitted: true, judged: true });

// Drag-to-zoom on the x axis, the pageviews.toolforge.org interaction: drag
// across a span of days and the chart zooms to them.
// The chart always holds the *whole* series; zooming only moves the x scale's
// min/max onto a narrower index window. That is what makes the transition
// smooth: every point keeps its own label, so chart.js animates each one from
// its old pixel to its new one -- a real zoom. Two earlier attempts are the
// reason this is worth spelling out. Slicing the array into the chart instead
// changed the label set, and chart.js tweens by *index*, so old index 0 slid
// across to the new index 0 and the curve swept sideways through dates it
// never had. Remounting the chart on the range killed that morph but replaced
// it with an instant cut, and nothing can smooth a swapped canvas -- only fade
// it. No dependency either way: this is what chartjs-plugin-zoom does to the
// scale, minus the plugin.
// The range is stored as the two ISO dates, not as indices: /stats is polled,
// and an index would silently point at a different day once a new one arrives.
const frameRef = ref(null);
const zoom = ref(null);          // { from, to } ISO dates, or null for the whole run
const drag = ref(null);          // { a, b } while the mouse is down

// Index window for the x scale. Falls back to the full range if either date is
// no longer in the series, which is what a poll adding a day looks like.
// ponytail: the y axis keeps its full-data scale while zoomed, because
// chart.js sizes y from every point and not just the visible x window. That
// reads as deliberate -- the vertical scale stays comparable between zooms --
// but a quiet week does zoom to a flat line near the floor. Fitting y to the
// window means recomputing it in an afterScale hook; do that if the empty
// headroom ever bothers anyone more than the shifting scale would.
const zoomBounds = computed(() => {
  if (!zoom.value) return {};
  const min = daily.value.findIndex(d => d.date === zoom.value.from);
  const max = daily.value.findIndex(d => d.date === zoom.value.to);
  return min < 0 || max < 0 ? {} : { min, max };
});

// The live chart, looked up from the canvas rather than held in a template
// ref: one less lifecycle thing to get wrong, and chart.js's own registry is
// always current.
function chartOf() {
  const canvas = frameRef.value?.querySelector('canvas');
  return canvas ? ChartJS.getChart(canvas) : null;
}

// Both coordinate systems at once: `cx` is canvas-relative for the scale
// lookup, `fx` is frame-relative for the selection rectangle.
function track(event) {
  const chart = chartOf();
  if (!chart?.chartArea || !frameRef.value) return null;
  const canvas = chart.canvas.getBoundingClientRect();
  const frame = frameRef.value.getBoundingClientRect();
  const cx = Math.min(Math.max(event.clientX - canvas.left, chart.chartArea.left), chart.chartArea.right);
  return { cx, fx: cx + canvas.left - frame.left };
}

function onPointerDown(event) {
  // Mouse only. Claiming a touch drag here would mean touch-action: none on
  // the frame, i.e. no page scrolling past the chart on a phone.
  if (event.pointerType !== 'mouse' || event.button !== 0) return;
  const at = track(event);
  if (!at) return;
  drag.value = { a: at, b: at };
  event.currentTarget.setPointerCapture(event.pointerId);
}

function onPointerMove(event) {
  if (!drag.value) return;
  const at = track(event);
  if (at) drag.value = { ...drag.value, b: at };
}

// Also the handler for lostpointercapture: without it, a capture stolen
// mid-drag would leave the selection rectangle painted over the chart with no
// way to clear it. It fires again right after a normal pointerup, which the
// null check below absorbs.
function onPointerUp() {
  const current = drag.value;
  drag.value = null;
  if (!current) return;
  const chart = chartOf();
  const days = daily.value;
  if (!chart || !days.length) return;
  // getValueForPixel is absolute (it adds the scale's current min), so a drag
  // inside an existing zoom narrows further without any offset arithmetic.
  const toIndex = px => Math.min(Math.max(Math.round(chart.scales.x.getValueForPixel(px) ?? 0), 0), days.length - 1);
  const [lo, hi] = [toIndex(current.a.cx), toIndex(current.b.cx)].sort((x, y) => x - y);
  // One day is a click, not a selection -- and zooming to a single point would
  // leave a chart with nothing to draw a line between.
  if (hi - lo < 1) return;
  zoom.value = { from: days[lo].date, to: days[hi].date };
}

const dragRect = computed(() => {
  if (!drag.value) return null;
  const { a, b } = drag.value;
  return { left: `${Math.min(a.fx, b.fx)}px`, width: `${Math.abs(b.fx - a.fx)}px` };
});
// One bulk-import day can hold most of a contest's submissions, which flattens
// every other day onto the axis. A log scale is the honest way to read both at
// once -- but only while it is labelled as one, so the control stays on screen
// rather than being an invisible default.
const scaleType = ref('logarithmic');
// A log axis has no zero, and on a quiet contest most days are zero: plotted
// literally they fall outside the scale and chart.js drops those segments,
// leaving disconnected dots instead of a curve. Quiet days are pinned to the
// axis floor so the line stays continuous -- the tooltip below still reports
// the real count.
const LOG_FLOOR = 0.9;
const DECADES = [1, 10, 100, 1000, 10000, 100000, 1000000];
const plot = (n) => (scaleType.value === 'logarithmic' ? (n || LOG_FLOOR) : n);
const chartData = computed(() => ({
  labels: daily.value.map(d => d.date),
  datasets: [{
    label: 'Submitted',
    hidden: !shown.value.submitted,
    data: daily.value.map(d => plot(d.count)),
    borderColor: ACCENT,
    backgroundColor: ACCENT,
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
  }, {
    label: 'Judged',
    hidden: !shown.value.judged,
    data: daily.value.map(d => plot(d.judged || 0)),
    borderColor: TEAL,
    backgroundColor: TEAL,
    borderWidth: 2,
    borderDash: [5, 4],
    cubicInterpolationMode: 'monotone',
    // No fill: two stacked translucent areas hide whichever curve is lower,
    // and the comparison between the two lines is the whole point of the panel.
    fill: false,
    pointRadius: 2.5,
    pointHoverRadius: 5,
    pointBackgroundColor: TEAL,
    pointBorderColor: '#ffffff',
    pointBorderWidth: 1.5,
  }],
}));

// Zooming replaces the label set, and chart.js tweens points by *index*, not by
// date: the old index 0 (Aug 9, say) slides across to the new index 0 (Aug 1),
// dragging the whole curve sideways through dates it never had. Remounting on
// the range instead draws the new span clean. Kept off `scaleType` -- swapping
// linear/log keeps the same labels, so that transition is honest.
const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  // This is the zoom transition -- the points travel to their new positions
  // over it. Long enough to read as movement, short enough not to be a wait.
  animation: { duration: 500 },
  // Follows the cursor across the whole column rather than needing a hit on
  // the 2.5px dot itself.
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },   // the .series-switch buttons are the legend
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
        // The real count, never the floor the log scale plots quiet days at.
        label: (ctx) => {
          const day = daily.value[ctx.dataIndex] || {};
          const n = (ctx.datasetIndex === 0 ? day.count : day.judged) ?? 0;
          const noun = ctx.datasetIndex === 0
            ? (n === 1 ? 'submission' : 'submissions')
            : (n === 1 ? 'judgment' : 'judgments');
          return `${n.toLocaleString()} ${noun}`;
        },
      },
    },
  },
  scales: {
    x: {
      ...zoomBounds.value,
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
    y: scaleType.value === 'logarithmic'
      ? {
          type: 'logarithmic',
          min: LOG_FLOOR,
          // A log scale ticks at 2,3,4…9 between every decade, and drawing a
          // gridline for each of them striped the panel with bands of doubled
          // lines. Only the decades get a line; the rest are labelled off too.
          grid: {
            color: ctx => (DECADES.includes(ctx.tick?.value) ? '#eef4f8' : 'transparent'),
          },
          border: { display: false },
          ticks: {
            color: '#47637c',
            font: { size: 11 },
            callback: v => (DECADES.includes(v) ? v.toLocaleString() : ''),
          },
        }
      : {
          beginAtZero: true,
          grid: { color: '#eef4f8' },
          border: { display: false },
          ticks: { color: '#47637c', font: { size: 11 }, precision: 0 },
        },
  },
}));

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

      <section v-if="judgeable" class="progress-panel">
        <div class="progress-head">
          <h2>Judging progress</h2>
          <p>{{ reviewed.toLocaleString() }} of {{ judgeable.toLocaleString() }} judged &middot; {{ progress }}%</p>
        </div>
        <cdx-progress-bar
          :value="progress"
          aria-label="Judging progress"
        />
      </section>

      <section class="chart-panel">
        <div class="chart-head">
          <h2>Submissions and judgments per day</h2>
          <div class="chart-head-right">
            <button v-if="zoom" type="button" class="zoom-reset" @click="zoom = null">
              Reset zoom
            </button>
            <div class="series-switch" role="group" aria-label="Series shown">
              <button
                v-for="s in SERIES"
                :key="s.key"
                type="button"
                :class="{ 'is-off': !shown[s.key] }"
                :aria-pressed="shown[s.key]"
                @click="shown[s.key] = !shown[s.key]"
              >
                <span class="series-swatch" :class="{ 'is-dashed': s.dash }" :style="{ '--swatch': s.color }" />
                {{ s.label }}
              </button>
            </div>
            <div class="scale-switch" role="group" aria-label="Vertical scale">
              <button type="button" :class="{ 'is-active': scaleType === 'linear' }" @click="scaleType = 'linear'">Linear</button>
              <button type="button" :class="{ 'is-active': scaleType === 'logarithmic' }" @click="scaleType = 'logarithmic'">Log</button>
            </div>
          </div>
        </div>
        <div
          v-if="daily.length"
          ref="frameRef"
          class="chart-frame"
          @pointerdown="onPointerDown"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @pointercancel="onPointerUp"
          @lostpointercapture="onPointerUp"
        >
          <Line :data="chartData" :options="chartOptions" aria-label="Articles submitted and judgments made per day" />
          <div v-if="dragRect" class="drag-select" :style="dragRect" />
        </div>
        <p v-if="daily.length" class="chart-hint">
          Drag across the chart to zoom into a date range.
        </p>
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
