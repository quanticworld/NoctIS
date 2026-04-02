<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Search Header -->
    <div class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Indexed Search</h2>

      <!-- Search Input -->
      <div class="input-group">
        <label class="label">Global Search (fuzzy search across all fields)</label>
        <input
          v-model="query"
          @keyup.enter="performSearch"
          type="text"
          placeholder="john, john@example.com, +33612345678... (optional - leave empty to use filters only)"
          class="w-full"
        />
      </div>

      <!-- Filters Section -->
      <div class="space-y-4 mb-4 p-4 bg-dark-200 border border-gray-700 rounded">
        <!-- Personal Info Filters -->
        <div class="grid grid-cols-2 gap-4">
          <div class="input-group">
            <label class="label">First Name</label>
            <input v-model="filters.first_name" type="text" placeholder="John, Dupont..." />
          </div>
          <div class="input-group">
            <label class="label">Last Name</label>
            <input v-model="filters.last_name" type="text" placeholder="Doe, Martin..." />
          </div>
        </div>

        <!-- Contact Filters -->
        <div class="grid grid-cols-3 gap-4">
          <div class="input-group">
            <label class="label">Email</label>
            <input v-model="filters.email" type="text" placeholder="john@example.com" />
          </div>
          <div class="input-group">
            <label class="label">Phone</label>
            <input v-model="filters.phone" type="text" placeholder="+336, 0612..." />
          </div>
          <div class="input-group">
            <label class="label">Username</label>
            <input v-model="filters.username" type="text" placeholder="johndoe, admin..." />
          </div>
        </div>

        <!-- Location Filters -->
        <div class="grid grid-cols-3 gap-4">
          <div class="input-group">
            <label class="label">City</label>
            <input v-model="filters.city" type="text" placeholder="Paris" />
          </div>
          <div class="input-group">
            <label class="label">Country</label>
            <input v-model="filters.country" type="text" placeholder="France" />
          </div>
          <div class="input-group">
            <label class="label">ZIP Code</label>
            <input v-model="filters.zip_code" type="text" placeholder="75001" />
          </div>
        </div>

        <!-- Professional Filters -->
        <div class="grid grid-cols-2 gap-4">
          <div class="input-group">
            <label class="label">Company</label>
            <input v-model="filters.company" type="text" placeholder="Acme Corp" />
          </div>
          <div class="input-group">
            <label class="label">Job Title</label>
            <input v-model="filters.job_title" type="text" placeholder="Software Engineer" />
          </div>
        </div>

        <!-- Source Filters -->
        <div class="grid grid-cols-2 gap-4">
          <div class="input-group">
            <label class="label">Breach Name</label>
            <input v-model="filters.breach_name" type="text" placeholder="LinkedIn, Adobe..." />
          </div>
          <div class="input-group">
            <label class="label">Domain</label>
            <input v-model="filters.domain" type="text" placeholder="gmail.com..." />
          </div>
        </div>

        <!-- Clear Filters -->
        <div class="flex justify-end">
          <button
            @click="clearFilters"
            class="btn-secondary text-sm"
          >
            CLEAR FILTERS
          </button>
        </div>
      </div>

      <!-- Quick Options -->
      <div class="grid grid-cols-3 gap-4 mb-4">
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
            <!-- Identifiers -->
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

            <!-- Personal Info -->
            <div v-if="result.first_name || result.last_name">
              <span class="text-gray-500">Name:</span>
              <span class="text-gray-300 ml-2">{{ result.first_name }} {{ result.last_name }}</span>
            </div>
            <div v-if="result.birth_date">
              <span class="text-gray-500">Birth Date:</span>
              <span class="text-gray-300 ml-2">{{ result.birth_date }}</span>
            </div>
            <div v-if="result.gender">
              <span class="text-gray-500">Gender:</span>
              <span class="text-gray-300 ml-2">{{ result.gender }}</span>
            </div>

            <!-- Location -->
            <div v-if="result.address">
              <span class="text-gray-500">Address:</span>
              <span class="text-gray-300 ml-2">{{ result.address }}</span>
            </div>
            <div v-if="result.city || result.country">
              <span class="text-gray-500">Location:</span>
              <span class="text-gray-300 ml-2">{{ result.city }}{{ result.city && result.country ? ', ' : '' }}{{ result.country }}</span>
            </div>
            <div v-if="result.zip_code">
              <span class="text-gray-500">ZIP:</span>
              <span class="text-gray-300 ml-2">{{ result.zip_code }}</span>
            </div>

            <!-- Professional -->
            <div v-if="result.company">
              <span class="text-gray-500">Company:</span>
              <span class="text-gray-300 ml-2">{{ result.company }}</span>
            </div>
            <div v-if="result.job_title">
              <span class="text-gray-500">Job Title:</span>
              <span class="text-gray-300 ml-2">{{ result.job_title }}</span>
            </div>

            <!-- Online Presence -->
            <div v-if="result.social_media">
              <span class="text-gray-500">Social Media:</span>
              <span class="text-gray-300 ml-2 text-xs">{{ result.social_media }}</span>
            </div>
            <div v-if="result.website">
              <span class="text-gray-500">Website:</span>
              <span class="text-gray-300 ml-2 text-xs">{{ result.website }}</span>
            </div>

            <!-- Source -->
            <div v-if="result.breach_name">
              <span class="text-gray-500">Breach:</span>
              <span class="text-red-team-500 ml-2 font-bold">{{ result.breach_name }}</span>
            </div>
            <div v-if="result.domain">
              <span class="text-gray-500">Domain:</span>
              <span class="text-gray-300 ml-2">{{ result.domain }}</span>
            </div>
          </div>
          <div v-if="result.notes" class="mt-2 text-xs text-gray-400">
            <span class="text-gray-500">Notes:</span> {{ truncate(result.notes, 100) }}
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
const perPage = ref(50)
const currentPage = ref(1)
const typoTolerance = ref(true)
const prefixSearch = ref(true)

