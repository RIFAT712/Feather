<script setup>
import { ref, onMounted, inject, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { CdxIcon } from '@wikimedia/codex';
import { cdxIconHome, cdxIconArrowPrevious } from '@wikimedia/codex-icons';

const user = inject('user');
const route = useRoute();
const router = useRouter();
const contest = ref(null);
const isLoading = ref(true);
const error = ref(null);
const roles = ref({ is_jury: false, is_owner: false });
const isReviewPage = computed(() => route.path.endsWith('/jury/review') || route.path.endsWith('/jury/review-v2'));

onMounted(async () => {
  try {
    const res = await fetch(`/api/contests/${route.params.code}`);
    if (!res.ok) throw new Error("Contest not found");
    contest.value = await res.json();
    const rolesRes = await fetch(`/api/contests/${route.params.code}/my-role`);
    if (rolesRes.ok) roles.value = await rolesRes.json();
  } catch (err) {
    error.value = err.message;
  } finally {
    isLoading.value = false;
  }
});
</script>

<template>
  <div v-if="isLoading" class="loading-wrap">Loading contest...</div>
  <div v-else-if="error" class="error-state">{{ error }}</div>
  <div v-else class="contest-layout" :class="{ 'review-layout': isReviewPage }">
    <!-- Back button shown only on /jury/review, replaces both nav bars -->
    <div v-if="isReviewPage" class="review-topbar">
      <router-link :to="`/${contest.code}/jury`" class="back-btn">
        <cdx-icon :icon="cdxIconArrowPrevious" class="back-icon" />
        <span>Back to Jury</span>
      </router-link>
      <span class="review-topbar-title">{{ contest.name }}</span>
    </div>

    <!-- Full contest header shown on all other pages -->
    <div v-else class="contest-header">
      <div class="contest-header-inner">
        <router-link :to="`/${contest.code}`" class="contest-title-link">
          <cdx-icon :icon="cdxIconHome" class="home-icon" />
          <div class="contest-title-info">
            <span class="contest-name">{{ contest.name }}</span>
            <span class="contest-dates-chip">
              {{ new Date(contest.start_date).toLocaleDateString() }} – {{ new Date(contest.end_date).toLocaleDateString() }}
            </span>
          </div>
        </router-link>

        <nav class="contest-nav" v-if="!isLoading">
          <router-link :to="`/${contest.code}`" class="nav-link" exact-active-class="nav-link--active">Dashboard</router-link>
          <router-link :to="`/${contest.code}/submit`" class="nav-link" active-class="nav-link--active">Submit</router-link>
          <router-link :to="`/${contest.code}/result`" class="nav-link" active-class="nav-link--active">Results</router-link>
          <router-link v-if="roles.is_jury || roles.is_owner" :to="`/${contest.code}/jury`" class="nav-link" active-class="nav-link--active">Jury</router-link>
        </nav>
      </div>
    </div>

    <div class="contest-content">
      <router-view :contest="contest" />
    </div>
  </div>
</template>

<style scoped src="../styles/views/ContestLayout.css"></style>
