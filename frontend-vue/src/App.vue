<script setup>
import { ref, onMounted, provide } from 'vue';
import { CdxButton } from '@wikimedia/codex';

const user = ref(null);
const isLoading = ref(true);
const isOverloaded = ref(false);

onMounted(async () => {
  try {
    const res = await fetch('/api/me');
    if (res.ok) user.value = await res.json();
  } catch { user.value = null; }
  finally { isLoading.value = false; }
  
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

const handleLogin = () => { window.location.href = '/auth/login'; };
const handleLogout = async () => {
  await fetch('/auth/logout', { method: 'POST' });
  window.location.href = '/';
};
</script>

<template>
  <div v-if="isLoading" class="loading-state">
    <div class="spinner"></div>
  </div>

  <div v-else-if="!user" class="login-state">
    <div class="login-card">
      <div class="login-logo">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z"/><line x1="16" y1="8" x2="2" y2="22"/><line x1="17.5" y1="15" x2="9" y2="15"/></svg>
      </div>
      <h1>Feather</h1>
      <p>Sign in with your Wikimedia account to participate in writing contests, submit articles, and track your contributions.</p>
      <cdx-button action="progressive" weight="primary" @click="handleLogin">
        Log in with Wikimedia
      </cdx-button>
    </div>
  </div>

  <div v-else class="app-layout">
    <div v-if="isOverloaded" class="overload-banner">
      ⚠️ System is overloaded. Please do not submit articles right now. Backing up data and restarting...
    </div>
    <header class="app-header">
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
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Loading ── */
.loading-state {
  display: flex; align-items: center; justify-content: center; min-height: 100vh;
  background: #0a0a0a;
}
.spinner {
  width: 36px; height: 36px;
  border: 2px solid rgba(255,255,255,0.08);
  border-top-color: rgba(255,255,255,0.5);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Login ── */
.login-state {
  display: flex; align-items: center; justify-content: center;
  min-height: 100vh; background: #0a0a0a;
}
.login-card {
  background: #111111;
  border: 1px solid rgba(255,255,255,0.07);
  padding: 48px 40px;
  border-radius: 12px;
  text-align: center;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 24px 64px rgba(0,0,0,0.6);
}
.login-logo {
  width: 56px; height: 56px; border-radius: 12px;
  background: #1f1f1f;
  border: 1px solid rgba(255,255,255,0.08);
  display: flex; align-items: center; justify-content: center;
  color: #9ca3af; margin: 0 auto 20px;
}
.login-card h1 {
  margin: 0 0 12px; font-size: 1.6rem; font-weight: 700; color: #f9fafb;
  font-family: 'Inter', sans-serif;
}
.login-card p {
  margin-bottom: 28px; color: #6b7280; font-size: 0.9rem; line-height: 1.65;
}

/* ── App Layout ── */
.app-layout {
  flex: 1; display: flex; flex-direction: column;
  background: #0a0a0a;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* ── Header ── */
.app-header {
  flex-shrink: 0; position: sticky; top: 0; z-index: 100;
  height: 54px; box-sizing: border-box;
  background: rgba(10,10,10,0.92);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.header-inner {
  display: flex; justify-content: space-between; align-items: center;
  height: 100%; padding: 0 20px;
  max-width: 1400px; margin: 0 auto; width: 100%; box-sizing: border-box;
}

/* Brand */
.header-left { display: flex; align-items: center; gap: 20px; }
.home-link {
  text-decoration: none; display: flex; align-items: center; gap: 8px;
  transition: opacity 0.15s;
}
.home-link:hover { opacity: 0.7; }
.brand-icon {
  width: 30px; height: 30px; border-radius: 7px;
  background: #1f1f1f; border: 1px solid rgba(255,255,255,0.1);
  display: flex; align-items: center; justify-content: center;
  font-size: 0.95rem; font-weight: 700; color: #e5e7eb;
}
.brand-text { display: flex; align-items: center; gap: 5px; }
.brand-name { font-size: 0.9rem; font-weight: 600; color: #e5e7eb; }
.brand-sep { color: rgba(255,255,255,0.2); font-size: 0.9rem; }
.brand-tag { font-size: 0.8rem; font-weight: 500; color: #6b7280; }

/* Nav */
.header-nav { display: flex; align-items: center; gap: 2px; }
.nav-item {
  text-decoration: none; color: #6b7280;
  font-size: 0.85rem; font-weight: 500;
  padding: 5px 11px; border-radius: 6px;
  transition: color 0.12s, background 0.12s;
}
.nav-item:hover { color: #d1d5db; background: rgba(255,255,255,0.05); }
.nav-item.router-link-active { color: #f9fafb; background: rgba(255,255,255,0.06); }

/* Right side */
.header-right { display: flex; align-items: center; gap: 8px; }
.user-pill-link { text-decoration: none; }
.user-pill {
  display: flex; align-items: center; gap: 8px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 24px; padding: 4px 12px 4px 4px;
  transition: background 0.15s, border-color 0.15s;
}
.user-pill:hover { background: rgba(255,255,255,0.07); border-color: rgba(255,255,255,0.12); }
.user-avatar {
  width: 28px; height: 28px; border-radius: 50%;
  background: #1f1f1f; border: 1px solid rgba(255,255,255,0.1);
  color: #9ca3af; font-size: 0.75rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.user-info { display: flex; flex-direction: column; gap: 1px; }
.username { font-size: 0.82rem; font-weight: 600; color: #e5e7eb; line-height: 1; }
.role-badge {
  font-size: 0.6rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.5px; padding: 1px 5px; border-radius: 3px;
  line-height: 1.4; width: fit-content;
}
.role-badge.owner { background: rgba(255,255,255,0.12); color: #e5e7eb; }
.role-badge.participant { background: rgba(255,255,255,0.06); color: #6b7280; }
.role-badge.jury { background: rgba(255,255,255,0.1); color: #d1d5db; }

/* Sign out */
.logout-btn {
  display: flex; align-items: center; gap: 5px;
  font-size: 0.78rem; font-weight: 500; color: #4b5563;
  background: none; border: 1px solid transparent;
  cursor: pointer; padding: 5px 10px; border-radius: 6px;
  transition: color 0.12s, background 0.12s;
  font-family: inherit;
}
.logout-btn:hover { color: #9ca3af; background: rgba(255,255,255,0.05); }

/* ── Main ── */
.app-main {
  flex: 1; width: 100%; box-sizing: border-box;
  display: flex; flex-direction: column;
}
.overload-banner {
  background: #ef4444; color: #fff; text-align: center;
  padding: 10px; font-weight: 600; font-size: 0.9rem;
  z-index: 1000; position: sticky; top: 0;
}

@media (max-width: 640px) {
  .header-inner { padding: 0 12px; gap: 8px; }
  .brand-name { display: none; }
  .user-info { display: none; }
  .user-pill { padding: 3px; border: none; background: transparent; }
  .logout-btn span, .logout-btn { padding: 4px 6px; font-size: 0.72rem; }
}
</style>
