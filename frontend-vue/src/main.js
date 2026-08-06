import { createApp } from 'vue'
import './style.css'
import '@wikimedia/codex-design-tokens/theme-wikimedia-ui.css'
import '@wikimedia/codex-design-tokens/theme-wikimedia-ui-mode-dark.css'
import '@wikimedia/codex/dist/codex.style.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(router).mount('#app')
