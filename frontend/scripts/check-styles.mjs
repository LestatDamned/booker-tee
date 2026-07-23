import { readdir, readFile } from "node:fs/promises";
import { basename, dirname, extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const appRoot = join(frontendRoot, "app");
const themesRoot = join(appRoot, "styles", "themes");
const themeIndexPath = join(themesRoot, "index.css");

const requiredThemeTokens = [
  "--color-bg-canvas",
  "--color-bg-secondary-pane",
  "--color-bg-shell",
  "--color-bg-surface",
  "--color-bg-elevated",
  "--color-bg-interactive",
  "--color-text-primary",
  "--color-text-secondary",
  "--color-text-muted",
  "--color-brand",
  "--color-brand-detail",
  "--color-action-primary",
  "--color-on-action-primary",
  "--color-action-secondary",
  "--color-on-action-secondary",
  "--color-interactive-active",
  "--color-information",
  "--color-automation",
  "--color-working",
  "--color-recent",
  "--color-neutral",
  "--color-link",
  "--color-border-default",
  "--color-border-control",
  "--color-border-strong",
  "--color-focus-ring",
  "--color-selection",
  "--color-caret",
  "--color-status-success",
  "--color-status-warning",
  "--color-status-danger",
  "--color-money-income",
  "--color-money-expense",
  "--color-money-transfer",
  "--color-money-profit",
  "--color-money-adjustment",
  "--color-category",
  "--color-overlay",
  "--shadow-surface",
];

const officialCatppuccinPalettes = {
  "catppuccin-latte": {
    "--ctp-rosewater": "#dc8a78",
    "--ctp-flamingo": "#dd7878",
    "--ctp-pink": "#ea76cb",
    "--ctp-mauve": "#8839ef",
    "--ctp-red": "#d20f39",
    "--ctp-maroon": "#e64553",
    "--ctp-peach": "#fe640b",
    "--ctp-yellow": "#df8e1d",
    "--ctp-green": "#40a02b",
    "--ctp-teal": "#179299",
    "--ctp-sky": "#04a5e5",
    "--ctp-sapphire": "#209fb5",
    "--ctp-blue": "#1e66f5",
    "--ctp-lavender": "#7287fd",
    "--ctp-text": "#4c4f69",
    "--ctp-subtext-1": "#5c5f77",
    "--ctp-subtext-0": "#6c6f85",
    "--ctp-overlay-2": "#7c7f93",
    "--ctp-overlay-1": "#8c8fa1",
    "--ctp-overlay-0": "#9ca0b0",
    "--ctp-surface-2": "#acb0be",
    "--ctp-surface-1": "#bcc0cc",
    "--ctp-surface-0": "#ccd0da",
    "--ctp-base": "#eff1f5",
    "--ctp-mantle": "#e6e9ef",
    "--ctp-crust": "#dce0e8",
  },
  "catppuccin-mocha": {
    "--ctp-rosewater": "#f5e0dc",
    "--ctp-flamingo": "#f2cdcd",
    "--ctp-pink": "#f5c2e7",
    "--ctp-mauve": "#cba6f7",
    "--ctp-red": "#f38ba8",
    "--ctp-maroon": "#eba0ac",
    "--ctp-peach": "#fab387",
    "--ctp-yellow": "#f9e2af",
    "--ctp-green": "#a6e3a1",
    "--ctp-teal": "#94e2d5",
    "--ctp-sky": "#89dceb",
    "--ctp-sapphire": "#74c7ec",
    "--ctp-blue": "#89b4fa",
    "--ctp-lavender": "#b4befe",
    "--ctp-text": "#cdd6f4",
    "--ctp-subtext-1": "#bac2de",
    "--ctp-subtext-0": "#a6adc8",
    "--ctp-overlay-2": "#9399b2",
    "--ctp-overlay-1": "#7f849c",
    "--ctp-overlay-0": "#6c7086",
    "--ctp-surface-2": "#585b70",
    "--ctp-surface-1": "#45475a",
    "--ctp-surface-0": "#313244",
    "--ctp-base": "#1e1e2e",
    "--ctp-mantle": "#181825",
    "--ctp-crust": "#11111b",
  },
};

const officialCatppuccinRoleReferences = {
  "--color-bg-canvas": "var(--ctp-base)",
  "--color-bg-secondary-pane": "var(--ctp-mantle)",
  "--color-bg-shell": "var(--ctp-crust)",
  "--color-bg-surface": "var(--ctp-mantle)",
  "--color-bg-elevated": "var(--ctp-surface-0)",
  "--color-bg-interactive": "var(--ctp-surface-0)",
  "--color-text-primary": "var(--ctp-text)",
  "--color-selection": "var(--ctp-overlay-2)",
  "--color-caret": "var(--ctp-rosewater)",
  "--color-brand-detail": "var(--ctp-rosewater)",
  "--color-action-primary": "var(--ctp-lavender)",
  "--color-action-secondary": "var(--ctp-surface-0)",
  "--color-on-action-secondary": "var(--ctp-text)",
  "--color-recent": "var(--ctp-blue)",
};

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
      "--color-interactive-active",
      "--color-information",
      "--color-automation",
      "--color-working",
      "--color-recent",
      "--color-neutral",
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
    ],
    backgrounds: [
      "--color-bg-canvas",
      "--color-bg-surface",
      "--color-bg-elevated",
    ],
    minimum: 4.5,
    purpose: "small status text",
  },
  {
    foregrounds: [
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
    purpose: "large financial text or non-text state",
  },
  {
    foregrounds: ["--color-brand"],
    backgrounds: ["--color-bg-canvas", "--color-bg-shell"],
    minimum: 4.5,
    purpose: "brand text",
  },
  {
    foregrounds: ["--color-on-action-primary"],
    backgrounds: ["--color-action-primary"],
    minimum: 4.5,
    purpose: "primary action text",
  },
  {
    foregrounds: ["--color-on-action-secondary"],
    backgrounds: ["--color-action-secondary"],
    minimum: 4.5,
    purpose: "secondary action text",
  },
  {
    foregrounds: ["--color-link"],
    backgrounds: [
      "--color-bg-canvas",
      "--color-bg-surface",
      "--color-bg-elevated",
    ],
    minimum: 4.5,
    purpose: "small link text",
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

function validateOfficialCatppuccinPalette(themeName, declarations) {
  const expectedPalette = officialCatppuccinPalettes[themeName];
  if (!expectedPalette) {
    return;
  }

  const actualTokens = [...declarations.keys()].filter((token) =>
    token.startsWith("--ctp-"),
  );
  const expectedTokens = Object.keys(expectedPalette);
  const missingTokens = expectedTokens.filter(
    (token) => !declarations.has(token),
  );
  const unexpectedTokens = actualTokens.filter(
    (token) => !Object.hasOwn(expectedPalette, token),
  );
  if (missingTokens.length > 0 || unexpectedTokens.length > 0) {
    throw new Error(
      `${themeName} official palette contract mismatch. Missing: ` +
        `${missingTokens.join(", ") || "none"}. Unexpected: ` +
        `${unexpectedTokens.join(", ") || "none"}.`,
    );
  }

  for (const [token, expectedValue] of Object.entries(expectedPalette)) {
    const actualValue = declarations.get(token)?.toLowerCase();
    if (actualValue !== expectedValue) {
      throw new Error(
        `${themeName} ${token} is ${actualValue}; official Catppuccin value ` +
          `is ${expectedValue}.`,
      );
    }
  }

  const legacyPaletteTokens = [...declarations.keys()].filter((token) =>
    token.startsWith("--palette-"),
  );
  if (legacyPaletteTokens.length > 0) {
    throw new Error(
      `${themeName} must use canonical --ctp-* palette tokens; found ` +
        `${legacyPaletteTokens.join(", ")}.`,
    );
  }

  for (const [token, expectedReference] of Object.entries(
    officialCatppuccinRoleReferences,
  )) {
    const actualReference = declarations.get(token);
    if (actualReference !== expectedReference) {
      throw new Error(
        `${themeName} ${token} is ${actualReference}; Catppuccin role requires ` +
          `${expectedReference}.`,
      );
    }
  }
}

const cssFiles = await findFiles(appRoot, (path) => extname(path) === ".css");
const cssModules = cssFiles.filter((path) => path.endsWith(".module.css"));
const rawPalettePattern = /#[0-9a-f]{3,8}\b|(?:rgb|hsl)a?\(/i;
const primitiveTokenPattern = /var\(--(?:ctp|palette)-/;
const legacyAccentPattern = /var\(--color-(?:on-)?accent(?:-strong)?\)/;

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
  if (primitiveTokenPattern.test(content)) {
    throw new Error(
      `Primitive palette token found outside theme directory: ${relative(frontendRoot, path)}`,
    );
  }
  if (legacyAccentPattern.test(content)) {
    throw new Error(
      `Legacy universal accent token found in ${relative(frontendRoot, path)}; use a named semantic role.`,
    );
  }
}

const sourceFiles = await findFiles(appRoot, (path) =>
  [".ts", ".tsx"].includes(extname(path)),
);
const rawInlineSvgPattern = /<svg(?:\s|>)/i;
const emojiPattern = /\p{Extended_Pictographic}/u;

for (const path of sourceFiles) {
  const content = await readFile(path, "utf8");
  if (rawInlineSvgPattern.test(content)) {
    throw new Error(
      `Raw inline SVG found in ${relative(frontendRoot, path)}; use the shared Icon renderer.`,
    );
  }
  if (emojiPattern.test(content)) {
    throw new Error(
      `Emoji found in ${relative(frontendRoot, path)}; structural UI uses shared SVG icons.`,
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
  validateOfficialCatppuccinPalette(themeName, declarations);
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
