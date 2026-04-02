/**
 * Typesense search store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface SearchResult {
  document: Record<string, any>
  highlights?: Record<string, any>
  text_match?: number
}

export interface SearchResponse {
  hits: SearchResult[]
  found: number
  out_of: number
  page: number
  search_time_ms: number
  facet_counts?: any[]
}

export interface CollectionStats {
  name: string
  num_documents: number
  created_at?: number
  num_memory_shards: number
}

export const useTypesenseStore = defineStore('typesense', () => {
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const API_PREFIX = '/api/v1'

  // State
  const searchResults = ref<SearchResponse | null>(null)
  const collectionStats = ref<CollectionStats | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Computed
  const hasResults = computed(() => searchResults.value && searchResults.value.found > 0)
  const totalDocuments = computed(() => collectionStats.value?.num_documents || 0)
  const results = computed(() => searchResults.value?.hits.map(hit => hit.document) || [])
  const totalResults = computed(() => searchResults.value?.found || 0)
  const searchTimeMs = computed(() => searchResults.value?.search_time_ms || 0)
  const searchPerformed = computed(() => searchResults.value !== null)

  // Actions
  async function search(params: {
    query: string
    search_fields?: string[]
    filter_by?: string
    per_page?: number
    page?: number
    typo_tolerance?: boolean
    prefix?: boolean
  }) {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_URL}${API_PREFIX}/search/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: params.query,
          search_fields: params.search_fields || [
            'email', 'username', 'password', 'phone',
            'first_name', 'last_name', 'full_name', 'gender',
            'address', 'city', 'country', 'zip_code',
            'company', 'job_title',
            'social_media', 'website',
            'domain', 'notes'
          ],
          filter_by: params.filter_by,
          per_page: params.per_page || 20,
          page: params.page || 1,
          typo_tolerance: params.typo_tolerance ?? true,
          prefix: params.prefix ?? true,
        }),
      })

      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`)
      }

      searchResults.value = await response.json()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      searchResults.value = null
    } finally {
      loading.value = false
    }
  }

  async function fetchCollectionStats() {
    try {
      const response = await fetch(`${API_URL}${API_PREFIX}/search/stats?collection=silver_records`)

      if (!response.ok) {
        throw new Error('Failed to fetch stats')
      }

      collectionStats.value = await response.json()
    } catch (err) {
      console.error('Failed to fetch collection stats:', err)
    }
  }

  async function initialize() {
    try {
      const response = await fetch(`${API_URL}${API_PREFIX}/search/initialize`, {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error('Failed to initialize collections')
      }

      await fetchCollectionStats()
      return await response.json()
    } catch (err) {
      console.error('Initialization error:', err)
      throw err
    }
  }

  function clearResults() {
    searchResults.value = null
    error.value = null
  }

  return {
    // State
    searchResults,
    collectionStats,
    loading,
    error,

    // Computed
    hasResults,
    totalDocuments,
    results,
    totalResults,
    searchTimeMs,
    searchPerformed,

    // Actions
    search,
    fetchCollectionStats,
    initialize,
    clearResults,
  }
})
