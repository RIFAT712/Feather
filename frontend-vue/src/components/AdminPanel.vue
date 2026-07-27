<script setup>
import { ref, onMounted } from 'vue';
import { CdxButton, CdxTextInput, CdxMessage } from '@wikimedia/codex';

const name = ref('');
const startDate = ref('');
const endDate = ref('');
const message = ref('');
const isError = ref(false);

const handleCreateContest = async () => {
  try {
    const res = await fetch('/api/admin/contests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.value,
        start_date: new Date(startDate.value).toISOString(),
        end_date: new Date(endDate.value).toISOString()
      })
    });
    if (!res.ok) throw new Error("Failed to create contest");
    message.value = "Contest created successfully!";
    isError.value = false;
    name.value = ''; startDate.value = ''; endDate.value = '';
  } catch (e) {
    message.value = e.message;
    isError.value = true;
  }
};

const contestId = ref('');
const juryUsername = ref('');
const juryMessage = ref('');
const juryError = ref(false);

const handleAssignJury = async () => {
  try {
    const res = await fetch('/api/admin/assign-jury', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contest_id: parseInt(contestId.value, 10),
        wiki_username: juryUsername.value
      })
    });
    if (!res.ok) throw new Error("Failed to assign jury");
    juryMessage.value = "Jury assigned successfully!";
    juryError.value = false;
    contestId.value = ''; juryUsername.value = '';
  } catch (e) {
    juryMessage.value = e.message;
    juryError.value = true;
  }
};
</script>

<template>
  <div class="admin-panel">
    <h2 class="section-title">Admin Panel</h2>

    <div class="admin-card">
      <h3>Create New Contest</h3>
      <div class="form-group">
        <label>Contest Name</label>
        <cdx-text-input v-model="name" placeholder="e.g. Wiki Loves Monuments 2026" />
      </div>
      <div class="form-group">
        <label>Start Date</label>
        <cdx-text-input v-model="startDate" type="datetime-local" />
      </div>
      <div class="form-group">
        <label>End Date</label>
        <cdx-text-input v-model="endDate" type="datetime-local" />
      </div>
      <cdx-button action="progressive" weight="primary" @click="handleCreateContest">
        Create Contest
      </cdx-button>
      <cdx-message v-if="message" :type="isError ? 'error' : 'success'" class="mt-4">
        {{ message }}
      </cdx-message>
    </div>

    <div class="admin-card mt-8">
      <h3>Assign Jury to Contest</h3>
      <div class="form-group">
        <label>Contest ID</label>
        <cdx-text-input v-model="contestId" type="number" placeholder="Enter Contest ID" />
      </div>
      <div class="form-group">
        <label>Jury Username</label>
        <cdx-text-input v-model="juryUsername" placeholder="Enter Wikipedia Username" />
      </div>
      <cdx-button action="progressive" weight="primary" @click="handleAssignJury">
        Assign Jury
      </cdx-button>
      <cdx-message v-if="juryMessage" :type="juryError ? 'error' : 'success'" class="mt-4">
        {{ juryMessage }}
      </cdx-message>
    </div>
  </div>
</template>

<style scoped>
.admin-panel {
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
.admin-card {
  border: 1px solid #eaecf0;
  padding: 24px;
  background-color: #f8f9fa;
  border-radius: 4px;
}
.admin-card h3 {
  margin-top: 0;
  margin-bottom: 16px;
}
.form-group {
  margin-bottom: 16px;
}
.form-group label {
  display: block;
  font-weight: bold;
  margin-bottom: 8px;
  color: #202122;
}
.mt-8 { margin-top: 32px; }
.mt-4 { margin-top: 16px; }
</style>
