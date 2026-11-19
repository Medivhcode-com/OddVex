import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { deleteBet, describeError, settleBet, updateBet } from '@/api/client';
import type { Bet, BetResult, BetSettle, BetUpdate, LegResult } from '@/api/types';
import { Badge } from '@/components/badge';
import { Choice, Field } from '@/components/form';
import { Price } from '@/components/price';
import { Button, Notice } from '@/components/states';
import { Num, Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { DRAFT_KEPT, useDraft, useDraftKept } from '@/session/drafts';
import { fontSize, radius, space } from '@/theme';
import { cleanOdds, formatDay, formatMoney, formatSignedPercent } from '@/utils/format';

const RESULTS: readonly { value: BetResult; label: string }[] = [
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
  { value: 'push', label: 'Push' },
  { value: 'void', label: 'Void' },
  { value: 'half_won', label: 'Half won' },
  { value: 'half_lost', label: 'Half lost' },
  { value: 'cashout', label: 'Cashed out' },
];
const LEG_RESULTS = RESULTS.slice(0, 4) as readonly { value: LegResult; label: string }[];
const RESULT_LABEL = Object.fromEntries(RESULTS.map((item) => [item.value, item.label])) as Record<BetResult, string>;
const RESULT_TONE: Record<BetResult, 'accent' | 'error' | 'neutral' | 'warn'> = {
  won: 'accent',
  half_won: 'accent',
  lost: 'error',
  half_lost: 'error',
  push: 'neutral',
  void: 'neutral',
  cashout: 'warn',
};

export function betTitle(bet: Bet): string {
  if (bet.legs.length === 1) return bet.legs[0].selection;
  return `${bet.legs.length}-leg ${bet.bet_type === 'sgp' ? 'same-game parlay' : 'parlay'}`;
}

/** Body for settling the whole bet with one result. Cashing out needs the amount received. */
export function settlePayload(result: BetResult, cashout: string): { error: string } | { body: BetSettle } {
  if (result !== 'cashout') return { body: { result } };
  const amount = Number(cashout);
  if (cashout.trim() === '' || !Number.isFinite(amount) || amount < 0) return { error: 'Enter the cash-out amount you received.' };
  return { body: { result, cashout_amount: amount } };
}

/** Body for settling a parlay leg by leg. The API works out the bet's result and payout from these. */
export function legSettlePayload(bet: Bet, results: Record<string, LegResult>): BetSettle {
  return { leg_results: bet.legs.map((leg) => ({ leg_id: leg.id, result: results[leg.id] ?? 'won' })) };
}

/** Body for an edit. Stake and sportsbook only change while the bet is open; closing odds only on a single leg. */
export function editPayload(
  bet: Bet,
  draft: { stake: string; sportsbook: string; notes: string; closing: string },
): { error: string } | { body: BetUpdate } {
  const open = bet.status === 'pending';
  const stake = Number(draft.stake);
  if (!Number.isFinite(stake) || stake <= 0) return { error: 'Enter a stake greater than zero.' };
  if (!draft.sportsbook.trim()) return { error: 'Enter the sportsbook.' };
  const body: BetUpdate = { notes: draft.notes.trim() || null };
  if (open) {
    body.stake = stake;
    body.sportsbook = draft.sportsbook.trim();
  }
  if (bet.legs.length === 1 && draft.closing.trim()) {
    body.closing_odds = [{ leg_id: bet.legs[0].id, closing_odds: cleanOdds(draft.closing), odds_format: 'american' }];
  }
  return { body };
}

type Mode = 'idle' | 'settle' | 'legs' | 'edit' | 'delete';

function Figure({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.figure}>
      <Txt variant="caption" tone="muted">
        {label}
      </Txt>
      {children}
    </View>
  );
}

/**
 * One bet: what it is, its numbers (all from the API), its status in words, and the settle, edit and delete actions.
 * An open settle or edit form is a draft: it comes back, with what was typed, if the session ends before it is
 * saved and the bet has not changed in the meantime. The delete confirmation is never brought back.
 */
