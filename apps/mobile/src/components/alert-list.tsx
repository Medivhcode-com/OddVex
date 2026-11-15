import { useRouter } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import { deleteAlert, describeError, evaluateAlerts, getAlerts, updateAlert } from '@/api/client';
import type { AlertEvaluation, AlertRule, AlertState } from '@/api/types';
import { Badge } from '@/components/badge';
import { Screen } from '@/components/screen';
import { Button, EmptyState, ErrorState, Notice, Panel, SkeletonCards } from '@/components/states';
import { Txt } from '@/components/text';
import { useResource } from '@/hooks/use-resource';
import { useSession } from '@/providers/session';
import { space } from '@/theme';

const GROUPS: readonly { state: AlertState; title: string; note: string }[] = [
  { state: 'active', title: 'Active', note: 'Being checked.' },
  { state: 'triggered', title: 'Triggered', note: 'Fired once and stopped. Set one again to keep watching.' },
  { state: 'paused', title: 'Paused', note: 'Not checked until you resume them.' },
  { state: 'expired', title: 'Expired', note: 'The game ended or is no longer available before the alert fired.' },
];

const STATE_BADGE: Record<AlertState, { label: string; tone: 'accent' | 'warn' | 'neutral'; mark?: 'dot' | 'diamond' }> = {
  active: { label: 'Active', tone: 'accent', mark: 'dot' },
  triggered: { label: 'Triggered', tone: 'warn', mark: 'diamond' },
  paused: { label: 'Paused', tone: 'neutral' },
  expired: { label: 'Expired', tone: 'neutral' },
};

