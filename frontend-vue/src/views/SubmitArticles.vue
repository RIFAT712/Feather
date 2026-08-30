<script setup>
import { ref, onMounted, watch, inject, computed } from 'vue';
import { useRoute } from 'vue-router';
import { CdxButton, CdxLookup } from '@wikimedia/codex';
import { useQueryClient } from '@tanstack/vue-query';
import { invalidateContestData } from '../composables/useContestData';
import { formatDate, toDate } from '../utils/datetime';

const props = defineProps(['contest']);
const route = useRoute();
const user = inject('user');
const queryClient = useQueryClient();
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
const selectionRange = ref('');
const customSelectionCount = ref(1);
const isFetchingArticles = ref(false);
const fetchError = ref(null);
const alreadySubmittedTitles = ref([]);
const articleSearch = ref('');

const contestDate = (value) => toDate(value) || new Date(NaN);
const submissionNotOpen = computed(() => props.contest?.start_date && Date.now() < contestDate(props.contest.start_date).getTime());
const submissionClosed = computed(() => props.contest?.end_date && Date.now() > contestDate(props.contest.end_date).getTime());

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
watch([isOnBehalf, onBehalfUsername], () => {
  userCreatedArticles.value = [];
  selectedArticles.value = [];
  fetchError.value = null;
  articleSearch.value = '';
});
let fetchSeq = 0;

const fetchUserArticles = async () => {
  if (!props.contest || !user.value) return;
  if (submissionClosed.value || submissionNotOpen.value) {
    fetchError.value = submissionClosed.value
      ? 'This contest has ended. New article submissions are closed.'
      : 'This contest has not started yet. Submissions are not open.';
    return;
  }
  const mySeq = ++fetchSeq;
  isFetchingArticles.value = true;
  fetchError.value = null;
  userCreatedArticles.value = [];
  selectedArticles.value = [];
  const targetUser = (isOnBehalf.value && onBehalfUsername.value) ? onBehalfUsername.value : user.value.wiki_username;

  try {
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
    // Backed by the wiki replica DB (same source /submit-bulk validates
    // against) with a server-side usercontribs fallback -- see
    // /api/contests/{code}/user-created-articles in main.py. Replaces
    // paginating the public usercontribs API directly from the browser,
    // which was slower and relied on the same MediaWiki origin=* CORS
    // workaround the DB-backed validation elsewhere in this app doesn't need.
    const res = await fetch(`/api/contests/${route.params.code}/user-created-articles?username=${encodeURIComponent(targetUser)}`);
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    if (mySeq !== fetchSeq) return;
    // The endpoint returns [{title, created_at}] (creation date comes free
    // with the replica row it already reads). Older payloads only had
    // `titles`, so fall back to that and just show no date.
    userCreatedArticles.value = data.articles
      ? data.articles
      : [...new Set(data.titles || [])].map(title => ({ title, created_at: null }));
  } catch (err) {
    if (mySeq !== fetchSeq) return;
    fetchError.value = 'Failed to fetch articles from Wikipedia.';
  }
  finally {
    if (mySeq !== fetchSeq) return;
    isFetchingArticles.value = false;
  }
};

onMounted(async () => {
  try {
    const rolesRes = await fetch(`/api/contests/${route.params.code}/my-role`);
    if (rolesRes.ok) roles.value = await rolesRes.json();
    await fetchUserArticles();
  } catch (err) { console.error(err); }
});

const availableArticles = computed(() => userCreatedArticles.value.filter(article => !alreadySubmittedTitles.value.includes(article.title)));
const submittedArticles = computed(() => userCreatedArticles.value.filter(article => alreadySubmittedTitles.value.includes(article.title)));

const isAvailableOpen = ref(true);
const isSubmittedOpen = ref(false);

const matchesSearch = (article, query) => article.title.toLowerCase().includes(query);

const filteredAvailableArticles = computed(() => {
  const query = articleSearch.value.toLowerCase().trim();
  if (!query) return availableArticles.value;
  return availableArticles.value.filter(article => matchesSearch(article, query));
});

const filteredSubmittedArticles = computed(() => {
  const query = articleSearch.value.toLowerCase().trim();
  if (!query) return submittedArticles.value;
  return submittedArticles.value.filter(article => matchesSearch(article, query));
});