export function BetCard({ bet, leagueName, onChanged }: { bet: Bet; leagueName?: string; onChanged: () => void }) {
  const theme = useTheme();
  const open = bet.status === 'pending';
  const multi = bet.legs.length > 1;
  const title = betTitle(bet);
  const draft = `bet:${bet.id}:${bet.updated_at}`;
  const [form, setForm] = useDraft<Exclude<Mode, 'delete'>>(`${draft}:form`, 'idle');
  const [deleting, setDeleting] = useState(false);
  const mode: Mode = deleting ? 'delete' : form;
  const setMode = (next: Mode) => {
    setDeleting(next === 'delete');
    if (next !== 'delete') setForm(next);
  };
  const [result, setResult] = useDraft<BetResult>(`${draft}:result`, 'won');
  const [cashout, setCashout] = useDraft(`${draft}:cashout`, '');
  const [legResults, setLegResults] = useDraft<Record<string, LegResult>>(`${draft}:legs`, () =>
    Object.fromEntries(bet.legs.map((leg) => [leg.id, 'won' as LegResult])),
  );
  const [stake, setStake] = useDraft(`${draft}:stake`, String(bet.stake));
  const [sportsbook, setSportsbook] = useDraft(`${draft}:sportsbook`, bet.sportsbook);
  const [notes, setNotes] = useDraft(`${draft}:notes`, bet.notes ?? '');
  const [closing, setClosing] = useDraft(`${draft}:closing`, '');
  const [keptNotice, dismissKeptNotice, draftSaved] = useDraftKept(draft);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    dismissKeptNotice();
    setBusy(true);
    setError(null);
    try {
      await action();
      setMode('idle');
      // The list reloads and replaces this card. Until it does, what the form holds is saved, not a draft.
      draftSaved();
      onChanged();
    } catch (caught) {
      setError(describeError(caught, "That didn't work. Try again."));
    } finally {
      setBusy(false);
    }
  }

  const go = (next: Mode) => {
    dismissKeptNotice();
    setError(null);
    setMode(next);
  };

  const settle = () => {
    const built = settlePayload(result, cashout);
    if ('error' in built) return setError(built.error);
    return run(() => settleBet(bet.id, built.body));
  };

  const save = () => {
    const built = editPayload(bet, { stake, sportsbook, notes, closing });
    if ('error' in built) return setError(built.error);
    return run(() => updateBet(bet.id, built.body));
  };

  const profit = bet.profit ?? 0;
  const meta = [multi ? null : bet.legs[0]?.event_label, leagueName, bet.sportsbook, formatDay(bet.placed_at)].filter(Boolean).join(', ');
  const closingPrice = bet.legs[0]?.closing_price;

  return (
    <View style={[styles.card, { backgroundColor: theme.surface, borderColor: theme.border }]}>
      <View style={styles.block}>
        <Txt weight="semibold">{title}</Txt>
        {multi
          ? bet.legs.map((leg) => (
              <View key={leg.id} style={styles.legLine}>
                <Txt variant="secondary" tone="muted" style={styles.grow}>
                  {leg.selection}
                </Txt>
                <Price price={leg.price} size={fontSize.secondary} tone="muted" />
              </View>
            ))
          : null}
        <Txt variant="secondary" tone="muted">
          {meta}
        </Txt>
        {bet.notes ? (
          <Txt variant="secondary" tone="muted">
            Note: {bet.notes}
          </Txt>
        ) : null}
      </View>

      <View style={styles.figures}>
        <Figure label="Odds">
          <Price price={bet.combined_price} />
        </Figure>
        <Figure label="Stake">
          <Num>{formatMoney(bet.stake)}</Num>
        </Figure>
        {bet.clv !== null && bet.clv !== undefined ? (
          <Figure label="CLV">
            <Num>{formatSignedPercent(bet.clv)}</Num>
          </Figure>
        ) : null}
        {open ? (
          <Figure label="To return">
            <Num>{formatMoney(bet.potential_payout)}</Num>
          </Figure>
        ) : (
          <Figure label="Profit">
            <Num tone={profit > 0 ? 'accent' : profit < 0 ? 'error' : 'text'} weight="semibold">
              {formatMoney(profit, { signed: true })}
            </Num>
          </Figure>
        )}
      </View>

      <View style={styles.badges}>
        {bet.status === 'settled' && bet.result ? (
          <Badge label={RESULT_LABEL[bet.result]} tone={RESULT_TONE[bet.result]} />
        ) : (
          <Badge label="Open" mark="dot" />
        )}
        {bet.settled_by === 'auto' ? <Badge label="Settled from final score" /> : null}
        {open && bet.legs.every((leg) => leg.gradeable) ? <Badge label="Tied to a game" /> : null}
        {bet.source === 'sync' ? <Badge label="Synced" /> : null}
      </View>

      {mode === 'idle' ? (
        <View style={styles.actions}>
          {open ? <Button label="Settle" variant="secondary" compact accessibilityLabel={`Settle ${title}`} onPress={() => go('settle')} /> : null}
          <Button label="Edit" variant="ghost" compact accessibilityLabel={`Edit ${title}`} onPress={() => go('edit')} />
          <Button label="Delete" variant="ghost" compact accessibilityLabel={`Delete ${title}`} onPress={() => go('delete')} />
        </View>
      ) : null}

      {keptNotice && mode !== 'idle' ? <Notice tone="neutral" text={DRAFT_KEPT} /> : null}

      {mode === 'settle' ? (
        <View style={[styles.sheet, { borderColor: theme.border }]}>
          <Choice label="Result" options={RESULTS} value={result} onChange={setResult} />
          {result === 'cashout' ? (
            <Field label="Cash-out amount ($)" mono placeholder="Amount received" keyboardType="decimal-pad" value={cashout} onChangeText={setCashout} />
          ) : null}
          <View style={styles.actions}>
            <Button label="Settle bet" compact disabled={busy} onPress={settle} />
            {multi ? <Button label="Settle by leg" variant="secondary" compact onPress={() => go('legs')} /> : null}
            <Button label="Cancel" variant="ghost" compact onPress={() => go('idle')} />
          </View>
        </View>
      ) : null}

      {mode === 'legs' ? (
        <View style={[styles.sheet, { borderColor: theme.border }]}>
          <Txt variant="heading" accessibilityRole="header">
            Result of each leg
          </Txt>
          {bet.legs.map((leg) => (
            <Choice
              key={leg.id}
              label={leg.selection}
              options={LEG_RESULTS}
              value={legResults[leg.id] ?? 'won'}
              onChange={(value) => setLegResults((current) => ({ ...current, [leg.id]: value }))}
            />
          ))}
          <Txt variant="caption" tone="muted">
            One lost leg loses the parlay. Pushed and void legs drop out and the odds are recalculated.
          </Txt>
          <View style={styles.actions}>
            <Button label="Settle parlay" compact disabled={busy} onPress={() => run(() => settleBet(bet.id, legSettlePayload(bet, legResults)))} />
            <Button label="Cancel" variant="ghost" compact onPress={() => go('idle')} />
          </View>
        </View>
      ) : null}

      {mode === 'edit' ? (
        <View style={[styles.sheet, { borderColor: theme.border }]}>
          {open ? (
            <>
              <Field label="Stake ($)" mono keyboardType="decimal-pad" value={stake} onChangeText={setStake} />
              <Field label="Sportsbook" autoCapitalize="words" value={sportsbook} onChangeText={setSportsbook} />
            </>
          ) : (
            <Txt variant="caption" tone="muted">
              Stake and odds are locked once a bet is settled. To correct the result, delete the bet and log it again.
            </Txt>
          )}
          {!multi ? (
            <Field
              label="Closing odds (American)"
              mono
              keyboardType="numbers-and-punctuation"
              placeholder={closingPrice ? String(Math.round(closingPrice.american)) : 'Optional'}
              hint="Used for closing line value."
              value={closing}
              onChangeText={setClosing}
            />
          ) : null}
          <Field label="Notes" autoCapitalize="sentences" maxLength={500} value={notes} onChangeText={setNotes} />
          <View style={styles.actions}>
            <Button label="Save changes" compact disabled={busy} onPress={save} />
            <Button label="Cancel" variant="ghost" compact onPress={() => go('idle')} />
          </View>
        </View>
      ) : null}

      {mode === 'delete' ? (
        <View style={[styles.sheet, { borderColor: theme.border }]}>
          <Txt variant="secondary">Delete this bet for good?</Txt>
          <View style={styles.actions}>
            <Button label="Delete bet" variant="danger" compact disabled={busy} onPress={() => run(() => deleteBet(bet.id))} />
            <Button label="Keep" variant="ghost" compact onPress={() => go('idle')} />
          </View>
        </View>
      ) : null}

      {error ? (
        <Txt variant="secondary" tone="error" accessibilityRole="alert" accessibilityLiveRegion="assertive">
          {error}
        </Txt>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.panel, padding: space[4], gap: space[3] },
  block: { gap: space[1] },
  grow: { flex: 1 },
  legLine: { flexDirection: 'row', alignItems: 'baseline', gap: space[3] },
  figures: { flexDirection: 'row', flexWrap: 'wrap', columnGap: space[5], rowGap: space[2] },
  figure: { gap: 2 },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  sheet: { gap: space[3], borderTopWidth: StyleSheet.hairlineWidth, paddingTop: space[3] },
});
