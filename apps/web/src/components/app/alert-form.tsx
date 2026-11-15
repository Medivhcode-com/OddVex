"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import clsx from "clsx";
import { Button, Field, Notice, SelectField } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { formatAmerican } from "@/lib/format";

export type AlertOutcome = { outcomeKey: string; label: string; line: number | null; american: number };
type Kind = "price_at_least" | "line_move" | "game_start" | "game_final";

const KINDS: { value: Kind; label: string }[] = [
  { value: "price_at_least", label: "Price reaches" },
  { value: "line_move", label: "Line moves" },
  { value: "game_start", label: "Before the game starts" },
  { value: "game_final", label: "When the game ends" },
];

/** Suggest a threshold a little better than the current best price, so the alert is not met on creation. */
function suggest(american: number): string {
  const next = american >= 100 ? american + 10 : american <= -110 ? american + 10 : 100;
  return formatAmerican(next === -100 ? 100 : next).replace("−", "-");
}

export function AlertForm({ eventId, market, outcomes, canStart }: { eventId: string; market: string; outcomes: AlertOutcome[]; canStart: boolean }) {
  const router = useRouter();
  const kinds = KINDS.filter((k) => (k.value === "line_move" ? market !== "moneyline" : k.value === "game_start" ? canStart : k.value === "price_at_least" ? outcomes.length > 0 : true));
  const [kind, setKind] = useState<Kind>(kinds[0].value);
  const [outcomeKey, setOutcomeKey] = useState(outcomes[0]?.outcomeKey ?? "");
  const outcome = outcomes.find((o) => o.outcomeKey === outcomeKey) ?? outcomes[0];
  const [threshold, setThreshold] = useState(outcome ? suggest(outcome.american) : "");
  const [move, setMove] = useState("1");
  const [minutes, setMinutes] = useState("60");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaved(false);
    setError(null);
    let body: Record<string, unknown>;
    if (kind === "price_at_least") {
      const value = threshold.trim().replace(/[−–]/g, "-");
      if (!outcome) return setError("Pick a side.");
      if (!/^[+-]?\d+$/.test(value) || Math.abs(Number(value)) < 100) return setError("Enter American odds, such as +150 or -110.");
      body = { kind, event_id: eventId, market, outcome_key: outcome.outcomeKey, threshold: value, odds_format: "american", ...(market === "moneyline" ? {} : { line: outcome.line }) };
    } else if (kind === "line_move") {
      const points = Number(move);
      if (!outcome) return setError("Pick a side.");
      if (!Number.isFinite(points) || points <= 0) return setError("Enter how many points the line must move, such as 1.");
      body = { kind, event_id: eventId, market, outcome_key: outcome.outcomeKey, min_move: points };
    } else if (kind === "game_start") {
      body = { kind, event_id: eventId, minutes_before: Number(minutes) };
    } else {
      body = { kind, event_id: eventId };
    }
    setBusy(true);
    try {
      await clientApi("/v1/alerts", { body });
      setSaved(true);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ClientApiError ? caught.message : "The alert was not saved. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const needsOutcome = kind === "price_at_least" || kind === "line_move";

  return (
    <form onSubmit={submit} className="space-y-4 p-4 sm:p-5" noValidate>
      <fieldset>
        <legend className="mb-2 text-sm font-medium">Tell me when</legend>
        <div className="flex flex-wrap gap-2">
          {kinds.map((option) => (
            <label
              key={option.value}
              className={clsx(
                "inline-flex min-h-9 cursor-pointer items-center rounded-full border px-3.5 text-sm font-medium has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-second",
                kind === option.value ? "border-ink bg-ink text-bg" : "border-line text-muted hover:border-line-strong hover:text-ink",
              )}
            >
              <input type="radio" name="alert-kind" value={option.value} checked={kind === option.value} onChange={() => { setKind(option.value); setSaved(false); setError(null); }} className="sr-only" />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="flex flex-wrap items-end gap-3">
        {needsOutcome ? (
          <SelectField
            id="alert-outcome"
            label="Side"
            className="min-w-0 flex-1"
            value={outcomeKey}
            onChange={(e) => {
              setOutcomeKey(e.target.value);
              const next = outcomes.find((o) => o.outcomeKey === e.target.value);
              if (next) setThreshold(suggest(next.american));
            }}
          >
            {outcomes.map((o) => (
              <option key={o.outcomeKey} value={o.outcomeKey}>
                {o.label}, best now {formatAmerican(o.american)}
              </option>
            ))}
          </SelectField>
        ) : null}
        {kind === "price_at_least" ? (
          <Field id="alert-threshold" label="Price at or above" className="w-40 [&_input]:font-mono" hint="American odds." value={threshold} onChange={(e) => setThreshold(e.target.value)} />
        ) : null}
        {kind === "line_move" ? (
          <Field id="alert-move" label="Moves by at least (points)" inputMode="decimal" className="w-48" value={move} onChange={(e) => setMove(e.target.value)} />
        ) : null}
        {kind === "game_start" ? (
          <SelectField id="alert-minutes" label="How long before" className="w-48" value={minutes} onChange={(e) => setMinutes(e.target.value)}>
            <option value="15">15 minutes</option>
            <option value="30">30 minutes</option>
            <option value="60">1 hour</option>
            <option value="120">2 hours</option>
          </SelectField>
        ) : null}
        <Button type="submit" variant="secondary" disabled={busy}>
          {busy ? "Saving alert" : "Save alert"}
        </Button>
      </div>

      <div aria-live="polite">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {saved ? (
          <Notice tone="accent">
            Alert saved. It is checked when you open OddVex. <Link href="/app/alerts">See your alerts</Link>
          </Notice>
        ) : null}
      </div>
    </form>
  );
}
