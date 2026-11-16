/**
 * Content-Security-Policy builder. Pure, so the exact policy is unit-tested.
 *
 * How scripts are allowed (see ADR-0003, "Security headers"):
 *
 * - Next.js writes inline scripts into every page (the React payload and its bootstrap), and
 *   the root layout adds the theme script. A plain `script-src 'self'` would stop hydration.
 * - The bundled CSP guide offers per-request nonces, which need dynamic rendering. Using them
 *   everywhere would make every marketing page dynamic, so nonces are used only for routes
 *   that are already rendered per request (`/app`, the auth pages).
 * - For prerendered pages the guide's nonce-free alternative is `'unsafe-inline'`. We do
 *   better: after `next build`, `scripts/csp-hashes.mjs` hashes the inline scripts of each
 *   prerendered page and the proxy allows exactly those hashes for that page. The pages stay
 *   static; the price is one extra build step and a manifest that must ship with the server.
 *
 * `application/ld+json` blocks are data, not script, and need no allowance.
 */
export type CspOptions = {
  /** Per-request nonce, for routes rendered on demand. */
  nonce?: string;
  /** `sha256-…` sources for known inline scripts. */
  scriptHashes?: readonly string[];
  /** Last resort when the hash manifest is missing in production. Never combined with a nonce. */
  unsafeInlineScripts?: boolean;
  /** `next dev` only: React needs eval for debugging, and dev tooling injects styles and a websocket. */
  dev?: boolean;
  /** Add `upgrade-insecure-requests`; only when the site is served over https. */
  https?: boolean;
};

export function buildCsp(options: CspOptions = {}): string {
  const script = ["'self'"];
  if (options.nonce) script.push(`'nonce-${options.nonce}'`);
  for (const hash of options.scriptHashes ?? []) script.push(`'${hash}'`);
  if (options.unsafeInlineScripts && !options.nonce) script.push("'unsafe-inline'");
  if (options.dev) script.push("'unsafe-eval'");

  const directives = [
    "default-src 'self'",
    `script-src ${script.join(" ")}`,
    // Stylesheets are files from this origin. No <style> element is allowed in production.
    options.dev ? "style-src 'self' 'unsafe-inline'" : "style-src 'self'",
    // Inline style *attributes* are needed: charts and meters set computed widths and colours
    // with React's `style` prop (e.g. the hit-rate bar), and a nonce or hash cannot cover an
    // attribute. This is narrower than `style-src 'unsafe-inline'`.
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    options.dev ? "connect-src 'self' ws: wss:" : "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ];
  if (options.https) directives.push("upgrade-insecure-requests");
  return directives.join("; ");
}

export const HSTS_VALUE = "max-age=31536000; includeSubDomains";
