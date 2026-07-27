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
const showSidebar = ref(true);
const showNewArticles = ref(true);
const showJudgedArticles = ref(false);
const isLoadingPreview = ref(false);

const roles = ref({ is_jury: false, is_owner: false });
const isAuthorized = computed(() => roles.value.is_jury || roles.value.is_owner);

const selectedForBulk = ref([]);

const WIKI_BASE = 'https://bn.wiktionary.org/wiki/';

// Dark-mode CSS injected into the preview iframe
const DARK_CSS = `
  :root { color-scheme: dark; }
  html, body {
    background: #12141f !important;
    color: #e2e8f0 !important;
    font-family: 'Linux Libertine', Georgia, Times, serif;
    font-size: 15px;
    line-height: 1.6;
    margin: 0;
    padding: 20px 32px 64px;
    max-width: 860px;
  }
  a { color: #d1d5db !important; }
  a:hover { text-decoration: underline; }

  /* --- strip ALL inline light-background colors from every element --- */
  * { background-color: unset !important; }

  /* tables */
  table { border-collapse: collapse; background: #1a1d30 !important; color: #e2e8f0 !important; }
  th, td { border: 1px solid rgba(255,255,255,0.12) !important; padding: 6px 10px; color: #e2e8f0 !important; }
  th { background: rgba(255,255,255,0.07) !important; }
  tr:nth-child(even) td { background: rgba(255,255,255,0.03) !important; }

  /* wikitable */
  .wikitable { background: #1a1d30 !important; border: 1px solid rgba(255,255,255,0.15) !important; }
  .wikitable > * > tr > th { background: rgba(255,255,255,0.1) !important; color: #e5e7eb !important; }
  .wikitable > * > tr > td { background: transparent !important; }

  /* NavFrame — Bengali conjugation/inflection boxes */
  .NavFrame {
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 6px;
    background: #1a1d30 !important;
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
  .NavContent { background: #12141f !important; }
  .NavContent td, .NavContent th { border-color: rgba(255,255,255,0.09) !important; }

  /* vsToggle — verb conjugation tables */
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
  #toc, .toc { background: #1a1d30 !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 6px; padding: 12px 18px; }
  .toc a { color: #d1d5db !important; }
  .toctitle { color: #e5e7eb !important; }

  /* hide edit links */
  .mw-editsection, .mw-editsection-bracket { display: none !important; }

  /* infobox */
  .infobox { background: #1a1d30 !important; border: 1px solid rgba(255,255,255,0.12) !important; }
  .infobox th { background: rgba(255,255,255,0.07) !important; }

  /* references */
  .reflist, ol.references { color: #94a3b8 !important; font-size: 0.85em; }
  .reflist a, .references a { color: #d1d5db !important; }

  /* categories */
  .catlinks { background: #1a1d30 !important; border: 1px solid rgba(255,255,255,0.1) !important; color: #94a3b8 !important; margin-top: 24px; padding: 8px 14px; border-radius: 6px; }
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
    // ── NavFrame ───────────────────────────────────────────────────────
    function initNavFrames() {
      document.querySelectorAll('.NavFrame').forEach(function(frame) {
        var head = frame.querySelector('.NavHead');
        var content = frame.querySelector('.NavContent');
        if (!head || !content) return;
        
        content.style.display = 'none'; // Collapsed by default
        
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

    // ── vsToggle (verb/inflection tables) ─────────────────────────────
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
        
        // Collapsed by default
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

    // ── mw-collapsible standard & tables ──────────────────────────────
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
        
        // Collapsed by default
        toggler.textContent = '▶';
        if (isTable) {
          var rows = el.querySelectorAll('tr');
          rows.forEach(function(row, idx) {
            if (idx > 0) row.style.display = 'none';
          });
        } else {
          var content = el.querySelector('.mw-collapsible-content');
          if (content) {
             content.style.display = 'none';
          } else {
             Array.from(el.children).forEach(function(child, idx) {
               if (idx > 0) child.style.display = 'none';
             });
          }
        }
        
        head.style.cursor = 'pointer';
        head.addEventListener('click', function(e) {
          e.preventDefault();
          var isCollapsed = toggler.textContent.includes('▶');
          toggler.textContent = isCollapsed ? '▼' : '▶';
          
          if (isTable) {
            var rows = el.querySelectorAll('tr');
            rows.forEach(function(row, idx) {
              if (idx > 0) row.style.display = isCollapsed ? '' : 'none';
            });
          } else {
            var content = el.querySelector('.mw-collapsible-content');
            if (content) {
               content.style.display = isCollapsed ? '' : 'none';
            } else {
               Array.from(el.children).forEach(function(child, idx) {
                 if (idx > 0) child.style.display = isCollapsed ? '' : 'none';
               });
            }
          }
        });
      });
    }

    document.addEventListener('DOMContentLoaded', function() {
      initNavFrames();
      initVsToggles();
      initMwCollapsibles();
    });
    // also run immediately in case DOM is already ready
    if (document.readyState !== 'loading') {
      initNavFrames();
      initVsToggles();
      initMwCollapsibles();
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
    previewSrcdoc.value = `<!DOCTYPE html><html><body style="color:#d1d5db;background:#12141f;padding:24px">Error loading preview.</body></html>`;
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
  return articles.value.filter(a => !a.reviews.some(r => r.reviewer === myUsername.value));
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
};

onMounted(async () => {
  await fetchArticles();
  if (availableNewArticles.value.length > 0 && !currentArticle.value) {
    const randomIdx = Math.floor(Math.random() * availableNewArticles.value.length);
    selectArticle(availableNewArticles.value[randomIdx]);
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
    await fetchArticles();
    if (availableNewArticles.value.length > 0) {
      selectArticle(availableNewArticles.value[0]);
    } else if (newArticles.value.length > 0) {
      selectArticle(newArticles.value[0]);
    } else {
      currentArticle.value = articles.value.find(a => a.article_id === currentArticle.value.article_id);
    }
  } catch (error) {
    console.error("Error submitting review", error);
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
  try {
    for (const article_id of selectedForBulk.value) {
      await fetch(`/api/articles/${article_id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, comment: 'Bulk reviewed' }),
      });
    }
    selectedForBulk.value = [];
    await fetchArticles();
    
    // Auto-select if current article was among the bulk reviewed
    if (!currentArticle.value || !availableNewArticles.value.find(a => a.article_id === currentArticle.value.article_id)) {
      if (availableNewArticles.value.length > 0) {
        const randomIdx = Math.floor(Math.random() * availableNewArticles.value.length);
        selectArticle(availableNewArticles.value[randomIdx]);
      } else {
        currentArticle.value = null;
      }
    }
  } catch (err) {
    console.error("Bulk review failed", err);
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
    <div v-if="!isLoading && !isAuthorized" class="unauthorized-banner">
      <div class="unauthorized-content">
        <span class="icon">⛔</span>
        <h2>Access Denied</h2>
        <p>You are not authorized to view this page. This area is restricted to Contest Jury and Owners.</p>
      </div>
    </div>

    <div v-else-if="isLoading" class="status-state">
      <p>⏳ Loading articles...</p>
    </div>

    <div v-else class="dashboard-layout">
      <!-- Left Sidebar: Lists -->
      <div class="sidebar" :class="{ 'is-collapsed': !showSidebar }">
        <div class="panel-header" @click="showSidebar = !showSidebar">
          <span v-if="showSidebar">Articles List</span>
          <span class="collapse-icon" title="Toggle Sidebar">{{ showSidebar ? '◀' : '▶' }}</span>
        </div>
        
        <div class="sidebar-content" v-show="showSidebar">
          <!-- Bulk Actions Panel -->
          <div v-if="selectedForBulk.length > 0" class="bulk-actions-panel">
            <div class="bulk-count">{{ selectedForBulk.length }} selected</div>
            <div class="bulk-buttons">
              <button class="bulk-btn accept" @click="handleBulkDecision('accepted')" :disabled="isSubmitting">Accept</button>
              <button class="bulk-btn reject" @click="handleBulkDecision('rejected')" :disabled="isSubmitting">Reject</button>
            </div>
          </div>

          <h3 @click="showNewArticles = !showNewArticles" class="section-toggle">
            <span class="toggle-icon">{{ showNewArticles ? '▼' : '▶' }}</span>
            New Articles ({{ newArticles.length }})
          </h3>
          <ul class="article-list" v-show="showNewArticles">
            <li v-for="a in newArticles" :key="a.article_id" 
                :class="{ active: currentArticle?.article_id === a.article_id }"
                @click="selectArticle(a)">
              <div class="li-left">
                <input type="checkbox" :checked="selectedForBulk.includes(a.article_id)" @click="toggleBulkSelection(a.article_id, $event)" class="bulk-checkbox" />
                <span>{{ a.title }}</span>
              </div>
            </li>
            <li v-if="!newArticles.length" class="empty-list">No new articles</li>
          </ul>

          <h3 @click="showJudgedArticles = !showJudgedArticles" class="section-toggle">
            <span class="toggle-icon">{{ showJudgedArticles ? '▼' : '▶' }}</span>
            My Judged Articles ({{ judgedArticles.length }})
          </h3>
          <ul class="article-list" v-show="showJudgedArticles">
            <li v-for="a in judgedArticles" :key="a.article_id" 
                :class="{ active: currentArticle?.article_id === a.article_id }"
                @click="selectArticle(a)">
              {{ a.title }}
              <span :class="['decision-badge', getMyLatestDecision(a)]">
                {{ getMyLatestDecision(a) === 'accepted' ? '✅' : getMyLatestDecision(a) === 'rejected' ? '❌' : '⏭' }}
              </span>
            </li>
            <li v-if="!judgedArticles.length" class="empty-list">You haven't judged any articles yet</li>
          </ul>
        </div>
      </div>

      <!-- Right Panel: Review Area -->
      <div class="review-area" v-if="currentArticle">
        <div v-if="currentArticle.locked_by && currentArticle.locked_by !== myUsername" class="lock-banner">
          ⚠️ <strong>{{ currentArticle.locked_by }}</strong> is probably reviewing this page right now.
        </div>
        <!-- Top: preview -->
        <div class="preview-pane">
          <div class="preview-header">
            <span>Live Preview</span>
            <a :href="articleUrl(currentArticle.title)" target="_blank" class="open-link">Open in new tab ↗</a>
          </div>
          <div class="preview-content-wrapper">
            <div v-if="isLoadingPreview" class="status-state">
              <p>⏳ Loading preview...</p>
            </div>
            <iframe
              v-else
              class="wiki-iframe"
              sandbox="allow-scripts"
              :srcdoc="previewSrcdoc"
              referrerpolicy="no-referrer"
            ></iframe>
          </div>
        </div>

        <!-- Talk Page Template Helper Card -->
        <div v-if="props.contest?.add_talk_template && talkPageSnippet" class="talk-template-card">
          <div class="talk-card-left">
            <span class="talk-card-icon">💬</span>
            <div class="talk-card-text">
              <span class="talk-card-label">Talk Page Template Code:</span>
              <code class="talk-code-inline">{{ talkPageSnippet.replace(/\n\n/g, '  |  ') }}</code>
            </div>
          </div>
          <div class="talk-card-actions">
            <button class="copy-talk-btn" @click="copyTalkSnippet" :title="talkPageSnippet">
              {{ isCopiedTalkSnippet ? '✅ Copied Code!' : '📋 Copy Talk Page Code' }}
            </button>
            <a :href="'https://bn.wiktionary.org/wiki/আলাপ:' + encodeURIComponent(currentArticle.title)" target="_blank" class="open-talk-link">
              Open Talk Page ↗
            </a>
          </div>
        </div>

        <!-- Bottom: Review Ribbon -->
        <div class="review-ribbon">
          <div class="ribbon-meta">
            <a :href="articleUrl(currentArticle.title)" target="_blank" class="article-title-link" :title="currentArticle.title">
              {{ currentArticle.title }}
            </a>
            <div class="meta-sub">
              by {{ currentArticle.submitted_by }}
              <span v-if="currentArticle.wiki_creation_date">
                • {{ new Date(currentArticle.wiki_creation_date).toLocaleDateString() }}
              </span>
            </div>
          </div>

          <div class="ribbon-comment">
            <cdx-text-input
              v-model="comment"
              placeholder="Leave a note (optional)..."
            />
          </div>

          <div class="ribbon-actions">
            <cdx-button action="progressive" weight="primary" :disabled="isSubmitting" @click="handleDecision('accepted')">
              <cdx-icon :icon="cdxIconCheck" /> Accept
            </cdx-button>
            <cdx-button action="destructive" weight="primary" :disabled="isSubmitting" @click="handleDecision('rejected')">
              <cdx-icon :icon="cdxIconClear" /> Reject
            </cdx-button>
            <cdx-button action="default" weight="quiet" :disabled="isSubmitting" @click="skipArticle">
              <cdx-icon :icon="cdxIconNext" /> Skip
            </cdx-button>
          </div>
          
          <div v-if="getMyLatestDecision(currentArticle)" class="ribbon-status">
            <span :class="['decision-badge', getMyLatestDecision(currentArticle)]">
              {{ getMyLatestDecision(currentArticle) === 'accepted' ? '✅ Accepted' : getMyLatestDecision(currentArticle) === 'rejected' ? '❌ Rejected' : '⏭ Skipped' }}
            </span>
          </div>
        </div>
      </div>
      <div v-else class="status-state empty">
        <p>🎉 You have reviewed all available articles!</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Unauthorized Banner */
.unauthorized-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  flex: 1;
}
.unauthorized-content {
  text-align: center;
  background: #1e293b;
  padding: 40px 60px;
  border-radius: 12px;
  border: 1px solid rgba(239, 68, 68, 0.3);
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  max-width: 500px;
}
.unauthorized-content .icon { font-size: 3rem; margin-bottom: 16px; display: block; }
.unauthorized-content h2 { color: #ffffff; margin: 0 0 12px 0; font-size: 1.5rem; font-weight: 700; }
.unauthorized-content p { color: #9ca3af; margin: 0; font-size: 0.95rem; line-height: 1.5; }

/* Lock Banner */
.lock-banner {
  background: rgba(255,255,255,0.1);
  color: #d1d5db;
  padding: 10px 16px;
  border-bottom: 2px solid rgba(255,255,255,0.1);
  font-size: 0.85rem;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Layout */
.review-queue { display: flex; flex-direction: column; height: 100%; min-height: 0; background: #0d0f1c; }
.status-state { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; color: #9ca3af; font-size: 1rem; padding: 64px 32px; gap: 12px; }
.status-state p { margin: 0; }
.status-state.empty::before { content: '🎉'; font-size: 2.5rem; }
.dashboard-layout { display: flex; flex: 1; height: 100%; overflow: hidden; min-height: 0; }

/* Sidebar */
.sidebar {
  width: 280px;
  background: #1e293b;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  flex-shrink: 0;
}
.sidebar.is-collapsed { width: 44px; cursor: pointer; }

.panel-header {
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #0f172a;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  font-weight: 700;
  font-size: 0.8rem;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  user-select: none;
  text-transform: uppercase;
  letter-spacing: 0.6px;
}
.panel-header:hover { background: #1e293b; color: rgba(255,255,255,0.8); }
.collapse-icon { font-size: 0.7rem; color: rgba(255,255,255,0.4); margin: 0; }

.sidebar-content { flex: 1; overflow-y: auto; }
.sidebar-content::-webkit-scrollbar { width: 4px; }
.sidebar-content::-webkit-scrollbar-track { background: transparent; }
.sidebar-content::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

/* Bulk Actions */
.bulk-actions-panel {
  padding: 12px 16px;
  background: #0f172a;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bulk-count {
  font-size: 0.75rem;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
}
.bulk-buttons {
  display: flex;
  gap: 8px;
}
.bulk-btn {
  flex: 1;
  padding: 6px 0;
  border: none;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  color: #fff;
  transition: opacity 0.15s, transform 0.1s;
}
.bulk-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.bulk-btn:active:not(:disabled) { transform: translateY(1px); }
.bulk-btn.accept { background: #2563eb; }
.bulk-btn.accept:hover:not(:disabled) { background: #1d4ed8; }
.bulk-btn.reject { background: #dc2626; }
.bulk-btn.reject:hover:not(:disabled) { background: #b91c1c; }

.sidebar h3 {
  margin: 0;
  padding: 10px 16px;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: rgba(255,255,255,0.35);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  position: sticky;
  top: 0;
  z-index: 2;
  background: #1e293b;
}
.sidebar h3.section-toggle { cursor: pointer; display: flex; align-items: center; gap: 8px; }
.sidebar h3.section-toggle:hover { color: rgba(255,255,255,0.7); }
.toggle-icon { font-size: 0.65rem; }

.article-list { list-style: none; margin: 0; padding: 4px 0; }
.article-list li {
  padding: 9px 16px;
  cursor: pointer;
  font-size: 0.82rem;
  color: rgba(255,255,255,0.65);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  transition: background 0.1s, color 0.1s;
  border-radius: 0;
  line-height: 1.4;
}
.article-list li:hover { background: rgba(255,255,255,0.07); color: #fff; }
.article-list li.active { background: #2563eb; color: #fff; font-weight: 600; }
.article-list li.empty-list { color: rgba(255,255,255,0.25); font-style: italic; cursor: default; font-size: 0.8rem; }
.article-list li.empty-list:hover { background: transparent; color: rgba(255,255,255,0.25); }
.li-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.bulk-checkbox {
  cursor: pointer;
  accent-color: #ffffff;
  width: 14px;
  height: 14px;
}

/* Review Area */
.review-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: #12141f; }

/* Preview Pane */
.preview-pane { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  background: #161829;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  font-size: 0.78rem;
  font-weight: 700;
  color: #64748b;
  flex-shrink: 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.open-link {
  font-weight: 500;
  color: #ffffff;
  text-decoration: none;
  font-size: 0.78rem;
  text-transform: none;
  letter-spacing: 0;
}
.open-link:hover { text-decoration: underline; }
.preview-content-wrapper {
  flex: 1;
  overflow: hidden;
  background: #12141f;
  display: flex;
  flex-direction: column;
}
.wiki-iframe {
  flex: 1;
  width: 100%;
  border: none;
  background: #12141f;
}


/* Review Ribbon */
.review-ribbon {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  background: #161829;
  border-top: 1px solid rgba(255,255,255,0.07);
  box-shadow: 0 -4px 16px rgba(0,0,0,0.3);
  flex-shrink: 0;
  z-index: 10;
}
.ribbon-meta {
  display: flex;
  flex-direction: column;
  min-width: 140px;
  max-width: 240px;
}
.article-title-link {
  font-weight: 700;
  font-size: 0.95rem;
  color: #e2e8f0;
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: 'Linux Libertine', Georgia, Times, serif;
}
.article-title-link:hover { color: #d1d5db; }
.meta-sub { font-size: 0.75rem; color: #9ca3af; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }
.ribbon-comment { flex: 1; }
.ribbon-actions { display: flex; gap: 8px; align-items: center; }
.ribbon-status {
  padding-left: 16px;
  border-left: 1px solid rgba(255,255,255,0.07);
  display: flex;
  align-items: center;
  font-size: 0.82rem;
  font-weight: 600;
}
.decision-badge { font-size: 0.82rem; }
/* Talk Template Helper Card */
.talk-template-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 8px;
  padding: 8px 16px;
  margin-bottom: 12px;
  gap: 12px;
}
.talk-card-left {
  display: flex;
  align-items: center;
  gap: 10px;
  overflow: hidden;
}
.talk-card-icon { font-size: 1.2rem; }
.talk-card-text { display: flex; flex-direction: column; overflow: hidden; }
.talk-card-label { font-size: 0.75rem; font-weight: 700; color: #e5e7eb; text-transform: uppercase; letter-spacing: 0.05em; }
.talk-code-inline { font-family: monospace; color: #d1d5db; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.talk-card-actions { display: flex; align-items: center; gap: 8px; shrink: 0; }
.copy-talk-btn {
  background: #2563eb;
  color: #fff;
  border: none;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.copy-talk-btn:hover { background: #1d4ed8; }
.open-talk-link {
  color: #e5e7eb;
  font-size: 0.8rem;
  text-decoration: none;
  font-weight: 500;
}
.open-talk-link:hover { text-decoration: underline; color: #e5e7eb; }
</style>
