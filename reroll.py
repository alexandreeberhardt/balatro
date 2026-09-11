#!/usr/bin/env python3
"""Reroll Balatro runs over ADB until a Charm Tag (Mega Arcana Pack) contains The Soul.

Per run: Options -> New Run -> Play, one screenshot, identify the Small/Big blind tag
icons against a self-learned library (tags/). Unknown or Charm-looking icons are
confirmed by tapping them and OCR-ing the tooltip. If a Charm Tag is present, skip
up to that blind, open the pack and look for The Soul (dark blue card among tan
tarot cards).
"""
import subprocess, sys, time, io, re, random, difflib, json, os, gzip, threading, colorsys
from PIL import Image

# Screen is 2400x1080 landscape
OPTIONS = (318, 944)
NEW_RUN = (1194, 330)
PLAY = (1196, 820)
SMALL_TAG = (814, 906)
BIG_TAG = (1176, 968)
SMALL_SKIP = (940, 906)
BIG_SKIP = (1308, 908)          # once Big Blind is the current blind
SMALL_SELECT_PX = (820, 355)    # orange when Small Blind is current
BIG_SELECT_PX = (1200, 380)     # orange when Big Blind is current
SMALL_SKIP_PX = (870, 870)      # red once the Small Blind card has settled
SKIP_SETTLED_PX = [(870, 872), (870, 934)]  # top & bottom of the Skip button: both red = card in place
BAND = (840, 1000)              # rows fetched by the fast path (tags + skip buttons)
SCREEN_W = 2400
TOOLTIP_BOX = (650, 380, 1650, 930)
PACK_LABEL_BOX = (1100, 930, 1420, 1060)   # "Arcana Pack / Choose 2"
PACK_SKIP = (1566, 960)
NEUTRAL = (2000, 150)           # empty background, safe to tap
BACK_NEW_RUN = (1194, 936)      # Back button of the New Run menu (returns straight to the game)
PACK_CARDS_X = [912, 1090, 1266, 1446, 1626]  # 5 card centres of a mega pack
PACK_CARDS_Y = 750
PACK_BAND = (700, 800)                     # rows: pack cards + right-hand background
PACK_BG_BOX = (2100, 710, 2350, 790)       # table background: green (h~155) or Arcana purple (h~265)
BIG_SKIP_SETTLED_PX = [(1240, 872), (1240, 934)]  # Big Blind's Skip button, once Big is current
OUT = os.path.dirname(os.path.abspath(__file__))
TAG_DIR = os.path.join(OUT, "tags")
ICON_R = 28                     # icon crop half-size
ICON_MATCH = 4.8                # colour-histogram distance below which an icon is named (log only)
# Charm detector: share (per mille) of saturated pixels with hue 235-265 (Charm's purple disc).
# Measured: Charm 236-246, next best (Polychrome) <= 63, everything else <= 25.
PURPLE_HUE = (235, 265)
CHARM_YES = 150                 # above: Charm for sure
CHARM_NO = 90                   # below: certainly not Charm; in between -> OCR confirm

KNOWN_TAGS = ["Uncommon", "Rare", "Negative", "Foil", "Holographic", "Polychrome",
              "Investment", "Voucher", "Boss", "Standard", "Charm", "Meteor", "Buffoon",
              "Handy", "Garbage", "Ethereal", "Coupon", "Double", "Juggle", "D6",
              "Top-up", "Speed", "Orbital", "Economy"]

# ---------------------------------------------------------------- device helpers
def adb(*args, binary=False):
    r = subprocess.run(["adb", *args], capture_output=True)
    return r.stdout if binary else r.stdout.decode(errors="ignore")

def tap(xy, wait=0.8, jitter=12):
    # Balatro seeds new runs from the cursor position: jitter taps so runs differ
    x = xy[0] + random.randint(-jitter, jitter)
    y = xy[1] + random.randint(-jitter, jitter)
    adb("shell", "input", "tap", str(x), str(y))
    time.sleep(wait)

def screenshot():
    return Image.open(io.BytesIO(adb("exec-out", "screencap", "-p", binary=True))).convert("RGB")

class Band:
    """A horizontal strip of the screen (rows BAND[0]..BAND[1]) addressed in screen coordinates."""
    def __init__(self, im, oy):
        self.im, self.oy = im, oy
    def getpixel(self, xy):
        return self.im.getpixel((xy[0], xy[1] - self.oy))
    def crop(self, box):
        return self.im.crop((box[0], box[1] - self.oy, box[2], box[3] - self.oy))

