# Guide de renouvellement des univers ML et Oracle

## Objet

Ce document est le contrat à donner à l'IA lors du renouvellement trimestriel ou
semestriel des symboles. Il évite de confondre :

1. l'univers large qui sert à construire les labels et entraîner Oracle ;
2. l'échantillon équilibré de 400 symboles pour les campagnes rapides ;
3. les symboles réellement servables par les modèles Per-Symbol LONG/SHORT.

Références scientifiques : [audit P0 de l'univers Oracle 400](oracle_universe_p0_audit.md)
et [construction P0d de l'univers équilibré](oracle_universe_p0d_balanced400.md).

## État constaté au 8 septembre 2026

`config/univers/univers_filtred.txt` contient :

| Mesure | Valeur |
|---|---:|
| Symboles uniques / avec barres | 2 696 / 2 696 |
| `tradable=1` et `bars_available=1` | 2 695 |
| Au moins 504 séances entre 2016 et 2025 | 2 696 |
| Au moins 2 000 séances | 2 333 |
| Couverture ≥ 95 % des 2 514 séances SPY | 2 186 |
| Première barre au plus tard le 1er janvier 2016 | 2 183 |
| Capitalisation courante connue ≥ 2 Md$ | 1 443 |
| Capitalisation courante connue ≥ 500 M$ | 1 866 |
| Capitalisation courante manquante | 830 |

Le fichier est une population candidate, pas un univers PIT historique. Depuis le
9 septembre 2026, `scripts.build_equity_universe` produit sans écraser la source :

```text
config/univers/univers_filtred_equities.txt
```

Le fichier contient 1 798 actions ; 898 ETF, ETN, fonds et produits structurés ou
à levier/inverses sont écartés. Les 830 capitalisations auparavant manquantes
étaient très majoritairement des produits collectifs, mais l'exclusion repose sur
la classification instrument et non sur l'absence de capitalisation.

## Ne pas retenir simplement les titres qui bougent le plus

L'audit P0 montre que les 20 % de symboles les plus contributeurs créent environ
41 % des tails. La fréquence D1/D10 est corrélée à 0,895 avec la volatilité et à
0,918 avec le range médian. Le quintile le plus calme produit 7,8 % d'extrêmes,
contre 40,8 % pour le plus volatil.

Sélectionner les 400 plus volatils ferait surtout apprendre à Oracle l'identité
des titres structurellement agités. La volatilité sert donc de plancher de
négociabilité, de contrôle des anomalies et de strate d'équilibrage. Elle ne
doit pas être le classement de sélection.

## Les trois livrables

### `oracle_pit_large_<YYYYMM>.txt`

La source recommandée est désormais `univers_filtred_equities.txt` (1 798 titres
au 9 septembre 2026), admise dynamiquement à chaque date. Cet univers sert aux
labels cross-sectionnels et au modèle Oracle mutualisé. Il peut rester bien plus
large que l'univers Per-Symbol car il ne crée pas un modèle par ticker.

### `oracle_balanced_400_<YYYYMM>.txt`

Échantillon rapide et déterministe, équilibré par secteur, capitalisation,
volatilité, bêta, ancienneté et type d'instrument. Il sert aux smoke tests et
ablations ; ce n'est pas automatiquement l'univers de production.

La première implémentation reproductible et ses résultats complets sont décrits
dans [P0d — Balanced 400](oracle_universe_p0d_balanced400.md).

### Univers directionnels

Trois fichiers après validation Walk-Forward :

```text
directional_long_servable_<YYYYMM>.txt
directional_short_servable_<YYYYMM>.txt
directional_long_short_servable_<YYYYMM>.txt
```

Un symbole peut être bon d'un seul côté. La servabilité exige l'artefact et les
folds nécessaires, pas seulement un F1 maximal ponctuel.

## Dates à figer avant de commencer

```text
selection_asof_date : dernière information autorisée pour sélectionner
training_start_date : début de l'entraînement
training_end_date   : fin de l'entraînement
oos_end_date        : fin de la confirmation éventuelle
```

Aucune donnée postérieure au cutoff ne participe au choix. Une sélection 2026
peut servir au trading futur, mais son replay 2016 est un résultat conditionnel
aux survivants 2026. Une vraie validation historique reconstruit l'univers à
chaque cutoff ou utilise une admission quotidienne PIT.

## Procédure de renouvellement

### A. Figer et normaliser la source

Partir de `config/univers/univers_filtred.txt` sans l'écraser, puis exécuter :

```powershell
python -m scripts.build_equity_universe --source config/univers/univers_filtred.txt --output config/univers/univers_filtred_equities.txt
```

Utiliser le fichier `univers_filtred_equities.txt` pour les nouveaux entraînements.

1. accepter virgules et lignes, ignorer commentaires/vides ;
2. supprimer les espaces, mettre en majuscules, dédupliquer ;
3. publier les nombres avant/après ;
4. calculer le SHA-256 du fichier ;
5. conserver source, dates, seed et commit Git dans un manifeste.

### B. Vérifier identité et métadonnées

Pour l'univers courant exécutable :

| Contrôle | Défaut |
|---|---|
| `status` | `active` |
| `tradable` / `bars_available` | `1` / `1` |
| `asset_class` | `us_equity` |
| dernière barre ou quote | âge ≤ 5 jours de marché |
| capitalisation absolue | connue et ≥ 500 M$ |
| cœur recherché | mid/large, donc ≥ 2 Md$ |

Mettre les capitalisations inconnues en quarantaine jusqu'au rafraîchissement.
Ne jamais les considérer implicitement comme non-micro-cap.

`asset_class=us_equity` ne distingue pas common stocks, ADR/ADS, actions
étrangères, REIT, BDC, MLP, ETF, preferred, warrants, units et rights. Exclure
ETF/funds/preferred/warrants/units/rights. Garder les autres catégories dans des
groupes explicites. Si la source manque, écrire `TYPE_NON_VERIFIE` plutôt que
prétendre que le filtre a réussi.

### C. Admission quotidienne PIT dans `oracle_pit_large`

À chaque date J, avec uniquement les données disponibles au plus tard à J :

| Contrôle | Seuil recommandé |
|---|---:|
| Historique réel | ≥ 504 séances |
| Clôture | ≥ 10 $ |
| Dollar-volume moyen trailing 20 j | ≥ 10 M$ |
| Volume moyen trailing 20 j | ≥ 100 000 actions |
| Barres remplies sur 252 j | ≤ 2 % |
| Dernière vraie barre | séance attendue |
| Rupture d'identité/saut inexpliqué | fail-closed |

Le dollar-volume est prioritaire sur le nombre d'actions. Capitalisation,
statut et type historiques ne peuvent filtrer le passé que si leur source est
réellement PIT. Une valeur courante ne doit pas être rétropropagée.

Pour 2016–2025, comparer deux contrats :

- cohorte fixe : première barre avant 2014 pour deux ans de warm-up ;
- univers dynamique recommandé : entrée après 504 séances réelles.

Ne pas appliquer automatiquement le plafond ATR de la stratégie au label
Oracle. Le filtre ATR 1,5–6 % appartient au risque/exécution. Pour Oracle,
isoler seulement les pathologies et conserver des strates de volatilité.

### D. Construire `oracle_balanced_400`

Calculer les strates uniquement avec les informations antérieures au cutoff et
utiliser une seed enregistrée.

Capitalisation cible :

| Groupe | Quota |
|---|---:|
| Mid 2–10 Md$ | 60–70 % |
| Large ≥ 10 Md$ | 20–30 % |
| Small 500 M$–2 Md$ | 10–15 % maximum |
| Mini < 500 M$ ou inconnue | 0 % |

Volatilité cible :

| Quintile | Quota |
|---|---:|
| Q1 très calme | 15 % |
| Q2 calme | 20 % |
| Q3 intermédiaire | 25 % |
| Q4 volatil | 25 % |
| Q5 très volatil | 15 % |

Contraintes : maximum 10 % dans un secteur ; groupes spéciaux ADR/REIT/BDC/MLP
plafonnés ensemble à 15 % sauf justification ; redistribution documentée si une
strate manque ; sortie triée pour être déterministe.

### E. Construire les univers Per-Symbol

Après entraînement seulement :

- support suffisant des événements Oracle par côté ;
- au moins trois folds Walk-Forward valides ;
- stabilité médiane/minimum/pass-rate par côté ;
- artefact champion chargeable ;
- calibrateur ou fallback explicitement admis ;
- contrat de features identique entre train et serving ;
- symbole exposé seulement si sa branche est réellement servable.

Le F1 LONG/SHORT du côté concerné est prioritaire ; F1 macro est contextuel.
La confirmation finale ne sert jamais à choisir les symboles.

## Critères interdits

Ne jamais sélectionner l'univers initial avec :

- D1/D10 ou fréquence `oracle_extreme10` sur la période évaluée ;
- rendement futur, PnL, Sharpe ou win rate futurs ;
- F1 observé sur la confirmation ;
- volatilité calculée après `selection_asof_date` ;
- choix manuel de tickers historiquement favorables ;
- statut/capitalisation actuels présentés comme connus dix ans plus tôt.

Ces données peuvent analyser un univers déjà gelé, jamais le fabriquer.

## Fichiers d'audit obligatoires

```text
artifacts/research/universe_selection/<run_id>/manifest.json
artifacts/research/universe_selection/<run_id>/symbol_audit.csv
artifacts/research/universe_selection/<run_id>/exclusions.csv
artifacts/research/universe_selection/<run_id>/strata_summary.csv
artifacts/research/universe_selection/<run_id>/report.md
```

Le manifeste contient dates, source/hash, commit, seed, seuils, nombres avant et
après chaque gate, fraîcheur/couverture des métadonnées, quotas demandés et
obtenus, limitations PIT et hash de chaque fichier produit.

## Gates avant entraînement

`oracle_pit_large` : aucun doublon, aucune présence avant cotation, au moins 20
titres par date, distribution de taille publiée, censure et raisons publiées,
concentration D1/D10 contrôlée par secteur et volatilité.

`oracle_balanced_400` : exactement 400, quotas proches de 15/20/25/25/15,
aucune mini-cap/capitalisation inconnue, plafond sectoriel respecté, seed/cutoff
enregistrés et distributions comparées à l'univers large.

Per-Symbol : distinguer `entraîné` et `servable`, listes LONG/SHORT/LONG_SHORT
cohérentes et statistiques Walk-Forward visibles par branche.

## Comparaison avec la version précédente

Toujours publier : tailles quotidiennes, entrées/sorties, secteurs/caps,
volatilité/bêta/prix/dollar-volume, concentration des tails, corrélation
tail-volatilité, proportion de labels D1/D10 modifiés, performance Oracle OOF
sur les mêmes dates, cohortes de cotation et couverture directionnelle servable.

Une hausse du score Oracle ne suffit pas : l'univers doit réduire le biais,
conserver une amplitude négociable et rester stable par fold et semestre.

## Prompt prêt à remettre à l'IA

```text
Renouvelle les univers selon doc/ml/oracle_universe_selection_playbook.md.
Lis entièrement ce document et vérifie le code réellement exécuté. Pars de
config/univers/univers_filtred.txt sans l'écraser.

Fixe d'abord selection_asof_date, training_start_date, training_end_date et la
période OOS. Audite doublons, barres, fraîcheur, capitalisations manquantes,
types d'instruments et ruptures d'identité.

Produis oracle_pit_large, oracle_balanced_400 et directional_servable séparés.
Applique les critères historiques quotidiennement avec uniquement les données
alors disponibles. Ne sélectionne jamais avec futurs D1/D10, fréquence future
des tails, F1/PnL de confirmation ou volatilité post-cutoff. Ne prends pas les
plus volatils : équilibre secteur, cap, volatilité, bêta, ancienneté et type.

Avant tout entraînement, produis manifeste, symbol_audit.csv, exclusions.csv,
strata_summary.csv, report.md et fichiers versionnés avec SHA-256. Publie les
nombres avant/après chaque gate et toutes les limites PIT. Ne touche pas aux
batchs en cours.
```
