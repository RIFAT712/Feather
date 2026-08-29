<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { formatDateTime as fmtDateTime } from '../utils/datetime';

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
  return fmtDateTime(dStr);
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

<style scoped src="../styles/views/UserProfile.css"></style>
