<script setup>
import { ref, onMounted, inject, computed } from 'vue';
import { useRoute } from 'vue-router';
import { CdxButton, CdxTextInput, CdxIcon } from '@wikimedia/codex';
import { cdxIconCheck, cdxIconClear, cdxIconNext } from '@wikimedia/codex-icons';

const props = defineProps(['contest']);
const route = useRoute();
const user = inject('user');

const articles = ref([]);
const currentArticle = ref(null);
const comment = ref('');
const isLoading = ref(true);
const isSubmitting = ref(false);
const isLoadingPreview = ref(false);

// Mobile tab: 'list' | 'review'
const mobileTab = ref('list');
const sidebarCollapsed = ref(false);

const showNewArticles = ref(true);
const showJudgedArticles = ref(false);

const roles = ref({ is_jury: false, is_owner: false });
const isAuthorized = computed(() => roles.value.is_jury || roles.value.is_owner);

const selectedForBulk = ref([]);

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

const fetchArticles = async () => {
  isLoading.value = true;
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
    !(roles.value.is_jury && !roles.value.is_owner && a.submitted_by === myUsername.value) &&
    !a.reviews.some(r => r.reviewer === myUsername.value)
  );
});

const availableNewArticles = computed(() => {
  return newArticles.value.filter(a => !a.locked_by || a.locked_by === myUsername.value);
});

const judgedArticles = computed(() => {
  if (!myUsername.value) return [];
  return articles.value.filter(a => a.reviews.some(r => r.reviewer === myUsername.value));
});

const getMyLatestDecision = (article) => {
  const myReviews = article.reviews.filter(r => r.reviewer === myUsername.value);
  if (!myReviews.length) return null;
  return myReviews[myReviews.length - 1].decision;
};

const selectArticle = (article) => {
  currentArticle.value = article;
  comment.value = '';
  fetchPreview(article.title);
  fetch(`/api/articles/${article.article_id}/lock`, { method: 'POST' }).catch(() => {});
  // On mobile, auto-switch to review tab
  mobileTab.value = 'review';
};

onMounted(async () => {
  await fetchArticles();
  if (availableNewArticles.value.length > 0 && !currentArticle.value) {
    const randomIdx = Math.floor(Math.random() * availableNewArticles.value.length);
    selectArticle(availableNewArticles.value[randomIdx]);
    if (window.innerWidth <= 768) {
      mobileTab.value = 'list';
    }
  }
});

