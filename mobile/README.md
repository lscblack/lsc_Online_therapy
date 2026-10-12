# Ubuzima (Flutter app)

A calm, private health companion for young people: chat, voice, onboarding
and settings (theme, language, edit profile, delete my data). Talks to the
Ubuzima backend over HTTP/SSE.

## Setup

```sh
cd mobile
flutter pub get
```

## Run

Start the backend bound to all interfaces so devices on your network can reach it:

```sh
# in backend/
uvicorn app.main:app --host 0.0.0.0 --port 8099
```

Then pick the client address for your target — the app has sensible defaults, and
`--dart-define=API_BASE=...` always overrides:

```sh
# Web / desktop / iOS simulator (default: http://127.0.0.1:8099)
flutter run -d chrome

# Android emulator (default: http://10.0.2.2:8099 — the host loopback)
flutter run -d emulator-5554

# Physical phone on the same Wi-Fi: use the host machine's LAN IP
flutter run --dart-define=API_BASE=http://192.168.1.74:8099   # replace with your IP (hostname -I)
```

`API_BASE` is read at compile time through `--dart-define`. The platform-aware
default lives in `lib/core/config.dart`.

## Build

```sh
flutter build web --dart-define=API_BASE=https://your-backend.example
```

Output is in `build/web/`.

### Android APK for a physical phone

```sh
flutter doctor --android-licenses          # accept once
flutter build apk --release --dart-define=API_BASE=http://<your-LAN-IP>:8099
# output: build/app/outputs/flutter-apk/app-release.apk  — copy to the phone and install
```

**Two things a physical phone needs** (both already handled in this repo):
- **The LAN IP, not a loopback.** A phone can't reach `127.0.0.1` (that's the phone) or
  `10.0.2.2` (that's the Android *emulator*). Pass the host's LAN IP via `--dart-define`.
  Run the backend with `--host 0.0.0.0` and make sure the phone is on the same Wi-Fi
  (no "AP/client isolation" on the router).
- **Cleartext HTTP.** Android blocks plain `http://` by default. `android:usesCleartextTraffic="true"`
  is set in `android/app/src/main/AndroidManifest.xml` so the app can talk to an `http://LAN-IP` backend
  in development. For production use `https://` and remove that flag.

iOS needs Xcode. Voice needs the microphone permission, already declared
(`RECORD_AUDIO` on Android, `NSMicrophoneUsageDescription` on iOS).

## Test

```sh
flutter test
flutter analyze
```

## Backend note

The backend currently runs in fake-provider mode: replies are placeholder
answers, and most health questions return a calm "please see a doctor"
response until an admin approves a knowledge PDF. This is expected, not a bug
in the app.

## Privacy

Tokens are kept in secure storage; chat text and voice transcripts are never
logged. Settings -> Delete my data removes the profile on the server, clears
local credentials and starts fresh onboarding on a new anonymous identity.
