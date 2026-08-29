import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
// Cloudflare Pages build: `npm run build`, output dir `dist`.
// See ./README.md for the exact Pages project settings.
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    build: {
        outDir: "dist",
    },
});
