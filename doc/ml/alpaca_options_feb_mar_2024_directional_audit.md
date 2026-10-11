# Options téléchargées : février–mars 2024, avec et sans TOP20 Oracle

Audit du 11 octobre 2026. Recherche exploratoire uniquement : aucune API appelée,
aucun entraînement, ordre, écriture SQL ou modification du téléchargement actif.

## Données et règles figées

Univers gelé du backfill : 1 790 titres actuels. 84 303 barres options examinées ;
10 994 paires titre/date, 1 246 titres, 39 dates avec options exploitables.
Février : 1 448 tâches complètes, 334 vides, 8 échouées ; mars : 1 542 complètes,
240 vides, 8 échouées. Aucune barre options le 2 février : lacune observée,
cause non résolue, aucune imputation. Aucun conflit de versions détecté.

Une paire CALL/PUT a la même échéance et le même strike. Choix de l'échéance
la plus proche de 20 jours calendaires dans 15–25 jours, strike à moins de 5 %
du cours brut IEX historique déjà archivé. Signal fixé :
`log(1 + volume CALL) - log(1 + volume PUT)`, croissant vers D10.
Ce n'est ni un flux acheteur/vendeur signé ni le volume de toute la chaîne.

Rendements actions : ouverture de la séance suivante à clôture de la H-ième
séance, entrée comprise. Déciles signés calculés sur l'univers complet :
D1 = bas, D10 = haut. Couverture labels : 1 790 titres sur les dates utilisées.
H20 principal ; H3/H5/H10 secondaires. Aucun seuil ni sens du signal optimisé.

## Comparaison conditionnelle demandée

Oracle H20 : `model-factory-20261003082853-e98332`. Chaque séance, sélectionner
les 358 meilleurs scores parmi 1 790 titres, **avant** de regarder la disponibilité
options. Tri probabilité décroissante, symbole croissant pour les égalités.
Ce sont les **20 % prédits**, pas les 20 titres ni les extrêmes futurs réels.
Les déciles ne sont pas recalculés à l'intérieur du TOP20.

40 séances de scores, toutes avec fold `2024-01-08`. Le contrat walk-forward
et l'audit H20 antérieur documentent des labels train disponibles au plus tard
le 7 juillet 2023 et validation au plus tard le 5 janvier 2024. Cependant,
les scores sont stockés dans une table réinscriptible, sans archive originale
OOF immuable : leur lineage historique intégral n'est **pas certifié** ici.
Le snapshot des scores et ses empreintes sont conservés dans le rapport.

Après disponibilité des paires : 2 714 observations, 368 titres distincts,
39 séances. À H20, 1 073 observations sont D1/D10, dont 511 D10 et 562 D1.
La proportion d'extrêmes augmente de 22,73 % à 39,54 % dans ces échantillons
options ; cela ne démontre pas une meilleure séparation du sens.

| Horizon | AUC sans filtre Oracle | AUC dans TOP20 Oracle | TOP20 février | TOP20 mars |
|---|---:|---:|---:|---:|
| H3 | 0,506 | 0,498 | 0,495 | 0,504 |
| H5 | 0,504 | 0,508 | 0,514 | 0,505 |
| H10 | 0,521 | 0,511 | 0,515 | 0,513 |
| H20 | 0,519 | 0,509 | 0,502 | 0,535 |

AUC 0,50 = classement comparable au hasard ; **pas un taux de trades gagnants**.
Les moyennes d'AUC quotidiennes ne sont pas les AUC regroupées : dans le TOP20,
H20 moyenne quotidienne 0,541 sur seulement 15 journées ayant au moins 20
extrêmes et les deux classes. La sélection de journées évaluables empêche
d'interpréter ce chiffre comme un gain stable.

À H20 parmi les seuls D1/D10 du TOP20, CALL > PUT donne 48,48 % de D10 contre
47,62 % sans condition, soit +0,85 point : faible écart descriptif.
La cohorte H20 à entrées espacées de vingt séances compte seulement deux dates
et 46 extrêmes (AUC 0,529) : insuffisant pour confirmer statistiquement.

## Conclusion et limites

**Pas d'amélioration directionnelle stable démontrée par ce signal dans le
TOP20 Oracle.** L'hypothèse reste raisonnable, mais le résultat ne justifie pas
un filtre live, un backtest économique ou une optimisation de seuils.
Reprendre les règles identiques quand davantage de mois sont disponibles,
avec séparation temporelle et qualification des sources.

Ce diagnostic n'évalue que l'écart de volume CALL/PUT ATM. Il ne permet pas
de conclure sur open interest, IV, Greeks ou consensus. Feed historique
`historical_default`, provenance `UNVERIFIED_OPRA` ; aucun NBBO utilisé.
Catalogues retrouvés aujourd'hui, univers actuel avec biais de survivance,
disponibilité historique avant ouverture supposée et non prouvée, barres reçues
en octobre 2026, rendements chevauchants, absence de neutralisation secteur/taille
et de traitement total-return des opérations sur titres.

## Reproduction et artefacts

Scripts : `scripts/research/options_downloaded_directional_audit.py`, puis
`scripts/research/options_oracle_top20_directional_audit.py`. Répertoires figés,
refus de les écraser. Trois tests locaux passés.

- Sans Oracle : `artifacts/research/alpaca_options_history/directional-feb-mar-2024-20261011-v1`.
- Conditionnel : `artifacts/research/alpaca_options_history/directional-oracle-top20-feb-mar-2024-20261011-v1`.

Protocoles, rapports JSON, paires par horizon et scores Oracle archivés ;
aucune modification des producteurs de données.