// Default search fields (all main fields for fuzzy search)
const searchFields = ['email', 'username', 'phone', 'first_name', 'last_name', 'city', 'country', 'company']

// Advanced filters (exact match)
const filters = ref({
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  username: '',
  city: '',
  country: '',
  zip_code: '',
  company: '',
  job_title: '',
  breach_name: '',
  domain: ''
})

const canSearch = computed(() => {
  // Can search if either:
  // 1. Query is present (global fuzzy search)
  // 2. Or at least one filter is filled (exact match search)
  const hasQuery = query.value.trim().length > 0
  const hasFilters = Object.values(filters.value).some(v => v.trim().length > 0)
  return hasQuery || hasFilters
})

async function performSearch() {
  if (!canSearch.value) return

  currentPage.value = 1
  await executeSearch()
}

async function executeSearch() {
  // Build filter_by from advanced filters
  const filterConditions: string[] = []

  // Add all non-empty filters with partial match (using : operator for contains)
  Object.entries(filters.value).forEach(([field, value]) => {
    if (value && value.trim()) {
      filterConditions.push(`${field}:${value.trim()}`)
    }
  })

  const filterBy = filterConditions.length > 0 ? filterConditions.join(' && ') : undefined

  // If no query but filters exist, use wildcard search
  const searchQuery = query.value.trim() || '*'
  // Always use all searchFields for global fuzzy search
  const fieldsToSearch = query.value.trim() ? searchFields : ['email']  // Use any field for wildcard

  await typesenseStore.search({
    query: searchQuery,
    search_fields: fieldsToSearch,
    filter_by: filterBy,
    per_page: perPage.value,
    page: currentPage.value,
    typo_tolerance: typoTolerance.value,
    prefix: prefixSearch.value
  })
}

function clearFilters() {
  Object.keys(filters.value).forEach(key => {
    filters.value[key as keyof typeof filters.value] = ''
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
  clearFilters()
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}
</script>
