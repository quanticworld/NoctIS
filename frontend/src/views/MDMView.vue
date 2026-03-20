<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Initial Loading State -->
    <div v-if="!stats && loading" class="flex flex-col items-center justify-center min-h-screen">
      <div class="relative w-20 h-20 mb-6">
        <div class="absolute inset-0 border-4 border-dark-300 rounded-full"></div>
        <div class="absolute inset-0 border-4 border-red-team-500 rounded-full border-t-transparent animate-spin"></div>
      </div>
      <div class="text-center mb-8">
        <div class="text-xl font-bold text-red-team-500 mb-2">Initializing MDM System</div>
        <div class="text-sm text-gray-400">Loading database collections into memory...</div>
        <div class="text-xs text-gray-500 mt-2">This may take a few minutes for large datasets</div>
      </div>

      <!-- Indeterminate Progress Bar -->
      <div class="w-96 max-w-full">
        <div class="bg-dark-300 h-2 rounded-full overflow-hidden relative">
          <div class="absolute h-full w-1/3 bg-gradient-to-r from-transparent via-red-team-500 to-transparent shimmer-animation">
          </div>
        </div>
        <div class="text-xs text-gray-500 text-center mt-2">
          Please wait while Typesense loads collections...
        </div>
      </div>
    </div>

    <!-- Main Content (only show when stats are loaded) -->
    <div v-else>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-red-team-500 uppercase tracking-wide">Master Data Management</h1>
        <p class="text-sm text-gray-400 mt-1">Entity resolution, deduplication & data quality</p>
      </div>

      <div class="flex gap-2">
        <button
          @click="showRulesModal = true"
          class="btn-secondary"
        >
          CORRELATION RULES
        </button>
        <button
          @click="showConflictsModal = true"
          class="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white font-bold rounded uppercase transition-colors"
        >
          RESOLVE CONFLICTS
        </button>
        <button
          @click="handleClearAll"
          :disabled="loading || deduping"
          class="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold rounded uppercase transition-colors"
        >
          CLEAR ALL DATA
        </button>
        <button
          @click="runDedup"
          :disabled="loading || deduping"
          class="btn-primary"
        >
          {{ deduping ? 'DEDUPLICATING...' : 'RUN DEDUPLICATION' }}
        </button>
      </div>
    </div>

    <!-- Deduplication Progress -->
    <div v-if="deduping || dedupComplete" class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 uppercase mb-4">Deduplication Progress</h2>

      <div v-if="dedupProgress" class="mb-4">
        <div class="flex items-center justify-between text-sm mb-2">
          <span class="text-gray-400">Batch {{ dedupProgress.batch.toLocaleString() }}</span>
          <span class="text-gray-400">
            Processed: {{ dedupProgress.processed.toLocaleString() }} / {{ stats?.silver_records.unlinked.toLocaleString() || '?' }}
            ({{ stats?.silver_records.unlinked ? Math.round((dedupProgress.processed / stats.silver_records.unlinked) * 100) : 0 }}%)
          </span>
        </div>
        <div class="bg-dark-200 h-3 rounded-full overflow-hidden">
          <div
            class="h-full bg-gradient-to-r from-red-team-600 to-red-team-400 transition-all duration-300"
            :style="{ width: `${stats?.silver_records.unlinked ? Math.min(100, (dedupProgress.processed / stats.silver_records.unlinked) * 100) : 0}%` }"
          ></div>
        </div>
        <div class="mt-2 text-xs text-gray-500">
          New Masters: {{ dedupProgress.new_masters.toLocaleString() }} |
          Merged: {{ dedupProgress.merged.toLocaleString() }} |
          Errors: {{ dedupProgress.errors.toLocaleString() }}
        </div>
      </div>

      <div v-if="dedupComplete" class="text-center">
        <div class="text-green-400 font-bold mb-2">✓ Deduplication Complete</div>
        <div class="text-sm text-gray-400">
          Processed {{ dedupComplete.processed.toLocaleString() }} records |
          Created {{ dedupComplete.new_masters.toLocaleString() }} masters |
          Merged {{ dedupComplete.merged.toLocaleString() }} records
        </div>
      </div>
    </div>

    <!-- Breaches Management -->
    <div v-if="breaches.length > 0" class="card p-4 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 uppercase mb-4">Data Sources</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        <div
          v-for="breach in breaches"
          :key="breach.name"
          class="flex items-center justify-between p-3 bg-dark-300 rounded hover:bg-dark-200 transition-colors"
        >
          <div class="flex-1">
            <div class="font-bold text-gray-200">{{ breach.name }}</div>
            <div class="text-xs text-gray-500">{{ breach.count.toLocaleString() }} records</div>
          </div>
          <button
            @click="handleDeleteBreach(breach.name)"
            :disabled="loading"
            class="ml-2 px-3 py-1 text-xs bg-red-600 hover:bg-red-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded uppercase transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
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
      <div class="grid grid-cols-1 gap-4">
        <!-- Row 1: Basic Filters -->
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
        </div>

        <!-- Row 2: Breach Filter -->
        <div class="input-group">
          <label class="label mb-2">
            Breaches (select multiple for AND filter - shows only masters in ALL selected breaches)
          </label>
          <div class="flex flex-wrap gap-2">
            <label
              v-for="breach in breaches"
              :key="breach.name"
              class="flex items-center gap-2 px-3 py-1.5 bg-dark-300 hover:bg-dark-200 rounded cursor-pointer transition-colors"
              :class="{'bg-red-team-600 hover:bg-red-team-700': selectedBreaches.includes(breach.name)}"
            >
              <input
                type="checkbox"
                :value="breach.name"
                v-model="selectedBreaches"
                class="w-4 h-4 cursor-pointer"
              />
              <span class="text-sm text-gray-300">
                {{ breach.name }}
                <span class="text-xs text-gray-500 ml-1">({{ breach.count.toLocaleString() }})</span>
              </span>
            </label>
          </div>
        </div>

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

      <div v-if="loading" class="p-8">
        <div class="flex flex-col items-center gap-4">
          <!-- Spinner -->
          <div class="relative w-16 h-16">
            <div class="absolute inset-0 border-4 border-dark-300 rounded-full"></div>
            <div class="absolute inset-0 border-4 border-red-team-500 rounded-full border-t-transparent animate-spin"></div>
          </div>

          <!-- Loading text -->
          <div class="text-gray-400 text-center">
            <div class="text-lg font-bold mb-1">Loading masters...</div>
            <div class="text-sm text-gray-500 mb-4">
              {{ stats ? `Fetching from ${stats.master_records.total.toLocaleString()} total records` : 'Querying database...' }}
            </div>

            <!-- Progress bar -->
            <div class="w-96 max-w-full mx-auto">
              <div class="bg-dark-300 h-2 rounded-full overflow-hidden relative">
                <div class="absolute h-full w-1/3 bg-gradient-to-r from-transparent via-red-team-400 to-transparent slide-animation">
                </div>
              </div>
            </div>
          </div>
        </div>
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

    <!-- Master Detail Modal -->
    <MasterDetailModal
      v-if="showDetailModal"
      :master-id="selectedMasterId"
      @close="showDetailModal = false"
      @refresh="loadMasters"
    />

    <!-- Correlation Rules Modal -->
    <CorrelationRulesModal
      v-if="showRulesModal"
      @close="showRulesModal = false"
      @save="onRulesSaved"
    />

    <!-- Conflict Resolution Modal -->
    <ConflictResolutionModal
      :isOpen="showConflictsModal"
      @close="showConflictsModal = false"
      @resolved="onConflictsResolved"
    />
    </div>
    <!-- End Main Content -->
  </div>
