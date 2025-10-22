<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAppStore } from '@/store/app'
import StopDetailsPanel from '@/components/StopDetailsPanel.vue'
import ControlsPanel from '@/components/ControlsPanel.vue'
import MapCanvas from '@/components/MapCanvas.vue'
import TravelTimeBarChart from '@/components/TravelTimeBarChart.vue'
import { useUrlStateSync } from '@/components/useUrlStateSync'
import { getBusesAffectedByFloods } from '@/api/api'

useUrlStateSync()
const store = useAppStore()

/* ================= Chart ================= */
const chartEntry = computed(() => {
  const o: any = (store as any).serviceRouteOverlay
  const d = o?.directions?.[0]
  if (!d || !Number.isFinite(d.duration_s) || !d.floodSummary) return null
  return { duration_s: Number(d.duration_s), floodSummary: d.floodSummary }
})

/* ================= Tabs ================= */
function clearFloodUI() {
  selectedFloodId.value = null
  affectedServices.value = []
  affectedError.value = null
  loadingAffected.value = false
}

function activateStops() {
  store.setActiveTab('stops')
  store.setLayerVisible('stops', true)
  store.setLayerVisible('floodEvents', false)
  clearFloodUI() // ← hide & reset flood UI/state
}

function activateFlood() {
  store.setActiveTab('flood')
  store.setLayerVisible('stops', false)
  store.setLayerVisible('floodEvents', true)
}

// Safety: if tab changes elsewhere, still clear flood UI
watch(() => store.activeTab, (tab) => {
  if (tab !== 'flood') clearFloodUI()
})

/* ================= Affected bus services ================= */
const selectedFloodId = ref<number | null>(null)
const affectedServices = ref<string[]>([])
const loadingAffected = ref(false)
const affectedError = ref<string | null>(null)

function normalizeServiceName(row: any): string | null {
  return (
    row?.service_no ??
    row?.ServiceNo ??
    row?.service ??
    row?.Service ??
    row?.route ??
    null
  )
}

async function onFloodClick(payload: { floodId: number }) {
  // Ignore flood clicks unless Flood tab is active
  if (store.activeTab !== 'flood') return

  selectedFloodId.value = payload.floodId
  loadingAffected.value = true
  affectedError.value = null
  affectedServices.value = []

  try {
    const res: any = await getBusesAffectedByFloods(payload.floodId)

    // Expecting: { results: [ { affected_bus_services: string[], candidate_stops: [...], flood_id: number } ] }
    if (!res || typeof res !== 'object' || !Array.isArray(res.results)) {
      throw new Error('Unexpected response shape (missing results).')
    }

    const first = res.results[0]
    if (!first || typeof first !== 'object') {
      // No results → no affected services
      affectedServices.value = []
      return
    }

    // Prefer backend flood_id if present
    if (first.flood_id != null && !Number.isNaN(Number(first.flood_id))) {
      selectedFloodId.value = Number(first.flood_id)
    }

    const list = Array.isArray(first.affected_bus_services)
      ? first.affected_bus_services
      : []

    // normalize → unique → sort numeric-aware
    const names = list
      .map((s: any) => String(s).trim())
      .filter(Boolean)

    affectedServices.value = [...new Set(names)].sort((a, b) =>
      String(a).localeCompare(String(b), undefined, { numeric: true })
    )

    // If you later want candidate stops, you can read first.candidate_stops here.
    // (Not stored to state since you said old shapes aren’t needed.)
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

</script>

<template>
  <div class="h-full grid grid-cols-12 gap-4 p-6 bg-gray-50">
    <!-- LEFT -->
    <div class="col-span-3 space-y-4">
      <!-- Tabs -->
      <div class="bg-white rounded-2xl shadow-sm p-3 border border-gray-100">
        <div class="flex gap-2">
          <button
            class="flex-1 py-2 rounded-lg font-medium transition-colors duration-200"
            :class="store.activeTab === 'stops'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
            @click="activateStops"
          >
            Stops
          </button>
          <button
            class="flex-1 py-2 rounded-lg font-medium transition-colors duration-200"
            :class="store.activeTab === 'flood'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
            @click="activateFlood"
          >
            Flood
          </button>
        </div>
      </div>

      <!-- Left card: Stops OR Flood (never both) -->
      <div class="bg-white rounded-2xl shadow-sm p-4 border border-gray-100">
        <!-- Stops content -->
        <StopDetailsPanel v-if="store.activeTab === 'stops'" />

        <!-- Flood content -->
        <div v-else>
          <h2 class="text-base font-semibold text-gray-800 mb-3">
            Affected Bus Services
          </h2>

          <div v-if="!selectedFloodId" class="text-sm text-gray-500">
            Click a flood marker on the map to load affected services (within 1 km).
          </div>

          <div v-else>
            <div class="text-sm text-gray-500 mb-2">
              Flood ID: <span class="font-medium">{{ selectedFloodId }}</span>
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

    <!-- RIGHT: Chart + Map -->
    <div class="col-span-9">
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 h-[calc(100vh-3rem)] p-3 flex flex-col">
        <!-- Optional chart -->
        <div v-if="chartEntry" class="mb-3">
          <TravelTimeBarChart :entry="chartEntry" title="Travel Time Scenarios" />
        </div>

        <!-- Map fills remaining space -->
        <div class="flex-1 min-h-0 overflow-hidden rounded-xl border border-gray-100">
          <MapCanvas @flood-click="onFloodClick" />
        </div>
      </div>
    </div>
  </div>
</template>