// Newest first by default -- what you just wrote is what you're most likely
// to be submitting. Articles with no creation date (the usercontribs
// fallback can omit it) sort to the bottom either way rather than jumping
// around as the direction flips.
const sortDirection = ref('desc');
const toggleSortDirection = () => { sortDirection.value = sortDirection.value === 'desc' ? 'asc' : 'desc'; };
const creationTime = (article) => {
  const parsed = toDate(article.created_at);
  const time = parsed ? parsed.getTime() : NaN;
  return Number.isNaN(time) ? null : time;
};
const sortByCreation = (articles) => {
  const factor = sortDirection.value === 'asc' ? 1 : -1;
  return [...articles].sort((a, b) => {
    const at = creationTime(a);
    const bt = creationTime(b);
    if (at === null && bt === null) return a.title.localeCompare(b.title);
    if (at === null) return 1;
    if (bt === null) return -1;
    return (at - bt) * factor;
  });
};
const formatCreated = (article) => {
  const parsed = toDate(article.created_at);
  return parsed && !Number.isNaN(parsed.getTime()) ? formatDate(parsed) : null;
};

const visibleAvailableArticles = computed(() => sortByCreation(filteredAvailableArticles.value));
const visibleSubmittedArticles = computed(() => sortByCreation(filteredSubmittedArticles.value));

const selectionOptions = computed(() => [
  'all',
  ...[10, 100, 1000, 2000].filter(amount => filteredAvailableArticles.value.length > amount),
  'custom',
]);
const effectiveSelectionLimit = computed(() => !selectionRange.value
  ? 0
  : selectionRange.value === 'all'
  ? Infinity
  : selectionRange.value === 'custom' ? Math.max(1, Number(customSelectionCount.value) || 1) : selectionRange.value);
const selectionRangeLabel = computed(() => selectionRange.value === 'all'
  ? 'all'
  : !selectionRange.value ? '—'
  : selectionRange.value === 'custom' ? effectiveSelectionLimit.value.toLocaleString() : selectionRange.value.toLocaleString());
const applySelectionRange = () => {
  if (!selectionRange.value) return;
  // Select from the sorted, on-screen order so "Select 10" takes the first
  // ten rows the user can actually see, not ten arbitrary ones.
  const inView = visibleAvailableArticles.value.map(article => article.title);
  selectedArticles.value = effectiveSelectionLimit.value === Infinity
    ? inView
    : inView.slice(0, effectiveSelectionLimit.value);
};
const deselectAll = () => { selectedArticles.value = []; };
const toggleArticleSelection = (title, event) => {
  if (event.target.checked) {
    const hasPresetLimit = Boolean(selectionRange.value) && effectiveSelectionLimit.value !== Infinity;
    if (hasPresetLimit && selectedArticles.value.length >= effectiveSelectionLimit.value) {
      event.target.checked = false;
      return;
    }
    selectedArticles.value = [...selectedArticles.value, title];
  } else {
    selectedArticles.value = selectedArticles.value.filter(item => item !== title);
  }
};

watch([selectionRange, customSelectionCount], applySelectionRange);

