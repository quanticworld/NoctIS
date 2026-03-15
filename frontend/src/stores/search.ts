import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SearchMatch, WebSocketMessage } from '@/types'

export const useSearchStore = defineStore('search', () => {
  const isSearching = ref(false)
  const matches = ref<SearchMatch[]>([])
  const filesScanned = ref(0)
  const totalFiles = ref<number | null>(null)
  const currentFile = ref('')
  const matchesFound = ref(0)
  const speed = ref(0)
  const etaSeconds = ref<number | null>(null)
  const duration = ref(0)
  const errorMessage = ref('')

  const ws = ref<WebSocket | null>(null)

  // Search form state (persists across navigation)
  const selectedTemplate = ref('name_search')
  const firstName = ref('')
  const lastName = ref('')
  const customPattern = ref('')

  const progressPercentage = computed(() => {
    if (!totalFiles.value) return 0
    return Math.round((filesScanned.value / totalFiles.value) * 100)
  })

  const formattedEta = computed(() => {
    if (!etaSeconds.value) return 'Calculating...'
    const seconds = Math.round(etaSeconds.value)
    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${minutes}m ${secs}s`
  })

  function connectWebSocket(): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/search`

      const socket = new WebSocket(wsUrl)

      socket.onopen = () => {
        ws.value = socket
        resolve(socket)
      }

      socket.onerror = (error) => {
        reject(error)
      }

      socket.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          handleMessage(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      socket.onclose = () => {
        ws.value = null
      }
    })
  }

  function handleMessage(message: WebSocketMessage) {
    switch (message.type) {
      case 'progress':
        filesScanned.value = message.files_scanned
        totalFiles.value = message.total_files ?? null
        currentFile.value = message.current_file
        matchesFound.value = message.matches_found
        speed.value = message.speed
        etaSeconds.value = message.eta_seconds ?? null
        break

      case 'result':
        matches.value.push(message.match)
        break

      case 'complete':
        isSearching.value = false
        duration.value = message.duration_seconds
        matchesFound.value = message.total_matches
        filesScanned.value = message.files_scanned
        break

      case 'error':
        isSearching.value = false
        errorMessage.value = message.message
        break
    }
  }

  async function startSearch(request: any) {
    // Reset state
    matches.value = []
    filesScanned.value = 0
    totalFiles.value = null
    currentFile.value = ''
    matchesFound.value = 0
    speed.value = 0
    etaSeconds.value = null
    duration.value = 0
    errorMessage.value = ''
    isSearching.value = true

    try {
      // Connect if not already connected
      if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
        await connectWebSocket()
      }

      // Send search request
      ws.value!.send(JSON.stringify({
        action: 'search',
        data: request,
      }))
    } catch (error) {
      isSearching.value = false
      errorMessage.value = `Failed to start search: ${error}`
      throw error
    }
  }

  function cancelSearch() {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ action: 'cancel' }))
    }
    isSearching.value = false
  }

  function clearResults() {
    matches.value = []
    filesScanned.value = 0
    totalFiles.value = null
    currentFile.value = ''
    matchesFound.value = 0
    speed.value = 0
    etaSeconds.value = null
    duration.value = 0
    errorMessage.value = ''
  }

  return {
    isSearching,
    matches,
    filesScanned,
    totalFiles,
    currentFile,
    matchesFound,
    speed,
    etaSeconds,
    duration,
    errorMessage,
    progressPercentage,
    formattedEta,
    startSearch,
    cancelSearch,
    clearResults,
    // Form state
    selectedTemplate,
    firstName,
    lastName,
    customPattern,
  }
})
