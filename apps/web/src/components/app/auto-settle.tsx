"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Schemas } from "@oddvex/types";
import { Button } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";

const REASONS: Record<string, string> = {
  not_gradeable: "not tied to a game and side",
  event_not_final: "game not finished",
  event_unavailable: "game no longer available",
};

/** Settles open bets that are tied to a finished game, from the final score. */
export function AutoSettleButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  async function run() {
    setBusy(true);
    setMessage(null);
    setFailed(false);
    try {
      const out = await clientApi<Schemas["AutoSettleOut"]>("/v1/bets/auto-settle", { method: "POST", body: {} });
      const counts = new Map<string, number>();
      for (const skip of out.skipped) counts.set(skip.reason, (counts.get(skip.reason) ?? 0) + 1);
      const skipped = [...counts].map(([reason, count]) => `${count} ${REASONS[reason] ?? reason}`).join(", ");
      setMessage(
        `${out.settled.length} ${out.settled.length === 1 ? "bet" : "bets"} settled from final scores.` + (skipped ? ` Left open: ${skipped}.` : ""),
      );
      router.refresh();
    } catch (caught) {
      setFailed(true);
      setMessage(caught instanceof ClientApiError ? caught.message : "Auto-settle failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button type="button" size="sm" variant="secondary" onClick={run} disabled={busy}>
        {busy ? "Checking scores" : "Settle from final scores"}
      </Button>
      {message ? (
        <p role={failed ? "alert" : "status"} className={`max-w-xs text-right text-xs ${failed ? "text-error" : "text-muted"}`}>
          {message}
        </p>
      ) : null}
    </div>
  );
}
