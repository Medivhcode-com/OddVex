import { Badge } from '@/components/badge';
import { isSynthetic, useMeta } from '@/providers/meta';

/** Shown in every header while the API reports `data_mode: "synthetic"`. Renders nothing otherwise. */
export function SyntheticBadge() {
  const meta = useMeta();
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
