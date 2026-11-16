// Runs after `next build`. Writes .next/csp-hashes.json: for every prerendered page, the
// SHA-256 hashes of its inline scripts. `src/proxy.ts` allows exactly those in that page's
// Content-Security-Policy, which keeps marketing pages static without 'unsafe-inline'.
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const appDir = path.join(root, ".next", "server", "app");

function* htmlFiles(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* htmlFiles(full);
    else if (entry.name.endsWith(".html")) yield full;
  }
}

const JS_TYPES = new Set(["", "module", "text/javascript", "application/javascript"]);
const SCRIPT_RE = /<script\b([^>]*)>([\s\S]*?)<\/script>/g;

function inlineScriptHashes(html) {
  const hashes = new Set();
  for (const [, attrs, body] of html.matchAll(SCRIPT_RE)) {
    if (/\ssrc\s*=/.test(attrs) || body === "") continue;
    const type = /\stype\s*=\s*"([^"]*)"/.exec(attrs)?.[1]?.toLowerCase() ?? "";
    if (!JS_TYPES.has(type)) continue; // e.g. application/ld+json is data and is never executed
    hashes.add(`sha256-${createHash("sha256").update(body, "utf8").digest("base64")}`);
  }
  return [...hashes];
}

if (!existsSync(appDir)) {
  console.error(`csp-hashes: ${appDir} not found. Run next build first.`);
  process.exit(1);
}

const manifest = {};
for (const file of htmlFiles(appDir)) {
  const relative = path.relative(appDir, file).split(path.sep).join("/").replace(/\.html$/, "");
  const route = relative === "index" ? "/" : `/${relative.replace(/\/index$/, "")}`;
  manifest[route] = inlineScriptHashes(readFileSync(file, "utf8"));
}
if (!manifest["/_not-found"]) {
  console.error("csp-hashes: the prerendered not-found page is missing; refusing to write a partial manifest.");
  process.exit(1);
}

const json = JSON.stringify(manifest);
const targets = [path.join(root, ".next", "csp-hashes.json")];
// `output: "standalone"` copies the server into .next/standalone; the manifest has to sit next to it.
const standalone = path.join(root, ".next", "standalone", "apps", "web", ".next");
if (existsSync(path.dirname(standalone))) targets.push(path.join(standalone, "csp-hashes.json"));
for (const target of targets) {
  mkdirSync(path.dirname(target), { recursive: true });
  writeFileSync(target, json);
}
console.log(`csp-hashes: ${Object.keys(manifest).length} prerendered pages -> ${targets.map((t) => path.relative(root, t)).join(", ")}`);
