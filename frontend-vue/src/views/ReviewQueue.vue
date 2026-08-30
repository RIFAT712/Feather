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
  cdxIconSearch,
  cdxIconNext,
  cdxIconTrash,
  cdxIconUpTriangle,
} from '@wikimedia/codex-icons';
import { formatDateDayFirst } from '../utils/datetime';
import { fetchAllContestLogPages } from '../utils/contestLog';

const props = defineProps(['contest', 'assignedQueue']);
const route = useRoute();
const user = inject('user');

const articles = ref([]);
const currentArticle = ref(null);
const comment = ref('');
const bulkComment = ref('');
const isLoading = ref(true);
const isSubmitting = ref(false);
const isLoadingPreview = ref(false);
const reviewError = ref('');
const mobileTab = ref('list');
const sidebarCollapsed = ref(false);
const reviewPanelCollapsed = ref(false);

const showNewArticles = ref(true);
const showJudgedArticles = ref(false);
const judgedSearch = ref("");
const showOtherReviewed = ref(false);
const theme = ref(localStorage.getItem('review_queue_theme') || 'light');
const ownerViewMode = ref('judge');
// Defaults to the owner's own queue, not just whichever jury happens to be
// first in the contest's jury list -- an owner opening /review-v2 should
// land on their own assigned articles, not silently start reviewing (and
// attributing decisions to) another jury member's queue by default.
const selectedJudge = ref(user?.value?.wiki_username || props.contest?.juries?.[0] || '');

const toggleTheme = () => {
  theme.value = theme.value === 'dark' ? 'light' : 'dark';
  localStorage.setItem('review_queue_theme', theme.value);
};

const ownerVisibleArticles = (items) => {
  if (!props.assignedQueue || !roles.value.is_owner || ownerViewMode.value === 'owner') return items;
  return items.filter(article => article.assigned_to === selectedJudge.value);
};

const roles = ref({ is_jury: false, is_owner: false });
const isAuthorized = computed(() => roles.value.is_jury || roles.value.is_owner);

const selectedForBulk = ref([]);
const sidebarVisibleCounts = ref({ pending: 100, other: 100, judged: 100 });
const assignedAfterId = ref(null);
const assignedHasMore = ref(false);
const assignedStatusStats = ref(null);
const permanentlyLockedArticleIds = new Set();
let articleFetchController = null;
let roleLoaded = false;
let assignedRefillPromise = null;

