#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_BASE_URL="${OPAL_API_BASE_URL:-https://opalschool2016.pythonanywhere.com/learning/api/v1}"

if ! command -v flutter >/dev/null 2>&1; then
  echo "Flutter SDK is required." >&2
  exit 2
fi

if [ ! -f android/app/src/main/AndroidManifest.xml ]; then
  bash tool/prepare_android.sh
else
  python3 tool/configure_android.py
fi

flutter pub get
flutter analyze
flutter test
flutter build apk --release --dart-define="OPAL_API_BASE_URL=$API_BASE_URL"
flutter build appbundle --release --dart-define="OPAL_API_BASE_URL=$API_BASE_URL"

sha256sum build/app/outputs/flutter-apk/app-release.apk \
  build/app/outputs/bundle/release/app-release.aab \
  > build/android-release-sha256.txt

printf '\nAPK: %s\nAAB: %s\nSHA: %s\n' \
  "$ROOT/build/app/outputs/flutter-apk/app-release.apk" \
  "$ROOT/build/app/outputs/bundle/release/app-release.aab" \
  "$ROOT/build/android-release-sha256.txt"
