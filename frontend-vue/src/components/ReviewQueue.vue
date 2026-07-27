<script setup>
import { ref, onMounted } from 'vue';
import { CdxButton, CdxTextArea } from '@wikimedia/codex';

const currentArticle = ref(null);
const comment = ref('');
const isLoading = ref(true);

const fetchNextPending = async () => {
  isLoading.value = true;
  try {
    const response = await fetch('/api/articles/pending/next');
    if (response.ok) {
      currentArticle.value = await response.json();
      comment.value = '';
    } else {
      currentArticle.value = null;
    }
  } catch (error) {
    console.error("Failed to fetch next article", error);
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  fetchNextPending();
});

const handleDecision = async (decision) => {
  if (!currentArticle.value) return;
  
  try {
    await fetch(`/api/articles/${currentArticle.value.id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, comment: comment.value }),
    });
    fetchNextPending();
  } catch (error) {
    console.error("Error submitting review", error);
  }
};
</script>

<template>
  <div class="review-queue">
    <h2 class="section-title">Review Queue</h2>

    <div v-if="isLoading && !currentArticle" class="loading-state">
      <p>Loading next article...</p>
    </div>

    <div v-else-if="!currentArticle" class="empty-state">
      <p>🎉 No pending articles to review!</p>
    </div>

    <div v-else class="article-card">
      <div class="article-meta">
        <span class="label">Article</span>
        <a 
          :href="`https://bn.wiktionary.org/wiki/${encodeURIComponent(currentArticle.title)}`"
          target="_blank"
          class="title-link"
        >
          {{ currentArticle.title }}
        </a>
        <div class="meta-details">
          <span>Submitted by: <strong>{{ currentArticle.submitter }}</strong></span>
          <span>Date: <strong>{{ new Date(currentArticle.creation_date).toLocaleDateString() }}</strong></span>
        </div>
      </div>

      <div class="comment-field">
        <label class="field-label">Review Comment (Optional)</label>
        <cdx-text-area
          v-model="comment"
          placeholder="Leave a note about your decision..."
          :rows="3"
        ></cdx-text-area>
      </div>

      <div class="action-buttons">
        <cdx-button action="progressive" weight="primary" @click="handleDecision('accepted')">
          Accept
        </cdx-button>
        <cdx-button action="destructive" weight="primary" @click="handleDecision('rejected')">
          Reject
        </cdx-button>
        <cdx-button action="default" weight="quiet" @click="handleDecision('skipped')">
          Skip
        </cdx-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.review-queue {
  background: white;
  padding: 24px;
  border-radius: 4px;
  border: 1px solid #a2a9b1;
}
.section-title {
  margin-top: 0;
  border-bottom: 1px solid #a2a9b1;
  padding-bottom: 8px;
  margin-bottom: 24px;
}
.loading-state, .empty-state {
  text-align: center;
  padding: 48px;
  color: #54595d;
}
.article-card {
  border: 1px solid #eaecf0;
  border-radius: 4px;
  padding: 24px;
  background-color: #f8f9fa;
}
.article-meta {
  margin-bottom: 24px;
}
.label {
  display: block;
  font-size: 0.85rem;
  color: #54595d;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}
.title-link {
  font-size: 1.5rem;
  font-family: 'Linux Libertine', Georgia, Times, serif;
  color: #ffffff;
  text-decoration: none;
}
.title-link:hover {
  text-decoration: underline;
}
.meta-details {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  font-size: 0.9rem;
  color: #202122;
}
.comment-field {
  margin-bottom: 24px;
}
.field-label {
  display: block;
  font-weight: bold;
  margin-bottom: 8px;
  color: #202122;
}
.action-buttons {
  display: flex;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid #eaecf0;
}
</style>
