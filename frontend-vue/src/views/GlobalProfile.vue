<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();
const profile = ref(null);
const isLoading = ref(true);
const error = ref(null);
const activeTab = ref('participated');
const expandedParticipated = ref(null);
const expandedJudged = ref(null);

const fetchProfile = async () => {
  isLoading.value = true;
  error.value = null;
  try {
    const res = await fetch(`/api/users/${route.params.username}/profile`);
    if (!res.ok) {
      if (res.status === 404) throw new Error('User not found.');
      throw new Error('Failed to load profile.');
    }
    profile.value = await res.json();
  } catch (e) {
    error.value = e.message;
  } finally {
    isLoading.value = false;
  }
};
watch(() => route.params.username, fetchProfile);
onMounted(fetchProfile);

const toggleParticipated = (code) => {
  expandedParticipated.value = expandedParticipated.value === code ? null : code;
};
const toggleJudged = (code) => {
  expandedJudged.value = expandedJudged.value === code ? null : code;
};

const goToContest = (code) => router.push(`/${code}`);

const formatDate = (d) => {
  if (!d) return 'N/A';
  const dStr = String(d);
  return new Date(dStr + (!dStr.endsWith('Z') ? 'Z' : '')).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};
const formatDateTime = (d) => {
  if (!d) return 'N/A';
  const dStr = String(d);
  return new Date(dStr + (!dStr.endsWith('Z') ? 'Z' : '')).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
};

const totalSubmissions = computed(() =>
  profile.value ? profile.value.participated_contests.reduce((s, c) => s + c.articles.length, 0) : 0
);
const totalReviews = computed(() =>
  profile.value ? profile.value.judged_contests.reduce((s, c) => s + c.reviews.length, 0) : 0
);
const acceptedArticles = computed(() =>
  profile.value
    ? profile.value.participated_contests.reduce(
        (s, c) => s + c.articles.filter(a => a.status === 'accepted').length, 0
      )
    : 0
);

const accentPalette = [
  { color: '#ffffff', light: 'rgba(255,255,255,0.1)', glow: 'rgba(255,255,255,0.1)' },
  { color: '#ffffff', light: 'rgba(255,255,255,0.1)', glow: 'rgba(255,255,255,0.1)' },
  { color: '#10b981', light: 'rgba(255,255,255,0.1)', glow: 'rgba(255,255,255,0.1)' },
  { color: '#ffffff', light: 'rgba(255,255,255,0.1)', glow: 'rgba(255,255,255,0.1)' },
  { color: '#ffffff', light: 'rgba(255,255,255,0.1)', glow: 'rgba(255,255,255,0.1)' },
  { color: '#ffffff', light: 'rgba(255,255,255,0.1)', glow: 'rgba(255,255,255,0.1)' },
];
const getAccent = (i) => accentPalette[i % accentPalette.length];

const pctAccepted = (contest) => {
  if (!contest.stats || !contest.stats.total) return 0;
  return Math.round((contest.stats.accepted / contest.stats.total) * 100);
};
</script>

