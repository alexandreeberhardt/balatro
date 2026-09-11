#!/bin/zsh
# Lance la boucle de reroll Balatro (Charm Tag -> The Soul) sur le téléphone via ADB wifi.
# Usage : ./run.sh [IP:PORT]      (défaut : dernière adresse dans .adb_addr)
set -e
cd "$(dirname "$0")"

ADDR="${1:-$(cat .adb_addr 2>/dev/null || true)}"
if [[ -z "$ADDR" ]]; then
  echo "Usage: ./run.sh IP:PORT  (adresse affichée dans 'Débogage sans fil' sur le téléphone)"; exit 1
fi
echo "$ADDR" > .adb_addr

command -v tesseract >/dev/null || { echo "tesseract manquant : brew install tesseract"; exit 1; }
[[ -x .venv/bin/python ]] || { uv venv .venv -q && uv pip install -q --python .venv/bin/python -r requirements.txt; }

if ! adb connect "$ADDR" | grep -q connected; then
  echo "Connexion ADB impossible. Si le Mac n'est pas encore appairé :"
  echo "  téléphone -> Débogage sans fil -> Associer l'appareil avec un code"
  echo "  puis :  adb pair IP:PORT_APPAIRAGE CODE"
  exit 1
fi
adb shell wm size | grep -q 2400x1080 || echo "Attention : écran != 2400x1080, les coordonnées du script peuvent être fausses"

echo "Balatro doit être ouvert, en cours de run (n'importe quel écran avec le bouton Options)."
exec .venv/bin/python -u reroll.py 2>&1 | tee -a reroll.log
