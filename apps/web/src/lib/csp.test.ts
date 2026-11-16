import { describe, expect, it } from "vitest";
import { servedOverHttps } from "./config";
import { buildCsp } from "./csp";

describe("buildCsp", () => {
  it("allows a prerendered page's inline scripts by hash only", () => {
    const csp = buildCsp({ scriptHashes: ["sha256-AAA=", "sha256-BBB="] });
    expect(csp).toContain("script-src 'self' 'sha256-AAA=' 'sha256-BBB=';");
    expect(csp).not.toContain("nonce-");
  });

  it("allows an on-demand page's scripts by nonce", () => {
    expect(buildCsp({ nonce: "abc", scriptHashes: ["sha256-AAA="] })).toContain("script-src 'self' 'nonce-abc' 'sha256-AAA=';");
  });

  it("never allows eval or inline scripts in the production policy", () => {
    for (const csp of [buildCsp(), buildCsp({ nonce: "n" }), buildCsp({ scriptHashes: ["sha256-A="] }), buildCsp({ https: true })]) {
      expect(csp).not.toContain("unsafe-eval");
      expect(csp.match(/script-src [^;]*/)?.[0]).not.toContain("unsafe-inline");
      expect(csp.match(/style-src [^;]*/)?.[0]).toBe("style-src 'self'");
    }
  });

  it("carries every fixed directive", () => {
    const csp = buildCsp();
    for (const directive of [
      "default-src 'self'",
      "style-src-attr 'unsafe-inline'",
      "img-src 'self' data:",
      "font-src 'self'",
      "connect-src 'self'",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ]) {
      expect(csp.split("; ")).toContain(directive);
    }
  });

  it("upgrades insecure requests only over https", () => {
    expect(buildCsp({ https: true })).toContain("upgrade-insecure-requests");
    expect(buildCsp()).not.toContain("upgrade-insecure-requests");
  });

  it("ignores the unsafe-inline fallback when a nonce is present", () => {
    expect(buildCsp({ nonce: "n", unsafeInlineScripts: true })).not.toContain("unsafe-inline' 'unsafe");
    expect(buildCsp({ nonce: "n", unsafeInlineScripts: true }).match(/script-src [^;]*/)?.[0]).toBe("script-src 'self' 'nonce-n'");
  });
});

describe("servedOverHttps (HSTS and Secure cookies)", () => {
  it("is on in production", () => {
    expect(servedOverHttps({ NODE_ENV: "production" })).toBe(true);
  });
  it("is off for local http runs of the production build and in development", () => {
    expect(servedOverHttps({ NODE_ENV: "production", ODDVEX_INSECURE_COOKIES: "true" })).toBe(false);
    expect(servedOverHttps({ NODE_ENV: "development" })).toBe(false);
  });
});
