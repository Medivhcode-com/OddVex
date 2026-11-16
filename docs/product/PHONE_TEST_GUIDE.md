# Real-phone test guide

Verified against the build branch at c044583, 2026-11-16. This guide is preparation; the mobile app has not been tested on physical hardware in this session.

## Choose a compatible client

The repo's apps/mobile/package.json uses Expo ~58.0.25. Current official Expo guidance says Apple App Store Expo Go stops at SDK 54. Installing that store app alone will not run this SDK 58 project on an iPhone.

- iPhone: prepare an SDK 58 development build, or eas go through an internal TestFlight team after Apple Developer enrollment. EAS project/build profiles and store identifiers still need configuration.
- Android: select an SDK 58-compatible build from https://expo.dev/go .

Official compatibility instructions: https://docs.expo.dev/troubleshooting/expo-go-version-mismatch/ .

Fix the current missing analytics screen/import and obtain passing mobile lint, types, tests and bundle checks before treating the build as ready for a device.

## Start the local API and Metro

Use a computer and phone on the same trusted Wi-Fi. Requirements: Node 22+, pnpm 10 and Python 3.13 as documented by this repo. Use a supported free port if 8000 conflicts locally.

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

Use the actual computer LAN IP. localhost on a physical phone points to the phone itself. Restart Metro after editing the environment. Scan the QR using the compatible client. Release builds require HTTPS.

## Evidence to return

| Area | Check on each phone |
| --- | --- |
| Navigation | Open every tab and game/prop detail; back navigation preserves context. |
| Account | Sign up with 21+ confirmation, sign in/out, show/hide keyboard and delete a synthetic account. |
| Research | Verify fictional/synthetic labels, freshness, loading, empty and API error states. |
| Tracking | Add, edit and settle a synthetic bet; compare payout and analytics. |
| Accessibility | Read labels with VoiceOver/TalkBack; use large text and both themes. |
| Layout | Capture clipped text, overlapping controls, unusable scroll areas and safe-area problems. |

Record device model, OS, client/build version, commit, steps, expected result, observed result and screenshots. Keep credentials, session tokens and personal notifications out of screenshots.
