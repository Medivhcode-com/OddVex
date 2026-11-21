# OddVex — Pre-launch audit, 2026-11-19

Written: 2026-11-21 · Prepared by: the build session, not by lawyers or an outside auditor · Code described: commit
`2b0c7c1` (pull request 19, deployed to the private preview on 2026-11-21 at 05:29 UTC), plus the documents of pull
request 20 where a row says so. Pull request 20 was **not merged** when this was written.

> Not legal advice and not an independent audit. The findings were produced and checked by automated reviewers working
> for the build session. Nothing here has been reviewed by counsel, a security firm or a responsible-gambling
> specialist.

## 1. Why the audit was run

A private preview went live on 2026-11-18: `preview.oddvex.com` behind a password and `api-preview.oddvex.com` open to
the internet, accepting sign-ups (`docs/product/DECISION_LOG.md`, D-021). Before anything public, the Founder's build
session audited the whole repository and the live configuration, then fixed what it found. Several findings could be
used against the preview while they were open.

## 2. Method

1. **Find.** Three audit groups looked at nine dimensions, which are the prefixes of the finding ids:
   API (`api-auth`, `api-data`, `quant-data`); Web and compliance (`web-product`, `web-security`, `compliance`);
   Mobile, deployment and documents (`mobile`, `deploy-ops`, `docs-truth`). Each finding states its evidence (file and
   line), a scenario and a proposed fix.
