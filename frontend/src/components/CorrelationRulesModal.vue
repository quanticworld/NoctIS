<template>
  <div class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4" @click.self="close">
    <div class="bg-dark-100 border border-red-team-500 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
      <!-- Header -->
      <div class="p-6 border-b border-gray-700 flex items-center justify-between">
        <div>
          <h2 class="text-xl font-bold text-red-team-500 uppercase">Correlation Rules</h2>
          <p class="text-sm text-gray-400 mt-1">Configure matching strategies for deduplication</p>
        </div>
        <button @click="close" class="text-gray-400 hover:text-white text-2xl">&times;</button>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex-1 flex items-center justify-center">
        <div class="text-gray-400">Loading rules...</div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex-1 flex items-center justify-center">
        <div class="text-red-team-500">ERROR: {{ error }}</div>
      </div>

      <!-- Content -->
      <div v-else class="flex-1 overflow-y-auto p-6">
        <div class="space-y-4">
          <div
            v-for="(rule, idx) in rules"
            :key="idx"
            class="card p-4 border-l-4"
            :class="{
              'border-green-500': rule.confidence >= 90,
              'border-yellow-500': rule.confidence >= 70 && rule.confidence < 90,
              'border-orange-500': rule.confidence >= 50 && rule.confidence < 70,
              'border-red-500': rule.confidence < 50
            }"
          >
            <div class="flex items-start gap-4">
              <!-- Rule Name -->
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-2">
                  <input
                    v-model="rule.name"
                    type="text"
                    class="flex-1 bg-dark-200 text-gray-200 px-3 py-2 rounded font-mono text-sm"
                    placeholder="Rule name (e.g., email_exact)"
                  />
                  <button
                    @click="removeRule(idx)"
                    class="px-3 py-2 bg-red-600 hover:bg-red-700 text-white rounded text-xs uppercase"
                  >
                    Remove
                  </button>
                </div>

                <!-- Confidence Score -->
                <div class="mb-3">
                  <label class="label">Confidence Score (%)</label>
                  <input
                    v-model.number="rule.confidence"
                    type="number"
                    min="0"
                    max="100"
                    class="w-32 bg-dark-200 text-gray-200 px-3 py-2 rounded"
                  />
                  <span class="ml-2 text-sm text-gray-400">
                    {{ rule.confidence >= 90 ? 'Golden' : 'Silver' }} threshold
                  </span>
                </div>

                <!-- Matching Keys -->
                <div>
                  <label class="label">Matching Keys</label>
                  <div class="flex items-center gap-2 mb-2">
                    <select
                      v-model="rule.newKey"
                      class="flex-1 bg-dark-200 text-gray-200 px-3 py-2 rounded"
                    >
                      <option value="">-- Select field --</option>
                      <option value="email">Email</option>
                      <option value="username">Username</option>
                      <option value="phone">Phone</option>
                      <option value="ip_address">IP Address</option>
                      <option value="full_name">Full Name</option>
                      <option value="first_name">First Name</option>
                      <option value="last_name">Last Name</option>
                      <option value="birth_date">Birth Date</option>
                      <option value="breach_name">Breach Name</option>
                    </select>
                    <button
                      @click="addKeyToRule(rule)"
                      :disabled="!rule.newKey"
                      class="btn-secondary whitespace-nowrap"
                    >
                      ADD KEY
                    </button>
                  </div>
                  <div class="flex gap-2 flex-wrap">
                    <span
                      v-for="(key, keyIdx) in rule.keys"
                      :key="keyIdx"
                      class="px-3 py-1 bg-red-team-600 text-white rounded text-sm flex items-center gap-2"
                    >
                      {{ key }}
                      <button
                        @click="removeKeyFromRule(rule, keyIdx)"
                        class="hover:text-red-200"
                      >
                        ×
                      </button>
                    </span>
                    <span v-if="rule.keys.length === 0" class="text-sm text-gray-500 italic">
                      No keys configured
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Add New Rule -->
        <button
          @click="addNewRule"
          class="btn-primary w-full mt-4"
        >
          + ADD NEW RULE
        </button>
      </div>

      <!-- Footer Actions -->
      <div class="p-6 border-t border-gray-700 flex justify-between">
        <button @click="resetToDefaults" class="btn-secondary">
          RESET TO DEFAULTS
        </button>
        <div class="flex gap-2">
          <button @click="close" class="btn-secondary">
            CANCEL
          </button>
          <button @click="saveRules" class="btn-primary">
            SAVE RULES
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface CorrelationRule {
  name: string
  confidence: number
  keys: string[]
  newKey?: string
}

