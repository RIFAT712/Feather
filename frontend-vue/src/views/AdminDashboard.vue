<script setup>
import { ref, onMounted, inject, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { CdxButton, CdxTextInput, CdxMessage, CdxCheckbox, CdxLookup } from '@wikimedia/codex';
import { contestTimeToUtcIso, utcToContestTimeParts, formatDate as fmtDate, windowStatus, windowProgress, formatDateTimeDayFirst, dayjs } from '../utils/datetime';

const user = inject('user');
const router = useRouter();

const activeTab = ref('overview'); // 'overview', 'create', 'jury'
const viewMode = ref('grid'); // 'grid', 'table'
const searchFilter = ref('');
const statusFilter = ref('all'); // 'all', 'active', 'upcoming', 'ended'

const contests = ref([]);
const stats = ref({
  total_contests: 0,
  active_contests: 0,
  total_articles: 0,
  accepted_articles: 0,
  total_users: 0,
  total_juries: 0,
  total_banned_users: 0
});

const systemStatus = ref({ cpu_percent: 0, mem_percent: 0, overloaded: false });
let statusInterval = null;

const isLoadingContests = ref(false);
const toastMessage = ref('');
const toastIsError = ref(false);
const showToast = (msg, isError = false) => {
  toastMessage.value = msg;
  toastIsError.value = isError;
  setTimeout(() => {
    toastMessage.value = '';
  }, 4000);
};

const fetchContests = async () => {
  isLoadingContests.value = true;
  try {
    const res = await fetch('/api/contests');
    if (res.ok) contests.value = await res.json();
  } catch (e) {
    console.error("Failed to fetch contests", e);
  } finally {
    isLoadingContests.value = false;
  }
};

const fetchStats = async () => {
  try {
    const res = await fetch('/api/admin/stats');
    if (res.ok) stats.value = await res.json();
  } catch (e) {}
};

const fetchSystemStatus = async () => {
  try {
    const res = await fetch('/api/system/status');
    if (res.ok) systemStatus.value = await res.json();
  } catch(e) {}
};

const systemLogs = ref([]);
const logsSourceFilter = ref('all');
const logsLoading = ref(false);
const fetchLogs = async () => {
  logsLoading.value = true;
  try {
    const res = await fetch('/api/logs?limit=200');
    if (res.ok) {
      const all = await res.json();
      systemLogs.value = all.filter(l => l.type === 'system');
    }
  } catch(e) {}
  finally { logsLoading.value = false; }
};

const filteredLogs = computed(() => {
  if (logsSourceFilter.value === 'all') return systemLogs.value;
  return systemLogs.value.filter(l => l.source === logsSourceFilter.value);
});

const logSources = computed(() => {
  const s = new Set(systemLogs.value.map(l => l.source));
  return ['all', ...Array.from(s)];
});

const expandedLogId = ref(null);
const toggleLogExpand = (id) => {
  expandedLogId.value = expandedLogId.value === id ? null : id;
};

const refreshData = async () => {
  await Promise.all([fetchContests(), fetchStats(), fetchSystemStatus(), fetchLogs()]);
};

watch(user, (newVal) => {
  if (newVal?.role === 'owner') {
    refreshData();
    if (!statusInterval) {
      statusInterval = setInterval(fetchSystemStatus, 3000);
    }
  } else {
    clearInterval(statusInterval);
    statusInterval = null;
  }
}, { immediate: true });
// Both of these used to parse the API's offset-less UTC strings with a bare
// `new Date(...)`, which JS reads as local time -- so a contest showed as
// 'active'/'ended' and its progress bar filled up six hours early or late for
// a viewer in Bangladesh, while formatDate() below (which did append a 'Z')
// showed the correct dates right next to it.
const getContestStatus = (c) => windowStatus(c.start_date, c.end_date);

const getContestProgress = (c) => windowProgress(c.start_date, c.end_date);
const filteredContests = computed(() => {
  return contests.value.filter(c => {
    const matchesSearch = c.name.toLowerCase().includes(searchFilter.value.toLowerCase()) ||
                          c.code.toLowerCase().includes(searchFilter.value.toLowerCase());
    const status = getContestStatus(c);
    const matchesStatus = statusFilter.value === 'all' || status === statusFilter.value;
    return matchesSearch && matchesStatus;
  });
});
const formSubTab = ref('basic'); // 'basic', 'rules', 'talk', 'governance'
const editFormSubTab = ref('basic');
const name = ref('');
const startDate = ref('');
const startTime = ref('00:00');
const endDate = ref('');
const endTime = ref('23:59');
const mustBeCreator = ref(true);
const minBytes = ref(0);
const minWords = ref(0);
const minRefs = ref(0);
const noRedirect = ref(true);
const noDisambig = ref(true);
const mainspaceOnly = ref(true);
const allowSelfReview = ref(false);
const addTalkTemplate = ref(false);
const talkTemplateName = ref('');
const includeTalkHeader = ref(true);

const createWikitextPreview = computed(() => {
  if (!addTalkTemplate.value) return '';
  let tName = talkTemplateName.value.trim() || 'উইকিঅভিধান প্রতিযোগিতা ২০২৬';
  if (!tName.startsWith('{{')) {
    tName = `{{${tName}}}`;
  }
  let text = '';
  if (includeTalkHeader.value) {
    text += '{{আলাপ পাতা}}\n';
  }
  text += tName;
  return text;
});

const createDurationLabel = computed(() => {
  if (!startDate.value || !endDate.value) return 'Set contest dates';
  // Interpret the form's date/time inputs in the contest timezone, the same
  // way handleCreate() does when it submits them -- parsing them in the
  // viewer's local zone made the preview disagree with what got saved.
  const start = dayjs(contestTimeToUtcIso(startDate.value, startTime.value || '00:00'));
  const end = dayjs(contestTimeToUtcIso(endDate.value, endTime.value || '23:59'));
  const days = Math.round(end.diff(start) / 86400000);
  return days >= 0 ? `${days + 1} day${days === 0 ? '' : 's'} scheduled` : 'Check date order';
});

const createRuleCount = computed(() => [mustBeCreator.value, mainspaceOnly.value, noRedirect.value, noDisambig.value]
  .filter(Boolean).length);

const isCreating = ref(false);
const handleCreate = async () => {
  if (!name.value || !startDate.value || !endDate.value) {
    showToast("Please fill in all required fields (Name, Start & End Date).", true);
    return;
  }
  isCreating.value = true;
  try {
    const res = await fetch('/api/admin/contests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.value,
        start_date: contestTimeToUtcIso(startDate.value, startTime.value),
        end_date: contestTimeToUtcIso(endDate.value, endTime.value),
        rule_must_be_creator: mustBeCreator.value,
        min_bytes: Number(minBytes.value) || 0,
        min_words: Number(minWords.value) || 0,
        min_refs: Number(minRefs.value) || 0,
        rule_no_redirect: noRedirect.value,
        rule_no_disambig: noDisambig.value,
        rule_mainspace_only: mainspaceOnly.value,
        allow_self_review: allowSelfReview.value,
        add_talk_template: addTalkTemplate.value,
        talk_template_name: talkTemplateName.value.trim(),
        include_talk_header: includeTalkHeader.value
      })
    });
    if (!res.ok) throw new Error("Create failed");
    const created = await res.json();
    if (createJuryTags.value.length > 0) {
      await fetch('/api/admin/assign-jury', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contest_code: created.code, wiki_usernames: createJuryTags.value })
      });
    }
    showToast(`🎉 Contest created! ${createJuryTags.value.length > 0 ? createJuryTags.value.length + ' jury member(s) assigned.' : ''}`);
    createJuryTags.value = [];
    resetCreateForm();
    activeTab.value = 'overview';
    refreshData();
  } catch (e) {
    showToast("Error creating contest.", true);
  } finally {
    isCreating.value = false;
  }
};

