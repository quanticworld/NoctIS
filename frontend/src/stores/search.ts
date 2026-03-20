import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SearchMatch, WebSocketMessage } from '@/types'

// Force reload - version 2
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
  const isCancelling = ref(false)

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
    console.log('[SEARCH STORE V2] Received message:', message.type, 'isSearching:', isSearching.value)

    // Ignore all messages except 'error' if search is not running
    // This prevents results from continuing to appear after cancel/complete
    if (!isSearching.value && message.type !== 'error') {
      console.log('[SEARCH STORE V2] *** IGNORING MESSAGE - search not active ***')
      return
    }

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
        console.log('[SEARCH STORE] Search completed')
        isSearching.value = false
        isCancelling.value = false
        duration.value = message.duration_seconds
        matchesFound.value = message.total_matches
        filesScanned.value = message.files_scanned
        break

      case 'error':
        console.log('[SEARCH STORE] Search error:', message.message)
        isSearching.value = false
        isCancelling.value = false
        errorMessage.value = message.message
        break
    }
  }

  async function startSearch(request: any) {
    console.log('[SEARCH STORE] startSearch called, current isSearching:', isSearching.value)

    // Prevent starting a new search if one is already running
    if (isSearching.value) {
      console.log('[SEARCH STORE] Search already in progress, ignoring')
      return
    }

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

    console.log('[SEARCH STORE] Starting new search')
    try {
      // Connect if not already connected
      if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
        console.log('[SEARCH STORE] Connecting WebSocket')
        await connectWebSocket()
      }

      // Send search request
      console.log('[SEARCH STORE] Sending search request to backend')
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
    console.log('[SEARCH STORE V3] cancelSearch called, ws ready:', ws.value?.readyState === WebSocket.OPEN, 'isCancelling:', isCancelling.value)

    // Prevent multiple cancel requests
    if (isCancelling.value) {
      console.log('[SEARCH STORE V3] Already cancelling, ignoring')
      return
    }

    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      console.log('[SEARCH STORE V3] Sending cancel message and closing WebSocket')
      isCancelling.value = true

      // Send cancel message to backend
      try {
        ws.value.send(JSON.stringify({ action: 'cancel' }))
      } catch (e) {
        console.log('[SEARCH STORE V3] Error sending cancel:', e)
      }

      // Close the WebSocket connection immediately to stop receiving messages
      ws.value.close()
      ws.value = null

      // Update state
      isSearching.value = false
      isCancelling.value = false
      console.log('[SEARCH STORE V3] WebSocket closed, search cancelled')
    }
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
    isCancelling,
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
