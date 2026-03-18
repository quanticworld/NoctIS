<template>
  <div class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4" @click.self="close">
    <div class="bg-dark-100 border border-gray-700 rounded-lg max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
      <!-- Header -->
      <div class="p-6 border-b border-gray-700 flex items-center justify-between">
        <div>
          <h2 class="text-xl font-bold text-red-team-500 uppercase">Master Record Detail</h2>
          <p v-if="master" class="text-sm text-gray-400 mt-1">ID: {{ master.id }}</p>
        </div>
        <button @click="close" class="text-gray-400 hover:text-white text-2xl">&times;</button>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex-1 flex items-center justify-center">
        <div class="text-gray-400">Loading master details...</div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex-1 flex items-center justify-center">
        <div class="text-red-team-500">ERROR: {{ error }}</div>
      </div>

      <!-- Content -->
      <div v-else-if="master" class="flex-1 overflow-y-auto p-6">
        <!-- Master Info -->
        <div class="card p-6 mb-6">
          <div class="flex items-start justify-between mb-4">
            <div>
              <h3 class="text-lg font-bold text-gray-200 uppercase">Master Information</h3>
            </div>
            <div class="flex gap-2">
              <span
                class="px-3 py-1 text-sm font-bold uppercase rounded"
                :class="{
                  'bg-yellow-500 text-dark-100': master.status === 'golden',
                  'bg-gray-600 text-gray-300': master.status === 'silver'
                }"
              >
                {{ master.status }}
              </span>
              <span class="px-3 py-1 text-sm bg-dark-300 text-gray-300 rounded">
                Confidence: {{ master.confidence_score.toFixed(1) }}%
              </span>
            </div>
          </div>

          <!-- Identity Fields -->
          <div class="grid grid-cols-2 gap-4 mb-4">
            <div v-if="master.email" class="input-group">
              <label class="label">Email</label>
              <input :value="master.email" readonly class="bg-dark-300" />
            </div>

            <div v-if="master.phone" class="input-group">
              <label class="label">Phone</label>
              <input :value="master.phone" readonly class="bg-dark-300" />
            </div>

            <div v-if="master.full_name" class="input-group">
              <label class="label">Full Name</label>
              <input :value="master.full_name" readonly class="bg-dark-300" />
            </div>

            <div v-if="master.first_name" class="input-group">
              <label class="label">First Name</label>
              <input :value="master.first_name" readonly class="bg-dark-300" />
            </div>

            <div v-if="master.last_name" class="input-group">
              <label class="label">Last Name</label>
              <input :value="master.last_name" readonly class="bg-dark-300" />
            </div>

            <div v-if="master.gender" class="input-group">
              <label class="label">Gender</label>
              <input :value="master.gender" readonly class="bg-dark-300" />
            </div>

            <div v-if="master.birth_date" class="input-group">
              <label class="label">Birth Date</label>
              <input :value="master.birth_date" readonly class="bg-dark-300" />
            </div>

            <div v-if="master.city" class="input-group">
              <label class="label">City</label>
              <input :value="master.city" readonly class="bg-dark-300" />
            </div>

            <div v-if="master.country" class="input-group">
              <label class="label">Country</label>
              <input :value="master.country" readonly class="bg-dark-300" />
            </div>

            <div v-if="master.company" class="input-group">
              <label class="label">Company</label>
              <input :value="master.company" readonly class="bg-dark-300" />
            </div>
          </div>

          <!-- Breaches -->
          <div class="mb-4">
            <label class="label">Breaches ({{ master.breach_names.length }})</label>
            <div class="flex gap-2 flex-wrap">
              <span
                v-for="breach in master.breach_names"
                :key="breach"
                class="px-2 py-1 text-xs bg-dark-300 text-gray-300 rounded"
              >
                {{ breach }}
              </span>
            </div>
          </div>

          <!-- Passwords -->
          <div v-if="master.passwords && master.passwords.length > 0" class="mb-4">
            <label class="label">Passwords Found ({{ master.passwords.length }})</label>
            <div class="bg-dark-300 p-3 rounded font-mono text-sm text-gray-300 max-h-32 overflow-y-auto">
              <div v-for="(pwd, idx) in master.passwords" :key="idx">{{ pwd }}</div>
            </div>
          </div>

          <!-- Timestamps -->
          <div class="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span class="text-gray-500">Created:</span>
              <span class="text-gray-300 ml-2">{{ formatDate(master.created_at) }}</span>
            </div>
            <div>
              <span class="text-gray-500">Updated:</span>
              <span class="text-gray-300 ml-2">{{ formatDate(master.updated_at) }}</span>
            </div>
            <div>
              <span class="text-gray-500">Sources:</span>
              <span class="text-gray-300 ml-2 font-bold">{{ master.source_count }}</span>
            </div>
          </div>
        </div>

        <!-- Silver Sources -->
        <div class="card p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold text-gray-200 uppercase">Silver Sources ({{ sources.length }})</h3>
            <button
              v-if="selectedSources.length > 0"
              @click="splitSelected"
              class="btn-secondary text-sm"
            >
              SPLIT {{ selectedSources.length }} SOURCES
            </button>
          </div>

          <div v-if="sources.length === 0" class="text-center text-gray-400 py-8">
            No sources found
          </div>

          <div v-else class="space-y-3">
            <div
              v-for="source in sources"
              :key="source.id"
              class="bg-dark-200 border border-gray-700 p-4 rounded hover:border-red-team-500 transition-colors"
            >
              <div class="flex items-start gap-3">
                <!-- Checkbox -->
                <input
                  type="checkbox"
                  :checked="selectedSources.includes(source.id)"
                  @change="toggleSourceSelection(source.id)"
                  class="mt-1"
                />

                <!-- Source Info -->
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-2">
                    <span class="text-xs font-bold text-red-team-500">{{ source.breach_name }}</span>
                    <span class="text-xs text-gray-500">•</span>
                    <span class="text-xs text-gray-500">{{ source.source_file }}</span>
                    <span class="text-xs text-gray-500">•</span>
                    <span class="text-xs text-gray-500">{{ formatDate(source.imported_at) }}</span>
                  </div>

                  <div class="grid grid-cols-3 gap-2 text-sm">
                    <div v-if="source.email">
                      <span class="text-gray-500">Email:</span>
                      <span class="text-gray-300 ml-1 font-mono text-xs">{{ source.email }}</span>
                    </div>
                    <div v-if="source.phone">
                      <span class="text-gray-500">Phone:</span>
                      <span class="text-gray-300 ml-1 font-mono text-xs">{{ source.phone }}</span>
                    </div>
                    <div v-if="source.full_name || (source.first_name && source.last_name)">
                      <span class="text-gray-500">Name:</span>
                      <span class="text-gray-300 ml-1 font-mono text-xs">
                        {{ source.full_name || `${source.first_name} ${source.last_name}` }}
                      </span>
                    </div>
                  </div>

                  <div v-if="source.password" class="mt-2 text-xs">
                    <span class="text-gray-500">Password:</span>
                    <span class="text-gray-300 ml-1 font-mono">{{ source.password }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer Actions -->
      <div v-if="master" class="p-6 border-t border-gray-700 flex justify-between">
        <div class="flex gap-2">
          <button
            v-if="master.status === 'silver'"
            @click="promote"
            class="btn-primary"
          >
            PROMOTE TO GOLDEN
          </button>
        </div>
        <button @click="close" class="btn-secondary">
          CLOSE
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useMDM } from '@/composables/useMDM'

