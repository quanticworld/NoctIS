/**
 * Composable for resuming background operations when returning to the app
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

interface ImportOperation {
  type: 'import'
  job_id: string
  status: string
  breach_name: string
  progress: {
    processed: number
    total: number
    percentage: number
  }
  created_at: string
  started_at: string | null
}

interface MeilisearchTask {
  task_uid: number
  index: string
  type: string
  status: string
  details: any
  enqueued_at: string
  started_at: string | null
}

interface OperationsStatus {
  imports: ImportOperation[]
  meilisearch_tasks: {
    processing: MeilisearchTask[]
    enqueued: MeilisearchTask[]
  }
  has_active_operations: boolean
  error?: string
}

export function useOperationsResume() {
  const router = useRouter()
  const activeOperations = ref<OperationsStatus | null>(null)
  const isChecking = ref(false)

  async function checkActiveOperations() {
    if (isChecking.value) return

    isChecking.value = true

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/operations/status`)

      if (!response.ok) {
        console.error('Failed to fetch operations status:', response.statusText)
        return
      }

      const data: OperationsStatus = await response.json()
      activeOperations.value = data

      // Log active operations for debugging
      if (data.has_active_operations) {
        console.log('📋 Active operations detected:', {
          imports: data.imports.length,
          meilisearch_processing: data.meilisearch_tasks.processing.length,
          meilisearch_enqueued: data.meilisearch_tasks.enqueued.length
        })

        // Auto-redirect to appropriate view if needed
        handleActiveOperations(data)
      }

    } catch (error) {
      console.error('Error checking active operations:', error)
    } finally {
      isChecking.value = false
    }
  }

  function handleActiveOperations(data: OperationsStatus) {
    const currentRoute = router.currentRoute.value.path

    // If there are active imports and we're not on the import page, show notification
    if (data.imports.length > 0 && !currentRoute.includes('/import')) {
      const activeImportCount = data.imports.length
      console.log(`ℹ️ ${activeImportCount} import(s) in progress. Visit Import page to monitor.`)

      // Could show a toast notification here
      // toast.info(`${activeImportCount} import(s) in progress`)
    }

    // If there are active Meilisearch tasks (deletions, etc.)
    const totalMeilisearchTasks =
      data.meilisearch_tasks.processing.length +
      data.meilisearch_tasks.enqueued.length

    if (totalMeilisearchTasks > 0) {
      console.log(`ℹ️ ${totalMeilisearchTasks} Meilisearch task(s) in progress`)

      // Find deletion tasks
      const deletionTasks = [
        ...data.meilisearch_tasks.processing,
        ...data.meilisearch_tasks.enqueued
      ].filter(task => task.type === 'documentDeletion')

      if (deletionTasks.length > 0) {
        console.log(`🗑️ ${deletionTasks.length} deletion task(s) in progress`)
        // Could refresh breach list if on MDM page
      }
    }
  }

  // Auto-check on mount
  onMounted(() => {
    checkActiveOperations()
  })

  return {
    activeOperations,
    isChecking,
    checkActiveOperations,
    hasActiveOperations: () => activeOperations.value?.has_active_operations ?? false
  }
}
