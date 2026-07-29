<script setup>
import { ref, onMounted, inject, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { CdxButton, CdxTextInput, CdxMessage, CdxCheckbox, CdxLookup } from '@wikimedia/codex';

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
  total_juries: 0
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

const refreshData = async () => {
  await Promise.all([fetchContests(), fetchStats(), fetchSystemStatus()]);
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

// Contest Status Helper
const getContestStatus = (c) => {
  const now = new Date();
  const start = new Date(c.start_date);
  const end = new Date(c.end_date);
  if (now < start) return 'upcoming';
  if (now > end) return 'ended';
  return 'active';
};

const getContestProgress = (c) => {
  const now = new Date().getTime();
  const start = new Date(c.start_date).getTime();
  const end = new Date(c.end_date).getTime();
  if (now < start) return 0;
  if (now > end) return 100;
  return Math.round(((now - start) / (end - start)) * 100);
};

// Filtered Contests
const filteredContests = computed(() => {
  return contests.value.filter(c => {
    const matchesSearch = c.name.toLowerCase().includes(searchFilter.value.toLowerCase()) ||
                          c.code.toLowerCase().includes(searchFilter.value.toLowerCase());
    const status = getContestStatus(c);
    const matchesStatus = statusFilter.value === 'all' || status === statusFilter.value;
    return matchesSearch && matchesStatus;
  });
});

// Wizard Form Tabs
const formSubTab = ref('basic'); // 'basic', 'rules', 'talk', 'governance'
const editFormSubTab = ref('basic');

// Create Contest State & Rules
const name = ref('');
const startDate = ref('');
const startTime = ref('00:00');
const endDate = ref('');
const endTime = ref('23:59');

// Rules Configuration
const mustBeCreator = ref(true);
const minBytes = ref(0);
const minWords = ref(0);
const minRefs = ref(0);
const noRedirect = ref(true);
const noDisambig = ref(true);
const mainspaceOnly = ref(true);
const allowSelfReview = ref(false);

// Talk Page Automation
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
    text += '{{আলাপ পাতা}}\n\n';
  }
  text += tName;
  return text;
});

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
        start_date: new Date(`${startDate.value}T${startTime.value}`).toISOString(),
        end_date: new Date(`${endDate.value}T${endTime.value}`).toISOString(),
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
    // Auto-assign jury if any were added in the create form
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

// Clone Contest Settings
const handleCloneContest = (c) => {
  name.value = `Copy of ${c.name}`;
  const start = new Date(c.start_date);
  startDate.value = start.toISOString().split('T')[0];
  startTime.value = start.toTimeString().slice(0,5);
  const end = new Date(c.end_date);
  endDate.value = end.toISOString().split('T')[0];
  endTime.value = end.toTimeString().slice(0,5);
  
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

// Export CSV & JSON
const handleExportCSV = (code) => {
  window.open(`/api/admin/contests/${code}/export/csv`, '_blank');
  showToast(`📥 Exporting CSV for contest ${code}...`);
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

// Delete Contest
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

// Edit Contest Modal State
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
    text += '{{আলাপ পাতা}}\n\n';
  }
  text += tName;
  return text;
});

const openEditModal = (c) => {
  editingContest.value = c;
  editName.value = c.name;
  
  const start = new Date(c.start_date);
  editStartDate.value = start.toISOString().split('T')[0];
  editStartTime.value = start.toTimeString().slice(0,5);
  
  const end = new Date(c.end_date);
  editEndDate.value = end.toISOString().split('T')[0];
  editEndTime.value = end.toTimeString().slice(0,5);
  
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
        start_date: new Date(`${editStartDate.value}T${editStartTime.value}`).toISOString(),
        end_date: new Date(`${editEndDate.value}T${editEndTime.value}`).toISOString(),
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

// Jury Management Hub
const selectedJuryContestCode = ref('');
const selectedJuryContest = computed(() => {
  return contests.value.find(c => c.code === selectedJuryContestCode.value) || null;
});

// --- Jury Command Center (existing contest) ---
const jurySearchValue = ref('');
const juryUsername = ref('');
const juryMenuItems = ref([]);
const juryTags = ref([]);

// --- Create-form jury (new contest) ---
const createJurySearchValue = ref('');
const createJuryUsername = ref('');
const createJuryMenuItems = ref([]);
const createJuryTags = ref([]);

const makeJuryWatcher = (searchVal, menuItems, tags, existingFn) => {
  let t;
  watch(searchVal, (newVal) => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const prefix = newVal.trim();
      if (prefix.length < 2) { menuItems.value = []; return; }
      try {
        const url = `https://bn.wiktionary.org/w/api.php?action=query&list=allusers&auprefix=${encodeURIComponent(prefix)}&format=json&origin=*`;
        const res = await fetch(url);
        const data = await res.json();
        if (data.query?.allusers) {
          const existing = existingFn();
          menuItems.value = data.query.allusers
            .map(u => ({ value: u.name, label: u.name }))
            .filter(u => !existing.includes(u.value) && !tags.value.includes(u.value));
        }
      } catch (err) {}
    }, 300);
  });
};

