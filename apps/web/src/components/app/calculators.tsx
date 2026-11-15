"use client";

import { useState, type ReactNode } from "react";
import { Button, Field, Notice, Panel, PanelHeader, SelectField, Stat } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";
import { formatAmerican, formatMoney, formatPercent } from "@/lib/format";
import type { PriceT } from "@/lib/types";

type Format = "american" | "decimal" | "fractional";
const clean = (raw: string) => raw.trim().replace(/[−–]/g, "-");
const signedPct = (fraction: number) => `${fraction > 0 ? "+" : fraction < 0 ? "−" : ""}${Math.abs(fraction * 100).toFixed(2)}%`;

function useCalc<T>(path: string) {
  const [result, setResult] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function run(body: unknown) {
    setBusy(true);
    setError(null);
    try {
      setResult(await clientApi<T>(path, { body }));
    } catch (caught) {
      setResult(null);
      setError(caught instanceof ClientApiError ? caught.message : "The calculation failed. Check the values and try again.");
    } finally {
      setBusy(false);
    }
  }
  return { result, error, busy, run };
}

function FormatSelect({ id, value, onChange }: { id: string; value: Format; onChange: (f: Format) => void }) {
  return (
    <SelectField id={id} label="Odds format" value={value} onChange={(e) => onChange(e.target.value as Format)}>
      <option value="american">American</option>
      <option value="decimal">Decimal</option>
      <option value="fractional">Fractional</option>
    </SelectField>
  );
}

