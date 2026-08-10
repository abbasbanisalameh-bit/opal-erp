from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android"
MANIFEST = ANDROID / "app" / "src" / "main" / "AndroidManifest.xml"

if not MANIFEST.exists():
    raise SystemExit("AndroidManifest.xml is missing; run tool/prepare_android.sh first.")

text = MANIFEST.read_text(encoding="utf-8")
permission = '<uses-permission android:name="android.permission.INTERNET" />'
if "android.permission.INTERNET" not in text:
    end = text.find(">")
    text = text[: end + 1] + "\n    " + permission + text[end + 1 :]

for old in ('android:label="opal_erp_app"', 'android:label="Opal Erp App"', 'android:label="OPAL ERP"'):
    text = text.replace(old, 'android:label="نظام أوبال"')
if "android:usesCleartextTraffic=" not in text:
    text = text.replace("<application", '<application android:usesCleartextTraffic="false"', 1)
MANIFEST.write_text(text, encoding="utf-8")

icon = ROOT / "assets" / "opal-erp-icon-192.png"
if icon.exists():
    for folder in ("mipmap-mdpi", "mipmap-hdpi", "mipmap-xhdpi", "mipmap-xxhdpi", "mipmap-xxxhdpi"):
        target_dir = ANDROID / "app" / "src" / "main" / "res" / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon, target_dir / "ic_launcher.png")

print("Configured OPAL ERP Android manifest, HTTPS-only networking, and official school icon.")
