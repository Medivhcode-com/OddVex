import clsx from "clsx";

/**
 * Hand-rolled SVG charts. They are small, server-renderable and themeable through CSS variables.
 * Every chart takes a text `summary` that is exposed to assistive tech; the drawing is decorative.
 */


function scale(values: number[], size: number, pad: number, invert = false) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return (v: number) => {
    const t = (v - min) / span;
    return pad + (invert ? 1 - t : t) * (size - pad * 2);
  };
}

export function Sparkline({
  values,
  width = 96,
  height = 28,
  tone = "second",
  summary,
}: {
  values: number[];
  width?: number;
  height?: number;
  tone?: "second" | "accent" | "error" | "muted";
  summary: string;
}) {
  if (values.length < 2) return <span className="text-xs text-muted">No history</span>;
  const sx = scale(values.map((_, i) => i), width, 2);
  const sy = scale(values, height, 3, true);
  const d = values.map((v, i) => `${i === 0 ? "M" : "L"}${sx(i).toFixed(1)} ${sy(v).toFixed(1)}`).join(" ");
  const color = { second: "var(--ov-second)", accent: "var(--ov-accent)", error: "var(--ov-error)", muted: "var(--ov-muted)" }[tone];
  const last = values.length - 1;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={summary} className="shrink-0">
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={sx(last)} cy={sy(values[last])} r="2.25" fill={color} />
    </svg>
  );
}

/** `label` is the text shown for a point: in its tooltip and, for the latest point, next to the series name. */
export type Series = { name: string; points: { t: number; v: number; label?: string }[]; emphasis?: boolean };

const SERIES_DASH = ["", "5 3", "2 3", "8 3 2 3", "1 4", "10 4"];

/** The label of a series' most recent point, if its points carry labels. */
function latestLabel(series: Series): string | undefined {
  return series.points.reduce<Series["points"][number] | undefined>((latest, p) => (!latest || p.t >= latest.t ? p : latest), undefined)?.label;
}

/**
 * Multi-series step chart for line movement. Series are told apart by dash pattern and a legend, not color alone.
 *
 * The vertical axis is linear in `v`, so `v` must be a quantity that is meaningful on a straight
 * scale (a probability, a line in points). Text that is not on such a scale, an American price
 * for example, goes in each point's `label`. `axisTitle` says in words what the axis shows.
 */
