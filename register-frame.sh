#!/usr/bin/env bash
# Add Time Crisis VR to the Steam Frame's Steam library (Non-Steam > Time Crisis VR),
# launched through Lepton like a Title Upload with runtime "Android". Needs Developer Mode and
# ssh access as steamos (your key paired with the Frame, or its Developer Mode password).
# FRAME_HOST (default: frame.local) selects the headset.
# Also installs the library artwork in frame/library-art (tools/make_library_art.py makes it).
# Usage: ./register-frame.sh [path/to/apk]      ./register-frame.sh --uninstall
set -euo pipefail
cd "$(dirname "$0")"
target="steamos@${FRAME_HOST:-frame.local}"
if [[ ${1:-} == --uninstall ]]; then
  scp -q frame/frame-register.sh frame/install-library-art.py "$target:/tmp/"
  ssh "$target" 'python3 /tmp/install-library-art.py --remove timecrisisvr || true; bash /tmp/frame-register.sh --uninstall; rm -f /tmp/frame-register.sh /tmp/install-library-art.py'
  exit
fi
apk=${1:-artifacts/frame/bundled/TimeCrisisVR-frame-with-ROM.apk}
[[ -f $apk ]] || { echo "APK missing. Run ./build-frame.sh first." >&2; exit 1; }
ssh "$target" 'mkdir -p ~/devkit-game/timecrisisvr'
scp -q frame/frame-register.sh "$target:/tmp/frame-register.sh"
scp "$apk" "$target:devkit-game/timecrisisvr/$(basename "$apk")"
ssh "$target" "bash /tmp/frame-register.sh ~/devkit-game/timecrisisvr/$(basename "$apk"); rm -f /tmp/frame-register.sh"
if [[ -d frame/library-art ]]; then
  ssh "$target" 'mkdir -p ~/.local/share/timecrisisvr/library-art'
  scp -q frame/library-art/*.png "$target:.local/share/timecrisisvr/library-art/"
  scp -q frame/install-library-art.py "$target:.local/share/timecrisisvr/install-library-art.py"
  ssh "$target" 'python3 ~/.local/share/timecrisisvr/install-library-art.py timecrisisvr ~/.local/share/timecrisisvr/library-art' \
    || echo "note: the artwork could not be installed; the game works without it"
fi
# Steam registers devkit titles as "Devkit Game: <gameid>": rename it and apply the artwork now,
# through the Steam client (the grid files above keep the artwork if this is unavailable).
scp -q frame/steam-library.py "$target:.local/share/timecrisisvr/steam-library.py"
art=(); [[ -d frame/library-art ]] && art=(--artwork-dir '~/.local/share/timecrisisvr/library-art')
ssh "$target" "python3 ~/.local/share/timecrisisvr/steam-library.py --gameid timecrisisvr --name 'Time Crisis VR' ${art[*]}" \
  || echo "note: Steam's client did not answer; the title keeps the name 'Devkit Game: timecrisisvr'"
