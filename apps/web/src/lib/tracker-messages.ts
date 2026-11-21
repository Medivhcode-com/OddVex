import type { Schemas } from "@oddvex/types";
import { ClientApiError } from "@/lib/client-api";
import { tryAgainText } from "@/lib/retry";

/** The sentences the tracker's auto-settle button, sync panel and export button show. Pure, so they are unit-tested. */

const REASONS: Record<string, string> = {
  not_gradeable: "not tied to a game and side",
  event_not_final: "game not finished",
  event_unavailable: "game no longer available",
  manual_result_required: "needs its result entered by hand",
};

/**
 * What one auto-settle call did. `more` is the API's `has_more`: the call stopped at the most
 * bets one call settles and open bets were left unchecked, so it can be run again.
 */
export function autoSettleMessage(out: Schemas["AutoSettleOut"]): { text: string; more: boolean } {
  const counts = new Map<string, number>();
  for (const skip of out.skipped) counts.set(skip.reason, (counts.get(skip.reason) ?? 0) + 1);
  const skipped = [...counts].map(([reason, count]) => `${count} ${REASONS[reason] ?? reason}`).join(", ");
  const more = out.has_more === true;
  const text =
    `${out.settled.length} ${out.settled.length === 1 ? "bet" : "bets"} settled from final scores.` +
    (skipped ? ` Left open: ${skipped}.` : "") +
    (more ? " More open bets are left to check." : "");
  return { text, more };
}

/**
 * What one sync run did. A succeeded run can still have left bets out (the account is full, or
 * the provider sent a value that cannot be recorded); the API then says how many and why in
 * `error_message`, and that sentence is shown.
 */
export function syncRunMessage(result: Schemas["SyncRunOut"]): { tone: "accent" | "warn"; text: string } {
  if (result.status === "failed") return { tone: "warn", text: `Sync failed${result.retryable ? " and can be retried" : ""}: ${result.error_message ?? "no detail given"}.` };
  const done = `Sync finished. ${result.imported_count} new ${result.imported_count === 1 ? "bet" : "bets"} imported, ${result.duplicate_count} already here.`;
  return result.error_message ? { tone: "warn", text: `${done} ${result.error_message}` } : { tone: "accent", text: done };
}

/** Why "Download my data" did not download. Exports are limited per account (429 with the wait). */
export function exportError(caught: unknown): string {
  if (caught instanceof ClientApiError && caught.status === 429) return `You have asked for several exports in a short time. ${tryAgainText(caught.details)}`;
  return caught instanceof ClientApiError ? caught.message : "The export failed. Try again.";
}
