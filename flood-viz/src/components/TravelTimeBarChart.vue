<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'

type Entry = {
  duration_s: number
  floodSummary?: { baseline_s?: number; scenarios?: { scenario: string; duration_s: number }[] }
}

const props = withDefaults(defineProps<{
  entry?: Entry | null
  title?: string
  barHeight?: number
  barGap?: number
  labelWidth?: number
  rightPad?: number
  valueColWidth?: number
  // colors
  baseColor?: string
  delayColor?: string
  trackColor?: string
}>(), {
  title: 'Travel time scenarios',
  barHeight: 26,
  barGap: 12,
  labelWidth: 160,
  rightPad: 12,
  valueColWidth: 96,
  baseColor: '#e5e7eb',   // grey for base time
  delayColor: '#fecaca',  // red for additional delay
  trackColor: '#f3f4f6',
})

/* ---------- series with base+delay ---------- */
function minutesTotal(entry: any, floodedBusDur_s: number) {
  const baselineBus = entry?.floodSummary?.baseline_s ?? 0
  return Math.max(0, Math.round((entry?.duration_s + (floodedBusDur_s - baselineBus)) / 60))
}
const series = computed(() => {
  const e = props.entry
  if (!e) return []
  const baseMin = Math.round(e.duration_s / 60) // total non-flooded itinerary minutes
  const out: Array<{
    label: string; baseMin: number; totalMin: number; deltaMin: number; flooded: boolean
  }> = [{ label: 'Non-flooded', baseMin, totalMin: baseMin, deltaMin: 0, flooded: false }]

  const baselineBus = e.floodSummary?.baseline_s ?? 0
  for (const sc of (e.floodSummary?.scenarios ?? [])) {
    const tot = minutesTotal(e, sc.duration_s)
    const delta = Math.max(0, Math.round((sc.duration_s - baselineBus) / 60))
    out.push({ label: sc.scenario, baseMin, totalMin: tot, deltaMin: delta, flooded: true })
  }
  return out
})
const maxMin = computed(() => Math.max(...series.value.map(s => s.totalMin), 1))

/* ---------- responsive width ---------- */
const wrapEl = ref<HTMLDivElement | null>(null)
const containerW = ref(640)
let ro: ResizeObserver | null = null
onMounted(() => {
  if (!wrapEl.value) return
  const measure = () => (containerW.value = Math.max(360, Math.round(wrapEl.value!.getBoundingClientRect().width)))
  ro = new ResizeObserver(measure); ro.observe(wrapEl.value); measure()
})
onBeforeUnmount(() => ro?.disconnect())

const plotLeft = computed(() => props.labelWidth + 14)
const plotWidth = computed(() =>
  Math.max(240, containerW.value - (plotLeft.value + props.valueColWidth + props.rightPad))
)
const svgHeight = computed(
  () => series.value.length * props.barHeight + (series.value.length - 1) * props.barGap + 24
)

const ticks = computed(() => {
  const step = maxMin.value > 80 ? 20 : maxMin.value > 40 ? 10 : 5
  const end = Math.ceil(maxMin.value / step) * step
  const arr: number[] = []; for (let v = 0; v <= end; v += step) arr.push(v)
  return { step, end, arr }
})
</script>

<template>
  <div ref="wrapEl" class="rounded-xl border border-gray-200 bg-white/90 backdrop-blur p-3 shadow-sm">
    <div class="mb-2 flex items-center gap-3">
      <div class="text-sm font-semibold">{{ title }}</div>
      <div class="ml-auto flex items-center gap-4 text-[11px] text-gray-600">
        <span class="inline-flex items-center gap-1">
          <span class="inline-block h-2 w-6 rounded" :style="{background: baseColor}"></span> Base (non-flooded)
        </span>
        <span class="inline-flex items-center gap-1">
          <span class="inline-block h-2 w-6 rounded" :style="{background: delayColor}"></span> Additional delay
        </span>
      </div>
    </div>

    <svg :width="containerW" :height="svgHeight" class="block">
      <!-- grid -->
      <g :transform="`translate(${plotLeft}, 14)`">
        <g v-for="v in ticks.arr" :key="'g'+v">
          <line :x1="(v / ticks.end) * plotWidth" y1="0"
                :x2="(v / ticks.end) * plotWidth" :y2="svgHeight - 24"
                :stroke="trackColor" stroke-width="1" />
          <text :x="(v / ticks.end) * plotWidth" y="-4" text-anchor="middle"
                class="fill-gray-500 text-[11px]">{{ v }}</text>
        </g>
      </g>

      <!-- bars -->
      <g v-for="(s, i) in series" :key="s.label">
        <!-- label -->
        <text :x="0" :y="24 + i * (barHeight + barGap) + barHeight * 0.72"
              class="fill-gray-700 text-[12px]">{{ s.label }}</text>

        <!-- track -->
        <rect :x="plotLeft" :y="24 + i * (barHeight + barGap)"
              :width="plotWidth" :height="barHeight" rx="7" ry="7"
              :fill="trackColor" />

        <!-- base segment -->
        <rect :x="plotLeft" :y="24 + i * (barHeight + barGap)"
              :width="Math.max(10, Math.round((s.baseMin / maxMin) * plotWidth))"
              :height="barHeight" rx="7" ry="7" :fill="baseColor" />

        <!-- delay segment (only the extra part) -->
        <rect v-if="s.deltaMin > 0"
              :x="plotLeft + Math.round((s.baseMin / maxMin) * plotWidth)"
              :y="24 + i * (barHeight + barGap)"
              :width="Math.max(2, Math.round((s.deltaMin / maxMin) * plotWidth))"
              :height="barHeight" rx="7" ry="7" :fill="delayColor" />

        <!-- values -->
        <text :x="plotLeft + plotWidth + 8"
              :y="24 + i * (barHeight + barGap) + barHeight * 0.72"
              class="fill-gray-800 text-[12px] tabular-nums">
          ~ {{ s.totalMin }} min
        </text>
        <text v-if="s.deltaMin > 0"
              :x="containerW - 6" text-anchor="end"
              :y="24 + i * (barHeight + barGap) + barHeight * 0.72"
              class="fill-gray-500 text-[11px]">
          +{{ s.deltaMin }} min
        </text>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.text-\[11px\]{font-size:11px}.text-\[12px\]{font-size:12px}
</style>