makeJuryWatcher(jurySearchValue, juryMenuItems, juryTags,
  () => selectedJuryContest.value?.juries || []);
makeJuryWatcher(createJurySearchValue, createJuryMenuItems, createJuryTags, () => []);

watch(juryUsername, (newVal) => {
  if (newVal && !juryTags.value.includes(newVal)) juryTags.value.push(newVal);
  juryUsername.value = ''; jurySearchValue.value = ''; juryMenuItems.value = [];
});
watch(createJuryUsername, (newVal) => {
  if (newVal && !createJuryTags.value.includes(newVal)) createJuryTags.value.push(newVal);
  createJuryUsername.value = ''; createJurySearchValue.value = ''; createJuryMenuItems.value = [];
});

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

const formatDate = (iso) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};
</script>

<template>
  <div class="admin-suite">
    <!-- Floating Toast Notification -->
    <transition name="toast">
      <div v-if="toastMessage" class="toast-banner" :class="{ 'toast-error': toastIsError }">
        <span class="toast-icon">{{ toastIsError ? '⚠️' : '✨' }}</span>
        <span>{{ toastMessage }}</span>
      </div>
    </transition>

    <!-- Unauthorized Banner -->
    <div v-if="user && user.role !== 'owner'" class="unauthorized-banner">
      <div class="unauthorized-content">
        <span class="icon">⛔</span>
        <h2>Owner Portal Restricted</h2>
        <p>You are logged in as <strong>{{ user.wiki_username }}</strong> ({{ user.role }}). Administrative control panels are restricted to System Owners.</p>
      </div>
    </div>

    <template v-else-if="user && user.role === 'owner'">
      <!-- Suite Header Banner -->
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
          </div>
        </div>

        <!-- Metric KPI Cards -->
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
        </div>
      </div>

      <!-- Navigation Tabs -->
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
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          Jury Command Center
        </button>
      </div>

      <!-- TAB 1: OVERVIEW & CONTESTS -->
      <div v-if="activeTab === 'overview'" class="tab-pane">
        <!-- Controls Bar -->
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

        <!-- GRID VIEW -->
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

            <!-- Progress bar -->
            <div class="progress-container">
              <div class="progress-bar-bg">
                <div class="progress-bar-fill" :style="{ width: getContestProgress(c) + '%' }"></div>
              </div>
              <span class="progress-txt">{{ getContestProgress(c) }}% elapsed</span>
            </div>

            <!-- Rules Badges -->
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

            <!-- Metrics footer -->
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

            <!-- Card Actions Bar -->
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

        <!-- TABLE VIEW -->
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

      <!-- TAB 2: CREATE CONTEST WIZARD -->
      <div v-if="activeTab === 'create'" class="tab-pane">
        <div class="form-pane-card">
          <div class="form-pane-header">
            <h2>Create New Contest</h2>
            <p>Configure complete validation constraints, article requirements, jury rules, and talk page templates.</p>
          </div>

          <!-- Wizard Sub-Tabs -->
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

          <!-- SUB-TAB 1: BASIC INFO -->
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
                <label class="field-label">Start Date & Time (UTC) <span class="req">*</span></label>
                <div class="datetime-flex">
                  <input type="date" v-model="startDate" class="native-picker" />
                  <input type="time" v-model="startTime" class="native-picker" />
                </div>
              </div>

              <div class="form-group">
                <label class="field-label">End Date & Time (UTC) <span class="req">*</span></label>
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

          <!-- SUB-TAB 2: RULES -->
          <div v-if="formSubTab === 'rules'" class="sub-tab-content">
            <div class="rules-config-grid">
              <!-- Creator constraint -->
              <div class="rule-card-toggle">
                <cdx-checkbox v-model="mustBeCreator">
                  <strong class="text-slate-100">👤 Rule: Submitter MUST be original article creator</strong>
                  <p class="toggle-desc">MediaWiki API / MariaDB replica verifies that the submitter is the original author who created the page.</p>
                </cdx-checkbox>
              </div>

              <!-- Mainspace Only -->
              <div class="rule-card-toggle">
                <cdx-checkbox v-model="mainspaceOnly">
                  <strong class="text-slate-100">📁 Rule: Mainspace Only (Namespace 0)</strong>
                  <p class="toggle-desc">Blocks talk pages, user sandboxes, category pages, and template pages from submission.</p>
                </cdx-checkbox>
              </div>

              <!-- Disallow Redirects -->
              <div class="rule-card-toggle">
                <cdx-checkbox v-model="noRedirect">
                  <strong class="text-slate-100">🚫 Rule: Disallow Redirect Pages</strong>
                  <p class="toggle-desc">Automatically rejects articles if they are hard or soft redirects to another entry.</p>
                </cdx-checkbox>
              </div>

              <!-- Disallow Disambiguation -->
              <div class="rule-card-toggle">
                <cdx-checkbox v-model="noDisambig">
                  <strong class="text-slate-100">🔀 Rule: Disallow Disambiguation Pages</strong>
                  <p class="toggle-desc">Automatically rejects disambiguation / index pages (with {{disambig}} template).</p>
                </cdx-checkbox>
              </div>

              <!-- Page Size (Bytes) -->
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

              <!-- Word Count -->
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

              <!-- References Count -->
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

          <!-- SUB-TAB 3: TALK PAGE TEMPLATE -->
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

          <!-- SUB-TAB 4: GOVERNANCE & JURY -->
          <div v-if="formSubTab === 'governance'" class="sub-tab-content">
            <div class="rule-card-toggle">
              <cdx-checkbox v-model="allowSelfReview">
                <strong class="text-slate-100">🛡️ Allow Jury Self-Review</strong>
                <p class="toggle-desc">If checked, jury members may evaluate articles they submitted themselves. If unchecked (default), self-review is strictly blocked.</p>
              </cdx-checkbox>
            </div>

            <!-- Jury Assignment -->
            <div class="jury-section mt-6">
              <h3 class="jury-section-title">👥 Add Jury Members</h3>
              <p class="toggle-desc mb-3">Search and add jury members now. They will be assigned automatically when the contest is created.</p>

              <div class="jury-lookup-row">
                <cdx-lookup
                  v-model:selected="createJuryUsername"
                  v-model:input-value="createJurySearchValue"
                  :menu-items="createJuryMenuItems"
                  placeholder="Search wiki username..."
                  class="jury-lookup"
                />
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

      <!-- TAB 3: JURY COMMAND CENTER -->
      <div v-if="activeTab === 'jury'" class="tab-pane">
        <div class="jury-hub-card">
          <div class="form-pane-header">
            <h2>Jury Command Center</h2>
            <p>Assign and manage evaluation jury members for each active writing contest.</p>
          </div>

          <!-- Contest Selector -->
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

            <!-- Existing Juror Badges with 1-click remove -->
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

            <!-- Add New Jury Members Section -->
            <div class="add-jury-section mt-6 border-t border-slate-700/50 pt-4">
              <label class="field-label">Add New Jury Members (Type username prefix)</label>
              
              <div class="tag-input-wrapper mt-2">
                <span v-for="tag in juryTags" :key="tag" class="jury-tag-new">
                  {{ tag }}
                  <button class="tag-remove" @click="removeJuryTag(tag)">&times;</button>
                </span>
                <cdx-lookup
                  v-model:selected="juryUsername"
                  v-model:input-value="jurySearchValue"
                  :menu-items="juryMenuItems"
                  placeholder="Search Wiktionary username..."
                  class="tag-lookup"
                />
              </div>
              <p class="field-hint">Search by username prefix, select to add. Multiple users can be added at once.</p>

              <button class="submit-btn primary mt-4" :disabled="!juryTags.length" @click="handleAssignJury">
                Assign {{ juryTags.length }} New Juror{{ juryTags.length !== 1 ? 's' : '' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- EDIT CONTEST MODAL OVERLAY -->
    <div v-if="editingContest" class="modal-backdrop" @click.self="closeEditModal">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Edit Contest Settings & Rules</h3>
          <button class="modal-close-btn" @click="closeEditModal">&times;</button>
        </div>

        <div class="modal-body">
          <!-- Wizard Sub-Tabs in Modal -->
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

          <!-- EDIT TAB 1: BASIC INFO -->
          <div v-if="editFormSubTab === 'basic'">
            <div class="form-group">
              <label class="field-label">Contest Name</label>
              <cdx-text-input v-model="editName" />
            </div>

            <div class="form-grid-2 mt-3">
              <div class="form-group">
                <label class="field-label">Start Date & Time (UTC)</label>
                <div class="datetime-flex">
                  <input type="date" v-model="editStartDate" class="native-picker" />
                  <input type="time" v-model="editStartTime" class="native-picker" />
                </div>
              </div>

              <div class="form-group">
                <label class="field-label">End Date & Time (UTC)</label>
                <div class="datetime-flex">
                  <input type="date" v-model="editEndDate" class="native-picker" />
                  <input type="time" v-model="editEndTime" class="native-picker" />
                </div>
              </div>
            </div>
          </div>

          <!-- EDIT TAB 2: RULES -->
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

          <!-- EDIT TAB 3: TALK TEMPLATE -->
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

          <!-- EDIT TAB 4: GOVERNANCE -->
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

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.admin-suite {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 20px 80px;
  font-family: 'Inter', system-ui, sans-serif;
  color: #e2e8f0;
}

/* Toast */
.toast-banner {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 10px;
  background: #1e1b4b;
  border: 1px solid #ffffff;
  color: #e5e7eb;
  padding: 12px 20px;
  border-radius: 12px;
  box-shadow: 0 16px 36px rgba(0,0,0,0.5);
  font-weight: 600;
  font-size: 0.95rem;
}
.toast-error {
  background: #451a1a;
  border-color: #ffffff;
  color: #9ca3af;
}
.toast-enter-active, .toast-leave-active { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(-20px); }

/* Header Card */
.admin-header-card {
  background: linear-gradient(135deg, #131627 0%, #1a1d36 100%);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  padding: 32px;
  margin-bottom: 28px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.4);
}
.header-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 28px;
}
.owner-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.1);
  color: #d1d5db;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 20px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}
