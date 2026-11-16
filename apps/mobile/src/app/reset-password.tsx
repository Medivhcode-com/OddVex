import { useLocalSearchParams } from 'expo-router';

import { linkToken, ResetPasswordScreen } from '@/screens/email-flows';

export default function ResetPasswordRoute() {
  const { token } = useLocalSearchParams<{ token?: string | string[] }>();
  return <ResetPasswordScreen token={linkToken(token)} />;
}
