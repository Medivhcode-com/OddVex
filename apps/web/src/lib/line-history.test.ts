import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LineHistoryChart } from "@/components/ui/charts";
import { lineMovementChart } from "@/lib/line-history";
import type { LineHistory } from "@/lib/types";

const HOUR = 3_600_000;
const T0 = Date.parse("2026-11-19T00:00:00Z");

/** One price as the API sends it: every format already worked out by the API. */
function price(american: number, decimal: number, implied: number) {
  return { american, decimal, fractional: "", implied_probability: implied };
}
const P = {
  m116: price(-116, 1.862069, 0.537037),
  m104: price(-104, 1.961538, 0.509804),
  p103: price(103, 2.03, 0.492611),
  p113: price(113, 2.13, 0.469484),
  p120: price(120, 2.2, 0.454545),
};

function history(market: LineHistory["market"], series: LineHistory["series"]): LineHistory {
  const team = (id: string, name: string) => ({ id, name, abbreviation: name.slice(0, 3).toUpperCase() });
  return {
    as_of: new Date(T0 + 48 * HOUR).toISOString(),
    data_mode: "synthetic",
    event: { id: "evt_test", league: "nhl", status: "upcoming", start_time: new Date(T0 + 50 * HOUR).toISOString(), home_team: team("h", "Harbor City Tides"), away_team: team("a", "Granite Peak Rams") },
    market,
    series,
  } as LineHistory;
}

function book(key: string, name: string, points: { hour: number; price: ReturnType<typeof price>; line?: number }[], outcome = { key: "home", name: "Harbor City Tides" }) {
  return {
    sportsbook: { key, name },
    outcome_key: outcome.key,
    outcome_name: outcome.name,
    points: points.map((p) => ({ timestamp: new Date(T0 + p.hour * HOUR).toISOString(), price: p.price, line: p.line ?? null })),
  };
}

/** The same game as the audit's example: one book goes −104, +103, +113 and the range is −116 to +120. */
const CROSSING = history("moneyline", [
  book("northline", "Northline", [
    { hour: 0, price: P.m104 },
    { hour: 20, price: P.p103 },
    { hour: 44, price: P.p113 },
  ]),
  book("cardinal", "Cardinal", [
    { hour: 0, price: P.m116 },
    { hour: 30, price: P.p120 },
  ]),
  // The other side of the market is not charted.
  book("northline", "Northline", [{ hour: 0, price: P.p120 }], { key: "away", name: "Granite Peak Rams" }),
]);

function render(chart: NonNullable<ReturnType<typeof lineMovementChart>>): string {
  return renderToStaticMarkup(
    createElement(LineHistoryChart, {
      series: chart.series,
      summary: chart.summary,
      axisTitle: chart.axisTitle,
      formatValue: chart.formatValue,
      formatTime: (t: number) => `${Math.round((T0 + 48 * HOUR - t) / HOUR)}h earlier`,
    }),
  );
}

/** The text of the y-axis tick labels, lowest value first. */
function axisLabels(html: string): string[] {
  return [...html.matchAll(/<text[^>]*data-axis="value"[^>]*>([^<]*)<\/text>/g)].map((match) => match[1]);
}

