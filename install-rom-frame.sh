#!/usr/bin/env bash
# ROM-free Steam Frame build: copies your own timecris.zip for the first-start import.
# Usage: ./install-rom-frame.sh path/to/timecris.zip [path/to/apk]
set -euo pipefail
cd "$(dirname "$0")"
rom=${1:?Usage: ./install-rom-frame.sh path/to/timecris.zip [apk]}
[[ -f $rom ]] || { echo "ROM ZIP not found." >&2; exit 1; }
# adb from PATH, else the copy in .tools/platform-tools (Google's platform-tools zip).
command -v adb >/dev/null || PATH="$PWD/.tools/platform-tools:$PATH"
command -v adb >/dev/null || { echo "adb not found: install Android platform-tools." >&2; exit 1; }
host=${FRAME_HOST:-frame.local}
if [[ -z ${ADB_SERIAL:-} ]]; then adb connect "$host"; [[ $host == *:* ]] && ADB_SERIAL=$host || ADB_SERIAL=$host:5555; fi
adb=(adb -s "$ADB_SERIAL")
"${adb[@]}" get-state >/dev/null
[[ -n ${2:-} ]] && "${adb[@]}" install -r "$2"
"${adb[@]}" shell am force-stop org.timecrisis.frame
destination=/sdcard/Android/data/org.timecrisis.frame/files
"${adb[@]}" shell mkdir -p "$destination"
"${adb[@]}" push "$rom" "$destination/timecris.zip"
activity=$("${adb[@]}" shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p org.timecrisis.frame | tail -n 1 | tr -d '\r')
[[ $activity =~ ^org\.timecrisis\.frame/org\.timecrisis\.quest\.(MainActivity|LauncherActivity)$ ]] || { echo "Cannot resolve the app launcher: $activity" >&2; exit 1; }
"${adb[@]}" shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n "$activity"
echo 'The app now verifies and imports your own ROM set. No ROM files are downloaded.'
