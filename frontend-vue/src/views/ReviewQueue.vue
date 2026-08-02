<script setup>
import { ref, onMounted, onBeforeUnmount, inject, computed, watch } from 'vue';
import { useRoute } from 'vue-router';
import { CdxButton, CdxTextInput, CdxIcon } from '@wikimedia/codex';
import {
  cdxIconArticle,
  cdxIconArticleCheck,
  cdxIconArrowPrevious,
  cdxIconCheck,
  cdxIconCollapse,
  cdxIconCopy,
  cdxIconDownTriangle,
  cdxIconExpand,
  cdxIconLinkExternal,
  cdxIconLock,
  cdxIconMenu,
  cdxIconSpeechBubbles,
  cdxIconNext,
  cdxIconTrash,
  cdxIconUpTriangle,
} from '@wikimedia/codex-icons';

const props = defineProps(['contest']);
const route = useRoute();
const user = inject('user');

const articles = ref([]);
const currentArticle = ref(null);
const comment = ref('');
const isLoading = ref(true);
const isSubmitting = ref(false);
const isLoadingPreview = ref(false);
const reviewError = ref('');

// Mobile tab: 'list' | 'review'
const mobileTab = ref('list');
const sidebarCollapsed = ref(false);
const reviewPanelCollapsed = ref(false);

const showNewArticles = ref(true);
const showJudgedArticles = ref(false);
const showOtherReviewed = ref(false);

const roles = ref({ is_jury: false, is_owner: false });
const isAuthorized = computed(() => roles.value.is_jury || roles.value.is_owner);

const selectedForBulk = ref([]);
// Accepted/rejected articles retain their lock permanently to prevent double review.
const permanentlyLockedArticleIds = new Set();

const WIKI_BASE = 'https://bn.wiktionary.org/wiki/';

// Dark-mode CSS injected into the preview iframe
const DARK_CSS = `
  :root { color-scheme: dark; }
  html, body {
    background: #0a0a0a !important;
    color: #e2e8f0 !important;
    font-family: 'Linux Libertine', Georgia, Times, serif;
    font-size: 15px;
    line-height: 1.6;
    margin: 0;
    padding: 20px 24px 64px;
    max-width: 860px;
  }
  a { color: #d1d5db !important; }
  a:hover { text-decoration: underline; }

  /* --- strip ALL inline light-background colors from every element --- */
  * { background-color: unset !important; }

  /* tables */
  table { border-collapse: collapse; background: #1f1f1f !important; color: #e2e8f0 !important; }
  th, td { border: 1px solid rgba(255,255,255,0.12) !important; padding: 6px 10px; color: #e2e8f0 !important; }
  th { background: rgba(255,255,255,0.07) !important; }
  tr:nth-child(even) td { background: rgba(255,255,255,0.03) !important; }

  /* wikitable */
  .wikitable { background: #1f1f1f !important; border: 1px solid rgba(255,255,255,0.15) !important; }
  .wikitable > * > tr > th { background: rgba(255,255,255,0.1) !important; color: #e5e7eb !important; }
  .wikitable > * > tr > td { background: transparent !important; }

  /* NavFrame */
  .NavFrame {
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 6px;
    background: #1f1f1f !important;
    margin: 12px 0;
    overflow: hidden;
  }
  .NavHead {
    background: rgba(255,255,255,0.1) !important;
    color: #e5e7eb !important;
    padding: 6px 10px !important;
    cursor: pointer !important;
    font-weight: 600;
    user-select: none;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .NavHead:hover { background: rgba(255,255,255,0.1) !important; }
  .NavToggle { color: #e5e7eb !important; font-size: 0.85em; }
  .NavContent { background: #111111 !important; }
  .NavContent td, .NavContent th { border-color: rgba(255,255,255,0.09) !important; }

  /* vsToggle */
  .vsToggleElement[style*='background'] { background: rgba(255,255,255,0.1) !important; color: #e5e7eb !important; }
  th[class~='vsToggleElement'] { background: rgba(255,255,255,0.1) !important; color: #e5e7eb !important; cursor: pointer !important; }

  /* mw-collapsible */
  .mw-collapsible-toggle { cursor: pointer; color: #d1d5db !important; }
  .mw-collapsed .mw-collapsible-content { display: none !important; }

  /* headings */
  h1, h2, h3, h4, h5 {
    color: #e2e8f0 !important;
    border-bottom: 1px solid rgba(255,255,255,0.1) !important;
    padding-bottom: 4px;
  }
  h2 { font-size: 1.4em; margin-top: 1.4em; }
  h3 { font-size: 1.15em; margin-top: 1em; }
  h4 { font-size: 1em; border-bottom: none !important; }

  /* TOC */
  #toc, .toc { background: #1f1f1f !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 6px; padding: 12px 18px; }
  .toc a { color: #d1d5db !important; }
  .toctitle { color: #e5e7eb !important; }

  /* hide edit links */
  .mw-editsection, .mw-editsection-bracket { display: none !important; }

  /* infobox */
  .infobox { background: #1f1f1f !important; border: 1px solid rgba(255,255,255,0.12) !important; }
  .infobox th { background: rgba(255,255,255,0.07) !important; }

  /* references */
  .reflist, ol.references { color: #94a3b8 !important; font-size: 0.85em; }
  .reflist a, .references a { color: #d1d5db !important; }

  /* categories */
  .catlinks { background: #1f1f1f !important; border: 1px solid rgba(255,255,255,0.1) !important; color: #94a3b8 !important; margin-top: 24px; padding: 8px 14px; border-radius: 6px; }
  .catlinks a { color: #d1d5db !important; }

  /* hatnote/notices */
  .hatnote, .dablink { background: rgba(255,255,255,0.04) !important; border-left: 3px solid #ffffff !important; padding: 6px 12px; color: #94a3b8 !important; }

  /* ib-header / inflection tables with inline styles */
  [style*='background:#'], [style*='background: #'], [style*='background:rgb'], [style*='background: rgb'] {
    background: rgba(80,80,120,0.25) !important;
    color: #e2e8f0 !important;
  }
  /* keep text-align / font-weight from inline styles but neutralise colour */
  [style*='color:rgb'], [style*='color: rgb'] { color: #e2e8f0 !important; }
`;

