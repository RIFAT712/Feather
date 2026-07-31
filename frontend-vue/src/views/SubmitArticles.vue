<script setup>
import { ref, onMounted, watch, inject, computed } from 'vue';
import { useRoute } from 'vue-router';
import { CdxButton, CdxLookup } from '@wikimedia/codex';

const props = defineProps(['contest']);
const route = useRoute();
const user = inject('user');
const results = ref([]);
const isLoading = ref(false);
const totalToSubmit = ref(0);
const processedCount = ref(0);
const submitProgress = ref(0);

const roles = ref({ is_jury: false, is_owner: false });
const isOnBehalf = ref(false);
const onBehalfUsername = ref('');
const onBehalfSearch = ref('');
const onBehalfMenu = ref([]);

const userCreatedArticles = ref([]);
const selectedArticles = ref([]);
const isFetchingArticles = ref(false);
const fetchError = ref(null);
const alreadySubmittedTitles = ref([]);
const articleSearch = ref('');

let searchTimeout;
watch(onBehalfSearch, (newVal) => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(async () => {
    const prefix = newVal.trim();
    if (prefix.length < 2) { onBehalfMenu.value = []; return; }
    try {
      const url = `https://bn.wiktionary.org/w/api.php?action=query&list=allusers&auprefix=${encodeURIComponent(prefix)}&format=json&origin=*`;
      const res = await fetch(url);
      const data = await res.json();
      if (data.query && data.query.allusers) {
        onBehalfMenu.value = data.query.allusers.map(u => ({ value: u.name, label: u.name }));
      }
    } catch (err) {}
  }, 300);
});

// When on-behalf user changes, reset fetched articles
watch([isOnBehalf, onBehalfUsername], () => {
  userCreatedArticles.value = [];
  selectedArticles.value = [];
  fetchError.value = null;
  articleSearch.value = '';
});

// Selection watcher - no upper limit needed with DB replica validation
// selectedArticles can contain all user articles

const fetchUserArticles = async () => {
  if (!props.contest || !user.value) return;
  isFetchingArticles.value = true;
  fetchError.value = null;
  userCreatedArticles.value = [];
  selectedArticles.value = [];
  const targetUser = (isOnBehalf.value && onBehalfUsername.value) ? onBehalfUsername.value : user.value.wiki_username;
  const start = new Date(props.contest.start_date + (!props.contest.start_date.endsWith('Z') ? 'Z' : '')).toISOString();
  const end = new Date(props.contest.end_date + (!props.contest.end_date.endsWith('Z') ? 'Z' : '')).toISOString();
  
  try {
    // 1. Fetch target user's already submitted articles for this contest
    const contestCode = route.params.code;
    const profileRes = await fetch(`/api/contests/${contestCode}/users/${encodeURIComponent(targetUser)}`);
    if (profileRes.ok) {
      const profileData = await profileRes.json();
      alreadySubmittedTitles.value = profileData.submissions.map(s => s.title);
    } else if (profileRes.status === 404) {
      alreadySubmittedTitles.value = []; // User hasn't participated yet
    }
  } catch (err) {
    console.warn("Could not fetch target user's existing submissions", err);
  }

  try {
    let allArticles = [];
    let continueToken = '';
    while (true) {
      const continueParam = continueToken ? `&uccontinue=${continueToken}` : '';
      const url = `https://bn.wiktionary.org/w/api.php?action=query&list=usercontribs&ucuser=${encodeURIComponent(targetUser)}&ucstart=${start}&ucend=${end}&ucdir=newer&ucnamespace=0&ucprop=title|timestamp&ucshow=new&uclimit=max&format=json&origin=*${continueParam}`;
      const res = await fetch(url);
      const data = await res.json();
      if (data.query && data.query.usercontribs) {
        allArticles.push(...data.query.usercontribs.map(c => c.title));
      }
      if (data.continue && data.continue.uccontinue) {
        continueToken = data.continue.uccontinue;
      } else {
        break;
      }
    }
    userCreatedArticles.value = [...new Set(allArticles)];
  } catch (err) { fetchError.value = 'Failed to fetch articles from Wikipedia.'; }
  finally { isFetchingArticles.value = false; }
};

