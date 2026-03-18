<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-red-team-500 uppercase tracking-wide">Master Data Management</h1>
        <p class="text-sm text-gray-400 mt-1">Entity resolution, deduplication & data quality</p>
      </div>

      <button
        @click="runDedup"
        :disabled="loading || deduping"
        class="btn-primary"
      >
        {{ deduping ? 'DEDUPLICATING...' : 'RUN DEDUPLICATION' }}
      </button>
    </div>

    <!-- Stats Dashboard -->
    <div v-if="stats" class="grid grid-cols-4 gap-4 mb-6">
      <!-- Silver Records -->
      <div class="card p-4 border-l-4 border-blue-500">
        <div class="text-sm text-gray-500 uppercase mb-1">Silver Records</div>
        <div class="text-3xl font-bold text-gray-200">{{ stats.silver_records.total.toLocaleString() }}</div>
        <div class="text-xs text-gray-400 mt-1">
          {{ stats.silver_records.unlinked.toLocaleString() }} unlinked
        </div>
      </div>

      <!-- Master Records -->
      <div class="card p-4 border-l-4 border-purple-500">
        <div class="text-sm text-gray-500 uppercase mb-1">Master Records</div>
        <div class="text-3xl font-bold text-gray-200">{{ stats.master_records.total.toLocaleString() }}</div>
        <div class="text-xs text-gray-400 mt-1">
          {{ ((stats.master_records.total / stats.silver_records.total) * 100).toFixed(1) }}% consolidation
        </div>
      </div>

      <!-- Golden Records -->
      <div class="card p-4 border-l-4 border-yellow-500">
        <div class="text-sm text-gray-500 uppercase mb-1">Golden Records</div>
        <div class="text-3xl font-bold text-yellow-400">{{ stats.master_records.golden.toLocaleString() }}</div>
        <div class="text-xs text-gray-400 mt-1">
          {{ ((stats.master_records.golden / stats.master_records.total) * 100).toFixed(1) }}% validated
        </div>
      </div>

      <!-- Silver Status -->
      <div class="card p-4 border-l-4 border-gray-500">
        <div class="text-sm text-gray-500 uppercase mb-1">Silver Status</div>
        <div class="text-3xl font-bold text-gray-200">{{ stats.master_records.silver.toLocaleString() }}</div>
        <div class="text-xs text-gray-400 mt-1">
          Pending validation
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="card p-4 mb-6">
      <div class="flex items-center gap-4">
        <!-- Status Filter -->
        <div class="input-group">
          <label class="label">Status</label>
          <select v-model="statusFilter" class="w-32">
            <option value="all">All</option>
            <option value="silver">Silver</option>
            <option value="golden">Golden</option>
          </select>
        </div>

        <!-- Confidence Filter -->
        <div class="input-group">
          <label class="label">Min Confidence</label>
          <input
            v-model.number="minConfidence"
            type="number"
            min="0"
            max="100"
            step="10"
            class="w-24"
          />
        </div>

        <!-- Sources Filter -->
        <div class="input-group">
          <label class="label">Min Sources</label>
          <input
            v-model.number="minSources"
            type="number"
            min="1"
            step="1"
            class="w-24"
          />
        </div>

        <button @click="loadMasters" class="btn-secondary mt-5">
          APPLY FILTERS
        </button>

        <!-- Selection Actions -->
        <div v-if="selectedMasters.length > 1" class="flex items-center gap-2 mt-5 ml-auto">
          <span class="text-sm text-gray-400">{{ selectedMasters.length }} selected</span>
          <button @click="mergeSelected" class="btn-primary">
            MERGE SELECTED
          </button>
        </div>
      </div>
    </div>

    <!-- Masters List -->
    <div class="card">
      <div class="p-4 border-b border-gray-700">
        <h2 class="text-lg font-bold text-red-team-500 uppercase">Master Records</h2>
        <p class="text-sm text-gray-400 mt-1">{{ filteredMasters.length }} records</p>
      </div>

      <div v-if="loading" class="p-8 text-center text-gray-400">
        Loading masters...
      </div>

      <div v-else-if="error" class="p-8 text-center text-red-team-500">
        ERROR: {{ error }}
      </div>

      <div v-else-if="filteredMasters.length === 0" class="p-8 text-center text-gray-400">
        No masters found. Try adjusting filters or run deduplication.
      </div>

      <div v-else class="divide-y divide-gray-700">
        <div
          v-for="master in filteredMasters"
          :key="master.id"
          class="p-4 hover:bg-dark-200 transition-colors cursor-pointer"
          @click="viewMaster(master.id)"
        >
          <div class="flex items-start justify-between">
            <!-- Master Info -->
            <div class="flex-1">
              <div class="flex items-center gap-3 mb-2">
                <!-- Checkbox -->
                <input
                  type="checkbox"
                  :checked="selectedMasters.includes(master.id)"
                  @click.stop="toggleSelection(master.id)"
                  class="w-4 h-4"
                />

                <!-- Status Badge -->
                <span
                  class="px-2 py-1 text-xs font-bold uppercase rounded"
                  :class="{
                    'bg-yellow-500 text-dark-100': master.status === 'golden',
                    'bg-gray-600 text-gray-300': master.status === 'silver'
                  }"
                >
                  {{ master.status }}
                </span>

                <!-- Confidence Score -->
                <div class="flex items-center gap-1">
                  <div class="text-xs text-gray-500">Confidence:</div>
                  <div
                    class="text-sm font-bold"
                    :class="{
                      'text-green-400': master.confidence_score >= 90,
                      'text-yellow-400': master.confidence_score >= 70 && master.confidence_score < 90,
                      'text-orange-400': master.confidence_score >= 50 && master.confidence_score < 70,
                      'text-red-400': master.confidence_score < 50
                    }"
                  >
                    {{ master.confidence_score.toFixed(1) }}%
                  </div>
                </div>

                <!-- Sources Count -->
                <div class="flex items-center gap-1">
                  <div class="text-xs text-gray-500">Sources:</div>
                  <div class="text-sm font-bold text-gray-300">{{ master.source_count }}</div>
                </div>
              </div>

              <!-- Identity -->
              <div class="grid grid-cols-3 gap-4 text-sm mb-2">
                <div v-if="master.full_name || (master.first_name && master.last_name)">
                  <span class="text-gray-500">Name:</span>
                  <span class="text-gray-300 ml-2 font-mono">
                    {{ master.full_name || `${master.first_name} ${master.last_name}` }}
                  </span>
                </div>

                <div v-if="master.email">
                  <span class="text-gray-500">Email:</span>
                  <span class="text-gray-300 ml-2 font-mono">{{ master.email }}</span>
                </div>

                <div v-if="master.phone">
                  <span class="text-gray-500">Phone:</span>
                  <span class="text-gray-300 ml-2 font-mono">{{ master.phone }}</span>
                </div>
              </div>

              <!-- Breaches -->
              <div class="flex items-center gap-2 text-xs">
                <span class="text-gray-500">Breaches:</span>
                <div class="flex gap-1 flex-wrap">
                  <span
                    v-for="breach in master.breach_names.slice(0, 5)"
                    :key="breach"
                    class="px-2 py-0.5 bg-dark-300 text-gray-400 rounded"
                  >
                    {{ breach }}
                  </span>
                  <span v-if="master.breach_names.length > 5" class="text-gray-500">
                    +{{ master.breach_names.length - 5 }} more
                  </span>
                </div>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex gap-2">
              <button
                v-if="master.status === 'silver'"
                @click.stop="promoteToGolden(master.id)"
                class="px-3 py-1 text-xs bg-yellow-600 hover:bg-yellow-700 text-white rounded uppercase"
              >
                Promote
              </button>
              <button
                @click.stop="viewMaster(master.id)"
                class="px-3 py-1 text-xs bg-red-team-600 hover:bg-red-team-700 text-white rounded uppercase"
              >
                View
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Master Detail Modal (will be implemented next) -->
    <MasterDetailModal
      v-if="showDetailModal"
      :master-id="selectedMasterId"
      @close="showDetailModal = false"
      @refresh="loadMasters"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useMDM } from '@/composables/useMDM'
