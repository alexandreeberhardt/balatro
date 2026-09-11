# Balatro – reroll auto jusqu'à un joker légendaire (The Soul)

Boucle ADB qui relance des parties (Plasma Deck / White Stake) jusqu'à ce qu'un
**Charm Tag** soit présent sur le Small ou le Big Blind ET que le Mega Arcana Pack
obtenu contienne **The Soul**.

## Pré-requis (une seule fois)

- `adb` (Android platform-tools), `tesseract` (`brew install tesseract`), `uv`.
- Téléphone : OnePlus 8T, écran **2400x1080 en paysage** (toutes les coordonnées
  du script sont en dur pour cette résolution).
- Appairage ADB wifi (à refaire seulement si le Mac n'est plus appairé) :
  1. Téléphone → Options développeur → Débogage sans fil → *Associer l'appareil avec un code*.
  2. `adb pair 10.241.82.253:PORT_APPAIRAGE CODE_6_CHIFFRES`
     (le port d'appairage est différent du port de connexion).

## Lancer

1. Sur le téléphone : ouvrir Balatro, démarrer/être dans une run (n'importe quel
   écran où le bouton **Options** est visible en bas à gauche). Deck et stake sont
   ceux déjà sélectionnés dans le menu New Run (Plasma / White au moment de l'écriture).
2. Débogage sans fil activé ; noter l'`IP:PORT` affiché (il change souvent).
3. `./run.sh 10.241.82.253:41657` (ou `./run.sh` pour reprendre la dernière adresse).
4. Le script s'arrête tout seul quand The Soul est trouvé, **la carte est
   sélectionnée mais pas encore utilisée** : il reste à appuyer sur *Use* sur
   le téléphone. Captures : `soul_found.png`, `soul_selected.png`.

`Ctrl+C` pour arrêter. Le log s'accumule dans `reroll.log`.

## Comment ça marche (`reroll.py`)

Cycle rapide (~3,5 s par run) :
1. `Play` → attente 2,4 s (transition + animation des cartes de blind).
2. Capture **partielle** de l'écran : seules les lignes 840-1000 (icônes de tag +
   boutons Skip) sont transférées, en raw+gzip (~400 Ko au lieu d'un PNG de 1,4 Mo ;
   le wifi à ~1 Mo/s est le goulot). Pendant ce transfert, le script ouvre déjà
   `Options → New Run` pour le run suivant (la capture est prise dans les 100
   premières ms de la commande, avant l'apparition du menu).
3. Vérifie que la carte du Small Blind est en place (bouton Skip rouge en haut et en bas).
4. **Détecteur Charm** : part de pixels saturés de teinte 235-265° (le disque violet
   du Charm Tag) dans chaque icône. Charm ≈ 240 ‰, tout le reste ≤ 63 ‰
   (Polychrome). ≥ 150 → Charm ; ≤ 90 → non ; entre les deux → confirmation par OCR
   du tooltip (tap sur l'icône, tesseract).
5. Pas de Charm → `Play` (le menu New Run est déjà ouvert). Charm → `Back`, puis
   (toujours en captures partielles, ~4 s pour le Small, ~7 s pour le Big) :
   - Charm sur le Small Blind : *Skip Blind* → attente 2,2 s → capture des lignes
     700-800 : pack Arcana ouvert si le fond de table est violet (teinte ~265° au
     lieu du vert ~155°), puis recherche de The Soul (carte bleu foncé parmi des
     tarots beiges : `r - b < 30` sur la couleur moyenne de chaque emplacement).
   - Charm sur le Big Blind : skip du Small (à l'ante 1 aucun autre tag n'ouvre de
     pack ; si le Small était aussi Charm, son pack est fermé), attente du bouton
     Skip rouge du Big Blind, skip du Big → même vérification.
   - Si un tap est avalé (pack/blind absent), il est rejoué une fois.
   - Un candidat Soul est confirmé (frame stable 0,7 s plus tard + capture complète
     + OCR "Arcana") avant d'être sélectionné.

Détails importants :
- Balatro génère le seed à partir de la position du curseur au clic : les taps sont
  légèrement aléatoires (`jitter`), sinon on retombe sur les mêmes runs.
- Les icônes du Big Blind ("Upcoming") sont assombries ; le détecteur de teinte y est
  insensible, contrairement à un histogramme couleur (abandonné).
- `tags/` (bibliothèque d'icônes par histogramme) ne sert plus qu'à nommer les tags
  dans le log ; elle n'est plus indispensable.
- `adb shell settings put` et `wm size` sont bloqués sur ce téléphone (OxygenOS).
  Balatro garde l'écran allumé (KEEP_SCREEN_ON) tant qu'il est au premier plan.

## Fichiers

- `reroll.py` : la boucle. Coordonnées et seuils en haut du fichier.
- `tags/` : bibliothèque d'icônes apprise (`tags.json` + crops PNG), utilisée
  seulement pour nommer les tags dans le log.
- `run.sh` : connexion ADB + venv + lancement.
- `requirements.txt` : `pillow` (venv dans `.venv/`).
- `.adb_addr` : dernière adresse IP:PORT utilisée.
- `ref_charm_blind_screen.png` : capture de référence de l'écran de blinds avec un
  Charm Tag sur le Small Blind (utile pour recalibrer les coordonnées/seuils).
- `debug_*.png`, `soul_*.png` : captures produites par le script (échecs / succès).

## Si ça casse

- Le script s'appuie sur des pixels fixes (bouton Select orange, Skip rouge, icônes
  à (814,906) et (1176,968)). Si Balatro ou l'écran change, prendre une capture
  (`adb exec-out screencap -p > s.png`) et ajuster les constantes en tête de `reroll.py`.
- Pour vérifier le détecteur Charm sur une capture : 
  `.venv/bin/python -c "import reroll; from PIL import Image; im=Image.open('s.png').convert('RGB'); print(reroll.classify(im, reroll.SMALL_TAG), reroll.classify(im, reroll.BIG_TAG))"`
- Si les runs se ressemblent (même boss, mêmes tags), c'est le seed lié au curseur :
  augmenter le `jitter` du tap sur Play.
