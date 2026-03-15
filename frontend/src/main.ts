import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'
import { useConfigStore } from '@/stores/config'

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)
app.use(router)

// Load saved settings from localStorage before mounting
const configStore = useConfigStore()
configStore.loadFromLocalStorage()

app.mount('#app')
