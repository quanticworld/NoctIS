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
import { ref, computed, onMounted } from 'vue'
import { useConfigStore } from '@/stores/config'
import { useSearchStore } from '@/stores/search'
import { useStatsStore } from '@/stores/stats'
import type { SearchMatch } from '@/types'

const configStore = useConfigStore()
const searchStore = useSearchStore()
const statsStore = useStatsStore()

const selectedTemplate = ref('name_search')
const firstName = ref('')
const lastName = ref('')
const customPattern = ref('')

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
    search_path: configStore.searchPath,
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
