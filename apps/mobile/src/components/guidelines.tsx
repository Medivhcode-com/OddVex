import { StyleSheet, View } from 'react-native';

import { getCommunityGuidelines } from '@/api/client';
import { Button, ErrorState, Panel, SkeletonCards } from '@/components/states';
import { Txt } from '@/components/text';
import { useResource } from '@/hooks/use-resource';
import { space } from '@/theme';

/**
 * The community rules exactly as `GET /v1/community/guidelines` words them. Nothing here is written in the
 * app, so the web, this app and the API's own checks cannot drift apart.
 */
export function Guidelines() {
  const guidelines = useResource('community-guidelines', getCommunityGuidelines);
  if (guidelines.status === 'loading') return <SkeletonCards label="Loading the community guidelines" count={1} />;
  if (!guidelines.data) return <ErrorState error={guidelines.error} onRetry={guidelines.reload} />;
  const { intro, rules, enforcement, help, version } = guidelines.data;
  return (
    <Panel>
      <View style={styles.block}>
        <Txt variant="heading" accessibilityRole="header">
          Community guidelines
        </Txt>
        <Txt variant="secondary">{intro}</Txt>
        {rules.map((rule, index) => (
          <View key={rule.key} style={styles.rule}>
            <Txt variant="secondary" weight="semibold">
              {index + 1}. {rule.title}
            </Txt>
            <Txt variant="secondary" tone="muted">
              {rule.text}
            </Txt>
          </View>
        ))}
        <Txt variant="secondary" tone="muted">
          {enforcement}
        </Txt>
        <Txt variant="secondary" selectable>
          {help}
        </Txt>
        <Txt variant="caption" tone="muted">
          Wording of {version}.
        </Txt>
        {guidelines.error !== undefined ? <Button label="Try again" variant="secondary" compact onPress={guidelines.reload} /> : null}
      </View>
    </Panel>
  );
}

const styles = StyleSheet.create({
  block: { gap: space[3] },
  rule: { gap: 2 },
});