onMounted(async () => {
  try {
    const rolesRes = await fetch(`/api/contests/${route.params.code}/my-role`);
    if (rolesRes.ok) roles.value = await rolesRes.json();
    // Pre-fetch articles automatically on load
    await fetchUserArticles();
  } catch (err) { console.error(err); }
});

const availableArticles = computed(() => userCreatedArticles.value.filter(title => !alreadySubmittedTitles.value.includes(title)));
const submittedArticles = computed(() => userCreatedArticles.value.filter(title => alreadySubmittedTitles.value.includes(title)));

const isAvailableOpen = ref(true);
const isSubmittedOpen = ref(false);

const filteredAvailableArticles = computed(() => {
  const query = articleSearch.value.toLowerCase().trim();
  if (!query) return availableArticles.value;
  return availableArticles.value.filter(title => title.toLowerCase().includes(query));
});

const filteredSubmittedArticles = computed(() => {
  const query = articleSearch.value.toLowerCase().trim();
  if (!query) return submittedArticles.value;
  return submittedArticles.value.filter(title => title.toLowerCase().includes(query));
});

const selectAll = () => { selectedArticles.value = [...filteredAvailableArticles.value]; };
const deselectAll = () => { selectedArticles.value = []; };

const handleSubmit = async () => {
  if (!selectedArticles.value.length) return;
  isLoading.value = true;
  totalToSubmit.value = selectedArticles.value.length;
  processedCount.value = 0;
  submitProgress.value = 0;
  results.value = [];
  
  const titlesToSubmit = [...selectedArticles.value];
  const chunkSize = 100;
  const contestCode = route.params.code;
  
  for (let i = 0; i < titlesToSubmit.length; i += chunkSize) {
    const chunk = titlesToSubmit.slice(i, i + chunkSize);
    const payload = { contest_code: contestCode, titles: chunk };
    if (isOnBehalf.value && (onBehalfUsername.value || onBehalfSearch.value)) {
      payload.on_behalf_of = onBehalfUsername.value || onBehalfSearch.value;
    }
    
    try {
      const response = await fetch('/api/submit-bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      if (!response.ok) {
        let errStr = `HTTP ${response.status}`;
        try {
          const errData = await response.json();
          errStr = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail) || errStr;
        } catch (e) {
          try { errStr = await response.text(); } catch(e2) {}
        }
        throw new Error(errStr);
      }
      
      const chunkResults = await response.json();
      results.value.push(...chunkResults);
    } catch (error) {
      console.error("Chunk failed:", error);
      chunk.forEach(t => results.value.push({ 
        title: t, 
        is_valid: false, 
        error: error.message || 'Network error' 
      }));
    }
    
    processedCount.value += chunk.length;
    submitProgress.value = Math.min(100, Math.round((processedCount.value / totalToSubmit.value) * 100));
  }
  
  try {
    const targetUser = (isOnBehalf.value && onBehalfUsername.value) ? onBehalfUsername.value : user.value.wiki_username;
    const profileRes = await fetch(`/api/contests/${contestCode}/users/${encodeURIComponent(targetUser)}`);
    if (profileRes.ok) {
      const profileData = await profileRes.json();
      alreadySubmittedTitles.value = profileData.submissions.map(s => s.title);
    } else if (profileRes.status === 404) {
      alreadySubmittedTitles.value = [];
    }
    selectedArticles.value = [];
  } catch (error) { console.error(error); }
  finally { isLoading.value = false; }
};

const targetDisplayName = computed(() =>
  isOnBehalf.value && onBehalfUsername.value ? onBehalfUsername.value : user.value?.wiki_username
);
</script>

