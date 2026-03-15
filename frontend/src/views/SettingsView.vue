<template>
  <div class="max-w-4xl mx-auto px-4 py-6">
    <div class="card p-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-6 uppercase tracking-wide">Configuration</h2>

      <!-- Search Path -->
      <div class="input-group">
        <label class="label">Search Path</label>
        <div class="flex space-x-3">
          <input
            v-model="searchPath"
            type="text"
            placeholder="/mnt/osint"
            class="flex-1"
          />
          <button @click="loadStats" :disabled="statsStore.isLoading" class="btn-primary">
            {{ statsStore.isLoading ? 'SCANNING...' : 'SCAN' }}
          </button>
        </div>
        <p class="text-xs text-gray-500 mt-1">
          Directory where ripgrep will search for files
        </p>
        <p v-if="statsStore.isLoading" class="text-xs text-red-team-500 mt-2">
          ⚠ Scanning directory (listing files, not reading content)...
        </p>
      </div>

      <!-- Threads -->
      <div class="input-group">
        <label class="label">Thread Count</label>
        <div class="flex items-center space-x-4">
          <input
            v-model.number="threads"
            type="range"
            min="1"
            max="16"
            class="flex-1"
          />
          <div class="w-12 text-right text-red-team-500 font-bold">{{ threads }}</div>
        </div>
        <p class="text-xs text-gray-500 mt-1">
          Number of parallel threads for ripgrep (1-16)
        </p>
      </div>

      <!-- Max Filesize -->
      <div class="input-group">
        <label class="label">Max File Size</label>
        <input
          v-model="maxFilesize"
          type="text"
          placeholder="100M"
        />
        <p class="text-xs text-gray-500 mt-1">
          Maximum file size to search (e.g., 100M, 1G)
        </p>
      </div>

      <!-- File Types to Include -->
      <div class="input-group">
        <label class="label">Include File Types (Optional)</label>
        <input
          v-model="fileTypesInput"
          type="text"
          placeholder="txt, log, json (comma separated)"
        />
        <p class="text-xs text-gray-500 mt-1">
          Only search these file types (leave empty for all)
        </p>
      </div>

      <!-- File Types to Exclude -->
      <div class="input-group">
        <label class="label">Exclude File Types (Optional)</label>
        <input
          v-model="excludeTypesInput"
          type="text"
          placeholder="pdf, zip, exe (comma separated)"
        />
        <p class="text-xs text-gray-500 mt-1">
          Skip these file types
        </p>
      </div>

      <!-- Save Button -->
      <button @click="saveSettings" class="btn-primary w-full">
        SAVE CONFIGURATION
      </button>

      <!-- Success Message -->
      <div v-if="showSavedMessage" class="mt-4 p-4 bg-red-team-500 bg-opacity-10 border border-red-team-500 text-red-team-500 text-center">
        ✓ Configuration saved successfully! Settings are now active for all searches.
      </div>

      <!-- Stats Display -->
      <div v-if="statsStore.stats" class="mt-8 pt-8 border-t border-gray-700">
        <h3 class="text-md font-bold text-red-team-500 mb-4 uppercase tracking-wide">Dataset Statistics</h3>

        <div class="grid grid-cols-2 gap-4 mb-6">
          <div class="stat-card">
            <div class="stat-value">{{ statsStore.formattedFiles }}</div>
            <div class="stat-label">Files</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ statsStore.formattedSize }}</div>
            <div class="stat-label">Size</div>
          </div>
        </div>

        <!-- File Types -->
        <div class="mb-6">
          <h4 class="text-sm text-gray-400 mb-3 uppercase tracking-wide">Top File Types</h4>
          <div class="space-y-2">
            <div
              v-for="[ext, count] in statsStore.topFileTypes"
              :key="ext"
              class="flex items-center justify-between bg-dark-200 border border-gray-700 px-3 py-2"
            >
              <span class="text-sm text-gray-300">{{ ext }}</span>
              <span class="text-sm text-red-team-500 font-bold">{{ count.toLocaleString() }}</span>
            </div>
          </div>
        </div>

        <!-- Largest Files -->
        <div>
          <h4 class="text-sm text-gray-400 mb-3 uppercase tracking-wide">Largest Files</h4>
          <div class="space-y-2">
            <div
              v-for="file in statsStore.stats.largest_files"
              :key="file.path"
              class="bg-dark-200 border border-gray-700 p-3"
            >
              <div class="text-sm text-gray-300 truncate mb-1">{{ file.path }}</div>
              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>{{ formatSize(file.size) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Error Display -->
      <div v-if="statsStore.error" class="mt-4 p-4 border border-red-team-500 bg-red-team-500 bg-opacity-10">
        <div class="text-red-team-500">ERROR: {{ statsStore.error }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConfigStore } from '@/stores/config'
import { useStatsStore } from '@/stores/stats'

const configStore = useConfigStore()
const statsStore = useStatsStore()

const searchPath = ref(configStore.searchPath)
const threads = ref(configStore.threads)
const maxFilesize = ref(configStore.maxFilesize)
const fileTypesInput = ref(configStore.fileTypes.join(', '))
const excludeTypesInput = ref(configStore.excludeTypes.join(', '))
const showSavedMessage = ref(false)

async function loadStats() {
  try {
    await statsStore.loadStats(searchPath.value)
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

function saveSettings() {
  // Update all settings in the store
  configStore.updateSearchPath(searchPath.value)
  configStore.updateThreads(threads.value)
  configStore.updateMaxFilesize(maxFilesize.value)

  // Parse file types from comma-separated input
  const fileTypes = fileTypesInput.value
    .split(',')
    .map(t => t.trim())
    .filter(t => t.length > 0)
  configStore.updateFileTypes(fileTypes)

  const excludeTypes = excludeTypesInput.value
    .split(',')
    .map(t => t.trim())
    .filter(t => t.length > 0)
  configStore.updateExcludeTypes(excludeTypes)

  // Debug: log what was saved
  console.log('Settings saved:', {
    searchPath: searchPath.value,
    threads: threads.value,
    maxFilesize: maxFilesize.value,
    fileTypes,
    excludeTypes,
  })

  // Verify localStorage
  console.log('localStorage:', {
    search_path: localStorage.getItem('noctis_search_path'),
    threads: localStorage.getItem('noctis_threads'),
    max_filesize: localStorage.getItem('noctis_max_filesize'),
    file_types: localStorage.getItem('noctis_file_types'),
    exclude_types: localStorage.getItem('noctis_exclude_types'),
  })

  // Show visual confirmation
  showSavedMessage.value = true
  setTimeout(() => {
    showSavedMessage.value = false
  }, 3000)
}

function formatSize(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIndex = 0

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }

  return `${size.toFixed(2)} ${units[unitIndex]}`
}

onMounted(() => {
  // Sync with store values
  searchPath.value = configStore.searchPath
  threads.value = configStore.threads
  maxFilesize.value = configStore.maxFilesize
  fileTypesInput.value = configStore.fileTypes.join(', ')
  excludeTypesInput.value = configStore.excludeTypes.join(', ')
})
</script>

<style scoped>
input[type="range"] {
  @apply bg-dark-200 appearance-none h-1 outline-none;
}

input[type="range"]::-webkit-slider-thumb {
  @apply appearance-none w-4 h-4 bg-red-team-500 cursor-pointer;
}

input[type="range"]::-moz-range-thumb {
  @apply w-4 h-4 bg-red-team-500 cursor-pointer border-0;
}
</style>
