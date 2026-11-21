import { useRouter } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { PROFILE_HIDDEN_EXPLAINED } from '@/components/community-copy';
import { CommunityGate } from '@/components/community-gate';
import { Guidelines } from '@/components/guidelines';
import { ProfileForm } from '@/components/profile-form';
import { Screen } from '@/components/screen';
import { Button, ErrorState, Notice, Panel, PanelHeading, SkeletonCards } from '@/components/states';
import { Txt } from '@/components/text';
import { useMyProfile } from '@/hooks/use-community';
import { space } from '@/theme';

function EditProfile() {
  const router = useRouter();
  const profile = useMyProfile();
  if (profile.status === 'loading') {
    return (
      <Screen>
        <SkeletonCards label="Loading your profile" count={1} />
      </Screen>
    );
  }
  if (profile.data === undefined) {
    return (
      <Screen>
        <ErrorState error={profile.error} onRetry={profile.reload} />
      </Screen>
    );
  }
  const existing = profile.data;
  return (
    <Screen>
      {existing === null ? <Guidelines /> : null}
      {existing && existing.moderation_status !== 'visible' ? (
        <Notice tone="neutral" title="Moderators have hidden your profile" text={existing.moderation_note ?? undefined}>
          <Txt variant="secondary" tone="muted">
            {PROFILE_HIDDEN_EXPLAINED}
          </Txt>
        </Notice>
      ) : null}
      <Panel>
        <View style={styles.block}>
          <PanelHeading
            title={existing ? 'Edit your profile' : 'Create your profile'}
            description="The community is opt-in. You choose the handle, and whether other people can see the profile."
          />
          <ProfileForm existing={existing} />
        </View>
      </Panel>
      <View style={styles.links}>
        <Button label="Open the community" variant="secondary" compact onPress={() => router.navigate('/community')} />
        {existing ? <Button label="Guidelines" variant="ghost" compact accessibilityLabel="Community guidelines" onPress={() => router.push('/community/guidelines')} /> : null}
      </View>
    </Screen>
  );
}

/** Create or edit your own community profile. Reached from the feed, your profile and "Share a pick". */
export function CommunityProfileEditScreen() {
  return <CommunityGate>{(user) => (user ? <EditProfile /> : null)}</CommunityGate>;
}

const styles = StyleSheet.create({
  block: { gap: space[3] },
  links: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
});
