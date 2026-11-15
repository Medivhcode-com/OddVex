import type { Metadata } from "next";
import { EventCard } from "@/components/app/event-bits";
import { AutoRefresh } from "@/components/app/auto-refresh";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState, Panel, Segmented } from "@/components/ui/primitives";
import { api, withQuery } from "@/lib/api";
import { getLeagues, leagueLabel, pick } from "@/lib/leagues";
import type { EventSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Games" };

const STATUSES = ["all", "live", "upcoming", "final"] as const;
const STATUS_LABEL = { all: "All", live: "Live", upcoming: "Upcoming", final: "Final" };

export default async function GamesPage({ searchParams }: { searchParams: Promise<{ league?: string; status?: string }> }) {
  const params = await searchParams;
  const leagues = await getLeagues();
  const league = pick(params.league, ["all", ...leagues.map((l) => l.key)], "all");
  const status = pick(params.status, STATUSES, "all");
  const events = await api<EventSummary[]>("/v1/events", {
    query: { league: league === "all" ? undefined : league, status: status === "all" ? undefined : status },
  });
  const href = (next: { league?: string; status?: string }) =>
    withQuery("/app/games", {
      league: (next.league ?? league) === "all" ? undefined : (next.league ?? league),
      status: (next.status ?? status) === "all" ? undefined : (next.status ?? status),
    });

  const groups = (["live", "upcoming", "final"] as const)
    .map((key) => ({ key, events: events.filter((event) => event.status === key) }))
    .filter((group) => group.events.length);

  return (
    <>
      <PageHeader title="Games" description="Scores and the best moneyline on each side. Open a game to compare every book." actions={<AutoRefresh seconds={60} />} />
      <div className="mb-6 space-y-1">
        <Segmented
          label="League"
          current={league}
          options={[{ value: "all", label: "All leagues", href: href({ league: "all" }) }, ...leagues.map((l) => ({ value: l.key, label: l.name, href: href({ league: l.key }) }))]}
        />
        <Segmented label="Status" current={status} options={STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s], href: href({ status: s }) }))} />
      </div>
      {groups.length === 0 ? (
        <Panel>
          <EmptyState title="No games match these filters">Try another league, or switch status to All.</EmptyState>
        </Panel>
      ) : (
        groups.map((group) => (
          <section key={group.key} aria-labelledby={`games-${group.key}`} className="mb-8">
            <h2 id={`games-${group.key}`} className="mb-3 text-sm font-semibold text-muted">
              {STATUS_LABEL[group.key]} <span className="num font-normal">({group.events.length})</span>
            </h2>
            <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {group.events.map((event) => (
                <li key={event.id}>
                  <EventCard event={event} leagueName={leagueLabel(leagues, event.league)} />
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </>
  );
}
