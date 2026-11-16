import { IBMPlexMono_400Regular } from '@expo-google-fonts/ibm-plex-mono/400Regular';
import { IBMPlexMono_500Medium } from '@expo-google-fonts/ibm-plex-mono/500Medium';
import { IBMPlexMono_600SemiBold } from '@expo-google-fonts/ibm-plex-mono/600SemiBold';
import { useFonts } from 'expo-font';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { useColorScheme } from 'react-native';

import { useTheme } from '@/hooks/use-theme';
import { MonoFontContext } from '@/providers/fonts';
import { FlagsProvider } from '@/providers/flags';
import { MetaProvider } from '@/providers/meta';
import { OddsFormatProvider } from '@/providers/odds-format';
import { SessionProvider } from '@/providers/session';
import { useStackOptions } from '@/hooks/use-stack-options';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const theme = useTheme();
  const stackOptions = useStackOptions();
  const light = useColorScheme() === 'light';
  const [fontsLoaded, fontError] = useFonts({ IBMPlexMono_400Regular, IBMPlexMono_500Medium, IBMPlexMono_600SemiBold });
  const fontsSettled = fontsLoaded || fontError !== null;

  useEffect(() => {
    if (fontsSettled) SplashScreen.hideAsync();
  }, [fontsSettled]);

  if (!fontsSettled) return null;

  const base = light ? DefaultTheme : DarkTheme;
  const navigationTheme = {
    ...base,
    colors: {
      ...base.colors,
      primary: theme.accent,
      background: theme.bg,
      card: theme.bg,
      text: theme.text,
      border: theme.border,
      notification: theme.accent,
    },
  };

  return (
    <ThemeProvider value={navigationTheme}>
      <MonoFontContext value={fontsLoaded}>
        <MetaProvider>
          <OddsFormatProvider>
            <StatusBar style={light ? 'dark' : 'light'} />
            <SessionProvider>
              {/* Log in and sign up sit above the tabs as modals, so they can open from any screen and close back to it. */}
              <FlagsProvider>
                <Stack screenOptions={stackOptions}>
                  <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
                  <Stack.Screen name="login" options={{ title: 'Log in', presentation: 'modal' }} />
                  <Stack.Screen name="signup" options={{ title: 'Create account', presentation: 'modal' }} />
                  <Stack.Screen name="forgot-password" options={{ title: 'Reset your password', presentation: 'modal' }} />
                  {/* Opened by a link (oddvex://verify-email?token=..., oddvex://reset-password?token=...). */}
                  <Stack.Screen name="verify-email" options={{ title: 'Confirm your email address', presentation: 'modal' }} />
                  <Stack.Screen name="reset-password" options={{ title: 'Set a new password', presentation: 'modal' }} />
                </Stack>
              </FlagsProvider>
            </SessionProvider>
          </OddsFormatProvider>
        </MetaProvider>
      </MonoFontContext>
    </ThemeProvider>
  );
}
