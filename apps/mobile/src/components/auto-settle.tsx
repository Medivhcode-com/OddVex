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
};

/** "2 bets settled from final scores. Left open: 1 game not finished." The same sentence the web tracker shows. */
export function autoSettleMessage(out: AutoSettle): string {
  const counts = new Map<string, number>();
  for (const skip of out.skipped) counts.set(skip.reason, (counts.get(skip.reason) ?? 0) + 1);
  const skipped = [...counts].map(([reason, count]) => `${count} ${REASONS[reason] ?? reason}`).join(', ');
  const settled = `${out.settled.length} ${out.settled.length === 1 ? 'bet' : 'bets'} settled from final scores.`;
  return settled + (skipped ? ` Left open: ${skipped}.` : '');
}

/** Settles open bets that are tied to a finished game, from the final score. The API does the grading. */
export function AutoSettleButton({ onSettled }: { onSettled: () => void }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  async function run() {
    setBusy(true);
    setMessage(null);
    setFailed(false);
    try {
      setMessage(autoSettleMessage(await autoSettleBets()));
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
    </View>
  );
}

const styles = StyleSheet.create({ wrap: { gap: space[2] } });
