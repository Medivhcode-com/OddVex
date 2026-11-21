import { describe, expect, it } from "vitest";
import type { Schemas } from "@oddvex/types";
import { ClientApiError } from "@/lib/client-api";
import { autoSettleMessage, exportError, syncRunMessage } from "@/lib/tracker-messages";

type Run = Schemas["SyncRunOut"];
const bet = (id: string) => ({ id }) as unknown as Schemas["BetOut"];

describe("autoSettleMessage", () => {
  it("counts what was settled and what was left open", () => {
    const message = autoSettleMessage({ checked: 3, settled: [bet("a")], skipped: [{ bet_id: "b", reason: "event_not_final" }, { bet_id: "c", reason: "event_not_final" }] } as Schemas["AutoSettleOut"]);
    expect(message.text).toBe("1 bet settled from final scores. Left open: 2 game not finished.");
    expect(message.more).toBe(false);
  });

  it("says more bets remain when the API stopped at its limit (has_more)", () => {
    const message = autoSettleMessage({ checked: 200, settled: Array.from({ length: 200 }, (_, i) => bet(String(i))), skipped: [], has_more: true } as Schemas["AutoSettleOut"]);
    expect(message.more).toBe(true);
    expect(message.text).toMatch(/^200 bets settled from final scores\./);
    expect(message.text).toContain("More open bets are left to check.");
  });

  it("reads a missing has_more as false", () => {
    const message = autoSettleMessage({ checked: 0, settled: [], skipped: [] } as unknown as Schemas["AutoSettleOut"]);
    expect(message.more).toBe(false);
    expect(message.text).not.toContain("More open bets");
  });
});

describe("syncRunMessage", () => {
  const run = (overrides: Partial<Run>): Run =>
    ({ id: "r", connection_id: "c", status: "succeeded", attempts: 1, fetched_count: 5, imported_count: 3, duplicate_count: 1, retryable: false, started_at: "2026-11-21T00:00:00Z", error_message: null, ...overrides }) as Run;

  it("a clean run", () => {
    expect(syncRunMessage(run({ fetched_count: 4 }))).toEqual({ tone: "accent", text: "Sync finished. 3 new bets imported, 1 already here." });
  });

  it("a succeeded run that left bets out shows the API's error_message", () => {
    const message = syncRunMessage(run({ error_message: "1 bet was left out: the account already holds the most bets it can (5000)." }));
    expect(message.tone).toBe("warn");
    expect(message.text).toBe("Sync finished. 3 new bets imported, 1 already here. 1 bet was left out: the account already holds the most bets it can (5000).");
  });

  it("a failed run", () => {
    expect(syncRunMessage(run({ status: "failed", retryable: true, error_message: "Provider timed out" }))).toEqual({ tone: "warn", text: "Sync failed and can be retried: Provider timed out." });
    expect(syncRunMessage(run({ status: "failed", error_message: null }))).toEqual({ tone: "warn", text: "Sync failed: no detail given." });
  });
});

describe("exportError", () => {
  it("gives the retry time for 429", () => {
    expect(exportError(new ClientApiError(429, "rate_limited", "Too many requests. Try again in 600 seconds.", { retry_after_seconds: 600 }))).toBe("You have asked for several exports in a short time. Try again in 10 minutes.");
    expect(exportError(new ClientApiError(429, "rate_limited", "Too many requests."))).toBe("You have asked for several exports in a short time. Try again later.");
  });
  it("keeps the API's message otherwise", () => {
    expect(exportError(new ClientApiError(401, "not_authenticated", "Log in first"))).toBe("Log in first");
    expect(exportError(new Error("x"))).toBe("The export failed. Try again.");
  });
});
