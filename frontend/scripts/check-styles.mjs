import { readdir, readFile } from "node:fs/promises";
import { basename, dirname, extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const appRoot = join(frontendRoot, "app");
const themesRoot = join(appRoot, "styles", "themes");
const themeIndexPath = join(themesRoot, "index.css");

const requiredThemeTokens = [
  "--color-bg-canvas",
  "--color-bg-surface",
  "--color-bg-elevated",
  "--color-bg-interactive",
  "--color-text-primary",
  "--color-text-secondary",
  "--color-text-inverse",
  "--color-border-default",
  "--color-border-control",
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
  "--color-category",
  "--color-working-surface",
  "--color-target-surface",
  "--color-recent-surface",
  "--color-overlay",
  "--shadow-surface",
];

const contrastChecks = [
  {
    foregrounds: ["--color-text-primary", "--color-text-secondary"],
    backgrounds: [
      "--color-bg-canvas",
      "--color-bg-surface",
      "--color-bg-elevated",
    ],
    minimum: 4.5,
    purpose: "body text",
  },
  {
    foregrounds: [
      "--color-focus-ring",
      "--color-accent",
      "--color-accent-strong",
      "--color-border-control",
      "--color-border-strong",
    ],
    backgrounds: ["--color-bg-canvas", "--color-bg-surface"],
    minimum: 3,
    purpose: "UI boundary or focus",
  },
  {
    foregrounds: [
      "--color-status-success",
      "--color-status-warning",
      "--color-status-danger",
      "--color-money-income",
      "--color-money-expense",
      "--color-money-transfer",
      "--color-money-profit",
      "--color-money-adjustment",
      "--color-category",
    ],
    backgrounds: [
      "--color-bg-canvas",
      "--color-bg-surface",
      "--color-bg-elevated",
    ],
    minimum: 3,
    purpose: "large text or financial state",
  },
  {
    foregrounds: ["--color-text-inverse"],
    backgrounds: ["--color-accent"],
    minimum: 4.5,
    purpose: "primary action text",
  },
];

async function findFiles(directory, predicate) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nestedFiles = await Promise.all(
    entries.map(async (entry) => {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) {
        return findFiles(path, predicate);
      }
      return predicate(path) ? [path] : [];
    }),
  );
  return nestedFiles.flat();
}

function parseDeclarations(stylesheet) {
  return new Map(
    Array.from(stylesheet.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g), (match) => [
      match[1],
      match[2].trim(),
    ]),
  );
}

function resolveToken(token, declarations, seen = new Set()) {
  if (seen.has(token)) {
    throw new Error(`Circular token reference found at ${token}.`);
  }
  const value = declarations.get(token);
  if (value === undefined) {
    throw new Error(`Token ${token} references a missing value.`);
  }
  const reference = value.match(/^var\((--[\w-]+)\)$/);
  if (!reference) {
    return value;
  }
  return resolveToken(reference[1], declarations, new Set([...seen, token]));
}

function parseHexColor(value, context) {
  const match = value.match(/^#([0-9a-f]{6})$/i);
  if (!match) {
    throw new Error(
      `${context} must resolve to an opaque six-digit hex color, got ${value}.`,
    );
  }
  return [0, 2, 4].map((offset) =>
    Number.parseInt(match[1].slice(offset, offset + 2), 16),
  );
}

function relativeLuminance(rgb) {
  const [red, green, blue] = rgb.map((channel) => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrastRatio(foreground, background) {
  const foregroundLuminance = relativeLuminance(foreground);
  const backgroundLuminance = relativeLuminance(background);
  const lighter = Math.max(foregroundLuminance, backgroundLuminance);
  const darker = Math.min(foregroundLuminance, backgroundLuminance);
  return (lighter + 0.05) / (darker + 0.05);
}

function validateContrast(themeName, declarations) {
  for (const check of contrastChecks) {
    for (const foregroundToken of check.foregrounds) {
      for (const backgroundToken of check.backgrounds) {
        const foreground = parseHexColor(
          resolveToken(foregroundToken, declarations),
          `${themeName} ${foregroundToken}`,
        );
        const background = parseHexColor(
          resolveToken(backgroundToken, declarations),
          `${themeName} ${backgroundToken}`,
        );
        const ratio = contrastRatio(foreground, background);
        if (ratio + Number.EPSILON < check.minimum) {
          throw new Error(
            `${themeName} ${check.purpose} contrast ${foregroundToken} / ` +
              `${backgroundToken} is ${ratio.toFixed(2)}:1; expected ` +
              `${check.minimum.toFixed(1)}:1 or higher.`,
          );
        }
      }
    }
  }
}

const cssFiles = await findFiles(appRoot, (path) => extname(path) === ".css");
const cssModules = cssFiles.filter((path) => path.endsWith(".module.css"));
const rawPalettePattern = /#[0-9a-f]{3,8}\b|(?:rgb|hsl)a?\(/i;

for (const path of cssFiles) {
  if (dirname(path) === themesRoot) {
    continue;
  }
  const content = await readFile(path, "utf8");
  if (rawPalettePattern.test(content)) {
    throw new Error(
      `Raw palette value found outside theme directory: ${relative(frontendRoot, path)}`,
    );
  }
}

const themePaths = (
  await findFiles(themesRoot, (path) => extname(path) === ".css")
)
  .filter((path) => path !== themeIndexPath)
  .sort();
if (themePaths.length === 0) {
  throw new Error("No theme files were found.");
}

const themeIndex = await readFile(themeIndexPath, "utf8");
for (const path of themePaths) {
  const expectedImport = `@import "./${basename(path)}";`;
  if (!themeIndex.includes(expectedImport)) {
    throw new Error(`Theme index does not import ${basename(path)}.`);
  }
}

for (const path of themePaths) {
  const stylesheet = await readFile(path, "utf8");
  const themeMatch = stylesheet.match(/\[data-theme="([^"]+)"\]/);
  if (!themeMatch) {
    throw new Error(`${basename(path)} has no data-theme selector.`);
  }
  const themeName = themeMatch[1];
  if (basename(path, ".css") !== themeName) {
    throw new Error(
      `${basename(path)} declares ${themeName}; the filename and theme name must match.`,
    );
  }

  const declarations = parseDeclarations(stylesheet);
  const semanticTokens = [...declarations.keys()].filter((token) =>
    /^(?:--color-|--shadow-)/.test(token),
  );
  const missingTokens = requiredThemeTokens.filter(
    (token) => !declarations.has(token),
  );
  const unexpectedTokens = semanticTokens.filter(
    (token) => !requiredThemeTokens.includes(token),
  );
  if (missingTokens.length > 0 || unexpectedTokens.length > 0) {
    throw new Error(
      `${themeName} theme contract mismatch. Missing: ` +
        `${missingTokens.join(", ") || "none"}. Unexpected: ` +
        `${unexpectedTokens.join(", ") || "none"}.`,
    );
  }

  for (const token of semanticTokens) {
    if (rawPalettePattern.test(declarations.get(token))) {
      throw new Error(
        `${themeName} ${token} must reference a raw palette token.`,
      );
    }
  }

  const financialValues = [
    "--color-money-income",
    "--color-money-expense",
    "--color-money-transfer",
    "--color-money-profit",
    "--color-money-adjustment",
  ].map((token) => resolveToken(token, declarations));
  if (new Set(financialValues).size !== financialValues.length) {
    throw new Error(`${themeName} financial state colors must be distinct.`);
  }

  validateContrast(themeName, declarations);
}

if (cssModules.length === 0) {
  throw new Error("No CSS Modules were found.");
}
