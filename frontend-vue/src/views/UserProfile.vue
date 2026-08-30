<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import { useRoute } from 'vue-router';
import { CdxTable } from '@wikimedia/codex';
import GlobalLoader from '../components/ui/GlobalLoader.vue';
import { formatDateTime as fmtDateTime } from '../utils/datetime';

const route = useRoute();
const profile = ref(null);
const isLoading = ref(true);
const error = ref(null);
const submissionSort = ref({});
const competitionPosition = ref(null);
const showScrollTop = ref(false);
const submissionColumns = [
  { id: 'title', label: 'Article', allowSort: true, minWidth: '220px' },
  { id: 'status', label: 'Status', allowSort: true },
  { id: 'jury', label: 'Jury', allowSort: true, minWidth: '160px' },
  { id: 'comment', label: 'Judgment comment', allowSort: true, minWidth: '250px' },
  { id: 'submitted_at', label: 'Submitted At', allowSort: true, minWidth: '170px' }
];

const updateSubmissionSort = (sort) => { submissionSort.value = sort; };

const articleStats = computed(() => {
  const submissions = profile.value?.submissions || [];
  return {
    total: submissions.length,
    accepted: submissions.filter((submission) => submission.status === 'accepted').length,
    rejected: submissions.filter((submission) => submission.status === 'rejected').length,
  };
});

const sortedSubmissions = computed(() => {
  const submissions = [...(profile.value?.submissions || [])];
  const [key, direction] = Object.entries(submissionSort.value)[0] || [];
  if (!key || direction === 'none') return submissions;
  const valueFor = (submission) => {
    if (key === 'jury') return (submission.reviews || []).map((review) => review.jury).join(', ');
    if (key === 'comment') return (submission.reviews || []).map((review) => review.comment || '').join(' ');
    return submission[key] || '';
  };
  const multiplier = direction === 'asc' ? 1 : -1;
  return submissions.sort((a, b) => multiplier * String(valueFor(a)).localeCompare(String(valueFor(b))));
});

const fetchProfile = async () => {
  isLoading.value = true;
  try {
    const [profileRes, resultsRes] = await Promise.all([
      fetch(`/api/contests/${route.params.code}/users/${route.params.username}`),
      fetch(`/api/contests/${route.params.code}/results`),
    ]);
    if (!profileRes.ok) {
      if (profileRes.status === 404) throw new Error("User not found or hasn't participated in this contest yet.");
      throw new Error("Failed to load profile.");
    }
    profile.value = await profileRes.json();

    if (resultsRes.ok) {
      const results = await resultsRes.json();
      const submitters = [...(results.submitters || [])].sort((a, b) => {
        if (b.accepted !== a.accepted) return b.accepted - a.accepted;
        return b.total - a.total;
      });
      const position = submitters.findIndex((submitter) => submitter.username === profile.value.username);
      competitionPosition.value = position === -1 ? null : position + 1;
    }
  } catch (e) {
    error.value = e.message;
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  fetchProfile();
  window.addEventListener('scroll', updateScrollTopVisibility, { passive: true });
});

const updateScrollTopVisibility = () => {
  showScrollTop.value = window.scrollY > 420;
};
const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
};
onBeforeUnmount(() => window.removeEventListener('scroll', updateScrollTopVisibility));

const formatDate = (dateStr) => {
  if (!dateStr) return 'N/A';
  const dStr = String(dateStr);
  return fmtDateTime(dStr);
};
</script>

