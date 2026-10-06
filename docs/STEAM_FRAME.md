# Time Crisis VR for Valve Steam Frame

The Steam Frame build is the same game, renderer and options as the Quest build, packaged as an Android APK for **Lepton**, the Frame's Android container. Only controller bindings, menu labels, the package name and a few runtime-detected graphics details differ.

**Status: experimental. First run on a Steam Frame on 2026-10-05:** the bundled APK starts in Lepton and runs in the headset at 72 Hz, 1728×1728 per eye, with the Frame controller profile, sRGB output and multiview. The items under [Unverified](#unverified-on-hardware) still need a full check.

## Install

For a complete walkthrough (ROM preparation, build, ssh setup, library installation and troubleshooting), see the **[Steam Frame install guide](STEAM_FRAME_INSTALL.md)**. A short version for the adb route:


1. On the Frame: **Steam Settings → System → Enable Developer Mode**, and set a user password.
2. Start **Lepton Development** from the Frame's Steam library. This enables adb.
3. On your computer, with Android platform-tools installed:

   ```sh
   ./install-frame.sh                        # macOS/Linux
   ./Install-Frame.ps1                       # Windows
   ```

   - The scripts run `adb connect frame.local`. Set `FRAME_HOST=<ip>` (or pass `-FrameHost`) if the name does not resolve.
   - Set `ADB_SERIAL` (or `-Serial`) for a USB connection: `adb forward tcp:5555 tcp:5555`, then `ADB_SERIAL=localhost:5555`.
4. Optional (ROM-free build only): `./install-rom-frame.sh path/to/timecris.zip`.
   - Lepton runs apps without a flat window, so the Quest build's ZIP picker is not shown.
   - Copy your ZIP with this script before the first start. The app then imports and verifies it automatically.
   - The chip files must sit at the top level of the ZIP, as in MAME sets. A ZIP that wraps them in a `timecris/` folder is rejected; re-zip the files themselves.

### Launch from the Steam library

```sh
./register-frame.sh          # copies the bundled APK and registers it (ssh as steamos)
./register-frame.sh --uninstall
```

This does what the SteamOS Devkit Client's **Title Upload** does with runtime **Android**:
- **Files:** the APK goes to `~/devkit-game/timecrisisvr/`. The start command is the APK name, and the compat tool is `lepton`.
- **Registration:** the title is registered with the Frame's Steam client.
- **Result:** the game appears under **Library → Non-Steam → Time Crisis VR** and starts like any other title, with no computer needed.
- **Name:** Steam registers devkit titles as "Devkit Game: <id>". `frame/steam-library.py` renames it through the Steam client's local DevTools port, which also applies the artwork without a Steam restart.

It also installs the library artwork from `frame/library-art/`. The artwork comes from the cover, an in-game picture and the logo, with "VR" and a "Steam Frame Edition" badge added:

```sh
python3 -m venv build/artenv && build/artenv/bin/pip install pillow numpy
build/artenv/bin/python tools/make_library_art.py --cover cover.jpeg --ingame ingame.jpeg --logo logo.jpeg
```

It needs Developer Mode and ssh access as `steamos`: your paired key, or the Developer Mode password.

Settings, saves and imported ROMs live in the app's private files. They survive `adb install -r`.

## Controls

The Frame's right controller has A, B, X and Y. The left controller has a d-pad and View instead of X, Y and Menu. The left hand keeps its Quest jobs on those controls; everything else matches the [Quest controls](../README.md#controls):

| Action | Default hand: right | Default hand: left |
| --- | --- | --- |
| Aim the visible 3D pistol | Controller selected by its trigger | Controller selected by its trigger |
| Select weapon hand and fire / start / confirm | Either trigger | Either trigger |
| Insert three credits | A right | **Left thumbstick click** |
| Toggle laser silently | B right | **Left d-pad left or right** |
| Pause and open options / resume | **View** (left) | **View** (left) |
| Set default hand, **in options** | Right thumbstick click | Right thumbstick click |
| Switch cover mode, **in options** | **Left d-pad left or right** | B right |
| Recenter and set upright head height | **Left thumbstick click** | A right |
| Grip cover: hold to leave cover; release both to hide/reload | Either grip | Either grip |
| Physical cover: hide/reload; leave cover | Duck; return upright | Duck; return upright |

The options panel shows these Frame names. The right controller's X and Y are unused.

If SteamVR uses its Oculus Touch fallback instead of the Frame bindings, the controls follow SteamVR's Touch mapping: Touch Menu maps to View, and Touch X/Y map to the d-pad.

## Build

```sh
./build-frame.sh path/to/timecris.zip                 # ROM-free APK
./build-frame.sh path/to/timecris.zip --bundle-roms   # APK with your ROMs
```

On Windows use `./Build-Frame.ps1 -Rom ... [-BundleRoms]`. Either way this calls `python tools/build.py --target frame`.

- **Requirements:** macOS, Linux or Windows; Git, CMake, Python 3 and a JDK. On macOS a Homebrew `openjdk` is found automatically, or set `JAVA_HOME`.
- **Dependencies:** `tools/bootstrap.py` downloads the matching NDK and build tools for the host.
- **Output:**
  - `artifacts/frame/TimeCrisisVR-frame-debug.apk` (ROM-free).
  - `artifacts/frame/bundled/TimeCrisisVR-frame-with-ROM.apk` (bundled).
  - Each folder also gets `build-info.json` and `vrpreferences.json`.
- **Verify:** `python tests/verify_apk.py --target frame [--apk ...]`.

## What differs from the Quest build

| Area | Quest | Steam Frame |
| --- | --- | --- |
| Package | `org.timecrisis.quest` | `org.timecrisis.frame` (Java classes shared) |
| Manifest | Oculus VR category and meta-data | Khronos `IMMERSIVE_HMD` + `LAUNCHER` only |
| Controller profile | `oculus/touch_controller` | `valve/frame_controller_valve`, Touch as fallback |
| Left X / Y / Menu | X, Y, Menu | Thumbstick click, d-pad left/right, View |
| Gun pose | aim pose of either hand | aim pose; derived from that hand's palm pose (`XR_EXT_palm_pose`) when SteamVR leaves the aim pose untracked |
| Eye size cap | 1440 | 1728 (Valve's recommended size) |
| Swapchain | sRGB (raw) or `RGBA8` | same, plus a linearizing copy for sRGB-only runtimes (see below) |
| SDL Java | as shipped | same; `build.py` stages a copy that tolerates Lepton's missing clipboard service, which made SDL 2.30 crash in `onCreate` |
| Refresh rate | 120 Hz, or the highest supported lower rate | SteamVR offers only its current rate (72 Hz by default); `vrpreferences.json` asks for 120 Hz |

**Swapchain choice.** The game's colours are already display-encoded. Like the Quest build, the host prefers `SRGB8_ALPHA8` with sRGB writes disabled (`GL_EXT_sRGB_write_control`), then `RGBA8`. The Frame may offer only sRGB formats; if its driver also lacks the write control, the host draws each eye in RGBA8 and does a final linearizing copy into the sRGB image.

The choice is logged.

**Refresh rate.** SteamVR does not switch rates on app request. `vrpreferences.json` (`preferMinRefreshRate: 120`) must sit at the package root of a Steam depot. It is not known whether SteamVR honours it for adb installs. The game itself always runs at its original 59.906 Hz, so 72 Hz is functionally correct.

## Diagnostics

```sh
adb logcat -s TCVR TCVR-ROM SDL OpenXR
adb shell run-as org.timecrisis.frame cat files/timecris-vr.log
adb shell run-as org.timecrisis.frame touch files/capture.request    # eye-0/1.ppm
python tools/device_check.py --package org.timecrisis.frame --capture
python tools/perf_report.py artifacts/frame-perf --capture --package org.timecrisis.frame --seconds 120
```

At startup `timecris-vr.log` records:
- The OpenXR runtime and version, the enabled extensions and the swapchain formats.
- The swapchain mode, the GL version, multiview on/off and the per-eye size.
- The controller profile each hand is bound to, and whether the gun follows the aim or the palm pose.

`perf_report.py` summarises the app's own `[XRPERF]` frame timing. Meta's runtime FPS lines do not exist on the Frame.

Private switches in `files/`, read at the next start:
- `eye-size.txt`: maximum per-eye size, e.g. `1440`.
- `refresh-rate.txt`.
- `multiview.off`: use separate eye passes instead of multiview.
- `profile.request`.

## Unverified on hardware

- The APK installs and opens immersively from Lepton.
- Which swapchain mode SteamVR selects, and that colours match the Quest capture (`docs/images/gameplay.png`).
- `GL_OVR_multiview2` under Zink renders a correct right eye. If it does not, create `multiview.off` and report the result.
- The Frame profile is accepted on the device (the mock-runtime test accepts it). Check View, d-pad, stick clicks and both grips.
- The palm-pose fallback, and whether the pistol model lines up with the Frame controller.
- Audio, recoil haptics on both hands, trigger hand handoff, focus/pause handling and physical ducking.
- Achievable frame rate at 1728² under Zink, and whether `vrpreferences.json` raises the rate for a sideloaded APK.