const WIKI_BASE = 'https://bn.wiktionary.org/wiki/';
const DARK_CSS = `
  :root { color-scheme: dark; }
  html, body {
    background: oklch(0.1 0.01 264) !important;
    color: oklch(0.96 0.02 264) !important;
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
  table { border-collapse: collapse; background: oklch(0.15 0.01 264) !important; color: oklch(0.96 0.02 264) !important; }
  th, td { border: 1px solid oklch(0.4 0.02 264) !important; padding: 6px 10px; color: oklch(0.96 0.02 264) !important; }
  th { background: oklch(0.2 0.01 264) !important; }
  tr:nth-child(even) td { background: oklch(0.18 0.01 264) !important; }

  /* wikitable */
  .wikitable { background: oklch(0.15 0.01 264) !important; border: 1px solid oklch(0.4 0.02 264) !important; }
  .wikitable > * > tr > th { background: oklch(0.2 0.01 264) !important; color: oklch(0.96 0.02 264) !important; }
  .wikitable > * > tr > td { background: transparent !important; }

  /* NavFrame */
  .NavFrame {
    border: 1px solid oklch(0.4 0.02 264) !important;
    border-radius: 6px;
    background: oklch(0.2 0.01 264) !important;
    margin: 12px 0;
    overflow: hidden;
  }
  .NavHead {
    background: oklch(0.25 0.02 264) !important;
    color: oklch(0.96 0.02 264) !important;
    padding: 6px 10px !important;
    cursor: pointer !important;
    font-weight: 600;
    user-select: none;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 1px solid oklch(0.4 0.02 264);
  }
  .NavHead:hover { background: oklch(0.3 0.02 264) !important; }
  .NavToggle { color: oklch(0.96 0.02 264) !important; font-size: 0.85em; }
  .NavContent { background: oklch(0.15 0.01 264) !important; }
  .NavContent td, .NavContent th { border-color: oklch(0.3 0.02 264) !important; }

  /* vsToggle */
  .vsToggleElement[style*='background'] { background: oklch(0.25 0.02 264) !important; color: oklch(0.96 0.02 264) !important; }
  th[class~='vsToggleElement'] { background: oklch(0.25 0.02 264) !important; color: oklch(0.96 0.02 264) !important; cursor: pointer !important; }

  /* mw-collapsible */
  .mw-collapsible-toggle { cursor: pointer; color: oklch(0.76 0.02 264) !important; }
  .mw-collapsed .mw-collapsible-content { display: none !important; }

  /* headings */
  h1, h2, h3, h4, h5 {
    color: oklch(0.96 0.02 264) !important;
    border-bottom: 1px solid oklch(0.4 0.02 264) !important;
    padding-bottom: 4px;
  }
  h2 { font-size: 1.4em; margin-top: 1.4em; }
  h3 { font-size: 1.15em; margin-top: 1em; }
  h4 { font-size: 1em; border-bottom: none !important; }

  /* TOC */
  #toc, .toc { background: oklch(0.2 0.01 264) !important; border: 1px solid oklch(0.4 0.02 264) !important; border-radius: 6px; padding: 12px 18px; }
  .toctitle { color: oklch(0.96 0.02 264) !important; }

  /* hide edit links */
  .mw-editsection, .mw-editsection-bracket { display: none !important; }

  /* infobox */
  .infobox { background: oklch(0.2 0.01 264) !important; border: 1px solid oklch(0.4 0.02 264) !important; }
  .infobox th { background: oklch(0.25 0.02 264) !important; }

  /* references */
  .reflist, ol.references { color: #94a3b8 !important; font-size: 0.85em; }

  /* categories */
  .catlinks { background: oklch(0.2 0.01 264) !important; border: 1px solid oklch(0.4 0.02 264) !important; color: oklch(0.76 0.02 264) !important; margin-top: 24px; padding: 8px 14px; border-radius: 6px; }

  /* hatnote/notices */
  .hatnote, .dablink { background: #1d3550 !important; border-left: 3px solid #4f9cf7 !important; padding: 6px 12px; color: #9eb6cc !important; }

  /* ib-header / inflection tables with inline styles */
  [style*='background:#'], [style*='background: #'], [style*='background:rgb'], [style*='background: rgb'] {
    background: rgba(80,80,120,0.25) !important;
    color: oklch(0.96 0.02 264) !important;
  }
  /* keep text-align / font-weight from inline styles but neutralise colour */
  [style*='color:rgb'], [style*='color: rgb'] { color: oklch(0.96 0.02 264) !important; }
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

const LIGHT_CSS = `
  :root { color-scheme: light; }
  html, body {
    background: #f5f8fb !important;
    color: #20364d !important;
    font-family: 'Linux Libertine', Georgia, Times, serif;
    font-size: 15px;
    line-height: 1.6;
    margin: 0;
    padding: 20px 24px 64px;
    max-width: 860px;
  }
  a { color: #1769aa !important; }
  a:visited { color: #7253a8 !important; }
  a.new, a.new:visited { color: #b42332 !important; }
  a:hover { text-decoration: underline; }
  * { background-color: unset !important; }
  table, .wikitable { border-collapse: collapse; background: #ffffff !important; color: #20364d !important; }
  th, td { border: 1px solid #c7d6e3 !important; padding: 6px 10px; color: #20364d !important; }
  th { background: #e7f0f7 !important; }
  tr:nth-child(even) td { background: #f4f8fb !important; }
  .NavFrame { border: 1px solid #c7d6e3 !important; border-radius: 6px; background: #ffffff !important; margin: 12px 0; overflow: hidden; }
  .NavHead { background: #e7f0f7 !important; color: #20364d !important; padding: 6px 10px !important; cursor: pointer !important; font-weight: 600; }
  .NavContent { background: #ffffff !important; }
  .vsToggleElement[style*='background'], th[class~='vsToggleElement'] { background: #e7f0f7 !important; color: #20364d !important; }
  .mw-collapsible-toggle { cursor: pointer; color: #47637c !important; }
  h1, h2, h3, h4, h5 { color: #20364d !important; border-bottom: 1px solid #c7d6e3 !important; padding-bottom: 4px; }
  #toc, .toc, .infobox { background: #ffffff !important; border: 1px solid #c7d6e3 !important; border-radius: 6px; }
  .mw-editsection, .mw-editsection-bracket { display: none !important; }
`;

const previewSrcdoc = ref('');
let previewRequestId = 0;

const fetchPreview = async (title) => {
  const requestId = ++previewRequestId;
  isLoadingPreview.value = true;
  previewSrcdoc.value = '';
  try {
    const res = await fetch(`https://bn.wiktionary.org/w/api.php?action=parse&page=${encodeURIComponent(title)}&format=json&prop=text&origin=*`);
    const data = await res.json();
    const body = data.parse?.text?.['*'] ?? '<p style="color:#94a3b8">Preview not available.</p>';
    if (requestId !== previewRequestId) return;
    previewSrcdoc.value = `<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="utf-8">
<base href="https://bn.wiktionary.org/wiki/">
<style>${theme.value === 'light' ? LIGHT_CSS : DARK_CSS}</style>
</head>
<body class="mw-body mw-parser-output">
${body}
<script>${COLLAPSIBLE_JS}<\/script>
</body>
</html>`;
  } catch (e) {
    console.error(e);
    const errorTheme = theme.value === 'light'
      ? 'color:#20364d;background:#f5f8fb'
      : 'color:oklch(0.96 0.02 264);background:oklch(0.1 0.01 264)';
    if (requestId === previewRequestId) previewSrcdoc.value = `<!DOCTYPE html><html><body style="${errorTheme};padding:24px">Error loading preview.</body></html>`;
  } finally {
    if (requestId === previewRequestId) isLoadingPreview.value = false;
  }
};

watch(theme, () => {
  if (currentArticle.value?.title) fetchPreview(currentArticle.value.title);
});

const fetchArticles = async (showLoading = true, append = false) => {
  if (showLoading) isLoading.value = true;
  articleFetchController?.abort();
  articleFetchController = new AbortController();
  const { signal } = articleFetchController;
  try {
    if (!roleLoaded) {
      const roleRes = await fetch(`/api/contests/${route.params.code}/my-role`, { signal });
      if (roleRes.ok) roles.value = await roleRes.json();
      roleLoaded = true;
    }

    if (!isAuthorized.value) {
      isLoading.value = false;
      return;
    }

    if (props.assignedQueue) {
      const ownerQuery = roles.value.is_owner && ownerViewMode.value === 'judge' && selectedJudge.value
        ? `&view_as=${encodeURIComponent(selectedJudge.value)}` : '';
      let cursor = append && assignedAfterId.value !== null ? assignedAfterId.value : null;
      let combinedArticles = append ? [...articles.value] : [];
      let shouldFetchMore = true;

      // Load the complete assigned queue across bounded keyset pages. This
      // keeps the queue stable across reloads and makes the manual next-page
      // button unnecessary for normal use.
      while (shouldFetchMore) {
        const cursorQuery = cursor === null ? '' : `&after_id=${cursor}`;
        const articleEndpoint = `/api/jury-panel/contests/${route.params.code}/articles/page?page_size=250${cursorQuery}${ownerQuery}`;
        const response = await fetch(articleEndpoint, { signal });
        if (!response.ok) throw new Error(`Queue fetch failed (${response.status})`);
        const payload = await response.json();
        const pageItems = ownerVisibleArticles(payload.items || []);
        const existingIds = new Set(combinedArticles.map(article => article.article_id));
        combinedArticles = [...combinedArticles, ...pageItems.filter(article => !existingIds.has(article.article_id))];
        articles.value = combinedArticles;
        assignedAfterId.value = payload.next_after_id ?? cursor;
        assignedHasMore.value = Boolean(payload.has_more);
        assignedStatusStats.value = payload.status_counts
          ? { total: payload.total, ...payload.status_counts }
          : assignedStatusStats.value;
        cursor = payload.next_after_id ?? null;
        shouldFetchMore = Boolean(payload.has_more) && Boolean(payload.items?.length) && cursor !== null;
      }
    } else {
      // The legacy fallback queue needs every article (for New/My Judged/Other
      // Judges grouping), fetched in bounded pages instead of one giant request.
      // The most recent page (likely to hold the still-pending articles) unblocks
      // the UI immediately; older pages keep streaming in behind it.
      let firstPage = true;
      await fetchAllContestLogPages(route.params.code, {
        signal,
        onPage: (items) => {
          articles.value = ownerVisibleArticles(items);
          if (firstPage) {
            firstPage = false;
            if (showLoading) isLoading.value = false;
          }
        },
      });
    }
  } catch (error) {
    if (error.name === 'AbortError') return;
    console.error("Failed to fetch articles", error);
  } finally {
    if (!signal.aborted) isLoading.value = false;
  }
};

watch([ownerViewMode, selectedJudge], () => {
  if (props.assignedQueue && roles.value.is_owner) fetchArticles(false);
});

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
  total: assignedStatusStats.value?.total ?? articles.value.length,
  accepted: assignedStatusStats.value?.accepted ?? articles.value.filter(a => a.status === 'accepted').length,
  rejected: assignedStatusStats.value?.rejected ?? articles.value.filter(a => a.status === 'rejected').length,
  pending: assignedStatusStats.value?.pending ?? articles.value.filter(a => a.status === 'pending').length,
}));
const hasMoreAssignedArticles = computed(() => props.assignedQueue && assignedHasMore.value);

const releaseArticleLock = (articleId) => {
  if (!articleId || permanentlyLockedArticleIds.has(articleId)) return;
  fetch(`/api/articles/${articleId}/lock`, { method: 'DELETE' }).catch(() => {});
};

const judgedArticles = computed(() => {
  if (!myUsername.value) return [];
  return articles.value.filter(a => a.reviews.some(r => r.reviewer === myUsername.value));
});

const filteredJudgedArticles = computed(() => {
  const query = judgedSearch.value.trim().toLocaleLowerCase();
  if (!query) return judgedArticles.value;
  return judgedArticles.value.filter(article => article.title.toLocaleLowerCase().includes(query));
});

const otherReviewedArticles = computed(() => {
  if (!myUsername.value || !roles.value.is_owner) return [];
  return articles.value.filter(a =>
    a.status !== 'pending' &&
    a.reviews.length > 0 &&
    !a.reviews.some(r => r.reviewer === myUsername.value)
  );
});

const visibleSidebarArticles = (section, list) => list.slice(0, sidebarVisibleCounts.value[section] || 100);
const hasMoreSidebarArticles = (section, list) => visibleSidebarArticles(section, list).length < list.length;
const loadMoreSidebarArticles = (section, list) => {
  sidebarVisibleCounts.value = {
    ...sidebarVisibleCounts.value,
    [section]: Math.min((sidebarVisibleCounts.value[section] || 100) + 100, list.length),
  };
};

const loadMoreAssignedArticles = () => {
  if (assignedHasMore.value && !isLoading.value) fetchArticles(false, true);
};

// Keep an assigned queue rolling: judged articles remain available in the
// history sections while one replacement is appended from the server.
const refillAssignedQueue = async (count = 1) => {
  if (!props.assignedQueue || !assignedHasMore.value || assignedAfterId.value === null) return;
  if (assignedRefillPromise) return assignedRefillPromise;
  assignedRefillPromise = (async () => {
    try {
      for (let i = 0; i < count && assignedHasMore.value; i += 1) {
        const ownerQuery = roles.value.is_owner && ownerViewMode.value === 'judge' && selectedJudge.value
          ? `&view_as=${encodeURIComponent(selectedJudge.value)}` : '';
        const response = await fetch(`/api/jury-panel/contests/${route.params.code}/articles/page?page_size=1&after_id=${assignedAfterId.value}${ownerQuery}`);
        if (!response.ok) throw new Error(`Queue refill failed (${response.status})`);
        const payload = await response.json();
        const pageItems = ownerVisibleArticles(payload.items || []);
        assignedAfterId.value = payload.next_after_id ?? assignedAfterId.value;
        assignedHasMore.value = Boolean(payload.has_more) && pageItems.length > 0;
        if (payload.status_counts) assignedStatusStats.value = { total: payload.total, ...payload.status_counts };
        const existingIds = new Set(articles.value.map(article => article.article_id));
        articles.value = [...articles.value, ...pageItems.filter(article => !existingIds.has(article.article_id))];
        if (!payload.items?.length) break;
      }
    } catch (error) { console.warn('Background queue refill failed', error); }
    finally { assignedRefillPromise = null; }
  })();
  return assignedRefillPromise;
};
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
let lastQueueSignature = null;

// For the legacy (non-assignedQueue) queue, a full refresh means re-fetching
// every article in bounded pages. Polling that unconditionally every 5s was the
// dominant cost on large contests, so only do it when a cheap counts endpoint
// reports something actually changed (new submission, new/updated review).
const pollLegacyQueue = async () => {
  try {
    const res = await fetch(`/api/contests/${route.params.code}/stats`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.signature !== lastQueueSignature) {
      lastQueueSignature = data.signature;
      await fetchArticles(false);
    }
  } catch (error) {
    console.error('Failed to check review queue for updates', error);
  }
};

onMounted(async () => {
  await fetchArticles();
  statsInterval = setInterval(() => {
    if (!props.assignedQueue) {
      pollLegacyQueue();
    }
  }, 5000);
  if (availableNewArticles.value.length > 0 && !currentArticle.value) {
    selectArticle(availableNewArticles.value[0]);
    if (window.innerWidth <= 768) {
      mobileTab.value = 'list';
    }
  }
});

const skipArticle = () => {
  if (!currentArticle.value) return;
  const previousArticleId = currentArticle.value.article_id;
  const list = availableNewArticles.value;
  
  if (list.length <= 1) return;
  
  const currentIndex = list.findIndex(a => a.article_id === previousArticleId);
  const nextIndex = (currentIndex + 1) % list.length;
  
  releaseArticleLock(previousArticleId);
  selectArticle(list[nextIndex]);
};

watch(mobileTab, (tab) => {
  if (tab === 'list') releaseArticleLock(currentArticle.value?.article_id);
});

onBeforeUnmount(() => {
  articleFetchController?.abort();
  clearInterval(statsInterval);
  releaseArticleLock(currentArticle.value?.article_id);
});

const handleDecision = async (decision) => {
  if (!currentArticle.value || isSubmitting.value) return;
  isSubmitting.value = true;
  reviewError.value = '';
    const reviewedArticleId = currentArticle.value.article_id;
    const reviewedArticle = currentArticle.value;
    const reviewComment = comment.value;
    const previousQueueIndex = availableNewArticles.value.findIndex(
      article => article.article_id === reviewedArticleId,
    );
  try {
    const res = await fetch(`/api/articles/${reviewedArticleId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, comment: reviewComment }),
    });
    if (!res.ok) {
      const errorBody = await res.json().catch(() => ({}));
      throw new Error(errorBody.detail || `Review failed (${res.status})`);
    }
    if (decision === 'accepted' || decision === 'rejected') permanentlyLockedArticleIds.add(reviewedArticleId);
    rememberDecision(reviewedArticle, decision, reviewComment);
    comment.value = '';

    // Update the local queue immediately so reviewing feels instantaneous.
    const optimisticReview = {
      reviewer: myUsername.value,
      decision,
      comment: reviewComment,
      reviewed_at: new Date().toISOString(),
    };
    articles.value = articles.value.map(article => article.article_id === reviewedArticleId
      ? { ...article, status: decision, reviews: [...(article.reviews || []), optimisticReview] }
      : article);
    const remainingArticles = availableNewArticles.value;
    const nextArticle = remainingArticles.length
      ? remainingArticles[Math.min(Math.max(previousQueueIndex, 0), remainingArticles.length - 1)]
      : null;
    if (nextArticle) {
      selectArticle(nextArticle);
    } else {
      currentArticle.value = null;
      mobileTab.value = 'list';
    }

    // Append the next keyset item instead of replacing the first page.
    if (props.assignedQueue) {
      refillAssignedQueue();
    } else {
      fetchArticles(false).catch(error => console.warn('Background queue refresh failed', error));
    }
  } catch (error) {
    console.error("Error submitting review", error);
    reviewError.value = error.message || 'Review failed';
  } finally {
    isSubmitting.value = false;
  }
};

// ── Undo ───────────────────────────────────────────────────────────────────
// Set after every successful decision so the toast (and the U key) can take
// it back. Cleared on a timer, on undo, and whenever a new decision replaces
// it -- only ever the single most recent decision, which is what "undo" means
// here; anything older is edited by re-opening the article as before.
const lastDecision = ref(null);
const isUndoing = ref(false);
let undoExpiryTimer;

const UNDO_WINDOW_MS = 12000;

const rememberDecision = (article, decision, commentText) => {
  clearTimeout(undoExpiryTimer);
  lastDecision.value = {
    articleId: article.article_id,
    title: article.title,
    decision,
    comment: commentText,
  };
  undoExpiryTimer = setTimeout(() => { lastDecision.value = null; }, UNDO_WINDOW_MS);
};

const dismissUndo = () => {
  clearTimeout(undoExpiryTimer);
  lastDecision.value = null;
};

const undoLastDecision = async () => {
  const pending = lastDecision.value;
  if (!pending || isUndoing.value) return;
  isUndoing.value = true;
  reviewError.value = '';
  try {
    const res = await fetch(`/api/articles/${pending.articleId}/review/undo`, { method: 'POST' });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Undo failed (${res.status})`);
    }
    const result = await res.json();
    permanentlyLockedArticleIds.delete(pending.articleId);
    // Put the article back the way it was locally so the queue doesn't have to
    // round-trip before the user can act on it again.
    articles.value = articles.value.map(article => article.article_id === pending.articleId
      ? {
          ...article,
          status: result.restored_status,
          reviews: (article.reviews || []).filter(r => r.reviewer !== myUsername.value),
        }
      : article);
    dismissUndo();
    const restored = articles.value.find(a => a.article_id === pending.articleId);
    if (restored) {
      selectArticle(restored);
      comment.value = pending.comment || '';
    }
    fetchArticles(false).catch(error => console.warn('Background queue refresh failed', error));
  } catch (error) {
    reviewError.value = error.message || 'Undo failed';
  } finally {
    isUndoing.value = false;
  }
};

// ── Keyboard shortcuts ─────────────────────────────────────────────────────
// The review queue is the highest-volume screen in the app (thousands of
// articles, a handful of juries) and was entirely mouse-driven.
const showShortcutHelp = ref(false);

const isTypingTarget = (target) => {
  if (!target) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
};

const handleShortcut = (event) => {
  if (event.ctrlKey || event.metaKey || event.altKey) return;

  // Escape always works, including from the comment box -- it's the way out.
  if (event.key === 'Escape') {
    if (showShortcutHelp.value) {
      showShortcutHelp.value = false;
      event.preventDefault();
    } else if (isTypingTarget(event.target)) {
      event.target.blur();
    }
    return;
  }

  // Never steal keys from the comment textarea or any search/filter input.
  if (isTypingTarget(event.target)) return;

  if (event.key === '?') {
    showShortcutHelp.value = !showShortcutHelp.value;
    event.preventDefault();
    return;
  }
  if (showShortcutHelp.value) return;
  if (!currentArticle.value || isSubmitting.value) return;

  switch (event.key.toLowerCase()) {
    case 'a':
      event.preventDefault();
      handleDecision('accepted');
      break;
    case 'r':
      event.preventDefault();
      handleDecision('rejected');
      break;
    case 's':
      event.preventDefault();
      skipArticle();
      break;
    case 'c':
      event.preventDefault();
      commentBox.value?.focus();
      break;
    case 'u':
      event.preventDefault();
      undoLastDecision();
      break;
    default:
      break;
  }
};

const commentBox = ref(null);

onMounted(() => window.addEventListener('keydown', handleShortcut));
onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleShortcut);
  clearTimeout(undoExpiryTimer);
});

const handleRemoveArticle = async (article) => {
  if (!article || isSubmitting.value) return;
  if (!confirm(`Remove "${article.title}" from this contest?`)) return;
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
    await fetchArticles(false);
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
  if (selectedForBulk.value.length < 2) bulkComment.value = '';
};

const handleBulkDecision = async (decision) => {
  if (isSubmitting.value || !selectedForBulk.value.length) return;
  isSubmitting.value = true;
  const errors = [];
  const selectedIds = [...selectedForBulk.value];
  const currentWasSelected = selectedIds.includes(currentArticle.value?.article_id);
  const reviewComment = bulkComment.value.trim() || 'Bulk reviewed';
  try {
    const res = await fetch('/api/articles/bulk-review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ article_ids: selectedIds, decision, comment: reviewComment }),
    });
    const result = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(result.detail || 'Bulk review failed');
    for (const article_id of result.succeeded || []) {
      if (decision === 'accepted' || decision === 'rejected') permanentlyLockedArticleIds.add(article_id);
    }
    errors.push(...(result.failed || []).map(item => item.article_id));
    selectedForBulk.value = [];
    bulkComment.value = '';
    const currentWasSuccessfullyReviewed = currentWasSelected && !errors.includes(currentArticle.value?.article_id);
    if (currentWasSuccessfullyReviewed) {
      currentArticle.value = null;
      previewRequestId++;
      previewSrcdoc.value = '';
      isLoadingPreview.value = false;
    }
    await fetchArticles(false);
    if (currentWasSuccessfullyReviewed || !currentArticle.value || !availableNewArticles.value.find(a => a.article_id === currentArticle.value.article_id)) {
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
  if (!confirm(`Remove ${selectedForBulk.value.length} article(s) from the contest?`)) return;
  isSubmitting.value = true;
  try {
    const selectedIds = [...selectedForBulk.value];
    const res = await fetch('/api/articles/bulk-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ article_ids: selectedIds }),
    });
    const result = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(result.detail || 'Bulk remove failed');
    selectedForBulk.value = [];
    bulkComment.value = '';
    currentArticle.value = null;
    // Reconcile silently; bulk deletion must not replace the workspace with
    // the full-screen initial loading state.
    await fetchArticles(false);
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
  <div class="rq-app" :class="`rq-theme-${theme}`">
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

    <div v-else class="rq-layout" :class="{ 'is-mobile-review': mobileTab === 'review' }">
      
      <!-- LEFT COLUMN: QUEUE -->
      <aside class="rq-panel rq-queue-panel" :class="{ 'mobile-hidden': mobileTab !== 'list', 'is-collapsed': sidebarCollapsed }">
        <header class="rq-panel-header">
          <div class="rq-panel-header-top">
            <div class="rq-brand-eyebrow">
              <span class="rq-eyebrow-text">Jury Workspace</span>
              <span class="rq-badge-live">Live</span>
            </div>
            <div class="rq-header-actions">
              <button class="rq-theme-btn" type="button" @click="toggleTheme" :aria-label="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'">
                <span aria-hidden="true">{{ theme === 'dark' ? '☀' : '◐' }}</span>
                {{ theme === 'dark' ? 'Light' : 'Dark' }}
              </button>
              <button class="rq-icon-btn rq-desktop-only" @click="sidebarCollapsed = true" title="Collapse Sidebar">
                <CdxIcon :icon="cdxIconCollapse" />
              </button>
            </div>
          </div>
          <h2 class="rq-panel-title">Review Queue</h2>
          <div v-if="props.assignedQueue && roles.is_owner" class="rq-owner-switcher">
            <span class="rq-owner-switcher-label">View as</span>
            <div class="rq-owner-mode-buttons">
              <button type="button" :class="{ 'is-active': ownerViewMode === 'judge' }" @click="ownerViewMode = 'judge'">Judge</button>
              <button type="button" :class="{ 'is-active': ownerViewMode === 'owner' }" @click="ownerViewMode = 'owner'">Owner</button>
            </div>
            <select v-if="ownerViewMode === 'judge'" v-model="selectedJudge" class="rq-owner-judge-select" aria-label="Choose jury member">
              <option v-for="jury in (props.contest?.juries || [])" :key="jury" :value="jury">{{ jury }}</option>
            </select>
          </div>
          
          <div class="rq-stats-strip">
            <div class="rq-stat"><span class="rq-stat-val">{{ statusStats.total }}</span><span class="rq-stat-lbl">Total</span></div>
            <div class="rq-stat rq-stat-pending"><span class="rq-stat-val">{{ statusStats.pending }}</span><span class="rq-stat-lbl">Pending</span></div>
            <div class="rq-stat rq-stat-ok"><span class="rq-stat-val">{{ statusStats.accepted }}</span><span class="rq-stat-lbl">OK</span></div>
            <div class="rq-stat rq-stat-rej"><span class="rq-stat-val">{{ statusStats.rejected }}</span><span class="rq-stat-lbl">Rej</span></div>
          </div>
        </header>

        <transition name="rq-fade">
          <div v-if="selectedForBulk.length > 0" class="rq-bulk-banner">
            <span class="rq-bulk-count">{{ selectedForBulk.length }} selected</span>
            <div class="rq-bulk-actions">
              <button type="button" class="rq-bbtn rq-bbtn-accept" @click.prevent="handleBulkDecision('accepted')" title="Accept"><CdxIcon :icon="cdxIconCheck" /></button>
              <button type="button" class="rq-bbtn rq-bbtn-reject" @click.prevent="handleBulkDecision('rejected')" title="Reject"><CdxIcon :icon="cdxIconClear" /></button>
              <button type="button" class="rq-bbtn rq-bbtn-remove" @click.prevent="handleBulkRemove" title="Remove"><CdxIcon :icon="cdxIconTrash" /></button>
            </div>
          </div>
        </transition>
        <div v-if="selectedForBulk.length > 1" class="rq-bulk-comment-panel">
          <div class="rq-bulk-comment-heading">
            <span>Bulk review comment</span>
            <span class="rq-bulk-comment-hint">Added to all {{ selectedForBulk.length }} selected articles</span>
          </div>
          <textarea
            v-model="bulkComment"
            class="rq-input rq-bulk-comment-input"
            rows="2"
            placeholder="Add comment"
          ></textarea>
        </div>

        <div class="rq-panel-scroll">
          <div class="rq-group">
            <button class="rq-group-header" @click="showNewArticles = !showNewArticles">
              <div class="rq-group-header-left">
                <span class="rq-dot rq-dot-pending"></span>
                <span class="rq-group-title">Pending Review</span>
              </div>
              <CdxIcon :icon="cdxIconDownTriangle" class="rq-group-chevron" :class="{ 'is-open': showNewArticles }" />
            </button>
            
            <div v-if="showNewArticles" class="rq-group-content is-open">
              <div class="rq-group-inner">
                <ul class="rq-list">
                  <li
                    v-for="a in visibleSidebarArticles('pending', newArticles)"
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
                  <li v-if="hasMoreSidebarArticles('pending', newArticles)" class="rq-load-more-wrap">
                    <button type="button" class="rq-load-more" @click="loadMoreSidebarArticles('pending', newArticles)">Show 100 more</button>
                  </li>
                  <li v-if="!hasMoreSidebarArticles('pending', newArticles) && hasMoreAssignedArticles" class="rq-load-more-wrap">
                    <button type="button" class="rq-load-more" @click="loadMoreAssignedArticles">Load next 250 articles from server</button>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          <div class="rq-group" v-if="otherReviewedArticles.length">
            <button class="rq-group-header" @click="showOtherReviewed = !showOtherReviewed">
              <div class="rq-group-header-left">
                <span class="rq-dot rq-dot-other"></span>
                <span class="rq-group-title">Other Judges</span>
                <span class="rq-group-count">{{ otherReviewedArticles.length }}</span>
              </div>
              <CdxIcon :icon="cdxIconDownTriangle" class="rq-group-chevron" :class="{ 'is-open': showOtherReviewed }" />
            </button>
            <div v-if="showOtherReviewed" class="rq-group-content is-open">
              <div class="rq-group-inner">
                <ul class="rq-list">
                  <li
                    v-for="a in visibleSidebarArticles('other', otherReviewedArticles)"
                    :key="`other-${a.article_id}`"
                    class="rq-list-item rq-item-readonly"
                  >
                    <div class="rq-item-content">
                      <span class="rq-item-title">{{ a.title }}</span>
                      <span class="rq-item-meta">{{ a.reviews.map(r => r.reviewer).join(', ') }}</span>
                    </div>
                  </li>
                  <li v-if="hasMoreSidebarArticles('other', otherReviewedArticles)" class="rq-load-more-wrap">
                    <button class="rq-load-more" @click="loadMoreSidebarArticles('other', otherReviewedArticles)">Load 100 more</button>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          <div class="rq-group">
            <button class="rq-group-header" @click="showJudgedArticles = !showJudgedArticles">
              <div class="rq-group-header-left">
                <span class="rq-dot rq-dot-judged"></span>
                <span class="rq-group-title">My Judged</span>
                <span class="rq-group-count">{{ judgedArticles.length }}</span>
              </div>
              <CdxIcon :icon="cdxIconDownTriangle" class="rq-group-chevron" :class="{ 'is-open': showJudgedArticles }" />
            </button>
            
            <div v-if="showJudgedArticles" class="rq-group-content is-open">
              <div class="rq-group-inner">
                <div class="rq-judged-search-wrap">
                  <CdxTextInput v-model="judgedSearch" class="rq-judged-search" placeholder="Search judged articles" aria-label="Search judged articles" :start-icon="cdxIconSearch" clearable />
                </div>
                <ul class="rq-list">
                  <li
                    v-for="a in visibleSidebarArticles('judged', filteredJudgedArticles)"
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
                  <li v-if="!filteredJudgedArticles.length" class="rq-list-empty">
                    <span>{{ judgedSearch ? "No matching judged articles" : "Nothing judged yet" }}</span>
                  </li>
                  <li v-if="hasMoreSidebarArticles('judged', filteredJudgedArticles)" class="rq-load-more-wrap">
                    <button class="rq-load-more" @click="loadMoreSidebarArticles('judged', judgedArticles)">Load 100 more</button>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- CENTER AREA (Preview + Decision) -->
      <div class="rq-review-area" :class="{ 'mobile-hidden': mobileTab !== 'review' }">
        
        <div v-if="!currentArticle" class="rq-center-state rq-center-full rq-panel">
          <div class="rq-card-done">
            <div class="rq-done-icon"><CdxIcon :icon="cdxIconArticleCheck" /></div>
            <h3>Queue is Clear</h3>
            <p>You have reviewed all available articles in your queue.</p>
            <button class="rq-btn-secondary" @click="sidebarCollapsed = false" style="margin-top: 16px;">
              <CdxIcon :icon="cdxIconMenu" /> Open Sidebar
            </button>
          </div>
        </div>

        <template v-else>
          <!-- PREVIEW (Top) -->
          <main class="rq-panel rq-preview-panel">
            <header class="rq-article-header">
              <!-- Sidebar Toggle (Desktop) -->
              <button v-if="sidebarCollapsed" class="rq-hamburger-btn rq-desktop-only" @click="sidebarCollapsed = false" title="Open Sidebar">
                <CdxIcon :icon="cdxIconMenu" />
              </button>

              <button class="rq-back-btn rq-mobile-only" @click="mobileTab = 'list'">
                <CdxIcon :icon="cdxIconArrowPrevious" />
              </button>
              
              <div class="rq-article-meta-area">
                <a :href="articleUrl(currentArticle.title)" target="_blank" class="rq-article-title-link" :title="currentArticle.title">
                  {{ currentArticle.title }}
                </a>
                <div class="rq-tags">
                  <span class="rq-tag">by {{ currentArticle.submitted_by }}</span>
                  <span v-if="currentArticle.wiki_creation_date" class="rq-tag rq-tag-date">
                    {{ formatDateDayFirst(currentArticle.wiki_creation_date) }}
                  </span>
                  <span v-if="currentArticle.locked_by && currentArticle.locked_by !== myUsername" class="rq-tag rq-tag-locked">
                    <CdxIcon :icon="cdxIconLock" /> {{ currentArticle.locked_by }} reviewing
                  </span>
                  <span v-if="getMyLatestDecision(currentArticle)" class="rq-tag rq-tag-verdict" :class="'rq-tag-' + getMyLatestDecision(currentArticle)">
                    {{ getMyLatestDecision(currentArticle) === 'accepted' ? '✓ Accepted' : getMyLatestDecision(currentArticle) === 'rejected' ? '✕ Rejected' : '→ Skipped' }}
                  </span>
                </div>
              </div>
              
              <a :href="articleUrl(currentArticle.title)" target="_blank" class="rq-btn-secondary rq-wiki-link-btn" title="Open on Wiktionary">
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
          </main>

          <!-- DECISION PANEL (Bottom) -->
          <footer class="rq-panel rq-decision-panel">
            <div class="rq-decision-body">
              <div v-if="reviewError" class="rq-error-msg">{{ reviewError }}</div>
              
              <div class="rq-decision-form">
                <textarea
                  ref="commentBox"
                  class="rq-input rq-textarea"
                  v-model="comment"
                  placeholder="Leave a note for the submitter (optional)… (C)"
                  rows="2"
                ></textarea>

                <div class="rq-actions-wrapper">
                  <div class="rq-primary-actions">
                    <button type="button" class="rq-btn rq-btn-accept" :disabled="isSubmitting" @click.prevent="handleDecision('accepted')" title="Accept (A)">
                      <CdxIcon :icon="cdxIconCheck" /> <span>Accept</span> <kbd class="rq-kbd rq-desktop-only">A</kbd>
                    </button>
                    <button type="button" class="rq-btn rq-btn-reject" :disabled="isSubmitting" @click.prevent="handleDecision('rejected')" title="Reject (R)">
                      <CdxIcon :icon="cdxIconClear" /> <span>Reject</span> <kbd class="rq-kbd rq-desktop-only">R</kbd>
                    </button>
                  </div>

                  <div class="rq-secondary-actions">
                    <button class="rq-btn-ghost rq-btn-skip" :disabled="isSubmitting" @click="skipArticle" title="Skip (S)">
                      <CdxIcon :icon="cdxIconNext" /> <span class="rq-desktop-only">Skip</span>
                    </button>
                    <button class="rq-btn-ghost rq-btn-remove" :disabled="isSubmitting" @click="handleRemove" title="Delete article">
                      <CdxIcon :icon="cdxIconTrash" /> <span class="rq-desktop-only">Delete</span>
                    </button>
                    <button
                      type="button"
                      class="rq-btn-ghost rq-btn-help rq-desktop-only"
                      title="Keyboard shortcuts (?)"
                      aria-label="Keyboard shortcuts"
                      @click="showShortcutHelp = true"
                    >?</button>
                  </div>
                </div>
              </div>
            </div>
          </footer>
        </template>
      </div>
    </div>

    <!-- Mobile Nav Tabs -->
    <nav class="rq-mobile-nav">
      <button class="rq-nav-btn" :class="{ 'is-active': mobileTab === 'list' }" @click="mobileTab = 'list'">
        <CdxIcon :icon="cdxIconMenu" class="rq-nav-icon" />
        <span class="rq-nav-label">Queue</span>
        <span class="rq-nav-badge" v-if="newArticles.length">{{ newArticles.length }}</span>
      </button>
      <button class="rq-nav-btn" :class="{ 'is-active': mobileTab === 'review' }" @click="mobileTab = 'review'" :disabled="!currentArticle">
        <CdxIcon :icon="cdxIconArticle" class="rq-nav-icon" />
        <span class="rq-nav-label">Review</span>
      </button>
    </nav>

    <!-- Undo toast: the affordance for taking back the decision just made. -->
    <div v-if="lastDecision" class="rq-undo-toast" role="status">
      <span class="rq-undo-text">
        <strong class="rq-undo-decision" :class="`rq-undo-${lastDecision.decision}`">{{ lastDecision.decision }}</strong>
        <span class="rq-undo-title">{{ lastDecision.title }}</span>
      </span>
      <button type="button" class="rq-undo-btn" :disabled="isUndoing" @click="undoLastDecision">
        {{ isUndoing ? 'Undoing…' : 'Undo' }} <kbd class="rq-kbd">U</kbd>
      </button>
      <button type="button" class="rq-undo-dismiss" aria-label="Dismiss" @click="dismissUndo">×</button>
    </div>

    <!-- Keyboard shortcut reference -->
    <div v-if="showShortcutHelp" class="rq-help-backdrop" @click="showShortcutHelp = false">
      <div class="rq-help-panel" role="dialog" aria-label="Keyboard shortcuts" @click.stop>
        <div class="rq-help-header">
          <h3>Keyboard shortcuts</h3>
          <button type="button" class="rq-help-close" aria-label="Close" @click="showShortcutHelp = false">×</button>
        </div>
        <dl class="rq-help-list">
          <div class="rq-help-row"><dt><kbd class="rq-kbd">A</kbd></dt><dd>Accept the current article</dd></div>
          <div class="rq-help-row"><dt><kbd class="rq-kbd">R</kbd></dt><dd>Reject the current article</dd></div>
          <div class="rq-help-row"><dt><kbd class="rq-kbd">S</kbd></dt><dd>Skip to the next article without deciding</dd></div>
          <div class="rq-help-row"><dt><kbd class="rq-kbd">C</kbd></dt><dd>Focus the comment box</dd></div>
          <div class="rq-help-row"><dt><kbd class="rq-kbd">U</kbd></dt><dd>Undo the last decision</dd></div>
          <div class="rq-help-row"><dt><kbd class="rq-kbd">Esc</kbd></dt><dd>Leave the comment box / close this panel</dd></div>
          <div class="rq-help-row"><dt><kbd class="rq-kbd">?</kbd></dt><dd>Show or hide this panel</dd></div>
        </dl>
        <p class="rq-help-note">Shortcuts are ignored while you're typing in a text field.</p>
      </div>
    </div>
  </div>
</template>

<style scoped src="../styles/views/ReviewQueue.css"></style>
