"use client";

import Link from "next/link";
import { useState } from "react";
import { TextArea } from "@/components/app/community/text-area";
import type { QuickBetOption } from "@/components/app/quick-bet";
import { Button, Notice, SelectField } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { ANALYSIS_MAX, communityError, pickLimitMessage, RULES_REMINDER, type Pick } from "@/lib/community-copy";
import { formatAmerican } from "@/lib/format";

function existingPickId(error: ClientApiError): string | null {
  const id = error.details && typeof error.details === "object" ? (error.details as { pick_id?: unknown }).pick_id : null;
  return typeof id === "string" ? id : null;
}

/**
 * Posts a structured pick on this game and market. There is no stake, no size and no
 * confidence field: the API accepts none. The price is recorded by the API when the pick
 * is posted, from the best open price at that moment.
 */
export function SharePick({ eventId, market, options }: { eventId: string; market: string; options: QuickBetOption[] }) {
  const [choice, setChoice] = useState(options[0]?.outcomeKey ?? "");
  const [analysis, setAnalysis] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [existing, setExisting] = useState<string | null>(null);
  const [posted, setPosted] = useState<Pick | null>(null);
  const option = options.find((entry) => entry.outcomeKey === choice);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPosted(null);
    setExisting(null);
    if (!option) return setError("Choose an outcome.");
    if (analysis.length > ANALYSIS_MAX) return setError(`Keep the analysis to ${ANALYSIS_MAX} characters or fewer.`);
    setBusy(true);
    setError(null);
    try {
      const pick = await clientApi<Pick>("/v1/community/picks", {
        body: { event_id: eventId, market, outcome_key: option.outcomeKey, line: option.line, analysis: analysis.trim() ? analysis : null },
      });
      setPosted(pick);
      setAnalysis("");
    } catch (caught) {
      if (caught instanceof ClientApiError) {
        setError(pickLimitMessage(caught) ?? communityError(caught, "The pick was not posted. Try again."));
        if (caught.code === "pick_exists") setExisting(existingPickId(caught));
      } else {
        setError("The pick was not posted. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4 p-4 sm:p-5">
      <SelectField id="share-pick-outcome" label="Outcome, at the best current price" className="max-w-xl" value={choice} onChange={(event) => setChoice(event.target.value)}>
        {options.map((entry) => (
          <option key={entry.outcomeKey} value={entry.outcomeKey}>
            {entry.label} {formatAmerican(entry.american)} at {entry.sportsbook}
          </option>
        ))}
      </SelectField>
      <TextArea
        id="share-pick-analysis"
        label="Analysis (optional)"
        max={ANALYSIS_MAX}
        value={analysis}
        onChange={(event) => setAnalysis(event.target.value)}
        hint={RULES_REMINDER}
        rows={4}
        className="max-w-xl"
      />
      <p className="max-w-prose text-sm text-muted">
        OddVex records the best open price at the moment you post, and grades the pick from the final score. One pick per game and market. A pick can&rsquo;t be edited, and
        it can&rsquo;t be deleted after the game starts.
      </p>
      <Button type="submit" disabled={busy}>
        {busy ? "Posting" : "Post pick"}
      </Button>
      <div aria-live="polite" className="space-y-2">
        {error ? (
          <Notice tone="error">
            {error}
            {existing ? (
              <>
                {" "}
                <Link href={`/app/community/picks/${encodeURIComponent(existing)}`}>Open your pick</Link>
              </>
            ) : null}
          </Notice>
        ) : null}
        {posted ? (
          <Notice tone="accent" title="Pick posted">
            {posted.selection}, recorded at {formatAmerican(posted.price.american)} at {posted.sportsbook.name}.{" "}
            <Link href={`/app/community/picks/${encodeURIComponent(posted.id)}`}>Open the pick</Link>
          </Notice>
        ) : null}
      </div>
    </form>
  );
}
