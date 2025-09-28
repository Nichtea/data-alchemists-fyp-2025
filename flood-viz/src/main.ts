import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import 'leaflet/dist/leaflet.css'
import './assets/main.css'


createApp(App).use(createPinia()).use(router).mount('#app')