/** Groups rules by state in a fixed order, keeping the API's newest-first order inside each and dropping empty groups. */
export function groupAlerts(rules: readonly AlertRule[]) {
  return GROUPS.map((group) => ({ ...group, rules: rules.filter((rule) => rule.state === group.state) })).filter(
    (group) => group.rules.length > 0,
  );
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** "Checked 4 alerts. 1 fired." The expired count is added only when there is one. */
export function evaluationText(result: AlertEvaluation): string {
  const expired = result.expired > 0 ? ` ${result.expired} expired.` : '';
  return `Checked ${plural(result.evaluated, 'alert', 'alerts')}. ${result.fired} fired.${expired}`;
}

/** One rule: the API's summary, its state in words, and the actions that state allows. */
function AlertRow({ rule, onChanged }: { rule: AlertRule; onChanged: () => void }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const badge = STATE_BADGE[rule.state];

  async function run(action: () => Promise<unknown>, fallback: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (caught) {
      setError(describeError(caught, fallback));
    } finally {
      setBusy(false);
    }
  }

  const setState = (state: 'active' | 'paused') => run(() => updateAlert(rule.id, state), 'The alert was not changed. Try again.');

  return (
    <Panel>
      <View style={styles.rule}>
        <Badge label={badge.label} tone={badge.tone} mark={badge.mark} />
        <Txt weight="medium">{rule.summary}</Txt>
        {rule.available === false ? (
          <Txt variant="caption" tone="muted">
            {rule.team_id ? 'This team is no longer in the data.' : 'This game is no longer in the data.'}
          </Txt>
        ) : null}
        {error ? <Notice tone="error" text={error} /> : null}
        {confirming ? (
          <View style={styles.rule}>
            <Txt variant="secondary">Delete this alert? Notifications it already created are kept.</Txt>
            <View style={styles.actions}>
              <Button
                label={busy ? 'Deleting' : 'Delete alert'}
                variant="danger"
                compact
                disabled={busy}
                accessibilityLabel={`Delete alert: ${rule.summary}`}
                onPress={() => run(() => deleteAlert(rule.id), 'The alert was not deleted. Try again.')}
              />
              <Button label="Keep alert" variant="secondary" compact disabled={busy} onPress={() => setConfirming(false)} />
            </View>
          </View>
        ) : (
          <View style={styles.actions}>
            {rule.state === 'active' ? (
              <Button label="Pause" variant="secondary" compact disabled={busy} accessibilityLabel={`Pause alert: ${rule.summary}`} onPress={() => setState('paused')} />
            ) : null}
            {rule.state === 'paused' ? (
              <Button label="Resume" variant="secondary" compact disabled={busy} accessibilityLabel={`Resume alert: ${rule.summary}`} onPress={() => setState('active')} />
            ) : null}
            {rule.state === 'triggered' ? (
              <Button
                label="Set again"
                variant="secondary"
                compact
                disabled={busy}
                accessibilityLabel={`Set alert again: ${rule.summary}`}
                onPress={() => setState('active')}
              />
            ) : null}
            {rule.event_id && rule.available !== false ? (
              <Button
                label="Open game"
                variant="ghost"
                compact
                accessibilityLabel={`Open game: ${rule.label}`}
                onPress={() =>
                  router.push({ pathname: '/event/[id]', params: rule.market ? { id: rule.event_id!, market: rule.market } : { id: rule.event_id! } })
                }
              />
            ) : null}
            <Button label="Delete" variant="ghost" compact disabled={busy} accessibilityLabel={`Delete alert: ${rule.summary}`} onPress={() => setConfirming(true)} />
          </View>
        )}
      </View>
    </Panel>
  );
}

/**
 * The signed-in user's alert rules, grouped Active / Triggered / Paused / Expired, with "Check now".
 * Alerts are created from a game page; this screen manages them.
 */
export function AlertList({ userId, header }: { userId: string; header?: ReactNode }) {
  const router = useRouter();
  const { revision, changed } = useSession();
  const alerts = useResource(`alerts:${userId}`, (signal) => getAlerts(null, signal), revision.alerts);
  const [checking, setChecking] = useState(false);
  const [checked, setChecked] = useState<string | null>(null);
  const [checkError, setCheckError] = useState<string | null>(null);

  async function checkNow() {
    setChecking(true);
    setChecked(null);
    setCheckError(null);
    try {
      const result = await evaluateAlerts();
      setChecked(evaluationText(result));
      alerts.reload();
      changed('notifications');
    } catch (caught) {
      setCheckError(describeError(caught, "The alerts weren't checked. Try again."));
    } finally {
      setChecking(false);
    }
  }

  const onChanged = () => {
    alerts.reload();
    changed('alerts');
  };
  const groups = alerts.data ? groupAlerts(alerts.data) : [];

  return (
    <Screen refreshing={alerts.refreshing} onRefresh={alerts.reload}>
      {header}
      {alerts.status === 'loading' ? (
        <SkeletonCards label="Loading your alerts" />
      ) : alerts.status === 'error' ? (
        <ErrorState error={alerts.error} onRetry={alerts.reload} />
      ) : groups.length === 0 ? (
        <EmptyState
          title="No alerts yet"
          body="Alerts are created from a game page. Open a game and choose Set an alert to watch a price, a line move, the start or the final score.">
          <Button label="Browse games" variant="secondary" onPress={() => router.navigate('/')} />
        </EmptyState>
      ) : (
        <>
          {alerts.error !== undefined ? <Notice text="Couldn't refresh. Showing the last alerts loaded." /> : null}
          <Panel>
            <View style={styles.rule}>
              <Txt variant="secondary" tone="muted">
                There is no push yet. Alerts are checked when you open the app or your notifications, or when you choose Check now.
              </Txt>
              <Button label={checking ? 'Checking' : 'Check now'} variant="secondary" disabled={checking} onPress={checkNow} />
              {checked ? <Notice tone="accent" text={checked} /> : null}
              {checkError ? <Notice tone="error" text={checkError} /> : null}
            </View>
          </Panel>
          {groups.map((group) => (
            <View key={group.state} style={styles.group}>
              <View style={styles.groupHeader}>
                <Txt variant="heading" accessibilityRole="header">
                  {group.title}
                </Txt>
                <Txt variant="caption" tone="muted">
                  {plural(group.rules.length, 'alert', 'alerts')}
                </Txt>
              </View>
              <Txt variant="caption" tone="muted">
                {group.note}
              </Txt>
              {group.rules.map((rule) => (
                <AlertRow key={`${rule.id}-${rule.state}`} rule={rule} onChanged={onChanged} />
              ))}
            </View>
          ))}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  rule: { gap: space[2] },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  group: { gap: space[2] },
  groupHeader: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', paddingTop: space[2] },
});
