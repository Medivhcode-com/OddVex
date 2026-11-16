import type { Href } from 'expo-router';

/**
 * Turns a web route the API sends (assistant suggestions, notification links) into the matching screen in
 * this app, or null when there is none. `/app/games/{id}` is the game (opened on its `market` when the link
 * names one), `/app/props/{id}` the prop analyzer (with its `market`), and the section roots go to their
 * tabs. The odds board on the web is the Games tab here.
 */
export function appRoute(href: string): Href | null {
  const [path, query = ''] = href.split('#')[0].split('?');
  const rawMarket = query
    .split('&')
    .map((pair) => pair.split('='))
    .find(([key]) => key === 'market')?.[1];
  const market = rawMarket ? decodeURIComponent(rawMarket) : undefined;
  const parts = path.replace(/\/+$/, '').split('/').filter(Boolean);
  if (parts[0] !== 'app') return null;
  const [, section, rawId] = parts;
  const id = rawId ? decodeURIComponent(rawId) : undefined;
  if (section === undefined) return '/';
  if (section === 'games' || section === 'odds') {
    if (!id) return '/';
    return { pathname: '/event/[id]', params: market ? { id, market } : { id } };
  }
  if (section === 'props') {
    if (!id) return '/props';
    return { pathname: '/player/[id]', params: market ? { id, market } : { id } };
  }
  if (section === 'tools') return '/tools';
  if (section === 'parlay') return '/parlay';
  if (section === 'tracker') return '/tracker';
  if (section === 'settings') return '/settings';
  if (section === 'assistant') return '/assistant';
  if (section === 'notifications') return '/notifications';
  if (section === 'alerts') return { pathname: '/notifications', params: { tab: 'alerts' } };
  return null;
}
