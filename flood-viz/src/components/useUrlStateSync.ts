// src/components/useUrlStateSync.ts
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/store/app'
import type { Scenario, Mode } from '@/api/types'

export function useUrlStateSync() {
  const store = useAppStore()
  const route = useRoute()
  const router = useRouter()

  // 1) On first mount: URL -> Store
  onMounted(() => {
    const q = route.query
    const mode = (q.mode as Mode) || 'car'

    // query flags: '1' -> true, '0' -> false; default to true if missing
    const stops = q.stops === '0' ? false : true
    const delay = q.delay === '0' ? false : true
    const flooded = q.flooded === '0' ? false : true
    const criticality = q.criticality === '0' ? false : true


    store.setMode(mode)
    store.setLayerVisible('stops', stops)
    store.setLayerVisible('delay', delay)
    store.setLayerVisible('flooded', flooded)
    store.setLayerVisible('criticality', criticality)
  })

  // 2) Store changes -> URL
  watch(
    () => [
      store.mode,
      store.layers.stops,
      store.layers.delay,
      store.layers.flooded,
      store.layers.criticality,
    ],
    () => {
      router.replace({
        query: {
          mode: store.mode,
          stops: store.layers.stops ? '1' : '0',
          delay: store.layers.delay ? '1' : '0',
          flooded: store.layers.flooded ? '1' : '0',
          criticality: store.layers.criticality ? '1' : '0',
        },
      })
    },
    { immediate: true }
  )
}
