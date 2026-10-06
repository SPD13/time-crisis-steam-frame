# Installing Time Crisis VR on a Steam Frame

This guide takes you from a fresh checkout to **Time Crisis VR** in your Steam Frame's library, launched like any other game and running entirely on the headset. You build the game on a computer, then copy it to the Frame over Wi-Fi.

The Steam Frame build is **experimental**. It has been run on a Steam Frame. The [technical notes](STEAM_FRAME.md#unverified-on-hardware) list what is still being checked.

**Contents:**
[How it works](#how-it-works) ·
[What you need](#what-you-need) ·
[1. Prepare your ROM set](#1-prepare-your-rom-set) ·
[2. Build the game](#2-build-the-game) ·
[3. Prepare the Steam Frame](#3-prepare-the-steam-frame) ·
[4. Install into the Steam library](#4-install-into-the-steam-library) ·
[5. Play](#5-play) ·
[Updating and uninstalling](#updating-and-uninstalling) ·
[Alternative: install with adb](#alternative-install-with-adb) ·
[Troubleshooting](#troubleshooting)

## How it works

The game is an Android app (APK). It runs on the Frame inside **Lepton**, Valve's Android compatibility layer, which is part of SteamOS on the Frame.

The installer does what Valve's SteamOS Devkit Client **Title Upload** does with runtime **Android**:
- **Files:** it copies the APK to the headset.
- **Registration:** it registers the APK as a devkit title that Steam starts through Lepton.
- **Library:** it names the title **Time Crisis VR** and adds library artwork.

After installation the computer is no longer needed. The game, its ROMs and your settings all live on the headset.

## What you need

**The headset**
- A Valve **Steam Frame**, on the same network as your computer.
- **Developer Mode** turned on, with a **user password** set. [Step 3](#3-prepare-the-steam-frame) covers both.

**The computer: macOS, Linux or Windows**

| Tool | Why | How to get it |
| --- | --- | --- |
| Git | Fetch the source and the engine submodule | git-scm.com, or `xcode-select --install` on macOS |
| Python 3 | Build scripts | python.org, or Homebrew `python` |
| CMake 3.22 or newer | Native build | cmake.org, or Homebrew `cmake` |
| A JDK (Java 17 or newer) | Android packaging | Homebrew `openjdk`, Adoptium, or Android Studio. The build finds Homebrew's and Android Studio's automatically; otherwise set `JAVA_HOME`. |
| ssh / scp | Copy the game to the headset | Built into macOS, Linux and Windows 10/11 |
| About 4 GB of free disk space | Android NDK and build tools | Downloaded automatically by the first build |

**On Windows**, the build runs from PowerShell (`Build-Frame.ps1`). The library installer `register-frame.sh` is a bash script, so run it from **Git Bash** (installed with Git for Windows) or WSL.

**Your own ROM set.** The game needs the arcade ROMs of **Time Crisis (World, TS2 Ver.B)**, the MAME set `timecris`, as `timecris.zip`. No ROMs are included in this repository or downloaded by it.

## 1. Prepare your ROM set

The build checks every chip by size and checksum. It also accepts older chip names, such as `ts2ver-b.1` for `ts2verb.1`, as long as the checksum matches. Other revisions (for example Ver.A only) do not work.

**The chip files must be at the top level of the ZIP**, as in MAME sets. Some downloads wrap them in a `timecris/` folder, and often add macOS `__MACOSX` entries as well. If `unzip -l timecris.zip` shows paths like `timecris/ts1cg0.8d`, re-pack the files themselves:

```sh
mkdir rom-tmp && cd rom-tmp
unzip -q ../timecris.zip -x '__MACOSX/*'
cd timecris && zip -q -j ../../timecris-flat.zip * && cd ../..
rm -r rom-tmp
```

Use `timecris-flat.zip` in the next steps. The game needs 31 chips; `c71.bin` is optional. Extra Ver.A files (`ts2ver-a.*`) are ignored.

## 2. Build the game

Clone this fork with its engine submodule. Its `steam-frame` branch holds the Steam Frame edition:

```sh
git clone --recurse-submodules -b steam-frame https://github.com/SPD13/time-crisis-steam-frame.git
cd time-crisis-steam-frame
```

Build the APK **with your ROMs included**. That APK starts straight into the game, with no import step:

```sh
./build-frame.sh path/to/timecris-flat.zip --bundle-roms --jobs 8          # macOS / Linux
./Build-Frame.ps1 -Rom 'C:\path\to\timecris-flat.zip' -BundleRoms -Jobs 8  # Windows PowerShell
```

The first build downloads the pinned Android NDK, build tools, SDL and the OpenXR loader into `.tools/`. That takes several minutes and a few GB. It also translates the game's DSP and sound programs from your ROMs. Later builds are much faster.

When it finishes, it prints a summary that includes the target and package, and confirms the APK is signed and aligned. You get:

| File | What it is |
| --- | --- |
| `artifacts/frame/bundled/TimeCrisisVR-frame-with-ROM.apk` | The game with your ROMs. **Install this one.** |
| `artifacts/frame/bundled/build-info.json` | Version, SHA-256 and build details |
| `artifacts/frame/bundled/vrpreferences.json` | Refresh-rate preference for a later Steam depot |

Optionally, check the package:

```sh
python3 tests/verify_apk.py --target frame --apk artifacts/frame/bundled/TimeCrisisVR-frame-with-ROM.apk
```

> The bundled APK contains your ROM files. Keep it for your own headset; do not share it.

## 3. Prepare the Steam Frame

### 3.1 Turn on Developer Mode

In the headset, open **Steam Settings → System**, turn on **Developer Mode**, and set a **user password** when asked. Developer Mode enables ssh access as the user `steamos`, which the installer uses.

Keep the headset awake. When it sleeps it drops off the network.

### 3.2 Find the headset on the network

The Frame announces itself as **`frame.local`**. Check from your computer:

```sh
ping frame.local
```

If the name does not resolve, look up the Frame's IP address in its network settings, then put `FRAME_HOST=<ip>` in front of the commands below.

### 3.3 Allow your computer to log in

The installer runs a few commands over ssh. Copy your ssh key to the headset once, so you aren't asked for the password every time:

```sh
ssh-keygen -t ed25519           # only if you have no key yet (~/.ssh/id_ed25519.pub)
ssh-copy-id steamos@frame.local # enter the Developer Mode password
ssh steamos@frame.local true    # should now return without asking for a password
```

If you have already paired this computer with the Frame, for example with the SteamOS Devkit Client, this step is done. Without a key the installer still works, but asks for the password several times.

## 4. Install into the Steam library

Put the headset on, or at least keep it awake with Steam running; it always is in normal headset mode. Then run, from the repository folder:

```sh
./register-frame.sh
```

By default this installs `artifacts/frame/bundled/TimeCrisisVR-frame-with-ROM.apk`. Pass another APK path as an argument to install a different one.

It performs these steps, and prints a line for each:
1. **Copy:** the APK goes to `~/devkit-game/timecrisisvr/` on the headset.
2. **Register:** the title is registered with the Frame's Steam client with the start command set to the APK and the runtime set to **Lepton** (Android). This is the same request the Devkit Client's Title Upload sends.
3. **Artwork:** the library artwork from `frame/library-art/` is installed.
4. **Name:** the entry is renamed from Steam's default "Devkit Game: timecrisisvr" to **Time Crisis VR**, and the artwork is applied immediately.

A successful run ends like this:

```text
registered as Devkit Game: timecrisisvr (Android runtime, Lepton)
Devkit Game: timecrisisvr: artwork installed for appid … in …/config/grid
steam-library: app id … is now 'Time Crisis VR', 4 artwork images set
```

## 5. Play

1. In the headset, open **Library → Non-Steam → Time Crisis VR** and press **Play**.
2. If Steam warns that Valve is still learning about the title's compatibility, continue. This is the standard notice for titles without a Steam Frame rating.
3. If the SteamVR dashboard stays in front of the game, choose **Resume**, or close the dashboard with the controller's Steam button. Keep the headset on: SteamVR only gives the game its display while the headset is worn.
4. When the arcade attract mode is running, press **A** (right controller) to add credits, then pull **either trigger** to start.

### Controls

| Action | Default (right-handed) |
| --- | --- |
| Aim | The controller whose trigger you pulled last |
| Fire / start / confirm | Either trigger |
| Insert three credits | A, right controller |
| Toggle the laser sight | B, right controller |
| Leave cover (hold) / hide and reload (release) | Either grip |
| Pause and options | View, left controller |
| Recenter / set upright height | Left thumbstick click |
| Switch cover mode (in options) | Left d-pad left or right |
| Set default hand (in options) | Right thumbstick click |

Left-handed mode swaps the button roles between the hands. The complete table and the physical-ducking option are in the [technical notes](STEAM_FRAME.md#controls). Settings are saved on the headset.

## Updating and uninstalling

**Update** after pulling new code: build again (step 2), then run `./register-frame.sh` again. It replaces the APK and re-applies the name and artwork. Your settings and saves are kept.

**Uninstall:**

```sh
./register-frame.sh --uninstall
```

This removes the library entry, its artwork and the files in `~/devkit-game/timecrisisvr/`.

## Alternative: install with adb

For development, or if you prefer Valve's sideloading route, you can install the APK straight into Lepton with adb.

1. Install Android platform-tools on the computer:
   - **Homebrew:** `brew install --cask android-platform-tools`.
   - **Google's download:** unzip Google's platform-tools into `.tools/platform-tools/`; the scripts look there too.
2. In the headset, start **Lepton Development** from the Steam library and keep it running. This opens adb on port 5555.
3. Run:

   ```sh
   ./install-frame.sh artifacts/frame/bundled/TimeCrisisVR-frame-with-ROM.apk   # macOS / Linux
   ./Install-Frame.ps1 -Apk artifacts\frame\bundled\TimeCrisisVR-frame-with-ROM.apk   # Windows
   ```

   The script connects to `frame.local:5555` (`FRAME_HOST` changes it), installs the APK and starts the game. Accept the debugging prompt in the headset if one appears.

A ROM-free build (`./build-frame.sh path/to/timecris.zip` without `--bundle-roms`) also exists. With it, push your flat ROM ZIP once with `./install-rom-frame.sh path/to/timecris-flat.zip`; the game imports and verifies it on first start.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `ssh: Could not resolve hostname frame.local` | The headset is asleep or on another network. Wake it, or use `FRAME_HOST=<ip> ./register-frame.sh`. |
| `Permission denied (publickey,password)` | Developer Mode or its password is not set, or your key was not copied. Redo [step 3](#3-prepare-the-steam-frame). |
| `Steam is not running on the Frame` | Put the headset on so Steam is running in its normal mode, then run the installer again. |
| `Steam did not answer` / `Steam refused` | Developer Mode is off. Turn it on and run the installer again. |
| The entry is called **Devkit Game: timecrisisvr** | The renaming step could not reach Steam (for example while Steam was restarting). Run `./register-frame.sh` again. |
| No artwork in the library | Run `./register-frame.sh` again, or restart the headset. Steam reads the artwork copies at startup. |
| Nothing appears in the headset after **Play** | The SteamVR dashboard is probably in front: choose **Resume**. Keep the headset on. |
| The build stops with a ROM error | Wrong revision, or the chips are inside a folder in the ZIP. See [step 1](#1-prepare-your-rom-set). |
| `adb: failed to connect to 'frame.local:5555'` | Only for the adb route: start **Lepton Development** in the headset first. |
| The game runs at 72 Hz | The Frame's default refresh rate. Gameplay timing is not affected: the arcade always runs at its original 59.9 Hz. |

### Logs

With **Lepton Development** running, adb can read the game's logs:

```sh
adb connect frame.local:5555
adb logcat -s TCVR TCVR-ROM SDL OpenXR
adb exec-out run-as org.timecrisis.frame cat files/timecris-vr.log
python3 tools/device_check.py --package org.timecrisis.frame \
  --apk artifacts/frame/bundled/TimeCrisisVR-frame-with-ROM.apk --capture   # log, runtime info, both eye images
```

When you report a problem, include:
- the APK version from `build-info.json`;
- the scene where it happened;
- the start of `timecris-vr.log`, which lists the OpenXR runtime, controller profile, swapchain and refresh rate.

Never attach ROMs or the bundled APK.
