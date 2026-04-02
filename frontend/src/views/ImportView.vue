<template>
  <div class="max-w-7xl mx-auto px-4 py-6">
    <!-- File Browser Modal -->
    <FileBrowser
      :show="showBrowser"
      mode="file"
      :initial-path="filePath || '/breaches'"
      @select="handleFileSelect"
      @close="showBrowser = false"
    />

    <!-- Step 1: File Selection -->
    <div class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Step 1: Select CSV File</h2>

      <div class="grid grid-cols-2 gap-4">
        <div class="input-group col-span-2">
          <label class="label">File Path</label>
          <div class="flex gap-2">
            <input
              v-model="filePath"
              type="text"
              placeholder="/breaches/breach.csv"
              class="flex-1"
            />
            <button @click="showBrowser = true" class="btn-secondary whitespace-nowrap">
              BROWSE
            </button>
          </div>
        </div>

        <div class="input-group">
          <label class="label">Delimiter (auto-detected if empty)</label>
          <select v-model="customDelimiter" class="w-full">
            <option value="">Auto-detect</option>
            <option value=",">, (Comma)</option>
            <option value=";">; (Semicolon)</option>
            <option value=":">: (Colon)</option>
            <option value="|">| (Pipe)</option>
            <option value="	">Tab</option>
          </select>
        </div>

        <div class="input-group">
          <label class="label">Encoding (auto-detected if empty)</label>
          <select v-model="customEncoding" class="w-full">
            <option value="">Auto-detect</option>
            <option value="utf-8">UTF-8</option>
            <option value="latin-1">Latin-1 (ISO-8859-1)</option>
            <option value="windows-1252">Windows-1252</option>
            <option value="cp1252">CP1252</option>
          </select>
        </div>
      </div>

      <button
        @click="analyzeFile"
        :disabled="!filePath || analyzing"
        class="btn-primary mt-4"
      >
        {{ analyzing ? 'ANALYZING...' : 'ANALYZE FILE' }}
      </button>

      <div v-if="analysisError" class="mt-4 text-red-team-500 text-sm">
        ERROR: {{ analysisError }}
      </div>
    </div>

    <!-- Step 2: File Analysis & Column Mapping -->
    <div v-if="fileAnalysis" class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Step 2: Map Columns</h2>

      <!-- File Info -->
      <div class="grid grid-cols-4 gap-4 mb-6 text-sm">
        <div>
          <span class="text-gray-500">Total Rows:</span>
          <span class="text-gray-300 ml-2 font-bold">{{ fileAnalysis.total_rows.toLocaleString() }}</span>
        </div>
        <div>
          <span class="text-gray-500">Encoding:</span>
          <span class="text-gray-300 ml-2">{{ fileAnalysis.encoding }}</span>
        </div>
        <div>
          <span class="text-gray-500">Delimiter:</span>
          <span class="text-gray-300 ml-2 font-mono">{{ fileAnalysis.delimiter }}</span>
        </div>
        <div>
          <span class="text-gray-500">Columns:</span>
          <span class="text-gray-300 ml-2 font-bold">{{ fileAnalysis.columns.length }}</span>
        </div>
      </div>

      <!-- Breach Info -->
      <div class="grid grid-cols-2 gap-4 mb-6">
        <div class="input-group">
          <label class="label">Breach Name *</label>
          <input v-model="breachName" type="text" placeholder="LinkedIn 2021" class="w-full" />
        </div>
        <div class="input-group">
          <label class="label">Breach Date (optional)</label>
          <input v-model="breachDate" type="date" class="w-full" />
        </div>
      </div>

      <!-- Column Mapping -->
      <div class="mb-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-bold text-gray-300 uppercase">Column Mapping</h3>
          <button @click="autoMapColumns" class="btn-secondary text-xs">AUTO-MAP</button>
        </div>

        <div class="grid grid-cols-1 gap-2">
          <div
            v-for="column in fileAnalysis.columns"
            :key="column.name"
            class="bg-dark-200 border border-gray-700 p-3 hover:border-red-team-500 transition-colors"
          >
            <div class="grid grid-cols-3 gap-4 items-center">
              <!-- Source Column -->
              <div>
                <div class="text-sm text-gray-400">{{ column.name }}</div>
                <div class="text-xs text-gray-600">{{ column.detected_type }}</div>
                <div v-if="column.sample_values && column.sample_values.length > 0" class="text-xs text-gray-500 mt-1">
                  Ex: {{ column.sample_values.slice(0, 3).join(', ').substring(0, 40) }}{{ column.sample_values.slice(0, 3).join(', ').length > 40 ? '...' : '' }}
                </div>
              </div>

              <!-- Arrow -->
              <div class="text-center text-gray-600">→</div>

              <!-- Target Field -->
              <div>
                <select
                  v-model="columnMapping[column.name]"
                  class="w-full text-sm"
                >
                  <option :value="undefined">-- Skip --</option>
                  <option value="email">Email</option>
                  <option value="username">Username</option>
                  <option value="password">Password</option>
                  <option value="password_hash">Password Hash</option>
                  <option value="phone">Phone</option>
                  <option value="ip_address">IP Address</option>
                  <option value="full_name">Full Name</option>
                  <option value="first_name">First Name</option>
                  <option value="last_name">Last Name</option>
                  <option value="gender">Gender</option>
                  <option value="birth_date">Birth Date</option>
                  <option value="address">Address</option>
                  <option value="city">City</option>
                  <option value="country">Country</option>
                  <option value="zip_code">ZIP Code</option>
                  <option value="company">Company</option>
                  <option value="job_title">Job Title</option>
                  <option value="social_media">Social Media</option>
                  <option value="website">Website</option>
                  <option value="notes">Notes</option>
                </select>
              </div>
            </div>

            <!-- Sample Data -->
            <div v-if="column.samples && column.samples.length > 0" class="mt-2 text-xs text-gray-500 font-mono truncate">
              Sample: {{ column.samples.slice(0, 3).join(', ') }}
            </div>
          </div>
        </div>
      </div>

      <!-- Preview Button -->
      <button
        @click="previewImport"
        :disabled="!canPreview"
        class="btn-secondary"
      >
        PREVIEW IMPORT
      </button>
    </div>

    <!-- Step 3: Preview -->
    <div v-if="importPreview" class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Step 3: Preview</h2>

      <div class="mb-4 text-sm text-gray-400">
        Preview of {{ importPreview.preview_count }} documents (out of {{ importPreview.total_rows.toLocaleString() }} total rows)
      </div>

      <div class="space-y-2 max-h-[400px] overflow-y-auto mb-4">
        <div
          v-for="(doc, index) in importPreview.sample_documents.slice(0, 5)"
          :key="index"
          class="bg-dark-200 border border-gray-700 p-3 text-sm"
        >
          <div class="grid grid-cols-2 gap-2">
            <div v-for="(value, key) in doc" :key="key">
              <span class="text-gray-500">{{ key }}:</span>
              <span class="text-gray-300 ml-2 font-mono text-xs">{{ truncate(String(value), 50) }}</span>
            </div>
          </div>
        </div>
      </div>

      <button
        @click="startImport"
        :disabled="importing"
        class="btn-primary"
      >
        {{ importing ? 'IMPORTING...' : 'START IMPORT' }}
      </button>
    </div>

    <!-- Import Progress -->
    <div v-if="importing || importComplete" class="card p-6 mb-6">
      <h2 class="text-lg font-bold text-red-team-500 mb-4 uppercase tracking-wide">Import Progress</h2>

      <div v-if="importProgress" class="mb-4">
        <!-- Progress Bar -->
        <div class="bg-dark-200 h-3 mb-2">
          <div
            class="progress-bar"
            :style="{ width: importProgress.progress + '%' }"
          ></div>
        </div>

        <!-- Stats -->
        <div class="flex items-center justify-between text-sm">
          <div class="text-gray-400">
            <span class="text-red-team-500 font-bold">{{ importProgress.imported?.toLocaleString() || 0 }}</span>
            / {{ importProgress.total_rows?.toLocaleString() || 0 }} rows imported
          </div>
          <div class="text-gray-400">
            {{ importProgress.progress }}%
          </div>
        </div>

        <!-- Status Message -->
        <div class="mt-3 text-sm" :class="{
          'text-gray-400': importProgress.status === 'importing',
          'text-green-500': importProgress.status === 'completed',
          'text-red-team-500': importProgress.status === 'error',
          'text-yellow-500': importProgress.status === 'cancelled'
        }">
          {{ importProgress.message }}
        </div>

        <!-- Errors -->
        <div v-if="importProgress.errors && importProgress.errors.length > 0" class="mt-3">
          <div class="text-sm text-red-team-500 mb-2">Errors:</div>
          <div class="space-y-1 text-xs text-gray-500 max-h-[200px] overflow-y-auto">
            <div v-for="(error, index) in importProgress.errors" :key="index">
              {{ error }}
            </div>
          </div>
        </div>
      </div>

      <!-- Cancel Button -->
      <button
        v-if="importing"
        @click="cancelImport"
        class="btn-secondary"
      >
        CANCEL IMPORT
      </button>

      <!-- Reset Button -->
      <button
        v-if="importComplete"
        @click="resetImport"
        class="btn-primary"
      >
        IMPORT ANOTHER FILE
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useFileService } from '@/composables/useFiles'
import { useImportService } from '@/composables/useImport'
import FileBrowser from '@/components/FileBrowser.vue'

