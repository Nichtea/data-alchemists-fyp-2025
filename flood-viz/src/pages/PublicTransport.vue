<script setup lang="ts">
import { computed, ref, watch, onMounted, onActivated, onUnmounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useAppStore } from '@/store/app'
import StopDetailsPanel from '@/components/StopDetailsPanel.vue'
import ControlsPanel from '@/components/ControlsPanel.vue'
import MapCanvas from '@/components/MapCanvas.vue'
import TravelTimeBarChart from '@/components/TravelTimeBarChart.vue'
import { useUrlStateSync } from '@/components/useUrlStateSync'
import { getBusesAffectedByFloods } from '@/api/api'

useUrlStateSync()
const store = useAppStore()

/* ─────────────────────────────
   ACTIVE TAB: 'route' | 'itinerary' | 'flood'
   ───────────────────────────── */
const activeTab = ref<'route' | 'itinerary' | 'flood'>('route')

function setTab(tab: 'route' | 'itinerary' | 'flood') {
  activeTab.value = tab

  // map-layer visibility rules
  if (tab === 'flood') {
    store.setLayerVisible('stops', false)
    store.setLayerVisible('floodEvents', true)
  } else {
    // route / itinerary tab
    store.setLayerVisible('stops', true)
    store.setLayerVisible('floodEvents', false)
    clearFloodUI()
  }
}

/* ─────────────────────────────
   RESET CHART ON (RE)ENTER PAGE
   ───────────────────────────── */
function resetChart() {
  ;(store as any).serviceRouteOverlay = null
}
onMounted(resetChart)
onActivated(resetChart)
onBeforeRouteLeave(resetChart)
onUnmounted(resetChart)

/* ================= Chart ================= */
const chartEntry = computed(() => {
  const o: any = (store as any).serviceRouteOverlay
  const d = o?.directions?.[0]
  if (!d || !Number.isFinite(d.duration_s) || !d.floodSummary) return null
  return { duration_s: Number(d.duration_s), floodSummary: d.floodSummary }
})

/* ================= Flood / affected bus services ================= */
const selectedFloodId = ref<number | null>(null)
const affectedServices = ref<string[]>([])
const loadingAffected = ref(false)
const affectedError = ref<string | null>(null)

function clearFloodUI() {
  selectedFloodId.value = null
  affectedServices.value = []
  affectedError.value = null
  loadingAffected.value = false
}

async function onFloodClick(payload: { floodId: number }) {
  // Only respond if we're actually looking at flood tab
  if (activeTab.value !== 'flood') return

  selectedFloodId.value = payload.floodId
  loadingAffected.value = true
  affectedError.value = null
  affectedServices.value = []

  try {
    const res: any = await getBusesAffectedByFloods(payload.floodId)

    if (!res || typeof res !== 'object' || !Array.isArray(res.results)) {
      throw new Error('Unexpected response shape (missing results).')
    }

    const first: any = res.results[0]
    if (!first || typeof first !== 'object') {
      affectedServices.value = []
      return
    }

    if (first.flood_id != null && !Number.isNaN(Number(first.flood_id))) {
      selectedFloodId.value = Number(first.flood_id)
    }

    const raw: unknown[] = Array.isArray(first.affected_bus_services)
      ? first.affected_bus_services
      : []

    const names: string[] = raw
      .map(s => String(s ?? '').trim())
      .filter((s): s is string => s.length > 0)

    affectedServices.value = Array.from(new Set(names)).sort((a, b) =>
      a.localeCompare(b, undefined, { numeric: true })
    )
  } catch (e: any) {
    const msg =
      e?.message ||
      e?.error ||
      (typeof e?.toString === 'function' ? e.toString() : '') ||
      'Failed to load affected services.'
    affectedError.value = msg
  } finally {
    loadingAffected.value = false
  }
}

/* If something else flips layers externally, keep things sane */
watch(
  () => activeTab.value,
  (tab) => {
    if (tab !== 'flood') clearFloodUI()
  }
)
</script>

<template>
  <div class="h-full grid grid-cols-12 gap-4 p-6 bg-gray-50">

    <!-- LEFT PANE -->
    <div class="col-span-3 space-y-4">

      <!-- Tabs -->
      <div class="bg-white rounded-2xl shadow-sm p-3 border border-gray-100">
        <div class="grid grid-cols-3 gap-2">
          <!-- Tab 1: Best Route -->
          <button
            class="py-2 rounded-lg font-medium text-center transition-colors duration-200"
            :class="activeTab === 'route'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
            @click="setTab('route')"
          >
            Best Route
          </button>

          <!-- Tab 2: Best Itinerary -->
          <button
            class="py-2 rounded-lg font-medium text-center transition-colors duration-200"
            :class="activeTab === 'itinerary'
              ? 'bg-purple-600 text-white shadow-sm'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
            @click="setTab('itinerary')"
          >
            Best Itinerary
          </button>

          <!-- Tab 3: Flood Impact -->
          <button
            class="py-2 rounded-lg font-medium text-center transition-colors duration-200"
            :class="activeTab === 'flood'
              ? 'bg-red-600 text-white shadow-sm'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
            @click="setTab('flood')"
          >
            Affected Bus<br class="hidden sm:block" />
            Services
          </button>
        </div>
      </div>

      <!-- Card body under tabs -->
      <div class="bg-white rounded-2xl shadow-sm p-4 border border-gray-100 min-h-[220px]">
        <!-- ROUTE TAB -->
        <div v-if="activeTab === 'route'">
          <!-- Panel shows only blue button -->
          <StopDetailsPanel mode="route" />
        </div>

        <!-- ITINERARY TAB -->
        <div v-else-if="activeTab === 'itinerary'">
          <!-- Panel shows only purple button -->
          <StopDetailsPanel mode="itinerary" />
        </div>

        <!-- FLOOD TAB -->
        <div v-else>
          <h2 class="text-base font-semibold text-gray-800 mb-3">
            Affected Bus Services
          </h2>

          <div v-if="!selectedFloodId" class="text-sm text-gray-500">
            Click a flood marker on the map to load affected services (within 1 km).
          </div>

          <div v-else>
            <div class="text-sm text-gray-500 mb-2">
              Flood ID:
              <span class="font-medium">{{ selectedFloodId }}</span>
            </div>

            <div v-if="loadingAffected" class="text-sm text-gray-600">Loading…</div>
            <div v-else-if="affectedError" class="text-sm text-red-600">{{ affectedError }}</div>
            <div v-else-if="!affectedServices.length" class="text-sm text-gray-600">
              No services found for this flood.
            </div>

            <ul v-else class="space-y-1 max-h-64 overflow-y-auto">
              <li
                v-for="svc in affectedServices"
                :key="svc"
                class="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50"
              >
                <span class="font-semibold text-blue-700">Service {{ svc }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Controls -->
      <div class="bg-white rounded-2xl shadow-sm p-4 border border-gray-100">
        <ControlsPanel />
      </div>
    </div>

    <!-- RIGHT PANE (Chart + Map) -->
    <div class="col-span-9">
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 h-[calc(100vh-3rem)] p-3 flex flex-col">
        <!-- Chart -->
        <div v-if="chartEntry" class="mb-3">
          <TravelTimeBarChart
            :entry="chartEntry"
            title="Travel Time Scenarios"
          />
        </div>

        <!-- Map -->
        <div class="flex-1 min-h-0 overflow-hidden rounded-xl border border-gray-100">
          <MapCanvas @flood-click="onFloodClick" />
        </div>
      </div>
    </div>
  </div>
</template>
