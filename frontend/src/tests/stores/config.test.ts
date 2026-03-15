import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useConfigStore } from '@/stores/config'

describe('Config Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('should have default values', () => {
    const store = useConfigStore()
    expect(store.searchPath).toBe('/mnt/osint')
    expect(store.threads).toBe(8)
    expect(store.maxFilesize).toBe('100M')
  })

  it('should update search path', () => {
    const store = useConfigStore()
    store.updateSearchPath('/custom/path')
    expect(store.searchPath).toBe('/custom/path')
    expect(localStorage.getItem('noctis_search_path')).toBe('/custom/path')
  })

  it('should update threads', () => {
    const store = useConfigStore()
    store.updateThreads(16)
    expect(store.threads).toBe(16)
    expect(localStorage.getItem('noctis_threads')).toBe('16')
  })

  it('should update max filesize', () => {
    const store = useConfigStore()
    store.updateMaxFilesize('500M')
    expect(store.maxFilesize).toBe('500M')
    expect(localStorage.getItem('noctis_max_filesize')).toBe('500M')
  })

  it('should load from localStorage', () => {
    localStorage.setItem('noctis_search_path', '/saved/path')
    localStorage.setItem('noctis_threads', '12')
    localStorage.setItem('noctis_max_filesize', '200M')

    const store = useConfigStore()
    store.loadFromLocalStorage()

    expect(store.searchPath).toBe('/saved/path')
    expect(store.threads).toBe(12)
    expect(store.maxFilesize).toBe('200M')
  })

  it('should handle path with spaces', () => {
    const store = useConfigStore()
    const pathWithSpaces = '/home/user/My Documents/OSINT Data'

    store.updateSearchPath(pathWithSpaces)
    expect(store.searchPath).toBe(pathWithSpaces)
    expect(localStorage.getItem('noctis_search_path')).toBe(pathWithSpaces)

    // Reload from localStorage
    const store2 = useConfigStore()
    store2.loadFromLocalStorage()
    expect(store2.searchPath).toBe(pathWithSpaces)
  })

  it('should handle path with special characters', () => {
    const store = useConfigStore()
    const specialPath = '/home/user/data-2024/files_v1.0 (backup)'

    store.updateSearchPath(specialPath)
    expect(store.searchPath).toBe(specialPath)
    expect(localStorage.getItem('noctis_search_path')).toBe(specialPath)
  })

  it('should handle file types with arrays', () => {
    const store = useConfigStore()
    const fileTypes = ['txt', 'log', 'json']
    const excludeTypes = ['pdf', 'zip']

    store.updateFileTypes(fileTypes)
    store.updateExcludeTypes(excludeTypes)

    expect(store.fileTypes).toEqual(fileTypes)
    expect(store.excludeTypes).toEqual(excludeTypes)

    // Check localStorage
    expect(JSON.parse(localStorage.getItem('noctis_file_types')!)).toEqual(fileTypes)
    expect(JSON.parse(localStorage.getItem('noctis_exclude_types')!)).toEqual(excludeTypes)

    // Reload from localStorage
    const store2 = useConfigStore()
    store2.loadFromLocalStorage()
    expect(store2.fileTypes).toEqual(fileTypes)
    expect(store2.excludeTypes).toEqual(excludeTypes)
  })
})
