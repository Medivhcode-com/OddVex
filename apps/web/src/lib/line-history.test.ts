import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LineHistoryChart, valueRange } from "@/components/ui/charts";
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
      valueAxis: chart.valueAxis,
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

  it("draws two points that share a time in one series, each with its own mark", () => {
    const twice = lineMovementChart(
      history("moneyline", [book("northline", "Northline", [{ hour: 0, price: P.m104 }, { hour: 0, price: P.p103 }, { hour: 2, price: P.p113 }])]),
      "moneyline",
      new Set(),
    )!;
    const html = render(twice);
    expect(html.match(/<title>/g)).toHaveLength(3);
    expect(html).toContain("<title>Northline: −104, 48h earlier</title>");
    expect(html).toContain("<title>Northline: +103, 48h earlier</title>");
  });

  it("takes both figures from the API and converts nothing", () => {
    // A price whose two formats do not agree stays as sent: the chart position is the API's
    // implied probability and the label is the API's American price.
    const odd = lineMovementChart(history("moneyline", [book("northline", "Northline", [{ hour: 0, price: price(-116, 1.862069, 0.6) }, { hour: 10, price: price(120, 2.2, 0.4) }])]), "moneyline", new Set())!;
    expect(odd.series[0].points.map((p) => [p.v, p.label])).toEqual([[0.6, "−116"], [0.4, "+120"]]);
  });
});

describe("moneyline line movement when the price barely moves", () => {
  const m110 = price(-110, 1.909091, 0.52381);
  /** The axis labels as numbers of percent. */
  const percents = (labels: string[]) => labels.map((label) => (/^\d{1,3}\.\d%$/.test(label) ? Number(label.slice(0, -1)) : Number.NaN));

  it("keeps a flat history on an axis of probabilities that can exist", () => {
    // Two books hold −110 for the whole window. Widening the flat range by one whole unit,
    // as the chart does for a line in points, put −47.6% and 152.4% on the axis.
    const flat = lineMovementChart(
      history("moneyline", [book("northline", "Northline", [{ hour: 0, price: m110 }, { hour: 24, price: m110 }]), book("cardinal", "Cardinal", [{ hour: 0, price: m110 }])]),
      "moneyline",
      new Set(),
    )!;
    const labels = axisLabels(render(flat));
    expect(labels).toEqual(["51.4%", "52.4%", "53.4%"]);
    for (const value of percents(labels)) {
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThanOrEqual(100);
    }
  });

  it("stays between 0% and 100% when a flat price sits at either end", () => {
    const short = price(-100000, 1.001, 0.999001);
    const long = price(100000, 1001, 0.000999);
    for (const [held, expected] of [
      [short, ["98.0%", "99.0%", "100.0%"]],
      [long, ["0.0%", "1.0%", "2.0%"]],
    ] as const) {
      const chart = lineMovementChart(history("moneyline", [book("northline", "Northline", [{ hour: 0, price: held }, { hour: 24, price: held }])]), "moneyline", new Set())!;
      expect(axisLabels(render(chart))).toEqual(expected);
    }
  });

  it("gives every tick its own label when the move is a fraction of a point", () => {
    // +10000 to +11000 is under a tenth of a point of probability. Stretched to the full
    // height of the chart, two of the three ticks read 0.9%.
    const chart = lineMovementChart(
      history("moneyline", [book("northline", "Northline", [{ hour: 0, price: price(10000, 101, 0.009901) }, { hour: 24, price: price(11000, 111, 0.009009) }])]),
      "moneyline",
      new Set(),
    )!;
    const labels = axisLabels(render(chart));
    expect(new Set(labels).size).toBe(3);
    expect(labels).toEqual(["0.0%", "1.0%", "2.0%"]);
  });

  it("leaves a wider range exactly as the prices set it", () => {
    const chart = lineMovementChart(CROSSING, "moneyline", new Set())!;
    expect(axisLabels(render(chart))).toEqual(["45.5%", "49.6%", "53.7%"]);
  });
});

describe("the ends of the chart's value axis", () => {
  const probability = { minSpan: 0.02, min: 0, max: 1 };

  it("widens a narrow range to the least width, around its middle", () => {
    const [low, high] = valueRange([0.5, 0.51], probability);
    expect(low).toBeCloseTo(0.495, 10);
    expect(high).toBeCloseTo(0.515, 10);
  });

  it("leaves a range that is wide enough alone", () => {
    expect(valueRange([0.4, 0.6], probability)).toEqual([0.4, 0.6]);
    expect(valueRange([-3.5, -2.5])).toEqual([-3.5, -2.5]);
  });

  it("slides a widened range inside the limits and keeps its width", () => {
    const [low, high] = valueRange([0.995], probability);
    expect(low).toBeCloseTo(0.98, 10);
    expect(high).toBe(1);
    expect(valueRange([0.001, 0.001], probability)).toEqual([0, 0.02]);
  });

  it("never cuts off a value it was given, even one outside the limits", () => {
    const [low, high] = valueRange([1.2, 1.2], probability);
    expect(low).toBeLessThan(1.2);
    expect(high).toBe(1.2);
  });

  it("gives values that are all the same one unit each way when no axis is described", () => {
    expect(valueRange([-110, -110])).toEqual([-111, -109]);
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

  it("widens a line that never moved by a point each way", () => {
    const flat = lineMovementChart(history("spread", [book("northline", "Northline", [{ hour: 0, price: P.m104, line: -3 }, { hour: 24, price: P.m116, line: -3 }])]), "spread", new Set())!;
    expect(axisLabels(render(flat))).toEqual(["−4", "−3", "−2"]);
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
