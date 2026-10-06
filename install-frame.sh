#!/usr/bin/env bash
# Install and start on a Steam Frame. Turn on Developer Mode and start "Lepton Development"
# from the library first. FRAME_HOST (default: frame.local) or ADB_SERIAL selects the headset.
# Usage: ./install-frame.sh [path/to/apk]
set -euo pipefail
cd "$(dirname "$0")"
apk=${1:-artifacts/frame/TimeCrisisVR-frame-debug.apk}
[[ -f $apk ]] || { echo "APK missing. Run ./build-frame.sh first." >&2; exit 1; }
# adb from PATH, else the copy in .tools/platform-tools (Google's platform-tools zip).
command -v adb >/dev/null || PATH="$PWD/.tools/platform-tools:$PATH"
command -v adb >/dev/null || { echo "adb not found: install Android platform-tools." >&2; exit 1; }
host=${FRAME_HOST:-frame.local}
if [[ -z ${ADB_SERIAL:-} ]]; then adb connect "$host"; [[ $host == *:* ]] && ADB_SERIAL=$host || ADB_SERIAL=$host:5555; fi
adb=(adb -s "$ADB_SERIAL")
"${adb[@]}" get-state >/dev/null || { echo "Steam Frame not reachable: enable Developer Mode, start Lepton Development, then retry." >&2; exit 1; }
"${adb[@]}" install -r "$apk"
activity=$("${adb[@]}" shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p org.timecrisis.frame | tail -n 1 | tr -d '\r')
[[ $activity =~ ^org\.timecrisis\.frame/org\.timecrisis\.quest\.(MainActivity|LauncherActivity)$ ]] || { echo "Cannot resolve the app launcher: $activity" >&2; exit 1; }
"${adb[@]}" shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n "$activity"
