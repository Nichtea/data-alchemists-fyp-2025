<!-- src/pages/LandingPage.vue -->
<script setup lang="ts">
import { ref } from 'vue'

const dark = ref(false)

function toggleDark() {
  dark.value = !dark.value
  document.documentElement.classList.toggle('dark', dark.value)
}
</script>

<template>
  <div class="min-h-screen bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100">
    <!-- HERO -->
    <section class="py-20 px-4 sm:px-6 lg:px-8 text-center max-w-4xl mx-auto">
      <h1 class="text-4xl sm:text-5xl font-extrabold">
        Smarter Routes, Safer Commutes
      </h1>
      <p class="mt-4 text-slate-600 dark:text-slate-300 text-lg">
        Discover how flooding impacts Singapore’s transport network — visualize affected roads and bus routes in real time with our interactive platform.
      </p>
      <div class="mt-6 flex justify-center gap-4">
        <a href="#video" class="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700">Watch Demo</a>
        <a href="#features" class="px-6 py-3 border border-slate-300 dark:border-slate-600 rounded-lg font-semibold hover:bg-slate-100 dark:hover:bg-slate-800">Learn More</a>
      </div>
    </section>

    <!-- FEATURES -->
    <section id="features" class="py-16 bg-slate-50 dark:bg-slate-800/50">
      <div class="max-w-6xl mx-auto px-4">
        <h2 class="text-3xl font-extrabold text-center">Key Features</h2>
        <div class="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          <div class="p-6 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
            <div class="text-3xl mb-2">🚌</div>
            <h3 class="font-semibold text-lg mb-1">Bus Stop Visualization</h3>
            <p class="text-slate-600 dark:text-slate-300 text-sm">
              Plot all bus stops on an interactive Leaflet map with hover details and clickable routes.
            </p>
          </div>
          <div class="p-6 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
            <div class="text-3xl mb-2">🌧️</div>
            <h3 class="font-semibold text-lg mb-1">Flood Event Layers</h3>
            <p class="text-slate-600 dark:text-slate-300 text-sm">
              Overlay flood polygons and points dynamically. Tooltip caching ensures instant details.
            </p>
          </div>
          <div class="p-6 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
            <div class="text-3xl mb-2">🗺️</div>
            <h3 class="font-semibold text-lg mb-1">Route & Travel Delay Analysis</h3>
            <p class="text-slate-600 dark:text-slate-300 text-sm">
              Compare baseline vs flooded travel times across different road segments with custom styling.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- VIDEO SECTION -->
    <section id="video" class="py-16">
      <div class="max-w-6xl mx-auto px-4 text-center">
        <h2 class="text-3xl font-extrabold mb-6">Demo Video</h2>
        <div class="relative aspect-[16/9] w-full max-w-4xl mx-auto rounded-xl overflow-hidden shadow-lg">
          <!-- Replace the URL below with your own YouTube video link -->
          <iframe
            class="w-full h-full"
            src="https://www.youtube.com/embed/CDWqFX6OvJc?si=F0alJ2AshklIZaVp"
            title="TransitFlood Demo Video"
            frameborder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowfullscreen>
          </iframe>
        </div>
      </div>
    </section>

    <!-- FOOTER -->
    <footer class="py-8 border-t border-slate-200 dark:border-slate-700 text-center text-sm text-slate-500 dark:text-slate-400">
      © {{ new Date().getFullYear() }} TransitFlood. Built with Vue + Tailwind CSS.
    </footer>
  </div>
</template>

<style scoped>
.aspect-\[16\/9\] { aspect-ratio: 16 / 9; }
</style>
