import { ref } from 'vue'

export interface ImportRequest {
  file_path: string
  breach_name: string
  column_mapping: Record<string, string | undefined>
  breach_date?: number
  batch_size?: number
}

export interface ImportPreview {
  total_rows: number
  preview_count: number
  sample_documents: any[]
  mapped_fields: string[]
}

export interface ImportProgress {
  status: 'analyzing' | 'importing' | 'completed' | 'error' | 'cancelled'
  message: string
  progress: number
  imported?: number
  failed?: number
  total_rows?: number
  rows_processed?: number
  errors?: string[]
}

export function useImportService() {
  const importPreview = ref<ImportPreview | null>(null)
  const importProgress = ref<ImportProgress | null>(null)
  const importing = ref(false)
  const importComplete = ref(false)
  let websocket: WebSocket | null = null
  let currentImportId: string | null = null

  async function previewImport(request: ImportRequest) {
    try {
      const response = await fetch('/api/v1/import/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to preview import')
      }

      importPreview.value = await response.json()
    } catch (err) {
      console.error('Preview error:', err)
      throw err
    }
  }

  async function startImport(request: ImportRequest) {
    importing.value = true
    importComplete.value = false
    importProgress.value = null
    currentImportId = `import_${Date.now()}`

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/v1/import/stream`

    websocket = new WebSocket(wsUrl)

    websocket.onopen = () => {
      const payload = {
        ...request,
        import_id: currentImportId
      }
      websocket?.send(JSON.stringify(payload))
    }

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log('Import progress update:', data)
        importProgress.value = data

        if (data.status === 'completed' || data.status === 'error' || data.status === 'cancelled') {
          importing.value = false
          importComplete.value = true
          websocket?.close()
        }
      } catch (err) {
        console.error('WebSocket message parse error:', err)
      }
    }

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error)
      importing.value = false
      importProgress.value = {
        status: 'error',
        message: 'WebSocket connection error',
        progress: 0
      }
    }

    websocket.onclose = () => {
      if (importing.value) {
        // Unexpected close
        importing.value = false
        if (importProgress.value?.status !== 'completed') {
          importProgress.value = {
            status: 'error',
            message: 'Connection closed unexpectedly',
            progress: importProgress.value?.progress || 0
          }
        }
      }
    }
  }

  async function cancelImport() {
    if (!currentImportId) return

    try {
      await fetch('/api/v1/import/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ import_id: currentImportId })
      })

      websocket?.close()
      importing.value = false
    } catch (err) {
      console.error('Cancel import error:', err)
    }
  }

  return {
    importPreview,
    importProgress,
    importing,
    importComplete,
    previewImport,
    startImport,
    cancelImport
  }
}