def grab_band_async():
    """Start a band grab in a thread; returns a callable that waits for and returns the Band."""
    res = {}
    t = threading.Thread(target=lambda: res.setdefault("b", grab_band()))
    t.start()
    def result():
        t.join()
        return res.get("b")
    return result

def blind_settled(band):
    return band is not None and all(is_red(band.getpixel(p)) for p in SKIP_SETTLED_PX)

def grab_band(y0=BAND[0], y1=BAND[1]):
    """Fetch only rows y0..y1 as raw RGBA piped through gzip: ~4x less wifi traffic than a PNG."""
    row = SCREEN_W * 4
    cmd = f"screencap | tail -c +{16 + y0 * row + 1} | head -c {(y1 - y0) * row} | gzip -1"
    out = adb("exec-out", cmd, binary=True)
    try:
        raw = gzip.decompress(out)
        im = Image.frombytes("RGBA", (SCREEN_W, y1 - y0), raw).convert("RGB")
    except Exception:
        return None
    return Band(im, y0)

def ocr(img, psm=6):
    buf = io.BytesIO(); img.save(buf, format="PNG")
    r = subprocess.run(["tesseract", "stdin", "stdout", "--psm", str(psm)],
                       input=buf.getvalue(), capture_output=True)
    return r.stdout.decode(errors="ignore")

# ---------------------------------------------------------------- pixel helpers
def is_orange(px):
    r, g, b = px[:3]
    return r > 200 and 100 < g < 200 and b < 80

def is_red(px):
    r, g, b = px[:3]
    return r > 170 and g < 120 and b < 120

def is_white(p):
    return p[0] > 235 and p[1] > 235 and p[2] > 235

