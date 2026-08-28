<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import { CdxIcon } from '@wikimedia/codex';
import { cdxIconAlert } from '@wikimedia/codex-icons';
import { fetchAllContestLogPages } from '../utils/contestLog';

const props = defineProps(['contest']);
const route = useRoute();
const log = ref([]);
const isLoading = ref(true);
const error = ref(null);
const viewMode = ref('per-user');
const openGroups = ref({});
const roles = ref({ is_jury: false, is_owner: false });
const isAuthorized = computed(() => roles.value.is_jury || roles.value.is_owner);

const fmt = (iso) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
};

const statusClass = (s) => ({
  accepted: 'badge-accepted',
  rejected: 'badge-rejected',
  pending:  'badge-pending',
  skipped:  'badge-skipped',
  validation_failed: 'badge-failed',
}[s] || '');

const statusLabel = (s) => ({
  accepted: 'Accepted',
  rejected: 'Rejected',
  pending:  'Pending',
  skipped:  'Skipped',
  validation_failed: 'Validation Error',
}[s] || s);

const groupedByUser = computed(() => {
  const map = {};
  log.value.forEach((entry, idx) => {
    const user = entry.submitted_by;
    if (!map[user]) map[user] = { user, entries: [], isOpen: false };
    map[user].entries.push(entry);
  });
  return Object.values(map);
});

const toggleUser = (group) => {
  openGroups.value[group.user] = !openGroups.value[group.user];
};

const reviewComments = (entry) => (entry.reviews || [])
  .filter(review => review.comment && review.comment.trim())
  .map(review => ({ reviewer: review.reviewer, comment: review.comment.trim() }));

onMounted(async () => {
  try {
    const roleRes = await fetch(`/api/contests/${route.params.code}/my-role`);
    if (roleRes.ok) roles.value = await roleRes.json();
    
    // Loaded in bounded pages and rendered as pages arrive, rather than blocking
    // on one request that joins and serializes every article + review at once.
    await fetchAllContestLogPages(route.params.code, {
      onPage: (items) => { log.value = items; },
    });
  } catch (e) {
    error.value = e.message;
  } finally {
    isLoading.value = false;
  }
});
</script>

