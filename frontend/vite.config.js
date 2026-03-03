import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Proxy all /api requests to Flask backend during local development.
      // This is ONLY active when running `npm run dev` - it has no effect
      // on the production build. In production, Flask serves both the
      // built React files AND the API from the same server, so no proxy needed.
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      }
    }
  },
  build: {
    // Output built files to frontend/dist
    // Flask is configured to serve static files from this folder.
    // Railway runs `npm run build` before starting the Flask server,
    // so this folder will exist by the time Flask starts.
    outDir: 'dist',
  }
})