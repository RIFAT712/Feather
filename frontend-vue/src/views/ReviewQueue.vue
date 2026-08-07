<script setup>
import { ref, onMounted, onBeforeUnmount, inject, computed, watch } from 'vue';
import { useRoute } from 'vue-router';
import { CdxButton, CdxTextInput, CdxIcon } from '@wikimedia/codex';
import {
  cdxIconArticle,
  cdxIconArticleCheck,
  cdxIconArrowPrevious,
  cdxIconCheck,
  cdxIconClear,
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
const mobileTab = ref('list');
const sidebarCollapsed = ref(false);
const reviewPanelCollapsed = ref(false);

const showNewArticles = ref(true);
const showJudgedArticles = ref(false);
const showOtherReviewed = ref(false);

const roles = ref({ is_jury: false, is_owner: false });
const isAuthorized = computed(() => roles.value.is_jury || roles.value.is_owner);

const selectedForBulk = ref([]);
const permanentlyLockedArticleIds = new Set();

const WIKI_BASE = 'https://bn.wiktionary.org/wiki/';
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
  /* Wikipedia-style link colors */
  a { color: #3366cc !important; }
  a:visited { color: #795cb2 !important; }
  a.new, a.new:visited { color: #d33 !important; }  /* red-links (missing pages) */
  a:hover { text-decoration: underline; }

  /* TOC, reflist, catlinks links inherit wiki-blue */
  .toc a, .toc a:visited { color: #3366cc !important; }
  .reflist a, .references a { color: #3366cc !important; }
  .catlinks a { color: #3366cc !important; }

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
  .toctitle { color: #e5e7eb !important; }

  /* hide edit links */
  .mw-editsection, .mw-editsection-bracket { display: none !important; }

  /* infobox */
  .infobox { background: #1f1f1f !important; border: 1px solid rgba(255,255,255,0.12) !important; }
  .infobox th { background: rgba(255,255,255,0.07) !important; }

  /* references */
  .reflist, ol.references { color: #94a3b8 !important; font-size: 0.85em; }

  /* categories */
  .catlinks { background: #1f1f1f !important; border: 1px solid rgba(255,255,255,0.1) !important; color: #94a3b8 !important; margin-top: 24px; padding: 8px 14px; border-radius: 6px; }

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
  mobileTab.value = 'review';
};

let statsInterval;

onMounted(async () => {
  await fetchArticles();
  statsInterval = setInterval(() => {
    fetchArticles(false).catch(error => console.error('Failed to refresh review queue', error));
  }, 5000);
  if (availableNewArticles.value.length > 0 && !currentArticle.value) {
    selectArticle(availableNewArticles.value[0]);
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
        selectArticle(availableNewArticles.value[0]);
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
  <div class="rq-app">
    <div v-if="!isLoading && !isAuthorized" class="rq-center-state">
      <div class="rq-card-unauth">
        <div class="rq-icon-large">⛔</div>
        <h2>Access Denied</h2>
        <p>This area is restricted to Contest Jury members and Owners.</p>
      </div>
    </div>

    <div v-else-if="isLoading" class="rq-center-state">
      <div class="rq-spinner"></div>
      <p class="rq-loading-text">Loading review queue…</p>
    </div>

    <div v-else class="rq-main-layout" :class="{ 'is-mobile-review': mobileTab === 'review' }">
      <aside class="rq-sidebar" :class="{ 'is-collapsed': sidebarCollapsed }">
        <header class="rq-sidebar-header">
          <div class="rq-sidebar-top">
            <div class="rq-brand-eyebrow">
              <span class="rq-eyebrow-text">Jury Workspace</span>
              <span class="rq-badge-live">Live</span>
            </div>
            <button
              type="button"
              class="rq-icon-btn rq-collapse-btn"
              @click="sidebarCollapsed = !sidebarCollapsed"
              :title="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
            >
              <CdxIcon :icon="sidebarCollapsed ? cdxIconExpand : cdxIconCollapse" />
            </button>
          </div>
          
          <div class="rq-sidebar-title-row" v-show="!sidebarCollapsed">
            <h2 class="rq-sidebar-title">Review Queue</h2>
          </div>

          <div class="rq-stats-strip" v-show="!sidebarCollapsed">
            <div class="rq-stat"><span class="rq-stat-val">{{ statusStats.total }}</span><span class="rq-stat-lbl">Total</span></div>
            <div class="rq-stat rq-stat-pending"><span class="rq-stat-val">{{ statusStats.pending }}</span><span class="rq-stat-lbl">Pending</span></div>
            <div class="rq-stat rq-stat-ok"><span class="rq-stat-val">{{ statusStats.accepted }}</span><span class="rq-stat-lbl">OK</span></div>
            <div class="rq-stat rq-stat-rej"><span class="rq-stat-val">{{ statusStats.rejected }}</span><span class="rq-stat-lbl">Rej</span></div>
          </div>
        </header>

        <transition name="rq-fade">
          <div v-if="selectedForBulk.length > 0 && !sidebarCollapsed" class="rq-bulk-banner">
            <span class="rq-bulk-count">{{ selectedForBulk.length }} selected</span>
            <div class="rq-bulk-actions">
              <button class="rq-bbtn rq-bbtn-accept" @click="handleBulkDecision('accepted')" title="Accept"><CdxIcon :icon="cdxIconCheck" /></button>
              <button class="rq-bbtn rq-bbtn-reject" @click="handleBulkDecision('rejected')" title="Reject"><CdxIcon :icon="cdxIconClear" /></button>
              <button class="rq-bbtn rq-bbtn-skip" @click="handleBulkDecision('skipped')" title="Skip"><CdxIcon :icon="cdxIconNext" /></button>
              <button class="rq-bbtn rq-bbtn-remove" @click="handleBulkRemove" title="Remove"><CdxIcon :icon="cdxIconTrash" /></button>
            </div>
          </div>
        </transition>

        <div class="rq-sidebar-scroll" v-show="!sidebarCollapsed">
          <div class="rq-group">
            <button class="rq-group-header" @click="showNewArticles = !showNewArticles">
              <div class="rq-group-header-left">
                <span class="rq-dot rq-dot-pending"></span>
                <span class="rq-group-title">Pending Review</span>
                <span class="rq-group-count">{{ newArticles.length }}</span>
              </div>
              <CdxIcon :icon="showNewArticles ? cdxIconUpTriangle : cdxIconDownTriangle" class="rq-group-chevron" />
            </button>
            
            <transition name="rq-slide">
              <ul v-show="showNewArticles" class="rq-list">
                <li
                  v-for="a in newArticles"
                  :key="a.article_id"
                  class="rq-list-item rq-item-pending"
                  :class="{ 'is-active': currentArticle?.article_id === a.article_id, 'is-locked': a.locked_by && a.locked_by !== myUsername }"
                  @click="selectArticle(a)"
                >
                  <label class="rq-cb-wrapper" @click.stop>
                    <input type="checkbox" :checked="selectedForBulk.includes(a.article_id)" @change="toggleBulkSelection(a.article_id, $event)" class="rq-cb" />
                  </label>
                  <div class="rq-item-content">
                    <span class="rq-item-title">{{ a.title }}</span>
                    <span class="rq-item-meta">{{ a.submitted_by }}</span>
                  </div>
                  <CdxIcon v-if="a.locked_by && a.locked_by !== myUsername" :icon="cdxIconLock" class="rq-icon-lock" title="Being reviewed by someone" />
                </li>
                <li v-if="!newArticles.length" class="rq-list-empty">
                  <CdxIcon :icon="cdxIconArticleCheck" class="rq-empty-icon" />
                  <span>All caught up!</span>
                </li>
              </ul>
            </transition>
          </div>

          <div class="rq-group" v-if="otherReviewedArticles.length">
            <button class="rq-group-header" @click="showOtherReviewed = !showOtherReviewed">
              <div class="rq-group-header-left">
                <span class="rq-dot rq-dot-other"></span>
                <span class="rq-group-title">Other Judges</span>
                <span class="rq-group-count">{{ otherReviewedArticles.length }}</span>
              </div>
              <CdxIcon :icon="showOtherReviewed ? cdxIconUpTriangle : cdxIconDownTriangle" class="rq-group-chevron" />
            </button>
            <transition name="rq-slide">
              <ul v-show="showOtherReviewed" class="rq-list">
                <li
                  v-for="a in otherReviewedArticles"
                  :key="`other-${a.article_id}`"
                  class="rq-list-item rq-item-readonly"
                >
                  <div class="rq-item-content">
                    <span class="rq-item-title">{{ a.title }}</span>
                    <span class="rq-item-meta">{{ a.reviews.map(r => r.reviewer).join(', ') }}</span>
                  </div>
                </li>
              </ul>
            </transition>
          </div>

          <div class="rq-group">
            <button class="rq-group-header" @click="showJudgedArticles = !showJudgedArticles">
              <div class="rq-group-header-left">
                <span class="rq-dot rq-dot-judged"></span>
                <span class="rq-group-title">My Judged</span>
                <span class="rq-group-count">{{ judgedArticles.length }}</span>
              </div>
              <CdxIcon :icon="showJudgedArticles ? cdxIconUpTriangle : cdxIconDownTriangle" class="rq-group-chevron" />
            </button>
            
            <transition name="rq-slide">
              <ul v-show="showJudgedArticles" class="rq-list">
                <li
                  v-for="a in judgedArticles"
                  :key="a.article_id"
                  class="rq-list-item"
                  :class="['rq-item-' + getMyLatestDecision(a), { 'is-active': currentArticle?.article_id === a.article_id }]"
                  @click="selectArticle(a)"
                >
                  <div class="rq-item-content">
                    <span class="rq-item-title">{{ a.title }}</span>
                    <span class="rq-item-meta">{{ a.submitted_by }}</span>
                  </div>
                </li>
                <li v-if="!judgedArticles.length" class="rq-list-empty">
                  <span>Nothing judged yet</span>
                </li>
              </ul>
            </transition>
          </div>
        </div>
      </aside>

      <main class="rq-main-content">
        <div v-if="!currentArticle" class="rq-center-state rq-center-full">
          <div class="rq-card-done">
            <div class="rq-done-icon">
              <CdxIcon :icon="cdxIconArticleCheck" />
            </div>
            <h3>Queue is Clear</h3>
            <p>You have reviewed all available articles in your queue.</p>
          </div>
        </div>

        <template v-else>
          <header class="rq-article-header">
            <button class="rq-back-btn" @click="mobileTab = 'list'">
              <CdxIcon :icon="cdxIconArrowPrevious" /> Back
            </button>
            
            <div class="rq-article-meta-area">
              <a :href="articleUrl(currentArticle.title)" target="_blank" class="rq-article-title-link" :title="currentArticle.title">
                {{ currentArticle.title }}
              </a>
              <div class="rq-tags">
                <span class="rq-tag">by {{ currentArticle.submitted_by }}</span>
                <span v-if="currentArticle.wiki_creation_date" class="rq-tag rq-tag-date">
                  {{ new Date(currentArticle.wiki_creation_date).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' }) }}
                </span>
                <span v-if="currentArticle.locked_by && currentArticle.locked_by !== myUsername" class="rq-tag rq-tag-locked">
                  <CdxIcon :icon="cdxIconLock" /> {{ currentArticle.locked_by }} reviewing
                </span>
                <span v-if="getMyLatestDecision(currentArticle)" class="rq-tag rq-tag-verdict" :class="'rq-tag-' + getMyLatestDecision(currentArticle)">
                  {{ getMyLatestDecision(currentArticle) === 'accepted' ? '✓ Accepted' : getMyLatestDecision(currentArticle) === 'rejected' ? '✕ Rejected' : '→ Skipped' }}
                </span>
              </div>
            </div>
            
            <a :href="articleUrl(currentArticle.title)" target="_blank" class="rq-btn-secondary" title="Open on Wiktionary">
              <CdxIcon :icon="cdxIconLinkExternal" /> <span class="rq-desktop-only">Wiki</span>
            </a>
          </header>

          <div class="rq-preview-container">
            <div v-if="isLoadingPreview" class="rq-center-state">
              <div class="rq-spinner rq-spinner-sm"></div>
              <span class="rq-loading-text">Loading Wikipedia preview…</span>
            </div>
            <iframe
              v-else
              class="rq-wiki-iframe"
              sandbox="allow-scripts"
              :srcdoc="previewSrcdoc"
              referrerpolicy="no-referrer"
            ></iframe>
          </div>

          <footer class="rq-review-panel" :class="{ 'is-collapsed': reviewPanelCollapsed }">
            <div class="rq-panel-header" @click="reviewPanelCollapsed = !reviewPanelCollapsed">
              <div class="rq-panel-title">
                <span class="rq-panel-kicker">DECISION PANEL</span>
                <h3>Review this article</h3>
              </div>
              <button
                type="button"
                class="rq-icon-btn"
                :title="reviewPanelCollapsed ? 'Expand review panel' : 'Collapse review panel'"
              >
                <CdxIcon :icon="reviewPanelCollapsed ? cdxIconExpand : cdxIconCollapse" />
              </button>
            </div>
            
            <div class="rq-panel-body" v-show="!reviewPanelCollapsed">
              <div v-if="reviewError" class="rq-error-msg">{{ reviewError }}</div>
              
              <div class="rq-comment-field">
                <input
                  type="text"
                  class="rq-input"
                  v-model="comment"
                  placeholder="Leave a note (optional)…"
                />
              </div>

              <div class="rq-action-buttons">
                <button
                  class="rq-btn rq-btn-accept"
                  :disabled="isSubmitting"
                  @click="handleDecision('accepted')"
                >
                  <CdxIcon :icon="cdxIconCheck" />
                  <span>Accept</span>
                </button>
                <button
                  class="rq-btn rq-btn-reject"
                  :disabled="isSubmitting"
                  @click="handleDecision('rejected')"
                >
                  <CdxIcon :icon="cdxIconClear" />
                  <span>Reject</span>
                </button>
                <button
                  class="rq-btn rq-btn-skip"
                  :disabled="isSubmitting"
                  @click="skipArticle"
                >
                  <CdxIcon :icon="cdxIconNext" />
                  <span>Skip</span>
                </button>
                <button
                  class="rq-btn rq-btn-remove"
                  :disabled="isSubmitting"
                  @click="handleRemove"
                >
                  <CdxIcon :icon="cdxIconTrash" />
                  <span class="rq-desktop-only">Remove</span>
                </button>
              </div>
            </div>
          </footer>
        </template>
      </main>
    </div>

    <nav class="rq-mobile-nav">
      <button
        class="rq-nav-btn"
        :class="{ 'is-active': mobileTab === 'list' }"
        @click="mobileTab = 'list'"
      >
        <CdxIcon :icon="cdxIconMenu" class="rq-nav-icon" />
        <span class="rq-nav-label">Articles</span>
        <span class="rq-nav-badge" v-if="newArticles.length">{{ newArticles.length }}</span>
      </button>
      <button
        class="rq-nav-btn"
        :class="{ 'is-active': mobileTab === 'review' }"
        @click="mobileTab = 'review'"
        :disabled="!currentArticle"
      >
        <CdxIcon :icon="cdxIconArticle" class="rq-nav-icon" />
        <span class="rq-nav-label">Review</span>
      </button>
    </nav>
  </div>
</template>

<style scoped>
:root {
  --rq-bg: #0b0f19;
  --rq-surface: #121826;
  --rq-surface-hover: #1c2438;
  --rq-border: rgba(255, 255, 255, 0.08);
  --rq-border-light: rgba(255, 255, 255, 0.12);
  --rq-text: #f8fafc;
  --rq-text-muted: #94a3b8;
  --rq-accent: #6366f1;
  --rq-accent-hover: #818cf8;
  --rq-accent-bg: rgba(99, 102, 241, 0.15);
  
  --rq-success: #10b981;
  --rq-success-dark: #059669;
  --rq-danger: #ef4444;
  --rq-danger-dark: #dc2626;
  --rq-warning: #f59e0b;
  
  --rq-font: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

* {
  box-sizing: border-box;
}

.rq-app {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--rq-bg);
  font-family: var(--rq-font);
  color: var(--rq-text);
  overflow: hidden;
  position: relative;
}

/* Scrollbars */
.rq-app *::-webkit-scrollbar { width: 6px; height: 6px; }
.rq-app *::-webkit-scrollbar-track { background: transparent; }
.rq-app *::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
.rq-app *::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

button, input { font-family: inherit; }
button { cursor: pointer; }

/* ─── Center States ─── */
.rq-center-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 40px 24px;
  gap: 16px;
  color: var(--rq-text-muted);
}
.rq-center-full { height: 100%; }
.rq-card-unauth, .rq-card-done {
  text-align: center;
  background: var(--rq-surface);
  border: 1px solid var(--rq-border);
  border-radius: 16px;
  padding: 48px;
  max-width: 400px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.3);
}
.rq-card-unauth { border-color: rgba(239, 68, 68, 0.3); }
.rq-icon-large, .rq-done-icon { font-size: 3rem; margin-bottom: 16px; }
.rq-done-icon { color: var(--rq-success); }
.rq-card-unauth h2, .rq-card-done h3 { color: var(--rq-text); margin: 0 0 8px; font-size: 1.4rem; font-weight: 600; }
.rq-card-unauth p, .rq-card-done p { color: var(--rq-text-muted); margin: 0; font-size: 0.95rem; line-height: 1.6; }

.rq-spinner {
  width: 40px; height: 40px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: var(--rq-accent);
  border-radius: 50%;
  animation: rq-spin 0.8s linear infinite;
}
.rq-spinner-sm { width: 24px; height: 24px; border-width: 2px; }
@keyframes rq-spin { to { transform: rotate(360deg); } }
.rq-loading-text { font-size: 0.95rem; font-weight: 500; }

/* ─── Main Layout ─── */
.rq-main-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ─── Sidebar ─── */
.rq-sidebar {
  width: 320px;
  flex-shrink: 0;
  background: var(--rq-surface);
  border-right: 1px solid var(--rq-border);
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 20;
}
.rq-sidebar.is-collapsed { width: 68px; }

.rq-sidebar-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--rq-border);
  background: rgba(18, 24, 38, 0.95);
  backdrop-filter: blur(8px);
  z-index: 10;
}
.rq-sidebar.is-collapsed .rq-sidebar-header { padding: 16px 12px; }

.rq-sidebar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.rq-sidebar.is-collapsed .rq-sidebar-top { justify-content: center; margin-bottom: 0; }
.rq-sidebar.is-collapsed .rq-brand-eyebrow { display: none; }

.rq-brand-eyebrow { display: flex; align-items: center; gap: 8px; }
.rq-eyebrow-text { font-size: 0.65rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--rq-text-muted); }
.rq-badge-live { font-size: 0.6rem; font-weight: 700; text-transform: uppercase; background: rgba(16, 185, 129, 0.15); color: var(--rq-success); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.2); }

.rq-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px; height: 32px;
  padding: 0;
  border: 1px solid var(--rq-border);
  border-radius: 8px;
  background: rgba(255,255,255,0.03);
  color: var(--rq-text-muted);
  transition: all 0.2s;
}
.rq-icon-btn:hover { background: rgba(255,255,255,0.08); color: var(--rq-text); }

.rq-sidebar-title-row { margin-bottom: 16px; }
.rq-sidebar-title { margin: 0; font-size: 1.2rem; font-weight: 600; color: var(--rq-text); }

.rq-stats-strip { display: flex; gap: 8px; }
.rq-stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: rgba(0,0,0,0.2);
  border: 1px solid var(--rq-border);
  border-radius: 8px;
  padding: 6px 4px;
}
.rq-stat-pending { border-color: rgba(245, 158, 11, 0.2); }
.rq-stat-ok { border-color: rgba(16, 185, 129, 0.2); }
.rq-stat-rej { border-color: rgba(239, 68, 68, 0.2); }

.rq-stat-val { font-size: 0.95rem; font-weight: 700; color: var(--rq-text); }
.rq-stat-pending .rq-stat-val { color: var(--rq-warning); }
.rq-stat-ok .rq-stat-val { color: var(--rq-success); }
.rq-stat-rej .rq-stat-val { color: var(--rq-danger); }

.rq-stat-lbl { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--rq-text-muted); margin-top: 2px; }

/* Bulk Banner */
.rq-bulk-banner {
  padding: 12px 20px;
  background: rgba(99, 102, 241, 0.1);
  border-bottom: 1px solid var(--rq-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.rq-bulk-count { font-size: 0.8rem; font-weight: 600; color: var(--rq-accent); }
.rq-bulk-actions { display: flex; gap: 6px; }
.rq-bbtn {
  width: 30px; height: 30px;
  border-radius: 6px;
  border: none;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  transition: transform 0.1s, filter 0.2s;
}
.rq-bbtn:hover:not(:disabled) { filter: brightness(1.2); }
.rq-bbtn:active:not(:disabled) { transform: scale(0.95); }
.rq-bbtn:disabled { opacity: 0.5; cursor: not-allowed; }
.rq-bbtn-accept { background: var(--rq-success-dark); }
.rq-bbtn-reject { background: var(--rq-danger-dark); }
.rq-bbtn-skip { background: rgba(255,255,255,0.1); border: 1px solid var(--rq-border-light); }
.rq-bbtn-remove { background: #450a0a; border: 1px solid rgba(239,68,68,0.3); }

/* Sidebar Scroll */
.rq-sidebar-scroll {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 24px;
}
.rq-group { margin-bottom: 8px; }
.rq-group-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: transparent;
  border: none;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  position: sticky;
  top: 0;
  z-index: 5;
  background: var(--rq-surface);
}
.rq-group-header:hover { background: var(--rq-surface-hover); }
.rq-group-header-left { display: flex; align-items: center; gap: 10px; }
.rq-dot { width: 8px; height: 8px; border-radius: 50%; }
.rq-dot-pending { background: var(--rq-warning); box-shadow: 0 0 8px rgba(245, 158, 11, 0.4); }
.rq-dot-other { background: var(--rq-text-muted); }
.rq-dot-judged { background: var(--rq-success); }
.rq-group-title { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--rq-text); }
.rq-group-count { background: rgba(255,255,255,0.08); padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 600; color: var(--rq-text-muted); }
.rq-group-chevron { color: var(--rq-text-muted); font-size: 1.2rem; transition: transform 0.2s; }

.rq-list { list-style: none; padding: 0; margin: 0; }
.rq-list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.02);
  border-left: 3px solid transparent;
  cursor: pointer;
  transition: background 0.15s;
}
.rq-list-item:hover { background: rgba(255,255,255,0.02); }
.rq-list-item.is-active {
  background: var(--rq-accent-bg);
  border-left-color: var(--rq-accent);
}
.rq-item-pending { border-left-color: rgba(245, 158, 11, 0.4); }
.rq-item-accepted { border-left-color: rgba(16, 185, 129, 0.4); }
.rq-item-rejected { border-left-color: rgba(239, 68, 68, 0.4); }
.rq-item-skipped { border-left-color: rgba(148, 163, 184, 0.4); }
.rq-item-readonly { cursor: default; }

.rq-cb-wrapper { display: flex; align-items: center; }
.rq-cb { width: 16px; height: 16px; accent-color: var(--rq-accent); cursor: pointer; }

.rq-item-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.rq-item-title { font-size: 0.9rem; font-weight: 500; color: var(--rq-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rq-list-item.is-active .rq-item-title { color: var(--rq-accent-hover); font-weight: 600; }
.rq-item-meta { font-size: 0.75rem; color: var(--rq-text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rq-list-item.is-locked { opacity: 0.6; }
.rq-icon-lock { color: var(--rq-text-muted); font-size: 1.1rem; }

.rq-list-empty { padding: 24px; text-align: center; color: var(--rq-text-muted); font-size: 0.85rem; font-style: italic; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.rq-empty-icon { font-size: 1.5rem; opacity: 0.5; }

/* ─── Main Content (Review Area) ─── */
.rq-main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--rq-bg);
  position: relative;
}

.rq-article-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: var(--rq-surface);
  border-bottom: 1px solid var(--rq-border);
  gap: 16px;
  z-index: 10;
}
.rq-back-btn { display: none; }
.rq-article-meta-area { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.rq-article-title-link {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--rq-text);
  text-decoration: none;
  font-family: 'Linux Libertine', Georgia, Times, serif;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  transition: color 0.2s;
}
.rq-article-title-link:hover { color: var(--rq-accent-hover); }

.rq-tags { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.rq-tag { font-size: 0.75rem; font-weight: 500; color: var(--rq-text-muted); background: rgba(255,255,255,0.05); padding: 4px 10px; border-radius: 6px; }
.rq-tag-locked { background: rgba(245, 158, 11, 0.15); color: var(--rq-warning); display: flex; align-items: center; gap: 4px; }
.rq-tag-verdict { font-weight: 600; }
.rq-tag-accepted { background: rgba(16, 185, 129, 0.15); color: var(--rq-success); }
.rq-tag-rejected { background: rgba(239, 68, 68, 0.15); color: var(--rq-danger); }
.rq-tag-skipped { background: rgba(148, 163, 184, 0.15); color: var(--rq-text-muted); }

.rq-btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--rq-accent-hover);
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  padding: 8px 16px;
  border-radius: 8px;
  text-decoration: none;
  transition: background 0.2s;
}
.rq-btn-secondary:hover { background: rgba(99, 102, 241, 0.2); }

.rq-preview-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #000;
}
.rq-wiki-iframe { flex: 1; width: 100%; border: none; }

/* Review Panel */
.rq-review-panel {
  flex-shrink: 0;
  background: rgba(18, 24, 38, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid var(--rq-border-light);
  display: flex;
  flex-direction: column;
  box-shadow: 0 -10px 40px rgba(0,0,0,0.5);
  z-index: 20;
}
.rq-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  cursor: pointer;
}
.rq-panel-title { display: flex; align-items: center; gap: 16px; }
.rq-panel-kicker { font-size: 0.65rem; font-weight: 700; color: var(--rq-text-muted); letter-spacing: 0.1em; text-transform: uppercase; border-right: 1px solid var(--rq-border); padding-right: 16px; }
.rq-panel-title h3 { margin: 0; font-size: 1rem; font-weight: 600; color: var(--rq-text); }
.rq-review-panel.is-collapsed .rq-panel-header { border-bottom: none; }

.rq-panel-body {
  padding: 0 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.rq-error-msg { color: var(--rq-danger); font-size: 0.85rem; padding: 8px; background: rgba(239,68,68,0.1); border-radius: 6px; }

.rq-comment-field { width: 100%; }
.rq-input {
  width: 100%;
  background: rgba(0,0,0,0.2);
  border: 1px solid var(--rq-border-light);
  border-radius: 8px;
  padding: 12px 16px;
  color: var(--rq-text);
  font-size: 0.95rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.rq-input:focus { outline: none; border-color: var(--rq-accent); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2); }
.rq-input::placeholder { color: rgba(255,255,255,0.3); }

.rq-action-buttons {
  display: flex;
  gap: 12px;
}
.rq-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 0.95rem;
  font-weight: 600;
  border: none;
  color: #fff;
  transition: transform 0.1s, filter 0.2s, box-shadow 0.2s;
}
.rq-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.rq-btn:active:not(:disabled) { transform: translateY(1px); }
.rq-btn:hover:not(:disabled) { filter: brightness(1.1); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }

.rq-btn-accept { background: linear-gradient(135deg, var(--rq-success), var(--rq-success-dark)); box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2); }
.rq-btn-reject { background: linear-gradient(135deg, var(--rq-danger), var(--rq-danger-dark)); box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2); }
.rq-btn-skip { background: rgba(255,255,255,0.08); border: 1px solid var(--rq-border-light); color: var(--rq-text); }
.rq-btn-remove { background: #450a0a; border: 1px solid rgba(239,68,68,0.3); flex: 0 0 auto; padding: 12px 16px; }
.rq-btn-remove:hover:not(:disabled) { background: var(--rq-danger-dark); }

/* ─── Mobile Bottom Nav ─── */
.rq-mobile-nav {
  display: none;
  background: rgba(18, 24, 38, 0.98);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-top: 1px solid var(--rq-border);
  padding-bottom: env(safe-area-inset-bottom);
}
.rq-nav-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 12px 8px;
  background: none;
  border: none;
  color: var(--rq-text-muted);
  transition: color 0.2s;
  position: relative;
}
.rq-nav-btn.is-active { color: var(--rq-accent-hover); }
.rq-nav-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.rq-nav-icon { font-size: 1.4rem; }
.rq-nav-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.rq-nav-badge { position: absolute; top: 6px; right: 25%; background: var(--rq-accent); color: #fff; font-size: 0.6rem; font-weight: 700; padding: 2px 6px; border-radius: 10px; }

/* ─── Responsive (Mobile) ─── */
@media (max-width: 768px) {
  .rq-desktop-only { display: none; }
  
  .rq-sidebar.is-collapsed { width: 100%; } /* prevent desktop collapse styling on mobile */

  .rq-main-layout {
    flex-direction: row;
    width: 200%;
    transform: translateX(0);
    transition: transform 0.35s cubic-bezier(0.2, 0.8, 0.2, 1);
  }
  .rq-main-layout.is-mobile-review {
    transform: translateX(-50%);
  }

  .rq-sidebar { width: 50%; border-right: none; }
  .rq-main-content { width: 50%; }

  .rq-mobile-nav { display: flex; }
  .rq-app { padding-bottom: 0; } /* We place the nav inside the flex column instead */
  
  /* Layout tweaks for mobile */
  .rq-sidebar-header { padding: 12px 16px; }
  .rq-sidebar-top { margin-bottom: 8px; }
  .rq-collapse-btn { display: none; } /* Hide sidebar toggle on mobile */
  .rq-sidebar-title { font-size: 1.1rem; }
  .rq-stats-strip { overflow-x: auto; padding-bottom: 4px; }
  .rq-stat { flex: 0 0 auto; min-width: 70px; }

  .rq-list-item { padding: 12px 16px; }

  .rq-article-header { padding: 12px 16px; gap: 12px; }
  .rq-back-btn { 
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(255,255,255,0.08);
    border: 1px solid var(--rq-border-light);
    color: var(--rq-text);
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
  }
  .rq-article-title-link { font-size: 1.1rem; }
  .rq-tags { gap: 6px; }

  /* Make sure Review bar leaves room for Bottom Nav */
  .rq-main-content { padding-bottom: 0; } 
  .rq-main-layout { margin-bottom: 0; height: calc(100% - 65px); flex: none; }
  .rq-app { padding-bottom: 65px; } /* fixed space for mobile nav */
  .rq-mobile-nav { position: fixed; bottom: 0; left: 0; right: 0; height: 65px; z-index: 50; }

  .rq-review-panel { padding: 12px 16px; gap: 12px; }
  .rq-panel-header { padding: 8px 0; }
  .rq-panel-body { padding: 0 0 12px; }
  .rq-btn { padding: 10px; font-size: 0.9rem; }
}

/* Animations */
.rq-slide-enter-active, .rq-slide-leave-active { transition: all 0.3s ease; }
.rq-slide-enter-from, .rq-slide-leave-to { opacity: 0; transform: translateY(-10px); }
.rq-fade-enter-active, .rq-fade-leave-active { transition: opacity 0.2s; }
.rq-fade-enter-from, .rq-fade-leave-to { opacity: 0; }
</style>
