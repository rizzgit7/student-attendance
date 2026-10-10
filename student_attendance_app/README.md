# Student Attendance — Android App (Flutter)

Student + teacher mobile client for the attendance API (blueprint §4/§8/§9/§14).

## Stack
Flutter/Dart · Riverpod (state) · Dio (HTTP) · go_router (navigation) ·
flutter_secure_storage (tokens) · intl · connectivity_plus

## First-time setup

Platform folders (`android/`) are already generated in this repo. If you ever
need to regenerate them:

```bash
cd student_attendance_app
flutter create . --platforms=android --project-name student_attendance_app
flutter pub get
```

## Run against a local API

- Android emulator → host machine: default `BASE_URL=http://10.0.2.2:5000` works.
- Real device / production build:

```bash
flutter run --dart-define=BASE_URL=https://your-api.example.com
flutter build apk --release --dart-define=BASE_URL=https://your-api.example.com
```

## Build the signed release APK (§20)

This machine's toolchain: Flutter `D:\flutter`, JDK 17 `D:\jdk-17.0.20.1+1`,
Android SDK `D:\androidsdk`. Set before building:

```bash
export PATH="/d/flutter/bin:$PATH" ANDROID_HOME=/d/androidsdk JAVA_HOME=/d/jdk-17.0.20.1+1
```

Sign the release with the upload keystore (already wired in
`android/app/build.gradle.kts` via `android/key.properties`):

- `android/app/upload-keystore.jks` + `android/key.properties` are git-ignored.
  **Back them up off-machine** — losing the keystore means you can never
  update the app on installed devices.
- Application id: `com.studentattendance.app` — must NOT change after the
  first public install.

Build (replace the BASE_URL with your deployed Vercel URL once known):

```bash
flutter build apk --release --dart-define=BASE_URL=https://your-app.vercel.app
# output: build/app/outputs/flutter-apk/app-release.apk
```

Note: `android/gradle/wrapper/gradle-wrapper.properties` currently points at
a local Gradle 9.3.1 zip (`D:\sdkdl\`) because this network blocks the
GitHub redirect used by services.gradle.org; the original URL is kept in
`gradle-wrapper.properties.bak`.

## Screens
- **Student**: login → home (today's classes + %) → enter 6-digit code →
  PRESENT/LATE result → history + subject-wise summary → leave requests →
  profile/logout (§8).
- **Teacher**: login → start session (class/section/subject) → live screen
  with rotating 6-digit code, countdown, live present/late counts, rotate and
  close → session history (§9).

## Notes
- Tokens are stored with `flutter_secure_storage` (encrypted shared
  preferences on Android); access tokens refresh automatically on 401 (§16).
- The server decides PRESENT vs LATE from its own clock and the institution's
  configurable windows — the device clock is never trusted (§11).
