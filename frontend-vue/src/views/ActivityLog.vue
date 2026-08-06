<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import { CdxIcon } from '@wikimedia/codex';
import { cdxIconAlert } from '@wikimedia/codex-icons';

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
    
    const res = await fetch(`/api/contests/${route.params.code}/log`);
    if (!res.ok) throw new Error('Failed to load log');
    log.value = await res.json();
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

<style scoped>
/* Unauthorized Banner */
.unauthorized-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60vh;
}
.unauthorized-content {
  text-align: center;
  background: #1a1a1a;
  padding: 40px 60px;
  border-radius: 12px;
  border: 1px solid rgba(239, 68, 68, 0.3);
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  max-width: 500px;
  margin: 0 auto;
}
.unauthorized-content .icon { font-size: 3rem; margin-bottom: 16px; display: block; }
.unauthorized-content h2 { color: #ffffff; margin: 0 0 12px 0; font-size: 1.5rem; font-weight: 700; }
.unauthorized-content p { color: #9ca3af; margin: 0; font-size: 0.95rem; line-height: 1.5; }

/* ── Root ── */
.log-root {
  background: #0a0a0a;
  min-height: 100%;
  padding: 28px 32px;
  font-family: 'Inter', 'Segoe UI', sans-serif;
  color: #e2e8f0;
}

/* ── States ── */
.state-center {
  text-align: center;
  padding: 60px 24px;
  color: #64748b;
  font-size: 0.95rem;
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin { to { transform: rotate(360deg); } }

.error-box {
  color: #ffffff;
}

.error-icon {
  font-size: 2rem;
  display: block;
  margin-bottom: 8px;
}

/* ── Stats Bar ── */
.stats-bar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.stat-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 600;
}

.chip-label {
  font-weight: 500;
  opacity: 0.8;
}

.chip-val {
  font-weight: 700;
  font-size: 0.9rem;
}

.chip-total    { background: rgba(255,255,255,0.07); color: #94a3b8; }
.chip-accepted { background: rgba(34,197,94,0.12); color: #22c55e; }
.chip-rejected { background: rgba(239,68,68,0.12); color: #ef4444; }
.chip-pending  { background: rgba(245,158,11,0.12); color: #f59e0b; }
.chip-failed   { background: rgba(239,68,68,0.08); color: #94a3b8; border: 1px solid rgba(239,68,68,0.2); }

.error-subtext {
  font-size: 0.76rem;
  color: #9ca3af;
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: normal;
  word-break: break-word;
}

.tl-error-banner {
  margin-top: 10px;
  padding: 8px 12px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 8px;
  color: #9ca3af;
  font-size: 0.83rem;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tl-accepted { border-left-color: #22c55e; }
.tl-rejected { border-left-color: #ef4444; }
.tl-pending  { border-left-color: #f59e0b; }
.tl-skipped  { border-left-color: #64748b; }
.tl-validation_failed { border-left-color: #ef4444; }

/* ── Badges ── */
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.73rem;
  font-weight: 700;
  text-transform: capitalize;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.badge-accepted { background: rgba(34,197,94,0.15); color: #22c55e; }
.badge-rejected { background: rgba(239,68,68,0.15); color: #ef4444; }
.badge-pending  { background: rgba(245,158,11,0.12); color: #f59e0b; }
.badge-skipped  { background: rgba(148,163,184,0.1); color: #94a3b8; }
.badge-failed   { background: rgba(239,68,68,0.1); color: #f87171; border: 1px solid rgba(239,68,68,0.2); }

/* ── Segmented Control ── */
.toggle-bar {
  margin-bottom: 24px;
}

.segmented-control {
  display: inline-flex;
  background: rgba(255,255,255,0.07);
  border-radius: 999px;
  padding: 3px;
  gap: 2px;
}

.seg-btn {
  padding: 7px 18px;
  border: none;
  background: transparent;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: background 0.18s, color 0.18s, box-shadow 0.18s;
}

.seg-btn.active {
  background: #1a1a1a;
  color: #e5e7eb;
  font-weight: 600;
  box-shadow: 0 1px 6px rgba(0,0,0,0.3);
}

.seg-btn:not(.active):hover {
  color: #e2e8f0;
}

/* ── View Section ── */
.view-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ── User Card ── */
.user-card {
  background: #1a1a1a;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 14px;
  box-shadow: 0 1px 8px rgba(0,0,0,0.3);
  overflow: hidden;
}

.user-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s;
}

.user-header:hover {
  background: rgba(255,255,255,0.04);
}

.user-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar-circle {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f46e5, #2563eb);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.95rem;
  flex-shrink: 0;
}

.user-name {
  font-weight: 600;
  font-size: 0.95rem;
}

.profile-link {
  color: #e5e7eb;
  text-decoration: none;
  transition: color 0.15s, text-decoration 0.15s;
}
.profile-link:hover {
  color: #e0e7ff;
  text-decoration: underline;
}

.count-badge {
  background: rgba(255,255,255,0.1);
  color: #e5e7eb;
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 0.75rem;
  font-weight: 700;
}

.chevron {
  font-size: 1.3rem;
  color: #94a3b8;
  transform: rotate(0deg);
  transition: transform 0.2s;
  line-height: 1;
}

.chevron.open {
  transform: rotate(90deg);
}

/* ── User Table ── */
.user-table-wrap {
  overflow-x: auto;
  border-top: 1px solid rgba(255,255,255,0.06);
  -webkit-overflow-scrolling: touch;
}

.user-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.user-table thead tr {
  background: rgba(255,255,255,0.04);
}

.user-table th {
  text-align: left;
  padding: 10px 16px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  border-bottom: 1px solid rgba(255,255,255,0.07);
}

.user-table td {
  padding: 11px 16px;
  color: #cbd5e1;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  vertical-align: middle;
}

.row-even { background: rgba(255,255,255,0.02); }
.row-odd  { background: transparent; }

.td-article  { font-weight: 500; color: #e2e8f0; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-reviewer { color: #64748b; }
.td-comment { min-width: 220px; max-width: 360px; color: #cbd5e1; line-height: 1.45; }
.comment-item { white-space: normal; overflow-wrap: anywhere; }
.comment-item + .comment-item { margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.06); }
.td-date     { color: #94a3b8; font-size: 0.8rem; white-space: nowrap; }
.article-link { color: inherit; text-decoration: none; border-bottom: 1px dashed #94a3b8; transition: border-color 0.15s, color 0.15s; }
.article-link:hover { color: #ffffff; border-bottom-color: #ffffff; }
.mini-tl-item { display: flex; align-items: center; gap: 10px; margin-top: 8px; font-size: 0.8rem; color: #64748b; }

/* ── Timeline Card ── */
.timeline-card {
  background: #1a1a1a;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 14px;
  box-shadow: 0 1px 8px rgba(0,0,0,0.3);
  padding: 18px 20px 16px 24px;
  border-left: 5px solid rgba(255,255,255,0.1);
  transition: box-shadow 0.15s;
}

.timeline-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}

.tl-accepted { border-left-color: #22c55e; }
.tl-rejected { border-left-color: #ef4444; }
.tl-pending  { border-left-color: #f59e0b; }
.tl-skipped  { border-left-color: #64748b; }

.tl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.tl-title {
  font-weight: 600;
  font-size: 0.95rem;
  color: #e2e8f0;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tl-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  color: #64748b;
  flex-wrap: wrap;
}

.tl-meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.tl-label {
  color: #94a3b8;
  font-style: italic;
}

.tl-sep {
  color: #cbd5e1;
}

/* Mini Timeline */
.mini-timeline {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  font-size: 0.8rem;
  color: #64748b;
}

.mini-tl-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #94a3b8;
}

.dot-accepted { background: #22c55e; }
.dot-rejected { background: #ef4444; }
.dot-pending  { background: #f59e0b; }

.mini-tl-line {
  width: 24px;
  height: 2px;
  background: rgba(255,255,255,0.1);
  flex-shrink: 0;
}

.mini-tl-event {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

/* ── Badges ── */
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.73rem;
  font-weight: 700;
  text-transform: capitalize;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.badge-accepted { background: rgba(34,197,94,0.15); color: #22c55e; }
.badge-rejected { background: rgba(239,68,68,0.15); color: #ef4444; }
.badge-pending  { background: rgba(245,158,11,0.12); color: #f59e0b; }
.badge-skipped  { background: rgba(148,163,184,0.1); color: #94a3b8; }

/* Mobile table responsiveness */
@media (max-width: 640px) {
  .log-root { padding: 16px; }
  .stats-bar { gap: 6px; }
  .stat-chip { padding: 5px 10px; font-size: 0.75rem; }
  .user-header { flex-wrap: wrap; gap: 8px; padding: 14px 16px; }
  .user-table th, .user-table td { padding: 8px 12px; font-size: 0.8rem; }
  .td-date { display: none; }
  .timeline-card { padding: 14px 16px 12px 18px; }
}
</style>
