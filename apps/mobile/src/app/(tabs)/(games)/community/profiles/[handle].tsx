import { useLocalSearchParams } from 'expo-router';

import { CommunityProfileScreen } from '@/screens/community-profile';

export default function CommunityProfileRoute() {
  const { handle } = useLocalSearchParams<{ handle: string }>();
  return <CommunityProfileScreen handle={handle} />;
}
