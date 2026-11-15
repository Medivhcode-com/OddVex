import type { Metadata } from "next";
import { PageHeader } from "@/components/app/page-header";
import { ParlayBuilder, type LegOption } from "@/components/app/parlay-builder";
import { api } from "@/lib/api";
import type { EventSummary } from "@/lib/types";

export const metadata: Metadata = { title: "Parlay research" };

export default async function ParlayPage() {
  const events = (await api<EventSummary[]>("/v1/events")).filter((event) => event.status !== "final").slice(0, 20);
  const options: LegOption[] = events.flatMap((event) => {
    const eventLabel = `${event.away_team.abbreviation} at ${event.home_team.abbreviation}`;
    return (["away", "home"] as const).flatMap((side) => {
      const best = event.best_moneyline?.[side];
      const team = side === "away" ? event.away_team : event.home_team;
      return best ? [{ id: `${event.id}:${side}`, eventId: event.id, eventLabel, label: `${team.name} ML`, price: best.price, book: best.sportsbook.name }] : [];
    });
  });
  return (
    <>
      <PageHeader
        title="Parlay research"
        description="See what a parlay pays and how often it has to win. When legs come from the same game, OddVex warns you and does not invent a combined probability."
      />
      <ParlayBuilder options={options} />
    </>
  );
}