2. **Check.** Every finding went to independent checkers who traced the code, judged who could reach it, or reproduced
   it: three checkers for 6 findings, two for 30, and one for 16 (all 16 rated low by the auditor; the checker raised
   two of them to medium). Every one of the 52 was confirmed as real. Checkers could change the severity; the severity
   below is the one after checking. Where checkers disagreed, the majority was taken (api-auth#2 critical, quant-data#1
   high); where two checkers split, the lower was taken (deploy-ops#4 and quant-data#5, low). The checkers' notes listed traps and the tests and documents pinned to the old
   behaviour.
3. **Fix in lanes.** The fixes were grouped into lanes by the files they touch. In each lane an engineer first wrote a
   test that failed for the reason the finding gave, then made the change and saw the test pass. Two reviewers then
   tried to break the lane (one attacking the fix, one judging the tests), and the engineer repaired what they found,
   for up to three rounds. Documentation-only findings needed no failing test. Exceptions, recorded so the method is
   not overstated: usage limits cut some review rounds short (the web security lane's second round had one of two
   reviews); the assistant lane was not approved after three rounds, because each review found new wordings the
   rules missed, and was closed by one bounded pass with a fixed list of items and one verifier, with further misses
   recorded as known (section 5).
4. **Release check.** The approved lanes were combined, the API schema and client types regenerated, and every suite
   run on the combined code: API 4,627 tests passed on SQLite (4 skipped, PostgreSQL-only) and 4,636 on PostgreSQL
   (1 skipped); web lint, types, 195 unit tests, build and 387 of 387 end-to-end tests against the working-tree API;
   mobile lint, types, 528 tests and the bundle export; 168 infrastructure tests; a secret pre-check. One reviewer
   approved it. Continuous integration then passed 9 of 9 jobs (these figures are as the lanes and the release check
   reported them; they were not re-run for this report), pull request 19 was squash-merged as `2b0c7c1`
   (D-028) and deployed. The server checks after that deploy are in `docs/product/BUILD_STATUS.md`.

Pull requests:

| PR | State | What it carried |
|---|---|---|
| 17 | Merged 2026-11-19 (`9a2a9bc`) | Bounded password hashing |
| 18 | Merged and deployed 2026-11-19 (`4092395`) | Mobile fixes, web security fixes, server scripts |
| 19 | Squash-merged and deployed 2026-11-21 (`2b0c7c1`) | API fixes, assistant safeguards, web product pages |
| 20 | **Open, not merged** | Client screens that use the new API fields, and the documents (this report among them) |

## 3. Findings

Status values: **fixed** (the defect described is gone at `2b0c7c1`, or in the documents of PR 20 where the row says
so); **partly** (some of it remains, see the last column); **open** (not changed); **documented** (the behaviour is
kept on purpose and written down, usually pending a decision). "Applies" in the audit's own terms is not repeated
here; every row was checked against the code at `2b0c7c1` for this report.

| Id | Finding | Severity | Status | PR | What remains |
|---|---|---|---|---|---|
| api-auth#1 | Twenty parallel sign-ins or sign-ups ran the API out of memory, and each crash emptied the rate limiter | critical | fixed | 17 | At most `ODDVEX_PASSWORD_HASH_CONCURRENCY` (default 2) hashes run at once; the rest wait up to 1 s, then get 429 with `Retry-After`, as a rate-limited request does. Rate-limit counts are still in memory and reset on restart |
| api-auth#2 | An account anyone can create could store unlimited data, then crash the API with one export | critical | partly | 19 | Done: 5,000 bets per account, per-user write and export limits, streamed export, the assistant's bet summary no longer loads every bet. Remaining: the preview API host is open to the internet; sign-ups are limited per IP address only, so one person can make many accounts; the database connection pool (5 plus 10) is smaller than the request thread pool; watchlist, alert and notification writes have no per-user limit; a streamed response has no send timeout |
| api-auth#3 | Anyone who knew an email could keep its owner signed out, with password reset off in production | medium | partly | 19 | Failures now count per email and client network (8) and per email overall (50). Someone with about seven networks can still keep one email refused; reset is still off in production. Recovery for the operator: `infrastructure/RUNBOOK.md` section 4.4 |
| api-auth#4 | The runbook described a read-only, promote-only, unaudited admin role | medium | fixed (PR 20) | 20 | Runbook admin section rewritten in PR 20 (docs-ops lane); not merged |
| api-auth#5 | A failed database statement logged its bound values (password hashes, emails); a NUL character could trigger it | low | fixed | 19 | Statement values hidden in logs; NUL refused before any route runs |
| api-auth#6 | With `ODDVEX_TRUST_PROXY=true` the API trusts `X-Forwarded-For` from any peer on the shared network | low | documented | 20 | Code unchanged. Risk and two options recorded in `THREAT_MODEL.md` S-6, deferred on 2026-11-21; Founder decision O-18 in the decision log |
| api-data#1 | A moderated profile or pick could be put back by its author in one request | medium | partly | 19, 20 | API fixed: an author's edit returns the content to the queue; staff can restore. The web restore action and the copy that promised an edit brings content back are changed in PR 20. Community is switched off |
| api-data#2 | A suspension was erased by deleting the account and registering again | low | fixed | 19 | The handle of a suspended account is reserved on deletion. A new email with a new handle still gets back in; no email fingerprint is kept (owner question OQ-12) |
| api-data#3 | A stake below half a cent was saved as 0.00 and broke the bet list and export | low | fixed | 19 | — |
| api-data#4 | A parlay priced at 10,000,000,000 or more passed validation but could not be stored on PostgreSQL | low | fixed | 19 | Same bounds applied to alert thresholds and community pick prices |
| api-data#5 | Deleting reported content left moderators nothing to judge | low | partly | 19, 20 | The API keeps a copy of the reported text and returns it; the admin screen shows it in PR 20. Retention of the copies is OQ-12 |
| api-data#6 | The leaderboard orders by win rate alone, so heavy-favourite pickers rank first | low | documented | 19, 20 | Order unchanged by decision; the method text says price is not part of it and each row carries average price and flat-stake return (screens show them in PR 20). Decision needed before `community_leaderboard` is switched on (OQ-13) |
| quant-data#1 | `/v1/props?market=*` emptied the prop board for every user through the cache | high | fixed | 19 | Checked on the server after the deploy: answers `[]` and the full board still loads |
| quant-data#2 | In live games the value screen and best-price marks compared quotes of different ages | high | fixed | 19 | One staleness rule everywhere, including quotes made before the latest score change. A live vendor must report score-change times or the 120 s threshold must come down (OQ-17). Reads are cached up to 10 s |
| quant-data#3 | A very short price was saved as 1.000000 despite a 422, breaking the bet list; calculators answered 500 on extreme input | medium | fixed | 19 | — |
| quant-data#4 | Synthetic final scores were not drawn from the pricing model, contradicting "no real edge" | medium | fixed | 19 | Calibration test over 3,000 games (`services/api/tests/test_audit_board_calibration.py`). The preview database holds bets graded on the old scores (OQ-18) |
| quant-data#5 | A quote with no timestamp, or one in the future, never went stale; the vendor normaliser let malformed fields through | low | fixed | 19 | Strict vendor text rules may reject some real names with invisible joiners; confirm with a vendor |
| quant-data#6 | The moneyline chart plotted American odds on a linear axis | low | fixed | 19 | — |
| web-product#1 | Same chart defect on the web, showing prices that cannot exist | medium | fixed | 19 | Labels stay American in Decimal mode; earlier prices only in hover tooltips on touch screens (OQ-19) |
| web-product#2 | Below 1024 px the web app showed no 21+, no-wagers and helpline line | low | fixed | 19 | — |
| web-product#3 | The responsible-gambling page stated unverified helpline facts | medium | fixed | 19 | Wording and the "checked on" date need Founder and counsel review (OQ-07) |
| web-product#4 | The tracker listed only the 50 newest settled bets | medium | fixed | 18, 19 | Mobile reads at most 1,000 open bets and says so |
| web-product#5 | Methodology and help claimed a combined probability the parlay tool never shows; the screen printed an API note asking for impossible input | medium | partly | 19, 20 | Pages and the API (`probability_status`) fixed. At `2b0c7c1` the web and mobile screens still read "Combined probability: Not shown" with the raw API note; PR 20 replaces them |
| web-product#6 | The pricing page published free-versus-paid packaging as fact | low | fixed | 19 | Settings still shows "Plan: Free" (OQ-16) |
| web-security#1 | A tab after the first slash got an off-site address past `safeNext` | medium | fixed | 18 | — |
| web-security#2 | An encoded slash bypassed the `/api/ov` allow-list | medium | fixed | 18 | — |
| web-security#3 | Every unknown `/blog/<anything>` was rendered, cached and written to disk | medium | fixed | 18 | — |
| web-security#4 | The error screen could never say the data service was unreachable in a production build | low | fixed | 18 | — |
| web-security#5 | A revoked session cookie was never cleared | low | fixed | 18 | When the API is also failing, the person lands on the login page and the cookie is kept |
| compliance#1 | The assistant had none of the documented responsible-gambling behaviours | medium | partly | 19, 20 | Fixed rules for crisis, under 21, distress and certainty, and a help sentence with the helpline and 988 on every answer that is not a support reply. The rules miss some wordings (`KNOWN_MISSES`, and threats such as "im going to shoot up my school", found after release). The AG-03 under-21 flag is not built. Support card on the clients and the documents in PR 20. Wording needs review (OQ-08) |
| compliance#2 | Every surface gave 1-800-GAMBLER, the Council on Compulsive Gambling of New Jersey's line, and called it the national helpline | medium | fixed (PR 20) | 18, 19, 20 | Code gives 1-800-MY-RESET (1-800-697-3738), text 800GAM, 988 and 911. Documents corrected in PR 20; at `2b0c7c1` `docs/compliance/RESPONSIBLE_GAMBLING.md` and `docs/product/SUPPORT_READINESS.md` still called the New Jersey line the national helpline, and nine more documents gave 1-800-GAMBLER as the helpline without naming it (COMPLIANCE_OVERVIEW, LAUNCH_READINESS_CHECKLIST, the counsel packet, APP_STORE_LISTING_DRAFT, BRAND_VOICE, PRODUCT_REQUIREMENTS, ROADMAP, SCREEN_MAP, USER_JOURNEYS), so this row is partly fixed at `2b0c7c1` alone. The only Android test APK predates the fix (OQ-20). Facts must be checked again before each release |
| compliance#3 | The privacy page misdescribed the export and what deletion leaves | medium | fixed | 19 | The page now says what the export omits and what is kept. Nothing removes audit entries (IP addresses kept with no end date, OQ-10); backups keep deleted accounts about 14 days plus pre-deploy copies (OQ-15) |
| compliance#4 | A suspended user could not export or delete their data, though the API description said they could | medium | partly | 19, 20 | Staff export and delete routes exist in the API. Their web screens and the suspended notice are in PR 20. No administrator exists on the preview and the procedure is not written (OQ-09) |
| compliance#5 | Below 1024 px no 21+ or helpline line; no help link on tracker and sync | low | fixed | 18, 19 | — |
| compliance#6 | The API logged every request twice, the second time with its query string | medium | fixed | 18, 19, 20 | Access log off in the server command and cleared by the application. Lines written before the 2026-11-19 deploy may still exist; container logs have no retention rule. Documents in PR 20 |
| deploy-ops#1 | The API's 768 MB memory limit was below what a small sign-in burst needs | high | fixed | 17 | Fixed by bounding concurrent hashing (api-auth#1); the limit itself is still 768 MB |
| deploy-ops#2 | A release could not be rolled back after a migration; a failed deploy left the preview down | medium | fixed | 18 | Rollback and the automatic put-back have not been exercised on the server |
| deploy-ops#3 | OddVex containers answered to `api` and `web` on the network shared with other projects | low | fixed | 18 | Checked on the server after the deploy |
| deploy-ops#4 | Image builds ran uncapped at normal priority | low | fixed | 18 | The build ceiling has not yet been seen holding a real build |
| deploy-ops#5 | The operations documents said nothing was deployed and described old behaviour | medium | fixed (PR 20) | 20 | Corrected in PR 20 (docs-ops lane); not merged |
| deploy-ops#6 | The backup loop pruned old dumps while new ones failed; no dump before a deploy's migrations | low | fixed | 18 | A restore has been rehearsed in tests only; all dumps are on the same server |
| mobile#1 | A rejected or expired token on Save discarded what was typed | medium | fixed | 18 | — |
| mobile#2 | The store preparation document said the build had no user-generated content, and other stale facts | medium | fixed (PR 20) | 20 | `docs/marketing/STORE_SUBMISSION_PREP.md` corrected in PR 20. Whether switched-off community screens must be declared is counsel question 26 |
| mobile#3 | The preview APK is signed with the public debug key and no document said so | low | documented | 18 | Kept on purpose for the Founder's own phone; `apps/mobile/README.md` "Builds" says so |
| mobile#4 | The "Synthetic data" badge disappeared when the one start-up call failed | low | fixed | 18 | — |
| mobile#5 | A bet save that timed out on the phone could already be saved, and the retry recorded it twice | low | partly | 19, 20 | The API accepts a client request id and stores a retry once. The mobile and web clients send it in PR 20 |
| docs-truth#1 | `infrastructure/hostinger/.env.example` said listed admin emails get the role at sign-up, which on the open API gives it to whoever registers first | medium | fixed | 18, 19, 20 | Role needs a listed and verified address; first administrator from `services/api/scripts/bootstrap_admin.py`. Remaining questions on that command (OQ-11). Documents in PR 20 |
| docs-truth#2 | The counsel packet marked ready to send, and its addendum, described a product that no longer exists | medium | fixed (PR 20) | 20 | Packet reissued from `2b0c7c1` with a list of what changed; addendum marked superseded. Not sent; counsel not chosen |
| docs-truth#3 | Decision log, build status, launch checklist and infrastructure README said nothing was deployed | medium | fixed (PR 20) | 20 | Corrected in PR 20 (decision log and build status by the docs-ops lane; the launch checklist, privacy, incident, support and roadmap documents by this lane). Whether anyone outside the team has signed up is unknown |
| docs-truth#4 | The decision log records a standing waiver of every gate, which the constitution says cannot exist | medium | documented | 20 | An amendment note in the constitution and decision D-029 let the two be read together; they do not settle the conflict. Founder decision O-17 |
| docs-truth#5 | Runbook, rollback plan and threat model described the code before PR #10 | medium | fixed (PR 20) | 20 | Corrected in PR 20 (docs-ops lane); not merged |
| docs-truth#6 | Mobile documents said Expo Go on an iPhone opens the app and that no EAS profiles exist | medium | partly (PR 20) | 20 | Store prep, screen map and the phone test guide corrected in PR 20. Still saying Expo Go: `apps/mobile/README.md` ("Run it") and decision-log row O-02, outside this lane |

Counts: 2 critical, 3 high, 27 medium, 20 low. As the table stands, with PR 20's documents as they are in the working
tree: 39 fixed (7 of them only fully through PR 20), 9 partly (1 of them only through PR 20), 4 documented, 0 open. At
`2b0c7c1` alone, before PR 20: 32 fixed, 9 partly (compliance#2 among them: its code was fixed, its documents were not), 2 documented (api-data#6, mobile#3) and 9 open, all nine being
documents that PR 20 corrects (api-auth#4, api-auth#6, deploy-ops#5, mobile#2, docs-truth#2 to #6). "Partly" rows
whose remaining part is in PR 20 count as partly in both.

## 4. Open items

Each needs code, a server action or a document outside the audit lanes.

| # | Item | From | Owner |
|---|---|---|---|
| 1 | Merge and deploy PR 20 (client screens and documents); until then rows marked PR 20 stay as described for `2b0c7c1` | Several | Build session |
| 2 | Preview API open to anyone; sign-ups limited per IP only; connection pool smaller than the thread pool; no per-user limit on watchlist, alert and notification writes; streams without send timeout | api-auth#2 | Engineering; Founder (OQ-14, OQ-21) |
| 3 | Sign-in refusal still possible from about seven networks; no password reset in production | api-auth#3 | Engineering; G-06 for real email |
| 4 | API trusts forwarded addresses from any peer on the shared network | api-auth#6 | Founder (O-18) |
| 5 | Assistant rule misses; AG-03 under-21 flag not built | compliance#1 | Founder and counsel (OQ-08) |
| 6 | Audit entries with IP addresses kept with no end date; backups hold deleted accounts; no copy off the server; logs have no retention rule | compliance#3, compliance#6, deploy-ops#6 | Founder and counsel (OQ-10, OQ-15) |
| 7 | Staff export and delete: no administrator on the preview, no procedure | compliance#4 | Founder (OQ-09, OQ-11, O-12) |
| 8 | Rollback, put-back, restore and the build ceiling not exercised on the server | deploy-ops#2, #4, #6 | Operations |
| 9 | Old Android APK shows the old helpline | compliance#2 | Build session (OQ-20) |
| 10 | Live vendor must report score-change times, or the live threshold comes down | quant-data#2 | Founder at G-01 (OQ-17) |
| 11 | Preview database graded on old synthetic scores | quant-data#4 | Founder (OQ-18) |
| 12 | `apps/mobile/README.md` and decision-log row O-02 still describe Expo Go on an iPhone | docs-truth#6 | Mobile and docs-ops owners |
| 13 | The draft `/privacy` page does not mention the server logs (on the preview the API request line holds the proxy's or web server's address, not the visitor's), the shared reverse proxy's own logs (not inspected; may hold visitors' addresses), the assistant's support log record, restore leftovers or copies of reported text | docs-truth#2, compliance#3 | Web owner; Founder and counsel (OQ-22) |

## 5. Decisions for the Founder

Recorded in `docs/backlog/owner-questions.md` (OQ-07 to OQ-22) and in the decision log (O-12, O-17, O-18). Those that
also need counsel are asked in `COUNSEL_REVIEW_PACKET.md` section 6 (questions 15 and 21 to 26).

| Question | Where |
|---|---|
| Responsible-gambling page wording and its "checked on" date; any state helpline text | OQ-07 |
| Assistant reply wording, threats getting the crisis reply when the rules catch them, the under-21 log line, accepting known misses, logging user messages to improve the rules, the AG-03 flag | OQ-08 |
| Staff export and delete procedure, second approver, reason retention | OQ-09 |
| IP addresses and action details kept in the audit log after deletion | OQ-10 |
| First administrator by `services/api/scripts/bootstrap_admin.py`: account takeover, attestation by command, printed password, no admin MFA | OQ-11, O-12 |
| Community: email fingerprint, reserved handles, report copies, look-alike handles, no release route, restore closing all reports | OQ-12 |
| Leaderboard order before it is switched on | OQ-13 |
| Per-account limits and the hourly export cap | OQ-14 |
| Backup retention and an off-server copy | OQ-15 |
| Pricing page wording and "Plan: Free" in Settings | OQ-16 |
| Live data requirement for score-change times | OQ-17 |
| Reseeding the preview database | OQ-18 |
| Chart labels in Decimal mode and touch tooltips | OQ-19 |
| Rebuilding the Android test APK | OQ-20 |
| Keeping the preview's sign-up open under draft legal pages | OQ-21 |
| What the draft `/privacy` page leaves out (server logs and the shared reverse proxy's logs, support log record, restore leftovers, report copies) | OQ-22 |
| What the gate waiver of 2026-11-19 covers | O-17 |
| Forwarded-address trust on the shared server | O-18 |

## 6. For a lawyer

Everything in section 5 that touches personal data, age, the assistant's replies, community content or the store
listings. The counsel packet (`COUNSEL_REVIEW_PACKET.md`) was reissued on 2026-11-21 for this reason and has not been
sent.
