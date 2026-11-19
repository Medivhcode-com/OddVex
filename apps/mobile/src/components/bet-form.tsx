import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { createBet, describeError } from '@/api/client';
import type { BetCreate, BetType, EntryOddsFormat } from '@/api/types';
import { Choice, Field } from '@/components/form';
import { Button, Notice } from '@/components/states';
import { Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { DRAFT_KEPT, useDraft, useDraftKept } from '@/session/drafts';
import { radius, space } from '@/theme';
import { cleanOdds } from '@/utils/format';

export type LegDraft = { selection: string; market: string; odds: string; closing_odds: string; event_label: string };
export const emptyLeg = (): LegDraft => ({ selection: '', market: 'moneyline', odds: '', closing_odds: '', event_label: '' });

const OTHER_LEAGUE = 'other';
const LEG_MARKETS: readonly { value: string; label: string }[] = [
  { value: 'moneyline', label: 'Moneyline' },
  { value: 'spread', label: 'Spread' },
  { value: 'total', label: 'Total' },
  { value: 'player_prop', label: 'Player prop' },
  { value: 'future', label: 'Future' },
  { value: 'other', label: 'Other' },
];
const TYPES: readonly { value: BetType; label: string }[] = [
  { value: 'straight', label: 'Straight' },
  { value: 'parlay', label: 'Parlay' },
  { value: 'sgp', label: 'Same-game parlay' },
  { value: 'future', label: 'Future' },
];
const FORMATS: readonly { value: EntryOddsFormat; label: string }[] = [
  { value: 'american', label: 'American' },
  { value: 'decimal', label: 'Decimal' },
  { value: 'fractional', label: 'Fractional' },
];
const ODDS_PLACEHOLDER: Record<EntryOddsFormat, string> = { american: '-110', decimal: '1.91', fractional: '10/11' };

export const isMulti = (betType: BetType) => betType === 'parlay' || betType === 'sgp';

export type BetDraft = {
  betType: BetType;
  format: EntryOddsFormat;
  league: string;
  sportsbook: string;
  stake: string;
  legs: LegDraft[];
};

/**
 * Checks the form the way the web tracker does and builds the request body. Odds are sent as typed (the API
 * parses and converts them); the only number made here is the stake.
 */
export function buildBetPayload(draft: BetDraft): { error: string } | { body: BetCreate } {
  const multi = isMulti(draft.betType);
  const stake = Number(draft.stake);
  const used = multi ? draft.legs : draft.legs.slice(0, 1);
  if (draft.stake.trim() === '' || !Number.isFinite(stake) || stake <= 0) return { error: 'Enter a stake greater than zero.' };
  if (!draft.sportsbook.trim()) return { error: 'Enter the sportsbook.' };
  if (multi && used.length < 2) return { error: 'A parlay needs at least two legs.' };
  if (used.some((leg) => !leg.selection.trim() || !leg.odds.trim())) return { error: 'Each leg needs a selection and odds.' };
  return {
    body: {
      bet_type: draft.betType,
      stake,
      sportsbook: draft.sportsbook.trim(),
      legs: used.map((leg) => ({
        selection: leg.selection.trim(),
        market: leg.market,
        league: draft.league && draft.league !== OTHER_LEAGUE ? draft.league : null,
        event_label: leg.event_label.trim() || null,
        odds: cleanOdds(leg.odds),
        odds_format: draft.format,
        closing_odds: leg.closing_odds.trim() ? cleanOdds(leg.closing_odds) : null,
      })),
    },
  };
}

/**
 * Log a bet by hand: straight, parlay, same-game parlay or future. OddVex records the bet. It does not place it.
 * The fields are drafts (`useDraft`): if the session ends before the bet is saved, they are back in the form
 * after the same person logs in again. A bet that was saved is not brought back. One of these forms is on
 * screen at a time.
 */
export function BetForm({
  leagues,
  sportsbooks,
  onSaved,
}: {
  leagues: readonly { key: string; name: string }[];
  sportsbooks: readonly string[];
  onSaved: () => void;
}) {
  const theme = useTheme();
  const [betType, setBetType] = useDraft<BetType>('log-bet:type', 'straight');
  const [format, setFormat] = useDraft<EntryOddsFormat>('log-bet:format', 'american');
  const [league, setLeague] = useDraft<string>('log-bet:league', leagues[0]?.key ?? OTHER_LEAGUE);
  const [sportsbook, setSportsbook] = useDraft('log-bet:sportsbook', sportsbooks[0] ?? '');
  const [stake, setStake] = useDraft('log-bet:stake', '');
  const [legs, setLegs] = useDraft<LegDraft[]>('log-bet:legs', () => [emptyLeg()]);
  // Said until the next Save: the fields came back after the session ended.
  const [keptNotice, dismissKeptNotice, draftSaved] = useDraftKept('log-bet');
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);
  const multi = isMulti(betType);
  const shown = multi ? legs : legs.slice(0, 1);

  const update = (index: number, patch: Partial<LegDraft>) =>
    setLegs((current) => current.map((leg, i) => (i === index ? { ...leg, ...patch } : leg)));

  const changeType = (next: BetType) => {
    setBetType(next);
    if (isMulti(next)) setLegs((current) => (current.length < 2 ? [...current, emptyLeg()] : current));
  };

  async function submit() {
    setSaved(false);
    dismissKeptNotice();
    const built = buildBetPayload({ betType, format, league, sportsbook, stake, legs });
    if ('error' in built) return setError(built.error);
    setError(null);
    setPending(true);
    try {
      await createBet(built.body);
      setLegs(isMulti(betType) ? [emptyLeg(), emptyLeg()] : [emptyLeg()]);
      setStake('');
      // What is in the form now is the saved state: a later sign-out has nothing of this bet to bring back.
      draftSaved();
      setSaved(true);
      onSaved();
    } catch (caught) {
      setError(describeError(caught, 'The bet was not saved. Try again.'));
    } finally {
      setPending(false);
    }
  }

  return (
    <View style={styles.form}>
      {keptNotice ? <Notice tone="neutral" text={DRAFT_KEPT} /> : null}
      <Choice label="Bet type" options={TYPES} value={betType} onChange={changeType} />
      <Choice
        label="League"
        options={[...leagues.map((item) => ({ value: item.key, label: item.name })), { value: OTHER_LEAGUE, label: 'Other' }]}
        value={league}
        onChange={setLeague}
      />
      <Field label="Sportsbook" value={sportsbook} onChangeText={setSportsbook} autoCapitalize="words" />
      {sportsbooks.length ? (
        <View style={styles.suggestions}>
          {sportsbooks.map((book) => (
            <Button
              key={book}
              label={book}
              variant={book === sportsbook ? 'secondary' : 'ghost'}
              compact
              selected={book === sportsbook}
              accessibilityLabel={`Use ${book} as the sportsbook`}
              onPress={() => setSportsbook(book)}
            />
          ))}
        </View>
      ) : null}
      <Choice label="Odds format" options={FORMATS} value={format} onChange={setFormat} />

      {shown.map((leg, index) => {
        const name = multi ? `Leg ${index + 1}` : 'Selection';
        return (
          <View key={index} style={[styles.leg, { borderColor: theme.border }]}>
            <Txt variant="heading" accessibilityRole="header">
              {name}
            </Txt>
            <Field
              label={multi ? `${name} pick` : 'Pick'}
              placeholder="Harbor City Tides ML"
              autoCapitalize="sentences"
              value={leg.selection}
              onChangeText={(selection) => update(index, { selection })}
            />
            <Field
              label={multi ? `${name} game (optional)` : 'Game (optional)'}
              placeholder="Tides at Rams"
              autoCapitalize="sentences"
              value={leg.event_label}
              onChangeText={(event_label) => update(index, { event_label })}
            />
            <Choice
              label={multi ? `${name} market` : 'Market'}
              options={LEG_MARKETS}
              value={leg.market}
              onChange={(market) => update(index, { market })}
            />
            <View style={styles.pair}>
              <View style={styles.half}>
                <Field
                  label={multi ? `${name} odds` : 'Odds'}
                  mono
                  placeholder={ODDS_PLACEHOLDER[format]}
                  keyboardType="numbers-and-punctuation"
                  value={leg.odds}
                  onChangeText={(odds) => update(index, { odds })}
                />
              </View>
              <View style={styles.half}>
                <Field
                  label={multi ? `${name} closing odds` : 'Closing odds'}
                  mono
                  placeholder="Optional"
                  keyboardType="numbers-and-punctuation"
                  value={leg.closing_odds}
                  onChangeText={(closing_odds) => update(index, { closing_odds })}
                />
              </View>
            </View>
            {multi && legs.length > 2 ? (
              <Button
                label={`Remove leg ${index + 1}`}
                variant="ghost"
                compact
                onPress={() => setLegs((current) => current.filter((_, i) => i !== index))}
              />
            ) : null}
          </View>
        );
      })}

      {multi ? <Button label="Add a leg" variant="secondary" onPress={() => setLegs((current) => [...current, emptyLeg()])} /> : null}
      <Field label="Stake ($)" mono placeholder="25.00" keyboardType="decimal-pad" value={stake} onChangeText={setStake} />
      {error ? <Notice tone="error" text={error} /> : null}
      {saved ? <Notice tone="accent" text="Bet saved. It is in your open bets." /> : null}
      <Button label={pending ? 'Saving bet' : 'Save bet'} onPress={submit} disabled={pending} />
    </View>
  );
}

const styles = StyleSheet.create({
  form: { gap: space[4] },
  suggestions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2], marginTop: -space[2] },
  leg: { gap: space[3], borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.cell, padding: space[3] },
  pair: { flexDirection: 'row', gap: space[3] },
  half: { flex: 1 },
});
