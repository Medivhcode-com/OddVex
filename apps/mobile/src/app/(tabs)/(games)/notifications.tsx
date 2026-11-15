import { useLocalSearchParams } from 'expo-router';

import { NotificationsScreen } from '@/screens/notifications';

export default function NotificationsRoute() {
  const { tab } = useLocalSearchParams<{ tab?: string }>();
  return <NotificationsScreen initialTab={tab === 'alerts' ? 'alerts' : 'notifications'} />;
}
