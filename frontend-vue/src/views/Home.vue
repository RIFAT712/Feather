<script setup>
import { ref, onMounted, inject, computed } from 'vue';
import { useRouter } from 'vue-router';

const user = inject('user');
const router = useRouter();
const contests = ref([]);

const fetchContests = async () => {
  const res = await fetch('/api/contests');
  if (res.ok) contests.value = await res.json();
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

    <!-- ── Ambient background orbs ── -->
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="bg-orb orb-3"></div>

    <!-- ── Hero ── -->
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

      <!-- Animated wave divider -->
      <div class="hero-wave">
        <svg viewBox="0 0 1440 60" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M0,30 C360,60 1080,0 1440,30 L1440,60 L0,60 Z" fill="#0d0f1c"/>
        </svg>
      </div>
    </section>

    <!-- ── Contests Section ── -->
    <section class="contests-section">
      <div class="section-inner">

        <!-- Section header -->
        <div class="section-header">
          <div class="section-label">
            <span class="section-label__dot"></span>
            Contests
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="contests.length === 0" class="empty-state">
          <div class="empty-glow"></div>
          <div class="empty-icon">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
            </svg>
          </div>
          <h2 class="empty-title">No contests yet</h2>
          <p class="empty-msg">There are no active contests right now. Check back soon!</p>
        </div>

        <!-- Contest Grid -->
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
            <!-- Top glow accent -->
            <div class="card-top-bar"></div>

            <!-- Status badge -->
            <div class="card-status-badge" :class="isContestActive(contest) ? 'badge--active' : 'badge--ended'">
              <span class="badge-dot"></span>
              {{ isContestActive(contest) ? 'Active' : 'Ended' }}
            </div>

            <!-- Card body -->
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

            <!-- Card footer CTA -->
            <div class="card-footer">
              <span class="card-cta">
                Enter contest
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
              </span>
            </div>

            <!-- Hover glow overlay -->
            <div class="card-hover-glow"></div>
          </div>
        </div>

      </div>
    </section>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Root ── */
.home-root {
  min-height: 100%;
  background: #0d0f1c;
  font-family: 'Inter', 'Segoe UI', sans-serif;
  position: relative;
  overflow-x: hidden;
}

/* ── Ambient orbs ── */
.bg-orb {
  position: fixed;
  border-radius: 50%;
  filter: blur(120px);
  pointer-events: none;
  z-index: 0;
  animation: drift 12s ease-in-out infinite alternate;
}
.orb-1 {
  width: 600px; height: 600px;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  top: -200px; left: -200px;
  animation-delay: 0s;
}
.orb-2 {
  width: 500px; height: 500px;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  top: 100px; right: -150px;
  animation-delay: -4s;
}
.orb-3 {
  width: 400px; height: 400px;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  bottom: 0; left: 40%;
  animation-delay: -8s;
}
@keyframes drift {
  from { transform: translate(0, 0) scale(1); }
  to   { transform: translate(30px, 20px) scale(1.05); }
}

/* ── Hero ── */
.hero {
  position: relative;
  z-index: 1;
  padding: 72px 32px 0;
  background: linear-gradient(160deg,
    #12142a 0%,
    #0f1a3a 35%,
    #0d1e3f 60%,
    #0d0f1c 100%
  );
  overflow: hidden;
}

/* Subtle grid lines on hero */
.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
  background-size: 48px 48px;
  pointer-events: none;
}

.hero-inner {
  position: relative;
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 32px;
  flex-wrap: wrap;
  padding-bottom: 64px;
}

.hero-left { flex: 1; min-width: 260px; }

.hero-greeting-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.greeting-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 0 10px #ffffff;
  animation: pulse-dot 2s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { box-shadow: 0 0 6px #ffffff; opacity: 1; }
  50%       { box-shadow: 0 0 16px #818cf8; opacity: 0.7; }
}
.greeting-text {
  font-size: 0.85rem;
  font-weight: 600;
  color: #818cf8;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.hero-name {
  margin: 0 0 12px;
  font-size: clamp(2rem, 5vw, 3.2rem);
  font-weight: 900;
  letter-spacing: -0.03em;
  line-height: 1.1;
  color: #fff;
  background: linear-gradient(135deg, #ffffff 0%, #e5e7eb 60%, #818cf8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-tagline {
  margin: 0 0 28px;
  font-size: 1rem;
  color: rgba(255,255,255,0.45);
  line-height: 1.65;
  max-width: 480px;
}

.hero-stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.stat-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 999px;
  padding: 6px 16px 6px 12px;
  backdrop-filter: blur(8px);
}
.stat-pill.accent-green { border-color: rgba(255,255,255,0.1); background: rgba(255,255,255,0.1); }
.stat-pill__num {
  font-size: 1.1rem;
  font-weight: 800;
  color: #fff;
  line-height: 1;
}
.stat-pill.accent-green .stat-pill__num { color: #d1d5db; }
.stat-pill__label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255,255,255,0.4);
}
.stat-pill.accent-green .stat-pill__label { color: rgba(74,222,128,0.6); }

