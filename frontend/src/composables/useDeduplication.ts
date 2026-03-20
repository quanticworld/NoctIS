/**
 * Composable for running deduplication with real-time progress via WebSocket
 */
import { ref } from 'vue'

export interface DeduplicationProgress {
  batch: number
  processed: number
  new_masters: number
  merged: number
  errors: number
}

export interface DeduplicationComplete {
  processed: number
  new_masters: number
  merged: number
  errors: number
  has_more: boolean
}

export function useDeduplication() {
  const isRunning = ref(false)
  const progress = ref<DeduplicationProgress | null>(null)
  const complete = ref<DeduplicationComplete | null>(null)
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null

  function connectWebSocket(): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/search`

      const socket = new WebSocket(wsUrl)

      socket.onopen = () => {
        ws = socket
        resolve(socket)
      }

      socket.onerror = (err) => {
        reject(err)
      }

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          handleMessage(message)
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      socket.onclose = () => {
        ws = null
      }
    })
  }

  function handleMessage(message: any) {
    console.log('[DEDUP] Received message:', message.type)

    switch (message.type) {
      case 'progress':
        progress.value = {
          batch: message.batch,
          processed: message.processed,
          new_masters: message.new_masters,
          merged: message.merged,
          errors: message.errors
        }
        break

      case 'complete':
        isRunning.value = false
        complete.value = {
          processed: message.processed,
          new_masters: message.new_masters,
          merged: message.merged,
          errors: message.errors,
          has_more: message.has_more
        }
        if (ws) {
          ws.close()
          ws = null
        }
        break

      case 'error':
        isRunning.value = false
        error.value = message.message
        if (ws) {
          ws.close()
          ws = null
        }
        break
    }
  }

  async function startDeduplication(batchSize = 250, maxBatches?: number) {
    if (isRunning.value) {
      console.log('[DEDUP] Already running')
      return
    }

    // Reset state
    progress.value = null
    complete.value = null
    error.value = null
    isRunning.value = true

    try {
      // Connect if not already connected
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        await connectWebSocket()
      }

      // Send deduplication request
      ws!.send(JSON.stringify({
        action: 'deduplication',
        data: {
          batch_size: batchSize,
          max_batches: maxBatches
        }
      }))
    } catch (err) {
      isRunning.value = false
      error.value = `Failed to start deduplication: ${err}`
      throw err
    }
  }

  function reset() {
    progress.value = null
    complete.value = null
    error.value = null
  }

  return {
    isRunning,
    progress,
    complete,
    error,
    startDeduplication,
    reset
  }
}
