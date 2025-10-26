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
  /** 'absolute' uses 0..max (+headroom). 'zoomed' uses min..max (+padding). */
  scaleMode?: 'absolute' | 'zoomed'
}>(), {
  title: 'Travel time scenarios',
  barHeight: 26,
  barGap: 12,
  labelWidth: 160,
  rightPad: 12,
  valueColWidth: 96,
  baseColor: '#e5e7eb',
  delayColor: '#fecaca',
  trackColor: '#f3f4f6',
  scaleMode: 'absolute',
})

/* ---------- build series (base + delay) ---------- */
function minutesTotal(entry: any, floodedDur_s: number) {
  const baseline = entry?.floodSummary?.baseline_s ?? 0
  return Math.max(0, Math.round((entry?.duration_s + (floodedDur_s - baseline)) / 60))
}
const series = computed(() => {
  const e = props.entry
  if (!e) return []
  const baseMin = Math.round(e.duration_s / 60)
  const out: Array<{ label: string; baseMin: number; totalMin: number; deltaMin: number }> = [
    { label: 'Non-flooded', baseMin, totalMin: baseMin, deltaMin: 0 },
  ]
  const baseline = e.floodSummary?.baseline_s ?? 0
  for (const sc of (e.floodSummary?.scenarios ?? [])) {
    const tot = minutesTotal(e, sc.duration_s)
    const delta = Math.max(0, Math.round((sc.duration_s - baseline) / 60))
    out.push({ label: sc.scenario, baseMin, totalMin: tot, deltaMin: delta })
  }
  return out
})

/* ---------- scale helpers ---------- */
function niceCeil(n: number, stepCandidates = [5, 10, 20, 25, 50]): number {
  // choose a "nice" upper bound
  if (n <= 0) return 1
  const order = Math.pow(10, Math.floor(Math.log10(n)))
  for (const s of stepCandidates) {
    const bound = Math.ceil(n / (s * (order / 10))) * (s * (order / 10))
    if (bound >= n) return bound
  }
  return Math.ceil(n)
}

const minVal = computed(() => {
  if (!series.value.length) return 0
  const mins = series.value.map(s => s.totalMin)
  return Math.min(...mins)
})
const maxVal = computed(() => {
  if (!series.value.length) return 1
  const mins = series.value.map(s => s.totalMin)
  return Math.max(...mins)
})

/** chart domain (minutes) */
const domain = computed(() => {
  if (!series.value.length) return { min: 0, max: 1 }

  if (props.scaleMode === 'zoomed') {
    // zoomed: focus on the visible range with ~10% padding
    const span = Math.max(1, maxVal.value - minVal.value)
    const pad = Math.max(0.5, span * 0.1)
    const min = Math.max(0, minVal.value - pad)
    const max = min + span + 2 * pad
    return { min, max: niceCeil(max) }
  }

  // absolute: start at 0 with ~15% headroom
  const maxWithHeadroom = maxVal.value * 1.15
  return { min: 0, max: niceCeil(maxWithHeadroom) }
})

/* ---------- responsive width ---------- */
const wrapEl = ref<HTMLDivElement | null>(null)
const containerW = ref(640)
let ro: ResizeObserver | null = null
onMounted(() => {
  if (!wrapEl.value) return
  const measure = () =>
    (containerW.value = Math.max(360, Math.round(wrapEl.value!.getBoundingClientRect().width)))
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

/* ---------- ticks ---------- */
const ticks = computed(() => {
  const span = Math.max(1, domain.value.max - domain.value.min)
  const rough = span <= 20 ? 5 : span <= 60 ? 10 : 20
  const end = niceCeil(domain.value.max)
  const start = domain.value.min
  const arr: number[] = []
  for (let v = Math.ceil(start / rough) * rough; v <= end; v += rough) arr.push(v)
  return { step: rough, start, end, arr }
})

/* ---------- x-position helpers ---------- */
const xFromMin = (m: number) => {
  const { min, max } = domain.value
  const span = Math.max(1e-6, max - min)
  const ratio = (m - min) / span
  return Math.max(0, Math.min(1, ratio)) * plotWidth.value
}
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
        <span class="text-gray-500">
          · Scale: <strong>{{ scaleMode === 'zoomed' ? 'Zoomed' : 'Absolute' }}</strong>
        </span>
      </div>
    </div>

    <svg :width="containerW" :height="svgHeight" class="block">
      <!-- grid -->
      <g :transform="`translate(${plotLeft}, 14)`">
        <g v-for="v in ticks.arr" :key="'g'+v">
          <line :x1="xFromMin(v)" y1="0"
                :x2="xFromMin(v)" :y2="svgHeight - 24"
                :stroke="trackColor" stroke-width="1" />
          <text :x="xFromMin(v)" y="-4" text-anchor="middle"
                class="fill-gray-500 text-[11px]">{{ v }}</text>
        </g>
        <!-- origin tick if zoomed (shows left baseline) -->
        <text v-if="scaleMode==='zoomed'"
              :x="xFromMin(domain.min)" y="-4" text-anchor="start"
              class="fill-gray-400 text-[10px]">min {{ Math.round(domain.min) }}</text>
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

        <!-- base segment (PROPORTIONAL: no min-width clamp) -->
        <rect :x="plotLeft" :y="24 + i * (barHeight + barGap)"
              :width="xFromMin(s.baseMin)"
              :height="barHeight" rx="7" ry="7" :fill="baseColor" />

        <!-- delay segment is only the extra part -->
        <rect v-if="s.deltaMin > 0"
              :x="plotLeft + xFromMin(s.baseMin)"
              :y="24 + i * (barHeight + barGap)"
              :width="xFromMin(s.deltaMin)"
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
