# OddVex — Launch Readiness Checklist

Last updated: 2026-11-15

**Status: NOT READY FOR LAUNCH.** Only M1 is in build, on synthetic data, with no production environment, no legal review and no real users. Boxes are unchecked unless trivially true today. A box may be checked only with evidence (link to PR, test run, signed document, or decision record) and the name/date of the person confirming.

"Launch" = public availability to real users (M6). Sub-gates: **[B]** = also required before a closed beta with real users (M2). **[F]** = Founder approval gate. **[C]** = counsel sign-off required.

## 0. Trivially true today

- [x] Product does not accept, place or route wagers and holds no user funds (by design; must be re-confirmed at each release)
- [x] No real customer data has been collected (no production environment exists)
- [x] No paid data provider, paid infrastructure or store submission has been initiated

## 1. Legal sign-offs [C] [F]

- [ ] Qualified counsel engaged (gaming, privacy, consumer protection/advertising, IP) [B]
- [ ] Written confirmation of licensing/registration position for the launch feature set, state by state (GB-01) [B]
- [ ] Affiliate decision made; if yes, required state registrations/licences obtained before any affiliate link goes live (GB-02)
- [ ] State availability decision recorded (any excluded/geo-restricted states) (GB-03) [B]
- [ ] Terms of Service final and approved [B]
- [ ] Privacy Policy final and approved; matches actual data practices [B]
- [ ] Responsible Gambling page approved; helpline details verified [B]
- [ ] Age-gating approach approved (AG-01) [B]
- [ ] Advertising/marketing rules memo received; banned-claims list confirmed (AD-01…AD-10)
- [ ] Data licence reviewed and signed (DL-01, DL-02) [B]
- [ ] Sync vendor agreement and consent language reviewed (if sync ships) (GB-07)
- [ ] Auto-renewal/subscription flows reviewed (if Premium ships) (SB-01…SB-07)
- [ ] AI disclosure and disclaimers reviewed (AI-C1…AI-C4)
- [ ] UGC terms, guidelines and DMCA process reviewed (if community ships)
- [ ] Trademark clearance for "OddVex" and tagline (DL-07)
- [ ] Policy on real team/league/player/sportsbook names and logos approved (G-12) [B]
- [ ] Breach-notification matrix on file (PR-10) [B]
- [ ] Legal entity, business registrations, tax and insurance confirmed (CP-08)
- [ ] Legal sign-off record stored (who, date, scope, version of documents reviewed)

## 2. Product boundary and honesty

- [ ] Re-verified: no wagering, no funds, no bet-slip execution hand-off in any surface
- [ ] No synthetic/demo data presented as real anywhere in the launch build; or demo surfaces clearly labelled [B]
- [ ] Every odds/score/stat block shows "as of"; stale handling verified against real feed interruptions [B]
- [ ] "Best line" logic verified against real multi-book data; commercial relationships do not influence it (or are disclosed)
- [ ] Features described as "planned" are not marketed as available
- [ ] `/methodology` matches implemented formulas and data sources
- [ ] No accuracy, performance or results claims without substantiation and counsel review (G-14)

## 3. Responsible gambling

- [ ] RG footer (21+, 1-800-GAMBLER) on every web, marketing and mobile surface [B]
- [ ] 21+ gate enforced at signup on web and mobile [B]
- [ ] `/responsible-gambling` live and linked from app settings [B]
- [ ] Assistant distress/guarantee/under-21 behaviours tested [B]
- [ ] Notification copy reviewed for inducement (if notifications ship)
- [ ] Tracker shows losses plainly; no celebratory or chasing prompts [B]
- [ ] Parlay screen shows probability with payout and correlation warning
- [ ] All copy passes BRAND_VOICE banned-claims check [B]
- [ ] No goals/KPIs tied to amount wagered or bet count

## 4. Privacy and data

- [ ] Data inventory reconciled with actual implementation and vendors [B]
- [ ] Self-serve account deletion works end-to-end on web and in the mobile apps [B]
- [ ] Data export works [B]
- [ ] Retention schedule implemented (logs, backups, analytics) [B]
- [ ] Sub-processor list published; DPAs signed with each vendor [B]
- [ ] Analytics events audited: no emails, stakes, notes or assistant text [B]
- [ ] Cookie/consent approach implemented per counsel
- [ ] Privacy contact mailbox live and monitored [B] [F]
- [ ] No sportsbook credentials collected or stored anywhere (code + UI audit)
- [ ] Sync tokens encrypted; disconnect revokes at vendor (if sync ships)
- [ ] LLM provider terms confirm no training on OddVex data and acceptable retention (if LLM ships)
- [ ] Process for suspected under-21 accounts documented [B]

## 5. Security

- [ ] SECURITY_BASELINE M1 verification checklist complete [B]
- [ ] All M2+ baseline controls implemented for production [B]
- [ ] Admin accounts use MFA; admin actions audit-logged [B]
- [ ] Secrets in managed store; none in repo history (full-history scan) [B]
- [ ] Dependency, secret and static scans clean or exceptions risk-accepted [B]
- [ ] Rate limiting and abuse controls load-tested [B]
- [ ] Backups automated; restore test passed with recorded RTO/RPO [B]
- [ ] Independent penetration test completed; findings resolved or risk-accepted by Founder [F]
- [ ] Security contact and `security.txt` published
- [ ] Access review complete; least privilege confirmed [B]

