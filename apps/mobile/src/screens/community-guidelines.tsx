import { CommunityGate } from '@/components/community-gate';
import { Guidelines } from '@/components/guidelines';
import { Screen } from '@/components/screen';

/** The community rules on their own screen. No sign-in needed, but still behind the `community` flag. */
export function CommunityGuidelinesScreen() {
  return (
    <CommunityGate account={false}>
      {() => (
        <Screen>
          <Guidelines />
        </Screen>
      )}
    </CommunityGate>
  );
}
