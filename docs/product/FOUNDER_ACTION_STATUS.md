# OddVex founder action status

Updated: 2026-11-16 (America/Los_Angeles). Work item: MED-71.

> Note added 2026-11-21: this receipt is a record of 2026-11-16 and is not kept up to date. The counsel packet it
> refers to was reissued on 2026-11-21 from the code at commit `2b0c7c1`
> (`docs/compliance/COUNSEL_REVIEW_PACKET.md`, section 0 lists what changed); the packet pinned at `c044583` and the
> addendum of 2026-11-16 are superseded and must not be sent. Hosting moved to the Hostinger server (D-016), where a
> private preview runs (D-021). Current state: `docs/product/BUILD_STATUS.md` and `docs/product/DECISION_LOG.md`.

This is an execution receipt, not a launch approval. The founder asked to work on the eight actions in parallel. No paid purchase, legal engagement, store enrollment, production deployment or real customer email was completed in this session.

## Verified source state

- Main inspected at bdd77a5bdb9f1b53ca5998ada2f6860cd4bf720b.
- The active build is draft PR #10, head c044583f9d1dd063311aff71d296fe62a04f04df. Its counsel packet and decision log are absent from main.
- PR #10 was not modified or merged by this work. Code and earlier test counts must be described at their actual revision.

## Eight actions

| Action | Completed in this session | Remaining dependency |
| --- | --- | --- |
| 1. Legal review | Reviewed the current packet; researched Ifrah Law, Dickinson Wright and Duane Morris; prepared a scoped quote request to Michelle W. Cohen at Ifrah Law in the founder's Gmail. Prepared an addendum correcting packet drift. | The email was NOT sent. Automatic approval review rejected disclosure to a lawyer not specifically approved as recipient. Founder approval of Michelle and the packet/addendum is needed. Conflicts, legal client details, fee cap and signed engagement remain outstanding. No counsel sign-off or lawyer turnaround is confirmed. |
| 2. Data provider | Verified current official prices and terms. Provisional procurement choice: The Odds API 5M plan, USD 119/month, subject to licence clarification and spending confirmation. A licence-clarification email is saved as an unsent Gmail draft. | Paid subscription, written confirmation that OddVex's paid comparison/analytics use fits the terms, current account-plan verification and secure credential entry remain incomplete. An older provider key-issuance email exists; this does not prove current paid access. Do not reuse the old key. |
| 3. Organization store accounts | Verified organization requirements and fees: Apple USD 99/year; Google Play USD 25 once. | Exact registered legal entity, formation jurisdiction, registered address, D-U-N-S, domain contact channels, signatory authority, account authentication, agreements and payment. No enrollment was submitted. A brand/trade name alone does not satisfy Apple's organization rule. D-U-N-S can add up to 30 days. |
| 4. Hosting | Vercel and Neon connections established. Created oddvex-preview on Neon's verified Free organization, PostgreSQL 16, AWS us-west-2. The preview branch is ready and a read-only SELECT returned connectivity_ok=1. | Vercel's medivh-code scope returns 403 until team access is authorized. No Vercel project/deployment was changed. No app migration, application connection or private preview was completed. Payment methods were not added. |
| 5. Email | Verified that current Resend supports shared Inboxes; its free tier includes three inboxes and can fit support@oddvex.com, privacy@oddvex.com and security@oddvex.com at low volume. | Resend account/authentication and domain-DNS access; actual DKIM/SPF/receiving records, inbox creation and monitored receipt/reply tests. Do not publish the addresses as working yet. The current API's Resend sender is still unimplemented. |
| 6. Real-phone testing | Confirmed the repo uses Expo SDK 58. Added PHONE_TEST_GUIDE.md with a compatible-client path and LAN-API setup. | Physical iPhone/Android access and compatible development client. App Store Expo Go stops at SDK 54 according to current Expo docs; the checklist's simple iPhone install instruction is insufficient. No physical-device test or screenshot was produced. |
| 7. GitHub | Closed Dependabot PRs #3, #5 and #6 using the connected GitHub account. Verified main is unprotected and the repository owner is a personal User account. | GitHub browser authentication failed; branch protection was not changed. Personal accounts cannot contain GitHub teams; supply actual reviewer usernames or separately choose an organization migration. The placeholder CODEOWNERS team was not treated as real. |
| 8. Founder decisions | Read DECISION_LOG.md from the build branch, including D-007. Recorded the current request and unresolved business choices without inventing approvals. | Founder answers remain needed for affiliate revenue, web-first versus simultaneous launch, community on/off, and Premium price/inclusions. No billing or price was activated. |

