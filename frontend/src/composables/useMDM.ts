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
  birth_date?: string
  city?: string
  country?: string
  company?: string
  passwords?: string[]
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
  password?: string
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

export interface Breach {
  name: string
  count: number
}

export interface DeduplicationStats {
  processed: number
  new_masters: number
  merged: number
  errors: number
  has_more?: boolean
}

export function useMDM() {
  const masters: Ref<MasterRecord[]> = ref([])
  const currentMaster: Ref<MasterWithSources | null> = ref(null)
  const stats: Ref<MDMStats | null> = ref(null)
  const breaches: Ref<Breach[]> = ref([])
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  // Filters
  const statusFilter: Ref<'all' | 'silver' | 'golden'> = ref('all')
  const minConfidence = ref(0)
  const minSources = ref(1)
  const selectedBreaches: Ref<string[]> = ref([])

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
      if (selectedBreaches.value.length > 0) {
        params.append('breaches', selectedBreaches.value.join(','))
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

  async function fetchBreaches() {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/api/v1/mdm/breaches`)

      if (!response.ok) {
        throw new Error(`Failed to fetch breaches: ${response.statusText}`)
      }

      breaches.value = await response.json()

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to fetch breaches:', err)
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

  async function demoteFromGolden(masterId: string): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(
        `${API_BASE}/api/v1/mdm/masters/${masterId}/demote`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        }
      )

      if (!response.ok) {
        throw new Error('Demote failed')
      }

      // Refresh current master if loaded
      if (currentMaster.value?.master.id === masterId) {
        await fetchMaster(masterId)
      }

      return true

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Demote failed:', err)
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

  async function deleteBreach(breachName: string): Promise<any> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/api/v1/mdm/breaches/${encodeURIComponent(breachName)}`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        throw new Error('Failed to delete breach')
      }

      const result = await response.json()
      console.log('Delete breach result:', result)

      // Refresh stats and breaches
      await Promise.all([fetchStats(), fetchBreaches()])

      return result

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Delete breach failed:', err)
      return null
    } finally {
      loading.value = false
    }
  }

  async function clearAllData(): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/api/v1/mdm/clear-all`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        throw new Error('Failed to clear data')
      }

      const result = await response.json()
      console.log('Clear result:', result)

      // Refresh stats
      await fetchStats()

      return true

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Clear all failed:', err)
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
    breaches,
    loading,
    error,

    // Filters
    statusFilter,
    minConfidence,
    minSources,
    selectedBreaches,
    filteredMasters,

    // Actions
    fetchMasters,
    fetchMaster,
    fetchStats,
    fetchBreaches,
    runDeduplication,
    mergeMasters,
    promoteToGolden,
    demoteFromGolden,
    splitMaster,
    deleteBreach,
    clearAllData,
    clearError
  }
}
