"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { Button, Field, Notice, SelectField } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { formatAmerican } from "@/lib/format";

export type QuickBetOption = {
  outcomeKey: string;
  label: string;
  line: number | null;
  american: number;
  sportsbook: string;
};

/**
 * Logs a bet on this game at the best current price, with a structured selection
 * so the tracker can grade it from the final score. OddVex records the bet. It does not place it.
 */
export function QuickBet({ eventId, eventLabel, league, market, options }: { eventId: string; eventLabel: string; league: string; market: string; options: QuickBetOption[] }) {
  const router = useRouter();
  const [choice, setChoice] = useState(options[0]?.outcomeKey ?? "");
  const [stake, setStake] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const option = options.find((o) => o.outcomeKey === choice);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaved(false);
    const amount = Number(stake);
    if (!option) return setError("Pick a side.");
    if (!Number.isFinite(amount) || amount <= 0) return setError("Enter a stake greater than zero.");
    setBusy(true);
    setError(null);
    try {
      await clientApi("/v1/bets", {
        body: {
          bet_type: "straight",
          stake: amount,
          sportsbook: option.sportsbook,
          legs: [
            {
              selection: option.label,
              market,
              league,
              event_id: eventId,
              event_label: eventLabel,
              outcome_key: option.outcomeKey,
              line: option.line,
              odds: String(Math.round(option.american)),
              odds_format: "american",
            },
          ],
        },
      });
      setStake("");
      setSaved(true);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ClientApiError ? caught.message : "The bet was not saved. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 p-4 sm:p-5" noValidate>
      <div className="flex flex-wrap items-end gap-3">
        <SelectField id="quick-bet-side" label="Side, at the best current price" className="min-w-0 flex-1" value={choice} onChange={(e) => setChoice(e.target.value)}>
          {options.map((o) => (
            <option key={o.outcomeKey} value={o.outcomeKey}>
              {o.label} {formatAmerican(o.american)} at {o.sportsbook}
            </option>
          ))}
        </SelectField>
        <Field id="quick-bet-stake" label="Stake ($)" inputMode="decimal" className="w-28" placeholder="25.00" value={stake} onChange={(e) => setStake(e.target.value)} />
        <Button type="submit" disabled={busy}>
          {busy ? "Saving bet" : "Add to tracker"}
        </Button>
      </div>
      <div aria-live="polite">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {saved ? (
          <Notice tone="accent">
            Bet saved. Because it is tied to this game, the tracker can settle it from the final score.{" "}
            <Link href="/app/tracker">Open the tracker</Link>
          </Notice>
        ) : null}
      </div>
    </form>
  );
}
