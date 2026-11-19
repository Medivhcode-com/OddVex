import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { createAlert, describeError } from '@/api/client';
import type { AlertCreate, EventSummary, OddsComparison, Team } from '@/api/types';
import { Choice, Field } from '@/components/form';
import { quickBetOptions, type QuickBetOption } from '@/components/quick-bet';
import { Button, Notice } from '@/components/states';
import { Txt } from '@/components/text';
import { useSession } from '@/providers/session';
import { DRAFT_KEPT, useDraft, useDraftKept } from '@/session/drafts';
import { space } from '@/theme';
import { cleanOdds, formatAmerican } from '@/utils/format';

type AlertChoice = 'price' | 'line' | 'start' | 'final';

const MARKET_NAMES = { moneyline: 'moneyline', spread: 'spread', total: 'total' } as const;
const MINUTES = [
  { value: '15', label: '15 minutes' },
  { value: '30', label: '30 minutes' },
  { value: '60', label: '1 hour' },
  { value: '120', label: '2 hours' },
] as const;

/** Minutes before the start for the "every game for this team" alert. */
export const TEAM_ALERT_MINUTES = 60;

export const ALERTS_IN_APP_NOTE =
  'Alerts show up under Notifications in this app. There is no push yet, so they are checked when you open the app.';

/**
 * A starting value for the price field: ten points above the current best on the American scale, which has
 * no values between −100 and +100 (−105 goes to +105, not −95). A convenience for the form, typed over freely.
 */
export function suggestedThreshold(american: number): string {
  const current = Math.round(american);
  const next = current + 10;
  const stepped = next > -100 && next < 100 ? next + 200 : next;
  return stepped > 0 ? `+${stepped}` : `${stepped}`;
}

/**
 * Checks a typed American price without converting it: a whole number of +100 or more, or −100 or less.
 * A number with no sign is taken as plus. Returns the text to send, or the message to show.
 */
export function readThreshold(raw: string): { value: string } | { error: string } {
  const text = cleanOdds(raw);
  if (text === '') return { error: 'Enter the price to reach in American odds, such as +150 or -105.' };
  if (!/^[+-]?\d+$/.test(text)) return { error: 'Use American odds: a plus or minus sign and a whole number, such as +150 or -105.' };
  if (Math.abs(Number(text)) < 100) return { error: 'American odds are +100 or higher, or -100 or lower.' };
  return { value: text.startsWith('+') || text.startsWith('-') ? text : `+${text}` };
}

/** A typed line move in points: a number greater than zero. */
export function readMove(raw: string): { value: number } | { error: string } {
  const text = raw.trim().replace(',', '.');
  const value = Number(text);
  if (text === '' || !Number.isFinite(value) || value <= 0) return { error: 'Enter a move greater than zero, in points, such as 1 or 1.5.' };
  return { value };
}

/**
 * "Set an alert" on a game: a price reaching a threshold, a line move, a time before the start, or the final
 * score. The price and line alerts use the market chosen in the market switcher. Nothing is computed here:
 * the form sends what was picked and typed, and the API decides when the alert fires. The choices and the
 * typed price and move are drafts: they come back if the session ends before the alert is saved, and not
 * once it has been.
 */
