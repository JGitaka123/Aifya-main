import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const configDirectory = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  css: {
    postcss: {},
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/__tests__/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
  resolve: {
    alias: {
      "@": resolve(configDirectory, "./src"),
      "@aifya/shared": resolve(configDirectory, "../../packages/shared/src"),
    },
  },
});
