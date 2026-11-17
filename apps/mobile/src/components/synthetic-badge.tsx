import { Badge } from '@/components/badge';
import { isReplay, isSynthetic, useMeta } from '@/providers/meta';

/**
 * Shown in every header while the API reports `data_mode: "synthetic"` or `"replay"`.
 * Renders nothing otherwise.
 */
export function SyntheticBadge() {
  const meta = useMeta();
  if (isReplay(meta.data)) {
    return (
      <Badge
        label="Replay"
        tone="warn"
        mark="diamond"
        accessible
        accessibilityLabel="Replay of past games. Sportsbooks and prices are simulated."
      />
    );
  }
  if (!isSynthetic(meta.data)) return null;
  return (
    <Badge
      label="Synthetic data"
      tone="warn"
      mark="diamond"
      accessible
      accessibilityLabel="Synthetic data. Teams, players and sportsbooks are fictional."
    />
  );
}
