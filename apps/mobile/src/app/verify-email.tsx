import { useLocalSearchParams } from 'expo-router';

import { linkToken, VerifyEmailScreen } from '@/screens/email-flows';

export default function VerifyEmailRoute() {
  const { token } = useLocalSearchParams<{ token?: string | string[] }>();
  return <VerifyEmailScreen token={linkToken(token)} />;
}
