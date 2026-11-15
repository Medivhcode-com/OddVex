# OddVex — Launch Plan (Draft)

Last updated: 2026-11-15 · Status: **DRAFT — nothing in this plan has been executed or approved.**

> **Every external action in this plan requires Founder approval before execution** (ROADMAP gates G-04 store, G-05 external marketing, G-06 real customer email, G-07 pricing, G-10 legal, G-11 real money). Actions are tagged **[RFA]** = *requires Founder approval*. Legal-dependent items are tagged **[C]** = counsel review first.
>
> No dates, budgets, audience sizes or performance targets are stated; none have been set. The product today runs on synthetic data and is not launchable.

## 1. Positioning summary

| Element | Draft |
|---|---|
| Category | Sports-betting intelligence (information and analytics) |
| One-liner | "Every Line. A Smarter Perspective." |
| Value proposition | Compare prices across sportsbooks, understand what each number means, research props, and keep an honest record — in one precise, calm product |
| Differentiators (to validate against `docs/research/`) | Freshness labelling on every number · transparent methodology · assistant that never invents numbers · no hype / no picks · RG built in |
| Not | A sportsbook, a picks service, or a promise of winning |
| Audience | 21+ US adults: curious fans, recreational bettors, serious bettors |

Message pillars: **Clarity** (every price, side by side) · **Understanding** (what the number means) · **Honesty** (your real record; sources shown) · **Responsibility** (information, never pressure).

## 2. Launch phases and gates

| Phase | Corresponds to | Pre-conditions |
|---|---|---|
| Phase 0 — Internal readiness | M1–M2 | Product on licensed data; legal pages reviewed; deletion/export working |
| Phase 1 — Pre-launch / waitlist | M2 | Founder approval for real email collection; privacy policy approved [C] |
| Phase 2 — Closed beta | M2–M3 | Production infra; beta terms [C]; incident response exercised |
| Phase 3 — Public launch | M6 | LAUNCH_READINESS_CHECKLIST complete; store approvals |
| Phase 4 — Post-launch | after M6 | Analytics and support in place |

## 3. Phase 0 — Internal readiness (no external actions)

| # | Action | Owner | Approval |
|---|---|---|---|
| 0.1 | Finalise brand voice, message pillars, boilerplate | Product/marketing docs | Internal |
| 0.2 | Marketing site content complete with accurate "available vs. planned" labelling | Product | Internal |
| 0.3 | Prepare illustrative screenshots (fictional data, labelled) | Design | Internal |
| 0.4 | Draft educational articles for pillars P1–P6 (unpublished) | Content | Internal |
| 0.5 | Implement analytics taxonomy in non-production | Engineering | Internal |
| 0.6 | Draft store listings (APP_STORE_LISTING_DRAFT) | Product | Internal |
| 0.7 | Draft press boilerplate and FAQ (no claims requiring substantiation) | Product | Internal |
| 0.8 | Compile counsel question list (COMPLIANCE_OVERVIEW §12) | Compliance docs | Internal |

## 4. Phase 1 — Pre-launch / waitlist

| # | Action | Channel | Approval |
|---|---|---|---|
| 1.1 | Deploy marketing site to production domain oddvex.com | Web | **[RFA]** (G-03) |
| 1.2 | Enable waitlist form (email + 21+ confirmation + consent wording) | Web | **[RFA]** (G-06) **[C]** |
| 1.3 | Send waitlist confirmation email | Email | **[RFA]** (G-06; paid email service G-02) |
| 1.4 | Create official social accounts and reserve handles | Social | **[RFA]** (G-05) |
| 1.5 | Publish first educational articles | Blog | **[RFA]** (G-05) |
| 1.6 | Register Search Console / webmaster tools | SEO | **[RFA]** |
| 1.7 | Occasional product-progress updates to waitlist (opt-in only; unsubscribe; RG line) | Email | **[RFA]** per send **[C]** for template |
| 1.8 | Founder-led posts about building OddVex (principles, methodology) | Social | **[RFA]** per post |
| 1.9 | Outreach to prospective beta testers in betting-analytics communities, following each community's rules | Community | **[RFA]** |

Waitlist rules: collect email only (plus 21+ attestation); no incentives tied to betting; no referral contest without counsel review **[C]**; no purchased lists; honour deletion requests.

## 5. Phase 2 — Closed beta

| # | Action | Approval |
|---|---|---|
| 2.1 | Select beta cohort size and criteria (mix of personas P1–P3) | **[RFA]** |
| 2.2 | Send beta invitations | **[RFA]** (G-06) |
| 2.3 | Beta terms / feedback consent | **[RFA]** **[C]** |
| 2.4 | TestFlight / Play internal testing for mobile | **[RFA]** (G-04) |
| 2.5 | Feedback channel (form or private community space) | **[RFA]** |
| 2.6 | User interviews (recruit from beta; consent; no testimonials used publicly without written permission and counsel-approved disclosures) | **[RFA]** |
| 2.7 | Weekly beta notes to participants | **[RFA]** per send |

Beta learning goals (questions, not targets): Do users understand best-line and no-vig displays? Is freshness labelling noticed and trusted? Which assistant questions go unanswered? Where do users drop in tracker logging? Is the correlation warning understood?

Beta exit criteria: critical bugs closed; activation and retention **measured** (baselines established); data-quality incidents reviewed; support macros written; readiness checklist [B] items complete.

