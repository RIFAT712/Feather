<script setup>
import { ref, onMounted, onUnmounted, computed, inject } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ActivityLog from './ActivityLog.vue';
import { CdxTable } from '@wikimedia/codex';
import { useContestStats } from '../composables/useContestData';
import { formatDateLong, windowStatus, toDate } from '../utils/datetime';

// roles comes from ContestLayout (the shared parent for every contest route),
// which already fetches /my-role once -- available synchronously here since
// the parent resolves it before this child even mounts, so no loading state
// is needed for it (unlike the old fetch-it-here-too approach).
const props = defineProps({
  contest: { type: Object, default: null },
  roles: { type: Object, default: () => ({ is_jury: false, is_owner: false }) },
});
const route = useRoute();
const router = useRouter();
// "Submissions by User" is open to any signed-in user, not just the jury: the
// endpoints behind it (/submitters and /log?submitted_by=) have no auth
// dependency, and a participant wants to see where their own entries sit.
// Anonymous visitors still get the counts and the jury tally, not this crawl.
const user = inject('user', null);

// The contest window arrives as naive UTC. Parsing it with a bare `new Date()`
// read it as local time, so the Active badge and the countdown below flipped
// six hours off from the dates shown in the same banner.
// Three states, not two: a contest that has not opened yet is "Upcoming", not
// "Inactive". Same vocabulary and class names AdminDashboard already uses.
const STATUS_LABEL = { active: 'Active', upcoming: 'Upcoming', ended: 'Ended' };
const status = computed(() => windowStatus(props.contest.start_date, props.contest.end_date));
const isActive = computed(() => status.value === 'active');

const timerText = ref("");
let timerInterval;

// Shared across views (dashboard/Timeline Log/Jury Stats all want the same
// /stats data) via vue-query's cache, so navigating between them doesn't
// re-fetch what another view just loaded seconds ago. refetchInterval keeps
// polling every 5s while this view is mounted and authorized -- previously a
// manual setInterval, now the query's own job.
// Public: /api/contests/{code}/stats needs no auth, and the counts + jury
// tally are what a logged-out visitor comes to a contest page for. Only the
// jury/owner view keeps polling -- an anonymous reader gets one fetch.
const statsQuery = useContestStats(() => route.params.code, {
  refetchInterval: computed(() => (props.roles.is_jury || props.roles.is_owner) ? 5000 : false),
});
const juryColumns = [
  { id: 'name', label: 'Jury Member', minWidth: '180px' },
  { id: 'total', label: 'Reviewed', textAlign: 'number' },
  { id: 'accepted', label: 'Accepted', textAlign: 'number' },
  { id: 'rejected', label: 'Rejected', textAlign: 'number' },
];
// Every jury member, not just the ones who have already decided something --
// a juror with no reviews yet still belongs in the list of who is judging.
const juryRows = computed(() => {
  const tally = Object.fromEntries((statsQuery.data.value?.jury_stats || []).map(j => [j.name, j]));
  return (props.contest?.juries || []).map(name => tally[name] || { name, total: 0, accepted: 0, rejected: 0 })
    .sort((a, b) => b.total - a.total);
});
const reviewedCount = computed(() => stats.value.accepted + stats.value.rejected);

const stats = computed(() => {
  const counts = statsQuery.data.value?.status_counts;
  return counts
    ? { total: counts.total, accepted: counts.accepted, rejected: counts.rejected, pending: counts.pending }
    : { total: 0, accepted: 0, rejected: 0, pending: 0 };
});

const updateTimer = () => {
  const now = new Date();
  const start = toDate(props.contest.start_date);
  const end = toDate(props.contest.end_date);
  if (!start || !end) return;

  if (now < start) {
    const diffDays = Math.ceil((start - now) / (1000 * 60 * 60 * 24));
    timerText.value = `Starts in ${diffDays} ${diffDays === 1 ? 'day' : 'days'}`;
  } else if (now > end) {
    timerText.value = "Contest ended";
  } else {
    const diffMs = end - now;
    const d = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const h = Math.floor((diffMs / (1000 * 60 * 60)) % 24);
    const m = Math.floor((diffMs / 1000 / 60) % 60);
    const s = Math.floor((diffMs / 1000) % 60);
    timerText.value = `${d}d ${h}h ${m}m ${s}s left`;
  }
};

