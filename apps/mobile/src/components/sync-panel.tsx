import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { createSyncConnection, deleteSyncConnection, describeError, runSync } from '@/api/client';
import type { SyncConnection, SyncProvider } from '@/api/types';
import { Badge } from '@/components/badge';
import { HelpLine } from '@/components/help-link';
import { Button, Notice } from '@/components/states';
import { Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { space } from '@/theme';
import { formatAge } from '@/utils/format';

type Message = { tone: 'accent' | 'error' | 'warn'; text: string };

/**
 * Sportsbook sync against the API's mock provider. No real account is contacted, and the panel says so.
 * `onChanged` reloads the connections and the bets after every action. The panel ends with the helpline.
 */
export function SyncPanel({
  providers,
  connections,
  now,
  onChanged,
}: {
  providers: readonly SyncProvider[];
  connections: readonly SyncConnection[];
  now: Date;
  onChanged: () => void;
}) {
  const theme = useTheme();
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<Message | null>(null);
  const provider = providers[0];

  async function run(key: string, action: () => Promise<Message | null>) {
    setBusy(key);
    setMessage(null);
    try {
      setMessage(await action());
      onChanged();
    } catch (caught) {
      setMessage({ tone: 'error', text: describeError(caught, "That didn't work. Try again.") });
    } finally {
      setBusy(null);
    }
  }

  const sync = (connection: SyncConnection) =>
    run(`sync-${connection.id}`, async () => {
      const result = await runSync(connection.id);
      if (result.status === 'failed') {
        return { tone: 'warn', text: `Sync failed${result.retryable ? ' and can be retried' : ''}: ${result.error_message ?? 'no detail given'}.` };
      }
      const imported = `${result.imported_count} new ${result.imported_count === 1 ? 'bet' : 'bets'} imported`;
      return { tone: 'accent', text: `Sync finished. ${imported}, ${result.duplicate_count} already here.` };
    });

  const disconnect = (connection: SyncConnection) =>
    run(`del-${connection.id}`, async () => {
      const out = await deleteSyncConnection(connection.id);
      return { tone: 'accent', text: `Disconnected. ${out.bets_deleted} synced ${out.bets_deleted === 1 ? 'bet' : 'bets'} deleted.` };
    });

  const connect = (target: SyncProvider) =>
    run('connect', async () => {
      await createSyncConnection(target.key);
      return { tone: 'accent', text: `Connected to ${target.name}. Choose Sync now to import its sample bets.` };
    });

  return (
    <View style={styles.panel}>
      <Notice
        title="Demonstration only"
        text="This connects to a mock sportsbook that returns sample bets. No real sportsbook account is contacted, and OddVex never asks for a sportsbook password."
      />
      {connections.length === 0 ? (
        <Txt variant="secondary" tone="muted">
          No connections yet.
        </Txt>
      ) : (
        connections.map((connection) => {
          const name = connection.label || connection.provider_name;
          return (
            <View key={connection.id} style={[styles.connection, { borderTopColor: theme.border }]}>
              <View style={styles.name}>
                <Txt weight="semibold">{name}</Txt>
                {connection.is_mock ? <Badge label="Mock" /> : null}
              </View>
              <Txt variant="secondary" tone="muted">
                {connection.bet_count} synced {connection.bet_count === 1 ? 'bet' : 'bets'}.{' '}
                {connection.last_synced_at ? `Last synced ${formatAge(connection.last_synced_at, now)}.` : 'Not synced yet.'}
              </Txt>
              <View style={styles.actions}>
                <Button
                  label={busy === `sync-${connection.id}` ? 'Syncing' : 'Sync now'}
                  variant="secondary"
                  compact
                  disabled={busy !== null}
                  accessibilityLabel={`Sync ${name} now`}
                  onPress={() => sync(connection)}
                />
                <Button
                  label="Disconnect and delete bets"
                  variant="danger"
                  compact
                  disabled={busy !== null}
                  accessibilityLabel={`Disconnect ${name} and delete its bets`}
                  onPress={() => disconnect(connection)}
                />
              </View>
            </View>
          );
        })
      )}
      {provider ? (
        <Button
          label={busy === 'connect' ? 'Connecting' : `Connect ${provider.name}`}
          variant="secondary"
          disabled={busy !== null}
          onPress={() => connect(provider)}
        />
      ) : null}
      {message ? <Notice tone={message.tone} text={message.text} /> : null}
      <HelpLine />
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { gap: space[3] },
  connection: { gap: space[2], borderTopWidth: StyleSheet.hairlineWidth, paddingTop: space[3] },
  name: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: space[2] },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
});
