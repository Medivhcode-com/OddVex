import { useCallback, useRef } from 'react';

import { useDraft } from '@/session/drafts';
import { newClientRequestId } from '@/utils/request-id';

/**
 * The id sent with the last save that has not succeeded yet, what the person had filled in (as JSON), and whether a
 * save since the last success went without a clear answer (so it may be on the server).
 */
type Attempt = { id: string; body: string; unconfirmed?: boolean } | null;

/**
 * Said in place of `DRAFT_KEPT` when the form that came back after a sign-out holds a save that got no clear answer
 * (`markUnconfirmed`): that save may have reached the server, so "nothing was saved" could be untrue.
 */
export const DRAFT_KEPT_UNCONFIRMED =
  'You were signed out before OddVex could confirm the save, so this bet may already be in your tracker. What you entered is still here. Check the tracker before you save it again.';

/**
 * The `client_request_id` for a bet form whose drafts are keyed `<form>:<field>`. `idFor(filled)` returns the id to
 * send, where `filled` is what the person filled in (for Log a bet the whole body; for "Track a bet on this game"
 * the game, market, side and stake, not the board's price, which a refresh can change). It returns the id of the
 * last attempt when that attempt had the same `filled` and has not succeeded, a new id otherwise (a first save, or
 * a form edited after a failure). Only the last attempt is remembered: changing the form, saving that, and changing
 * it back gives a new id. `clear()` is called when the save succeeds, before the form reports the save to the drafts
 * module, so the next bet gets an id of its own. `markUnconfirmed()` is called when a save got no clear answer
 * (`saveMayBeStored`); `unconfirmed` then stays true, across edits, until a save succeeds, and the form shows
 * `DRAFT_KEPT_UNCONFIRMED` instead of `DRAFT_KEPT` if it comes back after a sign-out.
 *
 * The attempt is also held in a ref, so two presses before React renders again (a fast double tap) send the same
 * id; the API answers the second with the bet the first stored.
 *
 * The attempt is itself a draft field (`<form>:request`): when the session ends before the save succeeds, it is
 * kept with the other fields and comes back with them. A save that reached the server before the session ended
 * is then sent again with the same id, and the API returns the bet it already stored instead of saving another.
 */
export function useClientRequestId(form: string): {
  idFor: (filled: unknown) => string;
  clear: () => void;
  markUnconfirmed: () => void;
  unconfirmed: boolean;
} {
  const [attempt, setAttempt] = useDraft<Attempt>(`${form}:request`, null);
  // Only this hook writes the attempt, so the ref always holds its latest value, even before React renders it.
  const latest = useRef(attempt);
  const write = useCallback(
    (next: Attempt) => {
      latest.current = next;
      setAttempt(next);
    },
    [setAttempt],
  );
  const idFor = useCallback(
    (filled: unknown) => {
      const sent = JSON.stringify(filled);
      const last = latest.current;
      if (last && last.body === sent) return last.id;
      const next = { id: newClientRequestId(), body: sent, unconfirmed: last?.unconfirmed ?? false };
      write(next);
      return next.id;
    },
    [write],
  );
  const clear = useCallback(() => write(null), [write]);
  const markUnconfirmed = useCallback(() => {
    const last = latest.current;
    if (last && !last.unconfirmed) write({ ...last, unconfirmed: true });
  }, [write]);
  return { idFor, clear, markUnconfirmed, unconfirmed: attempt?.unconfirmed === true };
}
