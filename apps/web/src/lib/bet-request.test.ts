import { afterEach, describe, expect, it, vi } from "vitest";
import { betSaveError, ClientRequestIds, newClientRequestId, stakeProblem } from "@/lib/bet-request";
import { clientApi, ClientApiError } from "@/lib/client-api";

const SHAPE = /^[A-Za-z0-9_-]{8,64}$/;

describe("newClientRequestId", () => {
  it("fits the API's client_request_id rule and differs every time", () => {
    const ids = new Set(Array.from({ length: 50 }, () => newClientRequestId()));
    expect(ids.size).toBe(50);
    for (const id of ids) expect(id).toMatch(SHAPE);
  });
});

describe("ClientRequestIds: one id per filled-in form", () => {
  const body = { stake: 20, sportsbook: "Northline", legs: [{ selection: "Harbor City Tides ML", odds: "+150" }] };

  it("sends the same id again when the same unchanged form is sent again after a failure", () => {
    const ids = new ClientRequestIds();
    const first = ids.forSend(body);
    expect(first).toMatch(SHAPE);
    expect(ids.forSend(structuredClone(body))).toBe(first);
  });

  it("makes a new id as soon as the form is edited after a failure, even if the edit is undone", () => {
    const ids = new ClientRequestIds();
    const first = ids.forSend(body);
    ids.edited();
    const second = ids.forSend(body);
    expect(second).not.toBe(first);
    expect(second).toMatch(SHAPE);
  });

  it("makes a new id when the body differs, whoever changed it", () => {
    const ids = new ClientRequestIds();
    const first = ids.forSend(body);
    expect(ids.forSend({ ...body, stake: 25 })).not.toBe(first);
  });

  it("makes a new id for the next bet once one was saved", () => {
    const ids = new ClientRequestIds();
    const first = ids.forSend(body);
    ids.saved();
    expect(ids.forSend(body)).not.toBe(first);
  });
});

describe("stakeProblem", () => {
  it("refuses a stake under 0.01", () => {
    expect(stakeProblem("0.001")).toBe("Enter a stake of at least $0.01.");
    expect(stakeProblem("0.004")).toBe("Enter a stake of at least $0.01.");
    expect(stakeProblem("0.009")).toBe("Enter a stake of at least $0.01.");
  });
  it("refuses an empty, zero, negative or unreadable stake", () => {
    for (const raw of ["", " ", "0", "-5", "abc", "Infinity"]) expect(stakeProblem(raw), raw).toBe("Enter a stake greater than zero.");
  });
  it("accepts a cent and more", () => {
    for (const raw of ["0.01", "1", "25.50", " 20 "]) expect(stakeProblem(raw), raw).toBeNull();
  });
});

describe("betSaveError", () => {
  it("shows the API's message for 409 bet_limit_reached", () => {
    const error = new ClientApiError(409, "bet_limit_reached", "An account holds at most 5000 bets. Delete some to add another.", { max_bets: 5000 });
    expect(betSaveError(error)).toBe("An account holds at most 5000 bets. Delete some to add another.");
  });
  it("gives the retry time for 429 rate_limited", () => {
    expect(betSaveError(new ClientApiError(429, "rate_limited", "Too many requests. Try again in 90 seconds.", { retry_after_seconds: 90 }))).toBe("Too many requests. Try again in 2 minutes.");
    expect(betSaveError(new ClientApiError(429, "rate_limited", "Too many requests. Try again in 20 seconds.", { retry_after_seconds: 20 }))).toBe("Too many requests. Try again in 20 seconds.");
    expect(betSaveError(new ClientApiError(429, "rate_limited", "Too many requests."))).toBe("Too many requests. Try again later.");
  });
  it("after a lost answer, says the bet may be saved and that sending it again does not record it twice", () => {
    for (const error of [
      new ClientApiError(0, "network", "You appear to be offline."),
      new ClientApiError(503, "api_unavailable", "OddVex can't reach its data service right now."),
      new ClientApiError(502, "http_error", "Request failed (502)."),
      new ClientApiError(504, "http_error", "Request failed (504)."),
    ]) {
      const text = betSaveError(error);
      expect(text).toMatch(/may already be saved/);
      expect(text).toMatch(/won't be recorded twice/);
    }
  });
  it("keeps the API's message for anything else", () => {
    expect(betSaveError(new ClientApiError(422, "invalid_stake", "Stake must be at least 0.01"))).toBe("Stake must be at least 0.01");
    expect(betSaveError(new Error("boom"))).toBe("The bet was not saved. Try again.");
  });
});

describe("clientApi", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("treats a 200 (a repeated create) like a 201 and returns the bet", async () => {
    for (const status of [200, 201]) {
      vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ id: "bet_1" }), { status, headers: { "content-type": "application/json" } })));
      await expect(clientApi<{ id: string }>("/v1/bets", { body: {} })).resolves.toEqual({ id: "bet_1" });
    }
  });
});
