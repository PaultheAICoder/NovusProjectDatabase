/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 6700,
    host: true,
    allowedHosts: ["localhost", ".ngrok-free.dev", ".ngrok.io"],
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET || "http://localhost:6701",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes("node_modules")) {
            // React core
            if (id.includes("react-dom") || id.includes("react-router")) {
              return "vendor-react";
            }
            if (id.includes("/react/") && !id.includes("@radix-ui")) {
              return "vendor-react";
            }
            // TanStack
            if (id.includes("@tanstack")) {
              return "vendor-tanstack";
            }
            // Radix UI
            if (id.includes("@radix-ui")) {
              return "vendor-radix";
            }
            // Form libraries
            if (
              id.includes("react-hook-form") ||
              id.includes("@hookform") ||
              id.includes("zod")
            ) {
              return "vendor-form";
            }
            // Icons
            if (id.includes("lucide-react")) {
              return "vendor-icons";
            }
            // Dropzone
            if (id.includes("react-dropzone")) {
              return "vendor-dropzone";
            }
            // Date utilities
            if (id.includes("date-fns")) {
              return "vendor-utils";
            }
          }
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./tests/setup.ts",
    exclude: ["**/node_modules/**", "**/tests/e2e/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
    },
  },
});
