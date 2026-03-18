<template>
  <div class="min-h-screen bg-dark-300">
    <!-- Top Navigation Bar -->
    <nav class="bg-dark-100 border-b border-gray-700">
      <div class="max-w-7xl mx-auto px-4">
        <div class="flex items-center justify-between h-14">
          <!-- Logo -->
          <div class="flex items-center space-x-3">
            <div class="w-2 h-2 bg-red-team-500"></div>
            <h1 class="text-lg font-bold tracking-wide">
              <span class="text-red-team-500">Noct</span><span class="text-gray-100">IS</span>
            </h1>
          </div>

          <!-- Navigation Links -->
          <div class="flex space-x-1">
            <RouterLink
              to="/explorer"
              class="nav-link"
              :class="{ 'nav-link-active': $route.name === 'explorer' }"
            >
              EXPLORER
            </RouterLink>
            <RouterLink
              to="/search"
              class="nav-link"
              :class="{ 'nav-link-active': $route.name === 'search' }"
            >
              SEARCH
            </RouterLink>
            <RouterLink
              to="/import"
              class="nav-link"
              :class="{ 'nav-link-active': $route.name === 'import' }"
            >
              IMPORT
            </RouterLink>
            <RouterLink
              to="/mdm"
              class="nav-link"
              :class="{ 'nav-link-active': $route.name === 'mdm' }"
            >
              MDM
            </RouterLink>
            <RouterLink
              to="/analytics"
              class="nav-link"
              :class="{ 'nav-link-active': $route.name === 'analytics' }"
            >
              ANALYTICS
            </RouterLink>
            <RouterLink
              to="/settings"
              class="nav-link"
              :class="{ 'nav-link-active': $route.name === 'settings' }"
            >
              SETTINGS
            </RouterLink>
          </div>

          <!-- Status Indicators -->
          <div class="flex items-center space-x-4">
            <!-- Search Status -->
            <div v-if="searchStore.isSearching" class="flex items-center space-x-2 px-3 py-1 bg-red-team-500 bg-opacity-10 border border-red-team-500">
              <div class="w-1.5 h-1.5 bg-red-team-500 animate-pulse"></div>
              <span class="text-xs text-red-team-500 uppercase tracking-wider">
                SEARCHING {{ searchStore.filesScanned.toLocaleString() }} files
              </span>
            </div>

            <!-- Backend Status -->
            <div class="flex items-center space-x-2">
              <div class="w-1.5 h-1.5" :class="{ 'bg-green-500': isOnline, 'bg-gray-500': !isOnline }"></div>
              <span class="text-xs text-gray-400 uppercase tracking-wider">{{ isOnline ? 'ONLINE' : 'OFFLINE' }}</span>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useConfigStore } from '@/stores/config'
import { useSearchStore } from '@/stores/search'

const configStore = useConfigStore()
const searchStore = useSearchStore()
const isOnline = ref(false)

onMounted(async () => {
  // localStorage already loaded in main.ts before app mount

  // Load config from API (templates)
  await configStore.loadConfig()

  // Check backend status
  try {
    const response = await fetch('/health')
    isOnline.value = response.ok
  } catch {
    isOnline.value = false
  }
})
</script>

<style scoped>
.nav-link {
  @apply px-4 py-2 text-sm text-gray-400 hover:text-gray-100 hover:bg-dark-200 transition-colors uppercase tracking-wider;
}

.nav-link-active {
  @apply text-red-team-500 bg-dark-200;
}
</style>
