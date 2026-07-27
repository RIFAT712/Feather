<script setup>
import { ref, onMounted, inject } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { CdxIcon } from '@wikimedia/codex';
import { cdxIconHome } from '@wikimedia/codex-icons';

const user = inject('user');
const route = useRoute();
const router = useRouter();
const contest = ref(null);
const isLoading = ref(true);
const error = ref(null);
const roles = ref({ is_jury: false, is_owner: false });

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
  <div v-else class="contest-layout">
    <div class="contest-header">
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

<style scoped>
.loading-wrap { padding: 32px; color: #4b5563; font-size: 0.9rem; }
.error-state { color: #ffffff; font-weight: bold; padding: 32px; }

.contest-layout {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 54px);
  overflow: hidden;
  background: #0a0a0a;
}

.contest-header {
  flex-shrink: 0;
  background: #0f0f0f;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.contest-header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 48px;
}

.contest-title-link {
  display: flex; align-items: center; gap: 8px;
  text-decoration: none; color: inherit; transition: opacity 0.15s;
}
.contest-title-link:hover { opacity: 0.7; }
.home-icon { color: #4b5563; }
.contest-title-info { display: flex; align-items: baseline; gap: 8px; }
.contest-name { font-weight: 600; font-size: 0.9rem; color: #d1d5db; }
.contest-dates-chip {
  font-size: 0.7rem; color: #4b5563;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 20px; padding: 2px 8px; font-weight: 500;
}

.contest-nav { display: flex; align-items: center; gap: 2px; }
.nav-link {
  padding: 5px 12px; border-radius: 5px;
  font-size: 0.84rem; font-weight: 500;
  color: #4b5563; text-decoration: none;
  transition: background 0.12s, color 0.12s;
}
.nav-link:hover { background: rgba(255,255,255,0.05); color: #d1d5db; }
.nav-link--active { background: rgba(255,255,255,0.07); color: #f9fafb; font-weight: 600; }

.contest-content {
  flex: 1; display: flex; flex-direction: column;
  overflow-y: auto; min-height: 0;
}
</style>
