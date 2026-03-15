import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Stats } from '@/types'

export const useStatsStore = defineStore('stats', () => {
  const stats = ref<Stats | null>(null)
  const isLoading = ref(false)
  const error = ref('')

  const formattedSize = computed(() => {
    if (!stats.value) return '0 B'
    const bytes = stats.value.total_size_bytes

    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let size = bytes
    let unitIndex = 0

    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024
      unitIndex++
    }

    return `${size.toFixed(2)} ${units[unitIndex]}`
  })

  const formattedLines = computed(() => {
    if (!stats.value) return '0'
    return stats.value.total_lines.toLocaleString()
  })

  const formattedFiles = computed(() => {
    if (!stats.value) return '0'
    return stats.value.total_files.toLocaleString()
  })

  const topFileTypes = computed(() => {
    if (!stats.value) return []
    const types = Object.entries(stats.value.file_types)
    types.sort((a, b) => b[1] - a[1])
    return types.slice(0, 5)
  })

  async function loadStats(path: string) {
    isLoading.value = true
    error.value = ''

    try {
      const response = await fetch('/api/v1/stats', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ path }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to load stats')
      }

      stats.value = await response.json()
    } catch (err: any) {
      error.value = err.message
      throw err
    } finally {
      isLoading.value = false
    }
  }

  return {
    stats,
    isLoading,
    error,
    formattedSize,
    formattedLines,
    formattedFiles,
    topFileTypes,
    loadStats,
  }
})
