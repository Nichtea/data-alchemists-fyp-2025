// vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { viteStaticCopy } from 'vite-plugin-static-copy'
export default defineConfig({
  plugins: [vue(),   viteStaticCopy({
      targets: [
        {
          src: 'node_modules/leaflet/dist/images/*',  // all Leaflet images
          dest: ''                                    // copy to dist root
        }
      ]
    })],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    strictPort: true,
    allowedHosts: [
      '8bf25a918999.ngrok-free.app', 
    ],
    hmr: {
      host: '8bf25a918999.ngrok-free.app',
      protocol: 'wss',   
      clientPort: 443,   
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',  // ← force IPv4
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },

      '/lta': {
        target: 'https://datamall2.mytransport.sg',
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/lta/, '/ltaodataservice'),
        configure: (proxy, _opts) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('AccountKey', 'KGBL20PBRt20LgUPc/yPFA==')
            proxyReq.setHeader('Accept', 'application/json')
          })
        },
      },
    },
  },
  publicDir: 'public',
})
