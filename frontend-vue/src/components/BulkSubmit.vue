<script setup>
import { ref, onMounted } from 'vue';
import { CdxTextArea, CdxButton, CdxIcon } from '@wikimedia/codex';
import { cdxIconCheck, cdxIconClear } from '@wikimedia/codex-icons';

const contests = ref([]);
const selectedContestId = ref('');
const titles = ref('');
const results = ref([]);
const isLoading = ref(false);

onMounted(async () => {
  const res = await fetch('/api/contests');
  if (res.ok) {
    contests.value = await res.json();
    if (contests.value.length > 0) {
      selectedContestId.value = contests.value[0].id;
    }
  }
});

const handleSubmit = async () => {
  if (!selectedContestId.value) {
    alert("Please select a contest.");
    return;
  }
  
  isLoading.value = true;
  const titleList = titles.value.split('\n').filter(t => t.trim() !== '');
  
  try {
    const response = await fetch('/api/submit-bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contest_id: parseInt(selectedContestId.value, 10), titles: titleList }),
    });
    results.value = await response.json();
  } catch (error) {
    console.error("Error submitting titles:", error);
  } finally {
    isLoading.value = false;
  }
};
</script>

<template>
  <div class="bulk-submit">
    <h2 class="section-title">Submit Articles</h2>
    
    <div class="field">
      <label class="field-label">Select Contest</label>
      <select v-model="selectedContestId" class="contest-select">
        <option v-for="c in contests" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
    </div>

    <div class="field">
      <label class="field-label">Paste Wikipedia Titles (one per line)</label>
      <cdx-text-area
        v-model="titles"
        placeholder="e.g. History of Wikipedia"
        :rows="6"
      ></cdx-text-area>
    </div>

    <div class="actions">
      <cdx-button 
        action="progressive" 
        weight="primary" 
        :disabled="isLoading || !titles.trim() || !selectedContestId"
        @click="handleSubmit"
      >
        {{ isLoading ? 'Validating & Submitting...' : 'Submit Articles' }}
      </cdx-button>
    </div>

    <div v-if="results.length > 0" class="results-section">
      <h3 class="subsection-title">Submission Results</h3>
      
      <div class="table-container" style="overflow-x: auto;">
        <table class="wikitable">
          <thead>
            <tr>
              <th>Title</th>
              <th>Status</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(result, idx) in results" :key="idx">
              <td>{{ result.title }}</td>
              <td class="status-cell">
                <cdx-icon v-if="result.is_valid" :icon="cdxIconCheck" class="icon-valid" />
                <cdx-icon v-else :icon="cdxIconClear" class="icon-invalid" />
              </td>
              <td>
                <span v-if="!result.is_valid" class="error-text">{{ result.error }}</span>
                <span v-else class="success-text">Saved Successfully!</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bulk-submit {
  background: white;
  padding: 24px;
  border-radius: 4px;
  border: 1px solid #a2a9b1;
}
.section-title {
  margin-top: 0;
  border-bottom: 1px solid #a2a9b1;
  padding-bottom: 8px;
  margin-bottom: 24px;
}
.field {
  margin-bottom: 16px;
}
.field-label {
  display: block;
  font-weight: bold;
  margin-bottom: 8px;
  color: #202122;
}
.contest-select {
  width: 100%;
  padding: 8px;
  border: 1px solid #a2a9b1;
  border-radius: 2px;
  font-size: 1rem;
}
.actions {
  margin-bottom: 32px;
}
.results-section {
  margin-top: 32px;
}
.subsection-title {
  margin-bottom: 16px;
}
.wikitable {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 24px;
}
.wikitable th, .wikitable td {
  border: 1px solid #a2a9b1;
  padding: 8px 12px;
  text-align: left;
}
.wikitable th {
  background-color: #eaecf0;
  font-weight: bold;
}
.status-cell {
  text-align: center;
}
.icon-valid {
  color: #ffffff;
}
.icon-invalid {
  color: #ffffff;
}
.error-text {
  color: #ffffff;
}
.success-text {
  color: #ffffff;
}
</style>
