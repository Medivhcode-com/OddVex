# OddVex — Compliance Overview (Issue-Spotting Checklist)

Last updated: 2026-11-21 (product facts in section 1 and the current positions checked against the code at commit `2b0c7c1`)

> **NOT LEGAL ADVICE.** This document is an internal issue-spotting checklist written by product staff, not lawyers. It lists topics that appear relevant and questions to put to counsel. It may be incomplete, out of date, or wrong. **Nothing here may be relied on as a statement of what the law requires. Qualified counsel (US gaming, privacy, consumer-protection/advertising, and IP) must review before any launch, beta with real users, marketing, or monetisation.** Laws and platform policies in this area change frequently and vary by state.

## 0. How to use this document

- Status column values: `Open` (not reviewed), `With counsel`, `Decided` (link the decision record).
- Every item below is **Open** as of this date. No legal review has occurred.
- Statements are phrased as "considerations" and "to be confirmed by counsel" deliberately.
- Decisions here are Founder-approval gate G-10 (see `docs/product/ROADMAP.md`).

## 1. Product facts counsel should rely on (and we must keep true)

| Fact | Notes |
|---|---|
| OddVex does not accept, place, route or settle wagers and holds no user funds | Core boundary; any feature that blurs this needs prior legal review |
| Information/analytics: odds comparison, prop research, calculators, tracker, assistant | — |
| US market, adults 21+ by policy | Self-attestation at sign-up; the time is stored, nothing else |
| Current build uses synthetic data and fictional teams/players/sportsbooks | No licensed data, no real brands. An internal-only replay with real NFL names exists and refuses to run in production mode (`docs/product/DECISION_LOG.md`, D-015) |
| Sportsbook sync is a mock; real sync only via authorized third-party vendors (planned M3) | No credential storage by OddVex |
| No affiliate links, no ads, no subscriptions today | All planned later; each changes the analysis |
| Community (user-generated content) is built and switched off | Profiles, picks, comments, follows, blocks, reports and moderation behind the `community` switch, off by default and on the preview. The screens are in the web and mobile code and appear when the switch is turned on |
| A private preview is running | Since 2026-11-18 on a Hostinger server, in production mode on synthetic data. The web preview is behind a password; the API at `api-preview.oddvex.com` is open and accepts sign-ups from anyone (`docs/product/DECISION_LOG.md`, D-021) |
| Assistant is rule-based today; LLM-backed planned (M4) | Fixed rules for crisis, under-21, distress and certainty messages, with known misses (RESPONSIBLE_GAMBLING section 5) |

**Triggers for fresh legal review:** affiliate/referral revenue; outbound sportsbook links; real brand names/logos; picks or projections; community/UGC; paid subscriptions; push/email marketing; any geo-targeting; non-US users; identity or location data collection.

---

## 2. US sports-betting information and affiliate considerations

Background (general understanding, to be confirmed by counsel): since the US Supreme Court's 2018 decision in *Murphy v. NCAA*, sports wagering is regulated primarily state by state; rules differ materially between states, and some states do not permit sports wagering.

| # | Issue | Why it may matter to OddVex | Question for counsel | Status |
|---|---|---|---|---|
| GB-01 | Whether a pure information/analytics service needs any gaming licence, registration or vendor approval in any state | We believe publishing odds information is generally distinct from operating wagering, but this must be confirmed per state | Confirm, state by state, that the current feature set requires no licence/registration | Open |
| GB-02 | **Affiliate / marketing-affiliate licensing or registration** | We understand that some states require sportsbook marketing affiliates to register or be licensed as vendors, and that requirements can differ by compensation model (e.g. flat fee/CPA vs. revenue share) | If OddVex adds affiliate links (ODDS-09): which states require what, for which compensation models, and what are timelines/costs? | Open |
| GB-03 | Displaying odds to users in states where sports betting is not legal, or where a displayed sportsbook is not licensed | Information may be lawful where wagering is not, but directing users to operators may raise issues | Any geo-restriction or state-specific display rules needed? Should "available in your state" filtering be mandatory before linking out? | Open |
| GB-04 | Offshore / unlicensed operators | Displaying or linking to unlicensed operators could create legal and reputational exposure | Policy: list only state-licensed operators — confirm criteria and how to verify | Open |
| GB-05 | Picks, projections, "+EV" labels (planned M4) | Could be characterised as betting advice/tout services; some jurisdictions have considered regulating such services; consumer-protection substantiation issues | Any regulatory regime for betting advice? What substantiation/disclaimers are needed? | Open |
| GB-06 | Federal statutes commonly cited in this space (e.g. Wire Act, UIGEA, state anti-gambling/"aiding" provisions) | We do not transmit wagers or process gambling payments; confirm no exposure through sync, links, or tracker | Confirm analysis for current and planned features | Open |
| GB-07 | Sportsbook sync via third-party vendors | Sportsbook terms of service may restrict third-party account access; vendor's authorization basis matters | Review vendor's legal basis, sportsbook ToS exposure, and our consent language | Open |
| GB-08 | Parlay builder / "send to sportsbook" deep links (not planned) | Any hand-off that pre-populates a bet slip may move us closer to facilitating wagers | Where is the line between information and facilitation? | Open |
| GB-09 | Minimum age | Many states set 21 for sports wagering; we understand some use a lower age. OddVex policy is 21+ everywhere | Is uniform 21+ sufficient and appropriate? | Open |
| GB-10 | Tribal gaming jurisdictions and US territories | Possible distinct rules | Any special handling? | Open |
| GB-11 | College sports / player-prop restrictions | We understand some states restrict certain college markets or props for operators | Do such restrictions affect an information service displaying those markets? | Open |
| GB-12 | Sweepstakes, DFS, prediction-market products | Out of scope today (NG-8) | Confirm we should not display these without separate review | Open |

