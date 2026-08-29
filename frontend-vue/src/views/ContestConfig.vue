<script setup>
import { ref, onMounted, inject, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { CdxTextInput, CdxCheckbox } from '@wikimedia/codex';
import { contestTimeToUtcIso, utcToContestTimeParts } from '../utils/datetime';

const route = useRoute();
const router = useRouter();
const user = inject('user');

const contest = ref(null);
const isLoading = ref(true);
const toastMessage = ref('');
const toastIsError = ref(false);
const talkHeaderLabel = '{{আলাপ পাতা}}';

const activeTab = ref('basic'); // 'basic', 'rules', 'talk', 'jury', 'integrity'

// ── Contest integrity re-check ─────────────────────────────────────────────
// Articles are validated once, at submission. A page deleted, moved, turned
// into a redirect, or blanked afterwards is never noticed, and can still be
// sitting in the accepted column when results are published. This re-runs
// those checks against the wiki as it stands now and reports what no longer
// holds -- it deliberately changes nothing, since a flagged article may have
// been moved or deleted for reasons that have nothing to do with the contest.
const integrityScope = ref('accepted');
const integrityReport = ref(null);
const integrityError = ref('');
const isCheckingIntegrity = ref(false);

const ISSUE_LABELS = {
  missing: 'No longer in mainspace',
  redirect: 'Now a redirect',
  below_min_bytes: 'Below the size rule',
  creator_changed: 'Different creator',
};
const issueLabel = (issue) => ISSUE_LABELS[issue] || issue;

const integrityFlagged = computed(() => {
  const report = integrityReport.value;
  if (!report) return 0;
  return report.checked - report.summary.ok;
});

const integrityBreakdown = computed(() => {
  const report = integrityReport.value;
  if (!report) return [];
  return Object.keys(ISSUE_LABELS)
    .map(key => ({ key, label: issueLabel(key), count: report.summary[key] || 0 }))
    .filter(row => row.count > 0);
});

const runIntegrityCheck = async () => {
  if (isCheckingIntegrity.value) return;
  isCheckingIntegrity.value = true;
  integrityError.value = '';
  try {
    const res = await fetch(
      `/api/admin/contests/${contest.value.code}/integrity-check?scope=${integrityScope.value}`,
      { method: 'POST' },
    );
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `Check failed (${res.status})`);
    integrityReport.value = body;
  } catch (e) {
    integrityReport.value = null;
    integrityError.value = e.message || 'Integrity check failed.';
  } finally {
    isCheckingIntegrity.value = false;
  }
};

// Downloaded rather than shown in full: a contest with thousands of flagged
// articles is something you work through in a spreadsheet, not a web table.
const downloadIntegrityReport = () => {
  const report = integrityReport.value;
  if (!report) return;
  const rows = [['Article ID', 'Title', 'Submitted by', 'Status', 'Issue', 'Detail']];
  for (const issue of report.issues) {
    rows.push([issue.article_id, issue.title, issue.submitted_by || '', issue.status, issueLabel(issue.issue), issue.detail || '']);
  }
  const csv = rows
    .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n');
  // BOM so Excel opens the Bengali/Devanagari titles as UTF-8.
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${report.contest.code}-integrity-${report.scope}.csv`;
  link.click();
  URL.revokeObjectURL(url);
};
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
const juries = ref([]);
const jurySearchValue = ref('');
const juryUsername = ref('');
const juryMenuItems = ref([]);
const juryTags = ref([]);
const juryRestrictions = ref([]);
const restrictionJury = ref('');
const restrictionSubmitter = ref('');
const bannedUsers = ref([]);
const banUsername = ref('');

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
      juryRestrictions.value = c.jury_restrictions || [];
      bannedUsers.value = (c.banned_users || []).map((username, index) => ({ id: `legacy-${index}`, username }));
      
      editName.value = c.name;
      const start = utcToContestTimeParts(c.start_date);
      editStartDate.value = start.date;
      editStartTime.value = start.time;
      const end = utcToContestTimeParts(c.end_date);
      editEndDate.value = end.date;
      editEndTime.value = end.time;
      
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
        start_date: contestTimeToUtcIso(editStartDate.value, editStartTime.value),
        end_date: contestTimeToUtcIso(editEndDate.value, editEndTime.value),
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

const handleAddRestriction = async () => {
  if (!restrictionJury.value || !restrictionSubmitter.value) {
    showToast('Choose both a jury member and a submitter.', true);
    return;
  }
  try {
    const res = await fetch(`/api/admin/contests/${contest.value.code}/jury-restrictions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contest_code: contest.value.code, jury_username: restrictionJury.value, submitter_username: restrictionSubmitter.value })
    });
    if (!res.ok) throw new Error('Failed');
    showToast(`Restricted ${restrictionJury.value} from ${restrictionSubmitter.value}'s articles.`);
    restrictionJury.value = '';
    restrictionSubmitter.value = '';
    await fetchContest();
  } catch (e) { showToast('Failed to add restriction.', true); }
};