</template>

<style scoped>
@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(300%);
  }
}

@keyframes loading-slide {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(300%);
  }
}

.shimmer-animation {
  animation: shimmer 2s ease-in-out infinite;
}

.slide-animation {
  animation: loading-slide 1.5s ease-in-out infinite;
}
</style>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useMDM } from '@/composables/useMDM'
import { useDeduplication } from '@/composables/useDeduplication'
import MasterDetailModal from '@/components/MasterDetailModal.vue'
import CorrelationRulesModal from '@/components/CorrelationRulesModal.vue'
import ConflictResolutionModal from '@/components/ConflictResolutionModal.vue'

const {
  stats,
  breaches,
  loading,
  error,
  statusFilter,
  minConfidence,
  minSources,
  selectedBreaches,
  filteredMasters,
  fetchMasters,
  fetchStats,
  fetchBreaches,
  mergeMasters,
  promoteToGolden: promoteToGoldenAction,
  deleteBreach,
  clearAllData
} = useMDM()

const {
  isRunning: deduping,
  progress: dedupProgress,
  complete: dedupComplete,
  error: dedupError,
  startDeduplication,
  reset: resetDedup
} = useDeduplication()

const selectedMasters = ref<string[]>([])
const showDetailModal = ref(false)
const selectedMasterId = ref<string>('')
const showRulesModal = ref(false)
const showConflictsModal = ref(false)

