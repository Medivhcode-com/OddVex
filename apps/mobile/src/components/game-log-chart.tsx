import { ScrollView, StyleSheet, View } from 'react-native';

import type { GameLogEntry } from '@/api/types';
import { Num, Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { space } from '@/theme';
import { formatDay, formatLine } from '@/utils/format';

const PLOT_HEIGHT = 140;
const BAR_WIDTH = 28;
const COLUMN_WIDTH = 48;

const RESULT_TEXT = { over: 'Over', under: 'Under', push: 'Push' } as const;

/**
 * Each game as a bar against the line, oldest on the left. Built from plain views: no chart library.
 * Bar heights only place values on the screen; over, under and push are the API's own grading of each game.
 * Over bars are filled, under bars are outlined, pushes are filled in a quieter tone, and every bar carries
 * its value and the word, so nothing depends on color. The line is drawn dashed and labelled.
 */
export function GameLogChart({ games, line, summary }: { games: readonly GameLogEntry[]; line: number; summary: string }) {
  const theme = useTheme();
  const top = Math.max(line, ...games.map((game) => game.value)) || 1;
  const height = (value: number) => Math.max(2, (value / (top * 1.1)) * PLOT_HEIGHT);
  const lineBottom = (line / (top * 1.1)) * PLOT_HEIGHT;

  return (
    <View accessible accessibilityRole="image" accessibilityLabel={summary}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <View>
          <View style={[styles.plot, { height: PLOT_HEIGHT, borderBottomColor: theme.borderStrong }]}>
            {games.map((game) => {
              const over = game.result === 'over';
              const push = game.result === 'push';
              return (
                <View key={`${game.date}-${game.event_id}`} style={styles.column}>
                  <Num size={11} tone="text">
                    {game.value}
                  </Num>
                  <View
                    style={[
                      styles.bar,
                      { height: height(game.value), borderColor: theme.borderStrong },
                      over && { backgroundColor: theme.accent, borderColor: theme.accent },
                      push && { backgroundColor: theme.muted, borderColor: theme.muted },
                    ]}
                  />
                </View>
              );
            })}
            <View pointerEvents="none" style={[styles.line, { bottom: lineBottom, borderTopColor: theme.second }]} />
            <View pointerEvents="none" style={[styles.lineLabel, { bottom: lineBottom + 2, backgroundColor: theme.surface }]}>
              <Num size={11} tone="second">
                Line {formatLine(line)}
              </Num>
            </View>
          </View>
          <View style={styles.labels}>
            {games.map((game) => (
              <View key={`${game.date}-${game.event_id}`} style={styles.column}>
                <Txt variant="caption" tone="muted" numberOfLines={1} maxFontSizeMultiplier={1.3}>
                  {game.is_home ? 'v' : '@'}
                  {game.opponent.abbreviation}
                </Txt>
                <Txt variant="caption" tone={game.result === 'over' ? 'accent' : 'muted'} weight="medium" maxFontSizeMultiplier={1.3}>
                  {RESULT_TEXT[game.result]}
                </Txt>
              </View>
            ))}
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

/** The same games as a list, most recent first: date, opponent, value and the result in words. */
export function GameLogList({ games }: { games: readonly GameLogEntry[] }) {
  const theme = useTheme();
  return (
    <View>
      {games.map((game) => {
        const where = `${game.is_home ? 'vs' : 'at'} ${game.opponent.name}`;
        const mark = game.result === 'over' ? '▲ ' : game.result === 'under' ? '▽ ' : '';
        return (
          <View
            key={`${game.date}-${game.event_id}`}
            accessible
            accessibilityLabel={`${formatDay(game.date)}, ${where}, ${game.value}, ${RESULT_TEXT[game.result]}`}
            style={[styles.row, { borderTopColor: theme.border }]}>
            <Txt variant="secondary" tone="muted" style={styles.date}>
              {formatDay(game.date)}
            </Txt>
            <Txt variant="secondary" style={styles.opponent} numberOfLines={2}>
              {where}
            </Txt>
            <Num>{game.value}</Num>
            <Txt variant="secondary" tone={game.result === 'over' ? 'accent' : 'muted'} style={styles.result}>
              {mark}
              {RESULT_TEXT[game.result]}
            </Txt>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingTop: space[2] },
  plot: { flexDirection: 'row', alignItems: 'flex-end', borderBottomWidth: 1 },
  column: { width: COLUMN_WIDTH, alignItems: 'center', gap: 2 },
  bar: { width: BAR_WIDTH, borderWidth: 1, borderBottomWidth: 0, borderTopLeftRadius: 3, borderTopRightRadius: 3 },
  line: { position: 'absolute', left: 0, right: 0, borderTopWidth: 2, borderStyle: 'dashed' },
  lineLabel: { position: 'absolute', right: 0, paddingHorizontal: space[1] },
  labels: { flexDirection: 'row', paddingTop: space[1] },
  row: { flexDirection: 'row', alignItems: 'center', gap: space[3], minHeight: 44, borderTopWidth: StyleSheet.hairlineWidth },
  date: { width: 56 },
  opponent: { flex: 1 },
  result: { width: 68, textAlign: 'right' },
});
