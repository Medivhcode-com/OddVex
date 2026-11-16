import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { describeError, getNotificationPreferences, setStakeReminder, updateNotificationPreferences } from '@/api/client';
import type { NotificationKind, NotificationPreferences, StakeReminder } from '@/api/types';
import { Field, SwitchRow } from '@/components/form';
import { Button, Notice } from '@/components/states';
import { Txt } from '@/components/text';
import { useStakeReminder } from '@/hooks/use-notifications';
import { useResource } from '@/hooks/use-resource';
import { useFlag } from '@/providers/flags';
import { useSession } from '@/providers/session';
import { space } from '@/theme';
import { formatMoney } from '@/utils/format';

export const NOTIFICATIONS_IN_APP_ONLY = 'Notifications appear in the app only. There is no push or email yet.';
export const STAKE_REMINDER_DESCRIPTION = 'A reminder, not a limit. OddVex will not stop you logging bets.';

const SWITCHES: readonly { kind: NotificationKind; label: string }[] = [
  { kind: 'price_alert', label: 'Price alerts' },
  { kind: 'line_move', label: 'Line moves' },
  { kind: 'game_start', label: 'Game start' },
  { kind: 'game_final', label: 'Final scores' },
  { kind: 'bet_settled', label: 'Settled bets' },
  { kind: 'sync_finished', label: 'Sync results' },
  { kind: 'stake_reminder', label: 'Weekly staking reminder' },
];
/** Only offered while the `community` flag is on: the API creates these kinds only then. */
const COMMUNITY_SWITCHES: readonly { kind: NotificationKind; label: string }[] = [
  { kind: 'new_follower', label: 'New followers' },
  { kind: 'pick_comment', label: 'Comments on your picks' },
  { kind: 'pick_graded', label: 'Graded picks' },
];

/** One switch per kind of notification. A change sends only that kind; the API leaves the others alone. */
export function NotificationPreferencesForm({ userId }: { userId: string }) {
  const router = useRouter();
  const loaded = useResource(`notification-preferences:${userId}`, getNotificationPreferences);
  const [saved, setSaved] = useState<NotificationPreferences | null>(null);
  const [pending, setPending] = useState<NotificationKind | null>(null);
  const [error, setError] = useState<string | null>(null);
  const preferences = saved ?? loaded.data;
  const community = useFlag('community');
  const switches = community ? [...SWITCHES, ...COMMUNITY_SWITCHES] : SWITCHES;
  // The three community kinds are typed as nullable for older clients. The API always sends them; a missing
  // value means the default, which is on.
  const isOn = (kind: NotificationKind) => preferences?.in_app[kind] !== false;

  async function toggle(kind: NotificationKind, value: boolean) {
    if (pending) return;
    setPending(kind);
    setError(null);
    try {
      setSaved(await updateNotificationPreferences({ in_app: { [kind]: value } }));
    } catch (caught) {
      setError(describeError(caught, 'That setting was not saved. Try again.'));
    } finally {
      setPending(null);
    }
  }

  return (
    <View style={styles.block}>
      {preferences ? (
        <View>
          {switches.map(({ kind, label }) => (
            // While a change is being saved the switch already shows the new position.
            <SwitchRow
              key={kind}
              label={label}
              value={pending === kind ? !isOn(kind) : isOn(kind)}
              onChange={(value) => void toggle(kind, value)}
            />
          ))}
        </View>
      ) : loaded.status === 'error' ? (
        <View style={styles.block} accessibilityRole="alert">
          <Txt variant="secondary" tone="muted">
            OddVex can&apos;t reach its data service, so your notification settings did not load.
          </Txt>
          <Button label="Try again" variant="secondary" accessibilityLabel="Try loading notification settings again" onPress={loaded.reload} />
        </View>
      ) : (
        <Txt variant="secondary" tone="muted" accessibilityLiveRegion="polite">
          Loading your notification settings.
        </Txt>
      )}
      {error ? <Notice tone="error" text={error} /> : null}
      <Txt variant="caption" tone="muted">
        Switching a kind off stops its notifications. Your alerts keep running.
      </Txt>
      <Button label="Open notifications" variant="secondary" onPress={() => router.push('/notifications')} />
    </View>
  );
}

/**
 * Shown when this week's stakes are at or above the amount the user set for themselves. Supportive and plain:
 * it states the two numbers, says nothing is blocked, and gives the helpline. Announced politely, not as an alarm.
 */
