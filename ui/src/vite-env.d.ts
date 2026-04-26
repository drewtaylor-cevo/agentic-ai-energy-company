/// <reference types="vite/client" />

// Injected at build time by ui/vite.config.ts `define` (Phase 8 D-15).
// Resolves from `git rev-parse --short HEAD` or falls back to "unknown".
declare const __GIT_SHA__: string;
