import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import AppError from "@/app/app/error";
import { ApiError, ApiUnavailableError } from "@/lib/api";

// `lib/api.ts` is server code; the marker package only exists to keep it out of the browser bundle.
vi.mock("server-only", () => ({}));

/**
 * The two ends of the "API is down" message together: the error `api()` throws on the
 * server, and the screen the browser draws from what is left of it. A production build hands
 * the screen a generic error that carries only the original's `digest`.
 */
function screenFor(thrown: { digest?: string }): string {
  const delivered: Error & { digest?: string } = new Error("An error occurred in the Server Components render.");
  if (thrown.digest !== undefined) delivered.digest = thrown.digest;
  return renderToStaticMarkup(createElement(AppError, { error: delivered, reset: () => {} }));
}

describe("the app error screen, from the error the server throws", () => {
  it("says OddVex can't reach its data service when the API was unreachable, with the request id", () => {
    const html = screenFor(new ApiUnavailableError("3f2b7c1e-8a41-4d59-9c0e-5a1b2c3d4e5f"));
    expect(html).toContain("OddVex can&#x27;t reach its data service");
    expect(html).toContain("Nothing is wrong with your account. The data service is not responding, so there are no prices to show.");
    expect(html).toContain("Reference 3f2b7c1e-8a41-4d59-9c0e-5a1b2c3d4e5f");
    expect(html).not.toContain("This screen failed to load");
    expect(html).not.toContain("api_unavailable");
    expect(html).not.toMatch(/not reachable/i);
  });

  it("says the same without a reference when the request had no id", () => {
    const html = screenFor(new ApiUnavailableError());
    expect(html).toContain("OddVex can&#x27;t reach its data service");
    expect(html).not.toContain("Reference");
  });

  it("keeps the general wording and the request id for an error the API answered with", () => {
    const html = screenFor(new ApiError(500, "internal_error", "Something broke", undefined, "e2e-request-id-0003"));
    expect(html).toContain("This screen failed to load");
    expect(html).toContain("Reference e2e-request-id-0003");
    expect(html).not.toContain("Something broke");
  });

  it("keeps the general wording for any other error", () => {
    const html = screenFor({ digest: "2843917650" });
    expect(html).toContain("This screen failed to load");
    expect(html).toContain("Reference 2843917650");
  });
});
