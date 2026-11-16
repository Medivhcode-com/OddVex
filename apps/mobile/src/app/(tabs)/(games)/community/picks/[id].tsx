import { useLocalSearchParams } from 'expo-router';

import { CommunityPickScreen } from '@/screens/community-pick';

export default function CommunityPickRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <CommunityPickScreen pickId={id} />;
}
