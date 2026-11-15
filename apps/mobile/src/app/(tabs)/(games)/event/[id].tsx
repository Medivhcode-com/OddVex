import { useLocalSearchParams } from 'expo-router';

import { GameDetailScreen } from '@/screens/game-detail';

export default function GameDetailRoute() {
  const { id, market } = useLocalSearchParams<{ id: string; market?: string }>();
  return <GameDetailScreen eventId={id} initialMarket={market} />;
}