describe("moneyline line movement when the price crosses even money", () => {
  const chart = lineMovementChart(CROSSING, "moneyline", new Set(["cardinal:home"]))!;

  it("charts one outcome, by book", () => {
    expect(chart.outcome).toBe("Harbor City Tides");
    expect(chart.series.map((s) => s.name)).toEqual(["Northline", "Cardinal"]);
    expect(chart.series.map((s) => s.emphasis)).toEqual([false, true]);
  });

  it("plots the implied probability the API sent for each point", () => {
    expect(chart.unit).toBe("probability");
    expect(chart.series[0].points.map((p) => p.v)).toEqual([0.509804, 0.492611, 0.469484]);
    expect(chart.series[1].points.map((p) => p.v)).toEqual([0.537037, 0.454545]);
  });

  it("labels each point with the American price the API sent for it", () => {
    expect(chart.series[0].points.map((p) => p.label)).toEqual(["−104", "+103", "+113"]);
    expect(chart.series[1].points.map((p) => p.label)).toEqual(["−116", "+120"]);
  });

  it("draws a move across even money no taller than the probability it stands for", () => {
    // −104 to +103 is 1.7 points of implied probability; +103 to +113 is 2.3. On a linear axis
    // of American odds the first was drawn as 207 and the second as 10.
    const [a, b, c] = chart.series[0].points.map((p) => p.v);
    expect(a - b).toBeCloseTo(0.0172, 4);
    expect(a - b).toBeLessThan(b - c);
  });

  it("puts percentages on the axis, never a price that cannot exist", () => {
    const labels = axisLabels(render(chart));
    expect(labels).toEqual(["45.5%", "49.6%", "53.7%"]);
    for (const label of labels) expect(label).not.toMatch(/^[+−-]\d+$/);
  });

  it("says what the axis shows", () => {
    expect(chart.axisTitle).toBe("Implied probability of each price, bookmaker margin included. Higher on the chart is a shorter price.");
    expect(render(chart)).toContain(chart.axisTitle);
  });

  it("gives each point a tooltip with the book, the American price and the time", () => {
    const html = render(chart);
    expect(html).toContain("<title>Northline: −104, 48h earlier</title>");
    expect(html).toContain("<title>Northline: +103, 28h earlier</title>");
    expect(html).toContain("<title>Cardinal: +120, 18h earlier</title>");
    expect(html).not.toMatch(/<title>[^<]*%/);
  });

  it("shows each book's latest American price next to its name, and in the text summary", () => {
    const html = render(chart);
    expect(html).toMatch(/Northline<\/span>\s*<span[^>]*>\+113<\/span>/);
    expect(html).toMatch(/Cardinal<\/span>\s*<span[^>]*>\+120<\/span>/);
    expect(chart.summary).toBe("Line movement for Harbor City Tides across 2 sportsbooks. Latest price: Northline +113, Cardinal +120.");
  });

  it("takes both figures from the API and converts nothing", () => {
    // A price whose two formats do not agree stays as sent: the chart position is the API's
    // implied probability and the label is the API's American price.
    const odd = lineMovementChart(history("moneyline", [book("northline", "Northline", [{ hour: 0, price: price(-116, 1.862069, 0.6) }, { hour: 10, price: price(120, 2.2, 0.4) }])]), "moneyline", new Set())!;
    expect(odd.series[0].points.map((p) => [p.v, p.label])).toEqual([[0.6, "−116"], [0.4, "+120"]]);
  });
});

describe("spread and total line movement", () => {
  const spread = lineMovementChart(
    history("spread", [
      book("northline", "Northline", [
        { hour: 0, price: P.m104, line: -3.5 },
        { hour: 24, price: P.m116, line: -2.5 },
      ]),
      book("cardinal", "Cardinal", [{ hour: 0, price: P.m104, line: -3 }]),
    ]),
    "spread",
    new Set(),
  )!;

  it("keeps plotting the line", () => {
    expect(spread.unit).toBe("line");
    expect(spread.series[0].points.map((p) => p.v)).toEqual([-3.5, -2.5]);
    expect(spread.series[0].points.map((p) => p.label)).toEqual(["−3.5", "−2.5"]);
    expect(axisLabels(render(spread))).toEqual(["−3.5", "−3", "−2.5"]);
    expect(spread.axisTitle).toBe("Spread, in points.");
    expect(spread.summary).toBe("Line movement for Harbor City Tides across 2 sportsbooks. Latest line: Northline −2.5, Cardinal −3.");
  });

  it("leaves out a point that has no line", () => {
    const total = lineMovementChart(history("total", [book("northline", "Northline", [{ hour: 0, price: P.m104, line: 221.5 }, { hour: 5, price: P.m104 }], { key: "over", name: "Over" })]), "total", new Set())!;
    expect(total.series[0].points.map((p) => [p.v, p.label])).toEqual([[221.5, "221.5"]]);
    expect(total.axisTitle).toBe("Total, in points.");
  });

  it("is nothing when the API has no history", () => {
    expect(lineMovementChart(history("moneyline", []), "moneyline", new Set())).toBeNull();
  });
});
