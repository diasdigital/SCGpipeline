import { defineConfig, loadEnv } from 'vite';
import { fileURLToPath, URL } from 'node:url';
import vue from '@vitejs/plugin-vue';

export default defineConfig(({ mode }) => {
    const rootDir = fileURLToPath(new URL('..', import.meta.url));
    const env = loadEnv(mode, rootDir, '');
    const backendUrl = env.BACKEND_URL || 'http://127.0.0.1:8000';
    const extraHosts = (env.VITE_ALLOWED_HOSTS || '')
        .split(',')
        .map((h) => h.trim())
        .filter(Boolean);

    return {
        envDir: rootDir,
        plugins: [vue()],

        server: {
            allowedHosts: extraHosts,
            proxy: {
                '/api': {
                    target: backendUrl,
                    changeOrigin: true,
                    secure: false,
                },
            },
        },

        resolve: {
            alias: {
                '@': fileURLToPath(new URL('./src', import.meta.url)),
            },
        },
    };
});
