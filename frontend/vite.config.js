import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    clearMocks: true,
  },
  server: {
    port: 5173,
    /*
     * 개발 환경 프록시 — /api/* 요청을 Spring Boot(8080)로 전달.
     * 브라우저는 같은 origin(5173)으로 요청하므로 CORS 불필요.
     * 프로덕션에서는 VITE_API_BASE_URL 환경변수로 실제 서버 URL 지정.
     */
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
