# OddVex — SEO and Content Strategy

Last updated: 2026-11-15 · Status: strategy draft. Publishing and promotion are external actions that **require Founder approval** (G-05).

**No search-volume, difficulty, traffic or ranking numbers appear in this document.** We have not purchased keyword data. Prioritisation below is qualitative and must be validated with a keyword tool and Search Console data before investment.

## 1. Goals and constraints

| Goal | Constraint |
|---|---|
| Earn qualified organic traffic from people researching betting markets and betting maths | Gambling-adjacent content is a "Your Money or Your Life"-type topic: quality, accuracy and trust signals matter |
| Convert readers to signups through genuinely useful tools | No hype or banned claims (BRAND_VOICE); RG line on every page |
| Build topical authority around odds maths and line shopping | No real odds/team/player pages until a data licence permits public display and SEO use (DL-02) |
| Stay honest | Current product data is synthetic — **no indexable page may present fictional odds as real** |

## 2. What can ship when

| Phase | Indexable content |
|---|---|
| M1 (now) | Marketing pages, methodology, RG page, help centre, evergreen educational articles, public calculators (if exposed outside the app — proposal) |
| M2+ (licensed data) | Programmatic league/game/market/player pages, line-movement pages |
| M3+ | State guides (only after counsel review), sportsbook profile pages (only with trademark/affiliate review) |

Demo/app routes (`/app/*`, `/login`, `/signup`) are `noindex`.

## 3. Keyword themes (qualitative; validate before use)

| Theme | Example query patterns | Intent | Target page type | Phase |
|---|---|---|---|---|
| T1 Odds maths & calculators | "implied probability calculator", "no vig calculator", "EV calculator betting", "parlay calculator", "CLV calculator", "american to decimal odds" | Tool / do | Calculator landing pages | M1 |
| T2 Betting concepts | "what is closing line value", "what does −110 mean", "what is the vig", "how do parlays work", "what is expected value in betting" | Learn | Glossary + guides | M1 |
| T3 Line shopping / odds comparison | "odds comparison", "compare sportsbook odds", "best odds [league]", "line shopping" | Compare | `/odds-comparison` + league hubs | M1 (feature page) / M2 (data pages) |
| T4 Player props research | "[league] player props", "player prop hit rates", "how to research player props" | Research | `/player-props` + guides; data pages later | M1 / M2 |
| T5 Bet tracking | "bet tracker", "how to track sports bets", "betting ROI calculator", "bet tracking spreadsheet alternative" | Tool / learn | `/bet-tracking` + guides + template | M1 |
| T6 Parlays & correlation | "same game parlay correlation", "are parlays worth it", "parlay odds explained" | Learn | Guides + parlay tool page | M1 |
| T7 AI and betting data | "AI sports betting assistant", "can AI predict sports bets" | Learn / evaluate | `/ai` + honest explainer articles | M1 |
| T8 Responsible gambling | "signs of problem gambling", "how to set a betting budget" | Help | `/responsible-gambling` + guides (reviewed against NCPG materials) | M1 |
| T9 Game / matchup odds | "[team] vs [team] odds", "[game] spread" | Compare now | Programmatic game pages | M2 |
| T10 State / legal | "is sports betting legal in [state]" | Inform | State guides — **only with counsel review; high legal-accuracy risk** | M3+ |
| T11 Brand | "OddVex", "OddVex app", "OddVex review" | Navigate | Home, about, download | M1 |

Themes to avoid: "free picks", "locks", "guaranteed bets", "promo codes/bonuses" (affiliate/advertising rules; revisit only with counsel), anything targeting under-21s.

## 4. Content pillars

| Pillar | Promise | Formats | Example titles (drafts) |
|---|---|---|---|
| **P1 Betting Math, Explained** | The clearest explanations of odds maths | Guides, worked examples, calculator pages, glossary | "Implied probability: what a price really says" · "No-vig odds: removing the sportsbook's margin" · "Expected value: what it is and what it isn't" |
| **P2 Reading the Market** | How lines and prices work across sportsbooks | Guides, annotated illustrative examples | "Why the same game has different prices" · "Line vs. price: reading a spread correctly" · "What closing line value tells you" |
| **P3 Research Methods** | How to research props and parlays responsibly | How-tos, checklists | "Sample size: why 5 games isn't a trend" · "Correlation in parlays, in plain language" |
| **P4 Know Your Numbers** | Honest record-keeping | Guides, templates | "How to track your bets (and why most people don't)" · "ROI, units and record: which numbers matter" |
| **P5 Trust & Transparency** | How OddVex works | Methodology, data notes, AI explainer, changelog | "How OddVex AI answers questions without inventing numbers" · "How we label data freshness" |
| **P6 Bet Responsibly** | Practical, non-judgemental guidance | Guides, resources | "Warning signs and where to get help" · "Setting limits before you bet" |

Editorial standards:
- Every article: named author or "OddVex Editorial", last-reviewed date, sources for factual claims, RG line.
- Worked examples use clearly fictional teams/sportsbooks or generic labels ("Team A", "Book 1").
- No outcome predictions; no claims of profitability; maths reviewed against the shared calculator module.
- AI-assisted drafts must be human-reviewed for accuracy; disclose where appropriate (counsel to advise).
- Legal/state content only after counsel review.

## 5. Programmatic page ideas