// JS injected into preview iframe for full collapsible support
const COLLAPSIBLE_JS = `
  (function() {
    function initNavFrames() {
      document.querySelectorAll('.NavFrame').forEach(function(frame) {
        var head = frame.querySelector('.NavHead');
        var content = frame.querySelector('.NavContent');
        if (!head || !content) return;
        content.style.display = 'none';
        var toggle = head.querySelector('.NavToggle a');
        if (!toggle) {
          var wrapper = document.createElement('span');
          wrapper.className = 'NavToggle';
          wrapper.style.cssText = 'float:right; font-weight:normal; font-size:smaller; padding-left: 8px;';
          toggle = document.createElement('a');
          toggle.href = '#';
          wrapper.appendChild(toggle);
          head.appendChild(wrapper);
        }
        toggle.textContent = '▶';
        head.style.cursor = 'pointer';
        head.addEventListener('click', function(e) {
          e.preventDefault();
          var hidden = content.style.display === 'none';
          content.style.display = hidden ? '' : 'none';
          toggle.textContent = hidden ? '▼' : '▶';
        });
      });
    }

    function initVsToggles() {
      document.querySelectorAll('.vsToggleElement').forEach(function(el) {
        var table = el.closest('table');
        if (!table) return;
        var anchor = el.querySelector('.NavToggle a');
        if (!anchor) {
          var wrapper = document.createElement('span');
          wrapper.className = 'NavToggle';
          wrapper.style.cssText = 'float:right; font-weight:normal; font-size:smaller; padding-left: 8px;';
          anchor = document.createElement('a');
          anchor.href = '#';
          wrapper.appendChild(anchor);
          el.appendChild(wrapper);
        }
        var shows = table.querySelectorAll('.vsShow');
        var hides = table.querySelectorAll('.vsHide');
        shows.forEach(function(r){ r.style.display = 'none'; });
        hides.forEach(function(r){ r.style.display = ''; });
        anchor.textContent = '▶';
        el.style.cursor = 'pointer';
        el.addEventListener('click', function(e) {
          e.preventDefault();
          var isExpanded = anchor.textContent.includes('▼');
          if (isExpanded) {
            shows.forEach(function(r){ r.style.display = 'none'; });
            hides.forEach(function(r){ r.style.display = ''; });
            anchor.textContent = '▶';
          } else {
            shows.forEach(function(r){ r.style.display = ''; });
            hides.forEach(function(r){ r.style.display = 'none'; });
            anchor.textContent = '▼';
          }
        });
      });
    }

    function initMwCollapsibles() {
      document.querySelectorAll('.mw-collapsible, table.collapsed, table.mw-collapsed').forEach(function(el) {
        var isTable = el.tagName === 'TABLE';
        var head = isTable ? el.querySelector('tr') : el.firstElementChild;
        if (!head) return;
        var toggler = el.querySelector('.mw-collapsible-toggle');
        if (!toggler) {
          toggler = document.createElement('span');
          toggler.className = 'mw-collapsible-toggle';
          toggler.style.cssText = 'float:right; cursor:pointer; user-select:none; font-size:smaller; padding-left:8px;';
          var th = head.querySelector('th') || head.querySelector('td') || head;
          if(th) th.appendChild(toggler);
        }
        toggler.textContent = '▶';
        if (isTable) {
          var rows = el.querySelectorAll('tr');
          rows.forEach(function(row, idx) { if (idx > 0) row.style.display = 'none'; });
        } else {
          var content = el.querySelector('.mw-collapsible-content');
          if (content) { content.style.display = 'none'; }
          else { Array.from(el.children).forEach(function(child, idx) { if (idx > 0) child.style.display = 'none'; }); }
        }
        head.style.cursor = 'pointer';
        head.addEventListener('click', function(e) {
          e.preventDefault();
          var isCollapsed = toggler.textContent.includes('▶');
          toggler.textContent = isCollapsed ? '▼' : '▶';
          if (isTable) {
            var rows = el.querySelectorAll('tr');
            rows.forEach(function(row, idx) { if (idx > 0) row.style.display = isCollapsed ? '' : 'none'; });
          } else {
            var content = el.querySelector('.mw-collapsible-content');
            if (content) { content.style.display = isCollapsed ? '' : 'none'; }
            else { Array.from(el.children).forEach(function(child, idx) { if (idx > 0) child.style.display = isCollapsed ? '' : 'none'; }); }
          }
        });
      });
    }

    document.addEventListener('DOMContentLoaded', function() {
      initNavFrames(); initVsToggles(); initMwCollapsibles();
    });
    if (document.readyState !== 'loading') {
      initNavFrames(); initVsToggles(); initMwCollapsibles();
    }
  })();
`;

const previewSrcdoc = ref('');

const fetchPreview = async (title) => {
  isLoadingPreview.value = true;
  previewSrcdoc.value = '';
  try {
    const res = await fetch(`https://bn.wiktionary.org/w/api.php?action=parse&page=${encodeURIComponent(title)}&format=json&prop=text&origin=*`);
    const data = await res.json();
    const body = data.parse?.text?.['*'] ?? '<p style="color:#94a3b8">Preview not available.</p>';
    previewSrcdoc.value = `<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="utf-8">
<base href="https://bn.wiktionary.org/wiki/">
<style>${DARK_CSS}</style>
</head>
<body class="mw-body mw-parser-output">
${body}
<script>${COLLAPSIBLE_JS}<\/script>
</body>
</html>`;
  } catch (e) {
    console.error(e);
    previewSrcdoc.value = `<!DOCTYPE html><html><body style="color:#d1d5db;background:#0a0a0a;padding:24px">Error loading preview.</body></html>`;
  } finally {
    isLoadingPreview.value = false;
  }
};

const fetchArticles = async (showLoading = true) => {
  if (showLoading) isLoading.value = true;
  try {
    const roleRes = await fetch(`/api/contests/${route.params.code}/my-role`);
    if (roleRes.ok) roles.value = await roleRes.json();

    if (!isAuthorized.value) {
      isLoading.value = false;
      return;
    }

    const response = await fetch(`/api/contests/${route.params.code}/log`);
    if (response.ok) {
      articles.value = await response.json();
    }
  } catch (error) {
    console.error("Failed to fetch articles", error);
  } finally {
    isLoading.value = false;
  }
};

const myUsername = computed(() => user.value?.wiki_username);

const newArticles = computed(() => {
  if (!myUsername.value) return [];
  return articles.value.filter(a =>
    a.status === 'pending' &&
    !(roles.value.is_jury && !roles.value.is_owner && a.submitted_by === myUsername.value) &&
    !a.reviews.some(r => r.reviewer === myUsername.value)
  );
});

const availableNewArticles = computed(() => {
  return newArticles.value.filter(a => !a.locked_by || a.locked_by === myUsername.value);
});

const statusStats = computed(() => ({
  total: articles.value.length,
  accepted: articles.value.filter(a => a.status === 'accepted').length,
  rejected: articles.value.filter(a => a.status === 'rejected').length,
  pending: articles.value.filter(a => a.status === 'pending').length,
}));

const releaseArticleLock = (articleId) => {
  if (!articleId || permanentlyLockedArticleIds.has(articleId)) return;
  fetch(`/api/articles/${articleId}/lock`, { method: 'DELETE' }).catch(() => {});
};

const judgedArticles = computed(() => {
  if (!myUsername.value) return [];
  return articles.value.filter(a => a.reviews.some(r => r.reviewer === myUsername.value));
});

const otherReviewedArticles = computed(() => {
  if (!myUsername.value) return [];
  return articles.value.filter(a =>
    a.status !== 'pending' &&
    a.reviews.length > 0 &&
    !a.reviews.some(r => r.reviewer === myUsername.value)
  );
});

const getMyLatestDecision = (article) => {
  const myReviews = article.reviews.filter(r => r.reviewer === myUsername.value);
  if (!myReviews.length) return null;
  return myReviews[myReviews.length - 1].decision;
};

const getMyLatestComment = (article) => {
  const myReviews = article.reviews.filter(r => r.reviewer === myUsername.value);
  if (!myReviews.length) return '';
  return myReviews[myReviews.length - 1].comment || '';
};

const selectArticle = (article) => {
  const canReReview = article?.reviews?.some(r => r.reviewer === myUsername.value);
  if (!article || (article.status !== 'pending' && !canReReview)) return;
  reviewError.value = '';
  if (currentArticle.value?.article_id && currentArticle.value.article_id !== article?.article_id) {
    releaseArticleLock(currentArticle.value.article_id);
  }
  currentArticle.value = article;
  comment.value = getMyLatestComment(article);
  fetchPreview(article.title);
  fetch(`/api/articles/${article.article_id}/lock`, { method: 'POST' }).catch(() => {});
  // On mobile, auto-switch to review tab
  mobileTab.value = 'review';
};

let statsInterval;

onMounted(async () => {
  await fetchArticles();
  statsInterval = setInterval(() => {
    fetchArticles(false).catch(error => console.error('Failed to refresh review queue', error));
  }, 5000);
  if (availableNewArticles.value.length > 0 && !currentArticle.value) {
    const randomIdx = Math.floor(Math.random() * availableNewArticles.value.length);
    selectArticle(availableNewArticles.value[randomIdx]);
    if (window.innerWidth <= 768) {
      mobileTab.value = 'list';
    }
  }
});

const skipArticle = () => {
  const previousArticleId = currentArticle.value?.article_id;
  releaseArticleLock(previousArticleId);
  const next = availableNewArticles.value.find(a => a.article_id !== currentArticle.value?.article_id);
  if (next) {
    selectArticle(next);
  } else if (newArticles.value.length > 0) {
    const fallback = newArticles.value.find(a => a.article_id !== currentArticle.value?.article_id) || newArticles.value[0];
    selectArticle(fallback);
  } else {
    currentArticle.value = articles.value.find(a => a.article_id === currentArticle.value?.article_id) || null;
  }
};

