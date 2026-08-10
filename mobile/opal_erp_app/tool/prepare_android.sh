#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if ! command -v flutter >/dev/null 2>&1; then
  echo "Flutter SDK is required to prepare Android." >&2
  exit 2
fi
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cp pubspec.yaml "$tmp/pubspec.yaml"
cp analysis_options.yaml "$tmp/analysis_options.yaml"
cp -a lib "$tmp/lib"
cp -a assets "$tmp/assets"
cp -a test "$tmp/test" 2>/dev/null || true
flutter create --platforms=android --org com.opalschool2016 --project-name opal_erp_app --no-pub .
cp "$tmp/pubspec.yaml" pubspec.yaml
cp "$tmp/analysis_options.yaml" analysis_options.yaml
rm -rf lib assets test
cp -a "$tmp/lib" lib
cp -a "$tmp/assets" assets
if [ -d "$tmp/test" ]; then cp -a "$tmp/test" test; fi
python3 tool/configure_android.py
echo "OPAL ERP Android scaffold is ready: $ROOT/android"