const handleSubmit = async () => {
  if (!selectedArticles.value.length) return;
  if (submissionNotOpen.value || submissionClosed.value) {
    fetchError.value = submissionNotOpen.value
      ? 'This contest has not started yet. Submissions are not open.'
      : 'This contest has ended. New article submissions are closed.';
    return;
  }
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
    if (isOnBehalf.value && onBehalfUsername.value) {
      payload.on_behalf_of = onBehalfUsername.value;
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
  
  // These submissions just changed the contest's article list -- any
  // Dashboard/Timeline Log/Jury Stats cache for it is now stale. Invalidating
  // means the next read anywhere (even a currently-mounted view) does a real
  // fetch instead of showing what existed before this submission.
  invalidateContestData(queryClient, contestCode);

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
    <div v-if="submissionClosed" class="submission-window-alert" role="alert">
      This contest has ended. New article submissions are closed.
    </div>
    <div v-else-if="submissionNotOpen" class="submission-window-alert" role="status">
      This contest has not started yet. Submissions are not open.
    </div>
    <div class="page-header">
      <h1 class="page-title">Submit Articles</h1>
      <p class="page-subtitle">
        Your eligible articles are automatically fetched. Select which ones to submit for review.
      </p>
    </div>

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
            {{ formatDate(contest.start_date) }} – {{ formatDate(contest.end_date) }}.
          </p>
        </div>
        <button
          v-if="roles.is_jury || roles.is_owner"
          class="fetch-btn"
          :class="{ 'fetch-btn--loading': isFetchingArticles }"
          @click="fetchUserArticles"
          :disabled="submissionClosed || submissionNotOpen || isFetchingArticles || (isOnBehalf && !onBehalfUsername)"
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

        <div v-if="filteredAvailableArticles.length > 0" class="article-section">
          <div class="article-section__header" @click="isAvailableOpen = !isAvailableOpen">
            <span class="article-section__label">
              <svg :style="{ transform: isAvailableOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="16" height="16" style="margin-right: 4px; vertical-align: -2px;"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
              Articles You Can Submit ({{ filteredAvailableArticles.length }})
              <span class="selection-counter">
                {{ selectedArticles.length }} selected
              </span>
            </span>
            <div class="article-section__actions" @click.stop>
              <label class="selection-range-control">
                <span>Select</span>
                <select v-model="selectionRange" aria-label="Number of articles to select">
                  <option value="" disabled>—</option>
                  <option v-for="amount in selectionOptions" :key="amount" :value="amount">
                    {{ amount === 'all' ? 'All' : amount === 'custom' ? 'Custom' : amount.toLocaleString() }}
                  </option>
                </select>
                <input v-if="selectionRange === 'custom'" v-model.number="customSelectionCount" type="number" min="1" :max="filteredAvailableArticles.length || 1" class="selection-custom-input" aria-label="Custom number of articles" />
              </label>
              <span class="link-btn-sep">·</span>
              <button
                type="button"
                class="sort-toggle"
                :aria-label="`Sort by creation date, ${sortDirection === 'desc' ? 'newest' : 'oldest'} first`"
                :title="sortDirection === 'desc' ? 'Newest first — click for oldest first' : 'Oldest first — click for newest first'"
                @click="toggleSortDirection"
              >
                <span>Date</span>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="13" height="13" :class="['sort-toggle__arrow', { 'sort-toggle__arrow--up': sortDirection === 'asc' }]"><path fill-rule="evenodd" d="M10 3a1 1 0 011 1v9.586l3.293-3.293a1 1 0 111.414 1.414l-5 5a1 1 0 01-1.414 0l-5-5a1 1 0 111.414-1.414L9 13.586V4a1 1 0 011-1z" clip-rule="evenodd" /></svg>
              </button>
              <span class="link-btn-sep">·</span>
              <button class="link-btn" @click="deselectAll">Deselect all</button>
            </div>
          </div>
          <div class="article-list" v-show="isAvailableOpen">
            <label
              v-for="article in visibleAvailableArticles"
              :key="article.title"
              class="article-item"
              :class="{ 'article-item--checked': selectedArticles.includes(article.title) }"
            >
              <input
                type="checkbox"
                :value="article.title"
                :checked="selectedArticles.includes(article.title)"
                @change="toggleArticleSelection(article.title, $event)"
                class="article-item__input"
              />
              <span class="article-item__box">
                <svg v-if="selectedArticles.includes(article.title)" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="12" height="12"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" /></svg>
              </span>
              <span class="article-item__title">{{ article.title }}</span>
              <span v-if="formatCreated(article)" class="article-item__date">{{ formatCreated(article) }}</span>
            </label>
          </div>
        </div>

        <div v-if="filteredSubmittedArticles.length > 0" class="article-section article-section--submitted">
          <div class="article-section__header" @click="isSubmittedOpen = !isSubmittedOpen">
            <span class="article-section__label">
              <svg :style="{ transform: isSubmittedOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="16" height="16" style="margin-right: 4px; vertical-align: -2px;"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
              Already Submitted ({{ filteredSubmittedArticles.length }})
            </span>
          </div>
          <div class="article-list" v-show="isSubmittedOpen">
            <label
              v-for="article in visibleSubmittedArticles"
              :key="article.title"
              class="article-item article-item--disabled"
            >
              <input type="checkbox" :value="article.title" disabled class="article-item__input" />
              <span class="article-item__box">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="12" height="12"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" /></svg>
              </span>
              <span class="article-item__title">{{ article.title }}</span>
              <span v-if="formatCreated(article)" class="article-item__date">{{ formatCreated(article) }}</span>
              <span class="already-submitted-inline-badge">Already submitted</span>
            </label>
          </div>
        </div>

                <div v-if="userCreatedArticles.length === 0 || (userCreatedArticles.length > 0 && availableArticles.length === 0 && submittedArticles.length === 0)" class="empty-state">
          <span v-if="isFetchingArticles" class="spinner spinner--large"></span>
          <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" width="40" height="40"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
          
          <template v-if="!isFetchingArticles">
            <p v-if="isOnBehalf && !onBehalfUsername">Select a user above, then click <strong>Fetch Articles</strong>.</p>
            <p v-else-if="userCreatedArticles.length > 0 && availableArticles.length === 0">All your fetched articles have already been submitted.</p>
            <p v-else>No articles found for the contest period.</p>
          </template>
        </div>
      </div>
    </div>

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
          :disabled="submissionClosed || submissionNotOpen || isLoading || selectedArticles.length === 0"
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
                    {{ result.is_valid ? 'Submitted' : 'Error' }}
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

<style scoped src="../styles/views/SubmitArticles.css"></style>
