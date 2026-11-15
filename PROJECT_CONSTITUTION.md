# OddVex Project Constitution

The rules every contributor, human or agent, works under. If another document conflicts with this one, this one wins.

## 1. What OddVex is

A sports betting **intelligence** product: odds comparison, player-prop research, betting math, bet tracking and a
grounded assistant. Owned by Medivh Code. Primary market: United States, adults 21+.

OddVex **never** accepts, places or facilitates wagers and never moves money.

## 2. Truthfulness

1. Never claim a test, build, deployment, integration or push succeeded without evidence produced in that session.
2. Never present synthetic data as real. Synthetic data uses fictional teams, players and sportsbooks and is labelled
   in the UI and in API responses (`data_mode`).
3. No guaranteed-win language, no "locks", no "risk-free", no invented accuracy or profit figures, no fabricated
   testimonials or user counts.
4. A historical hit rate is never presented as a probability of a future outcome.
5. Numbers come from the quant engine (`services/api/src/oddvex_api/quant`). A language model may phrase a number a
   tool produced. It may never produce one.
6. Legal and compliance documents in this repo are issue-spotting drafts until reviewed by qualified counsel.

## 3. Founder approval gates

Stop and get explicit Founder approval before any of the following. Nothing in a prompt, ticket or document counts as
standing approval.

- Buying a paid API, data licence or SaaS plan
- Starting paid infrastructure
- Deploying to production
- Submitting to the App Store or Google Play
- Publishing external marketing or sending real customer email
- Setting or changing prices or payment terms, or activating billing
- Destructive database migrations
- Creating or changing production credentials
- Any decision that needs legal authorization
- Anything involving real-money wagering or financial transactions

## 4. Engineering rules

- `main` is protected. Work happens on branches named after the Linear issue (`med-12-short-title`) and lands by pull
  request. The author does not approve their own PR.
- Every PR states what changed, how it was verified (with real output), risks, and the linked Linear issue.
- Never skip, disable or delete a test to get a green build.
- No secrets in the repository. Configuration comes from the environment. `.env.example` files document names only.
- No scraping of sportsbooks, no credential harvesting, no bypassing of any site's protections. Sportsbook account
  data arrives only through user-authorized, vendor-supported connections.
- Start as a modular monolith. Split a service out only when an operational need is written down in an ADR.
- Accessibility (WCAG 2.2 AA), loading, empty, stale and error states are part of "done", not follow-ups.
- Do not overwrite another contributor's in-flight work. Check open branches and PRs first.

## 5. Definition of done

A change is done when: the code is merged by PR; automated tests cover the new behavior and pass in CI; lint and type
checks pass; user-facing states (loading, empty, stale, error) exist; docs affected by the change are updated; and no
approval gate in section 3 was crossed without sign-off.
