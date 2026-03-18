<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Collection Stats -->
    <div class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Collection Statistics</h2>

      <div v-if="loading" class="text-center text-gray-400 py-8">
        Loading statistics...
      </div>

      <div v-else-if="error" class="text-red-team-500 text-sm">
        ERROR: {{ error }}
      </div>

      <div v-else-if="collectionStats" class="grid grid-cols-4 gap-4">
        <div class="stat-card">
          <div class="stat-value">{{ collectionStats.num_documents?.toLocaleString() || 0 }}</div>
          <div class="stat-label">Total Documents</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ facetStats.totalBreaches || 0 }}</div>
          <div class="stat-label">Unique Breaches</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ facetStats.totalDomains || 0 }}</div>
          <div class="stat-label">Unique Domains</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ collectionStats.num_memory_shards || 0 }}</div>
          <div class="stat-label">Memory Shards</div>
        </div>
      </div>
    </div>

    <!-- Top Breaches -->
    <div class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Top Breaches</h2>

      <div v-if="facets.breach_name && facets.breach_name.length > 0" class="space-y-2">
        <div
          v-for="breach in facets.breach_name.slice(0, 10)"
          :key="breach.value"
          class="bg-dark-200 border border-gray-700 p-3 hover:border-red-team-500 transition-colors"
        >
          <div class="flex items-center justify-between">
            <div class="text-sm text-gray-300">{{ breach.value }}</div>
            <div class="text-sm text-red-team-500 font-bold">
              {{ breach.count.toLocaleString() }} records
            </div>
          </div>
          <div class="mt-2 bg-dark-300 h-2">
            <div
              class="bg-red-team-500 h-full"
              :style="{ width: (breach.count / maxBreachCount * 100) + '%' }"
            ></div>
          </div>
        </div>
      </div>

      <div v-else class="text-center text-gray-500 py-8">
        No breach data available
      </div>
    </div>

    <!-- Top Domains -->
    <div class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Top Domains</h2>

      <div v-if="facets.domain && facets.domain.length > 0" class="grid grid-cols-2 gap-3">
        <div
          v-for="domain in facets.domain.slice(0, 20)"
          :key="domain.value"
          class="bg-dark-200 border border-gray-700 p-3 hover:border-red-team-500 transition-colors"
        >
          <div class="flex items-center justify-between">
            <div class="text-sm text-gray-300 font-mono">{{ domain.value }}</div>
            <div class="text-xs text-red-team-500 font-bold">
              {{ domain.count.toLocaleString() }}
            </div>
          </div>
        </div>
      </div>

      <div v-else class="text-center text-gray-500 py-8">
        No domain data available
      </div>
    </div>

    <!-- Breach Timeline -->
    <div v-if="facets.breach_date && facets.breach_date.length > 0" class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Breach Timeline</h2>

      <div class="space-y-2">
        <div
          v-for="date in sortedBreachDates.slice(0, 15)"
          :key="date.value"
          class="bg-dark-200 border border-gray-700 p-3"
        >
          <div class="flex items-center justify-between">
            <div class="text-sm text-gray-300">{{ formatDate(date.value) }}</div>
            <div class="text-sm text-red-team-500 font-bold">
              {{ date.count.toLocaleString() }} records
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Refresh Button -->
    <div class="flex justify-center">
      <button
        @click="loadAnalytics"
        :disabled="loading"
        class="btn-primary"
      >
        {{ loading ? 'LOADING...' : 'REFRESH STATISTICS' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

interface CollectionStats {
  name: string
  num_documents: number
  num_memory_shards: number
  created_at?: number
}

interface FacetCount {
  value: string
  count: number
}

interface Facets {
  breach_name?: FacetCount[]
  domain?: FacetCount[]
  breach_date?: FacetCount[]
}

const loading = ref(false)
const error = ref<string | null>(null)
const collectionStats = ref<CollectionStats | null>(null)
const facets = ref<Facets>({})

const facetStats = computed(() => {
  return {
    totalBreaches: facets.value.breach_name?.length || 0,
    totalDomains: facets.value.domain?.length || 0,
  }
})

const maxBreachCount = computed(() => {
  if (!facets.value.breach_name || facets.value.breach_name.length === 0) return 1
  return Math.max(...facets.value.breach_name.map(b => b.count))
})

const sortedBreachDates = computed(() => {
  if (!facets.value.breach_date) return []
  return [...facets.value.breach_date].sort((a, b) => parseInt(b.value) - parseInt(a.value))
})

async function loadAnalytics() {
  loading.value = true
  error.value = null

  try {
    // Load collection stats
    const statsResponse = await fetch('/api/v1/search/stats')
    if (!statsResponse.ok) throw new Error('Failed to load collection stats')
    collectionStats.value = await statsResponse.json()

    // Load facets
    const facetsResponse = await fetch('/api/v1/search/facets')
    if (!facetsResponse.ok) throw new Error('Failed to load facets')
    facets.value = await facetsResponse.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loading.value = false
  }
}

function formatDate(timestamp: string): string {
  const date = new Date(parseInt(timestamp) * 1000)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

onMounted(() => {
  loadAnalytics()
})
</script>