const skipArticle = () => {
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

const handleDecision = async (decision) => {
  if (!currentArticle.value || isSubmitting.value) return;
  isSubmitting.value = true;
  try {
    const res = await fetch(`/api/articles/${currentArticle.value.article_id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, comment: comment.value }),
    });
    if (!res.ok) throw new Error('Review failed');
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
  } finally {
    isSubmitting.value = false;
  }
};

const handleRemove = async () => {
  if (!currentArticle.value || isSubmitting.value) return;
  if (!confirm('Are you sure you want to permanently remove this article from the contest?')) return;
  isSubmitting.value = true;
  try {
    const res = await fetch(`/api/articles/${currentArticle.value.article_id}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Remove failed');
    currentArticle.value = null;
    await fetchArticles();
    mobileTab.value = 'list';
  } catch (error) {
    console.error("Error removing article", error);
  } finally {
    isSubmitting.value = false;
  }
};


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
          class="sidebar-toggle"
          @click="sidebarCollapsed = !sidebarCollapsed"
          :aria-label="sidebarCollapsed ? 'Expand article panel' : 'Collapse article panel'"
          :title="sidebarCollapsed ? 'Expand article panel' : 'Collapse article panel'"
        >{{ sidebarCollapsed ? '☰' : '×' }}</button>
        <!-- Stats row -->
        <div class="sidebar-stats">
          <div class="stat-pill pending">
            <span class="stat-num">{{ newArticles.length }}</span>
            <span class="stat-lbl">Pending</span>
          </div>
          <div class="stat-pill done">
            <span class="stat-num">{{ judgedArticles.length }}</span>
            <span class="stat-lbl">Judged</span>
          </div>
          <div class="stat-pill total">
            <span class="stat-num">{{ articles.length }}</span>
            <span class="stat-lbl">Total</span>
          </div>
        </div>

        <!-- Bulk Actions Banner -->
        <div v-if="selectedForBulk.length > 0" class="bulk-banner">
          <span class="bulk-label">{{ selectedForBulk.length }} selected</span>
          <div class="bulk-btns">
            <button class="bbtn accept" @click="handleBulkDecision('accepted')" title="Accept Selected">✓</button>
            <button class="bbtn reject" @click="handleBulkDecision('rejected')" title="Reject Selected">✕</button>
            <button class="bbtn skip" @click="handleBulkDecision('skipped')" title="Skip Selected">→</button>
            <button class="bbtn remove" @click="handleBulkRemove" title="Remove Selected">🗑️</button>
          </div>
        </div>

        <!-- New Articles section -->
        <div class="section-head" @click="showNewArticles = !showNewArticles">
          <span class="section-title">
            <span class="section-dot pending-dot"></span>
            Pending Review
          </span>
          <span class="section-count">{{ newArticles.length }}</span>
          <span class="section-chevron">{{ showNewArticles ? '▾' : '▸' }}</span>
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
              <span v-if="a.locked_by && a.locked_by !== myUsername" class="lock-badge" title="Being reviewed by someone">🔒</span>
            </li>
            <li v-if="!newArticles.length" class="empty-item">
              <span>🎉 All articles reviewed!</span>
            </li>
          </ul>
        </transition>

        <!-- Judged Articles section -->
        <div class="section-head" @click="showJudgedArticles = !showJudgedArticles">
          <span class="section-title">
            <span class="section-dot judged-dot"></span>
            My Judged
          </span>
          <span class="section-count">{{ judgedArticles.length }}</span>
          <span class="section-chevron">{{ showJudgedArticles ? '▾' : '▸' }}</span>
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
      </aside>

      <!-- ═══════════════ REVIEW AREA ═══════════════ -->
      <div class="review-area" :class="{ 'mobile-hidden': mobileTab !== 'review' }">
        <!-- Empty state -->
        <div v-if="!currentArticle" class="center-state full">
          <div class="done-state">
            <div class="done-icon">🎉</div>
            <h3>All Caught Up!</h3>
            <p>You have reviewed all available articles.</p>
          </div>
        </div>

        <template v-else>
          <!-- Article Header Bar -->
          <div class="article-header">
            <!-- Mobile back button -->
            <button class="back-btn mobile-only" @click="mobileTab = 'list'">
              ← Back
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
                  🔒 {{ currentArticle.locked_by }} reviewing
                </span>
                <span v-if="getMyLatestDecision(currentArticle)" class="verdict-chip" :class="getMyLatestDecision(currentArticle)">
                  {{ getMyLatestDecision(currentArticle) === 'accepted' ? '✓ Accepted' : getMyLatestDecision(currentArticle) === 'rejected' ? '✕ Rejected' : '→ Skipped' }}
                </span>
              </div>
            </div>
            <a :href="articleUrl(currentArticle.title)" target="_blank" class="open-wiki-btn" title="Open on Wiktionary">
              ↗ Wiki
            </a>
          </div>

          <!-- Talk Template Card -->
          <div v-if="false && props.contest?.add_talk_template && talkPageSnippet" class="talk-card">
            <span class="talk-icon">💬</span>
            <div class="talk-info">
              <span class="talk-label">Talk Template</span>
              <code class="talk-code">{{ talkPageSnippet.replace(/\n\n/g, '  |  ') }}</code>
            </div>
            <div class="talk-actions">
              <button class="talk-copy-btn" @click="copyTalkSnippet">
                {{ isCopiedTalkSnippet ? '✅ Copied!' : '📋 Copy' }}
              </button>
              <a :href="'https://bn.wiktionary.org/wiki/আলাপ:' + encodeURIComponent(currentArticle.title)" target="_blank" class="talk-open-btn">
                Talk ↗
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
          <div class="review-bar">
            <div class="review-bar-inner">
              <div class="review-comment">
                <cdx-text-input
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
                  <span class="action-icon">✓</span>
                  <span class="action-label">Accept</span>
                </button>
                <button
                  class="action-btn reject-btn"
                  :disabled="isSubmitting"
                  @click="handleDecision('rejected')"
                >
                  <span class="action-icon">✕</span>
                  <span class="action-label">Reject</span>
                </button>
                <button
                  class="action-btn skip-btn"
                  :disabled="isSubmitting"
                  @click="skipArticle"
                >
                  <span class="action-icon">→</span>
                  <span class="action-label">Skip</span>
                </button>
                <button
                  class="action-btn remove-btn"
                  :disabled="isSubmitting"
                  @click="handleRemove"
                >
                  <span class="action-icon">🗑️</span>
                  <span class="action-label">Remove</span>
                </button>
              </div>
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
        <span class="mob-nav-icon">☰</span>
        <span class="mob-nav-lbl">Articles <span class="mob-badge">{{ newArticles.length }}</span></span>
      </button>
      <button
        class="mob-nav-btn"
        :class="{ active: mobileTab === 'review' }"
        @click="mobileTab = 'review'"
        :disabled="!currentArticle"
      >
        <span class="mob-nav-icon">📝</span>
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
.sidebar.collapsed {
  width: 0;
  border-right: none;
  background: transparent;
}
.sidebar.collapsed > :not(.sidebar-toggle) { display: none; }
.sidebar-toggle {
  position: absolute;
  top: 12px;
  right: -12px;
  z-index: 50;
  width: 28px;
  height: 30px;
  padding: 0;
  border: 1px solid rgba(255,255,255,0.32);
  border-radius: 4px;
  background: #131520;
  color: #f8fafc;
  font-size: 1.35rem;
  line-height: 26px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.45);
}
.sidebar-toggle:hover { background: #1f2333; color: #fff; }
.sidebar.collapsed .sidebar-toggle {
  left: 0;
  right: auto;
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
.stat-pill.done { background: rgba(34, 197, 94, 0.1); }
.stat-pill.total { background: rgba(99, 102, 241, 0.1); }
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

  .main-layout {
    flex-direction: column;
    height: calc(100% - 58px);
    flex: 0 0 calc(100% - 58px);
    min-height: 0;
  }

  /* On mobile, sidebar and review area each take full space,
     and toggled by mobileTab */
  .sidebar {
    width: 100%;
    border-right: none;
    border-bottom: none;
    height: 100%;
    flex-shrink: 0;
  }
  .sidebar-toggle { right: 10px; }
  .sidebar-toggle { display: none; }

  .review-area {
    height: 100%;
    flex-shrink: 0;
    min-height: 0;
  }

  .preview-wrap {
    padding-bottom: 112px;
    box-sizing: border-box;
  }

  .review-bar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 58px;
    width: 100vw;
    z-index: 120;
  }

  .mobile-hidden {
    display: none !important;
  }

  /* Mobile bottom nav: flex displayed */
  .mobile-bottom-nav {
    display: flex;
  }

  /* Adjust review queue bottom padding for nav */
  .review-queue {
    padding-bottom: 0;
  }

  /* Review bar adapts */
  .review-bar-inner {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }
  .review-comment { min-width: 0; width: 100%; }
  .review-actions {
    width: 100%;
    min-width: 0;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
  }
  .action-btn {
    width: 100%;
    min-width: 0;
    justify-content: center;
    padding: 10px 8px;
    font-size: 0.82rem;
  }
  .action-btn .action-label { display: none; }
  .action-btn .action-icon { font-size: 1.1rem; }

  /* Article header adapts */
  .article-header {
    padding: 10px 14px;
    gap: 8px;
  }
  .article-title-link { font-size: 0.9rem; }
}

@media (max-width: 480px) {
  .unauth-card { padding: 28px 24px; }
  .sidebar-stats { gap: 6px; padding: 10px 12px; }
  .action-btn { padding: 10px 6px; }
}
</style>
