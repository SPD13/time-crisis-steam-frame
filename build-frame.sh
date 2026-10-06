#!/usr/bin/env bash
# Steam Frame APK on macOS/Linux. Usage: ./build-frame.sh [path/to/timecris.zip] [--bundle-roms] [--jobs N]
set -euo pipefail
cd "$(dirname "$0")"
rom="$HOME/Downloads/timecris.zip"
if [[ $# -gt 0 && $1 != --* ]]; then rom=$1; shift; fi
python3 tools/build.py --target frame --rom "$rom" "$@"