const handleDeleteRestriction = async (restriction) => {
  try {
    const res = await fetch(`/api/admin/contests/${contest.value.code}/jury-restrictions/${restriction.id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed');
    juryRestrictions.value = juryRestrictions.value.filter(item => item.id !== restriction.id);
    showToast('Jury restriction removed.');
  } catch (e) { showToast('Failed to remove restriction.', true); }
};

const handleBanUser = async () => {
  const username = banUsername.value.trim();
  if (!username) {
    showToast('Enter a Wikimedia username.', true);
    return;
  }
  try {
    const res = await fetch(`/api/admin/contests/${contest.value.code}/banned-users`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contest_code: contest.value.code, username })
    });
    if (!res.ok) throw new Error('Failed');
    banUsername.value = '';
    showToast(`${username}'s articles are hidden from review-v2.`);
    await fetchContest();
  } catch (e) { showToast('Failed to ban user.', true); }
};

const handleUnbanUser = async (ban) => {
  if (!String(ban.id).match(/^\d+$/)) return;
  try {
    const res = await fetch(`/api/admin/contests/${contest.value.code}/banned-users/${ban.id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed');
    bannedUsers.value = bannedUsers.value.filter(item => item.id !== ban.id);
    showToast(`${ban.username} can appear in review-v2 again.`);
  } catch (e) { showToast('Failed to remove ban.', true); }
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

const enabledRuleCount = computed(() => [
  editMustBeCreator.value,
  editMainspaceOnly.value,
  editNoRedirect.value,
  editNoDisambig.value,
  editAllowSelfReview.value
].filter(Boolean).length);
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
        <div class="header-title-row">
          <div>
            <span class="config-kicker">Owner controls</span>
            <h2>Contest Configuration</h2>
          </div>
          <code class="config-code">{{ contest.code }}</code>
        </div>
        <p>Modify settings and manage jury members for <strong>{{ contest.name }}</strong></p>
        <div class="config-summary-strip">
          <div><strong>{{ contest.articles_count || 0 }}</strong><span>submissions</span></div>
          <div><strong>{{ contest.juries?.length || 0 }}</strong><span>jury members</span></div>
          <div><strong>{{ enabledRuleCount }}/5</strong><span>active controls</span></div>
          <div><strong>{{ bannedUsers.length }}</strong><span>review exclusions</span></div>
        </div>
      </div>

      <div class="tabs">
        <button :class="{'active': activeTab === 'basic'}" @click="activeTab = 'basic'">Basic Info</button>
        <button :class="{'active': activeTab === 'rules'}" @click="activeTab = 'rules'">Rules</button>
        <button :class="{'active': activeTab === 'talk'}" @click="activeTab = 'talk'">Talk Page</button>
        <button :class="{'active': activeTab === 'jury'}" @click="activeTab = 'jury'">Jury Management</button>
        <button :class="{'active': activeTab === 'integrity'}" @click="activeTab = 'integrity'">Integrity</button>
      </div>

      <div v-if="activeTab !== 'jury' && activeTab !== 'integrity'" class="settings-form">
        <div v-if="activeTab === 'basic'" class="form-section">
          <div class="form-group">
            <label>Contest Name</label>
            <cdx-text-input v-model="editName" />
          </div>
          <div class="form-group">
            <label>Start Date & Time (BST)</label>
            <div style="display:flex;gap:8px;">
              <input type="date" v-model="editStartDate" class="native-input" />
              <input type="time" v-model="editStartTime" class="native-input" />
            </div>
          </div>
          <div class="form-group">
            <label>End Date & Time (BST)</label>
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

      <div v-if="activeTab === 'integrity'" class="integrity-section">
        <div class="integrity-card">
          <div class="integrity-intro">
            <h3>Contest integrity re-check</h3>
            <p>
              Articles are checked against the contest rules once, when they're submitted. This re-checks them
              against the wiki as it is now, and flags any that were deleted, moved out of mainspace, turned into
              a redirect, or blanked below the size rule since.
            </p>
            <p class="integrity-note">
              Nothing is changed automatically — this only produces a report for you to act on.
            </p>
          </div>

          <div class="integrity-controls">
            <label class="integrity-scope">
              <span>Check</span>
              <select v-model="integrityScope" :disabled="isCheckingIntegrity">
                <option value="accepted">Accepted articles only</option>
                <option value="all">All articles (except validation failures)</option>
              </select>
            </label>
            <button class="save-btn" :disabled="isCheckingIntegrity" @click="runIntegrityCheck">
              {{ isCheckingIntegrity ? 'Checking…' : 'Run re-check' }}
            </button>
          </div>

          <p v-if="isCheckingIntegrity" class="integrity-progress">
            Querying the wiki replica for every article in scope. On a large contest this can take a moment.
          </p>
          <p v-if="integrityError" class="integrity-error">{{ integrityError }}</p>

          <div v-if="integrityReport && !isCheckingIntegrity" class="integrity-results">
            <div class="integrity-summary">
              <div class="integrity-stat">
                <strong>{{ integrityReport.checked.toLocaleString() }}</strong>
                <span>articles checked</span>
              </div>
              <div class="integrity-stat" :class="integrityFlagged ? 'is-flagged' : 'is-clean'">
                <strong>{{ integrityFlagged.toLocaleString() }}</strong>
                <span>need attention</span>
              </div>
              <div class="integrity-stat is-clean">
                <strong>{{ integrityReport.summary.ok.toLocaleString() }}</strong>
                <span>still valid</span>
              </div>
            </div>

            <p v-if="!integrityFlagged" class="integrity-clean-note">
              Every article in scope still exists and still satisfies the contest rules.
            </p>

            <template v-else>
              <ul class="integrity-breakdown">
                <li v-for="row in integrityBreakdown" :key="row.key">
                  <span class="integrity-badge" :class="`integrity-badge-${row.key}`">{{ row.label }}</span>
                  <strong>{{ row.count.toLocaleString() }}</strong>
                </li>
              </ul>

              <div class="integrity-table-wrap">
                <table class="integrity-table">
                  <thead>
                    <tr>
                      <th>Article</th>
                      <th>Submitted by</th>
                      <th>Issue</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="issue in integrityReport.issues" :key="issue.article_id">
                      <td>
                        <a :href="`https://bn.wiktionary.org/wiki/${encodeURIComponent(issue.title)}`" target="_blank" rel="noopener">{{ issue.title }}</a>
                      </td>
                      <td>{{ issue.submitted_by || '—' }}</td>
                      <td><span class="integrity-badge" :class="`integrity-badge-${issue.issue}`">{{ issueLabel(issue.issue) }}</span></td>
                      <td class="integrity-detail">{{ issue.detail }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <p v-if="integrityReport.truncated" class="integrity-note">
                Showing the first {{ integrityReport.issues.length.toLocaleString() }} of
                {{ integrityFlagged.toLocaleString() }} flagged articles.
              </p>

              <div class="actions">
                <button class="save-btn" @click="downloadIntegrityReport">Download report (CSV)</button>
              </div>
            </template>
          </div>
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

        <div class="jury-list mt-4 restriction-panel">
          <h3>Conflict-of-interest restrictions</h3>
          <p class="restriction-help">Prevent a jury member from judging articles submitted by a specific user. Those articles will be redistributed among the remaining eligible juries.</p>
          <div class="restriction-form">
            <select v-model="restrictionJury" class="native-input" aria-label="Jury member to restrict">
              <option value="">Select jury member</option>
              <option v-for="jury in juries" :key="`restriction-jury-${jury}`" :value="jury">{{ jury }}</option>
            </select>
            <select v-model="restrictionSubmitter" class="native-input" aria-label="Submitter to restrict">
              <option value="">Select submitter</option>
              <option v-for="submitter in (contest.submitters || [])" :key="`restriction-submitter-${submitter}`" :value="submitter">{{ submitter }}</option>
            </select>
            <button class="save-btn" @click="handleAddRestriction" :disabled="!restrictionJury || !restrictionSubmitter">Add restriction</button>
          </div>
          <div v-if="juryRestrictions.length" class="restriction-list">
            <div v-for="restriction in juryRestrictions" :key="restriction.id" class="restriction-row">
              <span><strong>{{ restriction.jury_username }}</strong> cannot judge <strong>{{ restriction.submitter_username }}</strong></span>
              <button class="remove-btn" @click="handleDeleteRestriction(restriction)">Remove</button>
            </div>
          </div>
          <p v-else class="restriction-empty">No jury restrictions configured.</p>
        </div>

        <div class="jury-list mt-4 restriction-panel ban-panel">
          <h3>Hide a submitter from review-v2</h3>
          <p class="restriction-help">Banned users' articles remain in the contest records, but are not copied into the /review-v2 judgment panel.</p>
          <div class="restriction-form ban-form">
            <select v-model="banUsername" class="native-input" aria-label="Submitter to ban">
              <option value="">Select submitter</option>
              <option v-for="submitter in (contest.submitters || [])" :key="`ban-${submitter}`" :value="submitter">{{ submitter }}</option>
            </select>
            <input v-model="banUsername" class="native-input" placeholder="Or enter Wikimedia username" aria-label="Username to ban" />
            <button class="save-btn" @click="handleBanUser" :disabled="!banUsername.trim()">Hide from review-v2</button>
          </div>
          <div v-if="bannedUsers.length" class="restriction-list">
            <div v-for="ban in bannedUsers" :key="ban.id" class="restriction-row">
              <span><strong>{{ ban.username }}</strong> is hidden from review-v2</span>
              <button class="remove-btn" @click="handleUnbanUser(ban)">Restore</button>
            </div>
          </div>
          <p v-else class="restriction-empty">No users are hidden from review-v2.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped src="../styles/views/ContestConfig.css"></style>
