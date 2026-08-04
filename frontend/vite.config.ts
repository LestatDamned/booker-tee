import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";

const apiTarget = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [reactRouter()],
  preview: {
    host: "127.0.0.1",
  },
  server: {
    proxy: {
      "/api": apiTarget,
    },
  },
});
