# Real-phone test guide

Checked against commit `2b0c7c1` on 2026-11-21. This guide is preparation: the build session has not run the app on a
phone, and nobody has recorded doing so. Expo facts below come from Expo's own documentation as recorded in the
pre-launch audit (`docs/compliance/PRE_LAUNCH_AUDIT_2026-11-19.md`, finding docs-truth#6); they were not checked again
for this update.

## Choose a compatible client

`apps/mobile/package.json` uses Expo `~58.0.25`. The Expo Go app in Apple's App Store stops at SDK 54, so **Expo Go
on an iPhone cannot open this project.** Do not follow any older instruction that says to scan the QR code with Expo
Go on an iPhone.

| Phone | What works | Needs |
|---|---|---|
| Android | (a) An APK built with the `preview` profile (below). (b) For development against a local API: an SDK 58 build of Expo Go from https://expo.dev/go, or a development build | Nothing paid |
| iPhone | A development build installed on registered devices, or `eas go` through an internal TestFlight team | An Apple Developer Program membership, which does not exist yet (G-02, G-04; `docs/marketing/STORE_SUBMISSION_PREP.md` section 2) |
| iOS Simulator (a Mac) | A simulator build, or `i` in the Metro terminal | Xcode on a Mac; no Apple membership |

Official compatibility instructions: https://docs.expo.dev/troubleshooting/expo-go-version-mismatch/ .

## Android: the preview APK

The EAS project and its build profiles exist: `extra.eas.projectId` in `apps/mobile/app.json` (project
`e1023991-d90d-446e-ad08-64280426b84f`, decision D-020) and `apps/mobile/eas.json`. The app identifier is
`com.oddvex.app` on both platforms.

The `preview` profile builds an Android APK for direct install (`distribution: internal`), with
`EXPO_PUBLIC_API_URL=https://api-preview.oddvex.com` built in, so the phone needs no local API. It sets
`withoutCredentials: true`, so the APK is signed with the public debug key from the Expo template: it is for the
Founder's own phone only, must not be shared or uploaded to a store, and must be uninstalled before installing any
build signed with real credentials (`apps/mobile/README.md`, "Builds").

**The one APK that exists is out of date.** EAS build `e0686e6b-192e-460a-a60b-647ad97f7591` was made from commit
`9bb7677` (2026-11-19 05:30 UTC), before the audit fixes of pull requests 18 and 19. It still shows the old helpline
number and lacks the mobile fixes. Its download link expires on 2026-12-03 (`docs/product/BUILD_STATUS.md`). Build a
new one from `main` before testing.

First build of the preview profile from a computer:

```bash
# Once: install the EAS command-line tool and sign in to the Expo account that owns project e1023991.
# app.json has no `owner` field (D-020), so the build runs under whichever account is signed in;
# it must be the account that owns the project.
npm install -g eas-cli
eas login

# From the repository root
pnpm install
cd apps/mobile
eas build --platform android --profile preview
```

When the build finishes, open its page on expo.dev on the phone and install the APK (Android asks to allow installs
from that source). A build can also be started from the Expo website for a linked GitHub repository; whether that is
set up for this repository is not recorded here.

Do not remove `withoutCredentials` without reading "Builds" in `apps/mobile/README.md` first: the first build after
that creates a private keystore, and phones with the debug-signed build must uninstall it.

## Development against a local API (Android with an SDK 58 client, or a simulator)

Use a computer and phone on the same trusted Wi-Fi. Requirements: Node 22+, pnpm 10 and Python 3.13 as documented by
this repo. Use a free port if 8000 is taken.

```bash
# Repo root, once
pnpm install

# API terminal
cd services/api
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn oddvex_api.main:app --host 0.0.0.0 --port 8000

# Another terminal, repo root
cp apps/mobile/.env.example apps/mobile/.env.local
# Edit EXPO_PUBLIC_API_URL to http://<computer-LAN-IP>:8000
pnpm --filter @oddvex/mobile start
```

Use the actual computer LAN IP. localhost on a physical phone points to the phone itself. Restart Metro after editing
the environment. Scan the QR code with the compatible client from the table above. Release builds require HTTPS.

Before treating a build as ready for a device, the mobile checks should pass: `pnpm --filter @oddvex/mobile lint`,
typecheck, tests and the bundle export (`apps/mobile/README.md`). They passed on the combined code of pull request 19
(`docs/compliance/PRE_LAUNCH_AUDIT_2026-11-19.md`, "Method").

## Evidence to return

| Area | Check on each phone |
| --- | --- |
| Navigation | Open every tab and game/prop detail; back navigation preserves context. |
| Account | Sign up with 21+ confirmation, sign in/out, show/hide keyboard and delete a synthetic account. |
| Research | Verify fictional/synthetic labels, the data-source badge, freshness, loading, empty and API error states. |
| Tracking | Add, edit and settle a synthetic bet; compare payout and analytics. |
| Help | The helpline line on Settings, the tracker and the sync panel reads 1-800-MY-RESET (1-800-697-3738); the call and 988 links open the dialer. |
| Accessibility | Read labels with VoiceOver/TalkBack; use large text and both themes. |
| Layout | Capture clipped text, overlapping controls, unusable scroll areas and safe-area problems. |

Record device model, OS, client/build version, commit, steps, expected result, observed result and screenshots. Keep
credentials, session tokens and personal notifications out of screenshots. An account made on the preview API is a
real account on a live server: use a throwaway address and delete it afterwards.
