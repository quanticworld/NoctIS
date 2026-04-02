<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-red-team-500 uppercase tracking-wide">Scrapers & Monitors</h1>
        <p class="text-sm text-gray-400 mt-1">Automated data collection from Pastebin, paste sites, and custom sources</p>
      </div>
      <button @click="showCreateModal = true" class="btn-primary">
        + NEW SCRAPER
      </button>
    </div>

    <!-- Scrapers List -->
    <div class="grid grid-cols-1 gap-4 mb-6">
      <div v-if="loading" class="card p-6 text-center text-gray-400">
        Loading scrapers...
      </div>

      <div v-else-if="scrapers.length === 0" class="card p-6 text-center text-gray-400">
        No scrapers yet. Create one from a template or custom code.
      </div>

      <div
        v-for="scraper in scrapers"
        :key="scraper.id"
        class="card p-4 hover:border-red-team-500 transition-colors cursor-pointer"
        @click="selectScraper(scraper)"
      >
        <div class="flex items-center justify-between">
          <!-- Info -->
          <div class="flex-1">
            <div class="flex items-center space-x-3">
              <h3 class="text-lg font-bold text-gray-200">{{ scraper.name }}</h3>
              <span
                class="px-2 py-0.5 text-xs font-bold uppercase tracking-wider"
                :class="{
                  'bg-green-500 bg-opacity-10 text-green-500': scraper.enabled,
                  'bg-gray-500 bg-opacity-10 text-gray-500': !scraper.enabled
                }"
              >
                {{ scraper.enabled ? 'ENABLED' : 'DISABLED' }}
              </span>
              <span class="px-2 py-0.5 text-xs bg-dark-200 text-gray-400">
                {{ scraper.language.toUpperCase() }}
              </span>
            </div>

            <p class="text-sm text-gray-400 mt-1">{{ scraper.description }}</p>

            <div class="flex items-center space-x-4 mt-2 text-xs text-gray-500">
              <div v-if="scraper.cron_expression">
                Schedule: <span class="font-mono text-gray-400">{{ scraper.cron_expression }}</span>
              </div>
              <div v-if="scraper.next_run_at">
                Next: <span class="text-gray-400">{{ formatNextRun(scraper.next_run_at) }}</span>
              </div>
              <div v-if="scraper.keywords && scraper.keywords.length > 0">
                Keywords: <span class="text-gray-400">{{ scraper.keywords.join(', ') }}</span>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center space-x-2">
            <button
              @click.stop="executeScraper(scraper.id)"
              class="btn-secondary text-xs"
              :disabled="executing === scraper.id"
            >
              {{ executing === scraper.id ? 'RUNNING...' : 'RUN NOW' }}
            </button>
            <button
              @click.stop="toggleScraper(scraper)"
              class="btn-secondary text-xs"
            >
              {{ scraper.enabled ? 'DISABLE' : 'ENABLE' }}
            </button>
            <button
              @click.stop="deleteScraper(scraper.id)"
              class="text-red-team-500 hover:text-red-team-400 text-xs px-2 py-1"
            >
              DELETE
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Templates -->
    <div class="card p-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Templates</h2>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div
          v-for="template in templates"
          :key="template.id"
          class="bg-dark-200 border border-gray-700 p-4 hover:border-red-team-500 transition-colors cursor-pointer"
          @click="createFromTemplate(template)"
        >
          <h3 class="text-md font-bold text-gray-200 mb-2">{{ template.name }}</h3>
          <p class="text-sm text-gray-400 mb-3">{{ template.description }}</p>
          <div class="flex items-center justify-between">
            <span class="text-xs text-gray-500">{{ template.language.toUpperCase() }}</span>
            <button class="text-xs text-red-team-500 hover:text-red-team-400">
              USE TEMPLATE →
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create/Edit Modal -->
    <div
      v-if="showCreateModal || selectedScraper"
      class="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4"
      @click.self="closeModal"
    >
      <div class="bg-dark-100 border border-gray-700 max-w-6xl w-full max-h-[90vh] overflow-y-auto">
        <div class="sticky top-0 bg-dark-100 border-b border-gray-700 p-4 flex items-center justify-between">
          <h2 class="text-lg font-bold text-red-team-500 uppercase">
            {{ selectedScraper ? 'Edit Scraper' : 'New Scraper' }}
          </h2>
          <button @click="closeModal" class="text-gray-400 hover:text-gray-200">✕</button>
        </div>

        <div class="p-6">
          <!-- Basic Info -->
          <div class="grid grid-cols-2 gap-4 mb-4">
            <div class="input-group">
              <label class="label">Name *</label>
              <input v-model="form.name" type="text" placeholder="Pastebin Monitor" class="w-full" />
            </div>

            <div class="input-group">
              <label class="label">Language</label>
              <select v-model="form.language" class="w-full">
                <option value="python">Python</option>
                <option value="bash">Bash</option>
              </select>
            </div>
          </div>

          <div class="input-group mb-4">
            <label class="label">Description</label>
            <input v-model="form.description" type="text" placeholder="Monitor recent Pastebin pastes" class="w-full" />
          </div>

          <!-- Scheduling -->
          <div class="grid grid-cols-2 gap-4 mb-4">
            <div class="input-group">
              <label class="label">
                Cron Expression (optional)
                <span class="text-xs text-gray-500 ml-2">minute hour day month day_of_week</span>
              </label>
              <input v-model="form.cron_expression" type="text" placeholder="*/30 * * * * (every 30 min)" class="w-full font-mono text-sm" />
            </div>

            <div class="input-group">
              <label class="label">Keywords (comma-separated)</label>
              <input v-model="keywordsInput" type="text" placeholder="password, leak, database" class="w-full" />
            </div>
          </div>

          <!-- Options -->
          <div class="flex items-center space-x-4 mb-4">
            <label class="flex items-center space-x-2 cursor-pointer">
              <input v-model="form.enabled" type="checkbox" class="form-checkbox" />
              <span class="text-sm text-gray-300">Enable Scraper</span>
            </label>
            <label class="flex items-center space-x-2 cursor-pointer">
              <input v-model="form.auto_import" type="checkbox" class="form-checkbox" />
              <span class="text-sm text-gray-300">Auto-import findings to Typesense</span>
            </label>
          </div>

          <!-- Code Editor -->
          <div class="input-group mb-4">
            <label class="label">Code</label>
            <textarea
              v-model="form.code"
              class="w-full font-mono text-sm"
              rows="20"
              placeholder="#!/usr/bin/env python3..."
            ></textarea>
          </div>

          <!-- Actions -->
          <div class="flex items-center justify-end space-x-2">
            <button @click="closeModal" class="btn-secondary">CANCEL</button>
            <button @click="saveScraper" class="btn-primary" :disabled="!form.name || !form.code">
              {{ selectedScraper ? 'UPDATE' : 'CREATE' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Execution Logs Modal -->
    <div
      v-if="showLogsModal"
      class="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4"
      @click.self="showLogsModal = false"
    >
      <div class="bg-dark-100 border border-gray-700 max-w-6xl w-full max-h-[90vh] flex flex-col">
        <div class="bg-dark-100 border-b border-gray-700 p-4 flex items-center justify-between">
          <h2 class="text-lg font-bold text-red-team-500 uppercase">Execution Logs</h2>
          <button @click="showLogsModal = false" class="text-gray-400 hover:text-gray-200">✕</button>
        </div>

        <div class="flex-1 overflow-y-auto p-6">
          <div v-if="executionLogs.length === 0" class="text-center text-gray-400 py-8">
            No logs yet...
          </div>

          <div v-for="log in executionLogs" :key="log.timestamp" class="mb-2">
            <span class="text-xs text-gray-500">{{ log.timestamp }}</span>
            <span class="text-sm text-gray-300 ml-2" :class="{
              'text-red-team-500': log.type === 'stderr',
              'text-green-500': log.type === 'finding'
            }">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'

interface Scraper {
  id: string
  name: string
  description: string
  code: string
  language: string
  cron_expression: string | null
  enabled: boolean
  keywords: string[]
  auto_import: boolean
  next_run_at: number | null
  created_at: number
  updated_at: number
}

interface Template {
  id: string
  name: string
  description: string
  language: string
  keywords: string[]
}

const scrapers = ref<Scraper[]>([])
const templates = ref<Template[]>([])
const loading = ref(true)
const executing = ref<string | null>(null)

const showCreateModal = ref(false)
const selectedScraper = ref<Scraper | null>(null)
const showLogsModal = ref(false)
const executionLogs = ref<any[]>([])

const form = ref({
  name: '',
  description: '',
  code: '',
  language: 'python',
  cron_expression: '',
  enabled: false,
  keywords: [] as string[],
  auto_import: false
})

const keywordsInput = computed({
  get: () => form.value.keywords.join(', '),
  set: (value: string) => {
    form.value.keywords = value.split(',').map(k => k.trim()).filter(k => k.length > 0)
  }
})

async function loadScrapers() {
  try {
    const response = await fetch('/api/scrapers')
    if (response.ok) {
      scrapers.value = await response.json()
    }
  } catch (error) {
    console.error('Failed to load scrapers:', error)
  } finally {
    loading.value = false
  }
}

async function loadTemplates() {
  try {
    const response = await fetch('/api/scrapers/templates/list')
    if (response.ok) {
      templates.value = await response.json()
    }
  } catch (error) {
    console.error('Failed to load templates:', error)
  }
}

async function createFromTemplate(template: Template) {
  try {
    const response = await fetch(`/api/scrapers/templates/${template.id}/code`)
    if (response.ok) {
      const data = await response.json()

      form.value = {
        name: template.name,
        description: template.description,
        code: data.code,
        language: template.language,
        cron_expression: '*/30 * * * *',  // Every 30 minutes
        enabled: false,
        keywords: template.keywords,
        auto_import: false
      }

      showCreateModal.value = true
    }
  } catch (error) {
    console.error('Failed to load template code:', error)
  }
}

async function saveScraper() {
  try {
    const url = selectedScraper.value
      ? `/api/scrapers/${selectedScraper.value.id}`
      : '/api/scrapers'

    const method = selectedScraper.value ? 'PUT' : 'POST'

    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    })

    if (response.ok) {
      await loadScrapers()
      closeModal()
    } else {
      const error = await response.json()
      alert(`Failed to save scraper: ${error.detail}`)
    }
  } catch (error) {
    console.error('Failed to save scraper:', error)
    alert('Failed to save scraper')
  }
}

