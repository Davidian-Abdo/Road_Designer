/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Injected by Vite's `define` (see vite.config.ts) — the package.json version,
// shown beside the "Powered by Beamstack" attribution in SiteFooter.tsx.
declare const __APP_VERSION__: string;