| # | Page type | URL pattern (proposal) | Data needed | Guardrails | Phase |
|---|---|---|---|---|---|
| PG-1 | Calculator pages | `/tools/[calculator]` (public) or sections on marketing pages | None (client maths) | Unique explanatory copy per tool; formula; FAQ | M1 (proposal — currently calculators live at `/app/tools` behind auth; decide whether to expose publicly) |
| PG-2 | Odds conversion pages | `/odds/[american]` e.g. "+150 in decimal and implied probability" | None | Limit to a sensible set; consolidate with canonical; avoid thin near-duplicates | M2 |
| PG-3 | Glossary | `/glossary/[term]` | None | Real definitions; interlink | M1/M2 |
| PG-4 | League odds hubs | `/odds/[league]` | Licensed odds | Freshness label; `noindex` when no upcoming games | M2 |
| PG-5 | Game odds pages | `/odds/[league]/[game-slug]` | Licensed odds | Expire/redirect after event; structured data; timestamp | M2 |
| PG-6 | Market pages | `/odds/[league]/[market]` | Licensed odds | Avoid combinatorial explosion | M2 |
| PG-7 | Player prop pages | `/props/[league]/[player-slug]` | Licensed stats + props | Right-of-publicity/name-use review; no images without licence | M2/M3 |
| PG-8 | Line-movement pages | `/odds/.../movement` | Historical odds licence | Chart with text alternative | M2+ |
| PG-9 | State guides | `/states/[state]` | Counsel-reviewed content | Review dates; no legal assurances (BC-14) | M3+ |
| PG-10 | Sportsbook profiles | `/sportsbooks/[book]` | Trademark + (if any) affiliate review | Disclosures; neutral comparisons | M3+ |

Programmatic quality rules:
- Each page must offer unique value (data + explanation); otherwise `noindex`.
- Hard cap on generated URLs per release; monitor index coverage before scaling.
- No pages generated from synthetic fixtures are ever indexable.
- Stale data pages show "as of" and degrade gracefully.

## 6. Technical SEO checklist

Foundations
- [ ] Server-rendered or statically generated marketing pages (Next.js); content visible without client JS
- [ ] Unique `<title>` and meta description per page; one `<h1>`; logical heading order
- [ ] Canonical URLs on every indexable page; consistent trailing-slash and host (https, apex vs. www) policy with redirects
- [ ] `robots.txt` present; disallow `/app/`, auth routes and API; staging/preview environments `noindex` and/or auth-protected
- [ ] `noindex` on `/login`, `/signup`, `/app/*`
- [ ] XML sitemap (split by type when large), submitted in Search Console; `lastmod` accurate
- [ ] Clean, lowercase, hyphenated URLs; stable slugs; 301s for changed URLs
- [ ] Custom 404 returns HTTP 404; no soft-404s
- [ ] `lang="en-US"`; hreflang not needed at launch (US only)

Performance and UX
- [ ] Core Web Vitals within budgets (NFR-20): LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1
- [ ] Optimised images (modern formats, dimensions set, lazy-load below the fold); font loading without layout shift
- [ ] Mobile-first layouts; no intrusive interstitials
- [ ] Accessibility (WCAG 2.2 AA) — also benefits SEO

Structured data (validate with rich-results testing)
- [ ] `Organization` + `WebSite` on home
- [ ] `SoftwareApplication` / `MobileApplication` on `/download` (ratings only when real)
- [ ] `Article` / `BlogPosting` with author and dates on posts
- [ ] `BreadcrumbList` on nested pages
- [ ] `FAQPage` only where FAQs are genuinely on the page
- [ ] `SportsEvent` on game pages (M2; real data only)
- [ ] Never mark up fabricated reviews or ratings

Content integrity
- [ ] Open Graph and Twitter card tags with accurate images (no misleading claims in images)
- [ ] Internal linking: guides ↔ calculators ↔ feature pages ↔ methodology
- [ ] Author/about/contact/editorial-policy pages for trust signals
- [ ] Legal pages linked site-wide; RG line in footer
- [ ] Review dates on educational content; scheduled re-review

Operations
- [ ] Search Console and (if approved) Bing Webmaster verified — account creation is an external action (Founder approval)
- [ ] Analytics per taxonomy with consent handling
- [ ] Log/monitor crawl errors and index coverage
- [ ] Redirect map maintained; no chains
- [ ] Pre-launch: confirm production is indexable and all non-production hosts are not

## 7. Measurement (definitions only; no targets set)

| Metric | Source |
|---|---|
| Indexed pages vs. submitted | Search Console |
| Impressions / clicks / CTR by theme | Search Console |
| Organic landing → signup-start rate | Analytics (`signup_started` with `landing_page_type`) |
| Calculator page engagement (valid calculation completed) | Analytics |
| Core Web Vitals field data | Search Console / RUM |

## 8. Risks and open questions

| # | Item | Owner |
|---|---|---|
| SEO-Q1 | Expose calculators publicly (outside `/app`) for SEO? Product/engineering decision | Founder |
| SEO-Q2 | Does the data licence allow public, indexable odds pages and caching by search engines? | Counsel / provider (DL-02) |
| SEO-Q3 | Gambling-related ad/search platform policies for our category | Counsel (AD-07) |
| SEO-Q4 | Budget for a keyword research tool | Founder (G-01/G-02) |
| SEO-Q5 | Policy on AI-assisted content and disclosure | Founder + counsel |
| SEO-Q6 | State guides: worth the legal-review cost? | Founder |
