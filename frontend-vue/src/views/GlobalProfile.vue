<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { CdxTable, CdxIcon } from '@wikimedia/codex';
import { cdxIconLinkExternal } from '@wikimedia/codex-icons';
import { formatDate as fmtDate, formatDateTime as fmtDateTime } from '../utils/datetime';
import GlobalLoader from '../components/ui/GlobalLoader.vue';

const route = useRoute();
const router = useRouter();
const profile = ref(null);
const isLoading = ref(true);
const error = ref(null);
const expandedParticipated = ref(null);
const expandedJudged = ref(null);

const submissionColumns = [
  { id: 'title', label: 'Article Title', minWidth: '240px' },
  { id: 'status', label: 'Status' },
  { id: 'wiki_creator', label: 'Creator', minWidth: '140px' },
  { id: 'wiki_creation_date', label: 'Created', minWidth: '150px' },
  { id: 'submitted_at', label: 'Submitted', minWidth: '170px' },
];

const reviewColumns = [
  { id: 'article_title', label: 'Article', minWidth: '240px' },
  { id: 'decision', label: 'Decision' },
  { id: 'comment', label: 'Comment', minWidth: '260px' },
  { id: 'reviewed_at', label: 'Reviewed At', minWidth: '170px' },
];

// One contest section is open at a time, but a prolific user's section still
// holds thousands of rows: this endpoint returns every article they have ever
// submitted, across every contest, in a single response (2.3MB for a user with
// ~11k articles). The fetch is unchanged; only the number of rows drawn is.
// Keyed per contest so opening a second one does not inherit the first's
// window, and reset whenever a fresh profile arrives.
const ROW_WINDOW = 100;
const rowWindows = ref({});
const windowFor = (key) => rowWindows.value[key] || ROW_WINDOW;
const visibleRows = (key, rows) => (rows || []).slice(0, windowFor(key));
const hiddenRows = (key, rows) => Math.max((rows || []).length - windowFor(key), 0);
const showMoreRows = (key) => {
  rowWindows.value = { ...rowWindows.value, [key]: windowFor(key) + ROW_WINDOW };
};
watch(profile, () => { rowWindows.value = {}; });

// Same collapsible model as the per-contest profile, and the same reason: a
// contributor with a long history opened straight into a wall of contests.
// The two group headers are the navigation; the choice is remembered per
// browser, shared with nothing else via its own key.
const SECTION_STORAGE_KEY = 'global_profile_sections';
const openSections = ref({ participated: false, judged: false });
try {
  const saved = JSON.parse(localStorage.getItem(SECTION_STORAGE_KEY) || 'null');
  if (saved && typeof saved === 'object') openSections.value = { ...openSections.value, ...saved };
} catch { /* keep the defaults */ }
const isSectionOpen = (id) => openSections.value[id] !== false;
const toggleSection = (id) => {
  openSections.value = { ...openSections.value, [id]: !isSectionOpen(id) };
  try { localStorage.setItem(SECTION_STORAGE_KEY, JSON.stringify(openSections.value)); } catch { /* not persisted */ }
};

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

const formatDate = (d) => fmtDate(d, '—');
const formatDateTime = (d) => fmtDateTime(d, '—');

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

const countByStatus = (articles, status) => articles.filter(a => a.status === status).length;
</script>

