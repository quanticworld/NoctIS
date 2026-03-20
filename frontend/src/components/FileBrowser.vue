<template>
  <div v-if="show" class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-dark-100 border border-red-team-500 max-w-4xl w-full mx-4 max-h-[80vh] flex flex-col">
      <!-- Modal Header -->
      <div class="flex items-center justify-between p-4 border-b border-gray-700">
        <h3 class="text-lg font-bold text-red-team-500 uppercase tracking-wide">
          {{ mode === 'file' ? 'SELECT FILE' : 'SELECT DIRECTORY' }}
        </h3>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-100">
          <span class="text-2xl">×</span>
        </button>
      </div>

      <!-- Current Path -->
      <div class="p-4 border-b border-gray-700">
        <div class="text-sm text-gray-400 mb-2">Current Path:</div>
        <div class="font-mono text-sm text-gray-300 bg-dark-200 px-3 py-2 rounded">
          {{ currentPath }}
        </div>
      </div>

      <!-- File List -->
      <div class="flex-1 overflow-y-auto p-4">
        <div v-if="loading" class="text-center text-gray-500 py-8">
          Loading...
        </div>

        <div v-else-if="error" class="text-center text-red-team-500 py-8">
          ERROR: {{ error }}
        </div>

        <div v-else class="space-y-1">
          <!-- Parent Directory -->
          <button
            v-if="parentPath"
            @click="navigateToParent"
            class="w-full text-left px-4 py-2 hover:bg-dark-200 flex items-center gap-3 group"
          >
            <span class="text-red-team-500">📁</span>
            <span class="text-gray-400 group-hover:text-gray-100">..</span>
          </button>

          <!-- Items -->
          <button
            v-for="item in items"
            :key="item.path"
            @click="selectItem(item)"
            class="w-full text-left px-4 py-2 hover:bg-dark-200 flex items-center gap-3 group"
          >
            <span class="text-red-team-500">{{ item.is_directory ? '📁' : '📄' }}</span>
            <span class="flex-1 text-gray-300 group-hover:text-gray-100 font-mono text-sm">
              {{ item.name }}
            </span>
            <span v-if="!item.is_directory" class="text-xs text-gray-500">
              {{ formatSize(item.size) }}
            </span>
          </button>
        </div>
      </div>

      <!-- Footer Actions -->
      <div class="p-4 border-t border-gray-700">
        <div class="flex gap-2">
          <button @click="$emit('close')" class="btn-secondary">
            CANCEL
          </button>
          <button
            v-if="mode === 'directory'"
            @click="selectCurrentDirectory"
            class="btn-primary flex-1"
          >
            SELECT THIS DIRECTORY
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface FileItem {
  name: string
  path: string
  is_directory: boolean
  size: number
}

interface Props {
  show: boolean
  mode: 'file' | 'directory'
  initialPath?: string
}

const props = withDefaults(defineProps<Props>(), {
  initialPath: '/breaches'
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'select', path: string): void
}>()

const currentPath = ref(props.initialPath)
const parentPath = ref<string | null>(null)
const items = ref<FileItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

watch(() => props.show, async (newShow) => {
  if (newShow) {
    currentPath.value = props.initialPath
    await loadDirectory(currentPath.value)
  }
})

async function loadDirectory(path: string) {
  loading.value = true
  error.value = null

  try {
    const response = await fetch(`/api/v1/files/browse?path=${encodeURIComponent(path)}&mode=${props.mode}`)

    if (!response.ok) {
      throw new Error(`Failed to browse: ${response.statusText}`)
    }

    const data = await response.json()
    currentPath.value = data.current_path
    parentPath.value = data.parent_path
    items.value = data.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loading.value = false
  }
}

async function navigateToParent() {
  if (parentPath.value) {
    await loadDirectory(parentPath.value)
  }
}

async function selectItem(item: FileItem) {
  if (props.mode === 'file' && !item.is_directory) {
    // Select file and close
    emit('select', item.path)
    emit('close')
  } else if (props.mode === 'directory' && !item.is_directory) {
    // In directory mode, clicking a file does nothing
    return
  } else {
    // Navigate into directory
    await loadDirectory(item.path)
  }
}

function selectCurrentDirectory() {
  emit('select', currentPath.value)
  emit('close')
}

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}
</script>
