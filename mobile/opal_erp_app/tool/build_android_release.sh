#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
API="${OPAL_ERP_API_BASE_URL:-https://opalschool2016.pythonanywhere.com/mobile/api/v1}"
bash tool/prepare_android.sh
flutter pub get
flutter analyze
flutter test
flutter build apk --release --dart-define="OPAL_ERP_API_BASE_URL=$API"
flutter build appbundle --release --dart-define="OPAL_ERP_API_BASE_URL=$API"
