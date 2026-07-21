import { readdir, readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const appRoot = join(frontendRoot, "app");
const themesPath = join(appRoot, "styles", "themes.css");

const requiredThemeTokens = [
  "--color-bg-canvas",
  "--color-bg-surface",
  "--color-bg-elevated",
  "--color-bg-interactive",
  "--color-text-primary",
  "--color-text-secondary",
  "--color-text-inverse",
  "--color-border-default",
  "--color-border-strong",
  "--color-focus-ring",
  "--color-accent",
  "--color-accent-strong",
  "--color-status-success",
  "--color-status-warning",
  "--color-status-danger",
  "--color-money-income",
  "--color-money-expense",
  "--color-money-transfer",
  "--color-money-profit",
  "--color-money-adjustment",
  "--color-working-surface",
  "--color-target-surface",
  "--color-recent-surface",
  "--color-overlay",
  "--shadow-surface",
];

async function findCssModules(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nestedFiles = await Promise.all(
    entries.map(async (entry) => {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) {
        return findCssModules(path);
      }
      return entry.name.endsWith(".module.css") ? [path] : [];
    }),
  );
  return nestedFiles.flat();
}

function themeBlock(stylesheet, selector) {
  const start = stylesheet.indexOf(selector);
  if (start === -1) {
    throw new Error(`Theme selector ${selector} is missing.`);
  }
  const nextTheme = stylesheet.indexOf("[data-theme=", start + selector.length);
  return stylesheet.slice(start, nextTheme === -1 ? undefined : nextTheme);
}

const cssModules = await findCssModules(appRoot);
const rawPalettePattern = /#[0-9a-f]{3,8}\b|(?:rgb|hsl)a?\(/i;

for (const path of cssModules) {
  const content = await readFile(path, "utf8");
  if (rawPalettePattern.test(content)) {
    throw new Error(`Raw palette value found outside theme file: ${path}`);
  }
}

const themes = await readFile(themesPath, "utf8");
for (const selector of [
  '[data-theme="catppuccin-mocha"]',
  '[data-theme="test"]',
]) {
  const block = themeBlock(themes, selector);
  for (const token of requiredThemeTokens) {
    if (!block.includes(`${token}:`)) {
      throw new Error(`${selector} does not define ${token}.`);
    }
  }
}

if (cssModules.length === 0) {
  throw new Error("No CSS Modules were found.");
}
