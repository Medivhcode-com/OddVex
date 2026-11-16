import { createHash, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { type NextRequest, NextResponse } from "next/server";
import { API_URL, servedOverHttps, SESSION_COOKIE } from "@/lib/config";
import { buildCsp, HSTS_VALUE } from "@/lib/csp";
import { requestIdFrom, upstreamMetaHeaders } from "@/lib/request-meta";
import { FLAGGED_PATHS } from "@/lib/site";
import { THEME_SCRIPT } from "@/lib/theme-script";

/**
 * Runs in front of every page request (Node.js runtime). It does three things:
 *
 * 1. Security headers that depend on the request or on runtime configuration: the
 *    Content-Security-Policy and, over https only, Strict-Transport-Security. The fixed
 *    headers stay in `next.config.ts`. Policy details and trade-offs are in `lib/csp.ts`.
 * 2. One request id per request: a well-formed incoming `X-Request-ID` is kept, otherwise one
 *    is created. `api()` forwards it to the API and the response carries it back.
 * 3. A real 404 for `/app/admin` and everything under it when the visitor is not an admin,
 *    and for a page behind a feature flag while that flag is off. The pages check again; the
 *    check here exists because the `/app` tree streams behind `loading.tsx`, and a response
 *    that has started streaming is already a 200 (bundled docs: loading.md, "Status codes").
 *
 * The proxy does not make a page dynamic: prerendered pages are still served from the build.
 */

const isDev = process.env.NODE_ENV === "development";
const THEME_HASH = `sha256-${createHash("sha256").update(THEME_SCRIPT, "utf8").digest("base64")}`;
const NOT_FOUND = "/_not-found";
/** Matches no route, so a rewrite to it renders the not-found page with a 404 status. */
const UNMATCHED_PATH = "/_/not-found";

type HashManifest = Record<string, string[]>;
let manifest: HashManifest | null | undefined;

/** Inline-script hashes of the prerendered pages, written by `scripts/csp-hashes.mjs` after the build. */
function hashManifest(): HashManifest | null {
  if (manifest !== undefined) return manifest;
  if (isDev) return (manifest = null); // `next dev` renders every page on demand, so nonces cover everything
  try {
    manifest = JSON.parse(readFileSync(path.join(process.cwd(), ".next", "csp-hashes.json"), "utf8")) as HashManifest;
  } catch {
    manifest = null;
    console.error(
      "[csp] .next/csp-hashes.json is missing. Pages fall back to script-src 'unsafe-inline' so the site keeps working. " +
        "Build with `pnpm build` (it runs scripts/csp-hashes.mjs) and ship the file with the server.",
    );
  }
  return manifest;
}

function contentSecurityPolicy(pathname: string): { csp: string; nonce?: string } {
  const https = servedOverHttps();
  const hashes = hashManifest();
  if (!hashes && !isDev) return { csp: buildCsp({ unsafeInlineScripts: true, https }) };
  const route = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const prerendered = hashes?.[route];
  if (prerendered) return { csp: buildCsp({ scriptHashes: prerendered, https }) };
  // Rendered on demand: Next.js reads the nonce from the request's CSP header and puts it on
  // its own scripts. The theme script comes from the static root layout, which cannot read a
  // nonce without making every page dynamic, so it is allowed by hash. An unknown URL is
  // answered with the prerendered not-found page, hence its hashes as well.
  const nonce = Buffer.from(randomUUID()).toString("base64");
  return { csp: buildCsp({ nonce, scriptHashes: [...new Set([THEME_HASH, ...(hashes?.[NOT_FOUND] ?? [])])], dev: isDev, https }), nonce };
}

/** False only when the API positively says this visitor is not an admin. */
async function mayBeAdmin(request: NextRequest, requestHeaders: Headers): Promise<boolean> {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return false;
  try {
    const response = await fetch(`${API_URL}/v1/me`, {
      headers: { accept: "application/json", authorization: `Bearer ${token}`, ...upstreamMetaHeaders(requestHeaders).headers },
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    if (response.status === 401 || response.status === 403) return false;
    if (!response.ok) return true;
    return ((await response.json()) as { role?: string }).role === "admin";
  } catch {
    // The API is down: let the page render its own "can't reach the data service" state.
    return true;
  }
}

/** True only when the API positively says the flag is not on. If it can't be asked, the page decides. */
async function flagIsOff(flag: string, requestHeaders: Headers): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/v1/flags`, {
      headers: { accept: "application/json", ...upstreamMetaHeaders(requestHeaders).headers },
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    if (!response.ok) return false;
    return ((await response.json()) as { flags?: Record<string, boolean> }).flags?.[flag] !== true;
  } catch {
    return false;
  }
}

/** Whether this request must be answered with the not-found page before any page code runs. */
async function hidden(pathname: string, request: NextRequest, requestHeaders: Headers): Promise<boolean> {
  const path = pathname.replace(/\/+$/, "");
  if (path === "/app/admin" || path.startsWith("/app/admin/")) return !(await mayBeAdmin(request, requestHeaders));
  const flagged = FLAGGED_PATHS.find((entry) => entry.path === path);
  return flagged ? flagIsOff(flagged.flag, requestHeaders) : false;
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const requestId = requestIdFrom(request.headers);
  const { csp, nonce } = contentSecurityPolicy(pathname);

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-request-id", requestId);
  if (nonce) {
    requestHeaders.set("x-nonce", nonce);
    requestHeaders.set("Content-Security-Policy", csp);
  }

  const init = { request: { headers: requestHeaders } };
  const response = (await hidden(pathname, request, requestHeaders))
    ? NextResponse.rewrite(new URL(UNMATCHED_PATH, request.url), init)
    : NextResponse.next(init);

  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("X-Request-ID", requestId);
  // HSTS only makes sense over https. Local and e2e runs serve the production build over http
  // (ODDVEX_INSECURE_COOKIES=true), where the header would be ignored at best.
  if (servedOverHttps()) response.headers.set("Strict-Transport-Security", HSTS_VALUE);
  return response;
}

export const config = {
  matcher: [
    {
      // Pages only. Static assets need no CSP, and the /api/ov bridge sets its own request id.
      // Prefetches are skipped as the bundled CSP guide recommends.
      source: "/((?!api/|_next/static|_next/image|icon.svg|robots.txt|sitemap.xml).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
