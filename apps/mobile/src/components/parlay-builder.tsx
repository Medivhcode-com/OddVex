import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { describeError, quantParlay } from '@/api/client';
import type { EventSummary, ParlayRequest, ParlayResult, PriceT } from '@/api/types';
import { Field } from '@/components/form';
import { Price } from '@/components/price';
import { Button, Notice, Panel, PanelHeading, Stat, StatGrid, Working } from '@/components/states';
import { Num, Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { useOddsFormat } from '@/providers/odds-format';
import { radius, space } from '@/theme';
import { cleanOdds, formatAmerican, formatMoney, formatPercent, formatPrice, showTypedAmerican } from '@/utils/format';

export type LegOption = { id: string; eventId: string; eventLabel: string; label: string; price: PriceT; book: string };
type Leg = { key: string; label: string; odds: string; eventId: string | null; detail: string };

const BOARD_EVENTS = 20;

/** Best moneyline on each side of every game that has not finished, as legs to pick from. */
export function legOptions(events: readonly EventSummary[]): LegOption[] {
  return events
    .filter((event) => event.status !== 'final')
    .slice(0, BOARD_EVENTS)
    .flatMap((event) => {
      const eventLabel = `${event.away_team.abbreviation} at ${event.home_team.abbreviation}`;
      return (['away', 'home'] as const).flatMap((side) => {
        const best = event.best_moneyline?.[side];
        const team = side === 'away' ? event.away_team : event.home_team;
        return best
          ? [{ id: `${event.id}:${side}`, eventId: event.id, eventLabel, label: `${team.name} ML`, price: best.price, book: best.sportsbook.name }]
          : [];
      });
    });
}

export function parlayPayload(legs: readonly Leg[], stake: string): ParlayRequest {
  return {
    stake: Number(stake) > 0 ? Number(stake) : null,
    legs: legs.map((leg) => ({ odds: leg.odds, odds_format: 'american', label: leg.label, event_id: leg.eventId })),
  };
}

type ProbabilityStatus = ParlayResult['probability_status'];

/**
 * The sentence shown for each reason the API gives (`probability_status`) for sending no combined probability.
 * `needs_leg_probabilities` has none: this builder never sends a leg probability, so that is the normal answer
 * for legs from different games, and there is nothing for the person to do about it. The API's
 * `probability_note` is never shown: it is written for developers and can read as a request for input this
 * form does not take. Each sentence is the web's sentence for the same status, word for word
 * (`PROBABILITY_NOTICE` in `apps/web/src/components/app/parlay-builder.tsx`).
 */
export const PARLAY_PROBABILITY_SENTENCES: Record<Exclude<ProbabilityStatus, 'computed' | 'needs_leg_probabilities'>, string> = {
  same_event_legs: 'Two or more legs are from the same game, so their results are linked. OddVex gives no combined chance for these legs.',
  unverified_legs:
    "Custom legs can't be checked for independence, because OddVex does not know which game they are from. No combined chance is given.",
  no_active_legs: 'Every leg pushed or was voided, so no legs are left to combine.',
};

/**
 * What the API returned for the parlay: combined odds, payout and break-even. The combined probability is shown
 * only when the API computed one (`probability_status` is `computed`), marked as assuming the legs are
 * independent. Otherwise there is no probability stat, and the reason gets a plain sentence where it helps.
 */
export function ParlayResultView({ result }: { result: ParlayResult }) {
  const { format } = useOddsFormat();
  const combined = result.combined_price ? formatPrice(result.combined_price, format) : result.combined_decimal.toFixed(2);
  const hasPayout = result.payout !== null && result.payout !== undefined;
  const hasProfit = result.profit !== null && result.profit !== undefined;
  const status = result.probability_status;
  const probability = status === 'computed' && typeof result.combined_probability === 'number' ? result.combined_probability : null;
  return (
    <View accessibilityLiveRegion="polite" style={styles.block}>
      <StatGrid>
        <Stat label="Combined odds" value={combined} hint={`${result.active_legs} legs`} />
        <Stat
          label="Payout"
          value={hasPayout ? formatMoney(result.payout as number) : 'n/a'}
          hint={hasProfit ? `${formatMoney(result.profit as number)} profit on ${formatMoney(result.stake ?? 0)}` : undefined}
        />
        <Stat
          label="Break-even"
          value={result.combined_price ? formatPercent(result.combined_price.implied_probability, 2) : 'n/a'}
          hint="How often it must win"
        />
        {probability !== null ? (
          <Stat label="Combined probability" value={formatPercent(probability, 2)} hint="Assumes the legs are independent" />
        ) : null}
      </StatGrid>
      {status === 'same_event_legs' ? (
        <Notice title="These legs are correlated" text={PARLAY_PROBABILITY_SENTENCES.same_event_legs} />
      ) : status === 'unverified_legs' || status === 'no_active_legs' ? (
        <Notice tone="neutral" text={PARLAY_PROBABILITY_SENTENCES[status]} />
      ) : null}
      <Working steps={result.steps} />
    </View>
  );
}

export function ParlayBuilder({ options }: { options: readonly LegOption[] }) {
  const theme = useTheme();
  const [legs, setLegs] = useState<Leg[]>([]);
  const [showBoard, setShowBoard] = useState(false);
  const [manualLabel, setManualLabel] = useState('');
  const [manualOdds, setManualOdds] = useState('');
  const [stake, setStake] = useState('10');
  const [result, setResult] = useState<ParlayResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [serial, setSerial] = useState(0);

  const change = (next: Leg[]) => {
    setLegs(next);
    setResult(null);
    setSerial((value) => value + 1);
  };
  const addOption = (option: LegOption) => {
    setError(null);
    change([
      ...legs,
      {
        key: `${option.id}-${serial}`,
        label: option.label,
        odds: String(Math.round(option.price.american)),
        eventId: option.eventId,
        detail: `${option.eventLabel}, ${option.book}`,
      },
    ]);
  };
  const addManual = () => {
    if (!manualLabel.trim() || !manualOdds.trim()) return setError('A custom leg needs a name and American odds.');
    setError(null);
    change([...legs, { key: `manual-${serial}`, label: manualLabel.trim(), odds: cleanOdds(manualOdds), eventId: null, detail: 'Custom leg' }]);
    setManualLabel('');
    setManualOdds('');
  };

  async function calculate() {
    if (legs.length < 2) return setError('Add at least two legs.');
    setBusy(true);
    setError(null);
    try {
      setResult(await quantParlay(parlayPayload(legs, stake)));
    } catch (caught) {
      setResult(null);
      setError(describeError(caught, 'The parlay could not be calculated.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Panel>
        <View style={styles.block}>
          <PanelHeading title="Legs" description="Add moneylines from the board or type your own." />
          {legs.length === 0 ? (
            <Txt variant="secondary" tone="muted" style={[styles.none, { borderColor: theme.borderStrong }]}>
              No legs yet. Add two or more to see the combined price.
            </Txt>
          ) : (
            <View>
              {legs.map((leg, index) => (
                <View key={leg.key} style={[styles.leg, { borderTopColor: theme.border }]}>
                  <Num tone="muted">{index + 1}</Num>
                  <View style={styles.grow}>
                    <Txt weight="medium">{leg.label}</Txt>
                    <Txt variant="caption" tone="muted">
                      {leg.detail}
                    </Txt>
                  </View>
                  <Num>{showTypedAmerican(leg.odds)}</Num>
                  <Button
                    label="Remove"
                    variant="ghost"
                    compact
                    accessibilityLabel={`Remove ${leg.label}`}
                    onPress={() => change(legs.filter((item) => item.key !== leg.key))}
                  />
                </View>
              ))}
            </View>
          )}

          {options.length ? (
            <>
              <Button
                label={showBoard ? 'Hide the board' : 'Add a moneyline from the board'}
                variant="secondary"
                onPress={() => setShowBoard((value) => !value)}
              />
              {showBoard
                ? options.map((option) => (
                    <View key={option.id} style={[styles.leg, { borderTopColor: theme.border }]}>
                      <View style={styles.grow}>
                        <Txt weight="medium">{option.label}</Txt>
                        <Txt variant="caption" tone="muted">
                          {option.eventLabel}, {option.book}
                        </Txt>
                      </View>
                      <Price price={option.price} />
                      <Button
                        label="Add"
                        variant="ghost"
                        compact
                        accessibilityLabel={`Add ${option.label} ${formatAmerican(option.price.american)}, ${option.eventLabel}`}
                        onPress={() => addOption(option)}
                      />
                    </View>
                  ))
                : null}
            </>
          ) : null}

          <Field label="Custom leg" placeholder="Player over 22.5 points" autoCapitalize="sentences" value={manualLabel} onChangeText={setManualLabel} />
          <Field label="American odds" mono placeholder="-115" keyboardType="numbers-and-punctuation" value={manualOdds} onChangeText={setManualOdds} />
          <Button label="Add custom leg" variant="secondary" onPress={addManual} />

          <Field label="Stake ($)" mono keyboardType="decimal-pad" value={stake} onChangeText={setStake} />
          {error ? <Notice tone="error" text={error} /> : null}
          <Button label="Calculate parlay" disabled={busy || legs.length < 2} onPress={calculate} />
        </View>
      </Panel>

      <Panel>
        <View style={styles.block}>
          <PanelHeading title="Result" />
          {result ? (
            <ParlayResultView result={result} />
          ) : (
            <Txt variant="secondary" tone="muted" style={styles.center}>
              The combined price and payout appear here.
            </Txt>
          )}
        </View>
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  block: { gap: space[3] },
  grow: { flex: 1, gap: 2 },
  center: { textAlign: 'center', paddingVertical: space[4] },
  none: { textAlign: 'center', padding: space[4], borderWidth: 1, borderStyle: 'dashed', borderRadius: radius.cell },
  leg: { flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: space[2], borderTopWidth: StyleSheet.hairlineWidth },
});
