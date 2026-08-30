<script setup>
import { ref, onMounted, provide, computed } from 'vue';
import { CdxButton } from '@wikimedia/codex';
import { useRoute } from 'vue-router';
import GlobalLoader from './components/ui/GlobalLoader.vue';

const user = ref(null);
const route = useRoute();
const isReviewPage = computed(() => route.path.endsWith('/jury/review') || route.path.endsWith('/jury/review-v2'));
const isLoading = ref(true);
const isOverloaded = ref(false);
const showCookieBanner = ref(false);
const loginError = ref('');

onMounted(async () => {
  const params = new URLSearchParams(window.location.search);
  if (params.get('error') === 'login_failed') {
    loginError.value = 'Login failed. Please try again — make sure you authorise the app on Wikimedia.';
    const url = new URL(window.location.href);
    url.searchParams.delete('error');
    window.history.replaceState({}, '', url.toString());
  }

  try {
    const res = await fetch('/api/me');
    if (res.ok) user.value = await res.json();
  } catch { user.value = null; }
  finally { isLoading.value = false; }
  if (user.value) {
    const consent = localStorage.getItem('cookie_consent');
    if (!consent) showCookieBanner.value = true;
  }

  setInterval(async () => {
    try {
      const res = await fetch('/api/system/status');
      if (res.ok) {
        const data = await res.json();
        isOverloaded.value = data.overloaded;
      }
    } catch {}
  }, 5000);
});
provide('user', user);

const handleLogin = () => { window.location.href = `/auth/login?next=${encodeURIComponent(window.location.pathname)}`; };
const handleLogout = async () => {
  await fetch('/auth/logout', { method: 'POST' });
  window.location.href = '/';
};

const acceptCookies = () => {
  localStorage.setItem('cookie_consent', 'accepted');
  showCookieBanner.value = false;
};
const declineCookies = () => {
  localStorage.setItem('cookie_consent', 'declined');
  showCookieBanner.value = false;
};
</script>

<template>
  <GlobalLoader v-if="isLoading" fullscreen label="Loading Feather…" />

  <div v-else-if="!user" class="login-state">
    <div class="login-card">
      <div class="login-card-topline">
        <span class="login-context">bn.wiktionary</span>
        <span class="login-context-dot"></span>
        <span class="login-context">contest workspace</span>
      </div>
      <div class="login-logo" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z"/><line x1="16" y1="8" x2="2" y2="22"/><line x1="17.5" y1="15" x2="9" y2="15"/></svg>
      </div>
      <h1>Feather</h1>
      <p class="login-intro">Sign in with your Wikimedia account to participate in writing contests, submit articles, and track your contributions.</p>
      <div v-if="loginError" class="login-error" role="alert">{{ loginError }}</div>
      <cdx-button class="login-button" action="progressive" weight="primary" @click="handleLogin">
        Log in with Wikimedia
      </cdx-button>
      <p class="login-note">You’ll be redirected to Wikimedia to authorise Feather securely.</p>
    </div>
  </div>

  <div v-else class="app-layout">
    <div v-if="isOverloaded" class="overload-banner">
      ⚠️ System is overloaded. Please do not submit articles right now. Backing up data and restarting...
    </div>
    <header v-if="!isReviewPage" class="app-header">
      <div class="header-inner">
        <div class="header-left">
          <router-link to="/" class="home-link">
            <div class="brand-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z"/><line x1="16" y1="8" x2="2" y2="22"/><line x1="17.5" y1="15" x2="9" y2="15"/></svg>
            </div>
            <div class="brand-text">
              <span class="brand-name">Feather</span>
            </div>
          </router-link>
          <nav class="header-nav">
            <router-link to="/" class="nav-item">Home</router-link>
          </nav>
        </div>
        <div class="header-right">
          <router-link :to="'/user/' + user.wiki_username" class="user-pill-link">
            <div class="user-pill">
              <div class="user-avatar">{{ user.wiki_username[0].toUpperCase() }}</div>
              <div class="user-info">
                <span class="username">{{ user.wiki_username }}</span>
                <span class="role-badge" :class="user.role">{{ user.role }}</span>
              </div>
            </div>
          </router-link>
          <button class="logout-btn" @click="handleLogout">
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            Sign out
          </button>
        </div>
      </div>
    </header>

    <main class="app-main">
      <router-view />
    </main>

        <transition name="cookie-slide">
      <div v-if="showCookieBanner" class="cookie-banner" role="alertdialog" aria-label="Cookie consent">
        <div class="cookie-banner-inner">
          <div class="cookie-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>
          </div>
          <div class="cookie-text">
            <strong>Stay signed in</strong>
            <span>We use a session cookie to keep you logged in across visits. Accept to avoid signing in every time.</span>
          </div>
          <div class="cookie-actions">
            <button class="cookie-btn cookie-btn--accept" @click="acceptCookies" id="cookie-accept-btn">Accept</button>
            <button class="cookie-btn cookie-btn--decline" @click="declineCookies" id="cookie-decline-btn">Decline</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped src="./styles/App.css"></style>

