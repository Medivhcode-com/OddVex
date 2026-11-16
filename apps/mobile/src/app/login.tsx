import { useLocalSearchParams } from 'expo-router';

import { LoginScreen } from '@/screens/auth';

export default function LoginRoute() {
  const { reset } = useLocalSearchParams<{ reset?: string }>();
  return <LoginScreen passwordReset={reset === 'done'} />;
}
