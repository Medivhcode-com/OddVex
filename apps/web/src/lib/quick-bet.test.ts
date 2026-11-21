import { describe, expect, it } from "vitest";
import { ClientRequestIds } from "@/lib/bet-request";
import { quickBetRequest, type QuickBetPick } from "@/lib/quick-bet";

const game = { eventId: "evt_1", eventLabel: "Rams at Tides", league: "nfl", market: "moneyline" };
const home: QuickBetPick = { outcomeKey: "home", label: "Harbor City Tides ML", line: null, american: 150, sportsbook: "Northline" };
const away: QuickBetPick = { outcomeKey: "away", label: "Ridge Rams ML", line: null, american: -170, sportsbook: "Northline" };

describe("quickBetRequest: the id follows what the user entered, not the live price", () => {
  it("sends the full bet at the current best price, with a client_request_id", () => {
    const out = quickBetRequest(new ClientRequestIds(), game, home, "20");
    expect(out).toMatchObject({ bet_type: "straight", stake: 20, sportsbook: "Northline", legs: [{ outcome_key: "home", event_id: "evt_1", odds: "150", odds_format: "american" }] });
    expect(out.client_request_id).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
  });

  it("keeps the id when an auto-refresh moved the price between a lost answer and the resend", () => {
    const ids = new ClientRequestIds();
    const first = quickBetRequest(ids, game, home, "20");
    const resent = quickBetRequest(ids, game, { ...home, american: 145 }, "20");
    expect(resent.legs[0].odds).toBe("145");
    expect(resent.client_request_id).toBe(first.client_request_id);
  });

  it("keeps the id when an auto-refresh moved the best price to another book or line", () => {
    const ids = new ClientRequestIds();
    const first = quickBetRequest(ids, game, home, "20");
    expect(quickBetRequest(ids, game, { ...home, sportsbook: "Southpoint", line: 1.5 }, "20").client_request_id).toBe(first.client_request_id);
  });

  it("makes a new id when the side or the stake differs", () => {
    const ids = new ClientRequestIds();
    const first = quickBetRequest(ids, game, home, "20").client_request_id;
    const otherSide = quickBetRequest(ids, game, away, "20").client_request_id;
    expect(otherSide).not.toBe(first);
    const otherStake = quickBetRequest(ids, game, away, "25").client_request_id;
    expect(otherStake).not.toBe(otherSide);
  });

  it("makes a new id after an edit or a save, even for the same inputs", () => {
    const ids = new ClientRequestIds();
    const first = quickBetRequest(ids, game, home, "20").client_request_id;
    ids.edited();
    const second = quickBetRequest(ids, game, home, "20").client_request_id;
    expect(second).not.toBe(first);
    ids.saved();
    expect(quickBetRequest(ids, game, home, "20").client_request_id).not.toBe(second);
  });
});