/* Hero right */
.hero-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 16px;
  padding-top: 8px;
}
.wiki-badge {
  width: 72px; height: 72px;
  border-radius: 20px;
  background: linear-gradient(135deg, #cccccc 0%, #7c3aed 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 8px 32px rgba(255,255,255,0.1), 0 0 0 1px rgba(255,255,255,0.1) inset;
  animation: float 4s ease-in-out infinite;
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50%       { transform: translateY(-8px); }
}

.admin-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: rgba(255,255,255,0.07);
  border: 1px solid rgba(255,255,255,0.14);
  color: rgba(255,255,255,0.8);
  text-decoration: none;
  padding: 9px 18px;
  border-radius: 10px;
  font-size: 0.82rem;
  font-weight: 600;
  backdrop-filter: blur(8px);
  transition: background 0.2s, border-color 0.2s, color 0.2s;
  white-space: nowrap;
}
.admin-btn:hover {
  background: rgba(255,255,255,0.13);
  border-color: rgba(255,255,255,0.28);
  color: #fff;
}

/* Wave divider */
.hero-wave {
  position: relative;
  height: 60px;
  margin-top: -1px;
  margin-left: -32px;
  margin-right: -32px;
  width: calc(100% + 64px);
}
.hero-wave svg {
  width: 100%; height: 100%;
  display: block;
}

/* ── Contests Section ── */
.contests-section {
  position: relative;
  z-index: 1;
  background: #0d0f1c;
  padding-bottom: 64px;
}
.section-inner {
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 32px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: rgba(255,255,255,0.3);
}
.section-label__dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #ffffff;
}

/* ── Empty State ── */
.empty-state {
  position: relative;
  text-align: center;
  padding: 100px 24px;
  color: #64748b;
}
.empty-glow {
  position: absolute;
  width: 400px; height: 400px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
}
.empty-icon {
  width: 80px; height: 80px;
  border-radius: 24px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #818cf8;
  margin: 0 auto 24px;
  position: relative;
}
.empty-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #e2e8f0;
  margin: 0 0 10px;
}
.empty-msg {
  font-size: 0.95rem;
  margin: 0;
  color: #475569;
  max-width: 320px;
  margin: 0 auto;
  line-height: 1.6;
}

/* ── Contest Grid ── */
.contest-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

/* ── Contest Card ── */
.contest-card {
  position: relative;
  background: #12141f;
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 20px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.22s ease, border-color 0.22s ease;
  display: flex;
  flex-direction: column;
}
.contest-card:hover {
  transform: translateY(-6px) scale(1.01);
  border-color: rgba(255,255,255,0.12);
  box-shadow:
    0 20px 60px rgba(0,0,0,0.5),
    0 0 0 1px rgba(255,255,255,0.06),
    0 0 40px var(--glow, rgba(255,255,255,0.1));
}
.contest-card:hover .card-hover-glow {
  opacity: 1;
}
.contest-card:hover .card-cta {
  gap: 10px;
  color: var(--accent, #ffffff);
}

/* Top accent bar */
.card-top-bar {
  height: 3px;
  background: linear-gradient(90deg, var(--accent, #ffffff), transparent);
  flex-shrink: 0;
}

/* Hover glow overlay */
.card-hover-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at 50% 0%, var(--glow, rgba(255,255,255,0.1)) 0%, transparent 70%);
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}

/* Status badge */
.card-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  width: fit-content;
  margin: 16px 20px 0;
}
.badge--active {
  background: rgba(255,255,255,0.1);
  color: #d1d5db;
  border: 1px solid rgba(255,255,255,0.1);
}
.badge--ended {
  background: rgba(255,255,255,0.05);
  color: rgba(255,255,255,0.3);
  border: 1px solid rgba(255,255,255,0.08);
}
.badge-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.badge--active .badge-dot {
  animation: pulse-dot 2s ease-in-out infinite;
  box-shadow: 0 0 6px currentColor;
}

/* Card content */
.card-content {
  padding: 16px 20px 14px;
  flex: 1;
}
.card-title {
  font-size: 1.2rem;
  font-weight: 800;
  color: #f1f5f9;
  margin: 0 0 12px;
  line-height: 1.3;
  letter-spacing: -0.01em;
}
.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.card-code,
.card-dates {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.73rem;
  color: rgba(255,255,255,0.35);
  font-weight: 500;
}
.card-code { font-family: 'JetBrains Mono', 'Fira Code', monospace; }

/* Card footer */
.card-footer {
  padding: 12px 20px 18px;
  border-top: 1px solid rgba(255,255,255,0.05);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-cta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  font-weight: 700;
  color: rgba(255,255,255,0.4);
  transition: color 0.2s, gap 0.2s;
  letter-spacing: 0.01em;
}
</style>
