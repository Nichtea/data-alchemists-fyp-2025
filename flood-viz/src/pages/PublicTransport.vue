<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAppStore } from '@/store/app'
import StopDetailsPanel from '@/components/StopDetailsPanel.vue'
import ControlsPanel from '@/components/ControlsPanel.vue'
import MapCanvas from '@/components/MapCanvas.vue'
import TravelTimeBarChart from '@/components/TravelTimeBarChart.vue'
import { useUrlStateSync } from '@/components/useUrlStateSync'
import { getBusesAffectedByFloods } from '@/api/api'

useUrlStateSync()
const store = useAppStore()

/* ================= Chart (unchanged) ================= */
const chartEntry = computed(() => {
  const o: any = (store as any).serviceRouteOverlay
  const d = o?.directions?.[0]
  if (!d || !Number.isFinite(d.duration_s) || !d.floodSummary) return null
  return { duration_s: Number(d.duration_s), floodSummary: d.floodSummary }
})

/* ================= Tabs ================= */
function activateStops() {
  store.setActiveTab('stops')
  store.setLayerVisible('stops', true)
  store.setLayerVisible('floodEvents', false)
}
function activateFlood() {
  store.setActiveTab('flood')
  store.setLayerVisible('stops', false)
  store.setLayerVisible('floodEvents', true)
}

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
  selectedFloodId.value = payload.floodId
  loadingAffected.value = true
  affectedError.value = null
  affectedServices.value = []

  try {
    const res: any = await getBusesAffectedByFloods(payload.floodId)

    let names: string[] = []

    if (Array.isArray(res)) {
      // API returned an array. It could be strings OR objects.
      if (typeof res[0] === 'string') {
        names = res as string[]
      } else {
        names = (res as any[]).map(normalizeServiceName).filter(Boolean) as string[]
      }
    } else if (res && Array.isArray(res.affected_bus_services)) {
      // API returned an object with affected_bus_services
      names = res.affected_bus_services as string[]
    }

    // unique + human sort
    affectedServices.value = [...new Set(names)].sort((a, b) =>
      String(a).localeCompare(String(b), undefined, { numeric: true })
    )
  } catch (e: any) {
    affectedError.value = e?.message || 'Failed to load affected services.'
  } finally {
    loadingAffected.value = false
  }
}

</script>

<template>
  <div class="h-full grid grid-cols-12 gap-4 p-4">
    <!-- LEFT -->
    <div class="col-span-3 space-y-4">
      <!-- Tabs -->
      <div class="bg-white rounded shadow p-2">
        <div class="flex gap-2">
          <button
            class="px-3 py-1 rounded-full text-sm"
            :class="store.activeTab === 'stops' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'"
            @click="activateStops"
          >
            Stops
          </button>
          <button
            class="px-3 py-1 rounded-full text-sm"
            :class="store.activeTab === 'flood' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'"
            @click="activateFlood"
          >
            Flood
          </button>
        </div>
      </div>

      <!-- Stop details when in Stops tab -->
      <StopDetailsPanel v-if="store.activeTab === 'stops'" />

      <!-- Affected bus services when in Flood tab -->
      <div v-else class="bg-white rounded shadow p-3">
        <div class="text-sm font-semibold mb-2">Affected bus services</div>

        <div v-if="!selectedFloodId" class="text-xs text-gray-500">
          Click a flood marker on the map to load affected services (within 1 km).
        </div>

        <div v-else>
          <div class="text-xs text-gray-500 mb-2">
            Flood ID: <span class="font-medium">{{ selectedFloodId }}</span>
          </div>

          <div v-if="loadingAffected" class="text-sm text-gray-600">Loading…</div>
          <div v-else-if="affectedError" class="text-sm text-red-600">{{ affectedError }}</div>
          <div v-else-if="!affectedServices.length" class="text-sm text-gray-600">
            No services found for this flood.
          </div>

          <ul v-else class="space-y-1">
            <li
              v-for="svc in affectedServices"
              :key="svc"
              class="px-2 py-1 border rounded text-sm flex items-center justify-between"
            >
              <span class="font-medium">Service {{ svc }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Controls -->
      <div class="bg-white rounded shadow p-3">
        <ControlsPanel />
      </div>
    </div>

    <!-- RIGHT: Chart + Map -->
    <div class="col-span-9">
      <div class="bg-white rounded shadow h-[calc(100vh-2.5rem)] p-2 flex flex-col">
        <!-- Optional chart -->
        <div v-if="chartEntry" class="mb-2">
          <TravelTimeBarChart :entry="chartEntry" title="Travel time scenarios" />
        </div>

        <!-- Map fills remaining space -->
        <div class="flex-1 min-h-0">
          <!-- Listen for flood marker clicks -->
          <MapCanvas @flood-click="onFloodClick" />
        </div>
      </div>
    </div>
  </div>
</template>
