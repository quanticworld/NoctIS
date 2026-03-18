<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Search Header -->
    <div class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Indexed Search</h2>

      <!-- Search Input -->
      <div class="input-group">
        <label class="label">Search Query</label>
        <input
          v-model="query"
          @keyup.enter="performSearch"
          type="text"
          placeholder="email, username, phone, IP address..."
          class="w-full"
        />
      </div>

      <!-- Search Fields Selection -->
      <div class="input-group">
        <label class="label">Search In</label>
        <div class="grid grid-cols-4 gap-2">
          <label v-for="field in availableFields" :key="field" class="flex items-center space-x-2">
            <input
              type="checkbox"
              :value="field"
              v-model="selectedFields"
              class="form-checkbox text-red-team-500"
            />
            <span class="text-sm text-gray-300">{{ field }}</span>
          </label>
        </div>
      </div>

      <!-- Filters -->
      <div class="grid grid-cols-3 gap-4">
        <div class="input-group">
          <label class="label">Breach Name</label>
          <input v-model="breachFilter" type="text" placeholder="LinkedIn, Adobe..." />
        </div>
        <div class="input-group">
          <label class="label">Domain</label>
          <input v-model="domainFilter" type="text" placeholder="gmail.com..." />
        </div>
        <div class="input-group">
          <label class="label">Results Per Page</label>
          <select v-model.number="perPage" class="w-full">
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
          </select>
        </div>
      </div>

      <!-- Search Options -->
      <div class="flex items-center space-x-4 mb-4">
        <label class="flex items-center space-x-2">
          <input type="checkbox" v-model="typoTolerance" class="form-checkbox text-red-team-500" />
          <span class="text-sm text-gray-300">Typo Tolerance</span>
        </label>
        <label class="flex items-center space-x-2">
          <input type="checkbox" v-model="prefixSearch" class="form-checkbox text-red-team-500" />
          <span class="text-sm text-gray-300">Prefix Search</span>
        </label>
      </div>

      <!-- Search Button -->
      <div class="flex space-x-3">
        <button
          @click="performSearch"
          :disabled="!canSearch"
          class="btn-primary flex-1"
        >
          SEARCH
        </button>
        <button
          v-if="typesenseStore.results.length > 0"
          @click="clearResults"
          class="btn-secondary"
        >
          CLEAR
        </button>
      </div>
    </div>

    <!-- Results Stats -->
    <div v-if="typesenseStore.searchPerformed" class="card p-4 mb-6">
      <div class="flex items-center justify-between text-sm">
        <div class="text-gray-400">
          Found <span class="text-red-team-500 font-bold">{{ typesenseStore.totalResults.toLocaleString() }}</span> results
          <span v-if="typesenseStore.searchTimeMs"> in {{ typesenseStore.searchTimeMs }}ms</span>
        </div>
        <div v-if="typesenseStore.totalResults > perPage" class="text-gray-400">
          Page {{ currentPage }} of {{ Math.ceil(typesenseStore.totalResults / perPage) }}
        </div>
      </div>
    </div>

    <!-- Error Message -->
    <div v-if="typesenseStore.error" class="card p-4 mb-6 border-red-team-500">
      <div class="text-red-team-500">ERROR: {{ typesenseStore.error }}</div>
    </div>

    <!-- Results -->
    <div class="card p-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-bold text-red-team-500 uppercase tracking-wide">
          Results ({{ typesenseStore.results.length }})
        </h2>
      </div>

      <!-- Results List -->
      <div v-if="typesenseStore.results.length > 0" class="space-y-3 max-h-[700px] overflow-y-auto">
        <div
          v-for="(result, index) in typesenseStore.results"
          :key="index"
          class="bg-dark-200 border border-gray-700 p-4 hover:border-red-team-500 transition-colors"
        >
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div v-if="result.email">
              <span class="text-gray-500">Email:</span>
              <span class="text-gray-300 ml-2 font-mono">{{ result.email }}</span>
            </div>
            <div v-if="result.username">
              <span class="text-gray-500">Username:</span>
              <span class="text-gray-300 ml-2 font-mono">{{ result.username }}</span>
            </div>
            <div v-if="result.password">
              <span class="text-gray-500">Password:</span>
              <span class="text-gray-300 ml-2 font-mono">{{ result.password }}</span>
            </div>
            <div v-if="result.password_hash">
              <span class="text-gray-500">Hash:</span>
              <span class="text-gray-300 ml-2 font-mono text-xs">{{ truncate(result.password_hash, 40) }}</span>
            </div>
            <div v-if="result.phone">
              <span class="text-gray-500">Phone:</span>
              <span class="text-gray-300 ml-2 font-mono">{{ result.phone }}</span>
            </div>
            <div v-if="result.ip_address">
              <span class="text-gray-500">IP:</span>
              <span class="text-gray-300 ml-2 font-mono">{{ result.ip_address }}</span>
            </div>
            <div v-if="result.name">
              <span class="text-gray-500">Name:</span>
              <span class="text-gray-300 ml-2">{{ result.name }}</span>
            </div>
            <div v-if="result.breach_name">
              <span class="text-gray-500">Breach:</span>
              <span class="text-red-team-500 ml-2 font-bold">{{ result.breach_name }}</span>
            </div>
          </div>
          <div v-if="result.source_file" class="mt-2 text-xs text-gray-500 truncate">
            Source: {{ result.source_file }}
          </div>
        </div>
      </div>

      <div v-else-if="typesenseStore.searchPerformed" class="text-center text-gray-500 py-12">
        No results found for your query.
      </div>

      <div v-else class="text-center text-gray-500 py-12">
        Enter a search query and click "Search" to find indexed data.
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="typesenseStore.totalResults > perPage" class="flex justify-center space-x-2 mt-6">
      <button
        @click="goToPage(currentPage - 1)"
        :disabled="currentPage === 1"
        class="btn-secondary"
      >
        PREV
      </button>
      <div class="flex items-center px-4 text-gray-400">
        Page {{ currentPage }} of {{ Math.ceil(typesenseStore.totalResults / perPage) }}
      </div>
      <button
        @click="goToPage(currentPage + 1)"
        :disabled="currentPage >= Math.ceil(typesenseStore.totalResults / perPage)"
        class="btn-secondary"
      >
        NEXT
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTypesenseStore } from '@/stores/typesense'

