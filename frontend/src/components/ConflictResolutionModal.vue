<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-75 p-4"
    @click.self="closeModal"
  >
    <div class="card w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
      <!-- Header -->
      <div class="p-6 border-b border-dark-200">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-2xl font-bold text-red-team-500 uppercase">Conflict Resolution</h2>
            <p class="text-sm text-gray-500 mt-1">
              {{ conflicts.length }} conflict(s) requiring manual resolution
            </p>
          </div>
          <button
            @click="closeModal"
            class="px-4 py-2 bg-dark-200 hover:bg-dark-100 text-gray-300 rounded uppercase transition-colors"
          >
            Close
          </button>
        </div>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-6">
        <div v-if="loading" class="text-center py-12">
          <div class="text-gray-500">Loading conflicts...</div>
        </div>

        <div v-else-if="conflicts.length === 0" class="text-center py-12">
          <div class="text-2xl mb-2">✅</div>
          <div class="text-gray-500">No pending conflicts</div>
        </div>

        <div v-else class="space-y-6">
          <div
            v-for="conflict in conflicts"
            :key="conflict.id"
            class="card p-4 border-l-4 border-yellow-500"
          >
            <!-- Conflict Header -->
            <div class="flex items-center justify-between mb-4">
              <div>
                <div class="text-sm text-gray-500 uppercase tracking-wide">Field</div>
                <div class="text-lg font-bold text-gray-200">{{ conflict.field_name }}</div>
              </div>
              <div class="text-xs text-gray-600">
                Master: {{ conflict.master_id.substring(0, 8) }}...
              </div>
            </div>

            <!-- Conflict Options -->
            <div class="grid grid-cols-2 gap-4 mb-4">
              <!-- Option 1: Existing Value -->
              <div
                class="p-4 rounded border-2 transition-all cursor-pointer"
                :class="{
                  'border-green-500 bg-green-900 bg-opacity-20': selectedChoices[conflict.id] === conflict.existing_value,
                  'border-dark-200 hover:border-dark-100': selectedChoices[conflict.id] !== conflict.existing_value
                }"
                @click="selectChoice(conflict.id, conflict.existing_value)"
              >
                <div class="text-xs text-gray-500 uppercase mb-2">
                  Source: {{ conflict.existing_source }}
                </div>
                <div class="text-gray-200 font-mono break-all">
                  {{ conflict.existing_value }}
                </div>
              </div>

              <!-- Option 2: New Value -->
              <div
                class="p-4 rounded border-2 transition-all cursor-pointer"
                :class="{
                  'border-green-500 bg-green-900 bg-opacity-20': selectedChoices[conflict.id] === conflict.new_value,
                  'border-dark-200 hover:border-dark-100': selectedChoices[conflict.id] !== conflict.new_value
                }"
                @click="selectChoice(conflict.id, conflict.new_value)"
              >
                <div class="text-xs text-gray-500 uppercase mb-2">
                  Source: {{ conflict.new_source }}
                </div>
                <div class="text-gray-200 font-mono break-all">
                  {{ conflict.new_value }}
                </div>
              </div>
            </div>

            <!-- Resolve Button -->
            <div class="flex justify-end">
              <button
                @click="handleResolve(conflict)"
                :disabled="!selectedChoices[conflict.id]"
                class="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded uppercase transition-colors text-sm font-bold"
              >
                Resolve
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div v-if="conflicts.length > 0" class="p-4 border-t border-dark-200 bg-dark-300">
        <div class="flex items-center justify-between">
          <div class="text-sm text-gray-500">
            Tip: Click on a value to select it, then click "Resolve" to apply
          </div>
          <button
            @click="resolveAll"
            :disabled="Object.keys(selectedChoices).length !== conflicts.length"
            class="px-6 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded uppercase transition-colors font-bold"
          >
            Resolve All ({{ Object.keys(selectedChoices).length }}/{{ conflicts.length }})
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useConflicts } from '../composables/useConflicts'
import type { Conflict } from '../composables/useConflicts'

const props = defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits<{
  close: []
  resolved: []
}>()

const { conflicts, loading, resolveConflict, fetchConflicts } = useConflicts()
const selectedChoices = ref<Record<string, string>>({})

// Watch for modal opening
watch(() => props.isOpen, async (isOpen) => {
  if (isOpen) {
    await fetchConflicts(undefined, 'pending')
    selectedChoices.value = {}
  }
})

function selectChoice(conflictId: string, value: string) {
  selectedChoices.value[conflictId] = value
}

async function handleResolve(conflict: Conflict) {
  const chosenValue = selectedChoices.value[conflict.id]
  if (!chosenValue) {
    alert('Please select a value first')
    return
  }

  const success = await resolveConflict(conflict.id, chosenValue)
  if (success) {
    delete selectedChoices.value[conflict.id]

    // Check if all conflicts resolved
    if (conflicts.value.length === 0) {
      alert('✅ All conflicts resolved!')
      emit('resolved')
      closeModal()
    }
  } else {
    alert('❌ Failed to resolve conflict')
  }
}

async function resolveAll() {
  const resolvePromises = conflicts.value.map(async (conflict) => {
    const chosenValue = selectedChoices.value[conflict.id]
    if (chosenValue) {
      return resolveConflict(conflict.id, chosenValue)
    }
    return false
  })

  const results = await Promise.all(resolvePromises)
  const successCount = results.filter(r => r).length

  if (successCount === conflicts.value.length) {
    alert(`✅ Resolved ${successCount} conflict(s)!`)
    emit('resolved')
    closeModal()
  } else {
    alert(`⚠️ Resolved ${successCount}/${conflicts.value.length} conflicts`)
  }
}

function closeModal() {
  emit('close')
}
</script>
