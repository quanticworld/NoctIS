/**
 * Composable for managing data conflicts
 */
import { ref } from 'vue'
import type { Ref } from 'vue'

const API_BASE = ''

export interface Conflict {
  id: string
  master_id: string
  silver_id: string
  field_name: string
  status: 'pending' | 'resolved' | 'ignored'
  existing_value: string
  new_value: string
  existing_source: string
  new_source: string
  resolved_value?: string
  resolved_by?: string
  resolved_at?: number
  created_at: number
}

export function useConflicts() {
  const conflicts: Ref<Conflict[]> = ref([])
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  async function fetchConflicts(
    masterId?: string,
    status: 'pending' | 'resolved' | 'ignored' = 'pending'
  ) {
    loading.value = true
    error.value = null

    try {
      const params = new URLSearchParams({ status })
      if (masterId) {
        params.append('master_id', masterId)
      }

      const response = await fetch(`${API_BASE}/api/v1/mdm/conflicts?${params}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch conflicts: ${response.statusText}`)
      }

      conflicts.value = await response.json()

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to fetch conflicts:', err)
    } finally {
      loading.value = false
    }
  }

  async function resolveConflict(
    conflictId: string,
    chosenValue: string,
    resolvedBy = 'manual'
  ): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/api/v1/mdm/conflicts/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conflict_id: conflictId,
          chosen_value: chosenValue,
          resolved_by: resolvedBy
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Resolution failed')
      }

      // Remove resolved conflict from list
      conflicts.value = conflicts.value.filter(c => c.id !== conflictId)
      return true

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to resolve conflict:', err)
      return false
    } finally {
      loading.value = false
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    conflicts,
    loading,
    error,
    fetchConflicts,
    resolveConflict,
    clearError
  }
}