<template>
  <div class="submit-page">
    <!-- Page Header -->
    <div class="page-header">
      <h1 class="page-title">Submit Articles</h1>
      <p class="page-subtitle">
        Your eligible articles are automatically fetched. Select which ones to submit for review.
      </p>
    </div>

    <!-- On-Behalf Banner (Jury / Owner only) -->
    <div v-if="roles.is_jury || roles.is_owner" class="behalf-banner">
      <div class="behalf-banner__inner">
        <label class="behalf-toggle">
          <input type="checkbox" v-model="isOnBehalf" class="behalf-toggle__input" />
          <span class="behalf-toggle__track">
            <span class="behalf-toggle__thumb"></span>
          </span>
          <span class="behalf-toggle__label">Submit on behalf of another user</span>
        </label>
        <div v-if="isOnBehalf" class="behalf-lookup">
          <CdxLookup
            v-model:selected="onBehalfUsername"
            v-model:input-value="onBehalfSearch"
            :menu-items="onBehalfMenu"
            placeholder="Search username…"
          />
        </div>
      </div>
    </div>

    <!-- Fetch Card (full width) -->
    <div class="card">
      <div class="card__header">
        <div class="card__header-icon">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="18" height="18"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd" /></svg>
        </div>
        <div class="card__header-text">
          <h2 class="card__title">
            Articles by
            <span class="card__title-user">{{ targetDisplayName }}</span>
          </h2>
          <p class="card__desc">
            Showing articles created between
            {{ new Date(contest.start_date).toLocaleDateString() }} – {{ new Date(contest.end_date).toLocaleDateString() }}.
          </p>
        </div>
        <button
          v-if="roles.is_jury || roles.is_owner"
          class="fetch-btn"
          :class="{ 'fetch-btn--loading': isFetchingArticles }"
          @click="fetchUserArticles"
          :disabled="isFetchingArticles || (isOnBehalf && !onBehalfUsername)"
        >
          <span v-if="isFetchingArticles" class="spinner"></span>
          <span v-else>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="15" height="15" style="vertical-align:-2px;margin-right:5px;"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd" /></svg>
            Fetch Articles
          </span>
        </button>
      </div>

      <div class="card__body">
        <p v-if="fetchError" class="fetch-error">{{ fetchError }}</p>

        <!-- Article Search -->
        <div v-if="userCreatedArticles.length > 0" class="article-search">
          <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
          <input
            v-model="articleSearch"
            type="text"
            class="article-search__input"
            placeholder="Search fetched articles..."
          />
        </div>

        <div v-if="userCreatedArticles.length > 0 && filteredAvailableArticles.length === 0 && filteredSubmittedArticles.length === 0" class="empty-state" style="padding: 32px 16px;">
          <p>No articles match your search "<strong>{{ articleSearch }}</strong>".</p>
        </div>

        <!-- Available Articles -->
        <div v-if="filteredAvailableArticles.length > 0" class="article-section">
          <div class="article-section__header" @click="isAvailableOpen = !isAvailableOpen" style="cursor: pointer; user-select: none;">
            <span class="article-section__label">
              <svg :style="{ transform: isAvailableOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="16" height="16" style="margin-right: 4px; vertical-align: -2px;"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
              Articles You Can Submit ({{ filteredAvailableArticles.length }})
              <span class="selection-counter" style="margin-left: 8px; font-size: 0.8125rem; font-weight: 700; color: #e5e7eb; background: rgba(165, 180, 252, 0.15); padding: 2px 8px; border-radius: 99px;">
                {{ selectedArticles.length }} selected
              </span>
            </span>
            <div class="article-section__actions" @click.stop>
              <button class="link-btn" @click="selectAll">Select all</button>
              <span class="link-btn-sep">·</span>
              <button class="link-btn" @click="deselectAll">Deselect all</button>
            </div>
          </div>
          <div class="article-list" v-show="isAvailableOpen">
            <label
              v-for="title in filteredAvailableArticles"
              :key="title"
              class="article-item"
              :class="{ 'article-item--checked': selectedArticles.includes(title) }"
            >
              <input
                type="checkbox"
                :value="title"
                v-model="selectedArticles"
                class="article-item__input"
              />
              <span class="article-item__box">
                <svg v-if="selectedArticles.includes(title)" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="12" height="12"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" /></svg>
              </span>
              <span class="article-item__title">{{ title }}</span>
            </label>
          </div>
        </div>

        <!-- Submitted Articles -->
        <div v-if="filteredSubmittedArticles.length > 0" class="article-section" style="margin-top: 24px;">
          <div class="article-section__header" @click="isSubmittedOpen = !isSubmittedOpen" style="cursor: pointer; user-select: none;">
            <span class="article-section__label" style="color: #64748b;">
              <svg :style="{ transform: isSubmittedOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="16" height="16" style="margin-right: 4px; vertical-align: -2px;"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
              Already Submitted ({{ filteredSubmittedArticles.length }})
            </span>
          </div>
          <div class="article-list" v-show="isSubmittedOpen">
            <label
              v-for="title in filteredSubmittedArticles"
              :key="title"
              class="article-item article-item--disabled"
            >
              <input type="checkbox" :value="title" disabled class="article-item__input" />
              <span class="article-item__box">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="12" height="12"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" /></svg>
              </span>
              <span class="article-item__title" style="color: #64748b;">{{ title }}</span>
              <span class="already-submitted-inline-badge" style="font-size: 0.75rem; color: #64748b; background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px; margin-left: 8px;">Already submitted</span>
            </label>
          </div>
        </div>

        <!-- Empty / prompt state -->
        <div v-if="userCreatedArticles.length === 0 || (userCreatedArticles.length > 0 && availableArticles.length === 0 && submittedArticles.length === 0)" class="empty-state">
          <span v-if="isFetchingArticles" class="spinner" style="width:24px;height:24px;margin-bottom:12px;color:rgba(255,255,255,0.2);"></span>
          <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" width="40" height="40"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
          
          <template v-if="!isFetchingArticles">
            <p v-if="isOnBehalf && !onBehalfUsername">Select a user above, then click <strong>Fetch Articles</strong>.</p>
            <p v-else-if="userCreatedArticles.length > 0 && availableArticles.length === 0">All your fetched articles have already been submitted.</p>
            <p v-else>No articles found for the contest period.</p>
          </template>
        </div>
      </div>
    </div>

    <!-- Submit Button & Progress -->
    <div class="submit-section">
      <div v-if="isLoading && totalToSubmit > 0" class="submit-progress">
        <div class="submit-progress__info">
          <span>Submitting articles...</span>
          <span>{{ processedCount }} / {{ totalToSubmit }} ({{ submitProgress }}%)</span>
        </div>
        <div class="submit-progress__bar">
          <div class="submit-progress__fill" :style="{ width: submitProgress + '%' }"></div>
        </div>
      </div>

      <div class="submit-row">
        <button
          class="submit-btn"
          @click="handleSubmit"
          :disabled="isLoading || selectedArticles.length === 0"
          :class="{ 'submit-btn--loading': isLoading }"
        >
          <span v-if="isLoading" class="spinner spinner--white"></span>
          <span v-else>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="18" height="18" style="vertical-align:-4px;margin-right:8px;"><path d="M3.105 2.289a.75.75 0 00-.826.95l1.414 4.925A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.896 28.896 0 0015.293-7.154.75.75 0 000-1.115A28.897 28.897 0 003.105 2.289z" /></svg>
            Submit {{ selectedArticles.length > 0 ? `${selectedArticles.length} ` : '' }}Articles
          </span>
        </button>
      </div>
    </div>

    <!-- Results Card -->
    <div v-if="results.length > 0" class="card results-card">
      <div class="card__header">
        <div class="card__header-icon card__header-icon--green">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="18" height="18"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd" /></svg>
        </div>
        <div>
          <h2 class="card__title">Submission Results</h2>
          <p class="card__desc">{{ results.length }} article(s) processed.</p>
        </div>
      </div>
      <div class="card__body">
        <div class="results-table-wrapper">
          <table class="results-table">
            <thead>
              <tr>
                <th>Article Title</th>
                <th>Status</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(result, idx) in results" :key="idx" :class="['result-row', result.is_valid ? 'result-row--ok' : 'result-row--err']">
                <td class="result-title">{{ result.title }}</td>
                <td>
                  <span class="status-badge" :class="result.is_valid ? 'status-badge--ok' : 'status-badge--err'">
                    <svg v-if="result.is_valid" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="12" height="12"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" /></svg>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="12" height="12"><path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" /></svg>
                    {{ result.is_valid ? 'Accepted' : 'Error' }}
                  </span>
                </td>
                <td class="result-message">{{ result.is_valid ? 'Submitted successfully' : (result.error || '—') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Base ── */
.submit-page {
  font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
  background: #0d0f1c;
  min-height: 100%;
  padding: 32px 24px 64px;
  max-width: 860px;
  margin: 0 auto;
  box-sizing: border-box;
}

/* ── Page Header ── */
.page-header {
  margin-bottom: 28px;
}
.page-title {
  font-size: 1.875rem;
  font-weight: 700;
  color: #e2e8f0;
  margin: 0 0 6px;
  letter-spacing: -0.02em;
}
.page-subtitle {
  font-size: 0.9375rem;
  color: #6b7280;
  margin: 0;
}

/* ── On-Behalf Banner ── */
.behalf-banner {
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 14px 20px;
  margin-bottom: 20px;
}
.behalf-banner__inner {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.behalf-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}
.behalf-toggle__input {
  display: none;
}
.behalf-toggle__track {
  position: relative;
  width: 40px;
  height: 22px;
  background: rgba(255,255,255,0.1);
  border-radius: 11px;
  transition: background 0.2s;
  flex-shrink: 0;
}
.behalf-toggle__input:checked + .behalf-toggle__track {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
}
.behalf-toggle__thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 16px;
  height: 16px;
  background: #fff;
  border-radius: 50%;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  transition: transform 0.2s;
}
.behalf-toggle__input:checked ~ .behalf-toggle__track .behalf-toggle__thumb {
  transform: translateX(18px);
}
.behalf-toggle__label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #e5e7eb;
}
.behalf-lookup {
  flex: 1;
  min-width: 220px;
  max-width: 320px;
}

