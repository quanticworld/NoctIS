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
})
