import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { likeCommunityPick, unlikeCommunityPick } from '@/api/client';
import type { CommunityPick } from '@/api/types';
import { Badge } from '@/components/badge';
import { communityError, countText, pickStatusLabel } from '@/components/community-copy';
import { Notice, Panel } from '@/components/states';
import { Txt } from '@/components/text';
import { useTheme } from '@/hooks/use-theme';
import { useOddsFormat } from '@/providers/odds-format';
import { radius, space, touchTarget } from '@/theme';
import { formatAge, formatPrice, formatStart } from '@/utils/format';

/** The status as a badge. The word is always there; the tone and the mark only repeat it. */
export function PickStatusBadge({ pick }: { pick: CommunityPick }) {
  const label = pickStatusLabel(pick);
  if (label === 'Won') return <Badge label={label} tone="accent" mark="dot" />;
  if (label === 'Lost') return <Badge label={label} tone="error" mark="diamond" />;
  return <Badge label={label} />;
}

/**
 * Like / Liked with the count. The word and the heart change as well as the selected state. The API's
 * answer (`liked_by_me`, `like_count`) replaces what is shown; nothing is counted here.
 */
export function LikeButton({ pick, onChange }: { pick: CommunityPick; onChange: (pick: CommunityPick) => void }) {
  const theme = useTheme();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const liked = pick.liked_by_me;
  const count = countText(pick.like_count, 'like', 'likes');

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      const state = liked ? await unlikeCommunityPick(pick.id) : await likeCommunityPick(pick.id);
      onChange({ ...pick, liked_by_me: state.liked_by_me, like_count: state.like_count });
    } catch (caught) {
      setError(communityError(caught, liked ? 'Your like was not removed. Try again.' : 'Your like was not saved. Try again.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.like}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${liked ? 'Liked' : 'Like'}, ${count}`}
        accessibilityHint={liked ? 'Removes your like' : 'Likes this pick'}
        accessibilityState={{ selected: liked, disabled: busy, busy }}
        disabled={busy}
        onPress={toggle}
        style={({ pressed }) => [
          styles.likeButton,
          { borderColor: liked ? theme.accent : theme.border, backgroundColor: liked ? theme.accentSoft : 'transparent' },
          pressed && { backgroundColor: theme.raised },
          busy && styles.busy,
        ]}>
        <Txt variant="secondary" tone={liked ? 'accent' : 'muted'} accessibilityElementsHidden importantForAccessibility="no">
          {liked ? '♥' : '♡'}
        </Txt>
        <Txt variant="secondary" weight="medium" tone={liked ? 'text' : 'muted'}>
          {liked ? 'Liked' : 'Like'} · {pick.like_count}
        </Txt>
      </Pressable>
      {error ? (
        <Txt variant="caption" tone="error" accessibilityRole="alert" accessibilityLiveRegion="assertive">
          {error}
        </Txt>
      ) : null}
    </View>
  );
}

/**
 * One pick. Everything a person wrote (the handle, the analysis) is drawn as plain text: no markup is
 * interpreted and nothing is turned into a link. The game, the selection, the price and the sportsbook are
 * the API's words and numbers. With `link`, the body and the comment count open the pick's own screen.
 */
export function PickCard({ pick, now, onChange, link = true }: { pick: CommunityPick; now: Date; onChange: (pick: CommunityPick) => void; link?: boolean }) {
  const router = useRouter();
  const { format } = useOddsFormat();
  const status = pickStatusLabel(pick);
  const price = `Price when posted: ${formatPrice(pick.price, format)} at ${pick.sportsbook.name}`;
  const comments = countText(pick.comment_count, 'comment', 'comments');
  const open = () => router.push({ pathname: '/community/picks/[id]', params: { id: pick.id } });

  const body = (
    <>
      <View style={styles.game}>
        <Txt variant="caption" tone="muted">
          {pick.event_label} · {formatStart(pick.event_start_time)}
        </Txt>
        <Txt weight="semibold">{pick.selection}</Txt>
      </View>
      <Txt variant="secondary" tone="muted">
        {price}
      </Txt>
      {pick.analysis ? <Txt variant="secondary">{pick.analysis}</Txt> : null}
    </>
  );

  return (
    <Panel>
      <View style={styles.card}>
        <View style={styles.head}>
          <Pressable
            accessibilityRole="link"
            accessibilityLabel={`Profile of ${pick.author.handle}`}
            onPress={() => router.push({ pathname: '/community/profiles/[handle]', params: { handle: pick.author.handle } })}
            style={({ pressed }) => [styles.author, pressed && styles.pressed]}>
            <Txt variant="secondary" weight="semibold">
              @{pick.author.handle}
            </Txt>
          </Pressable>
          <PickStatusBadge pick={pick} />
        </View>
        {link ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${pick.event_label}. ${pick.selection}. ${price}. ${status}.`}
            accessibilityHint="Opens this pick and its comments"
            onPress={open}
            style={({ pressed }) => [styles.body, pressed && styles.pressed]}>
            {body}
          </Pressable>
        ) : (
          <View style={styles.body}>{body}</View>
        )}
        {pick.moderation_status !== 'visible' ? (
          <Notice tone="neutral" title="Hidden by moderators" text={pick.moderation_note ?? 'Other people can no longer see this pick. It still counts in your record.'} />
        ) : null}
        <Txt variant="caption" tone="muted">
          Posted {formatAge(pick.posted_at, now)}
        </Txt>
        <View style={styles.foot}>
          <LikeButton pick={pick} onChange={onChange} />
          {link ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={comments}
              accessibilityHint="Opens this pick and its comments"
              onPress={open}
              style={({ pressed }) => [styles.comments, pressed && styles.pressed]}>
              <Txt variant="secondary" tone="muted">
                {comments}
              </Txt>
            </Pressable>
          ) : (
            <View style={styles.comments}>
              <Txt variant="secondary" tone="muted">
                {comments}
              </Txt>
            </View>
          )}
        </View>
      </View>
    </Panel>
  );
}

const styles = StyleSheet.create({
  card: { gap: space[3] },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[3] },
  author: { minHeight: touchTarget, minWidth: touchTarget, justifyContent: 'center', flexShrink: 1 },
  body: { gap: space[2], minHeight: touchTarget },
  game: { gap: 2 },
  foot: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-start', gap: space[3] },
  like: { alignItems: 'flex-start', gap: space[1] },
  likeButton: {
    minHeight: touchTarget,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[2],
    paddingHorizontal: space[3],
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  comments: { minHeight: touchTarget, minWidth: touchTarget, justifyContent: 'center' },
  pressed: { opacity: 0.7 },
  busy: { opacity: 0.6 },
});