import MasterDetailModal from '@/components/MasterDetailModal.vue'

const {
  masters,
  stats,
  loading,
  error,
  statusFilter,
  minConfidence,
  minSources,
  filteredMasters,
  fetchMasters,
  fetchStats,
  runDeduplication,
  mergeMasters,
  promoteToGolden: promoteToGoldenAction
} = useMDM()

const deduping = ref(false)
const selectedMasters = ref<string[]>([])
const showDetailModal = ref(false)
const selectedMasterId = ref<string | null>(null)

onMounted(async () => {
  await Promise.all([
    loadMasters(),
    fetchStats()
  ])
})

async function loadMasters() {
  await fetchMasters(1, 100)
}

async function runDedup() {
  deduping.value = true
  try {
    const result = await runDeduplication(500)
    if (result) {
      alert(`Deduplication completed!\nProcessed: ${result.processed}\nNew Masters: ${result.new_masters}\nMerged: ${result.merged}\nErrors: ${result.errors}`)
      await Promise.all([
        loadMasters(),
        fetchStats()
      ])
    }
  } finally {
    deduping.value = false
  }
}

function toggleSelection(masterId: string) {
  const index = selectedMasters.value.indexOf(masterId)
  if (index >= 0) {
    selectedMasters.value.splice(index, 1)
  } else {
    selectedMasters.value.push(masterId)
  }
}

async function mergeSelected() {
  if (selectedMasters.value.length < 2) {
    alert('Select at least 2 masters to merge')
    return
  }

  if (!confirm(`Merge ${selectedMasters.value.length} masters?`)) {
    return
  }

  const success = await mergeMasters(selectedMasters.value)
  if (success) {
    alert('Masters merged successfully!')
    selectedMasters.value = []
    await fetchStats()
  }
}

async function promoteToGolden(masterId: string) {
  if (!confirm('Promote this master to Golden status?')) {
    return
  }

  const success = await promoteToGoldenAction(masterId)
  if (success) {
    alert('Master promoted to Golden!')
    await loadMasters()
    await fetchStats()
  }
}

function viewMaster(masterId: string) {
  selectedMasterId.value = masterId
  showDetailModal.value = true
}

// Auto-refresh when filters change
watch([statusFilter, minConfidence, minSources], () => {
  // Filters are applied client-side via computed
})
</script>
