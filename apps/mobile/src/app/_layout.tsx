import { IBMPlexMono_400Regular } from '@expo-google-fonts/ibm-plex-mono/400Regular';
import { IBMPlexMono_500Medium } from '@expo-google-fonts/ibm-plex-mono/500Medium';
import { IBMPlexMono_600SemiBold } from '@expo-google-fonts/ibm-plex-mono/600SemiBold';
import { useFonts } from 'expo-font';
import { DarkTheme, DefaultTheme, ThemeProvider } from 'expo-router';
import { NativeTabs } from 'expo-router/native-tabs';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { useColorScheme } from 'react-native';

import { useTheme } from '@/hooks/use-theme';
import { MonoFontContext } from '@/providers/fonts';
import { MetaProvider } from '@/providers/meta';
import { OddsFormatProvider } from '@/providers/odds-format';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const theme = useTheme();
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
            <NativeTabs
              backgroundColor={theme.surface}
              tintColor={theme.accent}
              iconColor={{ default: theme.muted, selected: theme.accent }}
              indicatorColor={theme.raised}
              labelStyle={{ default: { color: theme.muted }, selected: { color: theme.text } }}>
              <NativeTabs.Trigger name="(games)">
                <NativeTabs.Trigger.Label>Games</NativeTabs.Trigger.Label>
                <NativeTabs.Trigger.Icon sf="sportscourt" md="scoreboard" />
              </NativeTabs.Trigger>
              <NativeTabs.Trigger name="(settings)">
                <NativeTabs.Trigger.Label>Settings</NativeTabs.Trigger.Label>
                <NativeTabs.Trigger.Icon sf="gearshape" md="settings" />
              </NativeTabs.Trigger>
            </NativeTabs>
          </OddsFormatProvider>
        </MetaProvider>
      </MonoFontContext>
    </ThemeProvider>
  );
}
