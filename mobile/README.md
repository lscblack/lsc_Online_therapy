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

Native builds are possible but need platform tooling. `flutter build apk`
requires the Android SDK with accepted licenses (`flutter doctor
--android-licenses`); iOS needs Xcode. Voice needs the microphone permission,
already declared (`RECORD_AUDIO` on Android, `NSMicrophoneUsageDescription` on
iOS). Native device runs have not been verified here; the web build is the
verified target.

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
