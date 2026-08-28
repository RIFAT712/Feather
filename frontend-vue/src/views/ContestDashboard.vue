<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ActivityLog from './ActivityLog.vue';
import { getCachedStats, setCachedStats } from '../utils/contestDataCache';

const props = defineProps(['contest']);
const route = useRoute();
const router = useRouter();

const roles = ref({ is_jury: false, is_owner: false });
const isLoadingRoles = ref(true);
const stats = ref({ total: 0, accepted: 0, rejected: 0, pending: 0 });

const isActive = computed(() => {
  const now = new Date();
  return now >= new Date(props.contest.start_date) && now <= new Date(props.contest.end_date);
});

const timerText = ref("");
let timerInterval;
let statsInterval;

// Counts only — avoids re-downloading every article/review on the contest just
// to show four numbers, which used to be re-fetched in full every 5 seconds.
const applyStats = (data) => {
  stats.value = {
    total: data.status_counts.total,
    accepted: data.status_counts.accepted,
    rejected: data.status_counts.rejected,
    pending: data.status_counts.pending,
  };
};

// Shared across views (dashboard/Timeline Log/Jury Stats all want the same
// /stats data) so navigating between them doesn't re-fetch what another view
// just loaded seconds ago. Cached value renders instantly while a fresh fetch
// still runs underneath to catch up-to-the-moment counts and feed the poll below.
const fetchContestStats = async () => {
  const cached = getCachedStats(route.params.code);
  if (cached) applyStats(cached);
  const response = await fetch(`/api/contests/${route.params.code}/stats`);
  if (response.ok) {
    const data = await response.json();
    setCachedStats(route.params.code, data);
    applyStats(data);
  }
};

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
  const loadDashboard = async () => {
    try {
      const roleResponse = await fetch(`/api/contests/${route.params.code}/my-role`);
      if (roleResponse.ok) roles.value = await roleResponse.json();
      isLoadingRoles.value = false;
      if (roles.value.is_jury || roles.value.is_owner) {
        await fetchContestStats();
        statsInterval = setInterval(() => {
          fetchContestStats().catch(error => console.error('Failed to refresh contest stats', error));
        }, 5000);
      }
    } catch (error) {
      isLoadingRoles.value = false;
      console.error('Failed to load contest dashboard', error);
    }
  };
  loadDashboard();
  
  updateTimer();
  timerInterval = setInterval(updateTimer, 1000);
});

onUnmounted(() => {
  clearInterval(timerInterval);
  clearInterval(statsInterval);
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
          <button v-if="!isLoadingRoles && (roles.is_jury || roles.is_owner)" class="action-btn secondary" @click="router.push(`/${contest.code}/jury`)">
            Review Queue
          </button>
          <button v-if="!isLoadingRoles && (roles.is_jury || roles.is_owner)" class="action-btn secondary" @click="router.push(`/${contest.code}/jury`)">
            Statistics
          </button>
          <button v-if="!isLoadingRoles && roles.is_owner" class="action-btn secondary" @click="router.push(`/${contest.code}/config`)">
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

        <div v-if="!isLoadingRoles && (roles.is_jury || roles.is_owner) && stats.total > 0" class="stats-row">
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

        <div v-if="!isLoadingRoles && (roles.is_jury || roles.is_owner)" class="log-section">
      <ActivityLog :contest="contest" />
    </div>
  </div>
</template>

<style scoped src="../styles/views/ContestDashboard.css"></style>
