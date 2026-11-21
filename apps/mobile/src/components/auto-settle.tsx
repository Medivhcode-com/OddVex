import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { autoSettleBets, describeError } from '@/api/client';
import type { AutoSettle } from '@/api/types';
import { Button } from '@/components/states';
import { Txt } from '@/components/text';
import { space } from '@/theme';

const REASONS: Record<string, string> = {
  not_gradeable: 'not tied to a game and side',
  event_not_final: 'game not finished',
  event_unavailable: 'game no longer available',
  manual_result_required: 'needs its result entered by hand',
};

/** Added when one call stopped at its limit (the API settles at most 200 bets a call) with open bets unchecked. */
export const AUTO_SETTLE_MORE = 'More open bets are left to check: run it again to continue.';

/**
 * "2 bets settled from final scores. Left open: 1 game not finished." The same sentence the web tracker shows,
 * followed by `AUTO_SETTLE_MORE` when the API says `has_more` (a missing value counts as false).
 */
export function autoSettleMessage(out: AutoSettle): string {
  const counts = new Map<string, number>();
  for (const skip of out.skipped) counts.set(skip.reason, (counts.get(skip.reason) ?? 0) + 1);
  const skipped = [...counts].map(([reason, count]) => `${count} ${REASONS[reason] ?? reason}`).join(', ');
  const settled = `${out.settled.length} ${out.settled.length === 1 ? 'bet' : 'bets'} settled from final scores.`;
  return settled + (skipped ? ` Left open: ${skipped}.` : '') + (out.has_more ? ` ${AUTO_SETTLE_MORE}` : '');
}

/**
 * Settles open bets that are tied to a finished game, from the final score. The API does the grading. When it
 * reports more open bets than one call checks, a second button runs it again for the rest.
 */
export function AutoSettleButton({ onSettled }: { onSettled: () => void }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [more, setMore] = useState(false);

  async function run() {
    setBusy(true);
    setMessage(null);
    setFailed(false);
    setMore(false);
    try {
      const out = await autoSettleBets();
      setMessage(autoSettleMessage(out));
      setMore(Boolean(out.has_more));
      onSettled();
    } catch (caught) {
      setFailed(true);
      setMessage(describeError(caught, 'Auto-settle failed. Try again.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.wrap}>
      <Button label={busy ? 'Checking scores' : 'Settle from final scores'} variant="secondary" compact disabled={busy} onPress={run} />
      {message ? (
        <Txt
          variant="caption"
          tone={failed ? 'error' : 'muted'}
          accessibilityRole={failed ? 'alert' : undefined}
          accessibilityLiveRegion={failed ? 'assertive' : 'polite'}>
          {message}
        </Txt>
      ) : null}
      {more && !busy ? <Button label="Check the rest" variant="secondary" compact onPress={run} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({ wrap: { gap: space[2] } });
