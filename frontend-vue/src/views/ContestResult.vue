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
      
      // Sort submitters by accepted count (desc), then total count (desc)
      data.submitters.sort((a, b) => {
        if (b.accepted !== a.accepted) return b.accepted - a.accepted;
        return b.total - a.total;
      });
      
      // Sort juries by total reviewed (desc)
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

<style scoped>
.result-page { padding: 32px; max-width: 1000px; margin: 0 auto; color: #e2e8f0; }
.page-header h2 { font-size: 1.8rem; margin-bottom: 8px; color: #ffffff; }
.page-header p { color: #9ca3af; margin-bottom: 24px; }

.card { background: #161829; padding: 24px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); }
.card h3 { margin-top: 0; color: #ffffff; margin-bottom: 16px; font-size: 1.2rem; display: flex; align-items: center; gap: 8px; }
.mt-4 { margin-top: 24px; }

.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 14px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }
.data-table th { color: #9ca3af; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 0.5px; }
.data-table tr:hover { background: rgba(255,255,255,0.02); }

.rank { font-weight: bold; color: #9ca3af; }
.username a { color: #818cf8; text-decoration: none; font-weight: 500; }
.username a:hover { text-decoration: underline; }

.accepted { color: #d1d5db; font-weight: 600; }
.rejected { color: #d1d5db; font-weight: 600; }
.pending { color: #d1d5db; font-weight: 600; }
.empty { text-align: center; color: #6b7280; font-style: italic; }

.loading-state { text-align: center; padding: 60px; color: #9ca3af; }
.spinner { border: 4px solid rgba(255,255,255,0.1); border-top: 4px solid #ffffff; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 16px; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
</style>
