import { useLocalSearchParams } from 'expo-router';

import { PropAnalyzerScreen } from '@/screens/prop-analyzer';

export default function PlayerRoute() {
  const { id, market } = useLocalSearchParams<{ id: string; market?: string }>();
  // Keyed by player so the stat, window and split choices start fresh for each one.
  return <PropAnalyzerScreen key={id} playerId={id} initialMarket={market || undefined} />;
}
