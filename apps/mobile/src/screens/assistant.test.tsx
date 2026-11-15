import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import type { AssistantReply } from '@/api/types';
import { AssistantAnswer, AssistantScreen, examplePrompts, sourcesText, suggestionRoute } from '@/screens/assistant';
import { errorResponse, installFetch, jsonResponse } from '@/test/api';
import { liveEvent, now, propAnalysis } from '@/test/fixtures';

const reply: AssistantReply = {
  intent: 'compare_odds',
  answer: 'Best moneyline price for Iron Valley Forge is +118 at Northstar Sports.',
  disclaimer: 'For information only. OddVex does not predict outcomes or take bets.',
  sources: [
    { label: 'Odds board', data_mode: 'synthetic', as_of: '2026-11-15T19:59:18Z' },
    { label: 'Quant engine', data_mode: 'synthetic', as_of: '2026-11-15T19:54:00Z' },
  ],
  suggestions: [
    { label: 'Open this game', href: '/app/games/evt_1' },
    { label: 'Open the calculators', href: '/app/tools' },
    { label: 'Read the methodology', href: '/methodology' },
  ],
};

describe('suggestionRoute', () => {
  it.each([
    ['/app/games/evt_1', { pathname: '/event/[id]', params: { id: 'evt_1' } }],
    ['/app/games/evt_1?market=spread', { pathname: '/event/[id]', params: { id: 'evt_1', market: 'spread' } }],
    ['/app/notifications', '/notifications'],
    ['/app/alerts', { pathname: '/notifications', params: { tab: 'alerts' } }],
    ['/app/games', '/'],
    ['/app/odds', '/'],
    ['/app', '/'],
    ['/app/props/plr_1', { pathname: '/player/[id]', params: { id: 'plr_1' } }],
    ['/app/props/plr_1?market=points', { pathname: '/player/[id]', params: { id: 'plr_1', market: 'points' } }],
    ['/app/props', '/props'],
    ['/app/tools', '/tools'],
    ['/app/tools#ev', '/tools'],
    ['/app/parlay', '/parlay'],
    ['/app/tracker', '/tracker'],
    ['/app/settings', '/settings'],
  ])('maps %s', (href, route) => {
    expect(suggestionRoute(href)).toEqual(route);
  });

  it('has no screen for links outside the app', () => {
    expect(suggestionRoute('/methodology')).toBeNull();
    expect(suggestionRoute('https://example.test/app/tools')).toBeNull();
    expect(suggestionRoute('/app/unknown')).toBeNull();
  });
});

describe('sourcesText', () => {
  it('lists each source with its data mode and age', () => {
    expect(sourcesText(reply, now)).toBe(
      'Sources: Odds board (synthetic data, updated 42s ago); Quant engine (synthetic data, updated 6 min ago)',
    );
  });

  it('says so when no data was used', () => {
    expect(sourcesText({ sources: [] }, now)).toBe('No data was used for this answer.');
  });
});

describe('examplePrompts', () => {
  it('seeds the first two examples from current data', () => {
    const row = { player: propAnalysis.player, market: 'three_pointers' } as Parameters<typeof examplePrompts>[1][number];
    expect(examplePrompts([liveEvent], [row])).toEqual([
      'Who has the best price on the Harbor City Gulls?',
      'How has Corwin Ashdown done on three pointers lately?',
      'What is expected value?',
      'How do you remove the vig?',
      'How are my bets doing?',
    ]);
  });

  it('falls back to the general questions when nothing is loaded', () => {
    expect(examplePrompts([], [])).toEqual(['What is expected value?', 'How do you remove the vig?', 'How are my bets doing?']);
  });
});

describe('AssistantAnswer', () => {
  it('shows the answer, its sources and the disclaimer', async () => {
    await render(<AssistantAnswer reply={reply} now={now} onOpen={() => {}} />);

    expect(screen.getByText(reply.answer)).toBeOnTheScreen();
    expect(screen.getByText(/^Sources: Odds board \(synthetic data, updated 42s ago\); Quant engine/)).toBeOnTheScreen();
    expect(screen.getByText(reply.disclaimer)).toBeOnTheScreen();
  });

  it('keeps the disclaimer and says no data was used when there are no sources', async () => {
    await render(<AssistantAnswer reply={{ ...reply, sources: [], suggestions: [] }} now={now} onOpen={() => {}} />);

    expect(screen.getByText('No data was used for this answer.')).toBeOnTheScreen();
    expect(screen.getByText(reply.disclaimer)).toBeOnTheScreen();
  });

  it('opens the matching screen for a suggestion and drops links with no screen', async () => {
    const onOpen = jest.fn();
    await render(<AssistantAnswer reply={reply} now={now} onOpen={onOpen} />);

    expect(screen.queryByRole('button', { name: 'Read the methodology' })).toBeNull();
    await fireEvent.press(screen.getByRole('button', { name: 'Open this game' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Open the calculators' }));

    expect(onOpen.mock.calls).toEqual([[{ pathname: '/event/[id]', params: { id: 'evt_1' } }], ['/tools']]);
  });
});

describe('AssistantScreen', () => {
  function respond(fetchMock: jest.Mock, answer: () => unknown) {
    fetchMock.mockImplementation(async (url: string) => {
      if (url.includes('/v1/events')) return jsonResponse([liveEvent]);
      if (url.includes('/v1/props')) return jsonResponse([]);
      return answer();
    });
  }

  beforeEach(() => jest.mocked(router.push).mockClear());

  it('asks an example seeded from current data and shows the sourced answer', async () => {
    const { fetchMock, sent } = installFetch();
    respond(fetchMock, () => jsonResponse(reply));
    await render(<AssistantScreen />);

    await fireEvent.press(await screen.findByRole('button', { name: 'Ask: Who has the best price on the Harbor City Gulls?' }));

    expect(await screen.findByText(reply.answer)).toBeOnTheScreen();
    expect(screen.getByLabelText('You asked: Who has the best price on the Harbor City Gulls?')).toBeOnTheScreen();
    expect(screen.getByText(reply.disclaimer)).toBeOnTheScreen();
    const query = sent().find((request) => request.path === '/v1/assistant/query');
    expect(query).toMatchObject({ method: 'POST', body: { message: 'Who has the best price on the Harbor City Gulls?' } });

    await fireEvent.press(screen.getByRole('button', { name: 'Open this game' }));
    expect(router.push).toHaveBeenCalledWith({ pathname: '/event/[id]', params: { id: 'evt_1' } });
  });

  it('sends a typed question and explains a rate limit', async () => {
    const { fetchMock } = installFetch();
    respond(fetchMock, () => errorResponse(429, 'rate_limited', 'Rate limit exceeded'));
    await render(<AssistantScreen />);

    expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled();
    await fireEvent.changeText(screen.getByLabelText('Ask OddVex AI'), 'What is hold?');
    await fireEvent.press(screen.getByRole('button', { name: 'Send question' }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent("You've asked a lot of questions quickly. Wait a minute, then ask again."),
    );
    expect(screen.getByLabelText('Ask OddVex AI')).toHaveDisplayValue('');
  });
});
