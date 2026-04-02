/**
 * Composable for managing background imports
 */
import { ref, computed, onUnmounted } from 'vue'

export interface ImportProgress {
  total_lines: number
  processed_lines: number
  imported_count: number
  error_count: number
  current_batch: number
  total_batches: number
  percentage: number
  speed_lines_per_sec: number
  eta_seconds: number | null
  elapsed_seconds: number
}

export interface ImportJob {
  job_id: string
  file_path: string
  breach_name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  created_at: string
  started_at: string | null
  completed_at: string | null
  progress: ImportProgress
  error_message: string | null
}

export function useBackgroundImport() {
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const API_PREFIX = '/api/v1'

  const currentJob = ref<ImportJob | null>(null)
  const allJobs = ref<ImportJob[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  let pollInterval: number | null = null

  // Computed
  const isImporting = computed(() =>
    currentJob.value?.status === 'running' || currentJob.value?.status === 'pending'
  )

  const progress = computed(() => currentJob.value?.progress?.percentage || 0)
  const eta = computed(() => currentJob.value?.progress?.eta_seconds || null)
  const speed = computed(() => currentJob.value?.progress?.speed_lines_per_sec || 0)

  /**
   * Start a background import
   */
  async function startImport(params: {
    file_path: string
    breach_name: string
    column_mapping: Record<string, string>
    breach_date?: number
    batch_size?: number
  }): Promise<string | null> {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_URL}${API_PREFIX}/import/background/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to start import')
      }

      const data = await response.json()
      const jobId = data.job_id

      // Start polling for this job
      await pollJobStatus(jobId)
      startPolling(jobId)

      return jobId

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Poll job status
   */
  async function pollJobStatus(jobId: string) {
    try {
      const response = await fetch(`${API_URL}${API_PREFIX}/import/background/status/${jobId}`)

      if (!response.ok) {
        throw new Error('Failed to fetch job status')
      }

      const job: ImportJob = await response.json()
      currentJob.value = job

      // Stop polling if job is finished
      if (['completed', 'failed', 'cancelled'].includes(job.status)) {
        stopPolling()
      }

    } catch (err) {
      console.error('Failed to poll job status:', err)
      error.value = err instanceof Error ? err.message : 'Failed to fetch status'
    }
  }

  /**
   * Start polling
   */
  function startPolling(jobId: string, intervalMs: number = 2000) {
    stopPolling() // Clear any existing interval

    pollInterval = window.setInterval(() => {
      pollJobStatus(jobId)
    }, intervalMs)
  }

  /**
   * Stop polling
   */
  function stopPolling() {
    if (pollInterval !== null) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  /**
   * Cancel a running import
   */
  async function cancelImport(jobId: string): Promise<boolean> {
    try {
      const response = await fetch(`${API_URL}${API_PREFIX}/import/background/cancel/${jobId}`, {
        method: 'POST'
      })

      if (!response.ok) {
        throw new Error('Failed to cancel import')
      }

      await pollJobStatus(jobId)
      return true

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to cancel'
      return false
    }
  }

  /**
   * Fetch all jobs
   */
  async function fetchAllJobs(statusFilter?: string) {
    try {
      const url = statusFilter
        ? `${API_URL}${API_PREFIX}/import/background/jobs?status=${statusFilter}`
        : `${API_URL}${API_PREFIX}/import/background/jobs`

      const response = await fetch(url)

      if (!response.ok) {
        throw new Error('Failed to fetch jobs')
      }

      const data = await response.json()
      allJobs.value = data.jobs

    } catch (err) {
      console.error('Failed to fetch jobs:', err)
      error.value = err instanceof Error ? err.message : 'Failed to fetch jobs'
    }
  }

  /**
   * Cleanup old jobs
   */
  async function cleanupOldJobs(maxAgeHours: number = 24): Promise<boolean> {
    try {
      const response = await fetch(
        `${API_URL}${API_PREFIX}/import/background/cleanup?max_age_hours=${maxAgeHours}`,
        { method: 'DELETE' }
      )

      if (!response.ok) {
        throw new Error('Failed to cleanup jobs')
      }

      return true

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to cleanup'
      return false
    }
  }

  /**
   * Reset current job
   */
  function resetCurrentJob() {
    currentJob.value = null
    stopPolling()
    error.value = null
  }

  /**
   * Format ETA
   */
  function formatETA(seconds: number | null): string {
    if (!seconds || seconds <= 0) return 'Calculating...'

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

  /**
   * Format speed
   */
  function formatSpeed(linesPerSec: number): string {
    if (linesPerSec < 1000) {
      return `${Math.round(linesPerSec)} lines/s`
    } else if (linesPerSec < 1000000) {
      return `${(linesPerSec / 1000).toFixed(1)}k lines/s`
    } else {
      return `${(linesPerSec / 1000000).toFixed(2)}M lines/s`
    }
  }

  // Cleanup on unmount
  onUnmounted(() => {
    stopPolling()
  })

  return {
    // State
    currentJob,
    allJobs,
    loading,
    error,

    // Computed
    isImporting,
    progress,
    eta,
    speed,

    // Actions
    startImport,
    pollJobStatus,
    startPolling,
    stopPolling,
    cancelImport,
    fetchAllJobs,
    cleanupOldJobs,
    resetCurrentJob,

    // Helpers
    formatETA,
    formatSpeed
  }
}