watch(mobileTab, (tab) => {
  if (tab === 'list') releaseArticleLock(currentArticle.value?.article_id);
});

onBeforeUnmount(() => {
  clearInterval(statsInterval);
  releaseArticleLock(currentArticle.value?.article_id);
});

const handleDecision = async (decision) => {
  if (!currentArticle.value || isSubmitting.value) return;
  isSubmitting.value = true;
  reviewError.value = '';
  try {
    const res = await fetch(`/api/articles/${currentArticle.value.article_id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, comment: comment.value }),
    });
    if (!res.ok) {
      const errorBody = await res.json().catch(() => ({}));
      throw new Error(errorBody.detail || `Review failed (${res.status})`);
    }
    if (decision === 'accepted' || decision === 'rejected') {
      permanentlyLockedArticleIds.add(currentArticle.value.article_id);
    }
    comment.value = '';
    await fetchArticles();
    if (availableNewArticles.value.length > 0) {
      selectArticle(availableNewArticles.value[0]);
    } else if (newArticles.value.length > 0) {
      selectArticle(newArticles.value[0]);
    } else {
      currentArticle.value = articles.value.find(a => a.article_id === currentArticle.value.article_id);
      mobileTab.value = 'list';
    }
  } catch (error) {
    console.error("Error submitting review", error);
    reviewError.value = error.message || 'Review failed';
  } finally {
    isSubmitting.value = false;
  }
};

const handleRemoveArticle = async (article) => {
  if (!article || isSubmitting.value) return;
  if (!confirm(`Remove "${article.title}" permanently from this contest?`)) return;
  isSubmitting.value = true;
  try {
    const res = await fetch(`/api/articles/${article.article_id}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Remove failed');
    releaseArticleLock(article.article_id);
    if (currentArticle.value?.article_id === article.article_id) {
      currentArticle.value = null;
      mobileTab.value = 'list';
    }
    await fetchArticles();
  } catch (error) {
    console.error("Error removing article", error);
  } finally {
    isSubmitting.value = false;
  }
};

const handleRemove = () => handleRemoveArticle(currentArticle.value);


const toggleBulkSelection = (article_id, e) => {
  e.stopPropagation();
  const idx = selectedForBulk.value.indexOf(article_id);
  if (idx > -1) {
    selectedForBulk.value.splice(idx, 1);
  } else {
    selectedForBulk.value.push(article_id);
  }
};

const handleBulkDecision = async (decision) => {
  if (isSubmitting.value || !selectedForBulk.value.length) return;
  isSubmitting.value = true;
  const errors = [];
  try {
    for (const article_id of selectedForBulk.value) {
      const res = await fetch(`/api/articles/${article_id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, comment: 'Bulk reviewed' }),
      });
      if (!res.ok) {
        errors.push(article_id);
      } else if (decision === 'accepted' || decision === 'rejected') {
        permanentlyLockedArticleIds.add(article_id);
      }
    }
    selectedForBulk.value = [];
    await fetchArticles();
    if (!currentArticle.value || !availableNewArticles.value.find(a => a.article_id === currentArticle.value.article_id)) {
      if (availableNewArticles.value.length > 0) {
        const randomIdx = Math.floor(Math.random() * availableNewArticles.value.length);
        selectArticle(availableNewArticles.value[randomIdx]);
      } else {
        currentArticle.value = null;
        mobileTab.value = 'list';
      }
    }
  } catch (err) {
    console.error("Bulk review failed", err);
  } finally {
    if (errors.length) {
      console.warn(`Bulk review: ${errors.length} article(s) failed to update:`, errors);
    }
    isSubmitting.value = false;
  }
};

const handleBulkRemove = async () => {
  if (isSubmitting.value || !selectedForBulk.value.length) return;
  if (!confirm(`Are you sure you want to permanently remove ${selectedForBulk.value.length} article(s) from the contest?`)) return;
  isSubmitting.value = true;
  try {
    for (const article_id of selectedForBulk.value) {
      await fetch(`/api/articles/${article_id}`, { method: 'DELETE' });
    }
    selectedForBulk.value = [];
    currentArticle.value = null;
    await fetchArticles();
    mobileTab.value = 'list';
  } catch (err) {
    console.error("Bulk remove failed", err);
  } finally {
    isSubmitting.value = false;
  }
};

const articleUrl = (title) => `${WIKI_BASE}${encodeURIComponent(title)}`;

const talkPageSnippet = computed(() => {
  if (!props.contest?.add_talk_template) return '';
  let template = props.contest.talk_template_name || '';
  template = template.trim();
  if (template && !template.startsWith('{{')) {
    template = `{{${template}}}`;
  }
  let snippet = '';
  if (props.contest.include_talk_header) {
    snippet += '{{আলাপ পাতা}}\n\n';
  }
  if (template) {
    snippet += template;
  }
  return snippet;
});

const isCopiedTalkSnippet = ref(false);
const copyTalkSnippet = () => {
  if (!talkPageSnippet.value) return;
  navigator.clipboard.writeText(talkPageSnippet.value);
  isCopiedTalkSnippet.value = true;
  setTimeout(() => { isCopiedTalkSnippet.value = false; }, 2500);
};
</script>

<template>
  <div class="review-queue">
    <!-- Unauthorized -->
    <div v-if="!isLoading && !isAuthorized" class="center-state">
      <div class="unauth-card">
        <span class="unauth-icon">⛔</span>
        <h2>Access Denied</h2>
        <p>This area is restricted to Contest Jury members and Owners.</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-else-if="isLoading" class="center-state">
      <div class="loading-spinner"></div>
      <p class="loading-text">Loading review queue…</p>
    </div>

    <!-- Main Layout -->
    <div v-else class="main-layout">
      <!-- ═══════════════ SIDEBAR ═══════════════ -->
      <aside class="sidebar" :class="{ 'mobile-hidden': mobileTab !== 'list', collapsed: sidebarCollapsed }">
        <button
          type="button"
          class="sidebar-toggle"
          :aria-label="sidebarCollapsed ? 'Expand article sidebar' : 'Collapse article sidebar'"
          :title="sidebarCollapsed ? 'Expand article sidebar' : 'Collapse article sidebar'"
          @click="sidebarCollapsed = !sidebarCollapsed"
        ><CdxIcon :icon="sidebarCollapsed ? cdxIconExpand : cdxIconCollapse" /></button>
        <div class="queue-heading">
          <div>
            <span class="queue-eyebrow">JURY WORKSPACE</span>
            <h2>Review Queue</h2>
          </div>
          <span class="queue-live">Live</span>
        </div>
        <!-- Stats row -->
        <div class="sidebar-stats">
          <div class="stat-pill total">
            <span class="stat-num">{{ statusStats.total }}</span>
            <span class="stat-lbl">Total</span>
          </div>
          <div class="stat-pill accepted">
            <span class="stat-num">{{ statusStats.accepted }}</span>
            <span class="stat-lbl">Accepted</span>
          </div>
          <div class="stat-pill rejected">
            <span class="stat-num">{{ statusStats.rejected }}</span>
            <span class="stat-lbl">Rejected</span>
          </div>
          <div class="stat-pill pending">
            <span class="stat-num">{{ statusStats.pending }}</span>
            <span class="stat-lbl">Pending</span>
          </div>
        </div>

        <!-- Bulk Actions Banner -->
        <div v-if="selectedForBulk.length > 0" class="bulk-banner">
          <span class="bulk-label">{{ selectedForBulk.length }} selected</span>
          <div class="bulk-btns">
            <button class="bbtn accept" @click="handleBulkDecision('accepted')" title="Accept Selected"><CdxIcon :icon="cdxIconCheck" /></button>
            <button class="bbtn reject" @click="handleBulkDecision('rejected')" title="Reject Selected"><CdxIcon :icon="cdxIconClear" /></button>
            <button class="bbtn skip" @click="handleBulkDecision('skipped')" title="Skip Selected"><CdxIcon :icon="cdxIconNext" /></button>
            <button class="bbtn remove" @click="handleBulkRemove" title="Remove Selected"><CdxIcon :icon="cdxIconTrash" /></button>
          </div>
        </div>

        <div class="sidebar-scroll">
        <!-- New Articles section -->
        <div class="section-head" @click="showNewArticles = !showNewArticles">
          <span class="section-title">
            <span class="section-dot pending-dot"></span>
            Pending Review
          </span>
          <span class="section-count">{{ newArticles.length }}</span>
          <CdxIcon :icon="showNewArticles ? cdxIconUpTriangle : cdxIconDownTriangle" class="section-chevron" />
        </div>
        <transition name="section-slide">
          <ul v-show="showNewArticles" class="article-list">
            <li
              v-for="a in newArticles"
              :key="a.article_id"
              class="article-item"
              :class="{ active: currentArticle?.article_id === a.article_id, locked: a.locked_by && a.locked_by !== myUsername }"
              @click="selectArticle(a)"
            >
              <label class="cb-wrap" @click.stop>
                <input type="checkbox" :checked="selectedForBulk.includes(a.article_id)" @change="toggleBulkSelection(a.article_id, $event)" class="bulk-cb" />
              </label>
              <div class="item-body">
                <span class="item-title">{{ a.title }}</span>
                <span class="item-sub">by {{ a.submitted_by }}</span>
              </div>
              <CdxIcon v-if="a.locked_by && a.locked_by !== myUsername" :icon="cdxIconLock" class="lock-badge" title="Being reviewed by someone" />
            </li>
            <li v-if="!newArticles.length" class="empty-item">
              <span><CdxIcon :icon="cdxIconArticleCheck" /> All articles reviewed!</span>
            </li>
          </ul>
        </transition>

        <!-- Articles reviewed by other judges -->
        <div v-if="otherReviewedArticles.length" class="section-head other-reviewed-head" @click="showOtherReviewed = !showOtherReviewed">
          <span class="section-title">
            <span class="section-dot judged-dot"></span>
            Reviewed by Other Judges
          </span>
          <span class="section-count">{{ otherReviewedArticles.length }}</span>
          <CdxIcon :icon="showOtherReviewed ? cdxIconUpTriangle : cdxIconDownTriangle" class="section-chevron" />
        </div>
        <ul v-if="showOtherReviewed && otherReviewedArticles.length" class="article-list read-only-list">
          <li
            v-for="a in otherReviewedArticles"
            :key="`other-${a.article_id}`"
            class="article-item judged read-only-item"
          >
            <div class="item-body">
              <span class="item-title">{{ a.title }}</span>
              <span class="item-sub">Reviewed by {{ a.reviews.map(r => r.reviewer).join(', ') }}</span>
            </div>
            <span class="verdict-badge" :class="a.status">
              {{ a.status === 'accepted' ? '✓' : '✕' }}
            </span>
          </li>
        </ul>

        <!-- Judged Articles section -->
        <div class="section-head" @click="showJudgedArticles = !showJudgedArticles">
          <span class="section-title">
            <span class="section-dot judged-dot"></span>
            My Judged
          </span>
          <span class="section-count">{{ judgedArticles.length }}</span>
          <CdxIcon :icon="showJudgedArticles ? cdxIconUpTriangle : cdxIconDownTriangle" class="section-chevron" />
        </div>
        <transition name="section-slide">
          <ul v-show="showJudgedArticles" class="article-list">
            <li
              v-for="a in judgedArticles"
              :key="a.article_id"
              class="article-item judged"
              :class="{ active: currentArticle?.article_id === a.article_id }"
              @click="selectArticle(a)"
            >
              <div class="item-body">
                <span class="item-title">{{ a.title }}</span>
                <span class="item-sub">by {{ a.submitted_by }}</span>
              </div>
              <span
                class="verdict-badge"
                :class="getMyLatestDecision(a)"
              >
                {{ getMyLatestDecision(a) === 'accepted' ? '✓' : getMyLatestDecision(a) === 'rejected' ? '✕' : '→' }}
              </span>
            </li>
            <li v-if="!judgedArticles.length" class="empty-item">
              <span>Nothing judged yet</span>
            </li>
          </ul>
        </transition>

        </div>
      </aside>

      <!-- ═══════════════ REVIEW AREA ═══════════════ -->
      <div class="review-area" :class="{ 'mobile-hidden': mobileTab !== 'review' }">
        <!-- Empty state -->
        <div v-if="!currentArticle" class="center-state full">
          <div class="done-state">
            <div class="done-icon"><CdxIcon :icon="cdxIconArticleCheck" /></div>
            <h3>All Caught Up!</h3>
            <p>You have reviewed all available articles.</p>
          </div>
        </div>

        <template v-else>
          <!-- Article Header Bar -->
          <div class="article-header">
            <!-- Mobile back button -->
            <button class="back-btn mobile-only" @click="mobileTab = 'list'">
              <CdxIcon :icon="cdxIconArrowPrevious" /> Back
            </button>
            <div class="article-header-info">
              <a :href="articleUrl(currentArticle.title)" target="_blank" class="article-title-link" :title="currentArticle.title">
                {{ currentArticle.title }}
              </a>
              <div class="article-meta">
                <span class="meta-chip">by {{ currentArticle.submitted_by }}</span>
                <span v-if="currentArticle.wiki_creation_date" class="meta-chip">
                  {{ new Date(currentArticle.wiki_creation_date).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' }) }}
                </span>
                <span v-if="currentArticle.locked_by && currentArticle.locked_by !== myUsername" class="lock-chip">
                  <CdxIcon :icon="cdxIconLock" /> {{ currentArticle.locked_by }} reviewing
                </span>
                <span v-if="getMyLatestDecision(currentArticle)" class="verdict-chip" :class="getMyLatestDecision(currentArticle)">
                  {{ getMyLatestDecision(currentArticle) === 'accepted' ? '✓ Accepted' : getMyLatestDecision(currentArticle) === 'rejected' ? '✕ Rejected' : '→ Skipped' }}
                </span>
              </div>
            </div>
            <a :href="articleUrl(currentArticle.title)" target="_blank" class="open-wiki-btn" title="Open on Wiktionary">
              <CdxIcon :icon="cdxIconLinkExternal" /> Wiki
            </a>
          </div>

          <!-- Talk Template Card -->
          <div v-if="false && props.contest?.add_talk_template && talkPageSnippet" class="talk-card">
            <CdxIcon :icon="cdxIconSpeechBubbles" class="talk-icon" />
            <div class="talk-info">
              <span class="talk-label">Talk Template</span>
              <code class="talk-code">{{ talkPageSnippet.replace(/\n\n/g, '  |  ') }}</code>
            </div>
            <div class="talk-actions">
              <button class="talk-copy-btn" @click="copyTalkSnippet">
                <CdxIcon :icon="isCopiedTalkSnippet ? cdxIconCheck : cdxIconCopy" />
                {{ isCopiedTalkSnippet ? 'Copied!' : 'Copy' }}
              </button>
              <a :href="'https://bn.wiktionary.org/wiki/আলাপ:' + encodeURIComponent(currentArticle.title)" target="_blank" class="talk-open-btn">
              <CdxIcon :icon="cdxIconLinkExternal" /> Talk
              </a>
            </div>
          </div>

          <!-- Preview Area -->
          <div class="preview-wrap">
            <div v-if="isLoadingPreview" class="preview-loading">
              <div class="loading-spinner small"></div>
              <span>Loading preview…</span>
            </div>
            <iframe
              v-else
              class="wiki-iframe"
              sandbox="allow-scripts"
              :srcdoc="previewSrcdoc"
              referrerpolicy="no-referrer"
            ></iframe>
          </div>

          <!-- Review Action Bar (sticky at bottom) -->
          <div class="review-bar" :class="{ 'is-collapsed': reviewPanelCollapsed }">
            <div class="review-bar-inner">
              <button
                type="button"
                class="review-panel-toggle"
                :aria-label="reviewPanelCollapsed ? 'Expand review panel' : 'Collapse review panel'"
                :title="reviewPanelCollapsed ? 'Expand review panel' : 'Collapse review panel'"
                @click="reviewPanelCollapsed = !reviewPanelCollapsed"
              ><CdxIcon :icon="reviewPanelCollapsed ? cdxIconExpand : cdxIconCollapse" /></button>
              <div class="review-panel-heading">
                <span class="review-panel-kicker">DECISION</span>
                <h3>Review this article</h3>
                <p>Leave an optional note, then choose a verdict.</p>
              </div>
              <template v-if="!reviewPanelCollapsed">
                <div v-if="reviewError" class="review-error">{{ reviewError }}</div>
                <div class="review-comment">
                  <label for="jury-comment">Jury comment</label>
                  <cdx-text-input
                    id="jury-comment"
                    v-model="comment"
                    placeholder="Leave a note (optional)…"
                  />
                </div>
                <div class="review-actions">
                <button
                  class="action-btn accept-btn"
                  :disabled="isSubmitting"
                  @click="handleDecision('accepted')"
                >
                  <CdxIcon :icon="cdxIconCheck" class="action-icon" />
                  <span class="action-label">Accept</span>
                </button>
                <button
                  class="action-btn reject-btn"
                  :disabled="isSubmitting"
                  @click="handleDecision('rejected')"
                >
                  <CdxIcon :icon="cdxIconClear" class="action-icon" />
                  <span class="action-label">Reject</span>
                </button>
                <button
                  class="action-btn skip-btn"
                  :disabled="isSubmitting"
                  @click="skipArticle"
                >
                  <CdxIcon :icon="cdxIconNext" class="action-icon" />
                  <span class="action-label">Skip</span>
                </button>
                <button
                  class="action-btn remove-btn"
                  :disabled="isSubmitting"
                  @click="handleRemove"
                >
                  <CdxIcon :icon="cdxIconTrash" class="action-icon" />
                  <span class="action-label">Remove</span>
                </button>
                </div>
              </template>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- ═══════════════ MOBILE BOTTOM NAV ═══════════════ -->
    <nav class="mobile-bottom-nav mobile-only">
      <button
        class="mob-nav-btn"
        :class="{ active: mobileTab === 'list' }"
        @click="mobileTab = 'list'"
      >
        <CdxIcon :icon="cdxIconMenu" class="mob-nav-icon" />
        <span class="mob-nav-lbl">Articles <span class="mob-badge">{{ newArticles.length }}</span></span>
      </button>
      <button
        class="mob-nav-btn"
        :class="{ active: mobileTab === 'review' }"
        @click="mobileTab = 'review'"
        :disabled="!currentArticle"
      >
        <CdxIcon :icon="cdxIconArticle" class="mob-nav-icon" />
        <span class="mob-nav-lbl">Review</span>
      </button>
    </nav>
  </div>
</template>

<style scoped>
/* ─── Base ─────────────────────────────────────────── */
.review-queue {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: #0a0a0a;
  position: relative;
}

.center-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 40px 24px;
  gap: 16px;
  color: #9ca3af;
}

.unauth-card {
  text-align: center;
  background: #1f1f1f;
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 16px;
  padding: 40px 48px;
  max-width: 440px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.unauth-icon { font-size: 3rem; display: block; margin-bottom: 12px; }
.unauth-card h2 { color: #f1f5f9; margin: 0 0 8px; font-size: 1.4rem; }
.unauth-card p { color: #94a3b8; margin: 0; font-size: 0.9rem; line-height: 1.6; }

.loading-spinner {
  width: 36px; height: 36px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #4f46e5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-spinner.small { width: 20px; height: 20px; border-width: 2px; }
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { color: #94a3b8; font-size: 0.9rem; margin: 0; }

/* ─── Main Layout (desktop: sidebar + panel) ────────── */
.main-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ─── Sidebar ───────────────────────────────────────── */
.sidebar {
  width: 288px;
  flex-shrink: 0;
  background: #131520;
  border-right: 1px solid rgba(255,255,255,0.06);
  display: flex;
  flex-direction: column;
  overflow: visible;
  position: relative;
  overflow-x: hidden;
  box-sizing: border-box;
  transition: width 0.2s ease;
  z-index: 20;
}

/* Stats Row */
.sidebar-stats {
  display: flex;
  gap: 8px;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.stat-pill {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 4px;
  border-radius: 10px;
  background: rgba(255,255,255,0.04);
}
.stat-pill.pending { background: rgba(245, 158, 11, 0.1); }
.stat-pill.accepted { background: rgba(34, 197, 94, 0.1); }
.stat-pill.rejected { background: rgba(239, 68, 68, 0.1); }
.stat-pill.total { background: rgba(99, 102, 241, 0.1); }
.other-reviewed-head { order: 3; }
.read-only-list { order: 4; }
.read-only-item { cursor: default; opacity: 0.8; }
.stat-num {
  font-size: 1.2rem;
  font-weight: 700;
  color: #e2e8f0;
  line-height: 1;
}
.stat-lbl { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.06em; color: #64748b; }

/* Bulk Banner */
.bulk-banner {
  padding: 10px 14px;
  background: #111111;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.bulk-label { font-size: 0.78rem; font-weight: 600; color: #e5e7eb; white-space: nowrap; }
.bulk-btns { display: flex; gap: 6px; flex-wrap: wrap; }
.bbtn {
  padding: 4px 12px;
  border: none;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  color: #fff;
  transition: filter 0.15s, transform 0.1s;
}
.bbtn:disabled { opacity: 0.5; cursor: not-allowed; }
.bbtn:active:not(:disabled) { transform: scale(0.96); }
.bbtn.accept { background: #16a34a; }
.bbtn.accept:hover:not(:disabled) { filter: brightness(1.1); }
.bbtn.reject { background: #dc2626; }
.bbtn.reject:hover:not(:disabled) { filter: brightness(1.1); }
.bbtn.clear { background: rgba(255,255,255,0.1); }
.bbtn.clear:hover { background: rgba(255,255,255,0.15); }
.bbtn.skip { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.1); }
.bbtn.skip:hover:not(:disabled) { background: rgba(255,255,255,0.12); }
.bbtn.remove { background: #991b1b; }
.bbtn.remove:hover:not(:disabled) { filter: brightness(1.1); }

/* Section Headers */
.section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  position: sticky;
  top: 0;
  z-index: 2;
  background: #131520;
  transition: background 0.15s;
}
.section-head:hover { background: rgba(255,255,255,0.04); }
.section-title {
  flex: 1;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 7px;
}
.section-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.pending-dot { background: #f59e0b; }
.judged-dot { background: #22c55e; }
.section-count {
  font-size: 0.7rem;
  font-weight: 700;
  color: #475569;
  background: rgba(255,255,255,0.07);
  border-radius: 10px;
  padding: 1px 7px;
}
.section-chevron { font-size: 0.72rem; color: #475569; }

/* Article List */
.article-list {
  list-style: none;
  margin: 0;
  padding: 4px 0;
  overflow-y: auto;
  flex: 1;
}
.article-list::-webkit-scrollbar { width: 3px; }
.article-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }

.article-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  cursor: pointer;
  transition: background 0.12s;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}
.article-item:hover { background: rgba(255,255,255,0.05); }
.article-item.active {
  background: rgba(79, 70, 229, 0.18);
  border-left: 3px solid #4f46e5;
}
.article-item.locked { opacity: 0.6; }

.cb-wrap { flex-shrink: 0; display: flex; align-items: center; }
.bulk-cb {
  width: 14px; height: 14px;
  cursor: pointer;
  accent-color: #4f46e5;
}

.item-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.item-title {
  font-size: 0.83rem;
  font-weight: 500;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}
.article-item.active .item-title { color: #a5b4fc; }
.item-sub { font-size: 0.7rem; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.lock-badge { font-size: 0.75rem; flex-shrink: 0; }
.verdict-badge {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 5px;
  flex-shrink: 0;
}
.verdict-badge.accepted { background: rgba(34,197,94,0.15); color: #22c55e; }
.verdict-badge.rejected { background: rgba(239,68,68,0.15); color: #ef4444; }
.verdict-badge.skipped { background: rgba(148,163,184,0.15); color: #94a3b8; }

.empty-item {
  padding: 20px 16px;
  color: rgba(255,255,255,0.25);
  font-size: 0.8rem;
  font-style: italic;
  text-align: center;
}

/* Section slide animation */
.section-slide-enter-active,
.section-slide-leave-active {
  transition: opacity 0.18s ease;
}
.section-slide-enter-from,
.section-slide-leave-to {
  opacity: 0;
}

/* ─── Review Area ────────────────────────────────────── */
.review-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #0a0a0a;
  min-width: 0;
}
.review-area.full { flex: 1; }

.done-state {
  text-align: center;
  background: #131520;
  border: 1px solid rgba(99,102,241,0.2);
  border-radius: 16px;
  padding: 48px;
  max-width: 360px;
}
.done-icon { font-size: 3rem; margin-bottom: 12px; }
.done-state h3 { color: #e2e8f0; margin: 0 0 8px; font-size: 1.2rem; }
.done-state p { color: #64748b; margin: 0; font-size: 0.9rem; }

/* Article Header Bar */
.article-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: #131520;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  flex-shrink: 0;
  flex-wrap: wrap;
  min-height: 56px;
}
.article-header-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.article-title-link {
  font-size: 1rem;
  font-weight: 700;
  color: #e2e8f0;
  text-decoration: none;
  font-family: 'Linux Libertine', Georgia, Times, serif;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}
.article-title-link:hover { color: #a5b4fc; }
.article-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.meta-chip {
  font-size: 0.72rem;
  color: #64748b;
  background: rgba(255,255,255,0.05);
  padding: 2px 8px;
  border-radius: 6px;
}
.lock-chip {
  font-size: 0.72rem;
  color: #f59e0b;
  background: rgba(245,158,11,0.1);
  padding: 2px 8px;
  border-radius: 6px;
}
.verdict-chip {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 6px;
}
.verdict-chip.accepted { background: rgba(34,197,94,0.15); color: #22c55e; }
.verdict-chip.rejected { background: rgba(239,68,68,0.15); color: #ef4444; }
.verdict-chip.skipped { background: rgba(148,163,184,0.12); color: #94a3b8; }
.open-wiki-btn {
  font-size: 0.78rem;
  font-weight: 600;
  color: #a5b4fc;
  background: rgba(99,102,241,0.1);
  border: 1px solid rgba(99,102,241,0.2);
  padding: 5px 12px;
  border-radius: 8px;
  text-decoration: none;
  white-space: nowrap;
  transition: background 0.15s;
  flex-shrink: 0;
}
.open-wiki-btn:hover { background: rgba(99,102,241,0.2); }

/* Talk Template Card */
.talk-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  background: #111;
  border-bottom: 1px solid rgba(255,255,255,0.12);
  flex-shrink: 0;
  flex-wrap: wrap;
}
.talk-icon { font-size: 1rem; flex-shrink: 0; }
.talk-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.talk-label { font-size: 0.67rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #fff; }
.talk-code { font-size: 0.8rem; color: #e5e5e5; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-family: monospace; }
.talk-actions { display: flex; gap: 8px; align-items: center; flex-shrink: 0; }
.talk-copy-btn {
  background: #222;
  color: #fff;
  border: none;
  padding: 5px 12px;
  border-radius: 7px;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
}
.talk-copy-btn:hover { background: #333; }
.talk-open-btn {
  color: #e5e5e5;
  font-size: 0.75rem;
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;
}
.talk-open-btn:hover { text-decoration: underline; }

/* Preview */
.preview-wrap {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #0a0a0a;
  min-height: 0;
}
.preview-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 12px;
  color: #64748b;
  font-size: 0.85rem;
}
.wiki-iframe {
  flex: 1;
  width: 100%;
  border: none;
  background: #0a0a0a;
  min-height: 0;
}

/* Review Action Bar */
.review-bar {
  background: #131520;
  border-top: 1px solid rgba(255,255,255,0.07);
  box-shadow: 0 -4px 24px rgba(0,0,0,0.35);
  flex-shrink: 0;
  padding: 12px 16px;
  z-index: 10;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}
.review-bar-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  width: 100%;
  min-width: 0;
  position: relative;
}
.review-comment { flex: 1; min-width: 180px; }
.review-actions { display: flex; gap: 8px; flex-shrink: 0; }
.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  border: none;
  border-radius: 10px;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  transition: filter 0.15s, transform 0.1s;
  color: #fff;
}
.action-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.action-btn:active:not(:disabled) { transform: scale(0.96); }
.action-btn .action-icon { font-size: 1rem; }
.accept-btn { background: linear-gradient(135deg, #16a34a, #15803d); box-shadow: 0 2px 12px rgba(22,163,74,0.3); }
.accept-btn:hover:not(:disabled) { filter: brightness(1.1); }
.reject-btn { background: linear-gradient(135deg, #dc2626, #b91c1c); box-shadow: 0 2px 12px rgba(220,38,38,0.3); }
.reject-btn:hover:not(:disabled) { filter: brightness(1.1); }
.remove-btn { background: linear-gradient(135deg, #991b1b, #7f1d1d); box-shadow: 0 2px 12px rgba(153,27,27,0.3); }
.remove-btn:hover:not(:disabled) { filter: brightness(1.1); }
.skip-btn { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.1); color: #94a3b8; }
.skip-btn:hover:not(:disabled) { background: rgba(255,255,255,0.12); color: #e2e8f0; }

/* Back button (mobile) */
.back-btn {
  background: rgba(255,255,255,0.07);
  border: 1px solid rgba(255,255,255,0.1);
  color: #94a3b8;
  padding: 5px 12px;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  white-space: nowrap;
  transition: background 0.15s;
}
.back-btn:hover { background: rgba(255,255,255,0.12); color: #e2e8f0; }

/* ─── Mobile Bottom Nav ─────────────────────────────── */
.mobile-bottom-nav {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0; right: 0;
  background: #131520;
  border-top: 1px solid rgba(255,255,255,0.08);
  z-index: 100;
  box-shadow: 0 -4px 24px rgba(0,0,0,0.5);
  padding-bottom: env(safe-area-inset-bottom);
}
.mob-nav-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 10px 8px;
  background: none;
  border: none;
  color: #64748b;
  font-size: 0.7rem;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.15s;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.mob-nav-btn:disabled { opacity: 0.35; cursor: default; }
.mob-nav-btn.active { color: #818cf8; }
.mob-nav-icon { font-size: 1.2rem; }
.mob-nav-lbl { display: flex; align-items: center; gap: 4px; }
.mob-badge {
  background: #4f46e5;
  color: #fff;
  font-size: 0.6rem;
  padding: 1px 5px;
  border-radius: 8px;
  font-weight: 700;
}

/* ─── Responsive Breakpoints ────────────────────────── */
.mobile-only { display: none; }

@media (max-width: 768px) {
  .mobile-only { display: flex; }

  .review-queue {
    height: 100%;
    min-height: 0;
    background: #080a10;
  }

  .main-layout {
    flex-direction: column;
    height: calc(100% - 60px);
    flex: 0 0 calc(100% - 60px);
    min-height: 0;
    overflow: hidden;
  }

  .sidebar {
    width: 100%;
    height: 100%;
    min-height: 0;
    padding: 12px 12px 18px;
    gap: 8px;
    background: linear-gradient(180deg, #111522 0%, #080a10 100%);
    border: 0;
    overflow-y: auto;
    overflow-x: hidden;
    box-sizing: border-box;
    flex-shrink: 0;
  }
  .sidebar > * { flex-shrink: 0; }
  .sidebar-stats {
    gap: 8px;
    padding: 0 0 4px;
  }
  .stat-pill {
    min-height: 58px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.07);
    background: rgba(255,255,255,0.035);
  }
  .stat-num { font-size: 1.25rem; }
  .section-head {
    min-height: 46px;
    padding: 0 12px;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    background: rgba(255,255,255,0.035);
  }
  .article-list {
    max-height: none;
    overflow: visible;
    padding: 0;
  }
  .article-item {
    min-height: 62px;
    margin: 4px 0;
    padding: 11px 12px;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    background: rgba(255,255,255,0.025);
  }
  .article-item.active {
    background: rgba(99,102,241,0.16);
    border-color: rgba(129,140,248,0.45);
    box-shadow: 0 4px 18px rgba(0,0,0,0.18);
  }
  .item-title { font-size: 0.92rem; }
  .item-sub { font-size: 0.72rem; }
  .bulk-banner {
    margin: 0;
    padding: 10px 12px;
    border-radius: 12px;
  }
  .sidebar-toggle { display: none !important; }
  .sidebar.collapsed { width: 100%; background: #080a10; }

  .review-area {
    width: 100%;
    height: 100%;
    flex: 0 0 100%;
    min-height: 0;
    overflow: hidden;
    background: #080a10;
    padding-bottom: 110px;
    box-sizing: border-box;
  }
  .review-area.mobile-hidden,
  .sidebar.mobile-hidden {
    display: none !important;
  }

  .article-header {
    flex: 0 0 auto;
    min-height: 62px;
    padding: 10px 12px;
    gap: 8px;
    background: rgba(17,21,34,0.98);
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .back-btn {
    display: inline-flex;
    flex-shrink: 0;
    padding: 7px 9px;
    border-radius: 9px;
    font-size: 0.76rem;
  }
  .article-header-info { gap: 4px; }
  .article-title-link {
    max-width: 52vw;
    font-size: 0.94rem;
  }
  .article-meta { gap: 4px; }
  .meta-chip {
    max-width: 38vw;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .open-wiki-btn {
    flex-shrink: 0;
    padding: 7px 9px;
    border-radius: 9px;
    font-size: 0.72rem;
  }

  .preview-wrap {
    flex: 1 1 0;
    min-height: 0;
    height: auto;
    background: #0a0a0a;
  }
  .wiki-iframe {
    display: block;
    width: 100%;
    height: 100%;
    min-height: 0;
  }

  .review-bar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 60px;
    width: 100%;
    z-index: 40;
    flex: none;
    margin: 0;
    padding: 9px 10px 10px;
    background: #111522;
    border-top: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 -8px 24px rgba(0,0,0,0.28);
  }
  .review-bar-inner {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  .review-comment { width: 100%; min-width: 0; }
  .review-comment .cdx-text-input { width: 100%; }
  .review-actions {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 6px;
  }
  .action-btn {
    width: 100%;
    min-width: 0;
    min-height: 40px;
    padding: 8px 4px;
    border-radius: 9px;
    justify-content: center;
  }
  .action-btn .action-label { display: none; }
  .action-btn .action-icon { font-size: 1.05rem; }

  .mobile-bottom-nav {
    display: flex;
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    flex: none;
    height: 60px;
    min-height: 60px;
    padding: 5px 10px calc(5px + env(safe-area-inset-bottom));
    box-sizing: border-box;
    background: rgba(13,16,26,0.98);
    border-top: 1px solid rgba(255,255,255,0.1);
    z-index: 30;
  }
  .mob-nav-btn {
    min-height: 46px;
    border-radius: 11px;
    color: #64748b;
  }
  .mob-nav-btn.active {
    color: #c7d2fe;
    background: rgba(99,102,241,0.16);
  }

  .mobile-hidden { display: none !important; }
  .review-queue { padding-bottom: 0; }
}

.review-error {
  flex: 0 0 100%;
  color: #fca5a5;
  font-size: 0.85rem;
  padding: 0 0 6px;
}

@media (max-width: 480px) {
  .sidebar { padding: 10px 10px 16px; }
  .stat-pill { min-height: 54px; }
  .action-btn { min-height: 38px; }
}

/* Retained desktop collapse rules; mobile uses the dedicated two-screen layout above. */
@media (min-width: 769px) {
  .review-area { min-height: 0; }
}

/* Calm monochrome review workspace */
.review-queue,
.review-area,
.preview-wrap { background: var(--background-color-base); }
.main-layout { background: var(--background-color-base); }
.sidebar {
  width: 320px;
  background: var(--background-color-neutral-subtle);
  border-right: 1px solid var(--border-color-muted);
}
.sidebar-toggle,
.sidebar.collapsed .sidebar-toggle {
  background: var(--background-color-interactive);
  border-color: var(--border-color-base);
  color: var(--color-emphasized);
  box-shadow: 0 2px 8px rgba(0,0,0,0.55);
}
.sidebar-toggle:hover { background: var(--background-color-interactive--hover); }
.sidebar-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  padding: 16px;
  border-bottom-color: #292929;
}
.stat-pill,
.stat-pill.pending,
.stat-pill.accepted,
.stat-pill.rejected,
.stat-pill.total {
  background: var(--background-color-interactive-subtle);
  border: 1px solid var(--border-color-muted);
  border-radius: 7px;
  padding: 10px 8px;
}
.stat-pill:hover { background: var(--background-color-interactive); }
.stat-num { color: var(--color-emphasized); font-size: 1.15rem; }
.stat-lbl { color: var(--color-subtle); }
.section-head {
  position: static;
  background: var(--background-color-neutral-subtle);
  border-bottom: 1px solid var(--border-color-muted);
  padding: 13px 16px;
}
.section-head:hover { background: var(--background-color-interactive-subtle--hover); }
.section-title { color: var(--color-neutral); }
.section-dot,
.pending-dot,
.judged-dot { background: var(--color-subtle); }
.section-count {
  color: var(--color-base);
  background: var(--background-color-neutral);
  border: 1px solid var(--border-color-muted);
}
.section-chevron { color: var(--color-subtle); }
.article-list { padding: 6px 8px; }
.article-item {
  padding: 12px 10px;
  border: 1px solid transparent;
  border-bottom-color: var(--border-color-muted);
}
.article-item:hover { background: var(--background-color-interactive-subtle--hover); }
.article-item.active {
  background: var(--background-color-interactive);
  border-left: 3px solid var(--color-emphasized);
  border-top-color: var(--border-color-base);
  border-right-color: var(--border-color-base);
}
.article-item.active .item-title { color: var(--color-emphasized); }
.item-title { color: var(--color-base); }
.item-sub { color: var(--color-subtle); }
.verdict-badge,
.verdict-badge.accepted,
.verdict-badge.rejected,
.verdict-badge.skipped {
  background: var(--background-color-neutral);
  color: var(--color-neutral);
  border: 1px solid var(--border-color-muted);
}
.review-area { border-left: 1px solid #1e1e1e; }
.article-header {
  padding: 18px 28px;
  background: var(--background-color-neutral-subtle);
  border-bottom-color: var(--border-color-muted);
}
.article-title-link { color: var(--color-emphasized); font-size: 1.08rem; }
.article-title-link:hover { color: var(--color-base--hover); }
.meta-chip {
  background: var(--background-color-interactive-subtle);
  color: var(--color-subtle);
  border: 1px solid var(--border-color-muted);
}
.open-wiki-btn {
  color: var(--color-base);
  background: var(--background-color-interactive-subtle);
  border-color: var(--border-color-muted);
}
.open-wiki-btn:hover { background: var(--background-color-interactive--hover); }
.preview-wrap { padding: 18px 24px 0; }
.wiki-iframe {
  border: 1px solid var(--border-color-muted);
  border-bottom: 0;
  border-radius: 8px 8px 0 0;
}
.review-bar {
  background: var(--background-color-neutral-subtle);
  border-top-color: var(--border-color-base);
  box-shadow: 0 -8px 24px rgba(0,0,0,0.4);
  padding: 16px 24px;
}
.review-comment .cdx-text-input__input {
  background: var(--background-color-disabled-subtle);
  border-color: var(--border-color-muted);
  color: var(--color-emphasized);
}
.skip-btn,
.back-btn {
  background: var(--background-color-interactive-subtle);
  border-color: var(--border-color-muted);
  color: var(--color-neutral);
}
.skip-btn:hover:not(:disabled),
.back-btn:hover { background: var(--background-color-interactive--hover); color: var(--color-emphasized); }
.loading-spinner { border-top-color: #f0f0f0; }
.mobile-bottom-nav { background: var(--background-color-neutral-subtle); border-top-color: var(--border-color-muted); }
.mob-nav-btn.active { color: var(--color-emphasized); background: var(--background-color-neutral); }
.mob-badge { background: var(--background-color-interactive); }

@media (max-width: 768px) {
  .sidebar {
    width: 100%;
    background: var(--background-color-base);
    border: 0;
  }
  .sidebar-stats { grid-template-columns: repeat(4, minmax(0, 1fr)); padding: 0 0 4px; }
  .stat-pill,
  .stat-pill.pending,
  .stat-pill.accepted,
  .stat-pill.rejected,
  .stat-pill.total { background: #171717; }
  .section-head { background: var(--background-color-neutral-subtle); }
  .section-head:hover { background: var(--background-color-interactive-subtle--hover); }
  .article-item { background: var(--background-color-interactive-subtle); }
  .article-item.active { background: var(--background-color-interactive); border-color: var(--border-color-base); border-left-color: var(--color-emphasized); }
  .article-item:hover { background: var(--background-color-interactive-subtle--hover); }
  .review-area { border-left: 0; background: var(--background-color-base); }
  .article-header { padding: 10px 12px; background: var(--background-color-neutral-subtle); }
  .preview-wrap { padding: 0; }
  .wiki-iframe { border: 0; border-radius: 0; }
  .review-bar { padding: 9px 10px 10px; background: var(--background-color-neutral-subtle); }
}
@media (min-width: 769px) {
  .main-layout { position: relative; }
  .sidebar { width: 300px; }
  .queue-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 22px 18px 18px;
    border-bottom: 1px solid var(--border-color-muted);
  }
  .queue-eyebrow,
  .review-panel-kicker {
    display: block;
    color: var(--color-subtle);
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.1em;
  }
  .queue-heading h2,
  .review-panel-heading h3 {
    margin: 5px 0 0;
    color: var(--color-emphasized);
    font-size: 1.12rem;
    line-height: 1.2;
  }
  .queue-live {
    padding: 4px 8px;
    border: 1px solid var(--border-color-muted);
    border-radius: 4px;
    color: var(--color-subtle);
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .review-area { position: relative; display: flex; }
  .article-header { margin-right: 360px; padding: 22px 28px; }
  .preview-wrap { margin-right: 360px; padding: 22px 26px 0; }
  .review-bar {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 360px;
    box-sizing: border-box;
    padding: 26px 24px;
    border-top: 0;
    border-left: 1px solid var(--border-color-muted);
    box-shadow: none;
  }
  .review-bar-inner {
    height: 100%;
    flex-direction: column;
    align-items: stretch;
    flex-wrap: nowrap;
    gap: 18px;
  }
  .review-panel-heading p {
    margin: 8px 0 0;
    color: var(--color-subtle);
    font-size: 0.82rem;
    line-height: 1.5;
  }
  .review-comment { flex: 0 0 auto; }
  .review-comment label {
    display: block;
    margin-bottom: 8px;
    color: var(--color-neutral);
    font-size: 0.78rem;
    font-weight: 600;
  }
  .review-comment .cdx-text-input,
  .review-comment .cdx-text-input__input { width: 100%; box-sizing: border-box; }
  .review-actions {
    flex-direction: column;
    gap: 10px;
    margin-top: auto;
  }
  .action-btn {
    width: 100%;
    min-height: 44px;
    justify-content: center;
  }
  .review-error { flex: 0 0 auto; }
}

@media (max-width: 768px) {
  .review-panel-heading { display: none; }
  .queue-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 2px 12px;
    border-bottom: 1px solid var(--border-color-muted);
  }
  .queue-heading h2 { margin: 4px 0 0; color: var(--color-emphasized); font-size: 1.05rem; }
  .queue-eyebrow { color: var(--color-subtle); font-size: 0.62rem; font-weight: 700; letter-spacing: 0.1em; }
  .queue-live { padding: 3px 7px; border: 1px solid var(--border-color-muted); border-radius: 4px; color: var(--color-subtle); font-size: 0.62rem; text-transform: uppercase; }
}

/* Compact desktop ribbons: keep the original bottom review workflow. */
@media (min-width: 769px) {
  .sidebar { width: 270px; }
  .queue-heading { padding: 12px 14px 10px; align-items: center; }
  .queue-heading h2 { font-size: 0.98rem; }
  .queue-eyebrow { font-size: 0.58rem; }
  .queue-live { padding: 3px 6px; font-size: 0.58rem; }
  .sidebar-stats { padding: 10px 12px; gap: 5px; }
  .stat-pill { padding: 7px 5px; }
  .stat-num { font-size: 1rem; }
  .stat-lbl { font-size: 0.58rem; }
  .section-head { padding: 8px 12px; }
  .article-list { padding: 3px 6px; }
  .article-item { padding: 8px 8px; gap: 8px; }
  .article-header { margin-right: 0; padding: 10px 16px; min-height: 52px; }
  .article-title-link { font-size: 0.98rem; }
  .preview-wrap { margin-right: 0; padding: 12px 16px 0; }
  .review-bar {
    position: static;
    width: 100%;
    padding: 9px 14px;
    border-top: 1px solid var(--border-color-base);
    border-left: 0;
    box-shadow: none;
  }
  .review-bar-inner {
    height: auto;
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .review-panel-heading { display: none; }
  .review-comment { flex: 1 1 240px; }
  .review-comment label { display: none; }
  .review-actions { flex-direction: row; gap: 6px; margin-top: 0; }
  .action-btn { width: auto; min-height: 36px; padding: 7px 13px; border-radius: 6px; }
}

/* One scroll container keeps every queue section reachable and predictable. */
.sidebar {
  overflow: hidden;
  transition: none;
}
.sidebar-toggle {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 4;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--border-color-muted);
  border-radius: 4px;
  background: var(--background-color-interactive-subtle);
  color: var(--color-subtle);
  cursor: pointer;
}
.sidebar-toggle:hover {
  background: var(--background-color-interactive-subtle--hover);
  color: var(--color-emphasized);
}
.sidebar.collapsed {
  width: 44px;
  background: var(--background-color-base);
  border-right-color: var(--border-color-muted);
}
.sidebar.collapsed > :not(.sidebar-toggle) { display: none; }
.sidebar.collapsed .sidebar-toggle {
  position: static;
  margin: 8px auto;
}
.sidebar-scroll {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.sidebar-scroll .article-list {
  flex: none;
  max-height: none;
  overflow: visible;
}
.sidebar-scroll .section-head {
  position: static;
}
.section-chevron {
  width: 16px;
  height: 16px;
  color: var(--color-subtle);
  flex: 0 0 16px;
}
.article-header {
  min-height: 44px;
  padding: 6px 12px;
  gap: 8px;
}
.article-header-info { gap: 2px; }
.article-title-link { font-size: 0.96rem; }
.article-meta { gap: 4px; }
.review-panel-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--border-color-muted);
  border-radius: 4px;
  background: var(--background-color-interactive-subtle);
  color: var(--color-subtle);
  cursor: pointer;
}
.review-panel-toggle:hover {
  background: var(--background-color-interactive-subtle--hover);
  color: var(--color-emphasized);
}
.review-bar.is-collapsed { padding: 6px 10px; }
.review-bar.is-collapsed .review-bar-inner {
  min-height: 28px;
  justify-content: flex-end;
}
@media (max-width: 768px) {
  .sidebar-scroll { overflow-y: auto; }
  .sidebar-toggle { display: none; }
  .sidebar.collapsed { width: 100%; }
  .article-header { min-height: 46px; padding: 6px 10px; }
  .article-title-link { font-size: 0.92rem; }
  .review-bar.is-collapsed { padding: 5px 8px; }
}
</style>