onMounted(() => {
  updateTimer();
  timerInterval = setInterval(updateTimer, 1000);
});

onUnmounted(() => {
  clearInterval(timerInterval);
});
</script>

<template>
  <div class="dashboard">
    <div class="hero-banner">
      <div class="hero-content">
        <div class="hero-main">
        <div class="contest-status-badge" :class="status">
          <svg v-if="isActive" viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><circle cx="8" cy="8" r="8"/></svg>
          <svg v-else viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><rect x="3" y="2" width="4" height="12"/><rect x="9" y="2" width="4" height="12"/></svg>
          {{ STATUS_LABEL[status] }}
        </div>
        <h1 class="hero-title">{{ contest.name }}</h1>
        <p class="hero-dates">
          {{ formatDateLong(contest.start_date) }}
          &nbsp;→&nbsp;
          {{ formatDateLong(contest.end_date) }}
        </p>
        <div class="hero-actions">
          <button class="action-btn primary" @click="router.push(`/${contest.code}/submit`)">
            Submit Articles
          </button>
          <button v-if="(roles.is_jury || roles.is_owner)" class="action-btn secondary" @click="router.push(`/${contest.code}/jury`)">
            Review Queue
          </button>
          <button v-if="(roles.is_jury || roles.is_owner)" class="action-btn secondary" @click="router.push(`/${contest.code}/jury`)">
            Statistics
          </button>
          <button v-if="roles.is_owner" class="action-btn secondary" @click="router.push(`/${contest.code}/config`)">
            Config
          </button>
        </div>
        </div>
        <aside class="hero-side" aria-label="Contest status details">
          <span class="hero-side-label">Time remaining</span>
          <p class="hero-timer">{{ timerText }}</p>
          <div v-if="contest.juries && contest.juries.length > 0" class="hero-juries">
            <span class="hero-juries-label">Jury members</span>
            <div class="hero-jury-list">
              <span v-for="(jury, index) in contest.juries" :key="jury">
                {{ jury }}<span v-if="index < contest.juries.length - 1">, </span>
              </span>
            </div>
          </div>
        </aside>
      </div>
    </div>

        <div v-if="stats.total > 0" class="stats-row">
      <div class="stat-card">
        <div class="stat-number">{{ stats.total }}</div>
        <div class="stat-label">Total Submitted</div>
      </div>
      <div class="stat-card accent-green">
        <div class="stat-number">{{ stats.accepted }}</div>
        <div class="stat-label">Accepted</div>
      </div>
      <div class="stat-card accent-red">
        <div class="stat-number">{{ stats.rejected }}</div>
        <div class="stat-label">Rejected</div>
      </div>
      <div class="stat-card accent-amber">
        <div class="stat-number">{{ stats.pending }}</div>
        <div class="stat-label">Pending</div>
      </div>
    </div>

        <section v-if="(roles.is_jury || roles.is_owner) && juryRows.length" class="jury-tally">
      <div class="jury-tally-head">
        <h2>Jury tally</h2>
        <p>{{ reviewedCount }} of {{ stats.total }} submissions reviewed</p>
      </div>
      <cdx-table caption="Jury tally" hide-caption :columns="juryColumns" :data="juryRows">
        <template #item-name="{ item }">
          <router-link :to="`/${contest.code}/user/${encodeURIComponent(item)}`" class="jury-tally-name">{{ item }}</router-link>
        </template>
        <template #item-accepted="{ item }"><span :class="item ? 'tally-accepted' : 'tally-zero'">{{ item }}</span></template>
        <template #item-rejected="{ item }"><span :class="item ? 'tally-rejected' : 'tally-zero'">{{ item }}</span></template>
        <template #empty-state>No reviews yet.</template>
      </cdx-table>
    </section>

        <div v-if="user" class="log-section">
      <ActivityLog :contest="contest" :roles="roles" embedded />
    </div>
  </div>
</template>

<style scoped src="../styles/views/ContestDashboard.css"></style>
