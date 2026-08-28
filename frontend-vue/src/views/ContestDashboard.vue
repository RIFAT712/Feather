<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ActivityLog from './ActivityLog.vue';
import { useContestStats } from '../composables/useContestData';

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

const isActive = computed(() => {
  const now = new Date();
  return now >= new Date(props.contest.start_date) && now <= new Date(props.contest.end_date);
});

const timerText = ref("");
let timerInterval;

// Shared across views (dashboard/Timeline Log/Jury Stats all want the same
// /stats data) via vue-query's cache, so navigating between them doesn't
// re-fetch what another view just loaded seconds ago. refetchInterval keeps
// polling every 5s while this view is mounted and authorized -- previously a
// manual setInterval, now the query's own job.
const statsQuery = useContestStats(() => route.params.code, {
  enabled: computed(() => props.roles.is_jury || props.roles.is_owner),
  refetchInterval: 5000,
});
const stats = computed(() => {
  const counts = statsQuery.data.value?.status_counts;
  return counts
    ? { total: counts.total, accepted: counts.accepted, rejected: counts.rejected, pending: counts.pending }
    : { total: 0, accepted: 0, rejected: 0, pending: 0 };
});

const updateTimer = () => {
  const now = new Date();
  const start = new Date(props.contest.start_date);
  const end = new Date(props.contest.end_date);

  if (now < start) {
    const diffDays = Math.ceil((start - now) / (1000 * 60 * 60 * 24));
    timerText.value = `প্রতিযোগিতা শুরু হতে ${diffDays} দিন বাকি`;
  } else if (now > end) {
    timerText.value = "প্রতিযোগিতা শেষ";
  } else {
    const diffMs = end - now;
    const d = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const h = Math.floor((diffMs / (1000 * 60 * 60)) % 24);
    const m = Math.floor((diffMs / 1000 / 60) % 60);
    const s = Math.floor((diffMs / 1000) % 60);
    timerText.value = `${d} দিন ${h} ঘণ্টা ${m} মিনিট ${s} সেকেন্ড সময় বাকি`;
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
        <div class="contest-status-badge" :class="isActive ? 'active' : 'inactive'">
          <svg v-if="isActive" viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><circle cx="8" cy="8" r="8"/></svg>
          <svg v-else viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><rect x="3" y="2" width="4" height="12"/><rect x="9" y="2" width="4" height="12"/></svg>
          {{ isActive ? 'Active' : 'Inactive' }}
        </div>
        <h1 class="hero-title">{{ contest.name }}</h1>
        <p class="hero-dates">
          {{ new Date(contest.start_date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) }}
          &nbsp;→&nbsp;
          {{ new Date(contest.end_date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) }}
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

        <div v-if="(roles.is_jury || roles.is_owner) && stats.total > 0" class="stats-row">
      <div class="stat-card">
        <div class="stat-number">{{ stats.total }}</div>
        <div class="stat-label">Total Submitted</div>
      </div>
      <div class="stat-card accent-green">
        <div class="stat-number">{{ stats.accepted }}</div>
        <div class="stat-label">গৃহীত (Accepted)</div>
      </div>
      <div class="stat-card accent-red">
        <div class="stat-number">{{ stats.rejected }}</div>
        <div class="stat-label">প্রত্যাখ্যাত (Rejected)</div>
      </div>
      <div class="stat-card accent-amber">
        <div class="stat-number">{{ stats.pending }}</div>
        <div class="stat-label">অপেক্ষমাণ (Pending)</div>
      </div>
    </div>

        <div v-if="(roles.is_jury || roles.is_owner)" class="log-section">
      <ActivityLog :contest="contest" :roles="roles" embedded />
    </div>
  </div>
</template>

<style scoped src="../styles/views/ContestDashboard.css"></style>
