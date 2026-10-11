# Ubuzima (Flutter app)

A calm, private health companion for young people: chat, voice, onboarding
and settings (theme, language, edit profile, delete my data). Talks to the
Ubuzima backend over HTTP/SSE.

## Setup

```sh
cd app_flutter
flutter pub get
```

## Run (web)

Start the backend (it listens on port 8099 in the dev setup), then:

```sh
flutter run -d chrome --dart-define=API_BASE=http://127.0.0.1:8099
```

`API_BASE` is the backend base URL; it is read at compile time through
`--dart-define`.

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
