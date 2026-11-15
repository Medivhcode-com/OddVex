"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Field } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import type { Bet } from "@/lib/types";

const RESULTS = [
  ["won", "Won"],
  ["lost", "Lost"],
  ["push", "Push"],
  ["void", "Void"],
  ["half_won", "Half won"],
  ["half_lost", "Half lost"],
  ["cashout", "Cashed out"],
] as const;
const LEG_RESULTS = RESULTS.slice(0, 4);
const selectClass = "min-h-9 rounded-cell border border-line-strong bg-bg px-2 text-sm";
const cleanOdds = (raw: string) => raw.trim().replace(/[−–]/g, "-");

type Mode = "idle" | "legs" | "edit" | "delete";

export function BetActions({ bet, label }: { bet: Bet; label: string }) {
  const router = useRouter();
  const open = bet.status === "pending";
  const multi = bet.legs.length > 1;
  const [mode, setMode] = useState<Mode>("idle");
  const [result, setResult] = useState("won");
  const [cashout, setCashout] = useState("");
  const [legResults, setLegResults] = useState<Record<string, string>>(() => Object.fromEntries(bet.legs.map((leg) => [leg.id, "won"])));
  const [stake, setStake] = useState(String(bet.stake));
  const [sportsbook, setSportsbook] = useState(bet.sportsbook);
  const [notes, setNotes] = useState(bet.notes ?? "");
  const [closing, setClosing] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setMode("idle");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ClientApiError ? caught.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const settle = () => {
    const body: Record<string, unknown> = { result };
    if (result === "cashout") {
      const amount = Number(cashout);
      if (cashout.trim() === "" || !Number.isFinite(amount) || amount < 0) return setError("Enter the cash-out amount you received.");
      body.cashout_amount = amount;
    }
    return run(() => clientApi(`/v1/bets/${bet.id}/settle`, { body }));
  };

  const settleLegs = () =>
    run(() =>
      clientApi(`/v1/bets/${bet.id}/settle`, {
        body: { leg_results: bet.legs.map((leg) => ({ leg_id: leg.id, result: legResults[leg.id] })) },
      }),
    );

  const save = () => {
    const stakeValue = Number(stake);
    if (!Number.isFinite(stakeValue) || stakeValue <= 0) return setError("Enter a stake greater than zero.");
    if (!sportsbook.trim()) return setError("Enter the sportsbook.");
    const body: Record<string, unknown> = { notes: notes.trim() || null };
    if (open) {
      body.stake = stakeValue;
      body.sportsbook = sportsbook.trim();
    }
    if (!multi && closing.trim()) {
      body.closing_odds = [{ leg_id: bet.legs[0].id, closing_odds: cleanOdds(closing), odds_format: "american" }];
    }
    return run(() => clientApi(`/v1/bets/${bet.id}`, { method: "PATCH", body }));
  };

  return (
    <div className="flex w-full flex-col items-end gap-2 sm:w-auto">
      {mode === "idle" ? (
        <div className="flex flex-wrap items-center justify-end gap-2">
          {open ? (
            <>
              <label className="sr-only" htmlFor={`result-${bet.id}`}>
                Result for {label}
              </label>
              <select id={`result-${bet.id}`} value={result} onChange={(e) => setResult(e.target.value)} className={selectClass}>
                {RESULTS.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </select>
              {result === "cashout" ? (
                <>
                  <label className="sr-only" htmlFor={`cashout-${bet.id}`}>
                    Cash-out amount
                  </label>
                  <input id={`cashout-${bet.id}`} inputMode="decimal" placeholder="$ received" value={cashout} onChange={(e) => setCashout(e.target.value)} className="num min-h-9 w-28 rounded-cell border border-line-strong bg-bg px-2 text-sm" />
                </>
              ) : null}
              <Button size="sm" variant="secondary" disabled={busy} onClick={settle}>
                Settle
              </Button>
              {multi ? (
                <Button size="sm" variant="ghost" onClick={() => setMode("legs")}>
                  Settle by leg
                </Button>
              ) : null}
            </>
          ) : null}
          <Button size="sm" variant="ghost" aria-label={`Edit ${label}`} onClick={() => setMode("edit")}>
            Edit
          </Button>
          <Button size="sm" variant="ghost" aria-label={`Delete ${label}`} onClick={() => setMode("delete")}>
            Delete
          </Button>
        </div>
      ) : null}

      {mode === "legs" ? (
        <fieldset className="w-full rounded-cell border border-line p-3 sm:w-80">
          <legend className="px-1 text-sm font-medium">Result of each leg</legend>
          <ul className="space-y-2">
            {bet.legs.map((leg) => (
              <li key={leg.id} className="flex items-center justify-between gap-3">
                <label htmlFor={`leg-result-${leg.id}`} className="min-w-0 truncate text-sm">
                  {leg.selection}
                </label>
                <select id={`leg-result-${leg.id}`} value={legResults[leg.id]} onChange={(e) => setLegResults((current) => ({ ...current, [leg.id]: e.target.value }))} className={selectClass}>
                  {LEG_RESULTS.map(([value, text]) => (
                    <option key={value} value={value}>
                      {text}
                    </option>
                  ))}
                </select>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted">One lost leg loses the parlay. Pushed and void legs drop out and the odds are recalculated.</p>
          <div className="mt-3 flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setMode("idle")}>
              Cancel
            </Button>
            <Button size="sm" disabled={busy} onClick={settleLegs}>
              Settle parlay
            </Button>
          </div>
        </fieldset>
      ) : null}

      {mode === "edit" ? (
        <form
          className="w-full rounded-cell border border-line p-3 sm:w-80"
          onSubmit={(event) => {
            event.preventDefault();
            save();
          }}
        >
          <div className="space-y-3">
            {open ? (
              <>
                <Field id={`edit-stake-${bet.id}`} label="Stake ($)" inputMode="decimal" value={stake} onChange={(e) => setStake(e.target.value)} />
                <Field id={`edit-book-${bet.id}`} label="Sportsbook" value={sportsbook} onChange={(e) => setSportsbook(e.target.value)} />
              </>
            ) : (
              <p className="text-xs text-muted">Stake and odds are locked once a bet is settled. To correct the result, delete the bet and log it again.</p>
            )}
            {!multi ? (
              <Field
                id={`edit-closing-${bet.id}`}
                label="Closing odds (American)"
                className="[&_input]:font-mono"
                placeholder={bet.legs[0].closing_price ? String(Math.round(bet.legs[0].closing_price.american)) : "Optional"}
                hint="Used for closing line value."
                value={closing}
                onChange={(e) => setClosing(e.target.value)}
              />
            ) : null}
            <Field id={`edit-notes-${bet.id}`} label="Notes" value={notes} maxLength={500} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <Button type="button" size="sm" variant="ghost" onClick={() => setMode("idle")}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={busy}>
              Save changes
            </Button>
          </div>
        </form>
      ) : null}

      {mode === "delete" ? (
        <div className="flex flex-wrap items-center justify-end gap-2">
          <span className="text-sm text-muted">Delete this bet for good?</span>
          <Button size="sm" variant="danger" disabled={busy} onClick={() => run(() => clientApi(`/v1/bets/${bet.id}`, { method: "DELETE" }))}>
            Delete bet
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setMode("idle")}>
            Keep
          </Button>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="w-full text-right text-sm text-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
