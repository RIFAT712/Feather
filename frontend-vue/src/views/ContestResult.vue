<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { CdxTable } from '@wikimedia/codex';
import GlobalLoader from '../components/ui/GlobalLoader.vue';

const route = useRoute();
const results = ref(null);
const isLoading = ref(true);
const roles = ref({ is_jury: false, is_owner: false });
const exportMode = ref('summary');

// Both tables arrive pre-sorted from /results (submitters by accepted then
// total, juries by review count), so the columns stay unsorted -- turning on
// allowSort would offer a control that fights the ranking the page is about.
const submitterColumns = [
  { id: 'rank', label: 'Rank', width: '80px' },
  { id: 'username', label: 'Username', minWidth: '160px' },
  { id: 'total', label: 'Total Submitted', textAlign: 'number' },
  { id: 'accepted', label: 'গৃহীত (Accepted)', textAlign: 'number' },
  { id: 'rejected', label: 'প্রত্যাখ্যাত (Rejected)', textAlign: 'number' },
  { id: 'pending', label: 'অপেক্ষমাণ (Pending)', textAlign: 'number' },
];

const juryColumns = [
  { id: 'username', label: 'Jury Member', minWidth: '160px' },
  { id: 'total', label: 'Total Reviews', textAlign: 'number' },
  { id: 'accepted', label: 'Accepted Decisions', textAlign: 'number' },
  { id: 'rejected', label: 'Rejected Decisions', textAlign: 'number' },
];

// CdxTable renders from a row object, so the rank that used to come from the
// v-for index is materialised onto the row instead.
const rankedSubmitters = computed(() =>
  (results.value?.submitters || []).map((sub, index) => ({ ...sub, rank: index + 1 }))
);

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

    <GlobalLoader v-if="isLoading" label="Loading results…" />

    <div v-else-if="results" class="results-container">
      <section class="table-section">
        <h3>Submitter Leaderboard</h3>
        <cdx-table
          caption="Submitter leaderboard"
          hide-caption
          :columns="submitterColumns"
          :data="rankedSubmitters"
        >
          <template #item-rank="{ item }"><span class="rank">#{{ item }}</span></template>
          <template #item-username="{ item }">
            <router-link :to="`/${route.params.code}/user/${item}`">{{ item }}</router-link>
          </template>
          <template #item-accepted="{ item }"><span class="accepted">{{ item }}</span></template>
          <template #item-rejected="{ item }"><span class="rejected">{{ item }}</span></template>
          <template #item-pending="{ item }"><span class="pending">{{ item }}</span></template>
          <template #empty-state>No submissions yet.</template>
        </cdx-table>
      </section>

      <section class="table-section">
        <h3>Jury Activity</h3>
        <cdx-table
          caption="Jury activity"
          hide-caption
          :columns="juryColumns"
          :data="results.juries"
        >
          <template #item-username="{ item }">
            <router-link :to="`/${route.params.code}/user/${item}`">{{ item }}</router-link>
          </template>
          <template #item-accepted="{ item }"><span class="accepted">{{ item }}</span></template>
          <template #item-rejected="{ item }"><span class="rejected">{{ item }}</span></template>
          <template #empty-state>No jury activity yet.</template>
        </cdx-table>
      </section>
    </div>
  </div>
</template>

<style scoped src="../styles/views/ContestResult.css"></style>
