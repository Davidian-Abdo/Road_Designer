import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { createRequire } from "node:module";

// Cloudflare Pages build: `npm run build`, output dir `dist`.
// See ./README.md for the exact Pages project settings.
const pkg = createRequire(import.meta.url)("./package.json") as { version: string };

export default defineConfig({
  plugins: [react()],
  define: {
    // Build-time app version, surfaced beside the "Powered by Beamstack" credit
    // in src/components/SiteFooter.tsx. Kept in sync with package.json "version".
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "dist",
  },
});