def mean_color(im, box):
    reg = im.crop(box)
    px = list(reg.get_flattened_data()) if hasattr(reg, "get_flattened_data") else list(reg.getdata())
    n = len(px)
    return tuple(sum(p[i] for p in px) // n for i in range(3))

# ---------------------------------------------------------------- tag icon library
def icon_sig(im, xy):
    """4x4x4 RGB colour histogram (per mille) of the icon: robust to the idle wobble."""
    x, y = xy
    crop = im.crop((x - ICON_R, y - ICON_R, x + ICON_R, y + ICON_R))
    px = list(crop.get_flattened_data()) if hasattr(crop, "get_flattened_data") else list(crop.getdata())
    h = [0] * 64
    for r, g, b in px:
        h[(r // 64) * 16 + (g // 64) * 4 + (b // 64)] += 1
    return [v * 1000 / len(px) for v in h], crop

def sig_dist(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)

class TagLibrary:
    """Icon signatures per (position, tag name), persisted in tags/tags.json."""
    def __init__(self):
        os.makedirs(TAG_DIR, exist_ok=True)
        self.path = os.path.join(TAG_DIR, "tags.json")
        self.db = json.load(open(self.path)) if os.path.exists(self.path) else {}

    def _pos(self, xy):
        return "small" if xy == SMALL_TAG else "big"

    def nearest(self, sig, xy):
        best = (None, 1e9)
        charm = 1e9
        for name, sigs in self.db.get(self._pos(xy), {}).items():
            for s in sigs:
                d = sig_dist(sig, s)
                if d < best[1] and name != "Charm?":
                    best = (name, d)
                if name.startswith("Charm") and d < charm:
                    charm = d
        return best[0], best[1], charm

    def add(self, sig, crop, xy, name):
        pos = self._pos(xy)
        sigs = self.db.setdefault(pos, {}).setdefault(name, [])
        if len(sigs) < 8:
            sigs.append(sig)
            crop.save(os.path.join(TAG_DIR, f"{pos}_{name}_{len(sigs)}.png"))
            json.dump(self.db, open(self.path, "w"))

def dim_like_upcoming(crop):
    """Approximate how an 'Upcoming' (Big Blind) column dims an icon: 0.6*c + dark teal."""
    r, g, b = crop.split()
    return Image.merge("RGB", (r.point(lambda v: int(v * 0.6 + 10)),
                              g.point(lambda v: int(v * 0.6 + 20)),
                              b.point(lambda v: int(v * 0.6 + 22))))

LIB = TagLibrary()

def seed_charm_big():
    """Until a real dimmed Charm icon is learned, use a synthetic one as a 'suspect' reference."""
    if "Charm?" in LIB.db.get("big", {}) or "Charm" in LIB.db.get("big", {}):
        return
    p = os.path.join(TAG_DIR, "small_Charm_1.png")
    if os.path.exists(p):
        crop = dim_like_upcoming(Image.open(p).convert("RGB"))
        sig, _ = icon_sig(crop, (ICON_R, ICON_R))
        LIB.db.setdefault("big", {})["Charm?"] = [sig]
        json.dump(LIB.db, open(LIB.path, "w"))

seed_charm_big()

# ---------------------------------------------------------------- tag reading (OCR)
def tooltip_title(im, xc):
    """Locate the white tooltip body above the tag at x=xc and OCR its title bar."""
    x0, y0 = xc - 320, 380
    reg = im.crop((x0, y0, xc + 320, 900))
    w, h = reg.size
    px = reg.load()
    rows = [sum(1 for x in range(0, w, 2) if is_white(px[x, y])) * 2 for y in range(h)]
    top = next((y for y in range(h - 12) if all(rows[y + k] > 150 for k in range(12))), None)
    if top is None:
        return None
    cols = [x for x in range(w) if all(is_white(px[x, top + k]) for k in range(4))]
    if not cols:
        return None
    # keep the run of white columns nearest the tag (ignore side boxes like "+50 chips")
    cx = xc - x0
    runs, start = [], cols[0]
    for a, b in zip(cols, cols[1:] + [None]):
        if b is None or b > a + 20:
            runs.append((start, a)); start = b
    lo, hi = min(runs, key=lambda r: 0 if r[0] <= cx <= r[1] else min(abs(r[0] - cx), abs(r[1] - cx)))
    crop = im.crop((x0 + lo, y0 + top - 75, x0 + hi, y0 + top))
    crop = crop.resize((crop.width * 3, crop.height * 3))
    return ocr(crop, psm=7).strip()

TAG_RE = re.compile(r"([A-Za-z0-9\-]+)\s+[TIl]a[gq]")

def normalize_tag(word):
    """Map an OCR'd tag name onto the closest known tag (or keep it as is)."""
    m = difflib.get_close_matches(word.lower(), [t.lower() for t in KNOWN_TAGS], n=1, cutoff=0.6)
    return KNOWN_TAGS[[t.lower() for t in KNOWN_TAGS].index(m[0])] if m else word

def is_charm(word):
    w = word.lower()
    return w == "charm" or "arm" in w or difflib.SequenceMatcher(None, w, "charm").ratio() >= 0.7

def read_tag_ocr(xy, tries=3):
    """Tap the tag icon, OCR its tooltip. Returns (name, screenshot)."""
    im = None
    for attempt in range(tries):
        tap(xy, 1.0, jitter=0)
        im = screenshot()
        text = tooltip_title(im, xy[0]) or ""
        m = TAG_RE.search(text)
        if not m:  # fallback: OCR the whole tooltip area
            crop = im.crop(TOOLTIP_BOX)
            crop = crop.resize((crop.width * 2, crop.height * 2))
            m = TAG_RE.search(ocr(crop))
        if m:
            return normalize_tag(m.group(1)), im
        im.save(f"{OUT}/debug_tag_{xy[0]}_{attempt}.png")
        time.sleep(0.4)
    return "?", im

def purple_frac(crop):
    px = list(crop.get_flattened_data()) if hasattr(crop, "get_flattened_data") else list(crop.getdata())
    c = 0
    for r, g, b in px:
        h, sat, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if PURPLE_HUE[0] <= h * 360 <= PURPLE_HUE[1] and sat >= 0.2 and v > 0.2:
            c += 1
    return 1000 * c / len(px)

def classify(im, xy):
    """Charm detector on the icon at xy. Returns (verdict, info) with verdict in yes/no/maybe."""
    sig, crop = icon_sig(im, xy)
    pf = purple_frac(crop)
    name, d, _ = LIB.nearest(sig, xy)
    label = name if (name is not None and d < ICON_MATCH) else "?"
    verdict = "yes" if pf >= CHARM_YES else "no" if pf <= CHARM_NO else "maybe"
    return verdict, f"{label}(p{pf:.0f})"

def match_icon(im, xy):
    """Identify the tag at xy from its icon alone. Returns (name, info, sure)."""
    sig, crop = icon_sig(im, xy)
    name, d, dcharm = LIB.nearest(sig, xy)
    if name is not None and d < ICON_MATCH and (dcharm > CHARM_SUSPECT or name == "Charm"):
        return name, f"{name}~{d:.0f}", True
    return name, f"?(nearest {name}~{d:.0f})", False

def read_tag(im, xy):
    """Identify the tag at xy from its icon; fall back to tap+OCR and learn the icon."""
    name, info, sure = match_icon(im, xy)
    if sure:
        return name, info
    sig, crop = icon_sig(im, xy)
    d = info
    ocr_name, _ = read_tag_ocr(xy)
    tap(NEUTRAL, 0.4)  # dismiss the tooltip so the next tap is not swallowed
    if ocr_name in KNOWN_TAGS:
        LIB.add(sig, crop, xy, ocr_name)
    return ocr_name, f"{ocr_name} (ocr; {info})"

# ---------------------------------------------------------------- screens
def wait_blind_screen(timeout=8):
    """Wait until the Small Blind card is in place (Skip button red at top and bottom)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        band = grab_band()
        if blind_settled(band):
            return band
        time.sleep(0.3)
    return None

def wait_pixel(px, pred, timeout=8, settle=1.5):
    t0 = time.time()
    while time.time() - t0 < timeout:
        im = screenshot()
        if pred(im.getpixel(px)):
            time.sleep(settle)
            return screenshot()
        time.sleep(0.5)
    return None

def pack_label(im):
    return ocr(im.crop(PACK_LABEL_BOX).resize((640, 260))).lower()

def pack_open(im):
    t = pack_label(im)
    return "pack" in t or "choose" in t

def wait_pack(timeout=8):
    t0 = time.time()
    while time.time() - t0 < timeout:
        im = screenshot()
        if pack_open(im):
            time.sleep(1.5)  # cards fan out
            return screenshot()
        time.sleep(0.7)
    return None

def find_soul(im):
    """Return index of a non-tan (dark/blue) card among the 5 pack slots, or None."""
    found = None
    cols = []
    for i, cx in enumerate(PACK_CARDS_X):
        r, g, b = mean_color(im, (cx - 40, PACK_CARDS_Y - 40, cx + 40, PACK_CARDS_Y + 40))
        cols.append((r, g, b))
        if r - b < 30:      # tarot cards are tan: r - b ~ 80-100
            found = i
    return found, cols

def skip_blind(skip_xy, select_px, tries=3):
    """Tap Skip Blind and verify the blind is gone (its Select button no longer orange)."""
    for _ in range(tries):
        tap(skip_xy, 1.5, jitter=0)
        if not is_orange(screenshot().getpixel(select_px)):
            return True
    return False

def arcana_open(band):
    """Arcana pack overlay detected by the purple table background."""
    if band is None:
        return False
    r, g, b = mean_color(band, PACK_BG_BOX)
    h, sat, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return 240 <= h * 360 <= 300 and sat > 0.2

def wait_band(pred, y0, y1, tries=4, pause=0.5):
    for _ in range(tries):
        band = grab_band(y0, y1)
        if pred(band):
            return band
        time.sleep(pause)
    return None

def check_pack_fast(n, label, retap=None):
    """Pack should be open (or opening). Returns True if The Soul is found and selected."""
    band = wait_band(arcana_open, *PACK_BAND)
    if band is None and retap is not None:
        tap(retap, 2.3, jitter=0)          # the skip tap may have been swallowed
        band = wait_band(arcana_open, *PACK_BAND)
    if band is None:
        print(f"[{n}] {label}: Arcana pack non détecté", flush=True)
        screenshot().save(f"{OUT}/debug_pack_{n}.png")
        return False
    idx, cols = find_soul(band)
    print(f"[{n}] {label}: cartes {cols} -> soul={idx}", flush=True)
    if idx is None:
        return False
    # Rare path: confirm on a stable frame + full screenshot + label OCR before acting
    time.sleep(0.7)
    idx2, _ = find_soul(grab_band(*PACK_BAND))
    im = screenshot()
    if idx2 != idx or "arcana" not in pack_label(im):
        print(f"[{n}] {label}: candidat Soul non confirmé (idx2={idx2})", flush=True)
        im.save(f"{OUT}/debug_pack_{n}.png")
        return False
    im.save(f"{OUT}/soul_found.png")
    tap((PACK_CARDS_X[idx], PACK_CARDS_Y), 1.5, jitter=0)
    screenshot().save(f"{OUT}/soul_selected.png")
    return True

def close_pack_if_any(tries=3):
    for _ in range(tries):
        im = screenshot()
        if not pack_open(im):
            return True
        tap(PACK_SKIP, 2.0)
    return False

def press_play():
    time.sleep(random.uniform(0, 0.3))
    tap(PLAY, 2.4, jitter=40)

def new_run():
    tap(OPTIONS, 0.45)
    tap(NEW_RUN, 0.45)
    press_play()

def check_pack(n, label):
    """Pack should be opening now. Returns True if The Soul is found (and left on screen)."""
    im = wait_pack()
    if im is None:
        print(f"[{n}] {label}: pack non détecté", flush=True)
        screenshot().save(f"{OUT}/debug_pack_{n}.png")
        return False
    if "arcana" not in pack_label(im):
        print(f"[{n}] {label}: pack ouvert mais pas un Arcana Pack ?", flush=True)
        im.save(f"{OUT}/debug_pack_{n}.png")
        return False
    idx, cols = find_soul(im)
    print(f"[{n}] {label}: cartes {cols} -> soul={idx}", flush=True)
    if idx is not None:
        im.save(f"{OUT}/soul_found.png")
        tap((PACK_CARDS_X[idx], PACK_CARDS_Y), 1.5, jitter=0)
        screenshot().save(f"{OUT}/soul_selected.png")
        return True
    return False

# ---------------------------------------------------------------- main loop
def charm_flow(n, small_charm, big_charm):
    """Skip up to the Charm blind(s) and check the pack(s). Returns True if The Soul was found.
    At ante 1 no other tag opens a pack, so skipping a non-Charm Small Blind is instantaneous."""
    tap(SMALL_SKIP, 0.0, jitter=0)
    if small_charm:
        time.sleep(2.2)                     # pack opening + cards fanning out
        if check_pack_fast(n, "small", retap=SMALL_SKIP):
            print(f"THE SOUL TROUVÉ après {n} runs (Small Blind)", flush=True)
            return True
        if not big_charm:
            return False
        tap(PACK_SKIP, 1.0, jitter=0)
    else:
        time.sleep(1.0)
    big_ready = lambda b: b is not None and all(is_red(b.getpixel(p)) for p in BIG_SKIP_SETTLED_PX)
    if wait_band(big_ready, *BAND) is None:
        tap(PACK_SKIP if small_charm else SMALL_SKIP, 1.0, jitter=0)   # retry the swallowed tap
        if wait_band(big_ready, *BAND) is None:
            print(f"[{n}] Big Blind pas sélectionnable", flush=True)
            screenshot().save(f"{OUT}/debug_{n}.png")
            return False
    tap(BIG_SKIP, 2.2, jitter=0)
    if check_pack_fast(n, "big", retap=BIG_SKIP):
        print(f"THE SOUL TROUVÉ après {n} runs (Big Blind)", flush=True)
        return True
    return False

def main():
    n = 0
    t_start = time.time()
    new_run()
    t0 = time.time() - 2.4
    while True:
        n += 1
        # Fast path: fetch the tag band while already opening the New Run menu for the next run.
        # screencap grabs the frame within ~100 ms, well before the Options menu shows up.
        pending = grab_band_async()
        time.sleep(0.25)
        tap(OPTIONS, 0.45)
        tap(NEW_RUN, 0.2)
        band = pending()
        menu_open = True
        if not blind_settled(band):
            tap(BACK_NEW_RUN, 0.6, jitter=0)
            menu_open = False
            band = wait_blind_screen()
            if band is None:
                print(f"[{n}] pas sur l'écran de blinds, retry", flush=True)
                screenshot().save(f"{OUT}/debug_{n}.png")
                adb("shell", "input", "keyevent", "111")  # ESC to close any dialog
                time.sleep(1)
                new_run()
                continue
        v1, info1 = classify(band, SMALL_TAG)
        v2, info2 = classify(band, BIG_TAG)
        if v1 == "no" and v2 == "no":
            print(f"[{n}] Small: {info1:28s} Big: {info2:28s} ({time.time()-t0:.1f}s, moy {(time.time()-t_start)/n:.1f}s)", flush=True)
            if not menu_open:
                tap(OPTIONS, 0.45); tap(NEW_RUN, 0.2)
            press_play()
            t0 = time.time() - 2.4
            continue
        # Slow path: Charm (or ambiguous icon) -> back to the game screen, OCR if needed, skip flow
        if menu_open:
            tap(BACK_NEW_RUN, 0.6, jitter=0)
        if v1 == "maybe":
            t1, info1 = read_tag(band, SMALL_TAG); v1 = "yes" if is_charm(t1) else "no"
        if v2 == "maybe":
            t2, info2 = read_tag(band, BIG_TAG); v2 = "yes" if is_charm(t2) else "no"
        print(f"[{n}] Small: {info1:28s} Big: {info2:28s} ({time.time()-t0:.1f}s, moy {(time.time()-t_start)/n:.1f}s)", flush=True)
        small_charm, big_charm = v1 == "yes", v2 == "yes"
        if (small_charm or big_charm) and charm_flow(n, small_charm, big_charm):
            return
        new_run()
        t0 = time.time() - 2.4

if __name__ == "__main__":
    main()
