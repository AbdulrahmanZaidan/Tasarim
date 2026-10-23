import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// GitHub Pages: depo adı alt dizin olarak kullanılır (ör. /Tasarim1/).
// Gerekirse VITE_BASE ortam değişkeni ile değiştirilebilir.
export default defineConfig(async ({ mode }) => {
  const plugins = [react()];
  if (mode === 'single') {
    const { viteSingleFile } = await import('vite-plugin-singlefile');
    plugins.push(viteSingleFile());
  }
  const base =

process.env.VITE_BASE ?? (mode === 'ghpages' ? '/Tasarim/' : mode === 'single' ? './' : '/');
  return {
    base,
    plugins,
    build: {
      // Tarayıcı önbelleği için kütüphaneler ayrı paketlerde tutulur (uygulama kodu değişince yeniden indirilmez)
      rollupOptions: mode === 'single' ? undefined : {
        output: {
          manualChunks(id: string) {
            if (id.includes('node_modules/@supabase')) return 'vendor-supabase';
            if (/node_modules\/(react|react-dom|react-router|react-router-dom|@remix-run|scheduler)\//.test(id)) return 'vendor-react';
            if (id.includes('node_modules/lucide-react')) return 'vendor-icons';
            return undefined;
          },
        },
      },
    },
  };
});
