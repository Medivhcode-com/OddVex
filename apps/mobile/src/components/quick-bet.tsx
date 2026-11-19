import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { createBet, describeError } from '@/api/client';
import type { BetCreate, EventSummary, OddsComparison } from '@/api/types';
import { Choice, Field } from '@/components/form';
import { Button, Notice } from '@/components/states';
import { DRAFT_KEPT, useDraft, useDraftKept } from '@/session/drafts';
import { space } from '@/theme';
import { formatAmerican, formatLine } from '@/utils/format';

type OutcomeKey = 'home' | 'away' | 'draw' | 'over' | 'under';
const GRADEABLE: readonly string[] = ['home', 'away', 'draw', 'over', 'under'];

export type QuickBetOption = { outcomeKey: OutcomeKey; label: string; line: number | null; american: number; sportsbook: string };

/** One option per outcome the API marks a best price for: the side, its line, that price and the book offering it. */
export function quickBetOptions(odds: OddsComparison): QuickBetOption[] {
  return odds.best.flatMap((best) => {
    if (!GRADEABLE.includes(best.outcome_key)) return [];
    const name = odds.consensus.outcomes.find((outcome) => outcome.key === best.outcome_key)?.name ?? best.outcome_key;
    const book = odds.books.find((row) => row.sportsbook.key === best.sportsbook_key)?.sportsbook.name ?? best.sportsbook_key;
    const line = best.line ?? null;
    const lineText = line === null ? '' : ` ${formatLine(line, { signed: odds.market === 'spread' })}`;
    return [
      {
        outcomeKey: best.outcome_key as OutcomeKey,
        label: `${name}${lineText}${odds.market === 'moneyline' ? ' ML' : ''}`,
        line,
        american: best.price.american,
        sportsbook: book,
      },
    ];
  });
}

/** A straight bet with a structured leg, so the tracker can grade it from the final score. */
export function quickBetPayload(event: EventSummary, market: string, option: QuickBetOption, stake: number): BetCreate {
  return {
    bet_type: 'straight',
    stake,
    sportsbook: option.sportsbook,
    legs: [
      {
        selection: option.label,
        market,
        league: event.league,
        event_id: event.id,
        event_label: `${event.away_team.name} at ${event.home_team.name}`,
        outcome_key: option.outcomeKey,
        line: option.line,
        odds: String(Math.round(option.american)),
        odds_format: 'american',
      },
    ],
  };
}

/**
 * Logs a bet on this game at the best current price. OddVex records the bet. It does not place it.
 * The side and the stake are drafts: they come back if the session ends before the bet is saved.
 */
export function QuickBet({
  event,
  market,
  options,
  onSaved,
}: {
  event: EventSummary;
  market: string;
  options: readonly QuickBetOption[];
  onSaved: () => void;
}) {
  const router = useRouter();
  const draft = `quick-bet:${event.id}:${market}`;
  const [choice, setChoice] = useDraft<string>(`${draft}:side`, options[0]?.outcomeKey ?? '');
  const [stake, setStake] = useDraft(`${draft}:stake`, '');
  const [keptNotice, dismissKeptNotice, draftSaved] = useDraftKept(draft);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const option = options.find((item) => item.outcomeKey === choice);

  async function submit() {
    setSaved(false);
    dismissKeptNotice();
    const amount = Number(stake);
    if (!option) return setError('Pick a side.');
    if (stake.trim() === '' || !Number.isFinite(amount) || amount <= 0) return setError('Enter a stake greater than zero.');
    setBusy(true);
    setError(null);
    try {
      await createBet(quickBetPayload(event, market, option, amount));
      setStake('');
      draftSaved();
      setSaved(true);
      onSaved();
    } catch (caught) {
      setError(describeError(caught, 'The bet was not saved. Try again.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.form}>
      {keptNotice ? <Notice tone="neutral" text={DRAFT_KEPT} /> : null}
      <Choice
        label="Side, at the best current price"
        options={options.map((item): { value: string; label: string } => ({
          value: item.outcomeKey,
          label: `${item.label} ${formatAmerican(item.american)} at ${item.sportsbook}`,
        }))}
        value={choice}
        onChange={setChoice}
      />
      <Field label="Stake ($)" mono placeholder="25.00" keyboardType="decimal-pad" value={stake} onChangeText={setStake} />
      {error ? <Notice tone="error" text={error} /> : null}
      {saved ? (
        <Notice tone="accent" text="Bet saved. Because it is tied to this game, the tracker can settle it from the final score." />
      ) : null}
      <View style={styles.actions}>
        <Button label={busy ? 'Saving bet' : 'Add to tracker'} onPress={submit} disabled={busy} />
        {saved ? <Button label="Open the tracker" variant="secondary" onPress={() => router.navigate('/tracker')} /> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  form: { gap: space[3] },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[3] },
});