const resetCreateForm = () => {
  name.value = ''; startDate.value = ''; endDate.value = '';
  mustBeCreator.value = true; minBytes.value = 0; minWords.value = 0; minRefs.value = 0;
  noRedirect.value = true; noDisambig.value = true; mainspaceOnly.value = true; allowSelfReview.value = false;
  addTalkTemplate.value = false; talkTemplateName.value = ''; includeTalkHeader.value = true;
  createJuryTags.value = []; createJurySearchValue.value = ''; createJuryMenuItems.value = [];
  formSubTab.value = 'basic';
};
const handleCloneContest = (c) => {
  name.value = `Copy of ${c.name}`;
  const start = utcToContestTimeParts(c.start_date);
  startDate.value = start.date;
  startTime.value = start.time;
  const end = utcToContestTimeParts(c.end_date);
  endDate.value = end.date;
  endTime.value = end.time;
  
  mustBeCreator.value = c.rule_must_be_creator ?? true;
  minBytes.value = c.min_bytes ?? 0;
  minWords.value = c.min_words ?? 0;
  minRefs.value = c.min_refs ?? 0;
  noRedirect.value = c.rule_no_redirect ?? true;
  noDisambig.value = c.rule_no_disambig ?? true;
  mainspaceOnly.value = c.rule_mainspace_only ?? true;
  allowSelfReview.value = c.allow_self_review ?? false;
  addTalkTemplate.value = c.add_talk_template ?? false;
  talkTemplateName.value = c.talk_template_name ?? '';
  includeTalkHeader.value = c.include_talk_header ?? true;
  
  activeTab.value = 'create';
  showToast(`📋 Cloned rules from "${c.name}" into form!`);
};
const handleExportCSV = (code) => {
  window.open(`/api/admin/contests/${code}/export/csv`, '_blank');
  showToast(`📥 Exporting CSV for contest ${code}...`);
};
const handleDownloadDatabase = () => {
  window.location.href = '/api/admin/backup/download';
};

const handleExportJSON = async (code, cName) => {
  try {
    const res = await fetch(`/api/admin/contests/${code}/export/json`);
    if (!res.ok) throw new Error("Export failed");
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `contest_${code}_${cName.replace(/\s+/g, '_')}_export.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`📥 Downloaded JSON report for "${cName}"`);
  } catch (e) {
    showToast("Failed to export contest JSON data", true);
  }
};
const handleDelete = async (code, cName) => {
  if (!confirm(`Are you sure you want to permanently delete contest "${cName}"? All articles and reviews will be removed.`)) return;
  try {
    const res = await fetch(`/api/admin/contests/${code}`, { method: 'DELETE' });
    if (res.ok) {
      showToast(`Contest "${cName}" deleted.`);
      refreshData();
    }
  } catch (e) {
    showToast("Failed to delete contest", true);
  }
};
const editingContest = ref(null);
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

const editWikitextPreview = computed(() => {
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

const openEditModal = (c) => {
  editingContest.value = c;
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
  editFormSubTab.value = 'basic';
};

const closeEditModal = () => { editingContest.value = null; };

const saveEdit = async () => {
  try {
    const res = await fetch(`/api/admin/contests/${editingContest.value.code}`, {
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
    showToast("Contest settings updated!");
    closeEditModal();
    refreshData();
  } catch (e) {
    showToast("Error updating contest.", true);
  }
};
const selectedJuryContestCode = ref('');
const selectedJuryContest = computed(() => {
  return contests.value.find(c => c.code === selectedJuryContestCode.value) || null;
});
const jurySearchValue = ref('');
const juryMenuItems = ref([]);
const juryMenuVisible = ref(false);
const juryTags = ref([]);
const createJurySearchValue = ref('');
const createJuryMenuItems = ref([]);
const createJuryMenuVisible = ref(false);
const createJuryTags = ref([]);

const fetchJuryUsers = async (prefix, menuItemsRef, menuVisibleRef, tagsRef, existingFn) => {
  if (!prefix || prefix.trim().length < 2) {
    menuItemsRef.value = [];
    menuVisibleRef.value = false;
    return;
  }
  const cleanPrefix = prefix.trim();
  const url = `https://bn.wiktionary.org/w/api.php?action=query&list=allusers&auprefix=${encodeURIComponent(cleanPrefix)}&format=json&origin=*`;
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (data.query?.allusers) {
      const existing = existingFn();
      menuItemsRef.value = data.query.allusers
        .map(u => ({ value: u.name, label: u.name }))
        .filter(u => !existing.includes(u.value) && !tagsRef.value.includes(u.value));
      menuVisibleRef.value = menuItemsRef.value.length > 0;
    }
  } catch (e) {}
};

let juryTimeout;
watch(jurySearchValue, (newVal) => {
  clearTimeout(juryTimeout);
  juryTimeout = setTimeout(() => {
    fetchJuryUsers(newVal, juryMenuItems, juryMenuVisible, juryTags, () => selectedJuryContest.value?.juries || []);
  }, 300);
});

let createJuryTimeout;
watch(createJurySearchValue, (newVal) => {
  clearTimeout(createJuryTimeout);
  createJuryTimeout = setTimeout(() => {
    fetchJuryUsers(newVal, createJuryMenuItems, createJuryMenuVisible, createJuryTags, () => []);
  }, 300);
});

const selectJuryUser = (username) => {
  if (username && !juryTags.value.includes(username)) juryTags.value.push(username);
  jurySearchValue.value = '';
  juryMenuItems.value = [];
  juryMenuVisible.value = false;
};

const selectCreateJuryUser = (username) => {
  if (username && !createJuryTags.value.includes(username)) createJuryTags.value.push(username);
  createJurySearchValue.value = '';
  createJuryMenuItems.value = [];
  createJuryMenuVisible.value = false;
};

const removeJuryTag = (tag) => {
  juryTags.value = juryTags.value.filter(t => t !== tag);
};

