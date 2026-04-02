import { ref, onUnmounted } from 'vue'

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
  let currentJobId: string | null = null
  let pollInterval: number | null = null

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

    try {
      // Start background import
      const response = await fetch('/api/v1/import/background/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to start import')
      }

      const data = await response.json()
      currentJobId = data.job_id

      // Start polling for progress
      startPolling()

    } catch (err) {
      console.error('Import start error:', err)
      importing.value = false
      importProgress.value = {
        status: 'error',
        message: err instanceof Error ? err.message : 'Failed to start import',
        progress: 0
      }
    }
  }

  async function pollProgress() {
    if (!currentJobId) return

    try {
      const response = await fetch(`/api/v1/import/background/status/${currentJobId}`)

      if (!response.ok) {
        throw new Error('Failed to fetch import status')
      }

      const job = await response.json()

      // Convert backend progress format to frontend format
      const backendProgress = job.progress

      importProgress.value = {
        status: mapStatus(job.status),
        message: getStatusMessage(job.status, backendProgress),
        progress: backendProgress.percentage || 0,
        imported: backendProgress.imported_count,
        failed: backendProgress.error_count,
        total_rows: backendProgress.total_lines,
        rows_processed: backendProgress.processed_lines
      }

      // Check if import is finished
      if (['completed', 'failed', 'cancelled'].includes(job.status)) {
        importing.value = false
        importComplete.value = true
        stopPolling()

        if (job.status === 'failed') {
          importProgress.value.status = 'error'
          importProgress.value.message = job.error_message || 'Import failed'
        }
      }

    } catch (err) {
      console.error('Poll progress error:', err)
    }
  }

  function mapStatus(backendStatus: string): 'analyzing' | 'importing' | 'completed' | 'error' | 'cancelled' {
    switch (backendStatus) {
      case 'pending':
        return 'analyzing'
      case 'running':
        return 'importing'
      case 'completed':
        return 'completed'
      case 'failed':
        return 'error'
      case 'cancelled':
        return 'cancelled'
      default:
        return 'analyzing'
    }
  }

  function getStatusMessage(status: string, progress: any): string {
    switch (status) {
      case 'pending':
        return 'Starting import...'
      case 'running':
        const speed = progress.speed_lines_per_sec || 0
        const eta = progress.eta_seconds || null
        let msg = `Importing... ${progress.processed_lines?.toLocaleString() || 0} / ${progress.total_lines?.toLocaleString() || 0} lines`
        if (speed > 0) {
          msg += ` (${formatSpeed(speed)})`
        }
        if (eta) {
          msg += ` - ETA: ${formatETA(eta)}`
        }
        return msg
      case 'completed':
        return `Import completed! ${progress.imported_count?.toLocaleString() || 0} records imported`
      case 'failed':
        return 'Import failed'
      case 'cancelled':
        return 'Import cancelled'
      default:
        return 'Processing...'
    }
  }

  function formatSpeed(linesPerSec: number): string {
    if (linesPerSec < 1000) {
      return `${Math.round(linesPerSec)} lines/s`
    } else if (linesPerSec < 1000000) {
      return `${(linesPerSec / 1000).toFixed(1)}k lines/s`
    } else {
      return `${(linesPerSec / 1000000).toFixed(2)}M lines/s`
    }
  }

  function formatETA(seconds: number): string {
    if (seconds < 60) {
      return `${Math.round(seconds)}s`
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60)
      const secs = Math.round(seconds % 60)
      return `${minutes}m ${secs}s`
    } else {
      const hours = Math.floor(seconds / 3600)
      const minutes = Math.floor((seconds % 3600) / 60)
      return `${hours}h ${minutes}m`
    }
  }

  function startPolling() {
    stopPolling() // Clear any existing interval

    // Poll immediately
    pollProgress()

    // Then poll every 2 seconds
    pollInterval = window.setInterval(() => {
      pollProgress()
    }, 2000)
  }

  function stopPolling() {
    if (pollInterval !== null) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  async function cancelImport() {
    if (!currentJobId) return

    try {
      await fetch(`/api/v1/import/background/cancel/${currentJobId}`, {
        method: 'POST'
      })

      importing.value = false
      stopPolling()

      importProgress.value = {
        status: 'cancelled',
        message: 'Import cancelled',
        progress: importProgress.value?.progress || 0
      }
    } catch (err) {
      console.error('Cancel import error:', err)
    }
  }

  // Cleanup on unmount
  onUnmounted(() => {
    stopPolling()
  })

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
