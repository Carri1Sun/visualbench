import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const proxy = {
  '/api': { target: 'http://127.0.0.1:4174', changeOrigin: true },
};

export default defineConfig({
  plugins: [react()],
  server: { port: 4173, strictPort: true, proxy },
  preview: { port: 4173, strictPort: true, proxy },
});
