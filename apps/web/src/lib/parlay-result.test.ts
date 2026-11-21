import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ParlayResultView, type ParlayResult } from "@/components/app/parlay-builder";

/** The words a reader sees. */
function words(result: ParlayResult): string {
  return renderToStaticMarkup(createElement(ParlayResultView, { result }))
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

const price = (american: number, decimal: number) => ({ american, decimal, fractional: "1/1", implied_probability: 1 / decimal });

/** What the API answers for two moneylines, apart from the reason fields under test. */
function result(overrides: Partial<ParlayResult>): ParlayResult {
  return {
    legs: [
      { label: "Harbor City Tides ML", price: price(150, 2.5), counted: true },
      { label: "Granite Peak Rams ML", price: price(-120, 1.833333), counted: true },
    ],
    combined_price: price(358, 4.583333),
    combined_decimal: 4.5833,
    active_legs: 2,
    stake: 10,
    payout: 45.83,
    profit: 35.83,
    combined_probability: null,
    probability_status: "needs_leg_probabilities",
    probability_note: "not computed: a win probability is required for every leg",
    correlation_warnings: [],
    steps: ["Harbor City Tides ML: decimal 2.5000", "Granite Peak Rams ML: decimal 1.8333", "Combined decimal = 2.5000 x 1.8333 = 4.5833", "Payout = 10.00 x 4.5833 = 45.83 (profit +35.83)"],
    ...overrides,
  };
}

describe("the parlay result, by the API's probability_status", () => {
  it("legs from different games: price, payout and break-even, and no probability stat or API note", () => {
    const text = words(result({}));
    expect(text).toContain("Combined odds");
    expect(text).toContain("Payout");
    expect(text).toContain("Break-even");
    expect(text).not.toContain("Combined probability");
    expect(text).not.toContain("Not shown");
    expect(text).not.toContain("win probability is required");
    expect(text).not.toMatch(/correlated|linked/i);
  });

  it("computed: shows the API's combined probability, labelled as assuming independent legs", () => {
    const text = words(result({ probability_status: "computed", combined_probability: 0.2475, probability_note: "assumes independence: the legs are from distinct events and their win probabilities were multiplied" }));
    expect(text).toContain("Combined probability");
    expect(text).toContain("24.75%");
    expect(text).toMatch(/assumes the legs are independent/i);
    expect(text).not.toContain("assumes independence: the legs");
  });

  it("same_event_legs: says legs from the same game are linked and no combined chance is given", () => {
    const text = words(
      result({
        probability_status: "same_event_legs",
        probability_note: "not computed: legs may be correlated",
        correlation_warnings: ["2 legs are from the same event (evt_123); their outcomes are correlated, so leg probabilities cannot be multiplied"],
      }),
    );
    expect(text).toContain("Legs from the same game");
    expect(text).toMatch(/results are linked/);
    expect(text).toMatch(/no combined chance/i);
    expect(text).not.toContain("Combined probability");
    expect(text).not.toContain("Not shown");
    expect(text).not.toContain("evt_123");
    expect(text).not.toContain("not computed");
  });

  it("unverified_legs: says custom legs cannot be checked for independence", () => {
    const text = words(
      result({
        probability_status: "unverified_legs",
        probability_note: "not computed: legs may be correlated",
        correlation_warnings: ["1 leg(s) have no event_id, so independence between legs cannot be verified"],
      }),
    );
    expect(text).toMatch(/Custom legs can't be checked for independence/);
    expect(text).not.toMatch(/These legs are correlated/);
    expect(text).not.toContain("event_id");
    expect(text).not.toContain("Combined probability");
  });

  it("no_active_legs: says every leg pushed or was voided", () => {
    const text = words(result({ probability_status: "no_active_legs", probability_note: "no active legs remain", combined_price: null, active_legs: 0 }));
    expect(text).toMatch(/Every leg pushed or was voided/);
    expect(text).not.toContain("Combined probability");
    expect(text).not.toContain("no active legs remain");
  });

  it("an answer without probability_status (an older API) shows no probability and no note", () => {
    const text = words(result({ probability_status: undefined }));
    expect(text).not.toContain("Combined probability");
    expect(text).not.toContain("win probability is required");
  });
});
