import { readFileSync } from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

// Token design system dipakai di dua tempat: aplikasi petugas (SCSS ini) dan
// tampilan server (panel admin, portal, /aset/, /komando/). Keduanya harus sama.
const tokenBlock = (file: string): string => {
  const text = readFileSync(file, "utf8");
  const start = text.indexOf("/* sl-tokens:start */");
  const end = text.indexOf("/* sl-tokens:end */");
  expect(start).toBeGreaterThanOrEqual(0);
  expect(end).toBeGreaterThan(start);
  return text.slice(start, end);
};

const declarations = (block: string): Record<string, string> =>
  Object.fromEntries(
    [...block.matchAll(/(--sl-[\w-]+):\s*([^;]+);/g)].map((m) => [
      m[1],
      m[2].trim(),
    ]),
  );

describe("design tokens", () => {
  const spa = tokenBlock(path.resolve(__dirname, "_tokens.scss"));
  const server = tokenBlock(
    path.resolve(
      __dirname,
      "../../../../../backend/utils/static/simlahan/tokens.css",
    ),
  );

  it("are identical in the officer app and the server-rendered pages", () => {
    expect(declarations(spa)).toEqual(declarations(server));
  });

  it("define the core tokens", () => {
    const tokens = declarations(spa);
    for (const name of [
      "--sl-font",
      "--sl-primary",
      "--sl-bg",
      "--sl-surface",
      "--sl-text",
      "--sl-radius",
      "--sl-shadow-sm",
    ]) {
      expect(tokens[name], name).toBeTruthy();
    }
  });
});
