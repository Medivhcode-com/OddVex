import { useLocalSearchParams } from 'expo-router';

import { GameDetailScreen } from '@/screens/game-detail';

export default function GameDetailRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <GameDetailScreen eventId={id} />;
}
