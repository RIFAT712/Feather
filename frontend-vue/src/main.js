import { createApp } from 'vue'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import './style.css'
import '@wikimedia/codex-design-tokens/theme-wikimedia-ui.css'
import '@wikimedia/codex/dist/codex.style.css'
import './styles/light-theme.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)

// Replaces the old hand-rolled sessionStorage cache (contestDataCache.js):
// this is the shared cache/refetch layer for all contest-scoped data
// (stats, activity log crawls) across Dashboard/ActivityLog/JuryStats.
// staleTime: 0 means every mount revalidates in the background (matching the
// old cache's stale-while-revalidate behavior) while still serving cached
// data instantly instead of a loading spinner.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 0,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

app.use(router).use(VueQueryPlugin, { queryClient }).mount('#app')