## 6. Reliability and operations

- [ ] Production environment provisioned and documented [B] [F]
- [ ] Staging mirrors production; deploy and rollback rehearsed [B]
- [ ] Monitoring, alerting and on-call roster active [B]
- [ ] Data freshness monitors and feed kill switches in place [B]
- [ ] Feature flags / kill switches for assistant, sync, alerts
- [ ] Incident response tabletop completed [B]
- [ ] Load test at expected launch traffic (targets to be set)
- [ ] Performance budgets met on reference devices (NFR-20…NFR-25)
- [ ] Status page or in-app incident banner available
- [ ] Database migration plan reviewed; no pending destructive migrations without approval [F]
- [ ] Cost monitoring and budget alerts configured [F]

## 7. Quality and accessibility

- [ ] All M1…launch-scope acceptance criteria in the PRD verified
- [ ] Automated test suites green; critical user journeys (J1–J10) covered end-to-end [B]
- [ ] Calculator reference vectors pass on web, API, assistant and mobile [B]
- [ ] Assistant grounding test: 100 % of numbers traceable to tool output [B]
- [ ] WCAG 2.2 AA audit (automated + manual screen reader) complete for web; issues resolved or documented
- [ ] Mobile a11y pass (VoiceOver, TalkBack, font scaling, contrast, targets)
- [ ] Cross-browser/device matrix tested
- [ ] All screens implement loading / empty / stale / error states
- [ ] Copy review complete (US English, tone, no placeholder text)
- [ ] 404/500 pages and offline states verified

## 8. Store-submission preparation [F]

Apple App Store
- [ ] Organisation developer account under the correct legal entity
- [ ] Current App Review Guidelines re-read (gambling, account deletion, subscriptions, UGC, privacy sections) and gaps closed
- [ ] App Review notes drafted: app does not accept wagers; data sources and licences; how sync works
- [ ] Demo account for reviewers with representative data
- [ ] Age rating questionnaire completed accurately
- [ ] App privacy details ("nutrition labels") match data inventory and SDKs
- [ ] In-app account deletion present and discoverable
- [ ] Privacy Policy and Terms URLs live; support URL live
- [ ] In-app purchase products configured and tested; subscription disclosures on paywall (if Premium ships)
- [ ] Screenshots/preview show real app UI with licensed or fictional data; no misleading claims
- [ ] Push notification permission requested in context, not at first launch
- [ ] App Tracking Transparency position confirmed (no tracking, or prompt implemented)
- [ ] Export-compliance (encryption) questions answered
- [ ] TestFlight beta completed with approved testers

Google Play
- [ ] Organisation developer account verified
- [ ] Current Play policies re-read (real-money gambling, UGC, subscriptions, account deletion, AI content) and gaps closed
- [ ] Any gambling-related declaration/application the policy requires for this app type identified and completed
- [ ] Content rating (IARC) questionnaire completed accurately
- [ ] Data safety form matches data inventory and SDKs
- [ ] Account deletion: in-app path and web deletion URL provided
- [ ] Target audience set to adults; no child-directed declarations
- [ ] Play Billing configured and tested (if Premium ships)
- [ ] Target API level and other technical requirements met
- [ ] Closed/internal testing track completed per Play requirements for the account type
- [ ] Store listing assets and copy approved (APP_STORE_LISTING_DRAFT)

Both
- [ ] Listing copy passes banned-claims check; includes "does not accept wagers" and 21+
- [ ] Country availability set per Founder decision (US only at launch unless decided otherwise)
- [ ] Outbound sportsbook link behaviour consistent with each store's policy (or disabled in app)
- [ ] Founder approval recorded for submission (G-04)

## 9. Monetisation (only if Premium ships at launch) [F] [C]

- [ ] Pricing approved (G-07)
- [ ] Payment processor approved the business category
- [ ] Pre-purchase disclosures, consent capture, confirmation email, renewal reminders implemented per counsel
- [ ] Online cancellation at least as easy as signup; tested
- [ ] Refund policy published
- [ ] Entitlements enforced server-side; restore purchases works
- [ ] Sales-tax handling confirmed

## 10. Community (only if it ships at launch) [C]

- [ ] Community guidelines published
- [ ] Report, block, mute functional; moderation queue staffed with response-time targets
- [ ] Automated filtering for prohibited content in place
- [ ] Appeals process documented
- [ ] DMCA agent registered and takedown process live

## 11. Marketing and support [F]

- [ ] Launch plan approved; every external action individually approved (G-05)
- [ ] Ad-platform certifications obtained where required before any paid campaign
- [ ] Affiliate/influencer disclosures in place (if used)
- [ ] Email sending domain authenticated (SPF, DKIM, DMARC); unsubscribe works; physical address in footer per counsel (G-06)
- [ ] Support channel staffed; help centre content complete; macros for deletion, RG, data questions
- [ ] Press/boilerplate reviewed for claims
- [ ] Analytics dashboards for launch funnel ready; north-star definition agreed

## 12. Go / no-go

- [ ] All sections above complete or explicitly waived in writing by the Founder (waivers listed below)
- [ ] Rollback plan documented and rehearsed
- [ ] Go/no-go meeting held; decision recorded

| Waiver # | Item | Reason | Approved by | Date |
|---|---|---|---|---|
| | | | | |
