export const SITE = {
  name: "OddVex",
  url: process.env.NEXT_PUBLIC_SITE_URL ?? "https://oddvex.com",
  tagline: "Every line. A smarter perspective.",
  description:
    "Compare odds across sportsbooks, research player props, measure expected value and track every bet. OddVex is research and analytics only. It never takes wagers.",
  company: "Medivh Code",
  helpline: "1-800-GAMBLER",
} as const;

export const MARKETING_NAV = [
  { href: "/odds-comparison", label: "Odds" },
  { href: "/player-props", label: "Props" },
  { href: "/bet-tracking", label: "Tracker" },
  { href: "/ai", label: "OddVex AI" },
  { href: "/pricing", label: "Pricing" },
] as const;

/** `flag` names a feature flag (`GET /v1/flags`); the entry is hidden while that flag is off. */
export type AppNavItem = { href: string; label: string; icon: string; flag?: string };

export const APP_NAV: readonly AppNavItem[] = [
  { href: "/app", label: "Home", icon: "home" },
  { href: "/app/games", label: "Games", icon: "games" },
  { href: "/app/odds", label: "Odds", icon: "odds" },
  { href: "/app/value", label: "Value", icon: "value", flag: "value_screen" },
  { href: "/app/props", label: "Props", icon: "props" },
  { href: "/app/tracker", label: "Tracker", icon: "tracker" },
  { href: "/app/alerts", label: "Alerts", icon: "alerts" },
  { href: "/app/community", label: "Community", icon: "community", flag: "community" },
  { href: "/app/tools", label: "Calculators", icon: "tools" },
  { href: "/app/parlay", label: "Parlay", icon: "parlay" },
  { href: "/app/assistant", label: "OddVex AI", icon: "ai" },
];

/**
 * App pages that exist only while a feature flag is on. The proxy and the pages both check.
 * `prefix` covers every path underneath as well. A path can match several entries; all of
 * their flags must be on (the leaderboard needs `community` and `community_leaderboard`).
 */
export type FlaggedPath = { path: string; flag: string; prefix?: boolean };

export const FLAGGED_PATHS: readonly FlaggedPath[] = [
  { path: "/app/value", flag: "value_screen" },
  { path: "/app/tracker/analytics", flag: "tracker_analytics" },
  { path: "/app/community", flag: "community", prefix: true },
  { path: "/app/community/leaderboard", flag: "community_leaderboard", prefix: true },
  { path: "/app/admin/community", flag: "community", prefix: true },
];

/** The flags a path needs, without duplicates. Empty for a page that is always there. */
export function flagsForPath(pathname: string): string[] {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const flags = FLAGGED_PATHS.filter((entry) => entry.path === path || (entry.prefix === true && path.startsWith(`${entry.path}/`))).map((entry) => entry.flag);
  return [...new Set(flags)];
}
