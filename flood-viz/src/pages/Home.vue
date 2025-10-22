<!-- src/pages/LandingPage.vue -->
<script setup lang="ts">
</script>

<template>
  <!-- FULL BLEED WRAPPER -->
  <div class="full-bleed w-screen min-h-screen text-slate-800 relative overflow-hidden bg-gradient-to-b from-sky-100 via-sky-50 to-slate-100">
    <!-- ===== BACKGROUND LAYERS ===== -->
    <div aria-hidden="true" class="absolute inset-0 w-full overflow-hidden">
      <!-- Soft color blobs -->
      <div class="absolute -top-40 -left-40 size-[520px] rounded-full bg-sky-300/30 blur-3xl"></div>
      <div class="absolute -bottom-20 left-1/2 -translate-x-1/2 size-[640px] rounded-full bg-indigo-300/20 blur-3xl"></div>
      <div class="absolute -right-40 top-1/4 size-[480px] rounded-full bg-cyan-300/25 blur-3xl"></div>

      <!-- Animated raindrop pattern -->
      <svg aria-hidden="true" class="absolute inset-0 opacity-[0.18] animate-rain" width="100%" height="100%" preserveAspectRatio="none">
        <defs>
          <pattern id="drops" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M8 10c0-3 4-3 4 0 0 2-2 4-2 4s-2-2-2-4z" fill="#38bdf8" />
            <path d="M28 30c0-3 4-3 4 0 0 2-2 4-2 4s-2-2-2-4z" fill="#38bdf8" />
            <circle cx="24" cy="12" r="1.2" fill="#38bdf8" />
            <circle cx="14" cy="28" r="1.2" fill="#38bdf8" />
          </pattern>
        </defs>
        <rect x="0" y="0" width="100%" height="100%" fill="url(#drops)" />
      </svg>

      <!-- Mist / Vignette -->
      <div class="absolute inset-x-0 top-0 h-48 bg-gradient-to-b from-white/80 to-transparent"></div>

      <!-- Waves at bottom -->
      <div class="absolute inset-x-0 bottom-0">
        <svg class="w-full h-28 block opacity-70" viewBox="0 0 1440 160" preserveAspectRatio="none">
          <path
            d="M0,64 C160,128 320,0 480,48 C640,96 800,176 960,144 C1120,112 1280,48 1440,96 L1440,160 L0,160 Z"
            fill="url(#waveFill)"
          />
          <defs>
            <linearGradient id="waveFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stop-color="#60a5fa" stop-opacity="0.45" />
              <stop offset="100%" stop-color="#0ea5e9" stop-opacity="0.35" />
            </linearGradient>
          </defs>
        </svg>
      </div>
    </div>

    <!-- ===== PAGE CONTENT ===== -->
    <main class="relative z-10">
      <!-- HERO -->
      <section class="py-24 px-4 sm:px-6 lg:px-8 text-center max-w-5xl mx-auto">
        <h1 class="text-4xl sm:text-5xl font-extrabold tracking-tight drop-shadow-sm">
          Smarter Routes, Safer Commutes
        </h1>
        <p class="mt-4 text-slate-700/90 text-lg leading-relaxed">
          Discover how flooding impacts Singapore’s transport network — visualize affected roads and bus routes
          in real time with our interactive platform.
        </p>

        <div
          class="mt-8 mx-auto w-fit rounded-2xl border border-slate-300 bg-white/70 backdrop-blur-md shadow-md">
          <div class="p-3 flex items-center gap-2 text-sm text-slate-600">
            💡 Flood-aware routing • Live overlays • Delay analytics
          </div>
        </div>

        <div class="mt-7 flex justify-center gap-4">
          <a
            href="#video"
            class="px-6 py-3 rounded-xl font-semibold bg-blue-600 text-white shadow-md hover:bg-blue-700 transition"
          >
            Watch Demo
          </a>
          <a
            href="#features"
            class="px-6 py-3 rounded-xl font-semibold border border-slate-300 bg-white/70 backdrop-blur hover:bg-slate-100 transition"
          >
            Learn More
          </a>
        </div>
      </section>

      <!-- FEATURES -->
      <section id="features" class="py-16 bg-white/70 backdrop-blur">
        <div class="max-w-6xl mx-auto px-4">
          <h2 class="text-3xl font-extrabold text-center">Key Features</h2>
          <div class="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <div class="card">
              <div class="text-3xl mb-2">🚌</div>
              <h3 class="font-semibold text-lg mb-1">Bus Stop Visualization</h3>
              <p class="muted">
                Plot all bus stops on an interactive Leaflet map with hover details and clickable routes.
              </p>
            </div>
            <div class="card">
              <div class="text-3xl mb-2">🌧️</div>
              <h3 class="font-semibold text-lg mb-1">Flood Event Layers</h3>
              <p class="muted">
                Overlay flood polygons and points dynamically. Tooltip caching ensures instant details.
              </p>
            </div>
            <div class="card">
              <div class="text-3xl mb-2">🗺️</div>
              <h3 class="font-semibold text-lg mb-1">Route & Travel Delay Analysis</h3>
              <p class="muted">
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
          <div class="video-frame">
            <iframe
              class="w-full h-full"
              src="https://www.youtube.com/embed/CDWqFX6OvJc?si=F0alJ2AshklIZaVp"
              title="Flood-Viz Demo Video"
              frameborder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen
            />
          </div>
        </div>
      </section>
    </main>

    <!-- FOOTER -->
    <footer class="relative z-10 py-10 border-t border-slate-200 text-center text-sm text-slate-600 bg-white/70 backdrop-blur">
      © {{ new Date().getFullYear() }} Flood-Viz. All rights reserved.
    </footer>
  </div>
</template>

<style scoped>
/* Force full-bleed even inside centered layouts */
.full-bleed {
  position: relative;
  left: 50%;
  right: 50%;
  margin-left: -50vw;
  margin-right: -50vw;
  width: 100vw;
}

.muted { @apply text-slate-600 text-sm; }
.card {
  @apply p-6 rounded-xl border border-slate-200 bg-white/80 backdrop-blur shadow-sm hover:shadow transition;
}
.video-frame {
  @apply relative aspect-[16/9] w-full max-w-4xl mx-auto rounded-xl overflow-hidden shadow-lg bg-slate-200/40 backdrop-blur;
}

/* Rain animation */
@keyframes rainShift {
  0%   { transform: translate3d(0, 0, 0); }
  100% { transform: translate3d(-80px, 120px, 0); }
}
.animate-rain { animation: rainShift 18s linear infinite; }
@media (prefers-reduced-motion: reduce) {
  .animate-rain { animation: none !important; }
}
:where(h1,h2,h3) { text-shadow: 0 1px 0 rgba(255,255,255,0.15); }
</style>

<!-- Global tweaks (not scoped) to avoid stray gutters/scrollbars -->
<style>
html, body { overflow-x: hidden; background: #f8fafc; } /* Tailwind slate-50 */
</style>
