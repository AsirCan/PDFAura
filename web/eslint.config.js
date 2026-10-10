import js from "@eslint/js";
import svelte from "eslint-plugin-svelte";
import globals from "globals";
import ts from "typescript-eslint";

// Rules that keep the window safe under its Content-Security-Policy and
// keep every colour and every visible string in one place (#25):
// - no eval / new Function / {@html}: the CSP's eval ban stops working once
//   pywebview injects its bridge (spikes/faz0/RAPOR.md), so lint enforces it
// - no colour literals outside the generated theme
export default ts.config(
  { ignores: ["dist/", "node_modules/", "src/lib/generated/"] },
  js.configs.recommended,
  ...ts.configs.recommended,
  ...svelte.configs["flat/recommended"],
  {
    languageOptions: { globals: { ...globals.browser } },
    rules: {
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "svelte/no-at-html-tags": "error",
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
  {
    files: ["**/*.svelte", "**/*.svelte.ts"],
    languageOptions: { parserOptions: { parser: ts.parser } },
  },
  {
    files: ["tests/**", "vite.config.ts", "eslint.config.js", "svelte.config.js"],
    languageOptions: { globals: { ...globals.node } },
  },
);
