#!/bin/zsh
# Notification macOS (+ son) dès que reroll.log contient "THE SOUL TROUVÉ".
cd "$(dirname "$0")"
until grep -q "THE SOUL TROUVÉ" reroll.log 2>/dev/null; do
  pgrep -f reroll.py >/dev/null || { osascript -e 'display notification "Le script reroll.py s'\''est arrêté sans trouver The Soul" with title "Balatro" sound name "Basso"'; exit 1; }
  sleep 3
done
for i in 1 2 3; do afplay /System/Library/Sounds/Glass.aiff; done &
osascript -e 'display notification "THE SOUL trouvée ! Va appuyer sur Use dans Balatro." with title "Balatro 🃏" sound name "Glass"'
say "Soul trouvée" 2>/dev/null
