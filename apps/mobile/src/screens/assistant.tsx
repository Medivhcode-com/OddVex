import { useRouter, type Href } from 'expo-router';
import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-screens/experimental';

import { ApiError, askAssistant, describeError, getEvents, getProps } from '@/api/client';
import type { AssistantReply, EventSummary, PropBoardRow } from '@/api/types';
import { Button } from '@/components/states';
import { Txt } from '@/components/text';
import { useNow } from '@/hooks/use-now';
import { useResource } from '@/hooks/use-resource';
import { useTheme } from '@/hooks/use-theme';
import { fontSize, radius, space, touchTarget } from '@/theme';
import { formatAge } from '@/utils/format';

export const ASSISTANT_INTRO =
  "Answers come only from OddVex data and its calculation engine, with sources listed. It doesn't make picks or predict outcomes.";

/** Example questions seeded with names from the current data, so the first tap gets a real answer. */
export function examplePrompts(events: readonly EventSummary[], props: readonly PropBoardRow[]): string[] {
  const team = events[0]?.home_team.name;
  const prop = props[0];
  return [
    team ? `Who has the best price on the ${team}?` : null,
    prop ? `How has ${prop.player.name} done on ${prop.market.replace(/_/g, ' ')} lately?` : null,
    'What is expected value?',
    'How do you remove the vig?',
    'How are my bets doing?',
  ].filter((example): example is string => Boolean(example));
}

/**
 * Turns one of the assistant's web links into the matching screen in this app, or null when there is none.
 * `/app/games/{id}` is the game, `/app/props/{id}` the prop analyzer (with its `market`), and the section
 * roots go to their tabs. The odds board on the web is the Games tab here.
 */
export function suggestionRoute(href: string): Href | null {
  const [path, query = ''] = href.split('#')[0].split('?');
  const market = query
    .split('&')
    .map((pair) => pair.split('='))
    .find(([key]) => key === 'market')?.[1];
  const parts = path.replace(/\/+$/, '').split('/').filter(Boolean);
  if (parts[0] !== 'app') return null;
  const [, section, id] = parts;
  if (section === undefined) return '/';
  if (section === 'games' || section === 'odds') {
    return id ? { pathname: '/event/[id]', params: { id: decodeURIComponent(id) } } : '/';
  }
  if (section === 'props') {
    if (!id) return '/props';
    return { pathname: '/player/[id]', params: market ? { id: decodeURIComponent(id), market: decodeURIComponent(market) } : { id: decodeURIComponent(id) } };
  }
  if (section === 'tools') return '/tools';
  if (section === 'parlay') return '/parlay';
  if (section === 'tracker') return '/tracker';
  if (section === 'settings') return '/settings';
  if (section === 'assistant') return '/assistant';
  return null;
}

/** "Sources: Odds board (synthetic data, updated 42s ago)", or the line saying no data was used. */
export function sourcesText(reply: Pick<AssistantReply, 'sources'>, now: Date): string {
  if (!reply.sources.length) return 'No data was used for this answer.';
  return `Sources: ${reply.sources.map((source) => `${source.label} (${source.data_mode} data, updated ${formatAge(source.as_of, now)})`).join('; ')}`;
}

/** One answer: the text, links to the matching screens, then the sources and the disclaimer, every time. */
export function AssistantAnswer({ reply, now, onOpen }: { reply: AssistantReply; now: Date; onOpen: (route: Href) => void }) {
  const theme = useTheme();
  const links = reply.suggestions.flatMap((suggestion) => {
    const route = suggestionRoute(suggestion.href);
    return route ? [{ ...suggestion, route }] : [];
  });
  return (
    <View style={[styles.answer, { borderColor: theme.border, backgroundColor: theme.surface }]}>
      <Txt accessibilityLabel={`OddVex AI answered: ${reply.answer}`} style={styles.answerText}>
        {reply.answer}
      </Txt>
      {links.length ? (
        <View style={styles.chips}>
          {links.map((link) => (
            <Button key={link.href + link.label} label={link.label} variant="secondary" compact onPress={() => onOpen(link.route)} />
          ))}
        </View>
      ) : null}
      <View style={[styles.footnotes, { borderTopColor: theme.border }]}>
        <Txt variant="caption" tone="muted">
          {sourcesText(reply, now)}
        </Txt>
        <Txt variant="caption" tone="muted">
          {reply.disclaimer}
        </Txt>
      </View>
    </View>
  );
}

type Turn = { id: number; question: string; reply?: AssistantReply; error?: string };

