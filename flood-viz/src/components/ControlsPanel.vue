<script setup lang="ts">
import { reactive } from 'vue'
import { useAppStore } from '@/store/app'
import type { Mode } from '@/api/types'

const store = useAppStore()
type Layers = typeof store.layers

const local = reactive<{
  mode: Mode
  layers: Layers
}>({
  mode: store.mode,
  layers: { ...store.layers },
})

function apply() {
  store.setMode(local.mode)
  store.layers = { ...local.layers }
}
</script>

<template>
  <div class="space-y-4">

  </div>
</template>
