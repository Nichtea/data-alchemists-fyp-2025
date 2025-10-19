import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'home', component: () => import('@/pages/Home.vue') },
  { path: '/about', name: 'about', component: () => import('@/pages/About.vue') },
  { path: '/publictransport', name: 'publictransport', component: () => import('@/pages/PublicTransport.vue') },
  { path: '/privatetransport', name: 'privatetransport', component: () => import('@/pages/PrivateTransport.vue') },
  { path: '/flood', name: 'flood', component: () => import('@/pages/Flood.vue') },
]

export const router = createRouter({
  history: createWebHistory(),
  routes
})
