import { ref } from 'vue'

export interface ColumnInfo {
  name: string
  type: string
  samples?: string[]
}

export interface FileAnalysis {
  total_rows: number
  encoding: string
  delimiter: string
  columns: ColumnInfo[]
}

export function useFileService() {
  const fileAnalysis = ref<FileAnalysis | null>(null)
  const analyzing = ref(false)
  const analysisError = ref<string | null>(null)

  async function analyzeFile(filePath: string, delimiter?: string, encoding?: string) {
    analyzing.value = true
    analysisError.value = null
    fileAnalysis.value = null

    try {
      let url = `/api/v1/files/analyze?file_path=${encodeURIComponent(filePath)}`

      if (delimiter) {
        url += `&delimiter=${encodeURIComponent(delimiter)}`
      }

      if (encoding) {
        url += `&encoding=${encodeURIComponent(encoding)}`
      }

      const response = await fetch(url)

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to analyze file')
      }

      fileAnalysis.value = await response.json()
    } catch (err) {
      analysisError.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('File analysis error:', err)
    } finally {
      analyzing.value = false
    }
  }

  return {
    fileAnalysis,
    analyzing,
    analysisError,
    analyzeFile
  }
}