## Infrastructure receipt

| Field | Value |
| --- | --- |
| Neon project | shy-violet-89932177 (oddvex-preview) |
| Neon branch | br-bold-moon-bft55a2b (preview; default; ready) |
| Database / role | oddvex / oddvex_app |
| Engine / region | PostgreSQL 16 / aws-us-west-2 |
| Plan | Organization free; project owner subscription free_v3 |
| Compute bounds | 0.25 to 0.25 CU |
| Verification | SELECT 1 returned connectivity_ok=1; server_version 16.16 |
| Schema/migrations | Not run; the app is not connected |

No connection string, API key, password, sign-in code or temporary authorization link belongs in this file. The provider rejected a requested suspend-interval override on the free account; provisioning succeeded with account defaults, without a plan upgrade.

## Build state (updated after this receipt was written)

The blocker recorded here at commit `c044583` is resolved. The missing mobile analytics screen landed, the remaining
mobile checks passed, and pull request #10 was merged to `main` on 2026-11-16 with all eight CI jobs green. The
community module now exists in code and is switched off by default; see `BUILD_STATUS.md`.

## Handoff and next inputs

1. Approve or replace Michelle W. Cohen (michelle@ifrahlaw.com) as the legal recipient, and approve sharing the counsel packet as reissued on 2026-11-21 (`docs/compliance/COUNSEL_REVIEW_PACKET.md`; the packet pinned at `c044583` and its dated addendum are superseded). The unsent Gmail quote-request draft refers to the old packet and must be rewritten before use. Obtain her actual quote before committing to a fee.
2. Confirm legal entity and D-U-N-S details through provider intake, and authorize the specific known recurring/one-time costs and payment route. No card or credential should be pasted in chat.
3. Complete Vercel team-access authorization and GitHub authentication; then re-check actual project, billing and protection state.
4. Answer: affiliate revenue yes/no; web first/both; community on/off; Premium price and included features. A practical launch recommendation is web first with community and sportsbook affiliate links disabled pending review; this remains a recommendation.
5. The build session's handoff must include the packet corrections, free Neon receipt and remaining deployment/email work. (The failed mobile import is fixed.) Preserve counsel's eventual requested changes verbatim before implementing them.

## Primary references

- Counsel packet, reissued 2026-11-21: `docs/compliance/COUNSEL_REVIEW_PACKET.md` (on `main` once PR 20 is merged; until then `main` holds the 2026-11-16 version)
- [Counsel packet as pinned on 2026-11-16 (superseded, do not send)](https://github.com/Medivhcode-com/OddVex/blob/c044583f9d1dd063311aff71d296fe62a04f04df/docs/compliance/COUNSEL_REVIEW_PACKET.md)
- [Decision log, pinned build revision](https://github.com/Medivhcode-com/OddVex/blob/c044583f9d1dd063311aff71d296fe62a04f04df/docs/product/DECISION_LOG.md)
- [Michelle Cohen, Ifrah Law](https://www.ifrahlaw.com/team/michelle-cohen/)
- [Apple organization enrollment](https://developer.apple.com/help/account/membership/program-enrollment/)
- [Google organization requirements](https://support.google.com/googleplay/android-developer/answer/13628312?hl=en)
- [Google enrollment fee](https://support.google.com/googleplay/android-developer/answer/6112435?hl=en)
- [Resend pricing](https://resend.com/pricing)
- [Resend Inboxes](https://resend.com/docs/api-reference/inboxes/create-inbox)
- [Resend receiving domains](https://resend.com/docs/dashboard/receiving/custom-domains)
- [Vercel FastAPI support](https://vercel.com/docs/frameworks/backend/fastapi)
