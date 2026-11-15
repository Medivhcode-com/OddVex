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

export const APP_NAV = [
  { href: "/app", label: "Home", icon: "home" },
  { href: "/app/games", label: "Games", icon: "games" },
  { href: "/app/odds", label: "Odds", icon: "odds" },
  { href: "/app/props", label: "Props", icon: "props" },
  { href: "/app/tracker", label: "Tracker", icon: "tracker" },
  { href: "/app/tools", label: "Calculators", icon: "tools" },
  { href: "/app/parlay", label: "Parlay", icon: "parlay" },
  { href: "/app/assistant", label: "OddVex AI", icon: "ai" },
] as const;
