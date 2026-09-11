# First-time setup on a new phone

This guide covers a fresh Android phone and a fresh Mac checkout. It also
explains how to calibrate the script when the phone uses a different display
size or aspect ratio.

## 1. Install the Mac tools

Install the command-line tools once:

```sh
brew install android-platform-tools tesseract
brew install uv
```

Check that they are available:

```sh
adb version
tesseract --version
uv --version
```

## 2. Prepare Balatro on the phone

1. Install Balatro and open it once.
2. Set the phone display to landscape. The reference setup is 2400x1080, but
   other sizes can work after calibration (see [Calibrate a different
   display](#calibrate-a-different-display)).
3. Open **Settings > About phone** and tap **Build number** seven times if
   Developer options are not already enabled.
4. In **Developer options**, enable **Wireless debugging**.
5. Put the Mac and phone on the same Wi-Fi network.

The script expects the game to be open and to have the **Options** button
visible before it starts. Select the deck and stake you want to reroll before
launching it.

## 3. Pair the phone with ADB

On the phone, open **Wireless debugging > Pair device with pairing code**. Note
the pairing IP and port, then run:

```sh
adb pair PHONE_IP:PAIRING_PORT PAIRING_CODE
```

For example:

```sh
adb pair 192.168.1.42:37123 123456
```

The phone will then show a separate IP and connection port on the Wireless
debugging screen. Connect with that second address:

```sh
adb connect PHONE_IP:ADB_PORT
adb devices
```

The device should appear as `PHONE_IP:ADB_PORT` with the state `device`.

Pairing and connecting use different ports. If `adb devices` shows
`unauthorized`, accept the authorization dialog on the phone and run the
command again.

## 4. Get the project ready

Clone the repository and enter it:

```sh
git clone https://github.com/alexandreeberhardt/balatro.git
cd balatro
```

`run.sh` creates `.venv/` and installs Pillow automatically the first time. To
prepare it manually instead:

```sh
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

The ADB address is stored in `.adb_addr` after the first launch. That file is
local-only and is intentionally ignored by Git.

## 5. Run it

With Balatro open and the Options button visible:

```sh
./run.sh PHONE_IP:ADB_PORT
```

Example:

```sh
./run.sh 192.168.1.42:41657
```

The script checks the screen size, connects to the phone, and starts the loop.
Leave the phone awake and in the foreground. Use `Ctrl+C` in the terminal to
stop it.

When the log says that **The Soul** was found, the card is selected but not
used. Tap **Use** on the phone to keep it.

## If the phone changes its address

Wireless ADB addresses can change after reconnecting to Wi-Fi. Read the new
connection address from **Developer options > Wireless debugging** and pass it
again:

```sh
./run.sh NEW_PHONE_IP:NEW_ADB_PORT
```

The new address replaces the local value in `.adb_addr`.

## Calibrate a different display

The script does not automatically scale coordinates. It reads a screenshot at
the phone's real output size, so every coordinate must describe that same
image. Start by checking the dimensions ADB reports:

```sh
adb shell wm size
adb exec-out screencap -p > screen.png
file screen.png
```

Open `screen.png` and make sure the game is actually in landscape. If the
display has the same 20:9 ratio as 2400x1080, you can scale the reference
coordinates with:

```text
new_x = old_x * new_width  / 2400
new_y = old_y * new_height / 1080
```

Round the results to whole pixels. If the aspect ratio is different, do not
use a single scale factor: Balatro may be letterboxed or shifted. Measure the
buttons and card centres directly from `screen.png` instead.

Update the coordinate block near the top of `reroll.py`. It includes the
buttons and tag locations (`OPTIONS`, `NEW_RUN`, `PLAY`, `SMALL_TAG`,
`BIG_TAG`, `SMALL_SKIP`, `BIG_SKIP`), the blind-state sample pixels, the pack
card centres, and the tooltip/pack boxes. Also update `SCREEN_W` to the exact
width reported by the screenshot. `BAND`, `PACK_BAND`, `PACK_BG_BOX`, and
`ICON_R` must use the same coordinate system too.

Keep the color thresholds (`CHARM_YES`, `CHARM_NO`, and `PURPLE_HUE`) unchanged
for the first test. Only adjust them if the classifier is wrong after the
coordinates are correct.

Before starting the full loop, test the classifier against the saved frame:

```sh
.venv/bin/python -c "import reroll; from PIL import Image; im=Image.open('screen.png').convert('RGB'); print(reroll.classify(im, reroll.SMALL_TAG), reroll.classify(im, reroll.BIG_TAG))"
```

The result should be `yes`, `no`, or `maybe` for each tag. Test the actual
button coordinates with Balatro open and watch the first cycle closely. Stop
with `Ctrl+C` if a tap lands outside its target, then adjust the corresponding
constant and capture another frame.

The original layout is still available for comparison:

```sh
open ref_charm_blind_screen.png
```

Once the screen, tags, buttons, and Arcana cards line up, run the command from
the previous section.