export function StakeReminderNotice({ reminder }: { reminder: StakeReminder }) {
  if (!reminder.exceeded || reminder.weekly_stake_threshold == null) return null;
  return (
    <Notice
      tone="neutral"
      title="You have reached your weekly staking reminder"
      text={`You have staked ${formatMoney(reminder.staked_this_week)} this week. Your reminder is set at ${formatMoney(reminder.weekly_stake_threshold)}. This is a reminder, not a limit: OddVex will not stop you logging bets. If betting is causing you stress, free, confidential help is available at 1-800-GAMBLER.`}
    />
  );
}

function StakeReminderEditor({ reminder, onSaved }: { reminder: StakeReminder; onSaved: (next: StakeReminder) => void }) {
  const threshold = reminder.weekly_stake_threshold ?? null;
  const [amount, setAmount] = useState(threshold === null ? '' : String(threshold));
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function send(value: number | null) {
    setBusy(true);
    setError(null);
    setConfirmation(null);
    try {
      const next = await setStakeReminder(value);
      if (value === null) setAmount('');
      setConfirmation(value === null ? 'Reminder turned off.' : 'Reminder saved.');
      onSaved(next);
    } catch (caught) {
      setError(describeError(caught, 'The reminder was not saved. Try again.'));
    } finally {
      setBusy(false);
    }
  }

  function save() {
    const text = amount.trim().replace(/[$,]/g, '');
    const value = Number(text);
    if (text === '' || !Number.isFinite(value) || value <= 0) return setFieldError('Enter a weekly amount greater than zero.');
    if (value > 1_000_000) return setFieldError('Enter an amount of $1,000,000 or less.');
    setFieldError(null);
    void send(value);
  }

  return (
    <View style={styles.block}>
      <Txt variant="secondary">You have staked {formatMoney(reminder.staked_this_week)} this week.</Txt>
      <Txt variant="secondary" tone="muted">
        {threshold === null ? 'The reminder is off.' : `Your reminder is set at ${formatMoney(threshold)} a week.`}
      </Txt>
      <StakeReminderNotice reminder={reminder} />
      <Field
        label="Weekly amount ($)"
        hint="You get one notification in the week your total stakes reach this amount. Weeks run Monday to Sunday, UTC."
        mono
        placeholder="200"
        keyboardType="decimal-pad"
        value={amount}
        onChangeText={setAmount}
        error={fieldError}
      />
      {error ? <Notice tone="error" text={error} /> : null}
      {confirmation ? <Notice tone="accent" text={confirmation} /> : null}
      <View style={styles.row}>
        <Button label={busy ? 'Saving' : 'Save reminder'} onPress={save} disabled={busy} />
        {threshold !== null ? <Button label="Turn off" variant="secondary" accessibilityLabel="Turn off the reminder" onPress={() => void send(null)} disabled={busy} /> : null}
      </View>
    </View>
  );
}

/** The weekly staking reminder: this week's total, the amount to be reminded at, Save and Turn off. */
export function StakeReminderForm({ userId }: { userId: string }) {
  const { changed } = useSession();
  const loaded = useStakeReminder(userId);
  // The answer to the last save, shown until the next load replaces what it was based on.
  const [saved, setSaved] = useState<{ base: StakeReminder | undefined; value: StakeReminder } | null>(null);
  const reminder = saved && saved.base === loaded.data ? saved.value : loaded.data;

  if (!reminder) {
    return loaded.status === 'error' ? (
      <View style={styles.block} accessibilityRole="alert">
        <Txt variant="secondary" tone="muted">
          OddVex can&apos;t reach its data service, so your staking reminder did not load.
        </Txt>
        <Button label="Try again" variant="secondary" accessibilityLabel="Try loading the staking reminder again" onPress={loaded.reload} />
      </View>
    ) : (
      <Txt variant="secondary" tone="muted" accessibilityLiveRegion="polite">
        Loading your staking reminder.
      </Txt>
    );
  }
  return (
    <StakeReminderEditor
      reminder={reminder}
      onSaved={(next) => {
        setSaved({ base: loaded.data, value: next });
        changed('reminder');
      }}
    />
  );
}

const styles = StyleSheet.create({
  block: { gap: space[3] },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: space[3] },
});
