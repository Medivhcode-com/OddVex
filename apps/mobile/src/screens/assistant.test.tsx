import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';
import { Linking } from 'react-native';

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

// Word for word what the API sends for a distress message (services/api assistant/safeguards.py).
const distress: AssistantReply = {
  intent: 'support',
  answer: [
    "Thank you for telling me. I can't help size or pick a bet to win money back. Trying to win back losses is a recognised warning sign that betting may be causing harm, and it is worth talking to someone about. I'm leaving prices and other betting data out of this reply.",
    'The National Problem Gambling Helpline is confidential and answers 24 hours a day, every day: call 1-800-MY-RESET (1-800-697-3738) or text 800GAM (800426).',
    'OddVex has two tools you can use on your own. The weekly staking reminder in Settings tells you when your stakes for the week reach an amount you choose; it is a reminder, not a limit. The bet tracker shows what you have staked and how your bets settled.',
    'The helpline is not an emergency service. In a crisis, call or text 988 (the Suicide and Crisis Lifeline) or call 911.',
  ].join('\n\n'),
  data: null,
  disclaimer: 'OddVex gives information and math, not betting advice or predictions. All sports data shown is synthetic sample data.',
  sources: [],
  suggestions: [
    { label: 'Help and support resources', href: '/responsible-gambling' },
    { label: 'Weekly staking reminder', href: '/app/settings' },
    { label: 'Bet tracker', href: '/app/tracker' },
  ],
  support: { case: 'distress' },
};

const crisis: AssistantReply = {
  ...distress,
  answer: [
    "I'm sorry you are going through this. You don't have to face it alone, and help is available right now.",
    'Call or text 988 (the Suicide and Crisis Lifeline). If you are in immediate danger, call 911.',
    'If you can, tell someone you trust how you are feeling now.',
  ].join('\n\n'),
  suggestions: [{ label: 'Help and support resources', href: '/responsible-gambling' }],
  support: { case: 'crisis' },
};

describe('AssistantAnswer for a support reply', () => {
  beforeEach(() => jest.mocked(Linking.openURL).mockReset().mockResolvedValue(undefined));

  it('shows the reply with tappable helpline numbers and no sources or data panel', async () => {
    await render(<AssistantAnswer reply={distress} now={now} onOpen={() => {}} />);

    expect(screen.getByText(distress.answer)).toBeOnTheScreen();
    expect(screen.queryByText('No data was used for this answer.')).toBeNull();
    expect(screen.queryByText(/^Sources:/)).toBeNull();
    expect(screen.queryByText(distress.disclaimer)).toBeNull();

    await fireEvent.press(screen.getByRole('link', { name: 'Call the National Problem Gambling Helpline, 1-800-697-3738' }));
    await fireEvent.press(screen.getByRole('link', { name: 'Text the National Problem Gambling Helpline at 800GAM, 800426' }));
    await fireEvent.press(screen.getByRole('link', { name: 'Call 988, the Suicide and Crisis Lifeline' }));
    expect(jest.mocked(Linking.openURL).mock.calls).toEqual([['tel:+18006973738'], ['sms:800426'], ['tel:988']]);
  });

  it('opens the in-app help, the staking reminder and the tracker from the links in the reply', async () => {
    const onOpen = jest.fn();
    await render(<AssistantAnswer reply={distress} now={now} onOpen={onOpen} />);

    await fireEvent.press(screen.getByRole('button', { name: 'Help and support resources' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Weekly staking reminder' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Bet tracker' }));

    expect(onOpen.mock.calls).toEqual([['/settings'], ['/settings'], ['/tracker']]);
  });

  it('puts 988, its text line and 911 first for a crisis reply', async () => {
    await render(<AssistantAnswer reply={crisis} now={now} onOpen={() => {}} />);

    const links = screen.getAllByRole('link').map((link) => link.props.accessibilityLabel);
    expect(links.slice(0, 3)).toEqual(['Call 988, the Suicide and Crisis Lifeline', 'Text 988, the Suicide and Crisis Lifeline', 'Call 911']);
    await fireEvent.press(screen.getByRole('link', { name: 'Text 988, the Suicide and Crisis Lifeline' }));
    await fireEvent.press(screen.getByRole('link', { name: 'Call 911' }));
    expect(jest.mocked(Linking.openURL).mock.calls).toEqual([['sms:988'], ['tel:911']]);
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

  it('shows a support reply as a support card', async () => {
    const { fetchMock } = installFetch();
    respond(fetchMock, () => jsonResponse(distress));
    await render(<AssistantScreen />);

    await fireEvent.changeText(screen.getByLabelText('Ask OddVex AI'), 'I need to win it back tonight');
    await fireEvent.press(screen.getByRole('button', { name: 'Send question' }));

    expect(await screen.findByText('Help is available')).toBeOnTheScreen();
    expect(screen.getByText(distress.answer)).toBeOnTheScreen();
    expect(screen.queryByText('No data was used for this answer.')).toBeNull();
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
