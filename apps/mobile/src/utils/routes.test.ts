import { appRoute } from '@/utils/routes';

describe('appRoute', () => {
  it('opens the pick and the profile a community notification links to', () => {
    expect(appRoute('/app/community/picks/e627490a99064c93a138e8544e8d77a5')).toEqual({
      pathname: '/community/picks/[id]',
      params: { id: 'e627490a99064c93a138e8544e8d77a5' },
    });
    expect(appRoute('/app/community/profiles/fictional_fox')).toEqual({ pathname: '/community/profiles/[handle]', params: { handle: 'fictional_fox' } });
  });

  it('maps the rest of the community section', () => {
    expect(appRoute('/app/community')).toBe('/community');
    expect(appRoute('/app/community/')).toBe('/community');
    expect(appRoute('/app/community/leaderboard')).toBe('/community/leaderboard');
    expect(appRoute('/app/community/guidelines')).toBe('/community/guidelines');
    // A list with no id, or a page this app does not have, lands on the community's first screen.
    expect(appRoute('/app/community/picks')).toBe('/community');
    expect(appRoute('/app/community/moderation')).toBe('/community');
  });

  it('opens the in-app help in Settings for the responsible-gambling page the support replies link to', () => {
    expect(appRoute('/responsible-gambling')).toBe('/settings');
    expect(appRoute('/responsible-gambling/')).toBe('/settings');
    expect(appRoute('/responsible-gambling#helpline')).toBe('/settings');
  });

  it('still maps the earlier links', () => {
    expect(appRoute('/app/games/evt_2?market=spread')).toEqual({ pathname: '/event/[id]', params: { id: 'evt_2', market: 'spread' } });
    expect(appRoute('/app/props/pl_1')).toEqual({ pathname: '/player/[id]', params: { id: 'pl_1' } });
    expect(appRoute('/app/alerts')).toEqual({ pathname: '/notifications', params: { tab: 'alerts' } });
    expect(appRoute('/app/tracker')).toBe('/tracker');
    expect(appRoute('/pricing')).toBeNull();
    expect(appRoute('/app/admin')).toBeNull();
  });
});
