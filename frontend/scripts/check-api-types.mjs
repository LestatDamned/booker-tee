import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { execPath } from "node:process";
import { fileURLToPath } from "node:url";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const repositoryRoot = dirname(frontendRoot);
const generatedTypesPath = join(
  frontendRoot,
  "app",
  "api",
  "generated",
  "schema.ts",
);
const generatorPath = join(
  frontendRoot,
  "node_modules",
  "openapi-typescript",
  "bin",
  "cli.js",
);
const temporaryRoot = await mkdtemp(join(tmpdir(), "booker-api-contract-"));
const openApiPath = join(temporaryRoot, "openapi.json");
const temporaryTypesPath = join(temporaryRoot, "schema.ts");

try {
  await run("uv", ["run", "python", "scripts/export_openapi.py", openApiPath]);
  await run(execPath, [generatorPath, openApiPath, "-o", temporaryTypesPath]);

  const [committedTypes, generatedTypes] = await Promise.all([
    readFile(generatedTypesPath, "utf8"),
    readFile(temporaryTypesPath, "utf8"),
  ]);
  if (committedTypes !== generatedTypes) {
    throw new Error(
      "Generated API types are stale. Run `npm run api:generate` and commit the result.",
    );
  }
} finally {
  await rm(temporaryRoot, { recursive: true, force: true });
}

function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: repositoryRoot,
      stdio: "inherit",
    });
    child.on("error", reject);
    child.on("exit", (code, signal) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(
        new Error(
          `${command} failed${signal ? ` with signal ${signal}` : ` with exit code ${code}`}.`,
        ),
      );
    });
  });
}
