<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const profile = ref(null);
const isLoading = ref(true);
const error = ref(null);

const fetchProfile = async () => {
  isLoading.value = true;
  try {
    const res = await fetch(`/api/contests/${route.params.code}/users/${route.params.username}`);
    if (!res.ok) {
      if (res.status === 404) throw new Error("User not found or hasn't participated in this contest yet.");
      throw new Error("Failed to load profile.");
    }
    profile.value = await res.json();
  } catch (e) {
    error.value = e.message;
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  fetchProfile();
});

const formatDate = (dateStr) => {
  if (!dateStr) return 'N/A';
  const dStr = String(dateStr);
  return new Date(dStr + (!dStr.endsWith('Z') ? 'Z' : '')).toLocaleString();
};
</script>

<template>
  <div class="user-profile">
    <div v-if="isLoading" class="status-state">
      <p>⏳ Loading profile...</p>
    </div>
    
    <div v-else-if="error" class="status-state error">
      <p>❌ {{ error }}</p>
    </div>
    
    <div v-else-if="profile" class="profile-content">
      <div class="profile-header">
        <div class="avatar">
          {{ profile.username.charAt(0).toUpperCase() }}
        </div>
        <div class="info">
          <h2>{{ profile.username }}</h2>
          <span class="role-badge" :class="profile.role">{{ profile.role }}</span>
        </div>
      </div>
      
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ profile.submissions.length }}</div>
          <div class="stat-label">Submissions</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ profile.reviews.length }}</div>
          <div class="stat-label">Reviews</div>
        </div>
      </div>
      
      <div class="tables-container">
        <!-- Submissions Table -->
        <div class="table-section">
          <h3>Submissions</h3>
          <div class="table-wrapper">
            <table v-if="profile.submissions.length" class="data-table">
              <thead>
                <tr>
                  <th>Article</th>
                  <th>Status</th>
                  <th>Submitted At</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sub in profile.submissions" :key="sub.id">
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
                  <td>{{ formatDate(sub.submitted_at) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="empty-state">No submissions yet.</div>
          </div>
        </div>
        
        <!-- Reviews Table -->
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
  </div>
</template>

<style scoped>
.user-profile {
  padding: 32px 48px;
  max-width: 1200px;
  margin: 0 auto;
  color: #e2e8f0;
}

.status-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 300px;
  font-size: 1.2rem;
  color: #94a3b8;
}
.status-state.error {
  color: #ffffff;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 40px;
  background: #1e293b;
  padding: 32px;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.2);
  border: 1px solid rgba(255,255,255,0.05);
}

.avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f46e5, #2563eb);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.5rem;
  font-weight: 700;
  color: #fff;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

.info h2 {
  margin: 0 0 8px 0;
  font-size: 2rem;
  font-weight: 800;
}

.role-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: capitalize;
}
.role-badge.owner { background: rgba(239, 68, 68, 0.15); color: #ffffff; }
.role-badge.participant { background: rgba(59, 130, 246, 0.15); color: #d1d5db; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 24px;
  margin-bottom: 40px;
}

.stat-card {
  background: #1e293b;
  padding: 24px;
  border-radius: 16px;
  text-align: center;
  border: 1px solid rgba(255,255,255,0.05);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
.stat-value {
  font-size: 2.5rem;
  font-weight: 800;
  color: #ffffff;
  margin-bottom: 8px;
}
.stat-label {
  color: #94a3b8;
  font-size: 0.95rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tables-container {
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.table-section h3 {
  margin: 0 0 16px 0;
  font-size: 1.25rem;
  color: #f1f5f9;
  font-weight: 700;
}

.table-wrapper {
  background: #1e293b;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,0.05);
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.data-table th, .data-table td {
  padding: 16px 24px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.data-table th {
  background: rgba(15, 23, 42, 0.4);
  color: #94a3b8;
  font-weight: 600;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.data-table tbody tr:hover {
  background: rgba(255,255,255,0.02);
}

.title-link {
  color: #d1d5db;
  text-decoration: none;
  font-weight: 500;
}
.title-link:hover {
  text-decoration: underline;
}

.status-badge, .decision-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: capitalize;
}

.status-badge.accepted, .decision-badge.accepted { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
.status-badge.rejected, .decision-badge.rejected { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
.status-badge.pending { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
.status-badge.validation_failed { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.25); }
.decision-badge.skipped { background: rgba(148, 163, 184, 0.15); color: #94a3b8; }

.error-subtext {
  font-size: 0.78rem;
  color: #f87171;
  margin-top: 4px;
}

.comment-cell {
  max-width: 300px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #cbd5e1;
}

.empty-state {
  padding: 32px;
  text-align: center;
  color: #94a3b8;
  font-style: italic;
}

@media (max-width: 768px) {
  .user-profile { padding: 16px; }
  .profile-header { flex-direction: column; text-align: center; padding: 24px 16px; gap: 16px; }
  .table-wrapper { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .data-table th, .data-table td { padding: 10px 14px; font-size: 0.82rem; }
}
</style>
