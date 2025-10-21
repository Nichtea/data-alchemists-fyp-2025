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
  <!-- 与 Stops 面板统一：bg-white rounded shadow p-3 -->
  <div class="bg-white rounded shadow p-3 border border-gray-100">
    <div class="text-base font-semibold mb-2">Private Transport</div>

    <div class="space-y-2">
      <!-- Start address -->
      <label class="block">
        <div class="text-xs text-gray-600 mb-1">Starts At</div>
        <input
          v-model="startModel"
          type="text"
          placeholder="Type an address (e.g. Woodlands Checkpoint)"
          class="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          autocomplete="off"
        />
      </label>

      <!-- End address -->
      <label class="block">
        <div class="text-xs text-gray-600 mb-1">Ends At</div>
        <input
          v-model="endModel"
          type="text"
          placeholder="Type an address (e.g. Tampines East Community Club)"
          class="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          autocomplete="off"
        />
      </label>

      <!-- 可选：日期/时间（保持一致的输入尺寸与样式；需要时解注释） -->
      <!--
      <div class="grid grid-cols-2 gap-2">
        <label class="block">
          <div class="text-xs text-gray-600 mb-1">Date (optional)</div>
          <input
            v-model="dateModel"
            type="date"
            class="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          />
        </label>
        <label class="block">
          <div class="text-xs text-gray-600 mb-1">Time (optional)</div>
          <input
            v-model="timeModel"
            type="time"
            class="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          />
        </label>
      </div>
      -->

      <!-- 操作区：与 Stops 面板按钮风格统一（px-3 py-1.5 / text-sm / inline-flex） -->
      <div class="flex items-center gap-2 flex-wrap pt-1">
        <button
          class="inline-flex items-center gap-2 rounded bg-blue-600 text-white px-3 py-1.5 text-sm hover:bg-blue-700 disabled:opacity-60"
          :disabled="loading"
          @click="$emit('search')"
          title="Get route by car"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M3 13l2-2m0 0l7-7 4 4-7 7m-4-4v6a2 2 0 002 2h6"/>
          </svg>
          {{ loading ? 'Loading…' : 'Get route' }}
        </button>

        <button
          type="button"
          class="inline-flex items-center gap-2 rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
          @click="swapAddresses"
          title="Swap start/end"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 7h11M10 3l4 4-4 4M20 17H9m6 4-4-4 4-4"/>
          </svg>
          Swap
        </button>
      </div>

      <!-- 错误信息/总体状态：保持小号文字 -->
      <p v-if="errorMsg" class="text-xs text-rose-600 mt-1">{{ errorMsg }}</p>

      <div v-if="overallStatus" class="text-xs mt-1">
        Overall route status:
        <span
          :class="overallStatus === 'flooded'
            ? 'text-rose-600 font-medium'
            : 'text-blue-700 font-medium'"
        >
          {{ overallStatus }}
        </span>
      </div>
    </div>
  </div>
</template>
