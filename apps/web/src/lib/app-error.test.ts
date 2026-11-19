import { describe, expect, it } from "vitest";
import { apiUnavailableDigest, readAppError } from "./app-error";

/**
 * What the error screen receives in a production build: React replaces a server error with a
 * generic one and copies only `digest` across. A development render also forwards the name
 * and message, so a test that builds the real error class would pass for the wrong reason.
 */
function asTheBrowserGetsIt(digest: string | undefined): Error & { digest?: string } {
  const error: Error & { digest?: string } = new Error("An error occurred in the Server Components render. The specific message is omitted in production builds to avoid leaking sensitive details.");
  if (digest !== undefined) error.digest = digest;
  return error;
}

describe("the app error screen", () => {
  it("recognises an unreachable API from the digest alone, and shows the bare request id", () => {
    const seen = readAppError(asTheBrowserGetsIt(apiUnavailableDigest("3f2b7c1e-8a41-4d59-9c0e-5a1b2c3d4e5f")));
    expect(seen).toEqual({ unreachable: true, reference: "3f2b7c1e-8a41-4d59-9c0e-5a1b2c3d4e5f" });
  });

  it("recognises an unreachable API when there was no request id, and shows no reference", () => {
    expect(readAppError(asTheBrowserGetsIt(apiUnavailableDigest()))).toEqual({ unreachable: true, reference: null });
    expect(readAppError(asTheBrowserGetsIt(apiUnavailableDigest("")))).toEqual({ unreachable: true, reference: null });
  });

  it("shows any other error's digest as the reference, unchanged", () => {
    // An API error: the request id. Anything else: the hash Next.js made.
    expect(readAppError(asTheBrowserGetsIt("e2e-request-id-0001"))).toEqual({ unreachable: false, reference: "e2e-request-id-0001" });
    expect(readAppError(asTheBrowserGetsIt("2843917650"))).toEqual({ unreachable: false, reference: "2843917650" });
  });

  it("shows no reference when there is no digest", () => {
    expect(readAppError(asTheBrowserGetsIt(undefined))).toEqual({ unreachable: false, reference: null });
    expect(readAppError(asTheBrowserGetsIt(""))).toEqual({ unreachable: false, reference: null });
    expect(readAppError({})).toEqual({ unreachable: false, reference: null });
  });

  it("does not go by the name or the message, which never reach the browser", () => {
    const named = Object.assign(new Error("The OddVex API is not reachable."), { name: "ApiUnavailableError", digest: "e2e-request-id-0002" });
    expect(readAppError(named)).toEqual({ unreachable: false, reference: "e2e-request-id-0002" });
  });

  it("never puts anything but the request id after the marker", () => {
    expect(apiUnavailableDigest("abc-123_DEF.456")).toBe("api_unavailable:abc-123_DEF.456");
    expect(apiUnavailableDigest()).toBe("api_unavailable:");
    // A digest is written into the page; a value that is not a request id is left out.
    expect(apiUnavailableDigest('"><script>')).toBe("api_unavailable:");
    expect(readAppError(asTheBrowserGetsIt('api_unavailable:"><script>'))).toEqual({ unreachable: true, reference: null });
  });
});
