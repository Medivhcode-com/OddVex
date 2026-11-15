import { NativeTabs } from 'expo-router/native-tabs';

import { useTheme } from '@/hooks/use-theme';

/** Five tabs, the most a thumb reaches comfortably. Each tab owns a stack. */
export default function TabsLayout() {
  const theme = useTheme();
  return (
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
      <NativeTabs.Trigger name="(props)">
        <NativeTabs.Trigger.Label>Props</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="person.text.rectangle" md="person_search" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="(tracker)">
        <NativeTabs.Trigger.Label>Tracker</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="list.bullet.clipboard" md="receipt_long" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="(tools)">
        <NativeTabs.Trigger.Label>Tools</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="function" md="calculate" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="(settings)">
        <NativeTabs.Trigger.Label>Settings</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="gearshape" md="settings" />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
