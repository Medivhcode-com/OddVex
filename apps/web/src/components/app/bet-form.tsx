"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Field, Notice, SelectField } from "@/components/ui/primitives";
import { clientApi, ClientApiError } from "@/lib/client-api";

type Leg = { selection: string; market: string; odds: string; closing_odds: string; event_label: string };
const emptyLeg = (): Leg => ({ selection: "", market: "moneyline", odds: "", closing_odds: "", event_label: "" });
const MARKETS = ["moneyline", "spread", "total", "player_prop", "future", "other"];
const TYPES = [
  { value: "straight", label: "Straight" },
  { value: "parlay", label: "Parlay" },
  { value: "sgp", label: "Same-game parlay" },
  { value: "future", label: "Future" },
];

/** Accepts "+150", "-110", "2.5", "5/2". Typographic minus signs are normalized. */
function cleanOdds(raw: string) {
  return raw.trim().replace(/[−–]/g, "-");
}

export function BetForm({ leagues, sportsbooks }: { leagues: { key: string; name: string }[]; sportsbooks: string[] }) {
  const router = useRouter();
  const [betType, setBetType] = useState("straight");
  const [format, setFormat] = useState("american");
  const [league, setLeague] = useState(leagues[0]?.key ?? "");
  const [sportsbook, setSportsbook] = useState(sportsbooks[0] ?? "");
  const [stake, setStake] = useState("");
  const [legs, setLegs] = useState<Leg[]>([emptyLeg()]);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);
  const multi = betType === "parlay" || betType === "sgp";

  const update = (index: number, patch: Partial<Leg>) => setLegs((current) => current.map((leg, i) => (i === index ? { ...leg, ...patch } : leg)));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSaved(false);
    const stakeValue = Number(stake);
    const used = multi ? legs : legs.slice(0, 1);
    if (!Number.isFinite(stakeValue) || stakeValue <= 0) return setError("Enter a stake greater than zero.");
    if (!sportsbook.trim()) return setError("Enter the sportsbook.");
    if (multi && used.length < 2) return setError("A parlay needs at least two legs.");
    if (used.some((leg) => !leg.selection.trim() || !leg.odds.trim())) return setError("Each leg needs a selection and odds.");
    setPending(true);
    try {
      await clientApi("/v1/bets", {
        body: {
          bet_type: betType,
          stake: stakeValue,
          sportsbook: sportsbook.trim(),
          legs: used.map((leg) => ({
            selection: leg.selection.trim(),
            market: leg.market,
            league: league || null,
            event_label: leg.event_label.trim() || null,
            odds: cleanOdds(leg.odds),
            odds_format: format,
            closing_odds: leg.closing_odds.trim() ? cleanOdds(leg.closing_odds) : null,
          })),
        },
      });
      setLegs([emptyLeg()]);
      setStake("");
      setSaved(true);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ClientApiError ? caught.message : "The bet was not saved. Try again.");
    } finally {
      setPending(false);
    }
  }

  const placeholder = format === "american" ? "-110" : format === "decimal" ? "1.91" : "10/11";

  return (
    <form onSubmit={submit} className="space-y-4 p-4 sm:p-5" noValidate>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SelectField id="bet-type" label="Bet type" value={betType} onChange={(e) => { setBetType(e.target.value); if (e.target.value === "parlay" || e.target.value === "sgp") setLegs((l) => (l.length < 2 ? [...l, emptyLeg()] : l)); }}>
          {TYPES.map((type) => (
            <option key={type.value} value={type.value}>{type.label}</option>
          ))}
        </SelectField>
        <SelectField id="bet-league" label="League" value={league} onChange={(e) => setLeague(e.target.value)}>
          {leagues.map((l) => (
            <option key={l.key} value={l.key}>{l.name}</option>
          ))}
          <option value="">Other</option>
        </SelectField>
        <Field id="bet-book" label="Sportsbook" value={sportsbook} onChange={(e) => setSportsbook(e.target.value)} list="bet-books" autoComplete="off" />
        <datalist id="bet-books">
          {sportsbooks.map((book) => (
            <option key={book} value={book} />
          ))}
        </datalist>
        <SelectField id="bet-format" label="Odds format" value={format} onChange={(e) => setFormat(e.target.value)}>
          <option value="american">American</option>
          <option value="decimal">Decimal</option>
          <option value="fractional">Fractional</option>
        </SelectField>
      </div>

      {(multi ? legs : legs.slice(0, 1)).map((leg, index) => (
        <fieldset key={index} className="rounded-cell border border-line p-3">
          <legend className="px-1 text-sm font-medium">{multi ? `Leg ${index + 1}` : "Selection"}</legend>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_1.4fr_1fr_1fr_1fr]">
            <Field id={`leg-${index}-selection`} label="Pick" placeholder="Harbor City Tides ML" value={leg.selection} onChange={(e) => update(index, { selection: e.target.value })} />
            <Field id={`leg-${index}-event`} label="Game (optional)" placeholder="Tides at Rams" value={leg.event_label} onChange={(e) => update(index, { event_label: e.target.value })} />
            <SelectField id={`leg-${index}-market`} label="Market" value={leg.market} onChange={(e) => update(index, { market: e.target.value })}>
              {MARKETS.map((m) => (
                <option key={m} value={m}>{m.replace("_", " ").replace(/^\w/, (c) => c.toUpperCase())}</option>
              ))}
            </SelectField>
            <Field id={`leg-${index}-odds`} label="Odds" inputMode="text" className="[&_input]:font-mono" placeholder={placeholder} value={leg.odds} onChange={(e) => update(index, { odds: e.target.value })} />
            <Field id={`leg-${index}-closing`} label="Closing odds" inputMode="text" className="[&_input]:font-mono" placeholder="Optional" value={leg.closing_odds} onChange={(e) => update(index, { closing_odds: e.target.value })} />
          </div>
          {multi && legs.length > 2 ? (
            <Button type="button" variant="ghost" size="sm" className="mt-2" onClick={() => setLegs((current) => current.filter((_, i) => i !== index))}>
              Remove leg {index + 1}
            </Button>
          ) : null}
        </fieldset>
      ))}

      <div className="flex flex-wrap items-end gap-3">
        <Field id="bet-stake" label="Stake ($)" inputMode="decimal" className="w-36" placeholder="25.00" value={stake} onChange={(e) => setStake(e.target.value)} />
        {multi ? (
          <Button type="button" variant="secondary" onClick={() => setLegs((current) => [...current, emptyLeg()])}>
            Add a leg
          </Button>
        ) : null}
        <Button type="submit" disabled={pending}>
          {pending ? "Saving bet" : "Save bet"}
        </Button>
      </div>
      <div aria-live="polite">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {saved ? <Notice tone="accent">Bet saved. It is in your open bets below.</Notice> : null}
      </div>
    </form>
  );
}
