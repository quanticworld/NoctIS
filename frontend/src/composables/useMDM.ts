/**
 * Composable for Master Data Management operations
 * Provides reactive state and methods for MDM features
 */
import { ref, computed } from 'vue'
import type { Ref } from 'vue'

// Use relative URLs to work with Vite proxy (configured in vite.config.ts)
const API_BASE = ''

export interface MasterRecord {
  id: string
  status: 'silver' | 'golden'
  confidence_score: number
  source_count: number
  email?: string
  phone?: string
  full_name?: string
  first_name?: string
  last_name?: string
  gender?: string
  breach_names: string[]
  created_at: number
  updated_at: number
  matching_keys?: string[]
}

export interface SilverRecord {
  id: string
  source_id: string
  email?: string
  phone?: string
  full_name?: string
  first_name?: string
  last_name?: string
  breach_name: string
  source_file: string
  imported_at: number
  master_id?: string
}

export interface MasterWithSources {
  master: MasterRecord
  sources: SilverRecord[]
}

export interface MDMStats {
  silver_records: {
    total: number
    unlinked: number
  }
  master_records: {
    total: number
    golden: number
    silver: number
  }
}

export interface DeduplicationStats {
  processed: number
  new_masters: number
  merged: number
  errors: number
}

export function useMDM() {
  const masters: Ref<MasterRecord[]> = ref([])
  const currentMaster: Ref<MasterWithSources | null> = ref(null)
  const stats: Ref<MDMStats | null> = ref(null)
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  // Filters
  const statusFilter: Ref<'all' | 'silver' | 'golden'> = ref('all')
  const minConfidence = ref(0)
  const minSources = ref(1)

  const filteredMasters = computed(() => {
    let filtered = masters.value

    if (statusFilter.value !== 'all') {
      filtered = filtered.filter(m => m.status === statusFilter.value)
    }

    if (minConfidence.value > 0) {
      filtered = filtered.filter(m => m.confidence_score >= minConfidence.value)
    }

    if (minSources.value > 1) {
      filtered = filtered.filter(m => m.source_count >= minSources.value)
    }

    return filtered
  })

  async function fetchMasters(page = 1, perPage = 50) {
    loading.value = true
    error.value = null

    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage)
      })

      if (statusFilter.value !== 'all') {
        params.append('status', statusFilter.value)
      }
      if (minConfidence.value > 0) {
        params.append('min_confidence', String(minConfidence.value))
      }
      if (minSources.value > 1) {
        params.append('min_sources', String(minSources.value))
      }

      const response = await fetch(`${API_BASE}/api/v1/mdm/masters?${params}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch masters: ${response.statusText}`)
      }

      const data = await response.json()
      masters.value = data

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to fetch masters:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchMaster(masterId: string) {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/api/v1/mdm/masters/${masterId}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch master: ${response.statusText}`)
      }

      currentMaster.value = await response.json()

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to fetch master:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/api/v1/mdm/stats`)

      if (!response.ok) {
        throw new Error(`Failed to fetch stats: ${response.statusText}`)
      }

      stats.value = await response.json()

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to fetch stats:', err)
    } finally {
      loading.value = false
    }
  }

  async function runDeduplication(batchSize = 100): Promise<DeduplicationStats | null> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(
        `${API_BASE}/api/v1/mdm/deduplicate?batch_size=${batchSize}`,
        { method: 'POST' }
      )

      if (!response.ok) {
        throw new Error(`Deduplication failed: ${response.statusText}`)
      }

      return await response.json()

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Deduplication failed:', err)
      return null
    } finally {
      loading.value = false
    }
  }

  async function mergeMasters(
    masterIds: string[],
    keepMasterId?: string
  ): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/api/v1/mdm/masters/merge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          master_ids: masterIds,
          keep_master_id: keepMasterId
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Merge failed')
      }

      // Refresh masters list
      await fetchMasters()
      return true

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Merge failed:', err)
      return false
    } finally {
      loading.value = false
    }
  }

  async function promoteToGolden(
    masterId: string,
    validatedBy = 'manual'
  ): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(
        `${API_BASE}/api/v1/mdm/masters/${masterId}/promote`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            master_id: masterId,
            validated_by: validatedBy
          })
        }
      )

      if (!response.ok) {
        throw new Error('Promote failed')
      }

      // Refresh current master if loaded
      if (currentMaster.value?.master.id === masterId) {
        await fetchMaster(masterId)
      }

      return true

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Promote failed:', err)
      return false
    } finally {
      loading.value = false
    }
  }

  async function splitMaster(
    masterId: string,
    silverIds: string[]
  ): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(
        `${API_BASE}/api/v1/mdm/masters/${masterId}/split`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            master_id: masterId,
            silver_ids: silverIds
          })
        }
      )

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Split failed')
      }

      // Refresh current master
      await fetchMaster(masterId)
      return true

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Split failed:', err)
      return false
    } finally {
      loading.value = false
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    // State
    masters,
    currentMaster,
    stats,
    loading,
    error,

    // Filters
    statusFilter,
    minConfidence,
    minSources,
    filteredMasters,

    // Actions
    fetchMasters,
    fetchMaster,
    fetchStats,
    runDeduplication,
    mergeMasters,
    promoteToGolden,
    splitMaster,
    clearError
  }
}