/* ── Card ── */
.card {
  background: #161829;
  border-radius: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3), 0 4px 16px rgba(0,0,0,0.2);
  border: 1px solid rgba(255,255,255,0.07);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  margin-bottom: 20px;
}
.card__header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.card__header-text {
  flex: 1;
  min-width: 0;
}
.card__header-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: rgba(255,255,255,0.1);
  color: #d1d5db;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.card__header-icon--green {
  background: rgba(255,255,255,0.1);
  color: #d1d5db;
}
.card__title {
  font-size: 1rem;
  font-weight: 700;
  color: #e2e8f0;
  margin: 0 0 3px;
}
.card__title-user {
  color: #e5e7eb;
}
.card__desc {
  font-size: 0.8125rem;
  color: #64748b;
  margin: 0;
}
.card__body {
  padding: 20px 24px 24px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── Article Search ── */
.article-search {
  position: relative;
  margin-bottom: 8px;
}
.article-search__input {
  width: 100%;
  padding: 10px 14px 10px 36px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  font-family: inherit;
  font-size: 0.875rem;
  color: #e2e8f0;
  transition: border-color 0.2s, background 0.2s;
  box-sizing: border-box;
}
.article-search__input:focus {
  outline: none;
  border-color: rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.06);
}
.article-search__input::placeholder {
  color: #64748b;
}
.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: #64748b;
  pointer-events: none;
}