<template>
  <div class="log-root">

    <div v-if="!isLoading && !isAuthorized" class="unauthorized-banner">
      <div class="unauthorized-content">
        <span class="icon">⛔</span>
        <h2>Access Denied</h2>
        <p>You are not authorized to view this page. This area is restricted to Contest Jury and Owners.</p>
      </div>
    </div>

        <div v-else-if="isLoading" class="state-center">
      <div class="spinner" />
      <p>Loading activity log…</p>
    </div>

        <div v-else-if="error" class="state-center error-box">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:8px; display:block;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      <p>{{ error }}</p>
    </div>

    <template v-else>
            <div class="stats-bar">
        <div class="stat-chip chip-total">
          <span class="chip-label">Total</span>
          <span class="chip-val">{{ log.length }}</span>
        </div>
        <div class="stat-chip chip-accepted">
          <span class="chip-label">Accepted</span>
          <span class="chip-val">{{ log.filter(e => e.status === 'accepted').length }}</span>
        </div>
        <div class="stat-chip chip-rejected">
          <span class="chip-label">Rejected</span>
          <span class="chip-val">{{ log.filter(e => e.status === 'rejected').length }}</span>
        </div>
        <div class="stat-chip chip-pending">
          <span class="chip-label">Pending</span>
          <span class="chip-val">{{ log.filter(e => e.status === 'pending').length }}</span>
        </div>
        <div class="stat-chip chip-failed">
          <span class="chip-label">Errors</span>
          <span class="chip-val">{{ log.filter(e => e.status === 'validation_failed').length }}</span>
        </div>
      </div>

            <div class="toggle-bar">
        <div class="segmented-control">
          <button
            class="seg-btn"
            :class="{ active: viewMode === 'per-user' }"
            @click="viewMode = 'per-user'"
          >
            Per-User Table
          </button>
          <button
            class="seg-btn"
            :class="{ active: viewMode === 'timeline' }"
            @click="viewMode = 'timeline'"
          >
            Timeline Log
          </button>
        </div>
      </div>

            <div v-if="viewMode === 'per-user'" class="view-section">
        <div
          v-for="group in groupedByUser"
          :key="group.user"
          class="user-card"
        >
                    <button
            class="user-header"
            @click="toggleUser(group)"
            :aria-expanded="!!openGroups[group.user]"
          >
            <div class="user-header-left">
              <div class="avatar-circle">{{ group.user.charAt(0).toUpperCase() }}</div>
              <router-link :to="`/${route.params.code}/user/${encodeURIComponent(group.user)}`" class="user-name profile-link" @click.stop>{{ group.user }}</router-link>
              <span class="count-badge">{{ group.entries.length }}</span>
            </div>
            <span class="chevron" :class="{ open: openGroups[group.user] }">›</span>
          </button>

                    <div v-if="openGroups[group.user]" class="user-table-wrap">
            <table class="user-table">
              <thead>
                <tr>
                  <th>Article</th>
                  <th>Status</th>
                  <th>Reviewed by</th>
                  <th>Jury Comment</th>
                  <th>Submitted</th>
                  <th>Reviewed</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(entry, idx) in group.entries"
                  :key="entry.id || idx"
                  :class="idx % 2 === 0 ? 'row-even' : 'row-odd'"
                >
                  <td class="td-article">
                    <a :href="`https://bn.wiktionary.org/wiki/${encodeURIComponent(entry.title)}`" target="_blank" class="article-link">{{ entry.title }}</a>
                    <div v-if="entry.validation_error" class="error-subtext">
                      <CdxIcon :icon="cdxIconAlert" class="err-icon" /> {{ entry.validation_error }}
                    </div>
                  </td>
                  <td><span :class="['badge', statusClass(entry.status)]">{{ statusLabel(entry.status) }}</span></td>
                  <td class="td-reviewer">{{ entry.reviews && entry.reviews.length ? entry.reviews[0].reviewer : '—' }}</td>
                  <td class="td-comment">
                    <template v-if="reviewComments(entry).length">
                      <div v-for="(review, reviewIndex) in reviewComments(entry)" :key="`${review.reviewer}-${reviewIndex}`" class="comment-item">
                        {{ review.comment }}
                      </div>
                    </template>
                    <span v-else>—</span>
                  </td>
                  <td class="td-date">{{ fmt(entry.submitted_at) }}</td>
                  <td class="td-date">{{ entry.reviews && entry.reviews.length ? fmt(entry.reviews[0].reviewed_at) : '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

            <div v-if="viewMode === 'timeline'" class="view-section">
        <div
          v-for="(entry, idx) in log"
          :key="entry.id || idx"
          class="timeline-card"
          :class="`tl-${entry.status}`"
        >
          <div class="tl-header">
            <a :href="`https://bn.wiktionary.org/wiki/${encodeURIComponent(entry.title)}`" target="_blank" class="tl-title article-link">{{ entry.title }}</a>
            <span :class="['badge', statusClass(entry.status)]">{{ statusLabel(entry.status) }}</span>
          </div>
          <div class="tl-meta">
            <span class="tl-meta-item">
              <span class="tl-label">Submitted by</span>
              <strong><router-link :to="`/${route.params.code}/user/${encodeURIComponent(entry.submitted_by)}`" class="profile-link">{{ entry.submitted_by }}</router-link></strong>
            </span>
            <span class="tl-sep">·</span>
            <span class="tl-meta-item">
              <span class="tl-label">at</span>
              {{ fmt(entry.submitted_at) }}
            </span>
          </div>

                    <div v-if="entry.validation_error" class="tl-error-banner">
            <CdxIcon :icon="cdxIconAlert" class="err-icon" />
            <span class="err-msg"><strong>Error:</strong> {{ entry.validation_error }}</span>
          </div>

                    <div v-if="entry.reviews && entry.reviews.length" class="mini-timeline">
            <div v-for="rev in entry.reviews" :key="rev.reviewer" class="mini-tl-item">
              <div class="mini-tl-dot" :class="`dot-${rev.decision}`" />
              <div class="mini-tl-line" />
              <div class="mini-tl-event">
                <span class="tl-label">Reviewed by</span>
                <strong><router-link :to="`/${route.params.code}/user/${encodeURIComponent(rev.reviewer)}`" class="profile-link">{{ rev.reviewer }}</router-link></strong>
                <span class="tl-sep">·</span>
                {{ fmt(rev.reviewed_at) }}
              </div>
            </div>
          </div>
        </div>

        <div v-if="log.length === 0" class="state-center">
          <p>No activity recorded yet.</p>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped src="../styles/views/ActivityLog.css"></style>
