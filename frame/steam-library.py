#!/usr/bin/env python3
"""Runs on the Steam Frame. Gives the devkit title a library name and its artwork through the
Steam client's CEF DevTools port (127.0.0.1:8080, page SharedJSContext), without restarting
Steam. A devkit title is always registered as "Devkit Game: <gameid>"; this renames it.
The DevTools client is the one in stream-frame's lib/steam-shortcut.py. Stdlib only.

  steam-library.py --gameid timecrisisvr --name "Time Crisis VR" [--artwork-dir DIR]

Exit codes: 0 ok, 2 DevTools port unreachable or no such title, 1 other error.
"""
import argparse
import base64
import glob
import json
import os
import socket
import struct
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HOST = os.environ.get("STEAM_DEVTOOLS_HOST", "127.0.0.1")
PORT = int(os.environ.get("STEAM_DEVTOOLS_PORT", "8080"))
TARGET_TITLE = "SharedJSContext"


class PortUnavailable(Exception):
    pass


# ---------------------------------------------------------------- DevTools / WebSocket


def find_target():
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/json", timeout=3) as r:
            targets = json.load(r)
    except OSError as e:
        raise PortUnavailable(str(e)) from e
    for t in targets:
        if t.get("title") == TARGET_TITLE and t.get("webSocketDebuggerUrl"):
            return t["webSocketDebuggerUrl"]
    raise PortUnavailable(f"no {TARGET_TITLE} target on the DevTools port")


class WebSocket:
    """Minimal RFC 6455 client: text frames, masking, fragmentation, ping/pong."""

    def __init__(self, url):
        u = urllib.parse.urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {u.path or '/'} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise PortUnavailable("WebSocket handshake closed")
            resp += chunk
        head, self.buf = resp.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise PortUnavailable("WebSocket handshake refused: " + head.split(b"\r\n", 1)[0].decode(errors="replace"))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("WebSocket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _send_frame(self, opcode, payload):
        head = bytes([0x80 | opcode])
        n = len(payload)
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 1 << 16:
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def send(self, text):
        self._send_frame(0x1, text.encode())

    def recv(self):
        parts = []
        while True:
            b0, b1 = self._read(2)
            opcode, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if b1 & 0x80 else None
            data = self._read(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x9:
                self._send_frame(0xA, data)
                continue
            if opcode == 0x8:
                raise ConnectionError("WebSocket closed by peer")
            if opcode in (0x1, 0x2, 0x0):
                parts.append(data)
                if b0 & 0x80:
                    return b"".join(parts).decode()

    def close(self):
        try:
            self._send_frame(0x8, b"")
        finally:
            self.sock.close()


def evaluate(js):
    ws = WebSocket(find_target())
    try:
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": js, "awaitPromise": True, "returnByValue": True},
        }))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                break
    finally:
        ws.close()
    if "error" in msg:
        raise RuntimeError(msg["error"].get("message", str(msg["error"])))
    res = msg["result"]
    if res.get("exceptionDetails"):
        d = res["exceptionDetails"]
        raise RuntimeError(d.get("exception", {}).get("description") or d.get("text", "JavaScript exception"))
    return res["result"].get("value")


# ---------------------------------------------------------------- library entry

# Steam's custom artwork types (SteamClient.Apps.SetCustomArtworkForApp).
ARTWORK = {"capsule.png": 0, "hero.png": 1, "logo.png": 2, "wide.png": 3}

# Runs inside Steam's SharedJSContext. The SteamClient API is undocumented: every call is guarded.
NAME_JS = r"""
(async (p) => {
  const A = SteamClient.Apps;
  const warnings = [];
  try { A.SetShortcutName(p.appid, p.name); } catch (e) { warnings.push('SetShortcutName: ' + e); }
  for (const art of p.artwork) {
    try { await A.SetCustomArtworkForApp(p.appid, art.data, 'png', art.type); }
    catch (e) { warnings.push('artwork ' + art.name + ': ' + e); }
  }
  let name = null;
  try { name = appStore.GetAppOverviewByAppID(p.appid).display_name; } catch (e) {}
  return { name, warnings };
})(__PARAMS__)
"""


def devkit_appid(gameid):
    """The shortcut's app id, from Steam's shortcuts.vdf (binary KeyValues)."""
    def parse(data, pos=0):
        out = {}
        while True:
            t = data[pos]; pos += 1
            if t == 0x08:
                return out, pos
            end = data.index(b"\0", pos); key = data[pos:end].decode("utf-8", "replace"); pos = end + 1
            if t == 0x00:
                out[key], pos = parse(data, pos)
            elif t == 0x01:
                end = data.index(b"\0", pos); out[key] = data[pos:end].decode("utf-8", "replace"); pos = end + 1
            elif t == 0x02:
                out[key] = struct.unpack_from("<I", data, pos)[0]; pos += 4
            else:
                raise ValueError(f"unsupported VDF type {t:#x}")
    for vdf in glob.glob(os.path.expanduser("~/.local/share/Steam/userdata/*/config/shortcuts.vdf")):
        shortcuts, _ = parse(Path(vdf).read_bytes())
        entries = next((v for k, v in shortcuts.items() if k.lower() == "shortcuts"), {})
        for entry in entries.values():
            if entry.get("DevkitGameID") == gameid:
                return entry["appid"]
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gameid", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--artwork-dir")
    a = p.parse_args()
    appid = devkit_appid(a.gameid)
    if appid is None:
        print(f"steam-library: no devkit title {a.gameid}: register it first", file=sys.stderr)
        return 2
    folder = Path(a.artwork_dir).expanduser() if a.artwork_dir else None
    artwork = [{"name": n, "type": t, "data": base64.b64encode((folder / n).read_bytes()).decode()}
               for n, t in ARTWORK.items() if folder and (folder / n).is_file()]
    try:
        res = evaluate(NAME_JS.replace("__PARAMS__", json.dumps({"appid": appid, "name": a.name, "artwork": artwork})))
    except PortUnavailable as e:
        print(f"steam-library: Steam's DevTools port is unreachable ({e})", file=sys.stderr)
        return 2
    for w in res.get("warnings", []):
        print(f"steam-library: warning: {w}", file=sys.stderr)
    art = f", {len(artwork)} artwork images set" if artwork else ""
    print(f"steam-library: app id {appid} is now '{res.get('name')}'{art}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
