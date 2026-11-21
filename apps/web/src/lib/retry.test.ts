import { describe, expect, it } from "vitest";
import { retryAfterSeconds, tryAgainText, waitText } from "./retry";

describe("retryAfterSeconds", () => {
  it("reads the API's details.retry_after_seconds", () => {
    expect(retryAfterSeconds({ retry_after_seconds: 900 })).toBe(900);
    expect(retryAfterSeconds({ retry_after_seconds: 1 })).toBe(1);
  });
  it("is null when the API sent nothing usable", () => {
    for (const details of [undefined, null, "900", 900, {}, { retry_after_seconds: "900" }, { retry_after_seconds: 0 }, { retry_after_seconds: -5 }, { retry_after_seconds: Number.NaN }, { retry_after_seconds: Number.POSITIVE_INFINITY }]) {
      expect(retryAfterSeconds(details), JSON.stringify(details)).toBeNull();
    }
  });
});

describe("waitText", () => {
  it("never says less time than the API asked for", () => {
    expect(waitText(1)).toBe("1 second");
    expect(waitText(30)).toBe("30 seconds");
    expect(waitText(59)).toBe("59 seconds");
    expect(waitText(60)).toBe("1 minute");
    expect(waitText(61)).toBe("2 minutes");
    expect(waitText(900)).toBe("15 minutes");
    expect(waitText(3599)).toBe("60 minutes");
    expect(waitText(3600)).toBe("1 hour");
    expect(waitText(7201)).toBe("3 hours");
  });
  it("rounds a fraction of a second up", () => {
    expect(waitText(0.2)).toBe("1 second");
  });
});

describe("tryAgainText", () => {
  it("names the wait the API gave", () => {
    expect(tryAgainText({ retry_after_seconds: 900 })).toBe("Try again in 15 minutes.");
    expect(tryAgainText({ retry_after_seconds: 20 })).toBe("Try again in 20 seconds.");
  });
  it("falls back to neutral wording without a time, and never says 'a minute'", () => {
    expect(tryAgainText(undefined)).toBe("Try again later.");
    expect(tryAgainText({})).not.toMatch(/minute/);
    expect(tryAgainText(null, "Try again in a little while.")).toBe("Try again in a little while.");
  });
});
