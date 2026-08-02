import { createApp } from 'vue'
import './style.css'
import '@wikimedia/codex-design-tokens/theme-wikimedia-ui.css'
import '@wikimedia/codex-design-tokens/theme-wikimedia-ui-mode-dark.css'
import '@wikimedia/codex/dist/codex.style.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)

function reportErrorToBackend(err, info = '') {
  try {
    const errorData = {
      message: String(err?.message || err || 'Unknown Error'),
      stack_trace: String(err?.stack || info || ''),
      url: window.location.href,
      user_agent: navigator.userAgent
    }
    fetch('/api/logs/client-error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(errorData),
      keepalive: true
    }).catch(() => {})
  } catch (e) {
    // Ignore reporting errors
  }
}

app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue Global Error]', err, info)
  reportErrorToBackend(err, `Vue Component Error: ${info}`)
}

window.onerror = (message, source, lineno, colno, error) => {
  console.error('[JS Error]', message, source, lineno, colno, error)
  reportErrorToBackend(error || message, `Location: ${source}:${lineno}:${colno}`)
}

window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Promise Rejection]', event.reason)
  reportErrorToBackend(event.reason, 'Unhandled Promise Rejection')
})

app.use(router).mount('#app')
