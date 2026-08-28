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

<style scoped src="../styles/views/GlobalProfile.css"></style>
