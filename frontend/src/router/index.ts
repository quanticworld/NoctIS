import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/explorer',
    },
    {
      path: '/explorer',
      name: 'explorer',
      component: () => import('@/views/DataExplorerView.vue'),
      meta: { title: 'Data Explorer', icon: '🗂️' },
    },
    {
      path: '/search',
      name: 'search',
      component: () => import('@/views/TypesenseSearchView.vue'),
      meta: { title: 'Search', icon: '🔍' },
    },
    {
      path: '/import',
      name: 'import',
      component: () => import('@/views/ImportView.vue'),
      meta: { title: 'Import', icon: '📥' },
    },
    {
      path: '/analytics',
      name: 'analytics',
      component: () => import('@/views/AnalyticsView.vue'),
      meta: { title: 'Analytics', icon: '📊' },
    },
    {
      path: '/mdm',
      name: 'mdm',
      component: () => import('@/views/MDMView.vue'),
      meta: { title: 'MDM', icon: '🎯' },
    },
    {
      path: '/scrapers',
      name: 'scrapers',
      component: () => import('@/views/ScrapersView.vue'),
      meta: { title: 'Scrapers', icon: '🕷️' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { title: 'Settings', icon: '⚙️' },
    },
  ],
})

export default router
