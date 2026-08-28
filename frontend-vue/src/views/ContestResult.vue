<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const results = ref(null);
const isLoading = ref(true);
const roles = ref({ is_jury: false, is_owner: false });
const exportMode = ref('summary');

const handleExportCSV = () => {
  window.open(`/api/admin/contests/${route.params.code}/export/csv?mode=${exportMode.value}`, '_blank');
};
const handleExportJSON = () => {
  window.open(`/api/admin/contests/${route.params.code}/export/json?mode=${exportMode.value}`, '_blank');
};
const handleExportWikitable = () => {
  window.open(`/api/admin/contests/${route.params.code}/export/wikitable?mode=${exportMode.value}`, '_blank');
};

onMounted(async () => {
  try {
    const res = await fetch(`/api/contests/${route.params.code}/results`);
    if (res.ok) {
      const data = await res.json();
      data.submitters.sort((a, b) => {
        if (b.accepted !== a.accepted) return b.accepted - a.accepted;
        return b.total - a.total;
      });
      data.juries.sort((a, b) => b.total - a.total);
      
      results.value = data;
    }
    
    const roleRes = await fetch(`/api/contests/${route.params.code}/my-role`);
    if (roleRes.ok) roles.value = await roleRes.json();
    
  } catch (err) {
    console.error("Failed to load results", err);
  } finally {
    isLoading.value = false;
  }
});
</script>

<template>
  <div class="result-page">
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h2>Live Results</h2>
        <p>Real-time leaderboard and event statistics for <strong>{{ results?.contest?.name }}</strong>.</p>
      </div>
      <div v-if="roles.is_owner" class="export-actions" style="display: flex; gap: 8px; align-items: center;">
        <select v-model="exportMode" style="padding: 6px 12px; border-radius: 6px; background: rgba(255,255,255,0.1); color: white; border: 1px solid rgba(255,255,255,0.2); outline: none; cursor: pointer; font-family: inherit;">
          <option value="summary" style="color: black;">Article Count Based</option>
          <option value="detailed" style="color: black;">Article Name Based</option>
        </select>
        <button @click="handleExportJSON" style="padding: 6px 12px; border-radius: 6px; border: none; background: rgba(255,255,255,0.1); color: #e2e8f0; cursor: pointer;">JSON</button>
        <button @click="handleExportCSV" style="padding: 6px 12px; border-radius: 6px; border: none; background: rgba(255,255,255,0.1); color: #e2e8f0; cursor: pointer;">CSV</button>
        <button @click="handleExportWikitable" style="padding: 6px 12px; border-radius: 6px; border: none; background: #2563eb; color: #fff; font-weight: 600; cursor: pointer;">Wikitable</button>
      </div>
    </div>

    <div v-if="isLoading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading results...</p>
    </div>

    <div v-else-if="results" class="results-container">
      <div class="card leaderboard-card">
        <h3>🏆 Submitter Leaderboard</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Username</th>
              <th>Total Submitted</th>
              <th>গৃহীত (Accepted)</th>
              <th>প্রত্যাখ্যাত (Rejected)</th>
              <th>অপেক্ষমাণ (Pending)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(sub, index) in results.submitters" :key="sub.username">
              <td class="rank">#{{ index + 1 }}</td>
              <td class="username">
                <router-link :to="`/${route.params.code}/user/${sub.username}`">{{ sub.username }}</router-link>
              </td>
              <td>{{ sub.total }}</td>
              <td class="accepted">{{ sub.accepted }}</td>
              <td class="rejected">{{ sub.rejected }}</td>
              <td class="pending">{{ sub.pending }}</td>
            </tr>
            <tr v-if="!results.submitters.length">
              <td colspan="6" class="empty">No submissions yet.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card jury-card mt-4">
        <h3>⚖️ Jury Activity</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>Jury Member</th>
              <th>Total Reviews</th>
              <th>Accepted Decisions</th>
              <th>Rejected Decisions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="j in results.juries" :key="j.username">
              <td class="username">
                <router-link :to="`/${route.params.code}/user/${j.username}`">{{ j.username }}</router-link>
              </td>
              <td>{{ j.total }}</td>
              <td class="accepted">{{ j.accepted }}</td>
              <td class="rejected">{{ j.rejected }}</td>
            </tr>
            <tr v-if="!results.juries.length">
              <td colspan="4" class="empty">No jury activity yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped src="../styles/views/ContestResult.css"></style>
