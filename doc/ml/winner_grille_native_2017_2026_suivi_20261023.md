# Suivi — grille Winner native 2017–2026

## Lancement du 23 octobre 2026

GO utilisateur : « Go pour test la grille ». Calcul complet lancé après un
smoke technique terminé et audité : profil SL3/TR3/H10/TP15 sur les vingt
premières séances2017, deux achats et deux sorties vérifiés par un résolveur
scalaire séparé. Cash, frais, positions finales et confirmations d'entrée
vérifiés. Ce test court ne constitue pas une mesure de performance exploitable.

**16 tests unitaires passent** : nouvelle grille/configuration/cohorte,
qualification des scores et résolveur de protections antérieur.
Protocole scellé avant les résultats :
[grille et limites](winner_grille_native_2017_2026_protocole_20261023.md).
Ne pas modifier ce protocole ni les sources liées par empreinte en cours de run.

Grille **300 profils LONG ×10comptesannuels =3 000comptes**. Deux processus
maximum. Capital annuel4000USD, frais8bps/jambe, B4DD15, HALF sans ajout ;
levier autorisé2x mais plafond effectif1x inchangé. Aucune production modifiée,
aucun entraînement, fournisseur ou ordre. Snapshots SQL READONLY, traces locales.

### Couverture : réserve majeure à garder dans la conclusion

Snapshot2017 : **213/1470signaux admissibles**,1 257réservés pour fenêtre
SIP5m maximale incomplète. La comparaison sera sur une cohorte commune aux
300profils, conditionnée par la disponibilité future de la couverture, pas
sur tout leTOP10 initial. Les titres exclus ne sont pas remplacés et leurs
rangs ne sont pas recalculés. Cette forte attrition est une réserve de
représentativité, pas un signal directionnel ni une preuve d'absence de cotation.
Les bilans de couverture des autres années restent à produire pendant le run.

2018 reste traitée en dernier, après le rattrapage SIP en cours. Le lanceur
attend sa fin complète sans redémarrer de téléchargement. Si la collecte
termine encore incomplète, la grille reste partielle : pas deTOP3 définitif.

## Où suivre et reprendre

Répertoire :
`artifacts/research/us_winner_native_grid_2017_2026/20261023-v1/`.

- `progress.json` : progression globale, années, erreurs et compteurs ;
- `year-2017.json` et équivalents : profil et séance courants, comptes terminés ;
- `inputs/<année>/cohort.json` : effectifs admissibles/motifs de réserve ;
- `cases/<année>-<profil>/report.json` : compte terminé avec audit ;
- `cases/.../failure.json` : diagnostic local en cas d'échec ;
- `annual-<année>.csv` : résultats au fur et à mesure de cette année ;
- logs : `log/winner-native-grid-2017-2026-20261023-v1.stdout.log` et `.stderr.log`.

Lancement :

```powershell
python -u -m scripts.research.us_winner_native_grid_2017_2026_20261023 --phase run --workers 2
```

Le même lancement reprend les comptes terminés après vérification des fichiers,
sans les recalculer. Verrou exclusif du dossier ; ne pas lancer un second
processus concurrent sur ce même run. Aucune reprise automatique du fournisseur.

Fichiers finaux uniquement après3 000comptes audités : `annual-summary.csv`,
`profile-ranking.csv`, `top3-one-parameter-neighbours.csv`, `report.json`.
SélectionTOP3 selon2017–2023, résultats2024–2026 publiés sans re-sélection.
Ces années ont déjà été observées : pas de holdout indépendant garanti.

À la rédaction : lancement effectué, **aucunTOP3 définitif disponible**.
Le compteur vivant du dossier fait foi, pas cette note statique ni le smoke.