const typesenseStore = useTypesenseStore()

// Search state
const query = ref('')
const selectedFields = ref(['email', 'username', 'phone', 'ip_address'])
const breachFilter = ref('')
const domainFilter = ref('')
const perPage = ref(50)
const currentPage = ref(1)
const typoTolerance = ref(true)
const prefixSearch = ref(true)

const availableFields = [
  'email',
  'username',
  'password',
  'password_hash',
  'phone',
  'ip_address',
  'name',
  'address'
]

const canSearch = computed(() => {
  return query.value.trim().length > 0 && selectedFields.value.length > 0
})

async function performSearch() {
  if (!canSearch.value) return

  currentPage.value = 1
  await executeSearch()
}

async function executeSearch() {
  let filterBy = ''
  const filters: string[] = []

  if (breachFilter.value.trim()) {
    filters.push(`breach_name:=${breachFilter.value.trim()}`)
  }
  if (domainFilter.value.trim()) {
    filters.push(`domain:=${domainFilter.value.trim()}`)
  }

  if (filters.length > 0) {
    filterBy = filters.join(' && ')
  }

  await typesenseStore.search({
    query: query.value,
    search_fields: selectedFields.value,
    filter_by: filterBy || undefined,
    per_page: perPage.value,
    page: currentPage.value,
    typo_tolerance: typoTolerance.value,
    prefix: prefixSearch.value
  })
}

async function goToPage(page: number) {
  currentPage.value = page
  await executeSearch()
}

function clearResults() {
  typesenseStore.clearResults()
  query.value = ''
  currentPage.value = 1
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}
</script>
