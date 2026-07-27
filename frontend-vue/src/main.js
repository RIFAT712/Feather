import { createApp } from 'vue'
import './style.css'
import '@wikimedia/codex-design-tokens/theme-wikimedia-ui.css'
import '@wikimedia/codex/dist/codex.style.css'
import App from './App.vue'
import router from './router'

createApp(App).use(router).mount('#app')
