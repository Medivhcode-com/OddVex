import { describe, expect, it, vi } from "vitest";
import { ApiError, ApiUnavailableError } from "@/lib/api";
import { describeAuthError } from "@/lib/auth-errors";

// `lib/api.ts` is server code; the marker package only exists to keep it out of the browser bundle.
vi.mock("server-only", () => ({}));

const rateLimited = (details?: unknown) => new ApiError(429, "rate_limited", "Too many requests. Try again in 900 seconds.", details);

describe("the sign-in refusal after too many attempts", () => {
  it("gives the wait the API asked for, in minutes", () => {
    expect(describeAuthError(rateLimited({ retry_after_seconds: 900 }), "fallback")).toBe("Too many attempts. Try again in 15 minutes.");
    expect(describeAuthError(rateLimited({ retry_after_seconds: 45 }), "fallback")).toBe("Too many attempts. Try again in 45 seconds.");
  });

  it("uses neutral wording when the API gave no time", () => {
    const text = describeAuthError(rateLimited(), "fallback");
    expect(text).toBe("Too many attempts. Try again later.");
  });

  it("never says 'Wait a minute' for what can be a 15-minute refusal", () => {
    for (const details of [undefined, {}, { retry_after_seconds: 900 }, { retry_after_seconds: 60 }]) {
      expect(describeAuthError(rateLimited(details), "fallback")).not.toMatch(/wait a minute/i);
    }
  });

  it("keeps the other messages", () => {
    expect(describeAuthError(new ApiUnavailableError(), "fallback")).toBe("OddVex can't reach its data service right now. Try again in a moment.");
    expect(describeAuthError(new ApiError(401, "invalid_credentials", "Wrong email or password"), "fallback")).toBe("Wrong email or password");
    expect(describeAuthError(new ApiError(400, "bad", ""), "fallback")).toBe("fallback");
    expect(describeAuthError(new Error("boom"), "fallback")).toBe("fallback");
  });
});
