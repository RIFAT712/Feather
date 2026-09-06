<script setup>
import { ref, computed, inject, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { CdxTable, CdxIcon } from '@wikimedia/codex';
import { cdxIconAlert } from '@wikimedia/codex-icons';
import { postBulkInChunks } from '../utils/bulkReview';
import GlobalLoader from '../components/ui/GlobalLoader.vue';

// Owner-only screen: the entries on the owner's own jury queue that are
// missing a required section heading, so they can be declined in one sweep
// instead of one at a time in the review workspace.
const props = defineProps({
  roles: { type: Object, default: () => ({ is_jury: false, is_owner: false }) },
});
const route = useRoute();
const user = inject('user');

const columns = [
  { id: 'title', label: 'Article', minWidth: '240px' },
  { id: 'submitter', label: 'Submitter', minWidth: '160px' },
  { id: 'missing', label: 'Missing sections', minWidth: '200px' },
];

const items = ref([]);
const checked = ref(0);
const unread = ref(0);
const isLoading = ref(true);
const isScanning = ref(false);
const total = ref(0);
const error = ref('');
const isSubmitting = ref(false);
const notice = ref('');
const comment = ref('');
// No sorting on this table, so CdxTable reports selection as row indexes.
const selectedRows = ref([]);
const selectedIds = computed(() => selectedRows.value.map(i => items.value[i]?.article_id).filter(Boolean));

// Walks the whole assigned queue page by page rather than asking for it in one
// request: each page costs page_size/50 MediaWiki content reads, so results are
// rendered as they arrive instead of after a minute of blank screen.
let runId = 0;
const load = async () => {
  const run = ++runId;
  isScanning.value = true;
  isLoading.value = true;
  error.value = '';
  notice.value = '';
  selectedRows.value = [];
  items.value = [];
  checked.value = 0;
  unread.value = 0;
  total.value = 0;
  let afterId = null;
  try {
    for (;;) {
      const url = `/api/jury-panel/contests/${route.params.code}/admin-special`
        + (afterId === null ? '' : `?after_id=${afterId}`);
      const res = await fetch(url);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
      if (run !== runId) return;              // a newer scan started; drop this one
      items.value = items.value.concat(data.items || []);
      checked.value += data.checked || 0;
      unread.value += data.unread || 0;
      if (data.total !== null && data.total !== undefined) total.value = data.total;
      isLoading.value = false;                // first page is on screen; keep filling
      if (!data.has_more || !data.next_after_id) break;
      afterId = data.next_after_id;
    }
  } catch (err) {
    if (run === runId) error.value = err.message || 'Could not load the list.';
  } finally {
    if (run === runId) {
      isLoading.value = false;
      isScanning.value = false;
    }
  }
};

const declineSelected = async () => {
  if (isSubmitting.value || !selectedIds.value.length) return;
  isSubmitting.value = true;
  notice.value = '';
  const { succeeded, failed } = await postBulkInChunks('/api/articles/bulk-review', selectedIds.value, {
    decision: 'rejected',
    comment: comment.value.trim() || 'নিবন্ধে ===ব্যুৎপত্তি=== ও ===উচ্চারণ=== অনুচ্ছেদ নেই।',
  });
  notice.value = `Declined ${succeeded.length}${failed.length ? `, ${failed.length} failed (${failed[0].detail})` : ''}.`;
  // Drop the declined rows in place. Re-running load() would re-read every
  // remaining article's wikitext from the wiki to learn what we already know.
  const gone = new Set(succeeded);
  items.value = items.value.filter(row => !gone.has(row.article_id));
  selectedRows.value = [];
  isSubmitting.value = false;
};

onMounted(() => {
  if (props.roles.is_owner) load();
  else isLoading.value = false;
});
</script>

<template>
  <div class="as-page">
    <div v-if="!props.roles.is_owner" class="as-empty">This page is for the contest owner.</div>
    <template v-else>
      <header class="as-header">
        <div>
          <h2 class="as-title">Missing sections</h2>
          <p class="as-sub">
            Pending articles assigned to {{ user?.wiki_username }} without
            <code>===ব্যুৎপত্তি===</code> or <code>===উচ্চারণ===</code>.
          </p>
        </div>
        <button type="button" class="as-btn" :disabled="isLoading || isScanning" @click="load">Refresh</button>
      </header>

      <GlobalLoader v-if="isLoading" label="Reading article wikitext…" />
      <div v-else-if="error" class="as-error"><CdxIcon :icon="cdxIconAlert" /> {{ error }}</div>
      <template v-else>
        <p class="as-meta">
          <template v-if="isScanning">Checking {{ checked.toLocaleString() }} of {{ total.toLocaleString() }} assigned articles…</template>
          <template v-else>{{ items.length.toLocaleString() }} missing a section, out of {{ checked.toLocaleString() }} checked.</template>
          <span v-if="unread"> {{ unread.toLocaleString() }} could not be read from the wiki and were skipped.</span>
        </p>
        <div v-if="notice" class="as-notice">{{ notice }}</div>

        <div v-if="items.length" class="as-actions">
          <input v-model="comment" class="as-input" placeholder="Decline comment (optional)" />
          <button type="button" class="as-btn as-btn-danger" :disabled="!selectedIds.length || isSubmitting" @click="declineSelected">
            Decline {{ selectedIds.length || '' }} selected
          </button>
        </div>

        <cdx-table
          v-if="items.length"
          caption="Assigned articles missing a required section"
          hide-caption
          use-row-selection
          v-model:selected-rows="selectedRows"
          :columns="columns"
          :data="items"
        >
          <template #item-title="{ row }">
            <a :href="`https://bn.wiktionary.org/wiki/${encodeURIComponent(row.title)}`" target="_blank" class="as-link">{{ row.title }}</a>
          </template>
          <template #item-missing="{ item }">
            <span v-for="name in item" :key="name" class="as-tag">{{ name }}</span>
          </template>
        </cdx-table>
        <div v-else-if="!isScanning" class="as-empty">Nothing missing — every assigned pending article has both sections.</div>
      </template>
    </template>
  </div>
</template>

<style scoped src="../styles/views/AdminSpecial.css"></style>