## 6. Phase 3 — Public launch

### 6.1 Launch-day sequence (draft)

| # | Action | Approval |
|---|---|---|
| 3.1 | Go/no-go meeting; record decision | **[RFA]** |
| 3.2 | Release web app publicly | **[RFA]** (G-03) |
| 3.3 | Release mobile apps after store approval | **[RFA]** (G-04) |
| 3.4 | Launch email to waitlist | **[RFA]** (G-06) |
| 3.5 | Launch posts on owned social channels | **[RFA]** (G-05) |
| 3.6 | Launch blog post ("What OddVex is — and isn't") | **[RFA]** |
| 3.7 | Product-directory / community launch posts (where rules allow gambling-adjacent products) | **[RFA]** |
| 3.8 | Press outreach to sports-business and tech media with factual boilerplate | **[RFA]** **[C]** for claims |
| 3.9 | Update `/download` with store badges; `/pricing` with approved pricing (if Premium live) | **[RFA]** (G-04, G-07) |

### 6.2 Channels under consideration (none approved)

| Channel | Notes | Approval |
|---|---|---|
| Organic search | Per SEO_CONTENT_STRATEGY | **[RFA]** to publish |
| Owned social | Educational content; no picks; RG line | **[RFA]** |
| Email | Opt-in only | **[RFA]** **[C]** |
| Paid search / social / app-install ads | Platform gambling-category certification may be required; state ad rules; 21+ targeting | **[RFA]** (spend, G-05) **[C]** — do not start without counsel memo (AD-07) |
| Creator / influencer partnerships | FTC disclosures; creator must follow BRAND_VOICE; no pick-sellers | **[RFA]** **[C]** |
| Podcast / newsletter sponsorships | Audience must be predominantly 21+ | **[RFA]** **[C]** |
| Sportsbook affiliate partnerships | State affiliate registration/licensing questions (GB-02); changes store review posture | **[RFA]** **[C]** (G-11) |
| App Store Optimisation | Per APP_STORE_LISTING_DRAFT | **[RFA]** |
| PR | Factual only; no accuracy claims | **[RFA]** |

### 6.3 Launch assets checklist

- [ ] Final screenshots from the real app with licensed or clearly fictional data
- [ ] Launch blog post, email, social copy — all passing BRAND_VOICE review
- [ ] Press boilerplate, founder bio, FAQ
- [ ] Help centre complete; support macros
- [ ] RG line on every asset
- [ ] Tracking links/UTMs defined (see taxonomy)
- [ ] Rollback/communication plan for launch-day incidents (INCIDENT_RESPONSE)

## 7. Phase 4 — Post-launch

| # | Action | Approval |
|---|---|---|
| 4.1 | Daily launch-week review: stability, data freshness, support volume, funnel | Internal |
| 4.2 | Respond to store reviews (factual, courteous; no incentives for reviews) | **[RFA]** (policy once, then delegated) |
| 4.3 | Publish changelog / "what we shipped" updates | **[RFA]** |
| 4.4 | Ongoing educational content cadence | **[RFA]** (editorial calendar approval) |
| 4.5 | Lifecycle emails (onboarding tips, feature education — never betting inducements) | **[RFA]** **[C]** |
| 4.6 | In-app rating prompt (only after a positive, non-betting-outcome moment; never after a win) | **[RFA]** |
| 4.7 | Premium introduction (if not at launch) | **[RFA]** (G-07) **[C]** |
| 4.8 | Evaluate paid acquisition test | **[RFA]** **[C]** |
| 4.9 | Quarterly review: north-star trend, RG guardrail audit, compliance re-check | Internal + Founder |

## 8. Guardrails for all marketing

1. BRAND_VOICE banned claims apply everywhere, including partner and creator content.
2. No real user quotes, numbers or logos without written permission; no fabricated proof.
3. No marketing where the audience is likely to include a material share of under-21s.
4. No messages timed or worded to induce betting (e.g. "games start in 10 minutes — bet now").
5. No "risk-free"/"free bet" or sportsbook bonus promotion without counsel approval.
6. Every asset carries the RG line.
7. Any metric quoted publicly must be real, current and reviewed (G-14).

## 9. Measurement (definitions; see ANALYTICS_EVENT_TAXONOMY)

| Stage | Metric definition |
|---|---|
| Awareness | Marketing-site sessions by source |
| Interest | Waitlist signups / signup starts |
| Activation | New users completing ≥ 1 research action in first session |
| Engagement | Weekly Researching Users (north-star proposal) |
| Retention | Week-4 retention of activated users |
| Trust | Stale-data exposure rate; assistant unsupported-question rate; support contacts per active user |

## 10. Open questions for the Founder

| # | Question |
|---|---|
| LP-Q1 | Launch web first and mobile later, or simultaneously? |
| LP-Q2 | Is there a marketing budget, and is paid acquisition in scope at all in year one? |
| LP-Q3 | Founder-led content: is the Founder willing to be the public voice? |
| LP-Q4 | Affiliate model: pursue, defer, or rule out? (Drives much of the compliance work.) |
| LP-Q5 | Premium at launch or after? |
| LP-Q6 | Which season/sport calendar moment (if any) should launch align to? |
| LP-Q7 | Who approves day-to-day posts once a policy exists — Founder each time, or delegated within written rules? |
