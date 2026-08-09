#!/usr/bin/env python3
"""Small LAN bridge from a biometric terminal to OPAL HTTPS.

Modes:
  --json-file FILE   Send a JSON file containing either {"events": [...]} or a list.
  --zkteco           Poll a ZKTeco-compatible terminal using the optional `pyzk` package.

Environment variables:
  OPAL_BIOMETRIC_API_URL     e.g. https://school.pythonanywhere.com/timetable/biometric/api/v1/punches/
  OPAL_BIOMETRIC_TOKEN       one-time token generated in OPAL
  OPAL_BIOMETRIC_DEVICE_IP   terminal LAN IP for --zkteco
  OPAL_BIOMETRIC_DEVICE_PORT defaults to 4370
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(os.environ.get("OPAL_BIOMETRIC_STATE_FILE", ".opal_biometric_sent.json"))


def load_state():
    try:
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_state(values):
    STATE_FILE.write_text(json.dumps(sorted(values)[-50000:]), encoding="utf-8")


def stable_uid(user_id, timestamp, direction):
    return hashlib.sha256(f"{user_id}|{timestamp}|{direction}".encode()).hexdigest()


def push(events):
    url = os.environ.get("OPAL_BIOMETRIC_API_URL", "").strip()
    token = os.environ.get("OPAL_BIOMETRIC_TOKEN", "").strip()
    if not url or not token:
        raise SystemExit("Set OPAL_BIOMETRIC_API_URL and OPAL_BIOMETRIC_TOKEN first.")
    body = json.dumps({"events": events}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-OPAL-BIOMETRIC-TOKEN": token,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OPAL rejected the batch: HTTP {exc.code}: {detail}") from exc
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def json_events(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    events = raw.get("events") if isinstance(raw, dict) else raw
    if not isinstance(events, list):
        raise SystemExit("JSON must be a list or an object containing events[].")
    return events


def zkteco_events():
    try:
        from zk import ZK
    except ImportError as exc:
        raise SystemExit("ZKTeco mode needs pyzk on the local bridge computer: pip install pyzk") from exc
    ip = os.environ.get("OPAL_BIOMETRIC_DEVICE_IP", "").strip()
    if not ip:
        raise SystemExit("Set OPAL_BIOMETRIC_DEVICE_IP.")
    port = int(os.environ.get("OPAL_BIOMETRIC_DEVICE_PORT", "4370"))
    password = int(os.environ.get("OPAL_BIOMETRIC_DEVICE_PASSWORD", "0"))
    zk = ZK(ip, port=port, timeout=10, password=password, force_udp=False, ommit_ping=False)
    conn = None
    try:
        conn = zk.connect()
        records = conn.get_attendance() or []
        events = []
        for row in records:
            punch = getattr(row, "punch", None)
            # Common ZKTeco convention: 0/2/5 are entry-like; 1/3/4 are exit-like.
            direction = "in" if punch in {0, 2, 5} else "out" if punch in {1, 3, 4} else "unknown"
            stamp = getattr(row, "timestamp", None)
            if not isinstance(stamp, datetime):
                continue
            timestamp = stamp.isoformat()
            user_id = str(getattr(row, "user_id", "") or getattr(row, "uid", "")).strip()
            if not user_id:
                continue
            events.append({
                "user_id": user_id,
                "timestamp": timestamp,
                "direction": direction,
                "event_uid": stable_uid(user_id, timestamp, direction),
                "source": "pyzk",
            })
        return events
    finally:
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json-file")
    group.add_argument("--zkteco", action="store_true")
    parser.add_argument("--resend-all", action="store_true")
    args = parser.parse_args()
    events = zkteco_events() if args.zkteco else json_events(args.json_file)
    sent = load_state()
    pending = []
    for event in events:
        uid = str(event.get("event_uid") or stable_uid(event.get("user_id", ""), event.get("timestamp", ""), event.get("direction", "unknown")))
        event["event_uid"] = uid
        if args.resend_all or uid not in sent:
            pending.append(event)
    if not pending:
        print("No new punches.")
        return 0
    result = push(pending)
    if result.get("ok"):
        sent.update(item["event_uid"] for item in pending)
        save_state(sent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