const emit = defineEmits<{
  close: []
  save: [rules: CorrelationRule[]]
}>()

const loading = ref(false)
const error = ref<string | null>(null)
const rules = ref<CorrelationRule[]>([])

const DEFAULT_RULES: CorrelationRule[] = [
  { name: 'email_exact', confidence: 95, keys: ['email'] },
  { name: 'phone_firstname', confidence: 85, keys: ['phone', 'first_name'] },
  { name: 'phone_lastname', confidence: 85, keys: ['phone', 'last_name'] },
  { name: 'email_username', confidence: 80, keys: ['email', 'username'] },
  { name: 'fullname_birthdate', confidence: 75, keys: ['full_name', 'birth_date'] },
  { name: 'username_breach', confidence: 50, keys: ['username', 'breach_name'] }
]

onMounted(async () => {
  await loadRules()
})

async function loadRules() {
  loading.value = true
  error.value = null

  try {
    const response = await fetch('/api/v1/mdm/correlation-rules')

    if (!response.ok) {
      // If endpoint doesn't exist yet, use defaults
      if (response.status === 404) {
        rules.value = JSON.parse(JSON.stringify(DEFAULT_RULES))
        return
      }
      throw new Error(`Failed to load rules: ${response.statusText}`)
    }

    const data = await response.json()
    rules.value = data.rules || []

  } catch (err) {
    // Fall back to defaults if loading fails
    console.warn('Failed to load rules, using defaults:', err)
    rules.value = JSON.parse(JSON.stringify(DEFAULT_RULES))
  } finally {
    loading.value = false
  }
}

function addNewRule() {
  rules.value.push({
    name: 'new_rule',
    confidence: 50,
    keys: []
  })
}

function removeRule(index: number) {
  rules.value.splice(index, 1)
}

function addKeyToRule(rule: CorrelationRule) {
  if (rule.newKey && !rule.keys.includes(rule.newKey)) {
    rule.keys.push(rule.newKey)
    rule.newKey = ''
  }
}

function removeKeyFromRule(rule: CorrelationRule, keyIndex: number) {
  rule.keys.splice(keyIndex, 1)
}

function resetToDefaults() {
  if (!confirm('Reset all rules to defaults? This will discard your changes.')) {
    return
  }
  rules.value = JSON.parse(JSON.stringify(DEFAULT_RULES))
}

async function saveRules() {
  loading.value = true
  error.value = null

  try {
    // Validate rules
    for (const rule of rules.value) {
      if (!rule.name || rule.name.trim() === '') {
        throw new Error('All rules must have a name')
      }
      if (rule.keys.length === 0) {
        throw new Error(`Rule "${rule.name}" must have at least one matching key`)
      }
    }

    const response = await fetch('/api/v1/mdm/correlation-rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules: rules.value })
    })

    if (!response.ok) {
      throw new Error(`Failed to save rules: ${response.statusText}`)
    }

    alert('Correlation rules saved successfully!')
    emit('save', rules.value)
    emit('close')

  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
    alert(`Failed to save rules: ${error.value}`)
  } finally {
    loading.value = false
  }
}

function close() {
  emit('close')
}
</script>
