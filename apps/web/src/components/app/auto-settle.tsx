"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Schemas } from "@oddvex/types";
import { Button } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { autoSettleMessage } from "@/lib/tracker-messages";

/**
 * Settles open bets that are tied to a finished game, from the final score. One call checks
 * open bets until it has settled 200; when open bets are left unchecked the API says so
 * (`has_more`) and the button to run it again is offered next to the result.
 */
export function AutoSettleButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [more, setMore] = useState(false);

  async function run() {
    setBusy(true);
    setMessage(null);
    setFailed(false);
    setMore(false);
    try {
      const out = await clientApi<Schemas["AutoSettleOut"]>("/v1/bets/auto-settle", { method: "POST", body: {} });
      const result = autoSettleMessage(out);
      setMessage(result.text);
      setMore(result.more);
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
      {more && !busy ? (
        <Button type="button" size="sm" variant="ghost" onClick={run}>
          Check the next open bets
        </Button>
      ) : null}
    </div>
  );
}