/* ── Fetch Button ── */
.fetch-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 18px;
  background: rgba(255,255,255,0.1);
  color: #d1d5db;
  border: 1.5px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.18s, border-color 0.18s;
  white-space: nowrap;
  flex-shrink: 0;
}
.fetch-btn:hover:not(:disabled) {
  background: rgba(255,255,255,0.1);
  border-color: rgba(255,255,255,0.1);
}
.fetch-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Spinner ── */
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  display: inline-block;
  animation: spin 0.7s linear infinite;
}
.spinner--white {
  border-color: rgba(255,255,255,0.5);
  border-top-color: transparent;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Fetch Error ── */
.fetch-error {
  font-size: 0.8125rem;
  color: #d1d5db;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  padding: 8px 12px;
  margin: 0;
}

/* ── Article Section ── */
.article-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.article-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.article-section__label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #cbd5e1;
}
.article-section__actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.link-btn {
  background: none;
  border: none;
  font-size: 0.8125rem;
  color: #d1d5db;
  cursor: pointer;
  padding: 0;
  font-family: inherit;
  font-weight: 500;
  transition: color 0.15s;
}
.link-btn:hover { color: #d1d5db; }
.link-btn-sep {
  color: rgba(255,255,255,0.2);
  font-size: 0.8125rem;
}

/* ── Article List ── */
.article-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 340px;
  overflow-y: auto;
  padding-right: 4px;
}
.article-list::-webkit-scrollbar { width: 5px; }
.article-list::-webkit-scrollbar-track { background: rgba(255,255,255,0.04); border-radius: 99px; }
.article-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 99px; }

