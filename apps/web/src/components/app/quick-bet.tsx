"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { Button, Field, Notice, SelectField } from "@/components/ui/primitives";
import { betSaveError, ClientRequestIds, stakeProblem } from "@/lib/bet-request";
import { clientApi } from "@/lib/client-api";
import { formatAmerican } from "@/lib/format";
import { quickBetRequest, type QuickBetPick } from "@/lib/quick-bet";

export type QuickBetOption = QuickBetPick;

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
  // One client_request_id per filled-in form (side and stake), so a retry after a lost answer is not saved twice.
  const [requestIds] = useState(() => new ClientRequestIds());
  const option = options.find((o) => o.outcomeKey === choice);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaved(false);
    if (!option) return setError("Pick a side.");
    const stakeError = stakeProblem(stake);
    if (stakeError) return setError(stakeError);
    setBusy(true);
    setError(null);
    try {
      // 201 for a new bet, 200 when the API had already stored this one: both mean saved.
      // The id follows the side and stake only: an auto-refresh can move the price before a resend.
      await clientApi("/v1/bets", { body: quickBetRequest(requestIds, { eventId, eventLabel, league, market }, option, stake) });
      requestIds.saved();
      setStake("");
      setSaved(true);
      router.refresh();
    } catch (caught) {
      setError(betSaveError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} onChange={() => requestIds.edited()} className="space-y-3 p-4 sm:p-5" noValidate>
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