function Working({ steps }: { steps: string[] }) {
  if (!steps.length) return null;
  return (
    <details className="rounded-cell border border-line">
      <summary className="min-h-11 cursor-pointer px-3 py-2.5 text-sm font-medium">Show the working</summary>
      <ol className="num list-decimal space-y-1 border-t border-line px-3 py-3 pl-8 text-sm text-muted">
        {steps.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>
    </details>
  );
}

function Calc({ id, title, description, form, error, children }: { id: string; title: string; description: string; form: ReactNode; error: string | null; children: ReactNode }) {
  return (
    <Panel aria-labelledby={`${id}-heading`} id={id}>
      <PanelHeader id={`${id}-heading`} title={title} description={description} />
      <div className="space-y-4 p-4 sm:p-5">
        {form}
        <div aria-live="polite" className="space-y-4">
          {error ? <Notice tone="error">{error}</Notice> : null}
          {children}
        </div>
      </div>
    </Panel>
  );
}

function PriceStats({ price }: { price: PriceT }) {
  return (
    <>
      <Stat label="American" value={formatAmerican(price.american)} />
      <Stat label="Decimal" value={price.decimal.toFixed(3)} />
      <Stat label="Fractional" value={price.fractional} />
      <Stat label="Implied probability" value={formatPercent(price.implied_probability, 2)} />
    </>
  );
}

export function ConvertCalculator() {
  const [odds, setOdds] = useState("-110");
  const [format, setFormat] = useState<Format>("american");
  const calc = useCalc<{ price: PriceT; steps: string[] }>("/v1/quant/convert");
  return (
    <Calc
      id="convert"
      title="Odds converter"
      description="Turn a price into every format and the probability it implies."
      error={calc.error}
      form={
        <form onSubmit={(e) => { e.preventDefault(); calc.run({ odds: clean(odds), odds_format: format }); }} className="flex flex-wrap items-end gap-3">
          <Field id="convert-odds" label="Odds" className="w-32 [&_input]:font-mono" value={odds} onChange={(e) => setOdds(e.target.value)} />
          <FormatSelect id="convert-format" value={format} onChange={setFormat} />
          <Button type="submit" disabled={calc.busy}>Convert</Button>
        </form>
      }
    >
      {calc.result ? (
        <>
          <dl className="grid grid-cols-2 gap-4 md:grid-cols-4"><PriceStats price={calc.result.price} /></dl>
          <Working steps={calc.result.steps} />
        </>
      ) : null}
    </Calc>
  );
}

type NoVig = { outcomes: { label: string; price: PriceT; implied_probability: number; no_vig_probability: number; fair_price: PriceT }[]; overround: number; hold: number; steps: string[] };

export function NoVigCalculator() {
  const [sides, setSides] = useState(["-110", "-110"]);
  const [format, setFormat] = useState<Format>("american");
  const calc = useCalc<NoVig>("/v1/quant/no-vig");
  return (
    <Calc
      id="no-vig"
      title="No-vig calculator"
      description="Enter every side of one market to remove the sportsbook's margin."
      error={calc.error}
      form={
        <form onSubmit={(e) => { e.preventDefault(); calc.run({ odds: sides.map(clean), odds_format: format }); }} className="flex flex-wrap items-end gap-3">
          {sides.map((side, i) => (
            <Field key={i} id={`novig-${i}`} label={`Side ${i + 1}`} className="w-28 [&_input]:font-mono" value={side} onChange={(e) => setSides((s) => s.map((v, j) => (j === i ? e.target.value : v)))} />
          ))}
          <FormatSelect id="novig-format" value={format} onChange={setFormat} />
          <Button type="button" variant="secondary" onClick={() => setSides((s) => (s.length === 2 ? [...s, ""] : s.slice(0, 2)))}>
            {sides.length === 2 ? "Add a third side" : "Use two sides"}
          </Button>
          <Button type="submit" disabled={calc.busy}>Remove the vig</Button>
        </form>
      }
    >
      {calc.result ? (
        <>
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Table, scrolls sideways">
            <table className="w-full min-w-[26rem] border-collapse text-sm">
              <caption className="sr-only">No-vig result</caption>
              <thead>
                <tr className="text-xs text-muted">
                  <th scope="col" className="py-2 text-left font-medium">Side</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Price</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Implied</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">No-vig</th>
                  <th scope="col" className="py-2 text-right font-medium">Fair price</th>
                </tr>
              </thead>
              <tbody>
                {calc.result.outcomes.map((outcome, i) => (
                  <tr key={i} className="border-t border-line">
                    <th scope="row" className="py-2.5 text-left font-medium">{outcome.label}</th>
                    <td className="num px-2 py-2.5 text-right">{formatAmerican(outcome.price.american)}</td>
                    <td className="num px-2 py-2.5 text-right text-muted">{formatPercent(outcome.implied_probability, 2)}</td>
                    <td className="num px-2 py-2.5 text-right font-medium">{formatPercent(outcome.no_vig_probability, 2)}</td>
                    <td className="num py-2.5 text-right">{formatAmerican(outcome.fair_price.american)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <dl className="grid grid-cols-2 gap-4">
            <Stat label="Overround" value={formatPercent(calc.result.overround, 2)} hint="Implied probabilities minus 100%" />
            <Stat label="Hold" value={formatPercent(calc.result.hold, 2)} hint="The book's theoretical margin" />
          </dl>
          <Working steps={calc.result.steps} />
        </>
      ) : null}
    </Calc>
  );
}

type EV = { price: PriceT; ev_percent: number; ev_per_unit: number; expected_profit: number; breakeven_probability: number; edge: number; stake: number; steps: string[]; caveat: string };

export function EvCalculator() {
  const [odds, setOdds] = useState("+150");
  const [format, setFormat] = useState<Format>("american");
  const [probability, setProbability] = useState("45");
  const [stake, setStake] = useState("100");
  const calc = useCalc<EV>("/v1/quant/ev");
  const [localError, setLocalError] = useState<string | null>(null);
  return (
    <Calc
      id="ev"
      title="Expected value"
      description="What a bet is worth on average, if your win probability is right."
      error={localError ?? calc.error}
      form={
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const p = Number(probability);
            if (!(p > 0 && p < 100)) return setLocalError("Enter a win probability between 0 and 100.");
            setLocalError(null);
            calc.run({ odds: clean(odds), odds_format: format, win_probability: p / 100, stake: Number(stake) || 1 });
          }}
          className="flex flex-wrap items-end gap-3"
        >
          <Field id="ev-odds" label="Odds" className="w-28 [&_input]:font-mono" value={odds} onChange={(e) => setOdds(e.target.value)} />
          <FormatSelect id="ev-format" value={format} onChange={setFormat} />
          <Field id="ev-prob" label="Your win probability (%)" inputMode="decimal" className="w-44" value={probability} onChange={(e) => setProbability(e.target.value)} />
          <Field id="ev-stake" label="Stake ($)" inputMode="decimal" className="w-28" value={stake} onChange={(e) => setStake(e.target.value)} />
          <Button type="submit" disabled={calc.busy}>Calculate</Button>
        </form>
      }
    >
      {calc.result && !localError ? (
        <>
          <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label="Expected value" value={signedPct(calc.result.ev_per_unit)} tone={calc.result.ev_per_unit > 0 ? "accent" : calc.result.ev_per_unit < 0 ? "error" : undefined} hint="Per dollar staked" />
            <Stat label="Expected profit" value={formatMoney(calc.result.expected_profit, { signed: true })} hint={`On a ${formatMoney(calc.result.stake)} stake`} />
            <Stat label="Break-even" value={formatPercent(calc.result.breakeven_probability, 2)} hint="Win rate needed at this price" />
            <Stat label="Edge" value={signedPct(calc.result.edge)} hint="Your probability minus break-even" />
          </dl>
          <Notice tone="warn" title="Only as good as the probability you entered">{calc.result.caveat}</Notice>
          <Working steps={calc.result.steps} />
        </>
      ) : null}
    </Calc>
  );
}

type CLV = { price: PriceT; closing_price: PriceT; clv: number; beat_close: boolean; closing_no_vig_probability?: number | null; no_vig_probability_delta?: number | null; steps: string[] };

export function ClvCalculator() {
  const [odds, setOdds] = useState("+150");
  const [closing, setClosing] = useState("+135");
  const [opposite, setOpposite] = useState("");
  const [format, setFormat] = useState<Format>("american");
  const calc = useCalc<CLV>("/v1/quant/clv");
  return (
    <Calc
      id="clv"
      title="Closing line value"
      description="Compare the price you took with where the market closed."
      error={calc.error}
      form={
        <form
          onSubmit={(e) => {
            e.preventDefault();
            calc.run({ odds: clean(odds), closing_odds: clean(closing), closing_opposite_odds: opposite.trim() ? clean(opposite) : null, odds_format: format });
          }}
          className="flex flex-wrap items-end gap-3"
        >
          <Field id="clv-odds" label="Price you took" className="w-32 [&_input]:font-mono" value={odds} onChange={(e) => setOdds(e.target.value)} />
          <Field id="clv-close" label="Closing price" className="w-32 [&_input]:font-mono" value={closing} onChange={(e) => setClosing(e.target.value)} />
          <Field id="clv-opp" label="Closing price, other side" className="w-48 [&_input]:font-mono" placeholder="Optional" value={opposite} onChange={(e) => setOpposite(e.target.value)} />
          <FormatSelect id="clv-format" value={format} onChange={setFormat} />
          <Button type="submit" disabled={calc.busy}>Calculate</Button>
        </form>
      }
    >
      {calc.result ? (
        <>
          <dl className="grid grid-cols-2 gap-4 md:grid-cols-3">
            <Stat label="Closing line value" value={signedPct(calc.result.clv)} tone={calc.result.clv > 0 ? "accent" : calc.result.clv < 0 ? "error" : undefined} hint={calc.result.beat_close ? "You beat the close" : "The close was as good or better"} />
            <Stat label="Closing no-vig probability" value={formatPercent(calc.result.closing_no_vig_probability, 2)} hint="Needs the other side's closing price" />
            <Stat label="Probability gained" value={calc.result.no_vig_probability_delta === null || calc.result.no_vig_probability_delta === undefined ? "n/a" : signedPct(calc.result.no_vig_probability_delta)} hint="Closing no-vig minus your break-even" />
          </dl>
          <Working steps={calc.result.steps} />
        </>
      ) : null}
    </Calc>
  );
}
