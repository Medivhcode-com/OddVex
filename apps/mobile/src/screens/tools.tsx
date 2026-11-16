import { useRouter } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { getEvents } from '@/api/client';
import { ClvCalculator, ConvertCalculator, EvCalculator, NoVigCalculator } from '@/components/calculators';
import { legOptions, ParlayBuilder } from '@/components/parlay-builder';
import { Screen } from '@/components/screen';
import { Button, Notice, Panel, PanelHeading, SkeletonCards } from '@/components/states';
import { Txt } from '@/components/text';
import { useResource } from '@/hooks/use-resource';
import { useFlag } from '@/providers/flags';
import { ValueEntry } from '@/components/value-entry';
import { space } from '@/theme';

export function ToolsScreen() {
  const router = useRouter();
  const valueScreen = useFlag('value_screen');
  return (
    <Screen>
      {valueScreen ? <ValueEntry /> : null}
      <Txt variant="secondary" tone="muted">
        Each calculator shows its working. Enter odds as American (−110), decimal (1.91) or fractional (10/11).
      </Txt>
      <Panel>
        <View style={styles.block}>
          <PanelHeading
            title="Parlay research"
            description="See what a parlay pays and how often it has to win. When legs come from the same game, OddVex warns you and does not invent a combined probability."
          />
          <Button label="Open parlay research" variant="secondary" onPress={() => router.push('/parlay')} />
        </View>
      </Panel>
      <ConvertCalculator />
      <NoVigCalculator />
      <EvCalculator />
      <ClvCalculator />
    </Screen>
  );
}

export function ParlayScreen() {
  const events = useResource('events:', (signal) => getEvents({}, signal));
  return (
    <Screen refreshing={events.refreshing} onRefresh={events.reload}>
      <Txt variant="secondary" tone="muted">
        See what a parlay pays and how often it has to win. When legs come from the same game, OddVex warns you and
        does not invent a combined probability.
      </Txt>
      {events.status === 'loading' ? (
        <SkeletonCards label="Loading the board" count={1} />
      ) : (
        <>
          {events.error !== undefined ? (
            <Notice
              text={
                events.data
                  ? "Couldn't refresh the board. The legs listed use the last prices loaded."
                  : "OddVex can't reach its data service, so the board is unavailable. Pull down to try again, or add custom legs."
              }
            />
          ) : null}
          <ParlayBuilder options={legOptions(events.data ?? [])} />
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({ block: { gap: space[3] } });
