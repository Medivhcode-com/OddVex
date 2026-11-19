import { Linking, StyleSheet, View } from 'react-native';

import { Button } from '@/components/states';
import { Txt } from '@/components/text';
import { HELPLINE, RESPONSIBLE_GAMBLING_LINE } from '@/helpline';
import { space } from '@/theme';

/**
 * Hands a `tel:` or web address to the phone. A device with no dialer (a tablet, a simulator) rejects it;
 * nothing more is done then, because the number is always written out next to the link.
 */
function open(url: string): void {
  Linking.openURL(url).catch(() => {});
}

/** The helpline as a phone link: opens the dialer with the number filled in. */
export function HelplineCall() {
  return (
    <Button
      label={`Call ${HELPLINE.number}`}
      variant="secondary"
      compact
      accessibilityRole="link"
      accessibilityLabel={`Call the ${HELPLINE.name}, ${HELPLINE.digits}`}
      accessibilityHint="Opens the phone with the number filled in."
      onPress={() => open(HELPLINE.tel)}
    />
  );
}

/** 988 as a phone link, for the sentence that says the helpline is not an emergency service. */
export function CrisisCall() {
  return (
    <Button
      label={`Call ${HELPLINE.crisisNumber}`}
      variant="ghost"
      compact
      accessibilityRole="link"
      accessibilityLabel={`Call ${HELPLINE.crisisNumber}, the ${HELPLINE.crisisName}`}
      accessibilityHint="Opens the phone with the number filled in."
      onPress={() => open(HELPLINE.crisisTel)}
    />
  );
}

/** The Council's website, where online chat is offered. */
export function CouncilSite() {
  return (
    <Button
      label={HELPLINE.siteLabel}
      variant="ghost"
      compact
      accessibilityRole="link"
      accessibilityLabel={`Open the ${HELPLINE.council} website`}
      onPress={() => open(HELPLINE.site)}
    />
  );
}

/**
 * The short responsible-gambling line with the helpline as a phone link under it. On the tracker, in the
 * sportsbook sync panel and wherever else a screen should keep help one tap away.
 */
export function HelpLine() {
  return (
    <View style={styles.line}>
      <Txt variant="caption" tone="muted" selectable>
        {RESPONSIBLE_GAMBLING_LINE}
      </Txt>
      <HelplineCall />
    </View>
  );
}

const styles = StyleSheet.create({
  line: { gap: space[2] },
});
