import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Config, RegexTemplate } from '@/types'

export const useConfigStore = defineStore('config', () => {
  const searchPath = ref('/mnt/osint')
  const threads = ref(8)
  const maxFilesize = ref('100M')
  const fileTypes = ref<string[]>([])
  const excludeTypes = ref<string[]>([])
  const templates = ref<RegexTemplate[]>([])

  async function loadConfig() {
    try {
      const response = await fetch('/api/v1/config')
      const data: Config = await response.json()

      searchPath.value = data.search_path
      threads.value = data.threads
      maxFilesize.value = data.max_filesize
      templates.value = data.available_templates
    } catch (error) {
      console.error('Failed to load config:', error)
    }
  }

  function updateSearchPath(path: string) {
    searchPath.value = path
    localStorage.setItem('noctis_search_path', path)
  }

  function updateThreads(count: number) {
    threads.value = count
    localStorage.setItem('noctis_threads', count.toString())
  }

  function updateMaxFilesize(size: string) {
    maxFilesize.value = size
    localStorage.setItem('noctis_max_filesize', size)
  }

  function updateFileTypes(types: string[]) {
    fileTypes.value = types
    localStorage.setItem('noctis_file_types', JSON.stringify(types))
  }

  function updateExcludeTypes(types: string[]) {
    excludeTypes.value = types
    localStorage.setItem('noctis_exclude_types', JSON.stringify(types))
  }

  function loadFromLocalStorage() {
    const savedPath = localStorage.getItem('noctis_search_path')
    if (savedPath) searchPath.value = savedPath

    const savedThreads = localStorage.getItem('noctis_threads')
    if (savedThreads) threads.value = parseInt(savedThreads)

    const savedMaxFilesize = localStorage.getItem('noctis_max_filesize')
    if (savedMaxFilesize) maxFilesize.value = savedMaxFilesize

    const savedFileTypes = localStorage.getItem('noctis_file_types')
    if (savedFileTypes) fileTypes.value = JSON.parse(savedFileTypes)

    const savedExcludeTypes = localStorage.getItem('noctis_exclude_types')
    if (savedExcludeTypes) excludeTypes.value = JSON.parse(savedExcludeTypes)
  }

  return {
    searchPath,
    threads,
    maxFilesize,
    fileTypes,
    excludeTypes,
    templates,
    loadConfig,
    updateSearchPath,
    updateThreads,
    updateMaxFilesize,
    updateFileTypes,
    updateExcludeTypes,
    loadFromLocalStorage,
  }
})