const handleAssignJury = async () => {
  if (!selectedJuryContestCode.value) {
    showToast("Please select a contest.", true);
    return;
  }
  if (!juryTags.value.length) {
    showToast("Please add at least one username to assign.", true);
    return;
  }
  try {
    const res = await fetch('/api/admin/assign-jury', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contest_code: selectedJuryContestCode.value,
        wiki_usernames: juryTags.value
      })
    });
    if (!res.ok) throw new Error("Failed");
    const data = await res.json();
    showToast(`✅ Assigned ${data.added.length} jury member(s)!`);
    juryTags.value = [];
    refreshData();
  } catch (e) {
    showToast("Error assigning jury.", true);
  }
};

const handleUnassignJury = async (contestCode, username) => {
  if (!confirm(`Remove "${username}" from jury roster for this contest?`)) return;
  try {
    const res = await fetch('/api/admin/unassign-jury', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contest_code: contestCode,
        wiki_username: username
      })
    });
    if (res.ok) {
      showToast(`Removed ${username} from jury.`);
      refreshData();
    }
  } catch (e) {
    showToast("Failed to remove jury member", true);
  }
};

const openJuryHubForContest = (code) => {
  selectedJuryContestCode.value = code;
  activeTab.value = 'jury';
};

const formatDate = (iso) => fmtDate(iso);

// system_logs rows are also naive UTC. The template used to concatenate 'Z'
// unconditionally, so a timestamp that already carried one produced
// "…00:00ZZ" -> Invalid Date.
const formatLogTimestamp = (iso) => formatDateTimeDayFirst(iso);
</script>

