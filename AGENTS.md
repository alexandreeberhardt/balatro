# Agent guide

This file gives coding agents the context needed to work on this repository
without guessing how the phone, game, or screen calibration works.

## Project in one paragraph

This repository contains a macOS shell/Python tool that controls Balatro on an
Android phone over wireless ADB. It repeatedly opens New Run, reads the Small
and Big Blind tags from screenshots, skips to a Charm Tag, checks the Arcana
Pack, and stops after selecting The Soul. It is a personal automation project,
not an official Balatro integration.

## Repository map

- `reroll.py`: main loop, image processing, OCR, tap coordinates, and timing.
- `run.sh`: validates local tools, creates `.venv/`, connects ADB, and starts
  `reroll.py`.
- `notify_soul.sh`: optional macOS notification helper watching `reroll.log`.
- `requirements.txt`: Python dependencies. Keep this small unless there is a
  clear reason to add another dependency.
- `tags/`: learned icon crops and `tags.json`; useful for names in logs, but
  not required for the color-based Charm detector.
- `ref_charm_blind_screen.png`: reference screenshot for calibration.
- `banner.png`: README banner.
- `README.md`: short project overview and quick start.
- `FirstTime.md`: complete setup and display-calibration guide for a new phone.

Generated local files are intentionally ignored: `.venv/`, `.adb_addr`,
`reroll.log`, `debug_*.png`, `soul_*.png`, Python caches, and macOS metadata.
Do not commit them unless the user explicitly asks for a diagnostic artifact.

## New clone, new phone: complete workflow

Follow these steps in order. Do not assume that the phone has the reference
resolution.

1. Install the Mac tools:

   ```sh
   brew install android-platform-tools tesseract
   brew install uv
   ```

2. Clone the repository:

   ```sh
   git clone https://github.com/alexandreeberhardt/balatro.git
   cd balatro
   ```

3. On the phone, install and open Balatro, enable Developer options and
   Wireless debugging, set the game to landscape, and connect the phone and
   Mac to the same Wi-Fi network.

4. Pair and connect ADB. The pairing port is different from the normal ADB
   connection port:

   ```sh
   adb pair PHONE_IP:PAIRING_PORT PAIRING_CODE
   adb connect PHONE_IP:ADB_PORT
   adb devices
   ```

   Continue only when the device appears with state `device`. If it says
   `unauthorized`, accept the prompt on the phone.

5. Check the actual output size before touching the script:

   ```sh
   adb shell wm size
   adb exec-out screencap -p > screen.png
   file screen.png
   ```

6. Calibrate the script if the screenshot is not 2400x1080. Use the procedure
   below. Do not launch the unattended loop first.

7. With Balatro on a screen where **Options** is visible, start a supervised
   first cycle:

   ```sh
   ./run.sh PHONE_IP:ADB_PORT
   ```

8. Watch every first tap and stop with `Ctrl+C` if a tap misses. Once the first
   cycle is correct, the address is saved in the ignored `.adb_addr` file and
   later launches can use `./run.sh`.

## Calibration for an unknown phone format

The script uses absolute coordinates. It does not automatically scale or
detect the UI. The screenshot is the source of truth.

### Same aspect ratio

For a display with the same 20:9 ratio as 2400x1080, scale every reference
coordinate:

```text
new_x = old_x * actual_width  / 2400
new_y = old_y * actual_height / 1080
```

Round to whole pixels. Update `SCREEN_W` as well, because the fast screenshot
path reconstructs raw rows using that width.

### Different aspect ratio, letterboxing, or offsets

Do not use one global scale factor. Balatro may be centered inside a wider or
taller frame. Open `screen.png`, identify the actual game rectangle, and
measure each target in the screenshot. If the game is offset, include the
offset in each coordinate.

Update the coordinate block near the top of `reroll.py`:

- navigation: `OPTIONS`, `NEW_RUN`, `PLAY`, `BACK_NEW_RUN`;
- blind tags and skip buttons: `SMALL_TAG`, `BIG_TAG`, `SMALL_SKIP`,
  `BIG_SKIP`;
- blind-state sample pixels: `SMALL_SELECT_PX`, `BIG_SELECT_PX`,
  `SMALL_SKIP_PX`, `SKIP_SETTLED_PX`, `BIG_SKIP_SETTLED_PX`;
- screenshot regions: `BAND`, `TOOLTIP_BOX`, `PACK_LABEL_BOX`, `PACK_BAND`,
  `PACK_BG_BOX`;
- pack interaction: `PACK_SKIP`, `PACK_CARDS_X`, `PACK_CARDS_Y`, `NEUTRAL`;
- icon geometry: `ICON_R`.

Keep `CHARM_YES`, `CHARM_NO`, and `PURPLE_HUE` unchanged at first. Those are
detector thresholds, not screen coordinates. Change them only after the
coordinates are correct and a saved screenshot proves the detector is wrong.

### Calibration checks

Run the classifier on a saved screenshot:

```sh
.venv/bin/python -c "import reroll; from PIL import Image; im=Image.open('screen.png').convert('RGB'); print(reroll.classify(im, reroll.SMALL_TAG), reroll.classify(im, reroll.BIG_TAG))"
```

The output should be plausible (`yes`, `no`, or `maybe`) for both tag
locations. Then verify, in the game, that these targets are correct in order:

1. Options
2. New Run
3. Play
4. Small/Big tag icons
5. Small/Big Skip buttons
6. Arcana Pack card centres

Save useful calibration frames with descriptive names. Do not overwrite the
reference image without permission.

## Technical assumptions and pitfalls

- The reference display is 2400x1080 in landscape.
- ADB wireless addresses can change whenever the phone reconnects to Wi-Fi.
- Pairing and connecting use separate ports.
- The phone must stay awake and Balatro must remain in the foreground.
- The script expects the Options button to be visible at startup.
- Balatro can use tap position when generating a seed. The tap jitter in
  `reroll.py` is intentional; removing it can produce repeated runs.
- The fast path reads raw screenshot rows and depends on `SCREEN_W`, `BAND`,
  and the phone's real screenshot dimensions all agreeing.
- The Big Blind tag is dimmed as an upcoming blind. Do not replace the hue
  detector with a brightness-only test.
- OCR is a fallback for ambiguous tags. Keep `tesseract` as a prerequisite.
- `wm size` changes may be blocked by some Android builds. Prefer calibrating
  the script to the real screenshot instead of relying on a display override.

## Safe development workflow

Before changing behavior:

1. Read the constants at the top of `reroll.py` and the relevant section in
   `FirstTime.md`.
2. Preserve the user's local runtime files and do not commit ignored output.
3. Run a syntax check:

   ```sh
   .venv/bin/python -m py_compile reroll.py
   ```

4. Run `git diff --check` and inspect the diff.
5. Make focused commits with no `Co-authored-by` trailer. Push only after the
   worktree is clean and the requested behavior has been checked.

Do not run the live loop against a phone while changing coordinates unless the
user has asked for an on-device test. A screenshot-based check is safer and
usually enough to catch bad dimensions or crop regions.
