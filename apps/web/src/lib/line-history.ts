import type { Series } from "@/components/ui/charts";
import { formatAmerican, formatLine, formatPercent } from "@/lib/format";
import type { LineHistory } from "@/lib/types";

/**
 * What the line-movement chart on a game page draws, built from `GET /v1/events/{id}/line-history`.
 *
 * Moneyline: each point sits at the implied probability the API sent for that price
 * (`price.implied_probability`) and is labelled with the American price the API sent
 * (`price.american`). American odds are not plotted directly because they skip from −100 to
 * +100: on a straight axis a move across even money looks 200 points tall and the axis shows
 * prices that cannot exist. Nothing is converted here; both figures come from the API.
 *
 * Spread and total: each point sits at the line, as before.
 */
export type LineMovementChart = {
  series: Series[];
  unit: "probability" | "line";
  outcome: string;
  /** One sentence saying what the vertical axis shows. */
  axisTitle: string;
  /** The text alternative of the drawing, with each book's latest label. */
  summary: string;
  /** Formats a value on the vertical axis. */
  formatValue: (v: number) => string;
};

export function lineMovementChart(history: LineHistory, market: string, bestBooks: Set<string>): LineMovementChart | null {
  const first = history.series[0];
  if (!first) return null;
  // Chart one outcome so the lines are comparable: the first outcome the API lists.
  const chosen = history.series.filter((s) => s.outcome_key === first.outcome_key);
  const unit = market === "moneyline" ? "probability" : "line";
  const signed = market === "spread";
  const series = chosen
    .map((s) => ({
      name: s.sportsbook.name,
      emphasis: bestBooks.has(`${s.sportsbook.key}:${s.outcome_key}`),
      points: s.points
        .map((p) =>
          unit === "probability"
            ? { t: new Date(p.timestamp).getTime(), v: p.price.implied_probability, label: formatAmerican(p.price.american) }
            : { t: new Date(p.timestamp).getTime(), v: p.line ?? Number.NaN, label: formatLine(p.line, { signed }) },
        )
        .filter((p) => Number.isFinite(p.v) && Number.isFinite(p.t))
        .sort((a, b) => a.t - b.t),
    }))
    .filter((s) => s.points.length);
  const latest = series.map((s) => `${s.name} ${s.points[s.points.length - 1].label}`).join(", ");
  return {
    series,
    unit,
    outcome: first.outcome_name,
    axisTitle:
      unit === "probability"
        ? "Implied probability of each price, bookmaker margin included. Higher on the chart is a shorter price."
        : market === "spread"
          ? "Spread, in points."
          : "Total, in points.",
    summary: `Line movement for ${first.outcome_name} across ${series.length} ${series.length === 1 ? "sportsbook" : "sportsbooks"}.${latest ? ` Latest ${unit === "probability" ? "price" : "line"}: ${latest}.` : ""}`,
    formatValue: (v) => (unit === "probability" ? formatPercent(v) : formatLine(Math.round(v * 2) / 2, { signed })),
  };
}