<template>
  <div class="admin-suite">
        <transition name="toast">
      <div v-if="toastMessage" class="toast-banner" :class="{ 'toast-error': toastIsError }">
        <span class="toast-icon">{{ toastIsError ? '⚠️' : '✨' }}</span>
        <span>{{ toastMessage }}</span>
      </div>
    </transition>

        <div v-if="user && user.role !== 'owner'" class="unauthorized-banner">
      <div class="unauthorized-content">
        <span class="icon">⛔</span>
        <h2>Owner Portal Restricted</h2>
        <p>You are logged in as <strong>{{ user.wiki_username }}</strong> ({{ user.role }}). Administrative control panels are restricted to System Owners.</p>
      </div>
    </div>

    <template v-else-if="user && user.role === 'owner'">
            <div class="admin-header-card">
        <div class="header-main">
          <div class="header-title-group">
            <div class="owner-badge">
              <span class="star-icon">★</span> System Owner Portal
            </div>
            <h1 class="suite-title">Admin Management Suite</h1>
            <p class="suite-desc">Configure contest rules, govern juries, automate talk page templates, & export platform data.</p>
          </div>
          <div class="header-actions">
            <button class="action-btn primary" @click="activeTab = 'create'; formSubTab = 'basic';">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              New Contest
            </button>
            <button class="action-btn secondary" @click="refreshData">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
              Refresh
            </button>
            <button class="action-btn secondary" @click="handleDownloadDatabase" title="Download a database backup">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>
              Download Backup
            </button>
          </div>
        </div>

                <div class="kpi-grid">
          <div class="kpi-card indigo">
            <div class="kpi-icon">🏆</div>
            <div class="kpi-info">
              <span class="kpi-val">{{ stats.total_contests }}</span>
              <span class="kpi-lbl">Total Contests</span>
            </div>
            <div class="kpi-sub">
              <span class="pill-active">{{ stats.active_contests }} Active Now</span>
            </div>
          </div>

          <div class="kpi-card emerald">
            <div class="kpi-icon">📝</div>
            <div class="kpi-info">
              <span class="kpi-val">{{ stats.total_articles }}</span>
              <span class="kpi-lbl">Total Submissions</span>
            </div>
            <div class="kpi-sub">
              <span class="pill-green">{{ stats.accepted_articles }} Accepted</span>
            </div>
          </div>

          <div class="kpi-card violet">
            <div class="kpi-icon">🛡️</div>
            <div class="kpi-info">
              <span class="kpi-val">{{ stats.total_juries }}</span>
              <span class="kpi-lbl">Jury Assignments</span>
            </div>
            <div class="kpi-sub">Across All Contests</div>
          </div>

          <div class="kpi-card sky">
            <div class="kpi-icon">👥</div>
            <div class="kpi-info">
              <span class="kpi-val">{{ stats.total_users }}</span>
              <span class="kpi-lbl">Registered Editors</span>
            </div>
            <div class="kpi-sub">Wikimedia Participants</div>
          </div>
          
          <div class="kpi-card rose">
            <div class="kpi-icon">⚙️</div>
            <div class="kpi-info">
              <span class="kpi-val">{{ systemStatus.cpu_percent }}%</span>
              <span class="kpi-lbl">Server CPU</span>
            </div>
            <div class="kpi-sub">
              <span :class="systemStatus.cpu_percent > 85 ? 'text-red-400 font-bold' : ''">Load</span>
            </div>
          </div>
          
          <div class="kpi-card amber">
            <div class="kpi-icon">💾</div>
            <div class="kpi-info">
              <span class="kpi-val">{{ systemStatus.mem_percent }}%</span>
              <span class="kpi-lbl">Server RAM</span>
            </div>
            <div class="kpi-sub">
              <span :class="systemStatus.mem_percent > 85 ? 'text-red-400 font-bold' : ''">Utilization</span>
            </div>
          </div>

          <div class="kpi-card slate">
            <div class="kpi-icon">🚷</div>
            <div class="kpi-info">
              <span class="kpi-val">{{ stats.total_banned_users }}</span>
              <span class="kpi-lbl">Review Exclusions</span>
            </div>
            <div class="kpi-sub">Users hidden from review-v2</div>
          </div>
        </div>
      </div>

            <div class="suite-tabs-nav">
        <button class="nav-tab" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
          Contests & Rules Overview
          <span class="tab-badge">{{ contests.length }}</span>
        </button>

        <button class="nav-tab" :class="{ active: activeTab === 'create' }" @click="activeTab = 'create'">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
          Create Contest (Rules Wizard)
        </button>

        <button class="nav-tab" :class="{ active: activeTab === 'jury' }" @click="activeTab = 'jury'">
          <span class="icon">👥</span>
          Jury Management
        </button>
        <button class="nav-tab" :class="{ active: activeTab === 'logs' }" @click="activeTab = 'logs'">
          <span class="icon">📋</span>
          System Logs
        </button>
      </div>

            <div v-if="activeTab === 'overview'" class="tab-pane">
                <div class="controls-card">
          <div class="search-box">
            <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input v-model="searchFilter" placeholder="Search contests by name or code..." class="search-input" />
          </div>

          <div class="filter-group">
            <span class="filter-label">Status:</span>
            <div class="chip-filter">
              <button :class="{ active: statusFilter === 'all' }" @click="statusFilter = 'all'">All</button>
              <button :class="{ active: statusFilter === 'active' }" @click="statusFilter = 'active'">Active</button>
              <button :class="{ active: statusFilter === 'upcoming' }" @click="statusFilter = 'upcoming'">Upcoming</button>
              <button :class="{ active: statusFilter === 'ended' }" @click="statusFilter = 'ended'">Ended</button>
            </div>
          </div>

          <div class="view-switch">
            <button :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'" title="Grid View">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
            </button>
            <button :class="{ active: viewMode === 'table' }" @click="viewMode = 'table'" title="Table View">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
          </div>
        </div>

                <div v-if="viewMode === 'grid'" class="contests-grid">
          <div v-for="c in filteredContests" :key="c.code" class="contest-card" :class="getContestStatus(c)">
            <div class="card-top">
              <div class="card-status-badge" :class="getContestStatus(c)">
                <span class="status-dot"></span>
                {{ getContestStatus(c).toUpperCase() }}
              </div>
              <code class="contest-code-badge">{{ c.code }}</code>
            </div>

            <h3 class="card-title">{{ c.name }}</h3>

            <div class="card-dates">
              <span>📅 {{ formatDate(c.start_date) }}</span>
              <span>→</span>
              <span>{{ formatDate(c.end_date) }}</span>
            </div>

                        <div class="progress-container">
              <div class="progress-bar-bg">
                <div class="progress-bar-fill" :style="{ width: getContestProgress(c) + '%' }"></div>
              </div>
              <span class="progress-txt">{{ getContestProgress(c) }}% elapsed</span>
            </div>

                        <div class="card-rules-list">
              <span v-if="c.rule_must_be_creator" class="rule-tag font-medium">👤 Must Be Creator</span>
              <span v-if="c.min_bytes > 0" class="rule-tag amber">📐 Min {{ c.min_bytes }} B</span>
              <span v-if="c.min_words > 0" class="rule-tag emerald">📝 Min {{ c.min_words }} words</span>
              <span v-if="c.min_refs > 0" class="rule-tag sky">📚 Min {{ c.min_refs }} ref(s)</span>
              <span v-if="c.rule_no_redirect" class="rule-tag violet">🚫 No Redirects</span>
              <span v-if="c.rule_no_disambig" class="rule-tag rose">🔀 No Disambig</span>
              <span v-if="c.rule_mainspace_only" class="rule-tag slate">📁 Mainspace Only</span>
              <span v-if="c.add_talk_template" class="rule-tag indigo">💬 Talk Template</span>
            </div>

                        <div class="card-metrics-row">
              <div class="metric-item">
                <span class="m-val">{{ c.articles_count ?? 0 }}</span>
                <span class="m-lbl">Submitted</span>
              </div>
              <div class="metric-item accent">
                <span class="m-val">{{ c.accepted_count ?? 0 }}</span>
                <span class="m-lbl">Accepted</span>
              </div>
              <div class="metric-item" @click="openJuryHubForContest(c.code)" style="cursor:pointer;" title="Click to manage jury">
                <span class="m-val">{{ c.juries_count ?? 0 }}</span>
                <span class="m-lbl">Jurors ⚙️</span>
              </div>
            </div>

                        <div class="card-actions-bar">
              <router-link :to="'/' + c.code" class="card-btn secondary" title="View Contest Dashboard">↗ View</router-link>
              <button class="card-btn primary" @click="openEditModal(c)" title="Edit Contest Rules & Settings">✏️ Edit</button>
              <button class="card-btn secondary" @click="handleCloneContest(c)" title="Clone as new contest template">📋 Clone</button>
              <button class="card-btn secondary" @click="handleExportCSV(c.code)" title="Export CSV Report">📥 CSV</button>
              <button class="card-btn danger" @click="handleDelete(c.code, c.name)" title="Delete Contest">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </div>

          <div v-if="!filteredContests.length" class="empty-card">
            <span class="icon">🔍</span>
            <p>No contests found matching your filters.</p>
          </div>
        </div>

                <div v-else class="table-card">
          <table class="wikitable-modern">
            <thead>
              <tr>
                <th>Contest Name & Rules</th>
                <th>Code</th>
                <th>Status</th>
                <th>Timeline</th>
                <th>Submissions</th>
                <th>Jury Roster</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in filteredContests" :key="c.code">
                <td>
                  <div class="table-name-cell">
                    <span class="font-bold text-slate-100">{{ c.name }}</span>
                    <div class="rule-badges">
                      <span v-if="c.rule_must_be_creator" class="rule-badge">👤 Must Be Creator</span>
                      <span v-if="c.min_bytes > 0" class="rule-badge amber">📐 Min {{ c.min_bytes }} B</span>
                      <span v-if="c.min_words > 0" class="rule-badge emerald">📝 Min {{ c.min_words }} words</span>
                      <span v-if="c.min_refs > 0" class="rule-badge sky">📚 Min {{ c.min_refs }} refs</span>
                      <span v-if="c.add_talk_template" class="rule-badge indigo">💬 Talk Template: {{ c.talk_template_name }}</span>
                    </div>
                  </div>
                </td>
                <td><code>{{ c.code }}</code></td>
                <td>
                  <span class="card-status-badge mini" :class="getContestStatus(c)">
                    {{ getContestStatus(c).toUpperCase() }}
                  </span>
                </td>
                <td>
                  <div class="timeline-cell">
                    <span>{{ formatDate(c.start_date) }}</span>
                    <span class="text-slate-500">to</span>
                    <span>{{ formatDate(c.end_date) }}</span>
                  </div>
                </td>
                <td>
                  <div class="sub-cell">
                    <span class="font-semibold">{{ c.articles_count ?? 0 }} total</span>
                    <span class="text-emerald-400 text-xs">({{ c.accepted_count ?? 0 }} accepted)</span>
                  </div>
                </td>
                <td>
                  <button class="jury-pill-btn" @click="openJuryHubForContest(c.code)">
                    🛡️ {{ c.juries_count ?? 0 }} Juror(s)
                  </button>
                </td>
                <td class="action-cell">
                  <router-link :to="'/' + c.code" class="icon-action-btn" title="View Contest">↗</router-link>
                  <button class="icon-action-btn" @click="openEditModal(c)" title="Edit Rules">✏️</button>
                  <button class="icon-action-btn" @click="handleCloneContest(c)" title="Clone Contest">📋</button>
                  <button class="icon-action-btn" @click="handleExportCSV(c.code)" title="Export CSV">📥</button>
                  <button class="icon-action-btn danger" @click="handleDelete(c.code, c.name)" title="Delete">🗑️</button>
                </td>
              </tr>
              <tr v-if="!filteredContests.length">
                <td colspan="7" class="text-center py-8 text-slate-400">No contests found matching criteria.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

            <div v-if="activeTab === 'create'" class="tab-pane">
        <div class="form-pane-card">
          <div class="form-pane-header">
            <h2>Create New Contest</h2>
            <p>Configure complete validation constraints, article requirements, jury rules, and talk page templates.</p>
            <div class="create-flow-summary">
              <div class="create-summary-copy">
                <span class="summary-kicker">Contest setup</span>
                <strong>{{ name || 'Untitled contest' }}</strong>
                <span>{{ createDurationLabel }}</span>
              </div>
              <div class="create-summary-stats">
                <div><strong>{{ createRuleCount }}/4</strong><span>core rules</span></div>
                <div><strong>{{ createJuryTags.length }}</strong><span>jury ready</span></div>
                <div><strong>{{ addTalkTemplate ? 'On' : 'Off' }}</strong><span>talk template</span></div>
              </div>
            </div>
          </div>

                    <div class="wizard-sub-tabs mb-6">
            <button class="w-tab" :class="{ active: formSubTab === 'basic' }" @click="formSubTab = 'basic'">
              📌 1. Basic Info & Dates
            </button>
            <button class="w-tab" :class="{ active: formSubTab === 'rules' }" @click="formSubTab = 'rules'">
              ⚙️ 2. Rules
            </button>
            <button class="w-tab" :class="{ active: formSubTab === 'talk' }" @click="formSubTab = 'talk'">
              💬 3. Talk Page Template
            </button>
            <button class="w-tab" :class="{ active: formSubTab === 'governance' }" @click="formSubTab = 'governance'">
              🛡️ 4. Governance & Jury
            </button>
          </div>

                    <div v-if="formSubTab === 'basic'" class="sub-tab-content">
            <div class="form-grid-2">
              <div class="form-group span-2">
                <label class="field-label">Contest Name <span class="req">*</span></label>
                <cdx-text-input v-model="name" placeholder="e.g. Wiktionary Article Contest 2026" />
                <div class="preset-chips mt-2">
                  <span class="chip-lbl">Quick Presets:</span>
                  <button class="preset-chip" @click="name = 'উইকিঅভিধান প্রতিযোগিতা ২০২৬'">উইকিঅভিধান প্রতিযোগিতা ২০২৬</button>
                  <button class="preset-chip" @click="name = 'Wiktionary Edit-a-thon 2026'">Wiktionary Edit-a-thon 2026</button>
                </div>
              </div>

              <div class="form-group">
                <label class="field-label">Start Date & Time (BST) <span class="req">*</span></label>
                <div class="datetime-flex">
                  <input type="date" v-model="startDate" class="native-picker" />
                  <input type="time" v-model="startTime" class="native-picker" />
                </div>
              </div>

              <div class="form-group">
                <label class="field-label">End Date & Time (BST) <span class="req">*</span></label>
                <div class="datetime-flex">
                  <input type="date" v-model="endDate" class="native-picker" />
                  <input type="time" v-model="endTime" class="native-picker" />
                </div>
              </div>
            </div>

            <div class="tab-footer-nav mt-8">
              <button class="submit-btn primary" @click="formSubTab = 'rules'">Next: Rules →</button>
            </div>
          </div>

                    <div v-if="formSubTab === 'rules'" class="sub-tab-content">
            <div class="rules-config-grid">
                            <div class="rule-card-toggle">
                <cdx-checkbox v-model="mustBeCreator">
                  <strong class="text-slate-100">👤 Rule: Submitter MUST be original article creator</strong>
                  <p class="toggle-desc">MediaWiki API / MariaDB replica verifies that the submitter is the original author who created the page.</p>
                </cdx-checkbox>
              </div>

                            <div class="rule-card-toggle">
                <cdx-checkbox v-model="mainspaceOnly">
                  <strong class="text-slate-100">📁 Rule: Mainspace Only (Namespace 0)</strong>
                  <p class="toggle-desc">Blocks talk pages, user sandboxes, category pages, and template pages from submission.</p>
                </cdx-checkbox>
              </div>

                            <div class="rule-card-toggle">
                <cdx-checkbox v-model="noRedirect">
                  <strong class="text-slate-100">🚫 Rule: Disallow Redirect Pages</strong>
                  <p class="toggle-desc">Automatically rejects articles if they are hard or soft redirects to another entry.</p>
                </cdx-checkbox>
              </div>

                            <div class="rule-card-toggle">
                <cdx-checkbox v-model="noDisambig">
                  <strong class="text-slate-100">🔀 Rule: Disallow Disambiguation Pages</strong>
                  <p class="toggle-desc">Automatically rejects disambiguation / index pages (with {{disambig}} template).</p>
                </cdx-checkbox>
              </div>

                            <div class="rule-input-card span-2">
                <label class="field-label">📐 Minimum Article Size (Bytes)</label>
                <div class="flex-input-row">
                  <cdx-text-input v-model.number="minBytes" type="number" placeholder="0 = No limit (e.g. 3500)" />
                  <div class="preset-chips">
                    <button class="preset-chip" :class="{ active: minBytes === 0 }" @click="minBytes = 0">No Limit (0 B)</button>
                    <button class="preset-chip" :class="{ active: minBytes === 1000 }" @click="minBytes = 1000">1,000 Bytes</button>
                    <button class="preset-chip" :class="{ active: minBytes === 3000 }" @click="minBytes = 3000">3,000 Bytes</button>
                    <button class="preset-chip" :class="{ active: minBytes === 5000 }" @click="minBytes = 5000">5,000 Bytes</button>
                  </div>
                </div>
                <p class="field-hint">Articles with total page length under this byte threshold will fail automatic validation.</p>
              </div>

                            <div class="rule-input-card">
                <label class="field-label">📝 Minimum Word Count</label>
                <div class="flex-input-row">
                  <cdx-text-input v-model.number="minWords" type="number" placeholder="0 = No limit" />
                  <div class="preset-chips">
                    <button class="preset-chip" :class="{ active: minWords === 0 }" @click="minWords = 0">0 Words</button>
                    <button class="preset-chip" :class="{ active: minWords === 100 }" @click="minWords = 100">100 Words</button>
                    <button class="preset-chip" :class="{ active: minWords === 300 }" @click="minWords = 300">300 Words</button>
                  </div>
                </div>
                <p class="field-hint">Minimum required text words inside the entry body.</p>
              </div>

                            <div class="rule-input-card">
                <label class="field-label">📚 Minimum References / Citations</label>
                <div class="flex-input-row">
                  <cdx-text-input v-model.number="minRefs" type="number" placeholder="0 = No limit" />
                  <div class="preset-chips">
                    <button class="preset-chip" :class="{ active: minRefs === 0 }" @click="minRefs = 0">0 Refs</button>
                    <button class="preset-chip" :class="{ active: minRefs === 1 }" @click="minRefs = 1">1 Ref</button>
                    <button class="preset-chip" :class="{ active: minRefs === 2 }" @click="minRefs = 2">2 Refs</button>
                  </div>
                </div>
                <p class="field-hint">Minimum required &lt;ref&gt; citation tags in the wikitext.</p>
              </div>
            </div>

            <div class="tab-footer-nav mt-8">
              <button class="submit-btn quiet" @click="formSubTab = 'basic'">← Back</button>
              <button class="submit-btn primary" @click="formSubTab = 'talk'">Next: Talk Page Template →</button>
            </div>
          </div>

                    <div v-if="formSubTab === 'talk'" class="sub-tab-content">
            <div class="rule-card-toggle">
              <cdx-checkbox v-model="addTalkTemplate">
                <strong class="text-slate-100">💬 Feature: Auto-generate Talk Page Template (আলাপ পাতা)</strong>
                <p class="toggle-desc">Generates official wikitext templates for jury members to place on Wiktionary talk pages for accepted articles.</p>
              </cdx-checkbox>

              <div v-if="addTalkTemplate" class="talk-options-expanded mt-4">
                <div class="form-group">
                  <label class="field-label">Talk Page Template Name</label>
                  <cdx-text-input v-model="talkTemplateName" placeholder="e.g. উইকিঅভিধান প্রতিযোগিতা ২০২৬ or {{কথা প্রতিযোগিতা}}" />
                  <p class="field-hint">Specify the template to be placed on the talk page of submitted articles.</p>
                </div>

                <div class="form-group mt-3">
                  <cdx-checkbox v-model="includeTalkHeader">
                    Include default <code>&#123;&#123;আলাপ পাতা&#125;&#125;</code> header at top
                  </cdx-checkbox>
                </div>

                <div v-if="createWikitextPreview" class="wikitext-preview-card mt-4">
                  <div class="preview-head">
                    <span>Generated Talk Page Wikitext Preview:</span>
                  </div>
                  <pre class="code-box"><code>{{ createWikitextPreview }}</code></pre>
                </div>
              </div>
            </div>

            <div class="tab-footer-nav mt-8">
              <button class="submit-btn quiet" @click="formSubTab = 'rules'">← Back</button>
              <button class="submit-btn primary" @click="formSubTab = 'governance'">Next: Governance →</button>
            </div>
          </div>

                    <div v-if="formSubTab === 'governance'" class="sub-tab-content">
            <div class="rule-card-toggle">
              <cdx-checkbox v-model="allowSelfReview">
                <strong class="text-slate-100">🛡️ Allow Jury Self-Review</strong>
                <p class="toggle-desc">If checked, jury members may evaluate articles they submitted themselves. If unchecked (default), self-review is strictly blocked.</p>
              </cdx-checkbox>
            </div>

                        <div class="jury-section mt-6">
              <h3 class="jury-section-title">👥 Add Jury Members</h3>
              <p class="toggle-desc mb-3">Search and add jury members now. They will be assigned automatically when the contest is created.</p>

              <div class="jury-lookup-row" style="position:relative">
                <input
                  v-model="createJurySearchValue"
                  type="text"
                  class="native-picker w-full"
                  placeholder="Search wiki username..."
                  autocomplete="off"
                  @blur="setTimeout(() => { createJuryMenuVisible = false }, 200)"
                />
                <ul v-if="createJuryMenuVisible && createJuryMenuItems.length" class="jury-suggest-dropdown">
                  <li
                    v-for="item in createJuryMenuItems"
                    :key="item.value"
                    @mousedown.prevent="selectCreateJuryUser(item.value)"
                    class="jury-suggest-item"
                  >{{ item.label }}</li>
                </ul>
              </div>

              <div class="jury-tags-row mt-3" v-if="createJuryTags.length">
                <div v-for="tag in createJuryTags" :key="tag" class="juror-chip">
                  <div class="juror-avatar">{{ tag[0].toUpperCase() }}</div>
                  <span class="juror-name">{{ tag }}</span>
                  <button class="unassign-btn" @click="createJuryTags = createJuryTags.filter(t => t !== tag)">&times;</button>
                </div>
              </div>
              <p v-else class="no-jurors-notice" style="margin-top: 0.5rem;">No jury members added yet. You can also add them later from the Jury Command Center.</p>
            </div>

            <div class="form-submit-row mt-8">
              <button class="submit-btn primary" :disabled="isCreating" @click="handleCreate">
                {{ isCreating ? 'Creating Contest...' : '✨ Create Contest' }}
              </button>
              <button class="submit-btn quiet" @click="activeTab = 'overview'">Cancel</button>
            </div>
          </div>
        </div>
      </div>

            <div v-if="activeTab === 'jury'" class="tab-pane">
        <div class="jury-hub-card">
          <div class="form-pane-header">
            <h2>Jury Command Center</h2>
            <p>Assign and manage evaluation jury members for each active writing contest.</p>
          </div>

                    <div class="form-group max-w-lg">
            <label class="field-label">Select Target Contest</label>
            <select v-model="selectedJuryContestCode" class="native-picker w-full">
              <option value="" disabled>-- Select a contest --</option>
              <option v-for="c in contests" :key="c.code" :value="c.code">
                {{ c.name }} (Code: {{ c.code }}) — {{ c.juries_count ?? 0 }} Juror(s)
              </option>
            </select>
          </div>

          <div v-if="selectedJuryContest" class="jury-contest-details mt-6">
            <h3 class="text-indigo-400 font-bold mb-3">
              Current Jury Roster for "{{ selectedJuryContest.name }}"
            </h3>

                        <div class="assigned-jurors-grid">
              <div v-for="username in selectedJuryContest.juries" :key="username" class="juror-chip">
                <div class="juror-avatar">{{ username[0].toUpperCase() }}</div>
                <span class="juror-name">{{ username }}</span>
                <button class="unassign-btn" @click="handleUnassignJury(selectedJuryContest.code, username)" title="Remove juror">
                  &times;
                </button>
              </div>
              <div v-if="!selectedJuryContest.juries?.length" class="no-jurors-notice">
                No jury members assigned to this contest yet.
              </div>
            </div>

                        <div class="add-jury-section mt-6 border-t border-slate-700/50 pt-4">
              <label class="field-label">Add New Jury Members (Type username prefix)</label>
              
              <div class="tag-input-wrapper mt-2" style="position:relative">
                <span v-for="tag in juryTags" :key="tag" class="jury-tag-new">
                  {{ tag }}
                  <button class="tag-remove" @click="removeJuryTag(tag)">&times;</button>
                </span>
                <input
                  v-model="jurySearchValue"
                  type="text"
                  class="native-picker"
                  style="min-width:220px;flex:1"
                  placeholder="Search Wiktionary username..."
                  autocomplete="off"
                  @blur="setTimeout(() => { juryMenuVisible = false }, 200)"
                />
                <ul v-if="juryMenuVisible && juryMenuItems.length" class="jury-suggest-dropdown">
                  <li
                    v-for="item in juryMenuItems"
                    :key="item.value"
                    @mousedown.prevent="selectJuryUser(item.value)"
                    class="jury-suggest-item"
                  >{{ item.label }}</li>
                </ul>
              </div>
              <p class="field-hint">Search by username prefix, select to add. Multiple users can be added at once.</p>

              <button class="submit-btn primary mt-4" :disabled="!juryTags.length" @click="handleAssignJury">
                Assign {{ juryTags.length }} New Juror{{ juryTags.length !== 1 ? 's' : '' }}
              </button>
            </div>
          </div>
        </div>
      </div>
            <div v-if="activeTab === 'logs'" class="tab-pane">
        <div class="jury-hub-card">
          <div class="form-pane-header">
            <h2>System Logs</h2>
            <p>Background task status, talk page template errors, backups, and frontend errors.</p>
          </div>

                    <div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; align-items:center;">
            <button
              v-for="src in logSources"
              :key="src"
              @click="logsSourceFilter = src"
              :style="{
                padding: '4px 14px',
                borderRadius: '999px',
                fontSize: '0.78rem',
                fontWeight: '600',
                border: '1px solid',
                cursor: 'pointer',
                background: logsSourceFilter === src
                  ? (src === 'talk_template' ? 'rgba(239,68,68,0.18)' : 'rgba(99,102,241,0.18)')
                  : 'rgba(255,255,255,0.05)',
                borderColor: logsSourceFilter === src
                  ? (src === 'talk_template' ? '#ef4444' : '#6366f1')
                  : 'rgba(255,255,255,0.1)',
                color: logsSourceFilter === src
                  ? (src === 'talk_template' ? '#ef4444' : '#a5b4fc')
                  : '#94a3b8',
                transition: 'all 0.15s'
              }"
            >
              {{ src === 'all' ? '🗂 All' : src === 'talk_template' ? '💬 talk_template' : src === 'backup' ? '💾 backup' : src === 'frontend' ? '🌐 frontend' : src }}
              <span v-if="src !== 'all'" style="margin-left:4px; opacity:0.7">
                ({{ systemLogs.filter(l => l.source === src).length }})
              </span>
            </button>

            <button class="submit-btn quiet" @click="fetchLogs" :disabled="logsLoading" style="margin-left:auto; padding:0.4rem 1rem; font-size:0.82rem">
              {{ logsLoading ? '⏳ Loading…' : '🔄 Refresh' }}
            </button>
          </div>

                    <div style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px;">
            <span style="font-size:0.8rem; color:#94a3b8">Showing <strong style="color:#e2e8f0">{{ filteredLogs.length }}</strong> entries</span>
            <span v-if="filteredLogs.filter(l=>l.level==='error').length" style="font-size:0.8rem; color:#ef4444; font-weight:600">
              ⚠ {{ filteredLogs.filter(l=>l.level==='error').length }} error{{ filteredLogs.filter(l=>l.level==='error').length > 1 ? 's' : '' }}
            </span>
            <span v-if="filteredLogs.filter(l=>l.level==='warning').length" style="font-size:0.8rem; color:#f59e0b; font-weight:600">
              {{ filteredLogs.filter(l=>l.level==='warning').length }} warning{{ filteredLogs.filter(l=>l.level==='warning').length > 1 ? 's' : '' }}
            </span>
          </div>

          <div class="table-responsive">
            <table class="w-full text-left" style="border-collapse: collapse;">
              <thead>
                <tr class="text-slate-400 border-b border-slate-700/50" style="font-size: 0.78rem; text-transform: uppercase;">
                  <th style="padding:8px 12px; white-space:nowrap">Timestamp</th>
                  <th style="padding:8px 12px">Level</th>
                  <th style="padding:8px 12px">Source</th>
                  <th style="padding:8px 12px">Message</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="log in filteredLogs" :key="log.id">
                  <tr
                    @click="toggleLogExpand(log.id)"
                    style="cursor:pointer; border-bottom: 1px solid rgba(255,255,255,0.06); transition: background 0.12s"
                    :style="{ background: expandedLogId === log.id ? 'rgba(99,102,241,0.07)' : 'transparent' }"
                    class="hover:bg-slate-800/30"
                  >
                    <td style="padding:10px 12px; color:#94a3b8; font-size:0.78rem; white-space:nowrap; vertical-align:top">
                      {{ formatLogTimestamp(log.timestamp) }}
                    </td>
                    <td style="padding:10px 12px; vertical-align:top">
                      <span
                        style="padding:2px 9px; border-radius:999px; font-size:0.72rem; font-weight:700; border:1px solid"
                        :style="log.level === 'error'
                          ? 'background:rgba(239,68,68,0.15); color:#f87171; border-color:rgba(239,68,68,0.35)'
                          : log.level === 'warning'
                          ? 'background:rgba(245,158,11,0.12); color:#fbbf24; border-color:rgba(245,158,11,0.3)'
                          : 'background:rgba(99,102,241,0.12); color:#a5b4fc; border-color:rgba(99,102,241,0.3)'"
                      >{{ log.level.toUpperCase() }}</span>
                    </td>
                    <td style="padding:10px 12px; vertical-align:top">
                      <span
                        style="padding:2px 9px; border-radius:6px; font-size:0.72rem; font-weight:600"
                        :style="log.source === 'talk_template'
                          ? 'background:rgba(239,68,68,0.1); color:#fca5a5'
                          : log.source === 'backup'
                          ? 'background:rgba(34,197,94,0.1); color:#86efac'
                          : 'background:rgba(255,255,255,0.07); color:#94a3b8'"
                      >{{ log.source }}</span>
                    </td>
                    <td style="padding:10px 12px; color:#e2e8f0; font-size:0.83rem; max-width:420px; vertical-align:top">
                      <span v-if="expandedLogId !== log.id" style="display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; word-break:break-word">
                        {{ log.message }}
                      </span>
                      <span v-else style="white-space:pre-wrap; word-break:break-all; font-family:monospace; font-size:0.78rem; color:#e2e8f0">
                        {{ log.message }}
                      </span>
                    </td>
                  </tr>
                </template>
                <tr v-if="!filteredLogs.length">
                  <td colspan="4" style="padding:40px; text-align:center; color:#4b5563; font-style:italic">
                    {{ logsLoading ? 'Loading…' : 'No logs found for this filter.' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

        <div v-if="editingContest" class="modal-backdrop" @click.self="closeEditModal">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Edit Contest Settings & Rules</h3>
          <button class="modal-close-btn" @click="closeEditModal">&times;</button>
        </div>

        <div class="modal-body">
                    <div class="wizard-sub-tabs mb-4">
            <button class="w-tab" :class="{ active: editFormSubTab === 'basic' }" @click="editFormSubTab = 'basic'">
              📌 Basic Info
            </button>
            <button class="w-tab" :class="{ active: editFormSubTab === 'rules' }" @click="editFormSubTab = 'rules'">
              ⚙️ Rules
            </button>
            <button class="w-tab" :class="{ active: editFormSubTab === 'talk' }" @click="editFormSubTab = 'talk'">
              💬 Talk Template
            </button>
            <button class="w-tab" :class="{ active: editFormSubTab === 'governance' }" @click="editFormSubTab = 'governance'">
              🛡️ Governance
            </button>
          </div>

                    <div v-if="editFormSubTab === 'basic'">
            <div class="form-group">
              <label class="field-label">Contest Name</label>
              <cdx-text-input v-model="editName" />
            </div>

            <div class="form-grid-2 mt-3">
              <div class="form-group">
                <label class="field-label">Start Date & Time (BST)</label>
                <div class="datetime-flex">
                  <input type="date" v-model="editStartDate" class="native-picker" />
                  <input type="time" v-model="editStartTime" class="native-picker" />
                </div>
              </div>

              <div class="form-group">
                <label class="field-label">End Date & Time (BST)</label>
                <div class="datetime-flex">
                  <input type="date" v-model="editEndDate" class="native-picker" />
                  <input type="time" v-model="editEndTime" class="native-picker" />
                </div>
              </div>
            </div>
          </div>

                    <div v-if="editFormSubTab === 'rules'" class="rules-config-grid">
            <div class="rule-card-toggle">
              <cdx-checkbox v-model="editMustBeCreator">
                <strong class="text-slate-100">👤 Rule: Submitter MUST be original article creator</strong>
                <p class="toggle-desc">MediaWiki API / MariaDB replica verifies that the submitter is the original author who created the page.</p>
              </cdx-checkbox>
            </div>

            <div class="rule-card-toggle">
              <cdx-checkbox v-model="editMainspaceOnly">
                <strong class="text-slate-100">📁 Rule: Mainspace Only (Namespace 0)</strong>
                <p class="toggle-desc">Blocks talk pages, user sandboxes, category pages, and template pages from submission.</p>
              </cdx-checkbox>
            </div>

            <div class="rule-card-toggle">
              <cdx-checkbox v-model="editNoRedirect">
                <strong class="text-slate-100">🚫 Rule: Disallow Redirect Pages</strong>
                <p class="toggle-desc">Automatically rejects articles if they are hard or soft redirects to another entry.</p>
              </cdx-checkbox>
            </div>

            <div class="rule-card-toggle">
              <cdx-checkbox v-model="editNoDisambig">
                <strong class="text-slate-100">🔀 Rule: Disallow Disambiguation Pages</strong>
                <p class="toggle-desc">Automatically rejects disambiguation / index pages (with {{disambig}} template).</p>
              </cdx-checkbox>
            </div>

            <div class="rule-input-card span-2">
              <label class="field-label">📐 Minimum Article Size (Bytes)</label>
              <div class="flex-input-row">
                <cdx-text-input v-model.number="editMinBytes" type="number" placeholder="0 = No limit (e.g. 3500)" />
                <div class="preset-chips">
                  <button class="preset-chip" :class="{ active: editMinBytes === 0 }" @click="editMinBytes = 0">No Limit (0 B)</button>
                  <button class="preset-chip" :class="{ active: editMinBytes === 1000 }" @click="editMinBytes = 1000">1,000 Bytes</button>
                  <button class="preset-chip" :class="{ active: editMinBytes === 3000 }" @click="editMinBytes = 3000">3,000 Bytes</button>
                  <button class="preset-chip" :class="{ active: editMinBytes === 5000 }" @click="editMinBytes = 5000">5,000 Bytes</button>
                </div>
              </div>
              <p class="field-hint">Articles with total page length under this byte threshold will fail automatic validation.</p>
            </div>

            <div class="rule-input-card">
              <label class="field-label">📝 Minimum Word Count</label>
              <div class="flex-input-row">
                <cdx-text-input v-model.number="editMinWords" type="number" placeholder="0 = No limit" />
                <div class="preset-chips">
                  <button class="preset-chip" :class="{ active: editMinWords === 0 }" @click="editMinWords = 0">0 Words</button>
                  <button class="preset-chip" :class="{ active: editMinWords === 100 }" @click="editMinWords = 100">100 Words</button>
                  <button class="preset-chip" :class="{ active: editMinWords === 300 }" @click="editMinWords = 300">300 Words</button>
                </div>
              </div>
              <p class="field-hint">Minimum required text words inside the entry body.</p>
            </div>

            <div class="rule-input-card">
              <label class="field-label">📚 Minimum References / Citations</label>
              <div class="flex-input-row">
                <cdx-text-input v-model.number="editMinRefs" type="number" placeholder="0 = No limit" />
                <div class="preset-chips">
                  <button class="preset-chip" :class="{ active: editMinRefs === 0 }" @click="editMinRefs = 0">0 Refs</button>
                  <button class="preset-chip" :class="{ active: editMinRefs === 1 }" @click="editMinRefs = 1">1 Ref</button>
                  <button class="preset-chip" :class="{ active: editMinRefs === 2 }" @click="editMinRefs = 2">2 Refs</button>
                </div>
              </div>
              <p class="field-hint">Minimum required &lt;ref&gt; citation tags in the wikitext.</p>
            </div>
          </div>

                    <div v-if="editFormSubTab === 'talk'">
            <div class="rule-card-toggle">
              <cdx-checkbox v-model="editAddTalkTemplate">
                <strong class="text-slate-100">💬 Feature: Auto-generate Talk Page Template (আলাপ পাতা)</strong>
                <p class="toggle-desc">Generates official wikitext templates for jury members to place on Wiktionary talk pages for accepted articles.</p>
              </cdx-checkbox>
            </div>

            <div v-if="editAddTalkTemplate" class="talk-options-expanded mt-4">
              <div class="form-group">
                <label class="field-label">Talk Page Template Name</label>
                <cdx-text-input v-model="editTalkTemplateName" placeholder="e.g. উইকিঅভিধান প্রতিযোগিতা ২০২৬ or {{কথা প্রতিযোগিতা}}" />
                <p class="field-hint">Specify the template to be placed on the talk page of submitted articles.</p>
              </div>

              <div class="form-group mt-3">
                <cdx-checkbox v-model="editIncludeTalkHeader">
                  Include default <code>&#123;&#123;আলাপ পাতা&#125;&#125;</code> header at top
                </cdx-checkbox>
              </div>

              <div v-if="editWikitextPreview" class="wikitext-preview-card mt-4">
                <div class="preview-head">
                  <span>Generated Talk Page Wikitext Preview:</span>
                </div>
                <pre class="code-box"><code>{{ editWikitextPreview }}</code></pre>
              </div>
            </div>
          </div>

                    <div v-if="editFormSubTab === 'governance'">
            <div class="rule-card-toggle">
              <cdx-checkbox v-model="editAllowSelfReview">
                <strong class="text-slate-100">🛡️ Governance: Allow Jury Self-Review</strong>
                <p class="toggle-desc">If checked, jury members are permitted to evaluate articles they submitted themselves. If unchecked (default), self-review is strictly blocked by the backend API.</p>
              </cdx-checkbox>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button class="submit-btn primary" @click="saveEdit">Save Changes</button>
          <button class="submit-btn quiet" @click="closeEditModal">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped src="../styles/views/AdminDashboard.css"></style>
