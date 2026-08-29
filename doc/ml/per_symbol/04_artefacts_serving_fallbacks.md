# 4 — Artefacts, serving et fallbacks

## Artefacts

Le dossier du symbole contient checkpoint LSTM, scaler, calibrateur éventuel,
config et routes ; les tabulaires ont modèle/config propres et les horizons
secondaires leurs sous-dossiers. Un manifeste SHA256 signe checkpoint, scaler,
modèle, config et calibrateur présents pour chaque route.

## Résolution

`predict_symbol` résout d’abord les artefacts du symbole et du batch/run. Si le
modèle per-symbol n’existe pas, `_resolve_sector_run` peut trouver le run du
secteur. La source persistée est classée `per_symbol` ou `per_sector` depuis le
run réellement résolu, pas depuis le symbole demandé.

La configuration `research_only` bloque l’inférence. Le fingerprint des features
est vérifié. Si les signatures sont obligatoires, une absence ou divergence
SHA256 rend la route invalide. Les modèles sont chargés via caches tenant compte
de taille/mtime ; des fonctions permettent de vider les caches.

## Prédiction

Le chemin reconstruit les features PIT, valide que la dernière date correspond
au cutoff, applique scaler/modèle/calibrateur et transforme la sortie selon le
mode binaire, ternaire ou régression. La ligne persistée conserve modèle servi,
seuil, méthode de calibration, side/probas, disponibilité et source.

Une route globale cassée peut retomber sur LSTM si la config le permet. Une
absence d’artefact dans un batch explicitement dépourvu de per-symbol/per-sector
est normale et évite un warning par symbole ; dans un batch qui en contient,
elle est une anomalie.

