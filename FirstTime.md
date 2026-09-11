# First-time setup on a new phone

This guide covers a fresh Android phone and a fresh Mac checkout. It assumes
the phone is a OnePlus 8T (or another device with the same 2400x1080 landscape
layout). Other screen sizes will need coordinate changes in `reroll.py`.

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
2. Set the phone display to landscape and confirm the game is rendered at
   2400x1080.
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

## If the layout is different

The current script has fixed coordinates for 2400x1080 landscape mode. If a
different phone or display scaling is used, save a screenshot:

```sh
adb exec-out screencap -p > screen.png
```

Then compare it with `ref_charm_blind_screen.png` and update the coordinate
constants near the top of `reroll.py` before running the loop.