<template>
  <div class="gp-page">

        <div v-if="isLoading" class="state-center">
      <div class="spinner-wrap">
        <div class="spinner-ring"></div>
        <span class="spinner-label">Loading profile…</span>
      </div>
    </div>

        <div v-else-if="error" class="state-center">
      <div class="error-box">
        <div class="error-icon">✕</div>
        <p>{{ error }}</p>
        <button class="retry-btn" @click="fetchProfile">Try again</button>
      </div>
    </div>

        <div v-else-if="profile" class="gp-content">

            <div class="hero-card">
        <div class="hero-bg-orb"></div>
        <div class="hero-bg-orb hero-bg-orb-2"></div>

        <div class="hero-left">
          <div class="big-avatar">
            <span>{{ profile.username.charAt(0).toUpperCase() }}</span>
            <div class="avatar-ring-anim"></div>
          </div>
          <div class="hero-info">
            <h1 class="hero-name">{{ profile.username }}</h1>
            <div class="hero-meta">
              <span class="role-badge" :class="profile.role">{{ profile.role }}</span>
              <a
                :href="'https://bn.wiktionary.org/wiki/User:' + encodeURIComponent(profile.username)"
                target="_blank"
                class="wiki-ext-link"
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                View on Wiki
              </a>
            </div>
          </div>
        </div>

                <div class="hero-stats">
          <div class="hero-stat">
            <span class="hs-val">{{ profile.participated_contests.length }}</span>
            <span class="hs-lbl">Contests Entered</span>
          </div>
          <div class="hero-stat-divider"></div>
          <div class="hero-stat">
            <span class="hs-val">{{ totalSubmissions }}</span>
            <span class="hs-lbl">Articles Submitted</span>
          </div>
          <div class="hero-stat-divider"></div>
          <div class="hero-stat">
            <span class="hs-val accepted-val">{{ acceptedArticles }}</span>
            <span class="hs-lbl">Accepted</span>
          </div>
          <div v-if="profile.judged_contests.length" class="hero-stat-divider"></div>
          <div v-if="profile.judged_contests.length" class="hero-stat">
            <span class="hs-val judged-val">{{ profile.judged_contests.length }}</span>
            <span class="hs-lbl">Contests Judged</span>
          </div>
          <div v-if="profile.judged_contests.length" class="hero-stat-divider"></div>
          <div v-if="profile.judged_contests.length" class="hero-stat">
            <span class="hs-val reviews-val">{{ totalReviews }}</span>
            <span class="hs-lbl">Reviews Given</span>
          </div>
        </div>
      </div>

            <div class="tab-bar">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'participated' }"
          @click="activeTab = 'participated'"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          Participated Events
          <span class="tab-count">{{ profile.participated_contests.length }}</span>
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'judged' }"
          @click="activeTab = 'judged'"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          Judged Events
          <span class="tab-count judged-tab-count">{{ profile.judged_contests.length }}</span>
        </button>
        <div class="tab-indicator" :class="activeTab"></div>
      </div>

            <div v-if="activeTab === 'participated'" class="tab-content">
        <div v-if="!profile.participated_contests.length" class="empty-state">
          <div class="empty-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <p>No contest participations yet.</p>
        </div>

        <div v-else class="event-list">
          <div
            v-for="(contest, i) in profile.participated_contests"
            :key="'p-' + contest.code"
            class="event-card"
            :class="{ 'is-expanded': expandedParticipated === contest.code }"
            :style="{ '--accent': getAccent(i).color, '--accent-light': getAccent(i).light, '--accent-glow': getAccent(i).glow }"
          >
                        <div class="ec-header" @click="toggleParticipated(contest.code)">
              <div class="ec-accent-strip"></div>

              <div class="ec-icon" :style="{ background: getAccent(i).light, color: getAccent(i).color }">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              </div>

              <div class="ec-main">
                <div class="ec-title-row">
                  <h3 class="ec-title">{{ contest.name }}</h3>
                  <code class="ec-code">{{ contest.code }}</code>
                </div>
                <div class="ec-meta">
                  <span class="ec-dates">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                    {{ formatDate(contest.start_date) }} – {{ formatDate(contest.end_date) }}
                  </span>
                                    <div class="ec-status-pills">
                    <span v-if="contest.articles.filter(a => a.status === 'accepted').length" class="spill accepted">
                      ✓ {{ contest.articles.filter(a => a.status === 'accepted').length }} accepted
                    </span>
                    <span v-if="contest.articles.filter(a => a.status === 'pending').length" class="spill pending">
                      ◷ {{ contest.articles.filter(a => a.status === 'pending').length }} pending
                    </span>
                    <span v-if="contest.articles.filter(a => a.status === 'rejected').length" class="spill rejected">
                      ✕ {{ contest.articles.filter(a => a.status === 'rejected').length }} rejected
                    </span>
                  </div>
                </div>
              </div>

              <div class="ec-right">
                <div class="ec-article-pill" :style="{ background: getAccent(i).light, color: getAccent(i).color }">
                  {{ contest.articles.length }} article{{ contest.articles.length !== 1 ? 's' : '' }}
                </div>
                <div class="ec-chevron" :class="{ rotated: expandedParticipated === contest.code }">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                </div>
              </div>
            </div>

                        <div class="ec-body-grid" :class="{ 'is-open': expandedParticipated === contest.code }">
              <div class="ec-body-inner">
                <div class="ec-body">
                <div class="ec-body-toolbar">
                  <span class="ec-body-label">Submitted Articles</span>
                  <button class="go-btn" @click.stop="goToContest(contest.code)">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    Open Contest
                  </button>
                </div>

                <div v-if="!contest.articles.length" class="inner-empty">No articles submitted yet.</div>

                <table v-else class="inner-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Article Title</th>
                      <th>Status</th>
                      <th>Creator</th>
                      <th>Created</th>
                      <th>Submitted</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(art, idx) in contest.articles" :key="art.id" class="art-row">
                      <td class="row-num">{{ idx + 1 }}</td>
                      <td>
                        <a
                          :href="'https://bn.wiktionary.org/wiki/' + encodeURIComponent(art.title)"
                          target="_blank"
                          class="title-link"
                        >{{ art.title }}</a>
                      </td>
                      <td><span :class="['status-chip', art.status]">{{ art.status }}</span></td>
                      <td class="muted-cell">{{ art.wiki_creator || '—' }}</td>
                      <td class="muted-cell date-cell">{{ formatDate(art.wiki_creation_date) }}</td>
                      <td class="muted-cell date-cell">{{ formatDateTime(art.submitted_at) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
             </div>
            </div>
          </div>
        </div>
      </div>

            <div v-if="activeTab === 'judged'" class="tab-content">
        <div v-if="!profile.judged_contests.length" class="empty-state">
          <div class="empty-icon judged-empty-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          </div>
          <p>No jury assignments yet.</p>
        </div>

        <div v-else class="event-list">
          <div
            v-for="(contest, i) in profile.judged_contests"
            :key="'j-' + contest.code"
            class="event-card judged-card"
            :class="{ 'is-expanded': expandedJudged === contest.code }"
            :style="{ '--accent': getAccent(i + 2).color, '--accent-light': getAccent(i + 2).light, '--accent-glow': getAccent(i + 2).glow }"
          >
                        <div class="ec-header" @click="toggleJudged(contest.code)">
              <div class="ec-accent-strip"></div>

              <div class="ec-icon" :style="{ background: getAccent(i + 2).light, color: getAccent(i + 2).color }">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              </div>

              <div class="ec-main">
                <div class="ec-title-row">
                  <h3 class="ec-title">{{ contest.name }}</h3>
                  <code class="ec-code">{{ contest.code }}</code>
                                    <span
                    class="role-in-contest-badge"
                    :class="contest.role_in_contest || 'jury'"
                  >
                    <template v-if="contest.role_in_contest === 'owner'">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                      Owner
                    </template>
                    <template v-else>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                      Jury
                    </template>
                  </span>
                </div>
                <div class="ec-meta">
                  <span class="ec-dates">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                    {{ formatDate(contest.start_date) }} – {{ formatDate(contest.end_date) }}
                  </span>
                                    <div v-if="contest.stats" class="jury-mini-pills">
                    <span class="j-pill accepted">✓ {{ contest.stats.accepted }}</span>
                    <span class="j-pill rejected">✕ {{ contest.stats.rejected }}</span>
                    <span class="j-pill skipped">⊘ {{ contest.stats.skipped }}</span>
                    <span class="j-pill total">{{ contest.stats.total }} total</span>
                  </div>
                </div>
              </div>

              <div class="ec-right">
                                <div v-if="contest.stats && contest.stats.total" class="pct-ring">
                  <svg width="44" height="44" viewBox="0 0 44 44">
                    <circle cx="22" cy="22" r="18" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="4"/>
                    <circle
                      cx="22" cy="22" r="18"
                      fill="none"
                      :stroke="getAccent(i + 2).color"
                      stroke-width="4"
                      stroke-linecap="round"
                      :stroke-dasharray="`${pctAccepted(contest) * 1.131} 113.1`"
                      transform="rotate(-90 22 22)"
                      style="transition: stroke-dasharray 0.5s ease;"
                    />
                    <text x="22" y="26" text-anchor="middle" fill="#f1f5f9" font-size="9" font-weight="700" font-family="Inter, sans-serif">
                      {{ pctAccepted(contest) }}%
                    </text>
                  </svg>
                  <span class="pct-label">approved</span>
                </div>
                <div class="ec-chevron" :class="{ rotated: expandedJudged === contest.code }">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                </div>
              </div>
            </div>

                        <div class="ec-body-grid" :class="{ 'is-open': expandedJudged === contest.code }">
              <div class="ec-body-inner">
                <div class="ec-body">
                <div class="ec-body-toolbar">
                  <span class="ec-body-label">Judgment Details</span>
                  <button class="go-btn" @click.stop="goToContest(contest.code)">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    Open Contest
                  </button>
                </div>

                                <div v-if="contest.stats && contest.stats.total" class="stats-bar-wrap">
                  <div class="stats-bar">
                    <div class="bar-seg accepted-seg" :style="{ width: (contest.stats.accepted / contest.stats.total * 100) + '%' }"></div>
                    <div class="bar-seg rejected-seg" :style="{ width: (contest.stats.rejected / contest.stats.total * 100) + '%' }"></div>
                    <div class="bar-seg skipped-seg" :style="{ width: (contest.stats.skipped / contest.stats.total * 100) + '%' }"></div>
                  </div>
                  <div class="stats-bar-labels">
                    <span class="sbl accepted">{{ contest.stats.accepted }} accepted</span>
                    <span class="sbl rejected">{{ contest.stats.rejected }} rejected</span>
                    <span class="sbl skipped">{{ contest.stats.skipped }} skipped</span>
                    <span class="sbl total">{{ contest.stats.total }} total decisions</span>
                  </div>
                </div>

                <div v-if="!contest.reviews.length" class="inner-empty">No reviews given yet.</div>

                <table v-else class="inner-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Article</th>
                      <th>Decision</th>
                      <th>Comment</th>
                      <th>Reviewed At</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(rev, idx) in contest.reviews" :key="idx" class="art-row">
                      <td class="row-num">{{ idx + 1 }}</td>
                      <td>
                        <a
                          :href="'https://bn.wiktionary.org/wiki/' + encodeURIComponent(rev.article_title)"
                          target="_blank"
                          class="title-link"
                        >{{ rev.article_title }}</a>
                      </td>
                      <td><span :class="['status-chip', rev.decision]">{{ rev.decision }}</span></td>
                      <td class="comment-cell" :title="rev.comment">{{ rev.comment || '—' }}</td>
                      <td class="muted-cell date-cell">{{ formatDateTime(rev.reviewed_at) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
             </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Page ── */
.gp-page {
  padding: 32px 48px 80px;
  max-width: 1100px;
  margin: 0 auto;
  color: #e2e8f0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Loading / Error States ── */
.state-center {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 420px;
}
.spinner-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.spinner-ring {
  width: 42px; height: 42px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.spinner-label { color: #475569; font-size: 0.9rem; }

.error-box {
  text-align: center;
  padding: 48px 40px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 20px;
  max-width: 360px;
}
.error-icon {
  width: 52px; height: 52px;
  border-radius: 50%;
  background: rgba(255,255,255,0.1);
  color: #ffffff;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.4rem; font-weight: 700;
  margin: 0 auto 16px;
}
.error-box p { color: #d1d5db; margin: 0 0 20px; }
.retry-btn {
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.1);
  color: #d1d5db;
  padding: 8px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  font-family: inherit;
  transition: background 0.2s;
}
.retry-btn:hover { background: rgba(255,255,255,0.1); }

/* ── Hero Card ── */
.hero-card {
  position: relative;
  background: linear-gradient(135deg, #12152b 0%, #181c3a 60%, #0e1a30 100%);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 24px;
  padding: 36px 40px;
  margin-bottom: 28px;
  overflow: hidden;
  display: flex;
  align-items: center;
  gap: 32px;
  flex-wrap: wrap;
  box-shadow: 0 8px 40px rgba(0,0,0,0.35), 0 0 80px rgba(255,255,255,0.1);
}

.hero-bg-orb {
  position: absolute;
  width: 400px; height: 400px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  top: -150px; right: -80px;
  pointer-events: none;
}
.hero-bg-orb-2 {
  width: 250px; height: 250px;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  top: auto; right: auto;
  bottom: -80px; left: -60px;
}

.hero-left {
  display: flex;
  align-items: center;
  gap: 24px;
  flex: 1;
  min-width: 260px;
}

/* Animated avatar */
.big-avatar {
  position: relative;
  width: 90px; height: 90px;
  flex-shrink: 0;
}
.big-avatar span {
  position: absolute;
  inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 2.6rem;
  font-weight: 800;
  color: #fff;
  border-radius: 50%;
  background: linear-gradient(135deg, #cccccc, #7c3aed, #06b6d4);
  z-index: 1;
  box-shadow: 0 8px 28px rgba(255,255,255,0.1);
}
.avatar-ring-anim {
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  background: conic-gradient(from 0deg, #22c55e, #2563eb, #06b6d4, #818cf8);
  opacity: 0.4;
  animation: rotate-ring 4s linear infinite;
}
@keyframes rotate-ring { to { transform: rotate(360deg); } }

.hero-info { display: flex; flex-direction: column; gap: 8px; }
.hero-name {
  margin: 0;
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  background: linear-gradient(135deg, #fff 0%, #e5e7eb 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-meta {
  display: flex; align-items: center; gap: 10px;
  flex-wrap: wrap;
}
.role-badge {
  display: inline-block;
  padding: 4px 14px;
  border-radius: 20px;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
}
.role-badge.owner { background: linear-gradient(90deg,#f59e0b,#d97706); color: #111111; }
.role-badge.participant { background: rgba(255,255,255,0.1); color: #e5e7eb; border: 1px solid rgba(255,255,255,0.1); }
.wiki-ext-link {
  display: inline-flex; align-items: center; gap: 5px;
  color: #475569; font-size: 0.8rem; text-decoration: none;
  transition: color 0.2s;
}
.wiki-ext-link:hover { color: #e5e7eb; }

/* Hero stats */
.hero-stats {
  display: flex;
  align-items: center;
  gap: 0;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 16px;
  padding: 0 4px;
  flex-shrink: 0;
}
.hero-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 18px 24px;
  gap: 4px;
}
.hero-stat-divider {
  width: 1px;
  height: 36px;
  background: rgba(255,255,255,0.07);
}
.hs-val {
  font-size: 1.6rem;
  font-weight: 800;
  color: #f1f5f9;
  line-height: 1;
}
.hs-val.accepted-val { color: #d1d5db; }
.hs-val.judged-val { color: #818cf8; }
.hs-val.reviews-val { color: #d1d5db; }
.hs-lbl {
  font-size: 0.68rem;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  white-space: nowrap;
}

/* ── Tab Bar ── */
.tab-bar {
  position: relative;
  display: flex;
  gap: 4px;
  background: #0e1120;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 14px;
  padding: 6px;
  margin-bottom: 24px;
  width: fit-content;
}
.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: color 0.2s, background 0.2s;
  position: relative;
  z-index: 1;
}
.tab-btn:hover { color: #94a3b8; }
.tab-btn.active {
  background: rgba(255,255,255,0.1);
  color: #e5e7eb;
}
.tab-count {
  background: rgba(255,255,255,0.1);
  color: #64748b;
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 0.72rem;
  font-weight: 700;
  min-width: 22px;
  text-align: center;
}
.tab-btn.active .tab-count {
  background: rgba(255,255,255,0.1);
  color: #e5e7eb;
}
.judged-tab-count { }

/* ── Tab Content ── */
.tab-content { display: flex; flex-direction: column; gap: 0; }

/* ── Empty State ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 64px 32px;
  background: #0e1120;
  border: 1px dashed rgba(255,255,255,0.08);
  border-radius: 20px;
  color: #475569;
}
.empty-icon {
  width: 64px; height: 64px;
  border-radius: 16px;
  background: rgba(255,255,255,0.1);
  color: #cccccc;
  display: flex; align-items: center; justify-content: center;
}
.judged-empty-icon {
  background: rgba(255,255,255,0.1);
  color: #10b981;
}
.empty-state p { margin: 0; font-style: italic; font-size: 0.95rem; }

/* ── Event List ── */
.event-list { display: flex; flex-direction: column; gap: 10px; }

/* ── Event Card ── */
.event-card {
  background: #0e1120;
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 18px;
  overflow: hidden;
  transition: border-color 0.25s, box-shadow 0.25s;
}
.event-card:hover { border-color: rgba(255,255,255,0.1); }
.event-card.is-expanded {
  border-color: color-mix(in srgb, var(--accent) 35%, transparent);
  box-shadow: 0 8px 36px rgba(0,0,0,0.3), 0 0 28px var(--accent-glow);
}

/* Card Header */
.ec-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  cursor: pointer;
  position: relative;
  transition: background 0.2s;
  user-select: none;
}
.ec-header:hover { background: rgba(255,255,255,0.015); }

.ec-accent-strip {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: var(--accent);
  opacity: 0.5;
  transition: opacity 0.2s, width 0.2s;
}
.is-expanded .ec-accent-strip { opacity: 1; width: 4px; }

.ec-icon {
  width: 42px; height: 42px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  transition: transform 0.2s;
}
.ec-header:hover .ec-icon { transform: scale(1.05); }

.ec-main { flex: 1; min-width: 0; }
.ec-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.ec-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: #f1f5f9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ec-code {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.7rem;
  color: #475569;
  background: rgba(255,255,255,0.05);
  padding: 2px 8px;
  border-radius: 6px;
  white-space: nowrap;
}
.ec-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.ec-dates {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.72rem;
  color: #475569;
  font-weight: 500;
  white-space: nowrap;
}

/* Mini status pills on header */
.ec-status-pills {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.spill {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 8px;
  white-space: nowrap;
}
.spill.accepted { background: rgba(34,197,94,0.12); color: #22c55e; }
.spill.pending { background: rgba(255,255,255,0.1); color: #d1d5db; }
.spill.rejected { background: rgba(239,68,68,0.12); color: #ef4444; }

/* Jury mini pills */
.jury-mini-pills {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.j-pill {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 8px;
  white-space: nowrap;
}
.j-pill.accepted { background: rgba(34,197,94,0.12); color: #22c55e; }
.j-pill.rejected { background: rgba(239,68,68,0.12); color: #ef4444; }
.j-pill.skipped { background: rgba(148,163,184,0.08); color: #94a3b8; }
.j-pill.total { background: rgba(255,255,255,0.06); color: #64748b; }

/* Role in contest badge */
.role-in-contest-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 9px;
  border-radius: 8px;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  white-space: nowrap;
  flex-shrink: 0;
}
.role-in-contest-badge.owner {
  background: linear-gradient(90deg, rgba(255,255,255,0.1), rgba(251,191,36,0.18));
  color: #d1d5db;
  border: 1px solid rgba(255,255,255,0.1);
}
.role-in-contest-badge.jury {
  background: rgba(255,255,255,0.1);
  color: #e5e7eb;
  border: 1px solid rgba(255,255,255,0.1);
}

/* Right side of header */
.ec-right {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-shrink: 0;
}
.ec-article-pill {
  padding: 5px 14px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 700;
  white-space: nowrap;
}
.ec-chevron {
  color: #475569;
  display: flex;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.2s;
}
.ec-chevron.rotated {
  transform: rotate(180deg);
  color: var(--accent);
}

/* Pct ring */
.pct-ring {
  display: flex; flex-direction: column; align-items: center; gap: 3px;
}
.pct-label {
  font-size: 0.6rem; color: #475569; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
}

/* ── Expanded Body ── */
.ec-body-grid {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.ec-body-grid.is-open {
  grid-template-rows: 1fr;
}
.ec-body-inner {
  overflow: hidden;
}
.ec-body {
  border-top: 1px solid rgba(255,255,255,0.05);
  padding: 0 24px 24px;
}
.ec-body-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0 14px;
}
.ec-body-label {
  font-size: 0.78rem;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.go-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.1);
  color: #e5e7eb;
  padding: 7px 14px;
  border-radius: 9px;
  font-size: 0.78rem; font-weight: 600;
  cursor: pointer; font-family: inherit;
  transition: background 0.2s, border-color 0.2s;
}
.go-btn:hover { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.1); }

.inner-empty {
  padding: 24px;
  text-align: center;
  color: #475569;
  font-style: italic;
  font-size: 0.88rem;
}

/* Stats bar */
.stats-bar-wrap { margin-bottom: 16px; }
.stats-bar {
  height: 6px;
  border-radius: 4px;
  background: rgba(255,255,255,0.05);
  display: flex;
  overflow: hidden;
  margin-bottom: 8px;
}
.bar-seg { height: 100%; transition: width 0.4s ease; }
.accepted-seg { background: #22c55e; }
.rejected-seg { background: #ef4444; }
.skipped-seg { background: #64748b; }
.stats-bar-labels { display: flex; gap: 16px; flex-wrap: wrap; }
.sbl {
  font-size: 0.72rem; font-weight: 600;
}
.sbl.accepted { color: #22c55e; }
.sbl.rejected { color: #ef4444; }
.sbl.skipped { color: #94a3b8; }
.sbl.total { color: #475569; }

/* ── Inner Table ── */
.inner-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.875rem;
}
.inner-table th {
  padding: 10px 14px;
  background: rgba(15,23,42,0.5);
  color: #475569;
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.inner-table td {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.inner-table tbody tr:last-child td { border-bottom: none; }
.art-row { transition: background 0.15s; }
.art-row:hover { background: rgba(255,255,255,0.02); }

.row-num {
  color: #333333;
  font-size: 0.75rem;
  font-weight: 600;
  width: 36px;
  text-align: center;
}

.title-link {
  color: #d1d5db;
  text-decoration: none;
  font-weight: 500;
}
.title-link:hover { text-decoration: underline; }

.status-chip {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: capitalize;
}
.status-chip.accepted { background: rgba(34,197,94,0.15); color: #22c55e; }
.status-chip.rejected { background: rgba(239,68,68,0.15); color: #ef4444; }
.status-chip.pending { background: rgba(255,255,255,0.1); color: #d1d5db; }
.status-chip.skipped { background: rgba(148,163,184,0.1); color: #cbd5e1; }

.muted-cell { color: #94a3b8; }
.date-cell { font-size: 0.8rem; color: #475569; white-space: nowrap; }
.comment-cell {
  max-width: 220px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #94a3b8;
}



/* ── Responsive ── */
@media (max-width: 768px) {
  .gp-page { padding: 16px 16px 64px; }
  .hero-card { flex-direction: column; padding: 28px 24px; gap: 24px; }
  .hero-stats { width: 100%; flex-wrap: wrap; justify-content: center; }
  .hero-stat { padding: 12px 16px; }
  .hero-name { font-size: 1.6rem; }
  .big-avatar { width: 72px; height: 72px; }
  .tab-bar { width: 100%; }
  .tab-btn { flex: 1; justify-content: center; padding: 10px 12px; font-size: 0.82rem; }
  .ec-header { flex-wrap: wrap; gap: 12px; }
  .ec-right { width: 100%; justify-content: space-between; }
  .inner-table { font-size: 0.8rem; }
  .inner-table th, .inner-table td { padding: 8px 10px; }
}
</style>
