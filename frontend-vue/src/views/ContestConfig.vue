<script setup>
import { ref, onMounted, inject, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { CdxTextInput, CdxCheckbox } from '@wikimedia/codex';

const route = useRoute();
const router = useRouter();
const user = inject('user');

const contest = ref(null);
const isLoading = ref(true);
const toastMessage = ref('');
const toastIsError = ref(false);
const talkHeaderLabel = '{{আলাপ পাতা}}';

const activeTab = ref('basic'); // 'basic', 'rules', 'talk', 'jury'

// Form state
const editName = ref('');
const editStartDate = ref('');
const editStartTime = ref('');
const editEndDate = ref('');
const editEndTime = ref('');
const editMustBeCreator = ref(true);
const editMinBytes = ref(0);
const editMinWords = ref(0);
const editMinRefs = ref(0);
const editNoRedirect = ref(true);
const editNoDisambig = ref(true);
const editMainspaceOnly = ref(true);
const editAllowSelfReview = ref(false);
const editAddTalkTemplate = ref(false);
const editTalkTemplateName = ref('');
const editIncludeTalkHeader = ref(true);

// Jury state
const juries = ref([]);
const jurySearchValue = ref('');
const juryUsername = ref('');
const juryMenuItems = ref([]);
const juryTags = ref([]);

let searchTimeout;
watch(jurySearchValue, (newVal) => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(async () => {
    const prefix = newVal.trim();
    if (prefix.length < 2) {
      juryMenuItems.value = [];
      return;
    }
    try {
      const url = `https://bn.wiktionary.org/w/api.php?action=query&list=allusers&auprefix=${encodeURIComponent(prefix)}&format=json&origin=*`;
      const res = await fetch(url);
      const data = await res.json();
      if (data.query && data.query.allusers) {
        juryMenuItems.value = data.query.allusers
          .map(u => ({ value: u.name, label: u.name }))
          .filter(u => !juries.value.includes(u.value) && !juryTags.value.includes(u.value));
      }
    } catch (err) {}
  }, 300);
});

watch(juryUsername, (newVal) => {
  if (newVal && !juryTags.value.includes(newVal)) {
    juryTags.value.push(newVal);
  }
  juryUsername.value = '';
  jurySearchValue.value = '';
  juryMenuItems.value = [];
});

const removeJuryTag = (tag) => {
  juryTags.value = juryTags.value.filter(t => t !== tag);
};

const showToast = (msg, isError = false) => {
  toastMessage.value = msg;
  toastIsError.value = isError;
  setTimeout(() => { toastMessage.value = ''; }, 4000);
};

const fetchContest = async () => {
  isLoading.value = true;
  try {
    const res = await fetch(`/api/contests/${route.params.code}`);
    if (res.ok) {
      const c = await res.json();
      contest.value = c;
      juries.value = c.juries || [];
      
      editName.value = c.name;
      const start = new Date(c.start_date + (!c.start_date.endsWith('Z') ? 'Z' : ''));
      editStartDate.value = start.toISOString().split('T')[0];
      editStartTime.value = start.toISOString().split('T')[1].slice(0,5);
      const end = new Date(c.end_date + (!c.end_date.endsWith('Z') ? 'Z' : ''));
      editEndDate.value = end.toISOString().split('T')[0];
      editEndTime.value = end.toISOString().split('T')[1].slice(0,5);
      
      editMustBeCreator.value = c.rule_must_be_creator ?? true;
      editMinBytes.value = c.min_bytes ?? 0;
      editMinWords.value = c.min_words ?? 0;
      editMinRefs.value = c.min_refs ?? 0;
      editNoRedirect.value = c.rule_no_redirect ?? true;
      editNoDisambig.value = c.rule_no_disambig ?? true;
      editMainspaceOnly.value = c.rule_mainspace_only ?? true;
      editAllowSelfReview.value = c.allow_self_review ?? false;
      editAddTalkTemplate.value = c.add_talk_template ?? false;
      editTalkTemplateName.value = c.talk_template_name ?? '';
      editIncludeTalkHeader.value = c.include_talk_header ?? true;
    }
  } catch (e) {
    showToast("Failed to load contest.", true);
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  if (!user.value || user.value.role !== 'owner') {
    // Note: the template handles rendering the access denied message
    isLoading.value = false;
    return;
  }
  fetchContest();
});