## 3. Advertising and marketing rules

| # | Issue | Current OddVex position | Question for counsel | Status |
|---|---|---|---|---|
| AD-01 | "Risk-free", "free bet", "guaranteed", "can't lose" language | **Banned in all OddVex copy** (see `docs/marketing/BRAND_VOICE.md`). We understand regulators in several states and industry codes have restricted "risk-free"-type claims | Confirm banned-terms list; which rules apply to a non-operator publisher/affiliate | Open |
| AD-02 | Responsible-gaming messaging and helpline in ads | RG short line with 21+ and the National Problem Gambling Helpline, 1-800-MY-RESET (1-800-697-3738), on the web app, marketing site and mobile Settings, tracker and sync screens (verified 2026-11-19; 1-800-GAMBLER is the New Jersey council's line, not the national one) | State-specific helpline or wording requirements for ads/affiliates? Required prominence? | Open |
| AD-03 | Age targeting: 21+ | No marketing aimed at minors; no youth-appealing creative; no college-campus targeting | Audience-composition thresholds or placement restrictions that apply to us? | Open |
| AD-04 | Material-connection disclosures (FTC Endorsement Guides) | No affiliates/influencers today | Disclosure wording for affiliate links, sponsored placement, influencer content | Open |
| AD-05 | Ranking/"best" claims | "Best line" = objectively best displayed price; must not be influenced by commercial relationships without disclosure | Confirm labelling if any paid placement ever exists | Open |
| AD-06 | Performance/accuracy claims, testimonials | None permitted without substantiation and review (G-14) | Substantiation standard; typical-results disclosures | Open |
| AD-07 | Platform ad policies (search/social/app-install ads for gambling-related content) | No ads running. We understand major ad platforms have certification requirements for gambling-related advertisers, possibly including aggregators | Which certifications are needed before any paid campaign? | Open |
| AD-08 | Email/SMS/push marketing (CAN-SPAM, TCPA, state laws) | No messaging today (G-06) | Consent, opt-out, sender identification requirements; push content limits | Open |
| AD-09 | Advertising to self-excluded or vulnerable persons | We have no access to state self-exclusion lists | Obligations (if any) for affiliates/publishers; suppression expectations | Open |
| AD-10 | Use of sportsbook, league, team names/logos in marketing | Fictional only today | Trademark/nominative-use limits; league/partner rules | Open |

## 4. Apple App Store and Google Play considerations

Platform policies change; **re-read the current official text before submission.** Items below are our understanding to verify.

| # | Issue | Notes / understanding (verify) | Action | Status |
|---|---|---|---|---|
| ST-01 | Gambling policy classification | OddVex does not offer real-money gambling. Apple's App Review Guidelines address gambling (section 5.3) and Google Play has a real-money gambling policy; need to confirm how each treats odds-comparison / betting-information apps and what reviewers expect | Counsel + product to prepare review notes stating clearly that the app does not accept wagers | Open |
| ST-02 | Age rating | Gambling-related content is expected to drive a high age rating on both stores; Apple and Google (IARC) questionnaires must be answered accurately | Complete questionnaires truthfully; record answers in APP_STORE_LISTING_DRAFT | Open |
| ST-03 | Geo-availability | Decide storefront/country availability (US only at launch) | Founder decision | Open |
| ST-04 | Outbound links to sportsbooks / affiliate links in app | May affect gambling-policy treatment and require additional declarations | Decide before M3; ask counsel | Open |
| ST-05 | In-app account deletion | Both stores require apps that support account creation to offer account deletion (Apple in-app; Google also expects a web deletion path) — verify current wording | AUTH-06 + MOB-02 before submission | Open |
| ST-06 | Privacy disclosures | Apple privacy "nutrition labels" and Google Data safety form must match actual data practices and SDKs | Derive from PRIVACY_AND_DATA inventory | Open |
| ST-07 | Subscriptions / in-app purchase | Digital subscriptions sold in-app generally must use store billing, subject to evolving exceptions; subscription disclosure requirements apply | Counsel to confirm current rules at M4 | Open |
| ST-08 | User-generated content (M5) | Stores expect filtering, reporting, blocking and timely action on objectionable content. The community screens, with report and block, are compiled into the mobile app and appear when the server switch is on; moderation is web-only | Decide with counsel whether a binary with these screens switched off must declare user content (STORE_SUBMISSION_PREP section 3) | Open |
| ST-09 | AI features | Stores have requirements around AI-generated content/reporting and accurate metadata; check current policy | Review at M4 | Open |
| ST-10 | Demo account and review notes | Reviewers need working credentials and an explanation of data sources | Prepare at M6 | Open |
| ST-11 | Metadata accuracy | No misleading claims, no guaranteed-win language, screenshots reflect real app | BRAND_VOICE check | Open |
| ST-12 | Push notifications | Must not be required; promotional pushes need opt-in per platform rules (verify) | NOTF-01 design | Open |
| ST-13 | Third-party sync (credentials/third-party login) | May raise review questions about accessing other services' accounts | Review notes + vendor documentation | Open |
| ST-14 | Developer account entity and any gambling-related declarations/forms | Organisation account under the correct legal entity | Founder (G-04) | Open |

## 5. Age gating

| # | Issue | Current position | Question for counsel | Status |
|---|---|---|---|---|
| AG-01 | Method | 21+ self-attestation checkbox at signup, recorded with a timestamp only; no terms version is stored (AUTH-02) | Is attestation adequate for an information service? For an affiliate? Is a neutral date-of-birth screen expected? | Open |
| AG-02 | Marketing-site access | Public pages are not gated | Is an age interstitial advisable? | Open |
| AG-03 | Handling suspected minors | Policy: close account and delete data on credible indication. An administrator can delete an account; no written procedure exists. The assistant gives no betting information to someone who says they are under 21 but records nothing | Confirm process and any reporting duties | Open |
| AG-04 | Stronger verification | Not planned; would require new personal data (G-13) | When (if ever) would ID/age verification be required? | Open |
| AG-05 | State age-verification / app-store age-assurance laws | Several states have enacted or proposed laws on age assurance for apps/online services | Applicability to OddVex | Open |

## 6. Privacy

| # | Issue | Notes | Question for counsel | Status |
|---|---|---|---|---|
| PR-01 | California (CCPA/CPRA) | Applicability depends on statutory thresholds we may not yet meet; plan to honour core rights regardless | Applicability; notice-at-collection content; "sale/share" analysis for any analytics/ads tech | Open |
| PR-02 | Other US state privacy laws | A growing number of states have comprehensive privacy laws with differing thresholds and rights | Which apply; unified approach | Open |
| PR-03 | Sensitive data | Betting history may be sensitive in practice (financial behaviour; possible inference about gambling problems). Precise geolocation is not collected | Does any state treat our data as "sensitive"? Extra consent needed? | Open |
| PR-04 | GDPR / UK GDPR | US-only product, but EU/UK visitors can reach the website | Do we fall in scope? Geo-block, or comply (lawful basis, cookie consent, representatives)? | Open |
| PR-05 | Children (COPPA) | Service is not directed to children; 21+ only; no knowing collection from under-13s (or any minor) | Confirm "not directed to children" posture; wording in policy | Open |
| PR-06 | Cookies/trackers and Global Privacy Control | No ad trackers planned in M1 | Consent banner needs; GPC handling | Open |
| PR-07 | Sub-processors and DPAs | None engaged by contract. Hostinger hosts the preview server and its data, and the support mailbox | DPA requirements for hosting, analytics, email, LLM, sync vendors | Open |
| PR-08 | LLM provider data use (M4) | User prompts could include personal/betting data | Contract terms: no training on our data, retention limits, location | Open |
| PR-09 | Sync vendor data flows (M3) | Vendor handles sportsbook authentication | Controller/processor roles; consent; vendor security review | Open |
| PR-10 | Data-breach notification | State breach laws vary | Notification matrix for INCIDENT_RESPONSE | Open |
| PR-11 | Data subject request handling | Deletion and export are self-serve (export on web only). Staff can export or delete for an owner who cannot sign in; no identity-check procedure is written | Verification standards; response timelines | Open |
| PR-12 | Financial-privacy regimes (e.g. GLBA) | We are not a financial institution, but hold betting-transaction records | Confirm not applicable | Open |

Details: [PRIVACY_AND_DATA.md](./PRIVACY_AND_DATA.md).

## 7. Data licensing and intellectual property

| # | Issue | Notes | Question for counsel | Status |
|---|---|---|---|---|
| DL-01 | Odds/scores/stats source | Must be a licensed provider; **no scraping** of sportsbooks or sites (NG-4) | Review provider agreement before signing (G-01) | Open |
| DL-02 | Licence scope | Check: display rights (web + mobile), caching/storage, historical retention, derived data (no-vig, projections), use in AI answers, SEO pages, redistribution limits, attribution, delay requirements, termination/deletion duties | Contract review checklist | Open |
| DL-03 | "Official league data" | We understand some states require operators to use official data for certain bets; unclear relevance to an information service | Any impact on us? | Open |
| DL-04 | Team/league names and logos | Fictional today. Real names likely usable descriptively; logos generally need licence | Policy for names vs. logos | Open |
| DL-05 | Player names, images, likeness | Right-of-publicity considerations, esp. in marketing; no player images planned | Limits on use in product vs. advertising | Open |
| DL-06 | Sportsbook names/logos | Nominative use vs. implied endorsement; affiliate programmes may grant brand assets | Policy | Open |
| DL-07 | OddVex trademark | Clearance and registration for "OddVex" and tagline | Search/registration plan | Open |
| DL-08 | Open-source licence compliance | Dependency licences to be scanned | Any copyleft concerns | Open |
| DL-09 | DMCA agent (if UGC) | For M5 | Registration and policy | Open |

## 8. Subscriptions and auto-renewal (M4)

| # | Issue | Notes | Question for counsel | Status |
|---|---|---|---|---|
| SB-01 | Federal: ROSCA and FTC negative-option rules | We understand ROSCA requires clear disclosure of material terms, express informed consent before charging, and a simple cancellation mechanism. The status of the FTC's amended Negative Option ("click-to-cancel") rule has been subject to litigation and should be confirmed | Current federal requirements | Open |
| SB-02 | State automatic-renewal laws (ARLs) | Many states have ARLs; California's is commonly treated as a high-water mark and has been amended in recent years. Requirements may include pre-purchase disclosures, affirmative consent, acknowledgement emails, renewal reminders, online cancellation | Design to strictest applicable standard — confirm specifics | Open |
| SB-03 | Free trials and price changes | Extra notice requirements may apply | Trial-to-paid and price-change notice rules | Open |
| SB-04 | Cancellation UX | Product commitment: cancel online in as few steps as signup; no obstruction | Confirm adequacy | Open |
| SB-05 | Refund policy and store billing interplay | Store-billed subscriptions are managed/refunded via the store | Policy wording | Open |
| SB-06 | Payment processor acceptable-use | Processors may classify gambling-adjacent businesses as restricted/high-risk | Confirm eligibility before building (G-01/G-11) | Open |
| SB-07 | Sales tax on digital subscriptions | Varies by state | Tax advice needed | Open |

## 9. AI-generated content and assistant

| # | Issue | Current position | Question for counsel | Status |
|---|---|---|---|---|
| AI-C1 | Disclosure that users are interacting with an automated system | Always disclosed in UI (AI-05). We understand some states have bot/AI-disclosure laws | Required wording/prominence; state-specific rules | Open |
| AI-C2 | Accuracy / deception (FTC Act §5 and state UDAP laws) | Grounding contract: numbers only from verified tools; no invented numbers; "no data" responses | Disclaimers; liability for errors | Open |
| AI-C3 | Advice characterisation | Assistant gives information, not betting or financial advice; a request for a certain winner gets a fixed refusal | Is disclaimer sufficient? | Open |
| AI-C4 | Marketing claims about "AI" | M1 assistant is rule-based; marketing must not overstate capability | Substantiation for "AI" claims | Open |
| AI-C5 | LLM provider terms (M4) | Usage policies may restrict gambling-related use cases | Check provider acceptable-use policy before selection | Open |
| AI-C6 | Vulnerable users | Fixed rules route crisis, under-21 and distress messages to support replies with no betting data, in that order; every other answer ends with the helpline and 988. The rules miss some wordings (listed in the tests as `KNOWN_MISSES`). See RESPONSIBLE_GAMBLING section 5 | Any duty-of-care expectations | Open |
| AI-C7 | Retention of conversations | Not stored. Each support reply writes one log record with the case and whether the person was signed in, no text | Retention/notice requirements when persisted | Open |
| AI-C8 | Emerging state AI laws | Rapidly changing | Monitoring plan | Open |

## 10. User-generated content and moderation (M5)

| # | Issue | Question for counsel | Status |
|---|---|---|---|
| UG-01 | Platform liability posture (e.g. Section 230) and its limits | How to structure moderation without assuming undue liability | Open |
| UG-02 | Terms of use, community guidelines, licence grant from users | Draft review | Open |
| UG-03 | Prohibited content: pick-selling, guaranteed-win claims, solicitation, harassment, illegal operators, minors | Policy review | Open |
| UG-04 | User-posted affiliate/referral links and FTC disclosure | Ban or regulate? | Open |
| UG-05 | Copyright complaints (DMCA notice-and-takedown, agent registration) | Process | Open |
| UG-06 | Shared bet slips and personal data | Privacy defaults; consent | Open |
| UG-07 | Leaderboards / contests | Could they be characterised as contests/promotions or encourage harmful play? | Open |
| UG-08 | Reporting obligations (e.g. certain illegal content) | Requirements | Open |
| UG-09 | Minors' online-safety laws | Applicability given 21+ gate | Open |

## 11. General consumer protection

| # | Issue | Current position | Status |
|---|---|---|---|
| CP-01 | Unfair/deceptive practices (FTC Act, state UDAP) | No guarantees, no hype; clear "information only" statements; synthetic data labelled | Open |
| CP-02 | Demo data must not be mistaken for real odds | "Demo data" labelling (NFR-04); no public launch on synthetic data without clear labelling | Open |
| CP-03 | Dark patterns | None in signup, cancellation, deletion, consent flows | Open |
| CP-04 | Terms of Service enforceability (assent mechanics, arbitration/class waiver, limitation of liability, disclaimers for data errors/delays) | Counsel to draft/review | Open |
| CP-05 | Accessibility legal exposure (ADA / state laws) | WCAG 2.2 AA target (NFR-10) | Open |
| CP-06 | Data accuracy disclaimers | Odds may be delayed or wrong; always verify with the sportsbook | Open |
| CP-07 | Responsible gambling | See [RESPONSIBLE_GAMBLING.md](./RESPONSIBLE_GAMBLING.md) | Open |
| CP-08 | Corporate: entity, state registrations, insurance (cyber, E&O), tax | Founder + counsel | Open |

## 12. Consolidated open questions for counsel (priority order)

1. Does any current or planned OddVex feature require a gaming licence, vendor registration or affiliate registration in any state? (GB-01, GB-02)
2. If affiliate revenue is pursued, what is the state-by-state path and cost, by compensation model? (GB-02)
3. Is 21+ self-attestation adequate, or is date-of-birth entry or stronger verification expected? (AG-01)
4. Should any states be excluded or geo-restricted at launch, and is geolocation needed? (GB-03)
5. How do Apple and Google classify an odds-information app with no wagering, and what changes if it links out to sportsbooks? (ST-01, ST-04)
6. What do we need in Terms, Privacy Policy and RG pages before a closed beta with real users? (CP-04, PR-01…PR-06)
7. What contractual terms are essential in a data licence, including AI and SEO use? (DL-02)
8. Is third-party sportsbook sync legally sound, and under what consent and vendor terms? (GB-07)
9. What substantiation and disclaimers are required for projections/EV labels and for calling the assistant "AI"? (GB-05, AI-C4)
10. What auto-renewal design satisfies federal and the strictest state requirements today? (SB-01, SB-02)
11. Do GDPR/UK GDPR obligations arise from incidental EU/UK traffic, and should we geo-block? (PR-04)
12. What is the breach-notification matrix we should pre-build into incident response? (PR-10)