export function AssistantScreen() {
  const theme = useTheme();
  const router = useRouter();
  const now = useNow();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const nextId = useRef(1);
  const scroll = useRef<React.ComponentRef<typeof ScrollView>>(null);
  const events = useResource('assistant-events', (signal) => getEvents({ status: 'upcoming' }, signal).catch(() => []));
  const props = useResource('assistant-props', (signal) => getProps(null, signal).catch(() => []));
  const examples = events.data && props.data ? examplePrompts(events.data, props.data) : [];

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    const id = nextId.current++;
    setTurns((current) => [...current, { id, question: text }]);
    setInput('');
    setBusy(true);
    try {
      const reply = await askAssistant(text);
      setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, reply } : turn)));
    } catch (caught) {
      const error =
        caught instanceof ApiError && caught.status === 429
          ? "You've asked a lot of questions quickly. Wait a minute, then ask again."
          : describeError(caught, "OddVex AI couldn't answer. Try again.");
      setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, error } : turn)));
    } finally {
      setBusy(false);
    }
  }

  const open = (route: Href) => router.push(route);

  const body = (
    <KeyboardAvoidingView
      style={styles.fill}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 96 : 0}>
      <ScrollView
        ref={scroll}
        style={styles.fill}
        contentContainerStyle={styles.content}
        contentInsetAdjustmentBehavior="automatic"
        keyboardShouldPersistTaps="handled"
        onContentSizeChange={() => scroll.current?.scrollToEnd({ animated: false })}>
        <Txt variant="secondary" tone="muted">
          {ASSISTANT_INTRO}
        </Txt>
        {turns.length === 0 ? (
          <View style={styles.block}>
            <Txt variant="secondary" tone="muted">
              {examples.length ? 'Try one of these, or ask your own question.' : 'Loading example questions. You can ask your own now.'}
            </Txt>
            {examples.map((example) => (
              <Pressable
                key={example}
                accessibilityRole="button"
                accessibilityLabel={`Ask: ${example}`}
                onPress={() => ask(example)}
                style={({ pressed }) => [styles.example, { borderColor: theme.border, backgroundColor: pressed ? theme.raised : theme.surface }]}>
                <Txt variant="secondary">{example}</Txt>
              </Pressable>
            ))}
          </View>
        ) : null}
        {turns.map((turn) => (
          <View key={turn.id} style={styles.block}>
            <View style={[styles.question, { backgroundColor: theme.raised }]}>
              <Txt accessibilityLabel={`You asked: ${turn.question}`}>{turn.question}</Txt>
            </View>
            {turn.error ? (
              <View
                accessible
                accessibilityRole="alert"
                accessibilityLiveRegion="assertive"
                style={[styles.answer, { borderColor: theme.error, backgroundColor: theme.errorSoft }]}>
                <Txt variant="secondary">{turn.error}</Txt>
              </View>
            ) : turn.reply ? (
              <AssistantAnswer reply={turn.reply} now={now} onOpen={open} />
            ) : (
              <View accessible accessibilityLiveRegion="polite" style={[styles.pending, { backgroundColor: theme.raised }]}>
                <Txt variant="secondary" tone="muted">
                  Looking that up
                </Txt>
              </View>
            )}
          </View>
        ))}
      </ScrollView>
      <View style={[styles.composer, { borderTopColor: theme.border, backgroundColor: theme.surface }]}>
        <TextInput
          accessibilityLabel="Ask OddVex AI"
          value={input}
          onChangeText={setInput}
          maxLength={500}
          placeholder="Ask about a price, a player or your bets"
          placeholderTextColor={theme.muted}
          returnKeyType="send"
          onSubmitEditing={() => ask(input)}
          style={[styles.input, { color: theme.text, backgroundColor: theme.bg, borderColor: theme.borderStrong }]}
        />
        <Button label="Ask" compact disabled={busy || !input.trim()} accessibilityLabel="Send question" onPress={() => ask(input)} />
      </View>
    </KeyboardAvoidingView>
  );

  // On iOS the tab bar floats over the screen and only the scroll view is inset for it, so the composer needs
  // the bottom safe area itself. On Android the tab screen is already inset above the tab bar.
  const frame = [styles.fill, { backgroundColor: theme.bg }];
  return Platform.OS === 'ios' ? (
    <SafeAreaView edges={{ bottom: true }} style={frame}>
      {body}
    </SafeAreaView>
  ) : (
    <View style={frame}>{body}</View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  content: { padding: space[4], gap: space[4] },
  block: { gap: space[3] },
  example: { minHeight: touchTarget, justifyContent: 'center', paddingHorizontal: space[4], paddingVertical: space[2], borderRadius: radius.panel, borderWidth: 1 },
  question: { alignSelf: 'flex-end', maxWidth: '85%', paddingHorizontal: space[4], paddingVertical: space[3], borderRadius: radius.panel },
  answer: { alignSelf: 'flex-start', maxWidth: '94%', gap: space[3], padding: space[4], borderRadius: radius.panel, borderWidth: 1 },
  answerText: { lineHeight: 23 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  footnotes: { gap: space[1], borderTopWidth: StyleSheet.hairlineWidth, paddingTop: space[2] },
  pending: { alignSelf: 'flex-start', paddingHorizontal: space[4], paddingVertical: space[3], borderRadius: radius.panel },
  composer: { flexDirection: 'row', alignItems: 'center', gap: space[2], padding: space[3], borderTopWidth: StyleSheet.hairlineWidth },
  input: { flex: 1, minHeight: touchTarget, borderWidth: 1, borderRadius: radius.cell, paddingHorizontal: space[3], fontSize: fontSize.body },
});
