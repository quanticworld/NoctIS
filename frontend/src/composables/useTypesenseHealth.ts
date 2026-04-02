import { ref, onUnmounted } from 'vue'

export interface InitializationStatus {
  status: 'not_started' | 'checking' | 'initializing' | 'ready' | 'error'
  message: string
  progress: number
  initialized: boolean
}

export function useTypesenseHealth() {
  const status = ref<InitializationStatus>({
    status: 'not_started',
    message: 'Starting...',
    progress: 0,
    initialized: false
  })

  const isReady = ref(false)
  const error = ref<string | null>(null)
  let pollInterval: number | null = null

  async function checkStatus() {
    try {
      const response = await fetch('/api/v1/search/initialization-status')
      if (!response.ok) {
        throw new Error('Failed to fetch initialization status')
      }

      const data = await response.json()
      status.value = data

      // Check if initialization is complete
      if (data.status === 'ready' && data.initialized) {
        isReady.value = true
        stopPolling()
      } else if (data.status === 'error') {
        error.value = data.message || 'Initialization failed'
        stopPolling()
      }
    } catch (err) {
      console.error('Failed to check Typesense status:', err)
      error.value = err instanceof Error ? err.message : 'Unknown error'
    }
  }

  function startPolling(interval = 1000) {
    // Initial check
    checkStatus()

    // Poll every interval
    pollInterval = window.setInterval(() => {
      checkStatus()
    }, interval)
  }

  function stopPolling() {
    if (pollInterval !== null) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  onUnmounted(() => {
    stopPolling()
  })

  return {
    status,
    isReady,
    error,
    checkStatus,
    startPolling,
    stopPolling
  }
}
