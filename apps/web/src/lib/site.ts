export const SITE = {
  name: "OddVex",
  url: process.env.NEXT_PUBLIC_SITE_URL ?? "https://oddvex.com",
  tagline: "Every line. A smarter perspective.",
  description:
    "Compare odds across sportsbooks, research player props, measure expected value and track every bet. OddVex is research and analytics only. It never takes wagers.",
  company: "Medivh Code",
} as const;

/**
 * The address for questions and data-rights requests (`NEXT_PUBLIC_CONTACT_EMAIL`, read when the
 * web app is built). Empty until one is set: pages then point to the contact page, which says
 * an address is being set up.
 */
export const CONTACT_EMAIL = (process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "").trim();

/**
 * Where to get help with problem gambling. The one place these facts are written: every page,
 * component, link and sentence that gives the helpline reads them from here.
 *
 * Checked on 2026-11-19 against the National Council on Problem Gambling's own pages:
 * - The National Problem Gambling Helpline is 1-800-MY-RESET (1-800-697-3738), in service since
 *   2026-01-29.
 * - It takes calls, and texts to 800GAM (800426). It is confidential and answers 24 hours a
 *   day, every day.
 * - It is not an emergency service. In a crisis the numbers are 988 (the Suicide and Crisis
 *   Lifeline, call or text) and 911.
 * - Online chat is offered on the Council's website. The site links to the front page only,
 *   because deeper addresses move.
 *
 * The number the site gave before is not the national helpline. It is named once, on the
 * responsible-gambling page, as the line of the state council that runs it.
 *
 * Check these again before each release and change `verifiedOn` when you do.
 */
export const HELPLINE = {
  name: "National Problem Gambling Helpline",
  /** The number as the Council writes it. */
  number: "1-800-MY-RESET",
  /** The same number in digits. */
  digits: "1-800-697-3738",
  /** Both spellings, as the number is shown wherever it appears. */
  display: "1-800-MY-RESET (1-800-697-3738)",
  tel: "tel:+18006973738",
  /** The text line, as letters and as the digits they stand for. */
  textTo: "800GAM",
  textDigits: "800426",
  sms: "sms:800426",
  /** The day the number came into service. */
  inServiceSince: "2026-01-29",
  inServiceSinceText: "January 29, 2026",
  council: "National Council on Problem Gambling",
  site: "https://www.ncpgambling.org",
  /** The address as shown on the link. */
  siteLabel: "ncpgambling.org",
  crisisName: "Suicide and Crisis Lifeline",
  crisisNumber: "988",
  crisisTel: "tel:988",
  crisisSms: "sms:988",
  emergencyNumber: "911",
  emergencyTel: "tel:911",
  /** The day the facts above were last checked against the Council's own pages. */
  verifiedOn: "2026-11-19",
  verifiedOnText: "November 19, 2026",
} as const;

/** The short line before the number, so the number itself can be a phone link. */
export const RESPONSIBLE_GAMBLING_LEAD = "21+. OddVex does not take wagers. Gambling problem? Call";

/** The short line shown wherever a compact notice gives the helpline. */
export const RESPONSIBLE_GAMBLING_LINE = `${RESPONSIBLE_GAMBLING_LEAD} ${HELPLINE.display}.`;

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
