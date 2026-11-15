"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";

const RESULTS = [
  ["won", "Won"],
  ["lost", "Lost"],
  ["push", "Push"],
  ["void", "Void"],
  ["half_won", "Half won"],
  ["half_lost", "Half lost"],
  ["cashout", "Cashed out"],
] as const;

export function BetActions({ betId, pending: isOpenBet, label }: { betId: string; pending: boolean; label: string }) {
  const router = useRouter();
  const [result, setResult] = useState("won");
  const [cashout, setCashout] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ClientApiError ? caught.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  const settle = () => {
    const body: Record<string, unknown> = { result };
    if (result === "cashout") {
      const amount = Number(cashout);
      if (!Number.isFinite(amount) || amount < 0) return setError("Enter the cash-out amount you received.");
      body.cashout_amount = amount;
    }
    return run(() => clientApi(`/v1/bets/${betId}/settle`, { body }));
  };

  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {isOpenBet ? (
        <>
          <label className="sr-only" htmlFor={`result-${betId}`}>Result for {label}</label>
          <select id={`result-${betId}`} value={result} onChange={(e) => setResult(e.target.value)} className="min-h-9 rounded-cell border border-line-strong bg-bg px-2 text-sm">
            {RESULTS.map(([value, text]) => (
              <option key={value} value={value}>{text}</option>
            ))}
          </select>
          {result === "cashout" ? (
            <>
              <label className="sr-only" htmlFor={`cashout-${betId}`}>Cash-out amount</label>
              <input id={`cashout-${betId}`} inputMode="decimal" placeholder="$ received" value={cashout} onChange={(e) => setCashout(e.target.value)} className="num min-h-9 w-28 rounded-cell border border-line-strong bg-bg px-2 text-sm" />
            </>
          ) : null}
          <Button size="sm" variant="secondary" disabled={busy} onClick={settle}>
            Settle
          </Button>
        </>
      ) : null}
      {confirming ? (
        <>
          <Button size="sm" variant="danger" disabled={busy} onClick={() => run(() => clientApi(`/v1/bets/${betId}`, { method: "DELETE" }))}>
            Delete bet
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
            Keep
          </Button>
        </>
      ) : (
        <Button size="sm" variant="ghost" aria-label={`Delete ${label}`} onClick={() => setConfirming(true)}>
          Delete
        </Button>
      )}
      {error ? <p role="alert" className="w-full text-right text-sm text-error">{error}</p> : null}
    </div>
  );
}
