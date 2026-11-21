# Counsel-review addendum — 2026-11-16

> **Superseded on 2026-11-21. Do not send.** `COUNSEL_REVIEW_PACKET.md` was reissued on 2026-11-21 from the code at
> commit `2b0c7c1` and replaces both the packet pinned below and this addendum; its section 0 lists what changed.
> In particular the hosting row below is out of date: the Vercel and Neon preference was replaced by the Hostinger
> server (decision D-016 in `docs/product/DECISION_LOG.md`), and a private preview has run there since 2026-11-18
> (D-021). The text below is kept unchanged as the record of what was written on 2026-11-16.

Prepared by product/engineering; no legal opinion or sign-off. Read with COUNSEL_REVIEW_PACKET.md at commit c044583f9d1dd063311aff71d296fe62a04f04df. The original packet has not been sent. This addendum prevents stale implementation statements being presented as current facts.

## Corrections verified against the same build revision

| Packet statement | Current source at c044583 | Consequence for review |
| --- | --- | --- |
| Section 3.5: public privacy draft omits watchlists, alerts, notifications, staking reminder and retained audit IPs | apps/web/src/app/(marketing)/privacy/page.tsx now discloses these, stored unsent account messages, and security-log retention after deletion. It still says retention is to be confirmed before launch. | Review the current source draft; the earlier omission report is stale. Retention, deletion and restore policy still need review. |
| Section 4: responsible-gambling page has no draft banner | apps/web/src/app/(marketing)/responsible-gambling/page.tsx contains a DraftBanner immediately above OddVex commitments. The banner applies to commitments rather than the help information above it. | Review current wording and placement; do not report the banner as absent. |
| Section 2.4: no hosting account or infrastructure exists | The founder connected Vercel and Neon; a free Neon preview project/database was created and SELECT 1 verified. Vercel team access is blocked; no application deployment or customer launch was completed in this session. | Distinguish a provisioned preview database from deployed production. |
| Section 2.4: no provider account/key exists | A historical vendor key-issuance email exists. Its present plan/entitlement is unverified and no paid plan was bought by this work. | Do not claim current licensed access; an old issued key is not licence approval. |

## Requested scope remains

Please review Terms, Privacy Policy, Responsible Gambling commitments,21+ mechanism, state-by-state service eligibility, and the Apple/Google listing. Please separately assess sportsbook affiliate links, subscriptions, community, security-log retention, deletion/restores and the proposed data licence. Return exact redlines and written conditions with reviewed commit/version.

## Engagement and disclosure status

Recommended intake lead: Michelle W. Cohen at Ifrah Law, with gaming-regulatory colleagues as needed. This recommendation is based on the firm's published practice profile, not a completed bar-directory or conflicts check.

The prepared quote request is an unsent Gmail draft. Automatic approval review rejected sending the packet to a specific lawyer not yet approved by the founder. No lawyer was engaged, fee authorized, agreement accepted or sign-off received. Obtain recipient approval, conflicts clearance, legal client/entity details, scope, fee cap and engagement before billable work.
