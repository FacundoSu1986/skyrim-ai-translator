import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { siteConfig, getBasePath } from './site.config.js'

// https://vite.dev/config/
export default defineConfig({
  base: getBasePath(siteConfig.siteUrl),
  plugins: [react()],
})
