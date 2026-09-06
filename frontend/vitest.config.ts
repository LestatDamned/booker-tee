import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    projects: [
      {
        test: {
          name: "node",
          include: ["app/**/*.test.ts"],
          environment: "node",
        },
      },
      {
        test: {
          name: "dom",
          include: ["app/**/*.test.tsx"],
          environment: "jsdom",
          setupFiles: ["./app/test/setup.ts"],
        },
      },
    ],
  },
});
