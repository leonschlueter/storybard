import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // OrbStack gives every container an auto-generated <service>.<project>.orb.local
    // hostname (e.g. web.storybard.orb.local) — Vite's default Host-header allowlist
    // blocks anything not localhost/127.0.0.1 unless listed here. Local dev only.
    allowedHosts: ['.orb.local'],
  },
})
