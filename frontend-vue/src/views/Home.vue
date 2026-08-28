<script setup>
import { ref, onMounted, inject, computed } from 'vue';
import { useRouter } from 'vue-router';

const user = inject('user');
const router = useRouter();
const contests = ref([]);
const isLoading = ref(true);
const loadError = ref('');

const fetchContests = async () => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch('/api/contests', { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    contests.value = await res.json();
  } catch (error) {
    console.error('Failed to load contests', error);
    loadError.value = 'Contest list could not be loaded. Please try again.';
  } finally {
    clearTimeout(timeout);
    isLoading.value = false;
  }
};
onMounted(fetchContests);

const accentPalette = [
  { color: '#ffffff', glow: 'rgba(255,255,255,0.1)', label: 'Indigo' },
  { color: '#ffffff', glow: 'rgba(255,255,255,0.1)', label: 'Sky' },
  { color: '#10b981', glow: 'rgba(255,255,255,0.1)', label: 'Emerald' },
  { color: '#ffffff', glow: 'rgba(255,255,255,0.1)', label: 'Amber' },
  { color: '#ffffff', glow: 'rgba(255,255,255,0.1)',  label: 'Red' },
  { color: '#ffffff', glow: 'rgba(255,255,255,0.1)', label: 'Violet' },
];

const getAccent = (i) => accentPalette[i % accentPalette.length];

const isContestActive = (contest) => {
  const now = new Date();
  const startStr = String(contest.start_date);
  const endStr = String(contest.end_date);
  return now >= new Date(startStr + (!startStr.endsWith('Z') ? 'Z' : '')) && now <= new Date(endStr + (!endStr.endsWith('Z') ? 'Z' : ''));
};

const formatDate = (iso) => {
  const isoStr = String(iso);
  return new Date(isoStr + (!isoStr.endsWith('Z') ? 'Z' : '')).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

const greeting = computed(() => {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
});
</script>

<template>
  <div class="home-root">

        <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="bg-orb orb-3"></div>

        <section class="hero">
      <div class="hero-inner">
        <div class="hero-left">
          <div class="hero-greeting-row">
            <span class="greeting-dot"></span>
            <span class="greeting-text">{{ greeting }}</span>
          </div>
          <h1 class="hero-name">{{ user?.wiki_username || user?.username || 'Guest' }}</h1>
          <p class="hero-tagline">Your Feather writing contest hub. Browse active contests below and start contributing.</p>
          <div class="hero-stats">
            <div class="stat-pill">
              <span class="stat-pill__num">{{ contests.length }}</span>
              <span class="stat-pill__label">{{ contests.length === 1 ? 'Contest' : 'Contests' }}</span>
            </div>
            <div class="stat-pill accent-green">
              <span class="stat-pill__num">{{ contests.filter(c => isContestActive(c)).length }}</span>
              <span class="stat-pill__label">Active</span>
            </div>
          </div>
        </div>
        <div class="hero-right">
          <div class="wiki-badge">
            <svg viewBox="0 0 24 24" fill="none" width="28" height="28" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
            </svg>
          </div>
          <router-link v-if="user?.is_admin" to="/admin" class="admin-btn">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M16.24 7.76a6 6 0 0 1 0 8.49"/></svg>
            Admin Panel
          </router-link>
        </div>
      </div>

    </section>

        <section class="contests-section">
      <div class="section-inner">

                <div class="section-header">
          <div class="section-label">
            <span class="section-label__dot"></span>
            Contests
          </div>
        </div>

                <div v-if="isLoading" class="empty-state">
          <div class="empty-icon"><div class="spinner"></div></div>
          <h2 class="empty-title">Loading contests…</h2>
          <p class="empty-msg">Fetching the latest contest list.</p>
        </div>
                <div v-else-if="loadError" class="empty-state">
          <div class="empty-icon">!</div>
          <h2 class="empty-title">Unable to load contests</h2>
          <p class="empty-msg">{{ loadError }}</p>
          <button class="admin-btn" type="button" @click="fetchContests">Try again</button>
        </div>
                <div v-else-if="contests.length === 0" class="empty-state">
          <div class="empty-glow"></div>
          <div class="empty-icon">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
            </svg>
          </div>
          <h2 class="empty-title">No contests yet</h2>
          <p class="empty-msg">There are no active contests right now. Check back soon!</p>
        </div>

                <div v-else class="contest-grid">
          <div
            v-for="(contest, i) in contests"
            :key="contest.code"
            class="contest-card"
            :style="{
              '--accent': getAccent(i).color,
              '--glow': getAccent(i).glow,
            }"
            @click="router.push(`/${contest.code}`)"
          >
                        <div class="card-top-bar"></div>

                        <div class="card-status-badge" :class="isContestActive(contest) ? 'badge--active' : 'badge--ended'">
              <span class="badge-dot"></span>
              {{ isContestActive(contest) ? 'Active' : 'Ended' }}
            </div>

                        <div class="card-content">
              <h2 class="card-title">{{ contest.name }}</h2>
              <div class="card-meta">
                <span class="card-code">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                  {{ contest.code }}
                </span>
                <span class="card-dates">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                  {{ formatDate(contest.start_date) }} – {{ formatDate(contest.end_date) }}
                </span>
              </div>
            </div>

                        <div class="card-footer">
              <span class="card-cta">
                Enter contest
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
              </span>
            </div>

                        <div class="card-hover-glow"></div>
          </div>
        </div>

      </div>
    </section>
  </div>
</template>

<style scoped src="../styles/views/Home.css"></style>