export function LineHistoryChart({
  series,
  formatValue,
  formatTime,
  summary,
  axisTitle,
  height = 220,
}: {
  series: Series[];
  formatValue: (v: number) => string;
  formatTime: (t: number) => string;
  summary: string;
  axisTitle?: string;
  height?: number;
}) {
  const all = series.flatMap((s) => s.points);
  if (all.length < 2) return <p className="px-5 py-8 text-sm text-muted">Not enough history to chart yet.</p>;
  const width = 720;
  const padL = 52;
  const padR = 12;
  const padT = 12;
  const padB = 28;
  const ts = all.map((p) => p.t);
  const vs = all.map((p) => p.v);
  const [t0, t1] = [Math.min(...ts), Math.max(...ts)];
  let [v0, v1] = [Math.min(...vs), Math.max(...vs)];
  if (v0 === v1) {
    v0 -= 1;
    v1 += 1;
  }
  const x = (t: number) => padL + ((t - t0) / (t1 - t0 || 1)) * (width - padL - padR);
  const y = (v: number) => padT + (1 - (v - v0) / (v1 - v0)) * (height - padT - padB);
  const ticks = [0, 0.5, 1].map((f) => v0 + (v1 - v0) * f);
  const timeTicks = [0, 0.5, 1].map((f) => t0 + (t1 - t0) * f);
  const stroke = (s: Series, i: number) => (s.emphasis ? "var(--ov-accent)" : i % 2 ? "var(--ov-second)" : "var(--ov-muted)");

  return (
    <figure>
      {axisTitle ? <p className="mb-2 px-1 text-xs text-muted">{axisTitle}</p> : null}
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label={summary}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={padL} x2={width - padR} y1={y(tick)} y2={y(tick)} stroke="var(--ov-grid)" strokeWidth="1" />
            <text x={padL - 8} y={y(tick) + 4} textAnchor="end" fontSize="11" fill="var(--ov-muted)" className="num" data-axis="value">
              {formatValue(tick)}
            </text>
          </g>
        ))}
        {timeTicks.map((tick, i) => (
          <text
            key={tick}
            x={x(tick)}
            y={height - 8}
            textAnchor={i === 0 ? "start" : i === 2 ? "end" : "middle"}
            fontSize="11"
            fill="var(--ov-muted)"
          >
            {formatTime(tick)}
          </text>
        ))}
        {series.map((s, i) => {
          const sorted = [...s.points].sort((a, b) => a.t - b.t);
          const d = sorted
            .map((p, j) => (j === 0 ? `M${x(p.t).toFixed(1)} ${y(p.v).toFixed(1)}` : `H${x(p.t).toFixed(1)} V${y(p.v).toFixed(1)}`))
            .join(" ");
          return (
            <path
              key={s.name}
              d={`${d} H${x(t1).toFixed(1)}`}
              fill="none"
              stroke={stroke(s, i)}
              strokeWidth={s.emphasis ? 2.25 : 1.4}
              strokeDasharray={s.emphasis ? "" : SERIES_DASH[i % SERIES_DASH.length]}
              strokeLinejoin="round"
            />
          );
        })}
        {/* A mark on every labelled point. Hovering it shows the label; the wider clear circle is the hover target. */}
        {series.map((s, i) =>
          s.points.map((p) =>
            p.label ? (
              <g key={`${s.name}-${p.t}`}>
                <title>{`${s.name}: ${p.label}, ${formatTime(p.t)}`}</title>
                <circle cx={x(p.t)} cy={y(p.v)} r="7" fill="transparent" pointerEvents="all" />
                <circle cx={x(p.t)} cy={y(p.v)} r={s.emphasis ? 2.75 : 2.25} fill={stroke(s, i)} />
              </g>
            ) : null,
          ),
        )}
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-x-4 gap-y-1 px-1 text-xs text-muted">
        {series.map((s, i) => (
          <span key={s.name} className="inline-flex items-center gap-1.5">
            <svg width="22" height="6" aria-hidden="true">
              <line
                x1="0"
                x2="22"
                y1="3"
                y2="3"
                stroke={stroke(s, i)}
                strokeWidth={s.emphasis ? 2.25 : 1.4}
                strokeDasharray={s.emphasis ? "" : SERIES_DASH[i % SERIES_DASH.length]}
              />
            </svg>
            <span>{s.name}</span>
            {latestLabel(s) ? <span className="num text-ink">{latestLabel(s)}</span> : null}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}

/** Game-log bars against a prop line. Over/under is encoded by position relative to the line and a text mark. */
export function GameLogBars({
  games,
  line,
  summary,
}: {
  games: { label: string; value: number; detail: string }[];
  line: number;
  summary: string;
}) {
  if (games.length === 0) return <p className="px-5 py-8 text-sm text-muted">No games in this window.</p>;
  const width = 720;
  const height = 240;
  const padL = 36;
  const padB = 40;
  const padT = 18;
  const max = Math.max(line, ...games.map((g) => g.value)) * 1.12 || 1;
  const band = (width - padL) / games.length;
  const barW = Math.min(34, band * 0.62);
  const y = (v: number) => padT + (1 - v / max) * (height - padT - padB);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label={summary}>
      {[0, max / 2, max].map((tick) => (
        <g key={tick}>
          <line x1={padL} x2={width} y1={y(tick)} y2={y(tick)} stroke="var(--ov-grid)" />
          <text x={padL - 6} y={y(tick) + 4} textAnchor="end" fontSize="11" fill="var(--ov-muted)" className="num">
            {Math.round(tick)}
          </text>
        </g>
      ))}
      {games.map((g, i) => {
        const cx = padL + band * i + band / 2;
        const over = g.value > line;
        const push = g.value === line;
        return (
          <g key={`${g.label}-${i}`}>
            <title>{g.detail}</title>
            <rect
              x={cx - barW / 2}
              y={y(g.value)}
              width={barW}
              height={Math.max(1, y(0) - y(g.value))}
              rx="3"
              fill={over ? "var(--ov-accent)" : push ? "var(--ov-warn)" : "var(--ov-raised)"}
              stroke={over || push ? "none" : "var(--ov-border-strong)"}
            />
            <text x={cx} y={y(g.value) - 5} textAnchor="middle" fontSize="11" fill="var(--ov-text)" className="num">
              {g.value}
            </text>
            <text x={cx} y={height - 22} textAnchor="middle" fontSize="10.5" fill="var(--ov-muted)">
              {g.label}
            </text>
            <text x={cx} y={height - 8} textAnchor="middle" fontSize="10.5" fill={over ? "var(--ov-accent)" : "var(--ov-muted)"}>
              {over ? "Over" : push ? "Push" : "Under"}
            </text>
          </g>
        );
      })}
      <line x1={padL} x2={width} y1={y(line)} y2={y(line)} stroke="var(--ov-second)" strokeWidth="1.5" strokeDasharray="6 4" />
      <text x={width - 4} y={y(line) - 6} textAnchor="end" fontSize="11" fill="var(--ov-second)" className="num">
        Line {line}
      </text>
    </svg>
  );
}

/** Cumulative profit/loss area chart with a zero baseline. */
export function ProfitChart({ points, summary, height = 220 }: { points: { t: number; v: number }[]; summary: string; height?: number }) {
  if (points.length < 2) return <p className="px-5 py-8 text-sm text-muted">Settle a few bets to see your results over time.</p>;
  const width = 720;
  const padL = 56;
  const padR = 10;
  const padT = 12;
  const padB = 26;
  const vs = [...points.map((p) => p.v), 0];
  const [v0, v1] = [Math.min(...vs), Math.max(...vs)];
  const span = v1 - v0 || 1;
  const [t0, t1] = [points[0].t, points[points.length - 1].t];
  const x = (t: number) => padL + ((t - t0) / (t1 - t0 || 1)) * (width - padL - padR);
  const y = (v: number) => padT + (1 - (v - v0) / span) * (height - padT - padB);
  const d = points.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)} ${y(p.v).toFixed(1)}`).join(" ");
  const up = points[points.length - 1].v >= 0;
  const color = up ? "var(--ov-accent)" : "var(--ov-error)";
  const fmt = (v: number) => `${v < 0 ? "−" : ""}$${Math.abs(Math.round(v))}`;
  const day = (t: number) => new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(new Date(t));
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label={summary}>
      {[v0, v1].map((tick) => (
        <text key={tick} x={padL - 8} y={y(tick) + 4} textAnchor="end" fontSize="11" fill="var(--ov-muted)" className="num">
          {fmt(tick)}
        </text>
      ))}
      <line x1={padL} x2={width - padR} y1={y(0)} y2={y(0)} stroke="var(--ov-border-strong)" strokeDasharray="3 4" />
      <text x={padL - 8} y={y(0) + 4} textAnchor="end" fontSize="11" fill="var(--ov-muted)" className="num">
        {v0 < 0 && v1 > 0 ? "$0" : ""}
      </text>
      <path d={`${d} L${x(t1)} ${y(0)} L${x(t0)} ${y(0)} Z`} fill={color} opacity="0.1" />
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
      <text x={padL} y={height - 6} fontSize="11" fill="var(--ov-muted)">
        {day(t0)}
      </text>
      <text x={width - padR} y={height - 6} textAnchor="end" fontSize="11" fill="var(--ov-muted)">
        {day(t1)}
      </text>
    </svg>
  );
}

/** Horizontal bar for a 0..1 share, e.g. hit rate or no-vig probability. */
export function Meter({ value, label, className }: { value: number; label: string; className?: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      aria-label={label}
      className={clsx("h-1.5 w-full overflow-hidden rounded-full bg-raised", className)}
    >
      <div className="h-full rounded-full bg-second" style={{ width: `${pct}%` }} />
    </div>
  );
}
