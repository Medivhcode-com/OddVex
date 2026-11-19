import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * A page with `generateStaticParams` is prerendered for the listed values. Without
 * `dynamicParams = false`, Next.js also renders every other value on request and keeps the
 * result in its cache and on disk with no limit, so anyone could fill the disk by asking for
 * made-up addresses. This test fails for any such page, present or future.
 */
const APP_DIR = path.resolve(__dirname, "..", "app");

function* sourceFiles(dir: string): Generator<string> {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* sourceFiles(full);
    else if (/\.(ts|tsx)$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) yield full;
  }
}

/**
 * Whether a source file exports `generateStaticParams`, in any of the forms an export can
 * take: a function or constant declared in the file, a name in an export list (with or
 * without `from`, with or without `as`), or everything from another module.
 */
function exportsStaticParams(source: string): boolean {
  if (/export\s+(async\s+)?function\s+generateStaticParams\b|export\s+(const|let|var)\s+generateStaticParams\b/.test(source)) return true;
  for (const [, names] of source.matchAll(/export\s*\{([^}]*)\}/g)) {
    // In `a as b` the exported name is `b`; otherwise it is the name itself.
    if (names.split(",").some((name) => name.trim().split(/\s+as\s+/).pop() === "generateStaticParams")) return true;
  }
  return /export\s*\*\s*from\b/.test(source);
}

describe("the check for generateStaticParams", () => {
  it("sees every form of the export", () => {
    for (const source of [
      "export function generateStaticParams() { return []; }",
      "export async function generateStaticParams() { return []; }",
      "export const generateStaticParams = () => [];",
      'export { generateStaticParams } from "@/lib/posts";',
      'export { metadata, generateStaticParams } from "./shared";',
      'export {\n  generateStaticParams,\n} from "./shared";',
      "function generateStaticParams() { return []; }\nexport { generateStaticParams };",
      'export { slugs as generateStaticParams } from "@/lib/posts";',
      'export * from "./shared";',
    ]) {
      expect(exportsStaticParams(source), source).toBe(true);
    }
  });

  it("is not set off by a page that only mentions or imports the name", () => {
    for (const source of [
      "export default function Page() { return null; }",
      "// generateStaticParams is not used here\nexport const dynamic = \"force-dynamic\";",
      'import { generateStaticParams } from "./shared";\nexport default function Page() { return null; }',
      'export { generateStaticParams as slugs } from "./shared";',
      'export { metadata } from "./shared";',
    ]) {
      expect(exportsStaticParams(source), source).toBe(false);
    }
  });
});

describe("pages generated from a fixed list", () => {
  const generated = [...sourceFiles(APP_DIR)].filter((file) => exportsStaticParams(readFileSync(file, "utf8")));

  it("exist, so this check is looking at something", () => {
    expect(generated.map((file) => path.relative(APP_DIR, file))).toContain(path.join("(marketing)", "blog", "[slug]", "page.tsx"));
  });

  it("answer 404 for a value that is not on the list instead of rendering and storing it", () => {
    for (const file of generated) {
      expect(readFileSync(file, "utf8"), path.relative(APP_DIR, file)).toMatch(/^export const dynamicParams = false;$/m);
    }
  });
});
