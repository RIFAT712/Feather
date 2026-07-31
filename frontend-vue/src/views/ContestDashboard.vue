<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ActivityLog from './ActivityLog.vue';

const props = defineProps(['contest']);
const route = useRoute();
const router = useRouter();

const roles = ref({ is_jury: false, is_owner: false });
const isLoadingRoles = ref(true);
const log = ref([]);

const isActive = computed(() => {
  const now = new Date();
  return now >= new Date(props.contest.start_date) && now <= new Date(props.contest.end_date);
});

const stats = computed(() => {
  const total = log.value.length;
  const accepted = log.value.filter(a => a.status === 'accepted').length;
  const rejected = log.value.filter(a => a.status === 'rejected').length;
  const pending = log.value.filter(a => a.status === 'pending').length;
  return { total, accepted, rejected, pending };
});

const timerText = ref("");
let timerInterval;

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
  try {
    fetch(`/api/contests/${route.params.code}/my-role`)
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data) roles.value = data; isLoadingRoles.value = false; 
        if (roles.value.is_jury || roles.value.is_owner) {
          fetch(`/api/contests/${route.params.code}/log`)
            .then(res => res.ok ? res.json() : null)
            .then(data => { if (data) log.value = data; });
        }
      });
  } catch(e) {}
  
  updateTimer();
  timerInterval = setInterval(updateTimer, 1000);
});

import { onUnmounted } from 'vue';
onUnmounted(() => {
  clearInterval(timerInterval);
});
</script>

<template>
  <div class="dashboard">
    <!-- Hero Banner -->
    <div class="hero-banner">
      <div class="hero-content">
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
        <p class="hero-timer" style="font-weight: bold; font-size: 1.1rem; margin-bottom: 12px; color: #d1d5db;">
          {{ timerText }}
        </p>
        <p v-if="contest.juries && contest.juries.length > 0" class="hero-juries" style="color: rgba(255,255,255,0.7); font-size: 0.9rem; margin-bottom: 24px;">
          <strong>Jury Members:</strong> 
          <span v-for="(jury, index) in contest.juries" :key="jury">
            {{ jury }}<span v-if="index < contest.juries.length - 1">, </span>
          </span>
        </p>
        <div class="hero-actions">
          <button class="action-btn primary" @click="router.push(`/${contest.code}/submit`)">
            Submit Articles
          </button>
          <button v-if="!isLoadingRoles && (roles.is_jury || roles.is_owner)" class="action-btn secondary" @click="router.push(`/${contest.code}/jury`)">
            Review Queue
          </button>
          <button v-if="!isLoadingRoles && (roles.is_jury || roles.is_owner)" class="action-btn secondary" @click="router.push(`/${contest.code}/jury-stats`)">
            Statistics
          </button>
          <button v-if="!isLoadingRoles && roles.is_owner" class="action-btn secondary" @click="router.push(`/${contest.code}/config`)">
            Config
          </button>
        </div>
      </div>
    </div>

    <!-- Stats Cards (jury/owner only) -->
    <div v-if="!isLoadingRoles && (roles.is_jury || roles.is_owner) && log.length > 0" class="stats-row">
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

    <!-- Activity Log (jury/owner only) -->
    <div v-if="!isLoadingRoles && (roles.is_jury || roles.is_owner)" class="log-section">
      <ActivityLog :contest="contest" />
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* Hero */
.hero-banner {
  background: #111111;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  padding: 48px 32px;
  position: relative;
  overflow: hidden;
}
.hero-banner::before {
  content: '';
  position: absolute;
  inset: 0;
  background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
  pointer-events: none;
}
.hero-content {
  position: relative;
  max-width: 700px;
}
.contest-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  padding: 4px 12px;
  border-radius: 20px;
  margin-bottom: 16px;
}
.contest-status-badge.active { background: rgba(255,255,255,0.1); color: #d1d5db; border: 1px solid rgba(255,255,255,0.1); }
.contest-status-badge.inactive { background: rgba(107,114,128,0.2); color: #9ca3af; border: 1px solid rgba(107,114,128,0.3); }
.hero-title {
  margin: 0 0 10px 0;
  font-size: 2.2rem;
  font-weight: 800;
  color: #ffffff;
  font-family: 'Linux Libertine', Georgia, Times, serif;
  line-height: 1.2;
}
.hero-dates {
  margin: 0 0 28px 0;
  color: rgba(255,255,255,0.55);
  font-size: 0.9rem;
}
.hero-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.action-btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 6px;
}
.action-btn.primary {
  background: #2563eb;
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(37,99,235,0.35);
}
.action-btn.primary:hover { background: #1d4ed8; transform: translateY(-1px); }
.action-btn.secondary {
  background: rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.85);
  border: 1px solid rgba(255,255,255,0.2);
}
.action-btn.secondary:hover { background: rgba(255,255,255,0.18); }

/* Stats */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-bottom: 1px solid rgba(255,255,255,0.07);
  background: #111111;
}
.stat-card {
  padding: 20px 24px;
  border-right: 1px solid rgba(255,255,255,0.07);
  position: relative;
}
.stat-card:last-child { border-right: none; }
.stat-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: rgba(255,255,255,0.08);
}
.stat-card.accent-green::before { background: #22c55e; }
.stat-card.accent-red::before { background: #ef4444; }
.stat-card.accent-amber::before { background: #f59e0b; }
.stat-number {
  font-size: 2rem;
  font-weight: 800;
  color: #e2e8f0;
  line-height: 1;
  margin-bottom: 4px;
}
.stat-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #64748b;
}

/* Log */
.log-section {
  flex: 1;
}

@media (max-width: 768px) {
  .hero-banner { padding: 28px 20px; }
  .hero-title { font-size: 1.6rem; }
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .stat-card { padding: 14px 16px; border-bottom: 1px solid rgba(255,255,255,0.07); }
}
@media (max-width: 480px) {
  .stats-row { grid-template-columns: 1fr; }
  .hero-actions { flex-direction: column; }
  .action-btn { width: 100%; justify-content: center; }
}
</style>
