#!/usr/bin/env bash
# frame-register.sh - runs ON the Steam Frame, as its user (steamos). Puts the APK in
# ~/devkit-game/timecrisisvr and registers it with the Frame's Steam client as a devkit title on
# the Android (Lepton) runtime, as the SteamOS Devkit Client's Title Upload does with runtime
# "Android": start command = the APK name, compat tool "lepton". The Steam commands are the
# ones its devkit-utils send (devkit-1 IPC on ~/.steam/steam.pipe). It then appears in the
# Library as "Devkit Game: timecrisisvr" (Non-Steam).
#
#   frame-register.sh APK          install or update the title from APK
#   frame-register.sh --uninstall  remove the title (the app's saved settings stay in Lepton)
set -euo pipefail

GAMEID=timecrisisvr
DEVKIT="$HOME/devkit-game"
DEST="$DEVKIT/$GAMEID"

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# steam <create|delete> - asks the running Steam client to add or remove the devkit title, and
# waits for its answer (Steam writes it to a response file).
steam() {
  python3 - "$1" "$GAMEID" <<'PY'
import os, sys, time, tempfile
from urllib.parse import quote_plus
action, gameid = sys.argv[1], sys.argv[2]
steam_dir = os.path.expanduser('~/.steam')
try:
    pid = int(open(os.path.join(steam_dir, 'steam.pid')).read())
    os.kill(pid, 0)
except Exception:
    print('Steam is not running on the Frame. Put the headset on (Steam starts with it) and run this again.')
    sys.exit(3)
with tempfile.TemporaryDirectory(prefix=action + '-shortcut') as tmp:
    response = os.path.join(tmp, 'response')
    cmd = f'{action}-shortcut?response={quote_plus(response)}&gameid={gameid}'
    token = open(os.path.join(steam_dir, 'steam.token')).read()
    with open(os.path.realpath(os.path.join(steam_dir, 'steam.pipe')), 'wb', 0) as pipe:
        pipe.write(f'devkit-1 steam://devkit-1/{token}/{cmd}\n'.encode())
    for _ in range(15):
        time.sleep(1)
        if os.path.exists(response + '.error'):
            print('Steam refused: ' + open(response + '.error').read().strip())
            sys.exit(4)
        if os.path.exists(response) and not os.path.exists(response + '.lock'):
            sys.exit(0)
    print('Steam did not answer. Is Developer Mode on? (Settings > System > Developer Mode)')
    sys.exit(5)
PY
}

[ "$(uname -m)" = aarch64 ] || die "this runs on the Steam Frame (aarch64), not on $(uname -sm)"
mkdir -p "$DEVKIT"
if [ "${1:-}" = --uninstall ]; then
  rm -rf "$DEST" "$DEVKIT/$GAMEID-argv.json" "$DEVKIT/$GAMEID-settings.json" "$DEVKIT/$GAMEID-env.json"
  steam delete >/dev/null || say "note: Steam did not confirm; the title disappears at its next restart"
  say "Time Crisis VR removed from the Steam library."
  exit 0
fi
apk="${1:?usage: frame-register.sh APK | --uninstall}"
[ -f "$apk" ] || die "no such file: $apk"
name=$(basename "$apk")
mkdir -p "$DEST"
find "$DEST" -maxdepth 1 -name '*.apk' ! -name "$name" -delete
[ "$(realpath "$apk")" = "$(realpath -m "$DEST/$name")" ] || cp -f "$apk" "$DEST/$name"
printf '["%s"]' "$name" >"$DEVKIT/$GAMEID-argv.json"
printf '{"steam_play": "0", "compat_tool": "lepton"}' >"$DEVKIT/$GAMEID-settings.json"
steam create || die "the APK is copied but not registered with Steam (see above)"
say "registered as Devkit Game: $GAMEID (Android runtime, Lepton)"
