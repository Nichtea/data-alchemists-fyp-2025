<script setup lang="ts">
</script>

<template>
  <div class="h-screen w-screen bg-gray-100">
    <header class="h-12 bg-white border-b flex items-center px-4 gap-6">
      <h1 class="font-semibold">Flood-Viz</h1>
      <nav class="text-sm flex gap-4">
        <RouterLink to="/">Home</RouterLink>
        <RouterLink to="/about">About</RouterLink>
      </nav>
    </header>
    <RouterView />
  </div>
</template>
