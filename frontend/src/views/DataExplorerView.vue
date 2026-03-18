<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Stats Dashboard -->
    <div v-if="statsStore.stats" class="grid grid-cols-3 gap-4 mb-6">
      <div class="stat-card">
        <div class="stat-value">{{ statsStore.formattedFiles }}</div>
        <div class="stat-label">Total Files</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ statsStore.formattedSize }}</div>
        <div class="stat-label">Dataset Size</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ searchStore.matchesFound }}</div>
        <div class="stat-label">Matches Found</div>
      </div>
    </div>

    <!-- File Browser Modal -->
    <div v-if="showBrowser" class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50" @click.self="showBrowser = false">
      <div class="bg-dark-100 border border-red-team-500 max-w-4xl w-full mx-4 max-h-[80vh] flex flex-col">
        <!-- Modal Header -->
        <div class="flex items-center justify-between p-4 border-b border-gray-700">
          <h3 class="text-lg font-bold text-red-team-500 uppercase tracking-wide">
            {{ searchMode === 'file' ? 'SELECT FILE' : 'SELECT DIRECTORY' }}
          </h3>
          <button @click="showBrowser = false" class="text-gray-400 hover:text-gray-100">
            <span class="text-2xl">×</span>
          </button>
        </div>

        <!-- Current Path -->
        <div class="p-4 border-b border-gray-700">
          <div class="flex items-center gap-2">
            <span class="text-sm text-gray-400">PATH:</span>
            <span class="text-sm text-gray-100 font-mono">{{ browsePath }}</span>
          </div>
        </div>

        <!-- File List -->
        <div class="flex-1 overflow-y-auto p-4">
          <div v-if="browseLoading" class="text-center text-gray-400 py-8">
            Loading...
          </div>
          <div v-else-if="browseError" class="text-center text-red-team-500 py-8">
            {{ browseError }}
          </div>
          <div v-else class="space-y-1">
            <!-- Parent Directory -->
            <div
              v-if="browseParentPath"
              @click="navigateTo(browseParentPath)"
              class="flex items-center gap-3 p-2 hover:bg-dark-200 cursor-pointer border border-transparent hover:border-red-team-500 transition-colors"
            >
              <span class="text-red-team-500">📁</span>
              <span class="text-gray-300">..</span>
            </div>

            <!-- Directory/File Items -->
            <div
              v-for="item in browseItems"
              :key="item.path"
              @click="selectItem(item)"
              class="flex items-center gap-3 p-2 hover:bg-dark-200 cursor-pointer border border-transparent hover:border-red-team-500 transition-colors"
            >
              <span class="text-red-team-500">{{ item.is_directory ? '📁' : '📄' }}</span>
              <span class="flex-1 text-gray-300 truncate">{{ item.name }}</span>
              <span v-if="!item.is_directory" class="text-xs text-gray-500">
                {{ formatSize(item.size) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="p-4 border-t border-gray-700 flex justify-between items-center">
          <div class="text-sm text-gray-400">
            {{ browseItems.length }} items
          </div>
          <div class="flex gap-2">
            <button @click="showBrowser = false" class="btn-secondary">
              CANCEL
            </button>
            <button
              v-if="searchMode === 'directory'"
              @click="selectCurrentDirectory"
              class="btn-primary"
            >
              SELECT THIS DIRECTORY
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Search Configuration -->
    <div class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Search Parameters</h2>

      <!-- Template Selection -->
      <div class="input-group">
        <label class="label">Regex Template</label>
        <select v-model="selectedTemplate" class="w-full">
          <option v-for="template in configStore.templates" :key="template.id" :value="template.id">
            {{ template.name }} - {{ template.description }}
          </option>
        </select>
      </div>

      <!-- Search Target Selection -->
      <div class="input-group">
        <label class="label">Search Target</label>
        <div class="flex gap-3">
          <div class="flex items-center gap-2">
            <input type="radio" id="mode-dir" value="directory" v-model="searchMode" class="w-4 h-4" />
            <label for="mode-dir" class="text-sm text-gray-300 cursor-pointer">Directory</label>
          </div>
          <div class="flex items-center gap-2">
            <input type="radio" id="mode-file" value="file" v-model="searchMode" class="w-4 h-4" />
            <label for="mode-file" class="text-sm text-gray-300 cursor-pointer">Single File</label>
          </div>
        </div>
      </div>

      <!-- Path Input -->
      <div class="input-group">
        <label class="label">{{ searchMode === 'file' ? 'File Path' : 'Directory Path' }}</label>
        <div class="flex gap-2">
          <input
            v-model="searchPath"
            type="text"
            :placeholder="searchMode === 'file' ? '/home/quantic/tmp/France 01.txt' : '/home/quantic/tmp'"
            class="flex-1"
          />
          <button @click="browseFiles" class="btn-secondary whitespace-nowrap">
            BROWSE
          </button>
        </div>
        <div class="text-xs text-gray-500 mt-1">
          {{ searchMode === 'file' ? 'Specify exact file path to search within a single file' : 'Specify directory to search recursively' }}
        </div>
      </div>

      <!-- Dynamic Fields -->
      <div v-if="currentTemplate">
        <!-- Name Search Fields -->
        <div v-if="currentTemplate.id === 'name_search'" class="grid grid-cols-2 gap-4">
          <div class="input-group">
            <label class="label">First Name</label>
            <input v-model="firstName" type="text" placeholder="John" />
          </div>
          <div class="input-group">
            <label class="label">Last Name</label>
            <input v-model="lastName" type="text" placeholder="Doe" />
          </div>
        </div>

        <!-- Custom Pattern Field -->
        <div v-if="currentTemplate.id === 'custom'" class="input-group">
          <label class="label">Custom Regex Pattern</label>
          <input v-model="customPattern" type="text" placeholder="Enter regex pattern..." />
        </div>

        <!-- Pattern Preview -->
        <div class="input-group">
          <label class="label">Pattern Preview</label>
          <div class="bg-dark-200 border border-gray-700 px-3 py-2 text-sm text-gray-400 font-mono">
            {{ patternPreview }}
          </div>
        </div>
      </div>

      <!-- Search Button -->
      <div class="flex space-x-3">
        <button
          @click="startSearch"
          :disabled="searchStore.isSearching || !canSearch"
          class="btn-primary flex-1"
        >
          {{ searchStore.isSearching ? 'SEARCHING...' : 'START SEARCH' }}
        </button>
        <button
          v-if="searchStore.isSearching"
          @click="searchStore.cancelSearch()"
          class="btn-secondary"
        >
          CANCEL
        </button>
        <button
          v-if="searchStore.matches.length > 0"
          @click="searchStore.clearResults()"
          class="btn-secondary"
        >
          CLEAR
        </button>
      </div>
    </div>

    <!-- Progress Bar -->
    <div v-if="searchStore.isSearching" class="card p-6 mb-6">
      <div class="flex items-center justify-between mb-2">
        <div class="text-sm text-gray-400">
          <span class="text-red-team-500 font-bold">{{ searchStore.filesScanned.toLocaleString() }}</span>
          files scanned
          <span v-if="searchStore.totalFiles">
            / {{ searchStore.totalFiles.toLocaleString() }}
            ({{ searchStore.progressPercentage }}%)
          </span>
        </div>
        <div class="text-sm text-gray-400">
          <span class="text-red-team-500 font-bold">{{ searchStore.speed.toFixed(1) }}</span> files/sec
          <span v-if="searchStore.etaSeconds" class="ml-3">
            ETA: <span class="text-red-team-500">{{ searchStore.formattedEta }}</span>
          </span>
        </div>
      </div>

      <div class="bg-dark-200 h-2 mb-2">
        <div
          v-if="searchStore.totalFiles"
          class="progress-bar"
          :style="{ width: searchStore.progressPercentage + '%' }"
        ></div>
        <div
          v-else
          class="progress-bar animate-pulse"
          style="width: 100%"
        ></div>
      </div>

      <div class="text-xs text-gray-500 truncate">{{ searchStore.currentFile }}</div>
    </div>

    <!-- Error Message -->
    <div v-if="searchStore.errorMessage" class="card p-4 mb-6 border-red-team-500">
      <div class="text-red-team-500">ERROR: {{ searchStore.errorMessage }}</div>
    </div>

    <!-- Results -->
    <div class="card p-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-bold text-red-team-500 uppercase tracking-wide">
          Results ({{ searchStore.matches.length }})
        </h2>
        <div v-if="searchStore.duration > 0" class="text-sm text-gray-400">
          Completed in <span class="text-red-team-500">{{ searchStore.duration.toFixed(2) }}s</span>
        </div>
      </div>

      <!-- Results List -->
      <div v-if="searchStore.matches.length > 0" class="space-y-2 max-h-[600px] overflow-y-auto">
        <div
          v-for="(match, index) in searchStore.matches"
          :key="index"
          class="bg-dark-200 border border-gray-700 p-3 hover:border-red-team-500 transition-colors"
        >
          <div class="flex items-center justify-between mb-2">
            <div class="text-sm text-gray-400 truncate flex-1">
              {{ match.file_path }}
            </div>
            <div class="text-xs text-gray-500 ml-3">
              Line {{ match.line_number }}
            </div>
          </div>
          <div class="font-mono text-sm text-gray-300">
            <span v-html="highlightMatch(match)"></span>
          </div>
        </div>
      </div>

      <div v-else class="text-center text-gray-500 py-12">
        No results yet. Configure search parameters and click "Start Search".
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useConfigStore } from '@/stores/config'
import { useSearchStore } from '@/stores/search'
import { useStatsStore } from '@/stores/stats'
import type { SearchMatch } from '@/types'

const configStore = useConfigStore()
const searchStore = useSearchStore()
const statsStore = useStatsStore()

// Search target configuration
const searchMode = ref<'directory' | 'file'>('directory')
const searchPath = ref('/home/quantic/tmp')

// File browser state
const showBrowser = ref(false)
const browseLoading = ref(false)
const browseError = ref<string | null>(null)
const browsePath = ref('/home/quantic/tmp')
const browseParentPath = ref<string | null>(null)
const browseItems = ref<any[]>([])

// Use store refs for form state (persists across navigation)
const selectedTemplate = computed({
  get: () => searchStore.selectedTemplate,
  set: (value) => { searchStore.selectedTemplate = value }
})
const firstName = computed({
  get: () => searchStore.firstName,
  set: (value) => { searchStore.firstName = value }
})
const lastName = computed({
  get: () => searchStore.lastName,
  set: (value) => { searchStore.lastName = value }
})
const customPattern = computed({
  get: () => searchStore.customPattern,
  set: (value) => { searchStore.customPattern = value }
})

const currentTemplate = computed(() => {
  return configStore.templates.find((t) => t.id === selectedTemplate.value)
})

const patternPreview = computed(() => {
  if (!currentTemplate.value) return ''

  if (selectedTemplate.value === 'name_search') {
    const first = firstName.value || 'FIRST'
    const last = lastName.value || 'LAST'
    return `(${first}.*${last}|${last}.*${first})`
  } else if (selectedTemplate.value === 'custom') {
    return customPattern.value || 'Enter custom pattern...'
  } else {
    return currentTemplate.value.pattern
  }
})

const canSearch = computed(() => {
  if (selectedTemplate.value === 'name_search') {
    return firstName.value && lastName.value
  } else if (selectedTemplate.value === 'custom') {
    return customPattern.value
  }
  return true
})

async function startSearch() {
  const request: any = {
    template: selectedTemplate.value,
    search_path: searchPath.value,
    threads: configStore.threads,
    max_filesize: configStore.maxFilesize,
    case_insensitive: true,
  }

  if (selectedTemplate.value === 'name_search') {
    request.first_name = firstName.value
    request.last_name = lastName.value
  } else if (selectedTemplate.value === 'custom') {
    request.pattern = customPattern.value
  }

  // Add file type filters from settings
  if (configStore.fileTypes.length > 0) {
    request.file_types = configStore.fileTypes
  }
  if (configStore.excludeTypes.length > 0) {
    request.exclude_types = configStore.excludeTypes
  }

  await searchStore.startSearch(request)
}

async function browseFiles() {
  // Initialize browse path from current search path
  browsePath.value = searchPath.value
  showBrowser.value = true
  await loadBrowseData(browsePath.value)
}

async function loadBrowseData(path: string) {
  browseLoading.value = true
  browseError.value = null

  try {
    const response = await fetch(`/api/v1/files/browse?path=${encodeURIComponent(path)}&mode=${searchMode.value}`)

    if (!response.ok) {
      throw new Error('Failed to browse files')
    }

    const data = await response.json()
    browsePath.value = data.current_path
    browseParentPath.value = data.parent_path
    browseItems.value = data.items

  } catch (error) {
    browseError.value = error instanceof Error ? error.message : 'Failed to browse files'
    console.error('Browse failed:', error)
  } finally {
    browseLoading.value = false
  }
}

async function navigateTo(path: string) {
  await loadBrowseData(path)
}

function selectItem(item: any) {
  if (searchMode.value === 'directory' && item.is_directory) {
    // Navigate into directory
    navigateTo(item.path)
  } else if (searchMode.value === 'file' && !item.is_directory) {
    // Select file
    searchPath.value = item.path
    showBrowser.value = false
  } else if (searchMode.value === 'directory' && !item.is_directory) {
    // In directory mode, clicking a file does nothing (or could show a message)
    return
  } else {
    // In file mode, clicking a directory navigates into it
    navigateTo(item.path)
  }
}

function selectCurrentDirectory() {
  searchPath.value = browsePath.value
  showBrowser.value = false
}

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

function highlightMatch(match: SearchMatch): string {
  const { line_content, match_start, match_end } = match
  const before = escapeHtml(line_content.substring(0, match_start))
  const matchText = escapeHtml(line_content.substring(match_start, match_end))
  const after = escapeHtml(line_content.substring(match_end))

  return `${before}<span class="match-highlight">${matchText}</span>${after}`
}

function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  }
  return text.replace(/[&<>"']/g, (m) => map[m])
}

onMounted(async () => {
  // Stats are loaded on-demand from Settings page
  // Don't load automatically to avoid blocking on large datasets
})
</script>