onMounted(async () => {
  await Promise.all([
    loadMasters(),
    fetchStats(),
    fetchBreaches()
  ])
})

async function loadMasters() {
  await fetchMasters(1, 100)
}

async function runDedup() {
  resetDedup()
  await startDeduplication(250) // No batch limit - process all records
}

async function handleDeleteBreach(breachName: string) {
  const breach = breaches.value.find(b => b.name === breachName)
  const confirmed = confirm(
    `⚠️ Delete source: "${breachName}"?\n\n` +
    `This will:\n` +
    `- Delete ${breach?.count.toLocaleString() || '?'} silver records\n` +
    `- Remove this breach from all masters\n` +
    `- Delete masters that only had this breach\n\n` +
    `Type the breach name to confirm.`
  )

  if (!confirmed) return

  const confirmText = prompt(`Type "${breachName}" to confirm:`)
  if (confirmText !== breachName) {
    alert('Cancelled - name did not match')
    return
  }

  const result = await deleteBreach(breachName)
  if (result) {
    alert(
      `✅ Breach "${breachName}" deleted!\n\n` +
      `- Silver deleted: ${result.deleted_silver.toLocaleString()}\n` +
      `- Masters deleted: ${result.deleted_masters.toLocaleString()}\n` +
      `- Masters updated: ${result.updated_masters.toLocaleString()}`
    )
    await loadMasters()
  } else {
    alert('❌ Failed to delete breach. Check console for errors.')
  }
}

async function handleClearAll() {
  const confirmed = confirm(
    `⚠️ WARNING: This will DELETE ALL DATA!\n\n` +
    `- Silver records: ${stats.value?.silver_records.total.toLocaleString() || '?'}\n` +
    `- Master records: ${stats.value?.master_records.total.toLocaleString() || '?'}\n\n` +
    `This action CANNOT be undone!\n\n` +
    `Type 'DELETE' in the next prompt to confirm.`
  )

  if (!confirmed) return

  const confirmText = prompt('Type DELETE to confirm:')
  if (confirmText !== 'DELETE') {
    alert('Cancelled - text did not match')
    return
  }

  const success = await clearAllData()
  if (success) {
    alert('✅ All data cleared successfully!\n\nYou can now import a fresh dataset.')
    await Promise.all([
      loadMasters(),
      fetchStats(),
      fetchBreaches()
    ])
  } else {
    alert('❌ Failed to clear data. Check console for errors.')
  }
}

// Watch for deduplication completion
watch(dedupComplete, async (result) => {
  if (result) {
    alert(`Deduplication completed!\nProcessed: ${result.processed}\nNew Masters: ${result.new_masters}\nMerged: ${result.merged}\nErrors: ${result.errors}`)
    await Promise.all([
      loadMasters(),
      fetchStats()
    ])
  }
})

watch(dedupError, (err) => {
  if (err) {
    alert(`Deduplication failed: ${err}`)
  }
})

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

function onRulesSaved() {
  // Rules saved, could show notification or refresh if needed
  console.log('Correlation rules updated')
}

function onConflictsResolved() {
  // Conflicts resolved, refresh masters and stats
  loadMasters()
  fetchStats()
}

// Auto-refresh when filters change
watch([statusFilter, minConfidence, minSources, selectedBreaches], () => {
  // Filters are applied server-side, no need to reload automatically
  // User must click "APPLY FILTERS" button
})
</script>
