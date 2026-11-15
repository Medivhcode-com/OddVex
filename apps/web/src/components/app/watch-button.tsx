"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import clsx from "clsx";
import { clientApi, ClientApiError } from "@/lib/client-api";

/**
 * Follow or unfollow a team, player or game. Signed-out visitors are sent to log in and brought back.
 * The pressed state is carried by aria-pressed, a filled star and the word, not by color.
 */
export function WatchButton({
  kind,
  refId,
  name,
  itemId,
  signedIn,
  returnTo,
}: {
  kind: "team" | "player" | "event";
  refId: string;
  name: string;
  itemId: string | null;
  signedIn: boolean;
  returnTo: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const watching = itemId !== null;

  async function toggle() {
    if (!signedIn) return router.push(`/login?next=${encodeURIComponent(returnTo)}`);
    setBusy(true);
    setError(null);
    try {
      if (itemId) await clientApi(`/v1/watchlist/${itemId}`, { method: "DELETE" });
      else await clientApi("/v1/watchlist", { body: { kind, ref_id: refId } });
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ClientApiError ? caught.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-start">
      <button
        type="button"
        aria-pressed={watching}
        disabled={busy}
        onClick={toggle}
        className={clsx(
          "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3 text-sm font-medium transition-colors disabled:opacity-60",
          watching ? "border-accent bg-accent-soft text-ink" : "border-line text-muted hover:border-line-strong hover:text-ink",
        )}
      >
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" fill={watching ? "var(--ov-accent)" : "none"} stroke={watching ? "var(--ov-accent)" : "currentColor"} strokeWidth="1.3" strokeLinejoin="round">
          <path d="M7 1.2l1.75 3.6 3.95.55-2.85 2.8.67 3.95L7 10.2l-3.52 1.9.67-3.95L1.3 5.35l3.95-.55z" />
        </svg>
        {watching ? "Following" : "Follow"} {name}
      </button>
      {error ? (
        <span role="alert" className="mt-1 text-xs text-error">
          {error}
        </span>
      ) : null}
    </span>
  );
}