function selectScraper(scraper: Scraper) {
  selectedScraper.value = scraper
  form.value = {
    name: scraper.name,
    description: scraper.description,
    code: scraper.code,
    language: scraper.language,
    cron_expression: scraper.cron_expression || '',
    enabled: scraper.enabled,
    keywords: scraper.keywords,
    auto_import: scraper.auto_import
  }
}

function closeModal() {
  showCreateModal.value = false
  selectedScraper.value = null
  form.value = {
    name: '',
    description: '',
    code: '',
    language: 'python',
    cron_expression: '',
    enabled: false,
    keywords: [],
    auto_import: false
  }
}

async function executeScraper(scraperId: string) {
  try {
    executing.value = scraperId

    const response = await fetch(`/api/scrapers/${scraperId}/execute`, {
      method: 'POST'
    })

    if (response.ok) {
      const data = await response.json()
      alert(`Execution started: ${data.execution_id}`)
      // TODO: Open WebSocket logs
    } else {
      const error = await response.json()
      alert(`Failed to execute: ${error.detail}`)
    }
  } catch (error) {
    console.error('Failed to execute scraper:', error)
    alert('Failed to execute scraper')
  } finally {
    executing.value = null
  }
}

async function toggleScraper(scraper: Scraper) {
  try {
    const response = await fetch(`/api/scrapers/${scraper.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !scraper.enabled })
    })

    if (response.ok) {
      await loadScrapers()
    }
  } catch (error) {
    console.error('Failed to toggle scraper:', error)
  }
}

async function deleteScraper(scraperId: string) {
  if (!confirm('Are you sure you want to delete this scraper?')) {
    return
  }

  try {
    const response = await fetch(`/api/scrapers/${scraperId}`, {
      method: 'DELETE'
    })

    if (response.ok) {
      await loadScrapers()
    }
  } catch (error) {
    console.error('Failed to delete scraper:', error)
  }
}

function formatNextRun(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString()
}

onMounted(() => {
  loadScrapers()
  loadTemplates()
})
</script>

<style scoped>
.form-checkbox {
  @apply w-4 h-4 bg-dark-200 border-gray-600 text-red-team-500 focus:ring-red-team-500;
}

textarea {
  @apply bg-dark-200 border border-gray-700 text-gray-300 px-3 py-2 focus:outline-none focus:border-red-team-500;
}
</style>
