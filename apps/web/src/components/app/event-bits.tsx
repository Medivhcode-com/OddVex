import Link from "next/link";
import { Price } from "@/components/app/odds-format";
import { Badge } from "@/components/ui/primitives";
import { formatDay, formatStart } from "@/lib/format";
import type { BestSide, EventSummary } from "@/lib/types";

export function StatusBadge({ event }: { event: EventSummary }) {
  if (event.status === "live") {
    return (
      <Badge tone="accent">
        <span aria-hidden="true" className="size-1.5 rounded-full bg-accent" />
        Live{event.status_detail ? `, ${event.status_detail}` : ""}
      </Badge>
    );
  }
  if (event.status === "final") return <Badge>Final</Badge>;
  return (
    <span className="text-sm text-muted">
      {formatDay(event.start_time)}, {formatStart(event.start_time)}
    </span>
  );
}

function Side({ name, abbr, score, best, winner }: { name: string; abbr: string; score?: number; best?: BestSide; winner: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span aria-hidden="true" className="num grid size-8 shrink-0 place-items-center rounded-cell bg-raised text-[0.6875rem] font-semibold text-muted">
        {abbr}
      </span>
      <span className={`min-w-0 flex-1 leading-snug ${winner ? "font-semibold" : "font-medium"}`}>{name}</span>
      {score !== undefined ? <span className={`num text-lg ${winner ? "font-semibold" : "text-muted"}`}>{score}</span> : null}
      {best ? (
        <span className="flex w-20 shrink-0 flex-col items-end leading-tight">
          <Price price={best.price} className="font-medium" />
          <span className="max-w-20 truncate text-[0.6875rem] text-muted">{best.sportsbook.name}</span>
        </span>
      ) : score === undefined ? (
        <span className="w-24 text-right text-xs text-muted">No price</span>
      ) : null}
    </div>
  );
}

/** One game as a tappable card: status, both sides, and the best moneyline on each. */
export function EventCard({ event, leagueName }: { event: EventSummary; leagueName: string }) {
  const { score } = event;
  const final = event.status === "final" && score;
  const showPrices = event.status !== "final";
  return (
    <Link
      href={`/app/games/${event.id}`}
      className="block rounded-panel border border-line bg-surface p-4 transition-colors hover:border-line-strong"
      aria-label={`${event.away_team.name} at ${event.home_team.name}, ${leagueName}`}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <StatusBadge event={event} />
        <span className="text-xs text-muted">{leagueName}</span>
      </div>
      <div className="space-y-2.5">
        <Side
          name={event.away_team.name}
          abbr={event.away_team.abbreviation}
          score={score?.away}
          best={showPrices ? event.best_moneyline?.away : undefined}
          winner={Boolean(final && score.away > score.home)}
        />
        <Side
          name={event.home_team.name}
          abbr={event.home_team.abbreviation}
          score={score?.home}
          best={showPrices ? event.best_moneyline?.home : undefined}
          winner={Boolean(final && score.home > score.away)}
        />
      </div>
      {showPrices ? <p className="mt-3 text-right text-[0.6875rem] text-muted">Best moneyline</p> : null}
    </Link>
  );
}
