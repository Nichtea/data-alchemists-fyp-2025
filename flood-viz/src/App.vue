<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()
const navItems = [
  { name: 'Home', path: '/' },
  { name: 'About', path: '/about' },
  { name: 'Public Transport', path: '/PublicTransport' },
  { name: 'Private Transport', path: '/PrivateTransport' },
  { name: 'Flood', path: '/Flood' },
]

const isActive = (path: string) => computed(() => route.path === path)
</script>

<template>
  <div class="min-h-screen w-screen bg-gray-50 flex flex-col">
    <!-- Header -->
    <header
      class="h-16 bg-white shadow-sm border-b flex items-center justify-between px-10"
    >
      <h1 class="font-bold text-2xl text-blue-600 tracking-wide">
        Flood-Viz
      </h1>

      <nav class="text-base flex items-center gap-8">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="[ 
            'transition-colors duration-200 hover:text-blue-600',
            isActive(item.path).value ? 'text-blue-600 font-semibold' : 'text-gray-700',
          ]"
        >
          {{ item.name }}
        </RouterLink>
      </nav>
    </header>

    <!-- Main Content -->
    <main class="flex-1 overflow-y-auto p-8">
      <RouterView />
    </main>

    
  </div>
</template>
