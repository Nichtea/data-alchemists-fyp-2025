<script setup lang="ts">
import { useAppStore } from '@/store/app'
import StopDetailsPanel from '@/components/StopDetailsPanel.vue'
import FloodDetailsPanel from '@/components/FloodDetailsPanel.vue'
import ControlsPanel from '@/components/ControlsPanel.vue'
import MapCanvas from '@/components/MapCanvas.vue'
import { useUrlStateSync } from '@/components/useUrlStateSync'
useUrlStateSync()

const store = useAppStore()

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
</script>

<template>
  <div class="h-full grid grid-cols-12 gap-4 p-4">
    <div class="col-span-3 space-y-4">
      <div class="bg-white rounded shadow p-2">
        <div class="flex gap-2">
          <button class="px-3 py-1 rounded-full text-sm bg-gray-100 text-gray-500 cursor-default">mobility</button>
          <button
            class="px-3 py-1 rounded-full text-sm"
            :class="store.activeTab === 'stops' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'"
            @click="activateStops"
          >
            stops
          </button>
          <button class="px-3 py-1 rounded-full text-sm bg-gray-100 text-gray-500 cursor-default">routes</button>
          <button
            class="px-3 py-1 rounded-full text-sm"
            :class="store.activeTab === 'flood' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'"
            @click="activateFlood"
          >
            flood
          </button>
        </div>
      </div>

      <StopDetailsPanel v-if="store.activeTab === 'stops'" />
      <FloodDetailsPanel v-else-if="store.activeTab === 'flood'" />

      <div class="bg-white rounded shadow p-3">
        <ControlsPanel />
      </div>
    </div>

    <div class="col-span-9">
      <div class="bg-white rounded shadow h-[calc(100vh-2.5rem)] p-2">
        <MapCanvas />
      </div>
    </div>
  </div>
</template>