export function AlertForm({ event, odds }: { event: EventSummary; odds: OddsComparison }) {
  const router = useRouter();
  const session = useSession();
  const upcoming = event.status === 'upcoming';
  const kinds: { value: AlertChoice; label: string }[] = [
    { value: 'price', label: 'Price reaches' },
    { value: 'line', label: 'Line moves' },
    ...(upcoming ? [{ value: 'start' as const, label: 'Before the game starts' }] : []),
    { value: 'final', label: 'When the game ends' },
  ];
  const options = quickBetOptions(odds);
  const market = odds.market;
  const hasLine = market === 'spread' || market === 'total';

  const draft = `alert:${event.id}`;
  const [kind, setKind] = useDraft<AlertChoice>(`${draft}:kind`, 'price');
  const [picked, setPicked] = useDraft<string>(`${draft}:side`, '');
  // What was typed as the price, remembered only for the side and market it was typed for.
  const [typed, setTyped] = useDraft<{ key: string; text: string } | null>(`${draft}:price`, null);
  const [move, setMove] = useDraft(`${draft}:move`, '1');
  const [minutes, setMinutes] = useDraft<string>(`${draft}:minutes`, '30');
  const [keptNotice, dismissKeptNotice, draftSaved] = useDraftKept(draft);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  const option: QuickBetOption | undefined = options.find((item) => item.outcomeKey === picked) ?? options[0];
  const thresholdKey = `${market}:${option?.outcomeKey ?? ''}`;
  const threshold = typed?.key === thresholdKey ? typed.text : option ? suggestedThreshold(option.american) : '';
  const sideOptions = options.map((item): { value: string; label: string } => ({
    value: item.outcomeKey,
    label: `${item.label}, best now ${formatAmerican(item.american)} at ${item.sportsbook}`,
  }));

  function reset() {
    dismissKeptNotice();
    setFieldError(null);
    setError(null);
    setSaved(false);
  }

  function build(): AlertCreate | { fieldError: string } | { error: string } {
    if (kind === 'final') return { kind: 'game_final', event_id: event.id };
    if (kind === 'start') return { kind: 'game_start', event_id: event.id, minutes_before: Number(minutes) };
    if (!option) return { error: 'Pick a side.' };
    if (kind === 'line') {
      if (market === 'moneyline') return { error: 'Choose Spread or Total in the market switcher first.' };
      const points = readMove(move);
      if ('error' in points) return { fieldError: points.error };
      return { kind: 'line_move', event_id: event.id, market, outcome_key: option.outcomeKey, min_move: points.value };
    }
    const price = readThreshold(threshold);
    if ('error' in price) return { fieldError: price.error };
    return {
      kind: 'price_at_least',
      event_id: event.id,
      market,
      outcome_key: option.outcomeKey,
      // Spread and total alerts are tied to the line shown; a moneyline alert must not send one.
      ...(hasLine && option.line !== null ? { line: option.line } : null),
      threshold: price.value,
      odds_format: 'american',
    };
  }

  async function save(rule: AlertCreate, fromFields: boolean) {
    setBusy(true);
    try {
      await createAlert(rule);
      // The form keeps what was saved on screen: it is no longer unsaved input. The team buttons send none of
      // the fields, so a price or a move typed and not saved stays a draft after one of them is pressed.
      if (fromFields) draftSaved();
      setSaved(true);
      session.changed('alerts');
    } catch (caught) {
      // The API's own sentence (for example why a game or a line cannot take an alert), shown as sent.
      setError(describeError(caught, 'The alert was not saved. Try again.'));
    } finally {
      setBusy(false);
    }
  }

  function submit() {
    reset();
    const rule = build();
    if ('fieldError' in rule) return setFieldError(rule.fieldError);
    if ('error' in rule) return setError(rule.error);
    void save(rule, true);
  }

  function saveForTeam(team: Team) {
    reset();
    void save({ kind: 'game_start', team_id: team.id, minutes_before: TEAM_ALERT_MINUTES }, false);
  }

  const noPrices = (
    <Txt variant="secondary" tone="muted">
      No sportsbook has an open price on this market right now, so there is nothing to set this alert on. Try another market.
    </Txt>
  );

  return (
    <View style={styles.form}>
      {keptNotice ? <Notice tone="neutral" text={DRAFT_KEPT} /> : null}
      <Choice
        label="Alert me when"
        options={kinds}
        value={kind}
        onChange={(value) => {
          reset();
          setKind(value);
        }}
      />

      {kind === 'price' ? (
        options.length === 0 ? (
          noPrices
        ) : (
          <>
            <Choice label={`Side, on the ${MARKET_NAMES[market]} market`} options={sideOptions} value={option?.outcomeKey ?? ''} onChange={setPicked} />
            <Field
              label="Price to reach (American odds)"
              hint="The alert fires when the best price is at or above this. Filled in a little above the current best."
              mono
              placeholder="+150"
              keyboardType="numbers-and-punctuation"
              value={threshold}
              onChangeText={(text) => setTyped({ key: thresholdKey, text })}
              error={fieldError}
            />
          </>
        )
      ) : null}

      {kind === 'line' ? (
        !hasLine ? (
          <Txt variant="secondary" tone="muted">
            Line alerts follow the spread or the total. Choose Spread or Total in the market switcher above.
          </Txt>
        ) : options.length === 0 ? (
          noPrices
        ) : (
          <>
            <Choice label={`Side, on the ${MARKET_NAMES[market]} market`} options={sideOptions} value={option?.outcomeKey ?? ''} onChange={setPicked} />
            <Field
              label="Move, in points"
              hint="The alert fires when the consensus line is this far from where it is now, in either direction."
              mono
              placeholder="1"
              keyboardType="decimal-pad"
              value={move}
              onChangeText={setMove}
              error={fieldError}
            />
          </>
        )
      ) : null}

      {kind === 'start' ? <Choice label="How long before the start" options={MINUTES} value={minutes} onChange={setMinutes} /> : null}

      {kind === 'final' ? (
        <Txt variant="secondary" tone="muted">
          You get the final score once this game is over.
        </Txt>
      ) : null}

      {error ? <Notice tone="error" text={error} /> : null}
      {saved ? <Notice tone="accent" text="Alert saved." /> : null}
      <View style={styles.actions}>
        <Button label={busy ? 'Saving alert' : 'Save alert'} onPress={submit} disabled={busy} />
        {saved ? (
          <Button
            label="See your alerts"
            variant="secondary"
            onPress={() => router.push({ pathname: '/notifications', params: { tab: 'alerts' } })}
          />
        ) : null}
      </View>

      <View style={styles.teams}>
        <Txt variant="secondary" weight="medium">
          Every game for a team
        </Txt>
        <Txt variant="caption" tone="muted">
          {TEAM_ALERT_MINUTES} minutes before each game. It stays on until you pause or delete it.
        </Txt>
        <View style={styles.actions}>
          {[event.away_team, event.home_team].map((team) => (
            <Button
              key={team.id}
              label={`Alert me before ${team.name}'s games`}
              variant="secondary"
              compact
              disabled={busy}
              onPress={() => saveForTeam(team)}
            />
          ))}
        </View>
      </View>

      <Txt variant="caption" tone="muted">
        {ALERTS_IN_APP_NOTE}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  form: { gap: space[3] },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[3] },
  teams: { gap: space[2] },
});
