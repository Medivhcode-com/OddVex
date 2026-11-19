import { Badge } from '@/components/badge';
import { isReplay, isSynthetic, useMeta } from '@/providers/meta';

/**
 * The data-mode badge in every header. While the API reports `data_mode: "synthetic"` or `"replay"` it says
 * so. While the mode is not known (the read of `GET /v1/meta` is still in flight, failed and is being
 * retried, or came back without a data mode in it) it says the data source is not confirmed: an unknown mode
 * never draws nothing, and is never taken to mean real data. It draws nothing only once the API has named
 * another mode. The API has no such mode today; when it gets one, list here the modes that need no label.
 */
export function SyntheticBadge() {
  const meta = useMeta();
  // The type says the mode is always there. What arrived is checked anyway: an answer without one is not a known mode.
  const mode: unknown = meta.data?.data_mode;
  if (typeof mode !== 'string' || mode === '') {
    return (
      <Badge
        label="Data source not confirmed"
        accessible
        accessibilityLabel="Data source not confirmed. OddVex has not yet confirmed whether this data is synthetic."
      />
    );
  }
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