/* ── Article Item ── */
.article-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  border-radius: 8px;
  border: 1.5px solid rgba(255,255,255,0.07);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  background: rgba(255,255,255,0.03);
}
.article-item:hover {
  border-color: rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.1);
}
.article-item--checked {
  border-color: #ffffff;
  background: rgba(255,255,255,0.1);
}
.article-item__input {
  display: none;
}
.article-item__box {
  width: 18px;
  height: 18px;
  border-radius: 5px;
  border: 1.5px solid rgba(255,255,255,0.15);
  background: rgba(255,255,255,0.05);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: border-color 0.15s, background 0.15s;
  color: #fff;
}
.article-item--checked .article-item__box {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  border-color: #6366f1;
}
.article-item__title {
  font-size: 0.8375rem;
  color: #e2e8f0;
  line-height: 1.4;
  flex: 1;
  word-break: break-word;
}
.article-item--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.article-item--disabled:hover {
  background: rgba(255,255,255,0.03);
  border-color: rgba(255,255,255,0.07);
}
.article-item--disabled .article-item__box {
  background: rgba(255,255,255,0.1);
  border-color: rgba(255,255,255,0.2);
}
.already-submitted-inline-badge {
  font-size: 0.75rem;
  color: #d1d5db;
  font-weight: 600;
  background: rgba(255,255,255,0.1);
  padding: 4px 8px;
  border-radius: 6px;
  white-space: nowrap;
}



/* ── Empty State ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 16px;
  text-align: center;
  color: #64748b;
  flex: 1;
}
.empty-state svg { color: rgba(255,255,255,0.1); }
.empty-state p {
  font-size: 0.875rem;
  line-height: 1.6;
  max-width: 300px;
  margin: 0;
}
.empty-state strong { color: #e5e7eb; }

/* ── Submit Row & Progress ── */
.submit-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  margin-bottom: 28px;
}
.submit-progress {
  width: 100%;
  max-width: 420px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 16px 20px;
  box-sizing: border-box;
}
.submit-progress__info {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
  color: #e2e8f0;
  font-weight: 500;
  margin-bottom: 12px;
}
.submit-progress__bar {
  width: 100%;
  height: 8px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 99px;
  overflow: hidden;
}
.submit-progress__fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #818cf8);
  border-radius: 99px;
  transition: width 0.3s ease;
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
}
.submit-row {
  display: flex;
  justify-content: center;
  width: 100%;
}
.submit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  max-width: 420px;
  padding: 15px 36px;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(37,99,235,0.35);
  transition: opacity 0.18s, transform 0.12s, box-shadow 0.18s;
}
.submit-btn:hover:not(:disabled) {
  opacity: 0.92;
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(255,255,255,0.1);
}
.submit-btn:active:not(:disabled) { transform: translateY(0); }
.submit-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Results Card ── */
.results-card { margin-top: 4px; }
.results-table-wrapper {
  overflow-x: auto;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.07);
}
.results-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}
.results-table thead th {
  background: rgba(255,255,255,0.04);
  padding: 10px 16px;
  text-align: left;
  font-weight: 600;
  color: #94a3b8;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  white-space: nowrap;
}
.results-table tbody tr:not(:last-child) td {
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.results-table td {
  padding: 10px 16px;
  vertical-align: middle;
}
.result-row--ok { background: rgba(255,255,255,0.1); }
.result-row--err { background: rgba(255,255,255,0.1); }
.result-title {
  color: #e2e8f0;
  font-weight: 500;
  word-break: break-word;
  max-width: 400px;
}
.result-message {
  color: #6b7280;
  font-size: 0.8125rem;
}
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 99px;
  font-size: 0.75rem;
  font-weight: 600;
  white-space: nowrap;
}
.status-badge--ok {
  background: rgba(255,255,255,0.1);
  color: #d1d5db;
  border: 1px solid rgba(255,255,255,0.1);
}
.status-badge--err {
  background: rgba(255,255,255,0.1);
  color: #d1d5db;
  border: 1px solid rgba(255,255,255,0.1);
}
</style>