const saveSettings = async () => {
  try {
    const res = await fetch(`/api/admin/contests/${contest.value.code}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: editName.value,
        start_date: new Date(`${editStartDate.value}T${editStartTime.value}Z`).toISOString(),
        end_date: new Date(`${editEndDate.value}T${editEndTime.value}Z`).toISOString(),
        rule_must_be_creator: editMustBeCreator.value,
        min_bytes: Number(editMinBytes.value) || 0,
        min_words: Number(editMinWords.value) || 0,
        min_refs: Number(editMinRefs.value) || 0,
        rule_no_redirect: editNoRedirect.value,
        rule_no_disambig: editNoDisambig.value,
        rule_mainspace_only: editMainspaceOnly.value,
        allow_self_review: editAllowSelfReview.value,
        add_talk_template: editAddTalkTemplate.value,
        talk_template_name: editTalkTemplateName.value.trim(),
        include_talk_header: editIncludeTalkHeader.value
      })
    });
    if (!res.ok) throw new Error("Save failed");
    showToast("Contest settings updated successfully!");
    fetchContest();
  } catch (e) {
    showToast("Error updating settings.", true);
  }
};

const handleAssignJury = async () => {
  if (!juryTags.value.length) {
    showToast("Please add at least one username.", true);
    return;
  }
  try {
    const res = await fetch('/api/admin/assign-jury', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contest_code: contest.value.code,
        wiki_usernames: juryTags.value
      })
    });
    if (!res.ok) throw new Error("Failed");
    const data = await res.json();
    showToast(`✅ Assigned ${data.added.length} jury member(s)!`);
    juryTags.value = [];
    fetchContest();
  } catch (e) {
    showToast("Error assigning jury.", true);
  }
};

const handleUnassignJury = async (username) => {
  if (!confirm(`Remove "${username}" from jury roster?`)) return;
  try {
    const res = await fetch('/api/admin/unassign-jury', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contest_code: contest.value.code,
        wiki_username: username
      })
    });
    if (res.ok) {
      showToast(`Removed ${username} from jury.`);
      fetchContest();
    }
  } catch (e) {
    showToast("Failed to remove jury member", true);
  }
};

const wikitextPreview = computed(() => {
  if (!editAddTalkTemplate.value) return '';
  let tName = editTalkTemplateName.value.trim() || 'উইকিঅভিধান প্রতিযোগিতা ২০২৬';
  if (!tName.startsWith('{{')) {
    tName = `{{${tName}}}`;
  }
  let text = '';
  if (editIncludeTalkHeader.value) {
    text += '{{আলাপ পাতা}}\n';
  }
  text += tName;
  return text;
});
</script>

<template>
  <div class="config-page">
    <transition name="toast">
      <div v-if="toastMessage" class="toast-banner" :class="{ 'toast-error': toastIsError }">
        <span class="toast-icon">{{ toastIsError ? '⚠️' : '✨' }}</span>
        <span>{{ toastMessage }}</span>
      </div>
    </transition>

    <div v-if="isLoading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading...</p>
    </div>

    <div v-else-if="!user || user.role !== 'owner'" class="unauthorized-banner">
      <div class="unauthorized-content">
        <span class="icon">⛔</span>
        <h2>Owner Portal Restricted</h2>
        <p>You are not authorized to view this page. Only system owners can access contest configuration.</p>
      </div>
    </div>

    <div v-else-if="contest" class="config-container">
      <div class="header">
        <h2>Contest Configuration</h2>
        <p>Modify settings and manage jury members for <strong>{{ contest.name }}</strong></p>
      </div>

      <div class="tabs">
        <button :class="{'active': activeTab === 'basic'}" @click="activeTab = 'basic'">Basic Info</button>
        <button :class="{'active': activeTab === 'rules'}" @click="activeTab = 'rules'">Rules</button>
        <button :class="{'active': activeTab === 'talk'}" @click="activeTab = 'talk'">Talk Page</button>
        <button :class="{'active': activeTab === 'jury'}" @click="activeTab = 'jury'">Jury Management</button>
      </div>

      <div v-if="activeTab !== 'jury'" class="settings-form">
        <div v-if="activeTab === 'basic'" class="form-section">
          <div class="form-group">
            <label>Contest Name</label>
            <cdx-text-input v-model="editName" />
          </div>
          <div class="form-group">
            <label>Start Date & Time (UTC)</label>
            <div style="display:flex;gap:8px;">
              <input type="date" v-model="editStartDate" class="native-input" />
              <input type="time" v-model="editStartTime" class="native-input" />
            </div>
          </div>
          <div class="form-group">
            <label>End Date & Time (UTC)</label>
            <div style="display:flex;gap:8px;">
              <input type="date" v-model="editEndDate" class="native-input" />
              <input type="time" v-model="editEndTime" class="native-input" />
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'rules'" class="form-section">
          <div class="rule-item"><cdx-checkbox v-model="editMustBeCreator">Submitter must be creator</cdx-checkbox></div>
          <div class="rule-item"><cdx-checkbox v-model="editMainspaceOnly">Mainspace Only (Namespace 0)</cdx-checkbox></div>
          <div class="rule-item"><cdx-checkbox v-model="editNoRedirect">Disallow Redirects</cdx-checkbox></div>
          <div class="rule-item"><cdx-checkbox v-model="editNoDisambig">Disallow Disambiguation</cdx-checkbox></div>
          <div class="rule-item"><cdx-checkbox v-model="editAllowSelfReview">Allow Self Review (for Jury)</cdx-checkbox></div>
          <div class="form-group">
            <label>Min Bytes</label>
            <input type="number" v-model="editMinBytes" class="native-input" />
          </div>
          <div class="form-group">
            <label>Min Words</label>
            <input type="number" v-model="editMinWords" class="native-input" />
          </div>
          <div class="form-group">
            <label>Min References</label>
            <input type="number" v-model="editMinRefs" class="native-input" />
          </div>
        </div>

        <div v-if="activeTab === 'talk'" class="form-section">
          <div class="rule-item"><cdx-checkbox v-model="editAddTalkTemplate">Enable Automatic Talk Page Template</cdx-checkbox></div>
          <div v-if="editAddTalkTemplate" class="form-group mt-3">
            <label>Template Name</label>
            <cdx-text-input v-model="editTalkTemplateName" placeholder="e.g. উইকিঅভিধান প্রতিযোগিতা ২০২৬" />
          </div>
          <div v-if="editAddTalkTemplate" class="rule-item mt-3"><cdx-checkbox v-model="editIncludeTalkHeader">Include {{ talkHeaderLabel }} at top</cdx-checkbox></div>
          
          <div v-if="editAddTalkTemplate" class="preview-box mt-4">
            <strong>Preview:</strong>
            <pre>{{ wikitextPreview }}</pre>
          </div>
        </div>

        <div class="actions">
          <button class="save-btn" @click="saveSettings">Save Settings</button>
        </div>
      </div>

      <div v-if="activeTab === 'jury'" class="jury-section">
        <div class="jury-add-card">
          <h3>Add Jury Members</h3>
          <div class="search-wrap">
            <input type="text" v-model="jurySearchValue" placeholder="Search Wikimedia username..." class="native-input" style="width: 100%; margin-bottom: 8px;" />
            <div v-if="juryMenuItems.length" class="suggestions">
              <div v-for="item in juryMenuItems" :key="item.value" @click="juryUsername = item.value" class="suggestion-item">
                {{ item.label }}
              </div>
            </div>
          </div>
          <div v-if="juryTags.length" class="tags">
            <span v-for="tag in juryTags" :key="tag" class="tag">
              {{ tag }}
              <button class="remove-tag" @click="removeJuryTag(tag)">&times;</button>
            </span>
          </div>
          <button class="save-btn mt-3" @click="handleAssignJury" :disabled="!juryTags.length">Assign Selected</button>
        </div>

        <div class="jury-list mt-4">
          <h3>Current Jury Members</h3>
          <table class="jury-table">
            <thead>
              <tr><th>Username</th><th>Actions</th></tr>
            </thead>
            <tbody>
              <tr v-for="j in juries" :key="j">
                <td>{{ j }}</td>
                <td><button class="remove-btn" @click="handleUnassignJury(j)">Remove</button></td>
              </tr>
              <tr v-if="!juries.length"><td colspan="2">No jury assigned.</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.config-page { padding: 32px; max-width: 800px; margin: 0 auto; color: #e2e8f0; }
.header h2 { font-size: 1.8rem; margin-bottom: 8px; color: #ffffff; }
.header p { color: #9ca3af; margin-bottom: 24px; }

.tabs { display: flex; gap: 8px; margin-bottom: 24px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; }
.tabs button { background: none; border: none; color: #9ca3af; padding: 8px 16px; cursor: pointer; font-size: 1rem; border-radius: 6px; }
.tabs button:hover { background: rgba(255,255,255,0.05); }
.tabs button.active { color: #f9fafb; font-weight: 600; background: rgba(255,255,255,0.07); }

.form-section { background: #0f0f0f; padding: 24px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06); }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 6px; font-weight: 500; color: #cbd5e1; }
.native-input { background: #111111; border: 1px solid rgba(255,255,255,0.1); color: #e5e7eb; padding: 9px 13px; border-radius: 6px; width: 100%; box-sizing: border-box; font-family: inherit; }
.rule-item { margin-bottom: 12px; }
.mt-3 { margin-top: 16px; }
.mt-4 { margin-top: 24px; }

.preview-box { background: #000; padding: 12px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); }
.preview-box pre { color: #d1d5db; margin-top: 8px; font-family: monospace; white-space: pre-wrap; }

.actions { margin-top: 24px; display: flex; justify-content: flex-end; }
.save-btn { background: #2563eb; color: #ffffff; border: none; padding: 10px 20px; border-radius: 6px; font-weight: 700; cursor: pointer; transition: background 0.15s; }
.save-btn:hover { background: #1d4ed8; }
.save-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.jury-add-card, .jury-list { background: #0f0f0f; padding: 24px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06); }
.jury-add-card h3, .jury-list h3 { margin-top: 0; color: #ffffff; margin-bottom: 16px; font-size: 1.2rem; }
.suggestions { background: #1a1a1a; border: 1px solid #333333; border-radius: 6px; max-height: 150px; overflow-y: auto; margin-bottom: 12px; }
.suggestion-item { padding: 8px 12px; cursor: pointer; transition: background 0.1s; }
.suggestion-item:hover { background: rgba(255,255,255,0.07); }
.tags { display: flex; flex-wrap: wrap; gap: 8px; }
.tag { background: rgba(255,255,255,0.1); color: #e5e7eb; padding: 4px 10px; border-radius: 14px; font-size: 0.82rem; display: flex; align-items: center; gap: 6px; }
.remove-tag { background: none; border: none; color: white; font-weight: bold; cursor: pointer; padding: 0; }

.jury-table { width: 100%; border-collapse: collapse; }
.jury-table th, .jury-table td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }
.jury-table th { color: #9ca3af; text-transform: uppercase; font-size: 0.8rem; }
.remove-btn { background: rgba(255,255,255,0.1); color: #d1d5db; border: 1px solid rgba(255,255,255,0.1); padding: 5px 11px; border-radius: 4px; cursor: pointer; font-size: 0.82rem; }
.remove-btn:hover { background: rgba(255,255,255,0.1); }

.toast-banner { position: fixed; bottom: 20px; right: 20px; background: #1f1f1f; border: 1px solid rgba(255,255,255,0.1); color: #e5e7eb; padding: 12px 20px; border-radius: 8px; display: flex; gap: 8px; font-weight: 600; font-size: 0.88rem; box-shadow: 0 8px 24px rgba(0,0,0,0.5); z-index: 1000; }
.toast-error { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.1); color: #9ca3af; }

.loading-state { text-align: center; padding: 40px; color: #9ca3af; }
.unauthorized-banner { text-align: center; padding: 40px; }
.unauthorized-content { background: rgba(255,255,255,0.05); padding: 40px; border-radius: 8px; display: inline-block; border: 1px solid rgba(255,255,255,0.1); }
</style>