<template>
  <div class="user-profile">
    <GlobalLoader v-if="isLoading" label="Loading profile…" />

    <div v-else-if="error" class="status-state error">
      <p>{{ error }}</p>
      <button class="rows-more-btn" @click="fetchProfile">Try again</button>
    </div>

    <div v-else-if="profile" class="profile-content">
      <div class="profile-header">
        <div class="avatar">{{ profile.username.charAt(0).toUpperCase() }}</div>
        <div class="info">
          <p class="page-kicker">Wikimedia contributor</p>
          <h1>{{ profile.username }}</h1>
          <div class="header-meta">
            <span class="role-badge" :class="profile.role">{{ profile.role }}</span>
            <a
              :href="'https://bn.wiktionary.org/wiki/User:' + encodeURIComponent(profile.username)"
              target="_blank"
              class="wiki-link"
            >
              <cdx-icon :icon="cdxIconLinkExternal" size="small" />
              View on wiki
            </a>
          </div>
        </div>
        <div class="stats-grid">
          <div class="profile-metric">
            <div class="stat-value">{{ profile.participated_contests.length }}</div>
            <div class="stat-label">Contests entered</div>
          </div>
          <div class="profile-metric">
            <div class="stat-value">{{ totalSubmissions }}</div>
            <div class="stat-label">Articles submitted</div>
          </div>
          <div class="profile-metric profile-metric--accepted">
            <div class="stat-value">{{ acceptedArticles }}</div>
            <div class="stat-label">Accepted</div>
          </div>
          <div v-if="profile.judged_contests.length" class="profile-metric">
            <div class="stat-value">{{ profile.judged_contests.length }}</div>
            <div class="stat-label">Contests judged</div>
          </div>
          <div v-if="profile.judged_contests.length" class="profile-metric profile-metric--position">
            <div class="stat-value">{{ totalReviews }}</div>
            <div class="stat-label">Reviews given</div>
          </div>
        </div>
      </div>

      <div class="tables-container">
        <!-- Participated ------------------------------------------------- -->
        <div class="table-section" :class="{ 'is-collapsed': !isSectionOpen('participated') }">
          <button
            type="button"
            class="section-heading section-toggle"
            :aria-expanded="isSectionOpen('participated') ? 'true' : 'false'"
            @click="toggleSection('participated')"
          >
            <div>
              <p class="section-kicker">Article history</p>
              <h2>Participated events</h2>
            </div>
            <span class="section-meta">
              <span class="section-count">{{ profile.participated_contests.length }} contests</span>
              <span class="section-chevron" aria-hidden="true">&#9662;</span>
            </span>
          </button>

          <template v-if="isSectionOpen('participated')">
            <p v-if="!profile.participated_contests.length" class="empty-state">
              No contest participations yet.
            </p>
            <div v-else class="contest-list">
              <div
                v-for="contest in profile.participated_contests"
                :key="'p-' + contest.code"
                class="contest-block"
                :class="{ 'is-collapsed': expandedParticipated !== contest.code }"
              >
                <button
                  type="button"
                  class="contest-toggle"
                  :aria-expanded="expandedParticipated === contest.code ? 'true' : 'false'"
                  @click="toggleParticipated(contest.code)"
                >
                  <span class="contest-identity">
                    <span class="contest-name">{{ contest.name }}</span>
                    <code class="contest-code">{{ contest.code }}</code>
                  </span>
                  <span class="contest-meta">
                    <span class="contest-dates">{{ formatDate(contest.start_date) }} – {{ formatDate(contest.end_date) }}</span>
                    <span class="contest-pills">
                      <span v-if="countByStatus(contest.articles, 'accepted')" class="status-badge accepted">{{ countByStatus(contest.articles, 'accepted') }} accepted</span>
                      <span v-if="countByStatus(contest.articles, 'pending')" class="status-badge pending">{{ countByStatus(contest.articles, 'pending') }} pending</span>
                      <span v-if="countByStatus(contest.articles, 'rejected')" class="status-badge rejected">{{ countByStatus(contest.articles, 'rejected') }} rejected</span>
                    </span>
                    <span class="section-count">{{ contest.articles.length }} article{{ contest.articles.length === 1 ? '' : 's' }}</span>
                    <span class="section-chevron" aria-hidden="true">&#9662;</span>
                  </span>
                </button>

                <template v-if="expandedParticipated === contest.code">
                  <div class="contest-actions">
                    <button type="button" class="rows-more-btn" @click.stop="goToContest(contest.code)">Open contest</button>
                  </div>
                  <cdx-table
                    class="profile-table"
                    :caption="`Articles submitted to ${contest.name}`"
                    hide-caption
                    :columns="submissionColumns"
                    :data="visibleRows('sub-' + contest.code, contest.articles)"
                  >
                    <template #item-title="{ item }">
                      <a :href="'https://bn.wiktionary.org/wiki/' + encodeURIComponent(item)" target="_blank" class="title-link">{{ item }}</a>
                    </template>
                    <template #item-status="{ item }">
                      <span class="status-badge" :class="item">{{ item }}</span>
                    </template>
                    <template #item-wiki_creator="{ item }">
                      <span class="muted-value">{{ item || '—' }}</span>
                    </template>
                    <template #item-wiki_creation_date="{ item }">
                      <span class="muted-value">{{ formatDate(item) }}</span>
                    </template>
                    <template #item-submitted_at="{ item }">
                      <span class="muted-value">{{ formatDateTime(item) }}</span>
                    </template>
                    <template #empty-state>No articles submitted yet.</template>
                  </cdx-table>
                  <div v-if="hiddenRows('sub-' + contest.code, contest.articles)" class="rows-more-wrap">
                    <button type="button" class="rows-more-btn" @click="showMoreRows('sub-' + contest.code)">
                      Show 100 more - {{ hiddenRows('sub-' + contest.code, contest.articles).toLocaleString() }} not shown
                    </button>
                  </div>
                </template>
              </div>
            </div>
          </template>
        </div>

        <!-- Judged ------------------------------------------------------- -->
        <div
          v-if="profile.judged_contests.length"
          class="table-section"
          :class="{ 'is-collapsed': !isSectionOpen('judged') }"
        >
          <button
            type="button"
            class="section-heading section-toggle"
            :aria-expanded="isSectionOpen('judged') ? 'true' : 'false'"
            @click="toggleSection('judged')"
          >
            <div>
              <p class="section-kicker">Jury history</p>
              <h2>Judged events</h2>
            </div>
            <span class="section-meta">
              <span class="section-count">{{ profile.judged_contests.length }} contests</span>
              <span class="section-chevron" aria-hidden="true">&#9662;</span>
            </span>
          </button>

          <template v-if="isSectionOpen('judged')">
            <div class="contest-list">
              <div
                v-for="contest in profile.judged_contests"
                :key="'j-' + contest.code"
                class="contest-block"
                :class="{ 'is-collapsed': expandedJudged !== contest.code }"
              >
                <button
                  type="button"
                  class="contest-toggle"
                  :aria-expanded="expandedJudged === contest.code ? 'true' : 'false'"
                  @click="toggleJudged(contest.code)"
                >
                  <span class="contest-identity">
                    <span class="contest-name">{{ contest.name }}</span>
                    <code class="contest-code">{{ contest.code }}</code>
                    <span class="role-badge" :class="contest.role_in_contest || 'jury'">
                      {{ contest.role_in_contest === 'owner' ? 'owner' : 'jury' }}
                    </span>
                  </span>
                  <span class="contest-meta">
                    <span class="contest-dates">{{ formatDate(contest.start_date) }} – {{ formatDate(contest.end_date) }}</span>
                    <span v-if="contest.stats" class="contest-pills">
                      <span class="status-badge accepted">{{ contest.stats.accepted }} accepted</span>
                      <span class="status-badge rejected">{{ contest.stats.rejected }} rejected</span>
                      <span class="decision-badge skipped">{{ contest.stats.skipped }} skipped</span>
                    </span>
                    <span class="section-count">{{ contest.reviews.length }} review{{ contest.reviews.length === 1 ? '' : 's' }}</span>
                    <span class="section-chevron" aria-hidden="true">&#9662;</span>
                  </span>
                </button>

                <template v-if="expandedJudged === contest.code">
                  <div class="contest-actions">
                    <button type="button" class="rows-more-btn" @click.stop="goToContest(contest.code)">Open contest</button>
                  </div>
                  <cdx-table
                    class="profile-table"
                    :caption="`Reviews given in ${contest.name}`"
                    hide-caption
                    :columns="reviewColumns"
                    :data="visibleRows('rev-' + contest.code, contest.reviews)"
                  >
                    <template #item-article_title="{ item }">
                      <a :href="'https://bn.wiktionary.org/wiki/' + encodeURIComponent(item)" target="_blank" class="title-link">{{ item }}</a>
                    </template>
                    <template #item-decision="{ item }">
                      <span class="decision-badge" :class="item">{{ item }}</span>
                    </template>
                    <template #item-comment="{ item }">
                      <span class="comment-cell" :title="item">{{ item || '—' }}</span>
                    </template>
                    <template #item-reviewed_at="{ item }">
                      <span class="muted-value">{{ formatDateTime(item) }}</span>
                    </template>
                    <template #empty-state>No reviews given yet.</template>
                  </cdx-table>
                  <div v-if="hiddenRows('rev-' + contest.code, contest.reviews)" class="rows-more-wrap">
                    <button type="button" class="rows-more-btn" @click="showMoreRows('rev-' + contest.code)">
                      Show 100 more - {{ hiddenRows('rev-' + contest.code, contest.reviews).toLocaleString() }} not shown
                    </button>
                  </div>
                </template>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<!-- The per-contest profile's stylesheet is the design; this page now uses the
     same header, metrics, section headings, badges and table treatment rather
     than a parallel set that drifted into a dark theme of its own. -->
<style scoped src="../styles/views/UserProfile.css"></style>
<style scoped src="../styles/views/GlobalProfile.css"></style>