<template>
  <div class="user-profile">
    <div v-if="false" class="status-state">
      <p>⏳ Loading profile...</p>
    </div>
    
    <GlobalLoader v-if="isLoading" label="Loading profile…" />
    <div v-else-if="error" class="status-state error">
      <p>❌ {{ error }}</p>
    </div>
    
    <div v-else-if="profile" class="profile-content">
      <div class="profile-header">
        <div class="avatar">
          {{ profile.username.charAt(0).toUpperCase() }}
        </div>
        <div class="info">
          <p class="page-kicker">Contest participant</p>
          <h1>{{ profile.username }}</h1>
          <span class="role-badge" :class="profile.role">{{ profile.role }}</span>
        </div>
        <div class="stats-grid">
          <div class="profile-metric profile-metric--position">
            <div class="stat-value">{{ competitionPosition ? `#${competitionPosition}` : '—' }}</div>
            <div class="stat-label">Position</div>
          </div>
          <div class="profile-metric">
            <div class="stat-value">{{ articleStats.total }}</div>
            <div class="stat-label">Total articles</div>
          </div>
          <div class="profile-metric profile-metric--accepted">
            <div class="stat-value">{{ articleStats.accepted }}</div>
            <div class="stat-label">Accepted</div>
          </div>
          <div class="profile-metric profile-metric--rejected">
            <div class="stat-value">{{ articleStats.rejected }}</div>
            <div class="stat-label">Rejected</div>
          </div>
        </div>
      </div>
      
      <div class="tables-container">
        <div class="table-section">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Article history</p>
              <h2>Submissions</h2>
            </div>
            <span class="section-count">{{ profile.submissions.length }} articles</span>
          </div>
          <cdx-table v-if="profile.submissions.length" class="profile-table" caption="Submissions" hide-caption :columns="submissionColumns" :data="sortedSubmissions" :sort="submissionSort" @update:sort="updateSubmissionSort">
            <template #item-title="{ row }">
              <a :href="'https://bn.wiktionary.org/wiki/' + encodeURIComponent(row.title)" target="_blank" class="title-link">{{ row.title }}</a>
              <div v-if="row.validation_error" class="error-subtext">âš ï¸ {{ row.validation_error }}</div>
            </template>
            <template #item-status="{ row }"><span :class="['status-badge', row.status]">{{ row.status === 'validation_failed' ? 'Failed' : row.status }}</span></template>
            <template #item-jury="{ row }">
              <template v-if="row.reviews?.length"><div v-for="(review, reviewIndex) in row.reviews" :key="`${row.id}-${reviewIndex}`" class="jury-entry"><span class="jury-name">{{ review.jury }}</span></div></template>
              <span v-else class="muted-value">Awaiting review</span>
            </template>
            <template #item-comment="{ row }">
              <template v-if="row.reviews?.length"><div v-for="(review, reviewIndex) in row.reviews" :key="`${row.id}-comment-${reviewIndex}`" class="judgment-comment">{{ review.comment || 'No comment' }}</div></template>
              <span v-else class="muted-value">&mdash;</span>
            </template>
            <template #item-submitted_at="{ row }">{{ formatDate(row.submitted_at) }}</template>
          </cdx-table>
          <div v-else class="empty-state">No submissions yet.</div>
          <!--
            Codex renders the sortable header and accessible aria-sort state.
            The custom slots above keep article links and review details rich.
          -->
          <!--
            Legacy table markup intentionally removed below.
          -->
          <template v-if="false"><table>
              <thead>
                <tr>
                  <th><button class="sortable-header" @click="toggleSubmissionSort('title')">Article <span>{{ sortIndicator('title') }}</span></button></th>
                  <th><button class="sortable-header" @click="toggleSubmissionSort('status')">Status <span>{{ sortIndicator('status') }}</span></button></th>
                  <th><button class="sortable-header" @click="toggleSubmissionSort('jury')">Jury <span>{{ sortIndicator('jury') }}</span></button></th>
                  <th><button class="sortable-header" @click="toggleSubmissionSort('comment')">Judgment comment <span>{{ sortIndicator('comment') }}</span></button></th>
                  <th><button class="sortable-header" @click="toggleSubmissionSort('submitted_at')">Submitted At <span>{{ sortIndicator('submitted_at') }}</span></button></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sub in sortedSubmissions" :key="sub.id">
                  <td>
                    <a :href="'https://bn.wiktionary.org/wiki/' + encodeURIComponent(sub.title)" target="_blank" class="title-link">
                      {{ sub.title }}
                    </a>
                    <div v-if="sub.validation_error" class="error-subtext">
                      ⚠️ {{ sub.validation_error }}
                    </div>
                  </td>
                  <td>
                    <span :class="['status-badge', sub.status]">{{ sub.status === 'validation_failed' ? 'Failed' : sub.status }}</span>
                  </td>
                  <td class="jury-cell">
                    <template v-if="sub.reviews?.length">
                      <div v-for="(review, reviewIndex) in sub.reviews" :key="`${sub.id}-${reviewIndex}`" class="jury-entry">
                        <span class="jury-name">{{ review.jury }}</span>

                      </div>
                    </template>
                    <span v-else class="muted-value">Awaiting review</span>
                  </td>
                  <td class="comment-cell">
                    <template v-if="sub.reviews?.length">
                      <div v-for="(review, reviewIndex) in sub.reviews" :key="`${sub.id}-comment-${reviewIndex}`" class="judgment-comment">
                        {{ review.comment || 'No comment' }}
                      </div>
                    </template>
                    <span v-else class="muted-value">—</span>
                  </td>
                  <td>{{ formatDate(sub.submitted_at) }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>
        
                <div class="table-section" v-if="profile.reviews.length">
          <h3>Reviews</h3>
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Article</th>
                  <th>Decision</th>
                  <th>Comment</th>
                  <th>Reviewed At</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(rev, idx) in profile.reviews" :key="idx">
                  <td>
                    <a :href="'https://bn.wiktionary.org/wiki/' + encodeURIComponent(rev.article_title)" target="_blank" class="title-link">
                      {{ rev.article_title }}
                    </a>
                  </td>
                  <td>
                    <span :class="['decision-badge', rev.decision]">{{ rev.decision }}</span>
                  </td>
                  <td class="comment-cell" :title="rev.comment">{{ rev.comment || '-' }}</td>
                  <td>{{ formatDate(rev.reviewed_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    <button v-if="showScrollTop" class="scroll-top-button" type="button" aria-label="Back to top" title="Back to top" @click="scrollToTop">
      <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m10 3.2 6.2 6.2-1.4 1.4-3.8-3.8V17H9V7l-3.8 3.8-1.4-1.4z" /></svg>
    </button>
  </div>
</template>

<style scoped src="../styles/views/UserProfile.css"></style>
