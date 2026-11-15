"use client";

import { useState } from "react";
import { Button, Field, Notice, Panel, PanelHeader, SelectField, Stat } from "@/components/ui/primitives";
import { Price } from "@/components/app/odds-format";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { formatAmerican, formatMoney, formatPercent } from "@/lib/format";
import type { PriceT } from "@/lib/types";

export type LegOption = { id: string; eventId: string; eventLabel: string; label: string; price: PriceT; book: string };
type Leg = { key: string; label: string; odds: string; eventId: string | null; detail: string };
type ParlayResult = {
  legs: { label: string; price: PriceT; counted: boolean }[];
  combined_price: PriceT | null;
  combined_decimal: number;
  active_legs: number;
  stake?: number | null;
  payout?: number | null;
  profit?: number | null;
  combined_probability?: number | null;
  probability_note: string;
  correlation_warnings: string[];
  steps: string[];
};

export function ParlayBuilder({ options }: { options: LegOption[] }) {
  const [legs, setLegs] = useState<Leg[]>([]);
  const [choice, setChoice] = useState(options[0]?.id ?? "");
  const [manualLabel, setManualLabel] = useState("");
  const [manualOdds, setManualOdds] = useState("");
  const [stake, setStake] = useState("10");
  const [result, setResult] = useState<ParlayResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const change = (next: Leg[]) => {
    setLegs(next);
    setResult(null);
  };
  const addOption = () => {
    const option = options.find((o) => o.id === choice);
    if (!option) return;
    change([...legs, { key: `${option.id}-${legs.length}-${Date.now()}`, label: option.label, odds: String(Math.round(option.price.american)), eventId: option.eventId, detail: `${option.eventLabel}, ${option.book}` }]);
  };
  const addManual = () => {
    if (!manualLabel.trim() || !manualOdds.trim()) return setError("A custom leg needs a name and American odds.");
    setError(null);
    change([...legs, { key: `manual-${Date.now()}`, label: manualLabel.trim(), odds: manualOdds.trim().replace(/[−–]/g, "-"), eventId: null, detail: "Custom leg" }]);
    setManualLabel("");
    setManualOdds("");
  };

  async function calculate() {
    if (legs.length < 2) return setError("Add at least two legs.");
    setBusy(true);
    setError(null);
    try {
      setResult(
        await clientApi<ParlayResult>("/v1/quant/parlay", {
          body: { stake: Number(stake) > 0 ? Number(stake) : null, legs: legs.map((leg) => ({ odds: leg.odds, odds_format: "american", label: leg.label, event_id: leg.eventId })) },
        }),
      );
    } catch (caught) {
      setResult(null);
      setError(caught instanceof ClientApiError ? caught.message : "The parlay could not be calculated.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1.1fr_1fr]">
      <Panel aria-labelledby="legs-heading">
        <PanelHeader id="legs-heading" title="Legs" description="Add moneylines from the board or type your own." />
        <div className="space-y-4 p-4 sm:p-5">
          {options.length ? (
            <div className="flex flex-wrap items-end gap-3">
              <SelectField id="parlay-option" label="From tonight's board" className="min-w-0 flex-1" value={choice} onChange={(e) => setChoice(e.target.value)}>
                {options.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label} {formatAmerican(option.price.american)} ({option.eventLabel})
                  </option>
                ))}
              </SelectField>
              <Button type="button" variant="secondary" onClick={addOption}>Add leg</Button>
            </div>
          ) : null}
          <div className="flex flex-wrap items-end gap-3">
            <Field id="parlay-manual-label" label="Custom leg" className="min-w-0 flex-1" placeholder="Player over 22.5 points" value={manualLabel} onChange={(e) => setManualLabel(e.target.value)} />
            <Field id="parlay-manual-odds" label="American odds" className="w-32 [&_input]:font-mono" placeholder="-115" value={manualOdds} onChange={(e) => setManualOdds(e.target.value)} />
            <Button type="button" variant="secondary" onClick={addManual}>Add custom leg</Button>
          </div>
          {legs.length === 0 ? (
            <p className="rounded-cell border border-dashed border-line-strong px-4 py-6 text-center text-sm text-muted">No legs yet. Add two or more to see the combined price.</p>
          ) : (
            <ol className="divide-y divide-line rounded-cell border border-line">
              {legs.map((leg, index) => (
                <li key={leg.key} className="flex items-center gap-3 px-3 py-2.5">
                  <span className="num w-5 text-sm text-muted">{index + 1}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{leg.label}</span>
                    <span className="block truncate text-xs text-muted">{leg.detail}</span>
                  </span>
                  <span className="num font-medium">{leg.odds.startsWith("-") || leg.odds.startsWith("+") ? leg.odds.replace("-", "−") : `+${leg.odds}`}</span>
                  <Button type="button" variant="ghost" size="sm" aria-label={`Remove ${leg.label}`} onClick={() => change(legs.filter((l) => l.key !== leg.key))}>
                    Remove
                  </Button>
                </li>
              ))}
            </ol>
          )}
          <div className="flex flex-wrap items-end gap-3">
            <Field id="parlay-stake" label="Stake ($)" inputMode="decimal" className="w-32" value={stake} onChange={(e) => setStake(e.target.value)} />
            <Button type="button" onClick={calculate} disabled={busy || legs.length < 2}>Calculate parlay</Button>
          </div>
          {error ? <Notice tone="error">{error}</Notice> : null}
        </div>
      </Panel>

      <Panel aria-labelledby="result-heading">
        <PanelHeader id="result-heading" title="Result" />
        <div className="space-y-4 p-4 sm:p-5" aria-live="polite">
          {!result ? (
            <p className="py-6 text-center text-sm text-muted">The combined price and payout appear here.</p>
          ) : (
            <>
              <dl className="grid grid-cols-2 gap-4">
                <Stat label="Combined odds" value={result.combined_price ? <Price price={result.combined_price} /> : result.combined_decimal.toFixed(2)} hint={`${result.active_legs} legs`} />
                <Stat label="Payout" value={result.payout === null || result.payout === undefined ? "n/a" : formatMoney(result.payout)} hint={result.profit === null || result.profit === undefined ? undefined : `${formatMoney(result.profit)} profit on ${formatMoney(result.stake ?? 0)}`} />
                <Stat label="Break-even" value={result.combined_price ? formatPercent(result.combined_price.implied_probability, 2) : "n/a"} hint="How often it must win" />
                <Stat label="Combined probability" value={result.combined_probability === null || result.combined_probability === undefined ? "Not shown" : formatPercent(result.combined_probability, 2)} />
              </dl>
              {result.correlation_warnings.length ? (
                <Notice tone="warn" title="These legs are correlated">
                  <ul className="list-disc space-y-1 pl-4">
                    {result.correlation_warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </Notice>
              ) : null}
              <Notice>{result.probability_note}</Notice>
              <details className="rounded-cell border border-line">
                <summary className="min-h-11 cursor-pointer px-3 py-2.5 text-sm font-medium">Show the working</summary>
                <ol className="num list-decimal space-y-1 border-t border-line px-3 py-3 pl-8 text-sm text-muted">
                  {result.steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
              </details>
            </>
          )}
        </div>
      </Panel>
    </div>
  );
}