.suite-title {
  font-size: 1.85rem;
  font-weight: 800;
  color: #f8fafc;
  margin: 0 0 6px;
}
.suite-desc {
  color: #94a3b8;
  font-size: 0.95rem;
  margin: 0;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}
.action-btn.primary {
  background: linear-gradient(135deg, #4f46e5, #2563eb);
  color: #fff;
  box-shadow: 0 4px 14px rgba(79,70,229,0.3);
}
.action-btn.primary:hover { background: linear-gradient(135deg, #4338ca 0%, #1d4ed8 100%); }
.action-btn.secondary {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  color: #cbd5e1;
}
.action-btn.secondary:hover { background: rgba(255,255,255,0.12); }

/* KPI Grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
.kpi-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 14px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.kpi-icon { font-size: 1.5rem; margin-bottom: 2px; }
.kpi-info { display: flex; flex-direction: column; }
.kpi-val { font-size: 1.75rem; font-weight: 800; color: #f8fafc; line-height: 1.1; }
.kpi-lbl { font-size: 0.8rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.04em; }
.kpi-sub { font-size: 0.75rem; color: #64748b; font-weight: 500; margin-top: 4px; }
.pill-active { color: #d1d5db; font-weight: 600; }
.pill-green { color: #d1d5db; font-weight: 600; }

/* Tabs Nav */
.suite-tabs-nav {
  display: flex;
  gap: 10px;
  margin-bottom: 24px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding-bottom: 12px;
}
.nav-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: none;
  color: #94a3b8;
  font-weight: 600;
  font-size: 0.95rem;
  padding: 10px 18px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}
.nav-tab:hover { color: #e2e8f0; background: rgba(255,255,255,0.04); }
.nav-tab.active { color: #fff; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.1); }
.tab-badge {
  background: rgba(255,255,255,0.1);
  color: #cbd5e1;
  font-size: 0.75rem;
  padding: 1px 7px;
  border-radius: 10px;
}

/* Controls Card */
.controls-card {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: #121422;
  border: 1px solid rgba(255,255,255,0.07);
  padding: 14px 20px;
  border-radius: 14px;
  margin-bottom: 24px;
}
.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #1a1d30;
  border: 1px solid rgba(255,255,255,0.1);
  padding: 8px 14px;
  border-radius: 8px;
  flex: 1;
  min-width: 260px;
}
.search-icon { color: #64748b; }
.search-input {
  background: transparent;
  border: none;
  outline: none;
  color: #f8fafc;
  font-size: 0.9rem;
  width: 100%;
}
.filter-group { display: flex; align-items: center; gap: 10px; }
.filter-label { font-size: 0.85rem; color: #94a3b8; font-weight: 600; }
.chip-filter { display: flex; gap: 4px; background: #1a1d30; padding: 3px; border-radius: 8px; }
.chip-filter button {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.chip-filter button.active { background: #2563eb; color: #fff; }
.view-switch { display: flex; gap: 4px; background: #1a1d30; padding: 3px; border-radius: 8px; }
.view-switch button {
  background: transparent;
  border: none;
  color: #64748b;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
}
.view-switch button.active { background: rgba(255,255,255,0.1); color: #fff; }

/* Contests Grid */
.contests-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 20px;
}
.contest-card {
  background: #121422;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 16px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  transition: transform 0.2s, border-color 0.2s;
}
.contest-card:hover { transform: translateY(-2px); border-color: rgba(255,255,255,0.1); }
.card-top { display: flex; justify-content: space-between; align-items: center; }
.card-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.7rem;
  font-weight: 800;
  padding: 3px 9px;
  border-radius: 12px;
  letter-spacing: 0.05em;
}
.card-status-badge.active { background: rgba(255,255,255,0.1); color: #d1d5db; border: 1px solid rgba(255,255,255,0.1); }
.card-status-badge.upcoming { background: rgba(255,255,255,0.1); color: #d1d5db; border: 1px solid rgba(255,255,255,0.1); }
.card-status-badge.ended { background: rgba(148,163,184,0.12); color: #94a3b8; border: 1px solid rgba(148,163,184,0.2); }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.contest-code-badge { background: #1a1d30; color: #e5e7eb; font-family: monospace; font-size: 0.8rem; padding: 2px 8px; border-radius: 6px; }
.card-title { font-size: 1.2rem; font-weight: 700; color: #f8fafc; margin: 0; line-height: 1.3; }
.card-dates { display: flex; gap: 8px; font-size: 0.82rem; color: #94a3b8; font-weight: 500; }
.progress-container { display: flex; flex-direction: column; gap: 4px; }
.progress-bar-bg { height: 6px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden; }
.progress-bar-fill { height: 100%; background: linear-gradient(90deg, #2563eb, #818cf8); border-radius: 3px; transition: width 0.4s; }
.progress-txt { font-size: 0.72rem; color: #64748b; text-align: right; }

.card-rules-list { display: flex; flex-wrap: wrap; gap: 6px; }
.rule-tag { background: rgba(255,255,255,0.05); color: #cbd5e1; font-size: 0.75rem; padding: 2px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.08); }
.rule-tag.amber { background: rgba(255,255,255,0.1); color: #d1d5db; border-color: rgba(255,255,255,0.1); }
.rule-tag.emerald { background: rgba(255,255,255,0.1); color: #6ee7b7; border-color: rgba(255,255,255,0.1); }
.rule-tag.sky { background: rgba(255,255,255,0.1); color: #d1d5db; border-color: rgba(255,255,255,0.1); }
.rule-tag.violet { background: rgba(255,255,255,0.1); color: #d1d5db; border-color: rgba(255,255,255,0.1); }
.rule-tag.rose { background: rgba(244,63,94,0.12); color: #fda4af; border-color: rgba(244,63,94,0.25); }
.rule-tag.indigo { background: rgba(255,255,255,0.1); color: #e5e7eb; border-color: rgba(255,255,255,0.1); }
.rule-tag.slate { background: rgba(148,163,184,0.12); color: #cbd5e1; border-color: rgba(148,163,184,0.25); }

.card-metrics-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  background: #1a1d30;
  border-radius: 10px;
  padding: 10px;
  text-align: center;
}
.metric-item { display: flex; flex-direction: column; }
.metric-item .m-val { font-weight: 800; font-size: 1.1rem; color: #f8fafc; }
.metric-item.accent .m-val { color: #d1d5db; }
.metric-item .m-lbl { font-size: 0.7rem; color: #64748b; font-weight: 600; text-transform: uppercase; }

.card-actions-bar { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.card-btn {
  padding: 7px 10px;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 600;
  text-align: center;
  text-decoration: none;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}
.card-btn.primary { background: #2563eb; color: #fff; }
.card-btn.primary:hover { background: #1d4ed8; }
.card-btn.secondary { background: rgba(255,255,255,0.06); color: #cbd5e1; border: 1px solid rgba(255,255,255,0.1); }
.card-btn.secondary:hover { background: rgba(255,255,255,0.12); }
.card-btn.danger { background: rgba(255,255,255,0.1); color: #d1d5db; border: 1px solid rgba(255,255,255,0.1); }
.card-btn.danger:hover { background: rgba(255,255,255,0.1); }

/* Table View */
.table-card { background: #121422; border: 1px solid rgba(255,255,255,0.07); border-radius: 14px; overflow: hidden; }
.wikitable-modern { width: 100%; border-collapse: collapse; text-align: left; }
.wikitable-modern th { background: #1a1d30; padding: 12px 16px; font-size: 0.8rem; text-transform: uppercase; color: #94a3b8; font-weight: 700; border-bottom: 1px solid rgba(255,255,255,0.08); }
.wikitable-modern td { padding: 14px 16px; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.9rem; color: #cbd5e1; }
.table-name-cell { display: flex; flex-direction: column; gap: 4px; }
.rule-badges { display: flex; flex-wrap: wrap; gap: 4px; }
.rule-badge { font-size: 0.7rem; background: rgba(255,255,255,0.06); padding: 1px 6px; border-radius: 4px; color: #94a3b8; }
.rule-badge.amber { background: rgba(255,255,255,0.1); color: #d1d5db; }
.rule-badge.emerald { background: rgba(255,255,255,0.1); color: #6ee7b7; }
.rule-badge.sky { background: rgba(255,255,255,0.1); color: #d1d5db; }
.rule-badge.indigo { background: rgba(255,255,255,0.1); color: #e5e7eb; }
.timeline-cell { display: flex; gap: 6px; font-size: 0.82rem; }
.sub-cell { display: flex; flex-direction: column; }
.jury-pill-btn { background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.1); color: #e5e7eb; font-size: 0.8rem; font-weight: 600; padding: 4px 10px; border-radius: 20px; cursor: pointer; }
.icon-action-btn { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); color: #e2e8f0; padding: 6px 10px; border-radius: 6px; text-decoration: none; cursor: pointer; margin-right: 4px; }
.icon-action-btn.danger { color: #d1d5db; background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.1); }

/* Form Wizard & Controls */
.form-pane-card, .jury-hub-card {
  background: #121422;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  padding: 32px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.3);
}
.form-pane-header {
  margin-bottom: 24px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding-bottom: 18px;
}
.form-pane-header h2 { margin: 0 0 6px; font-size: 1.45rem; font-weight: 800; color: #f8fafc; }
.form-pane-header p { margin: 0; color: #94a3b8; font-size: 0.92rem; }

.wizard-sub-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding-bottom: 14px;
}
.w-tab {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  color: #94a3b8;
  font-weight: 600;
  font-size: 0.88rem;
  padding: 9px 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.w-tab:hover { color: #f8fafc; background: rgba(255,255,255,0.07); border-color: rgba(255,255,255,0.15); }
.w-tab.active {
  background: rgba(255,255,255,0.1);
  color: #e5e7eb;
  border-color: rgba(255,255,255,0.1);
  box-shadow: 0 4px 12px rgba(255,255,255,0.1);
}

.rules-config-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
@media (max-width: 768px) {
  .rules-config-grid { grid-template-columns: 1fr; }
  .span-2 { grid-column: span 1 !important; }
}

.rule-card-toggle {
  background: #16192c;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  padding: 18px;
  transition: border-color 0.2s, background-color 0.2s;
}
.rule-card-toggle:hover {
  border-color: rgba(255,255,255,0.1);
  background-color: #1a1d34;
}

.rule-input-card {
  background: #16192c;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  padding: 18px;
  transition: border-color 0.2s;
}
.rule-input-card:hover { border-color: rgba(255,255,255,0.1); }

.preset-chips { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.preset-chip {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  color: #cbd5e1;
  font-size: 0.78rem;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.preset-chip:hover { background: rgba(255,255,255,0.12); color: #fff; border-color: rgba(255,255,255,0.2); }
.preset-chip.active {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
  box-shadow: 0 2px 8px rgba(37,99,235,0.3);
}
.chip-lbl { font-size: 0.78rem; color: #64748b; font-weight: 600; }

.flex-input-row { display: flex; flex-direction: column; gap: 10px; margin-top: 8px; }

.form-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.span-2 { grid-column: span 2; }
.field-label {
  display: block;
  font-weight: 700;
  font-size: 0.82rem;
  color: #cbd5e1;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.req { color: #d1d5db; margin-left: 2px; }

.native-picker {
  padding: 10px 14px;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 8px;
  font-family: inherit;
  font-size: 0.92rem;
  color: #f8fafc;
  background-color: #1a1d30;
  color-scheme: dark;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.native-picker:focus {
  outline: none;
  border-color: #ffffff;
  box-shadow: 0 0 0 3px rgba(255,255,255,0.1);
}

.datetime-flex { display: flex; gap: 12px; }
.datetime-flex > input { flex: 1; min-width: 0; }

.toggle-desc { font-size: 0.82rem; color: #94a3b8; margin: 4px 0 0 26px; font-weight: normal; line-height: 1.4; }
.talk-options-expanded { background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.1); padding: 20px; border-radius: 12px; }
.field-hint { font-size: 0.8rem; color: #94a3b8; margin-top: 6px; line-height: 1.35; }
.wikitext-preview-card { background: #0b0d18; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 14px; }
.preview-head { font-size: 0.8rem; font-weight: 700; color: #e5e7eb; margin-bottom: 8px; }
.code-box { margin: 0; font-family: monospace; font-size: 0.88rem; color: #d1d5db; white-space: pre-wrap; word-break: break-all; }
.tab-footer-nav { display: flex; justify-content: space-between; align-items: center; }
.form-submit-row { display: flex; gap: 12px; }
.submit-btn {
  padding: 11px 24px;
  border-radius: 10px;
  font-weight: 700;
  font-size: 0.92rem;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
}
.submit-btn.primary { background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: #fff; box-shadow: 0 4px 14px rgba(37,99,235,0.3); }
.submit-btn.primary:hover { background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%); transform: translateY(-1px); }
.submit-btn.quiet { background: rgba(255,255,255,0.05); color: #cbd5e1; border: 1px solid rgba(255,255,255,0.08); }
.submit-btn.quiet:hover { background: rgba(255,255,255,0.1); color: #fff; }

/* Jury Hub */
.assigned-jurors-grid { display: flex; flex-wrap: wrap; gap: 10px; min-height: 48px; padding: 12px; background: #1a1d30; border-radius: 10px; border: 1px solid rgba(255,255,255,0.07); align-items: center; }
.juror-chip { display: inline-flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.1); color: #e5e7eb; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 0.88rem; }
.juror-avatar { width: 22px; height: 22px; border-radius: 50%; background: linear-gradient(135deg, #4f46e5, #2563eb); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 800; }
.unassign-btn { background: none; border: none; color: #e5e7eb; font-size: 1.1rem; cursor: pointer; padding: 0 2px; }
.unassign-btn:hover { color: #d1d5db; }
.no-jurors-notice { color: #64748b; font-size: 0.88rem; font-style: italic; }
.tag-input-wrapper { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 10px; background: #1a1d30; border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; }
.jury-tag-new { display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.1); color: #d1d5db; font-weight: 700; padding: 3px 10px; border-radius: 16px; font-size: 0.85rem; }
.tag-remove { background: none; border: none; color: inherit; cursor: pointer; font-size: 1rem; }
.tag-lookup { flex: 1; min-width: 200px; border: none !important; padding: 0 !important; }

/* Modal */
.modal-backdrop { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.75); backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; z-index: 999; padding: 20px; }
.modal-card { background: #121422; border: 1px solid rgba(255,255,255,0.12); border-radius: 20px; width: 100%; max-width: 720px; max-height: 90vh; overflow-y: auto; box-shadow: 0 25px 50px rgba(0,0,0,0.6); }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; border-bottom: 1px solid rgba(255,255,255,0.08); }
.modal-header h3 { margin: 0; font-size: 1.25rem; font-weight: 700; color: #f8fafc; }
.modal-close-btn { background: none; border: none; color: #94a3b8; font-size: 1.5rem; cursor: pointer; transition: color 0.2s; }
.modal-close-btn:hover { color: #d1d5db; }
.modal-body { padding: 24px; }
.modal-footer { padding: 16px 24px; border-top: 1px solid rgba(255,255,255,0.08); display: flex; gap: 12px; justify-content: flex-end; }
</style>
