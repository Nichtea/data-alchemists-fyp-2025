<!-- File: src/components/AddressDetailsPanel.vue -->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  startAddress: string
  endAddress: string
  date?: string
  time?: string
  loading?: boolean
  errorMsg?: string | null
  overallStatus?: 'clear' | 'flooded'
}>()

const emit = defineEmits<{
  (e: 'update:startAddress', v: string): void
  (e: 'update:endAddress', v: string): void
  (e: 'update:date', v: string): void
  (e: 'update:time', v: string): void
  (e: 'search'): void
}>()

const startModel = computed({
  get: () => props.startAddress,
  set: (v: string) => emit('update:startAddress', v),
})
const endModel = computed({
  get: () => props.endAddress,
  set: (v: string) => emit('update:endAddress', v),
})
const dateModel = computed({
  get: () => props.date ?? '',
  set: (v: string) => emit('update:date', v),
})
const timeModel = computed({
  get: () => props.time ?? '',
  set: (v: string) => emit('update:time', v),
})

function swapAddresses() {
  emit('update:startAddress', props.endAddress || '')
  emit('update:endAddress', props.startAddress || '')
}
</script>

<template>
  <div class="bg-white rounded-2xl shadow-sm p-4 border border-gray-100">
    <div class="flex items-center justify-between">
      <div class="text-base font-semibold">Private Transport</div>
      <div v-if="overallStatus" class="text-xs">
        <span
          :class="overallStatus === 'flooded' ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700'"
          class="px-2 py-0.5 rounded-full font-medium"
        >
          {{ overallStatus }}
        </span>
      </div>
    </div>

    <div class="mt-3 space-y-3">
      <!-- Start -->
      <label class="block">
        <div class="text-xs text-gray-600 mb-1 flex items-center gap-1">
          <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white text-[11px] font-bold">A</span>
          <span>Starts At</span>
        </div>
        <input
          v-model="startModel"
          type="text"
          placeholder="Type an address (e.g. Woodlands Checkpoint)"
          class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          autocomplete="off"
        />
      </label>

      <!-- End -->
      <label class="block">
        <div class="text-xs text-gray-600 mb-1 flex items-center gap-1">
          <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-green-600 text-white text-[11px] font-bold">B</span>
          <span>Ends At</span>
        </div>
        <input
          v-model="endModel"
          type="text"
          placeholder="Type an address (e.g. Tampines East Community Club)"
          class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          autocomplete="off"
        />
      </label>

      <!-- Actions -->
      <div class="flex items-center gap-2 flex-wrap pt-1">
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-blue-600 text-white px-3 py-2 text-sm hover:bg-blue-700 disabled:opacity-60"
          :disabled="loading"
          @click="$emit('search')"
          title="Get route by car"
        >
          {{ loading ? 'Loading…' : 'Get route' }}
        </button>

        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
          @click="swapAddresses"
          title="Swap start/end"
        >
          Swap
        </button>
      </div>

      <p v-if="errorMsg" class="text-xs text-rose-600 mt-1">{{ errorMsg }}</p>
    </div>
  </div>
</template>