const props = defineProps<{
  masterId: string
}>()

const emit = defineEmits<{
  close: []
  refresh: []
}>()

const {
  currentMaster,
  loading,
  error,
  fetchMaster,
  promoteToGolden,
  splitMaster
} = useMDM()

const selectedSources = ref<string[]>([])

const master = computed(() => currentMaster.value?.master)
const sources = computed(() => currentMaster.value?.sources || [])

onMounted(async () => {
  await fetchMaster(props.masterId)
})

function close() {
  emit('close')
}

function formatDate(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString()
}

function toggleSourceSelection(sourceId: string) {
  const index = selectedSources.value.indexOf(sourceId)
  if (index >= 0) {
    selectedSources.value.splice(index, 1)
  } else {
    selectedSources.value.push(sourceId)
  }
}

async function splitSelected() {
  if (selectedSources.value.length === 0) return

  if (!confirm(`Split ${selectedSources.value.length} sources from this master?`)) {
    return
  }

  const success = await splitMaster(props.masterId, selectedSources.value)
  if (success) {
    alert('Sources split successfully!')
    selectedSources.value = []
    emit('refresh')
  }
}

async function promote() {
  if (!confirm('Promote this master to Golden status?')) {
    return
  }

  const success = await promoteToGolden(props.masterId, 'manual')
  if (success) {
    alert('Master promoted to Golden!')
    emit('refresh')
    emit('close')
  }
}
</script>
