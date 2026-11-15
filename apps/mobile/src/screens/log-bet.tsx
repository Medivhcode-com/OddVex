import { getLeagues, getSportsbooks } from '@/api/client';
import { BetForm } from '@/components/bet-form';
import { Screen } from '@/components/screen';
import { Button, EmptyState, ErrorState, Panel, SkeletonCards } from '@/components/states';
import { Txt } from '@/components/text';
import { useResource } from '@/hooks/use-resource';
import { openLogin, useSession } from '@/providers/session';

/** The log-a-bet form on its own screen, so the keyboard has room. */
export function LogBetScreen() {
  const session = useSession();
  const leagues = useResource('leagues', getLeagues);
  const books = useResource('sportsbooks', getSportsbooks);

  if (!session.user) {
    return (
      <Screen>
        <EmptyState title="Log in to track your bets" body="Bets are saved to your account, so you need to be logged in to add one.">
          <Button label="Log in" onPress={openLogin} />
        </EmptyState>
      </Screen>
    );
  }

  const retry = () => {
    leagues.reload();
    books.reload();
  };

  return (
    <Screen>
      <Txt variant="secondary" tone="muted">
        OddVex records the bet. It does not place it. Enter odds as American (−110), decimal (1.91) or fractional (10/11).
      </Txt>
      {leagues.status === 'loading' || books.status === 'loading' ? (
        <SkeletonCards label="Loading the form" count={2} />
      ) : leagues.status === 'error' || books.status === 'error' ? (
        <ErrorState error={leagues.error ?? books.error} onRetry={retry} />
      ) : (
        <Panel>
          <BetForm
            leagues={leagues.data ?? []}
            sportsbooks={(books.data ?? []).map((book) => book.name)}
            onSaved={() => session.changed('bets')}
          />
        </Panel>
      )}
    </Screen>
  );
}