const { analyzeFile: analyzeCSV, fileAnalysis, analyzing, analysisError } = useFileService()
const { previewImport: previewImportData, startImport: executeImport, cancelImport: cancelImportProcess, importPreview, importProgress, importing, importComplete } = useImportService()

// File browser state
const showBrowser = ref(false)

// Form state
const filePath = ref('')
const breachName = ref('')
const breachDate = ref('')
const customDelimiter = ref('')
const customEncoding = ref('')
const columnMapping = ref<Record<string, string | undefined>>({})

function handleFileSelect(path: string) {
  filePath.value = path
}

const canPreview = computed(() => {
  return breachName.value.trim().length > 0 &&
    Object.values(columnMapping.value).some(v => v !== undefined)
})

async function analyzeFile() {
  if (!filePath.value) return

  columnMapping.value = {}
  await analyzeCSV(filePath.value, customDelimiter.value, customEncoding.value)

  // Initialize all mappings to undefined (skip)
  if (fileAnalysis.value) {
    for (const column of fileAnalysis.value.columns) {
      columnMapping.value[column.name] = undefined
    }
  }
}

function autoMapColumns() {
  if (!fileAnalysis.value) return

  for (const column of fileAnalysis.value.columns) {
    const name = column.name.toLowerCase()
    const type = column.type?.toLowerCase() || ''

    // Auto-map based on column name or type (order matters - most specific first)
    if (name.includes('email') || name.includes('mail') || type.includes('email')) {
      columnMapping.value[column.name] = 'email'
    } else if (name.includes('user') || name.includes('login') || name.includes('pseudo')) {
      columnMapping.value[column.name] = 'username'
    } else if (name.includes('pass') && name.includes('hash')) {
      columnMapping.value[column.name] = 'password_hash'
    } else if (name.includes('pass') || name.includes('pwd') || name.includes('mot de passe')) {
      columnMapping.value[column.name] = 'password'
    } else if (name.includes('phone') || name.includes('mobile') || name.includes('tel') || name.includes('gsm')) {
      columnMapping.value[column.name] = 'phone'
    } else if (name.includes('ip') && !name.includes('zip')) {
      columnMapping.value[column.name] = 'ip_address'
    } else if (name.includes('firstname') || name.includes('first_name') || name.includes('prenom') || name.includes('prénom')) {
      columnMapping.value[column.name] = 'first_name'
    } else if (name.includes('lastname') || name.includes('last_name') || name.includes('nom') && !name.includes('prenom')) {
      columnMapping.value[column.name] = 'last_name'
    } else if (name.includes('fullname') || name.includes('full_name') || name.includes('name') && !name.includes('user') && !name.includes('file')) {
      columnMapping.value[column.name] = 'full_name'
    } else if (name.includes('gender') || name.includes('sex') || name.includes('sexe') || name.includes('genre')) {
      columnMapping.value[column.name] = 'gender'
    } else if (name.includes('birth') || name.includes('dob') || name.includes('naissance') || name.includes('birthday')) {
      columnMapping.value[column.name] = 'birth_date'
    } else if (name.includes('city') || name.includes('ville') || name.includes('town')) {
      columnMapping.value[column.name] = 'city'
    } else if (name.includes('country') || name.includes('pays') || name.includes('nation')) {
      columnMapping.value[column.name] = 'country'
    } else if (name.includes('zip') || name.includes('postal') || name.includes('cp')) {
      columnMapping.value[column.name] = 'zip_code'
    } else if (name.includes('company') || name.includes('entreprise') || name.includes('société') || name.includes('societe')) {
      columnMapping.value[column.name] = 'company'
    } else if (name.includes('job') || name.includes('title') || name.includes('poste') || name.includes('profession')) {
      columnMapping.value[column.name] = 'job_title'
    } else if (name.includes('facebook') || name.includes('twitter') || name.includes('instagram') || name.includes('linkedin') || name.includes('social')) {
      columnMapping.value[column.name] = 'social_media'
    } else if (name.includes('website') || name.includes('site') || name.includes('url') && !name.includes('email')) {
      columnMapping.value[column.name] = 'website'
    } else if (name.includes('address') || name.includes('adresse') || name.includes('street') || name.includes('rue')) {
      columnMapping.value[column.name] = 'address'
    } else if (name.includes('note') || name.includes('comment') || name.includes('description')) {
      columnMapping.value[column.name] = 'notes'
    }
  }
}

async function previewImport() {
  if (!canPreview.value) return

  const breachDateTimestamp = breachDate.value ? new Date(breachDate.value).getTime() / 1000 : undefined

  await previewImportData({
    file_path: filePath.value,
    breach_name: breachName.value,
    column_mapping: columnMapping.value,
    breach_date: breachDateTimestamp
  })
}

async function startImport() {
  const breachDateTimestamp = breachDate.value ? new Date(breachDate.value).getTime() / 1000 : undefined

  await executeImport({
    file_path: filePath.value,
    breach_name: breachName.value,
    column_mapping: columnMapping.value,
    breach_date: breachDateTimestamp
  })
}

function cancelImport() {
  cancelImportProcess()
}

function resetImport() {
  filePath.value = ''
  breachName.value = ''
  breachDate.value = ''
  columnMapping.value = {}
  importProgress.value = null
  importComplete.value = false
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}
</script>
