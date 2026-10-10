import { svelte } from "@sveltejs/vite-plugin-svelte";
import { svelteTesting } from "@testing-library/svelte/vite";
import { defineConfig } from "vitest/config";

// The build goes to web/dist, which src/app/server.py serves to the window.
// Everything is emitted as files (no inline script or style), since the
// window's Content-Security-Policy allows nothing inline.
export default defineConfig({
  // svelteTesting: under Vitest, resolve Svelte for the browser and clean up after each test.
  plugins: [svelte(), svelteTesting()],
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2022",
    assetsInlineLimit: 0,
    modulePreload: { polyfill: false },
    reportCompressedSize: false,
  },
  server: { port: 5173, strictPort: true },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts"],
    setupFiles: ["tests/setup.ts"],
  },
});
