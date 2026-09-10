# Trajectoire intraday 5 minutes de la séance complète

## Statut

**POC terminé — `NO_GO` direction et `NO_GO` amplitude.**

Cette expérience teste une information distincte des snapshots et des cinq
dernières minutes : la forme de la séance J complète. Les signaux sont calculés
après 16:00 ET et ne peuvent être utilisés qu'à partir de l'open J+1.

Code : `modelFactory/directional_data_research/intraday_session_path_pilot.py`.

Artefact :
`artifacts/research/eroya_directional/intraday-session-path-20260908045642-0e94ac/`.

## Population et contrat PIT

- batch Oracle : `model-factory-20260907170018-0e94ac` ;
- 393 dates Oracle OOF uniques du 5 juillet 2018 au 4 mars 2022 ;
- un symbole par date, choisi par hash `date|symbol` ;
- sélection sans rendement futur ;
- barres Eroya ajustées de cinq minutes ;
- seules les barres dont le début appartient à 09:30–16:00 America/New_York
  sont conservées ;
- minimum 60 barres régulières par événement ;
- 393 requêtes terminées, 330 séances exploitables ;
- 330 lignes avec labels corrigés, dont 270 tails H20.

Le filtrage en heure de New York traite automatiquement les changements
d'heure. Les barres pre-market et after-hours ne sont jamais mélangées aux
features de séance régulière.

## Features préfixées

Direction, avec signe momentum positif fixé avant le run :

- rendement 09:30→11:00 ;
- rendement 13:00→16:00 ;
- rendement après-midi moins rendement matin ;
- clôture contre VWAP de séance ;
- position de clôture dans le range de séance.

Amplitude :

- volatilité réalisée des clôtures 5 minutes ;
- range haut-bas de séance ;
- divergence absolue matin/après-midi ;
- part du volume de la première heure ;
- part du volume de la dernière heure ;
- logarithme du nombre de transactions.

Les onze tests partagent une correction Bonferroni. Un signal devait passer
simultanément population, AUC >= 0,53, Spearman >= 0,03, au moins 70 % de
semestres favorables et p corrigée < 0,05.

## Résultats directionnels

| Feature | AUC D1/D10 | Spearman rendement | Stabilité | p corrigée | Verdict |
|---|---:|---:|---:|---:|---|
| après-midi moins matin | **0,53** | +0,09 | 5/8 | 1,00 | `NO_GO` |
| clôture contre VWAP | 0,47 | -0,08 | 2/8 | 1,00 | `NO_GO` |
| rendement après-midi | 0,47 | -0,06 | 3/8 | 1,00 | `NO_GO` |
| position dans le range | 0,46 | -0,10 | 2/8 | 1,00 | `NO_GO` |
| rendement matin | 0,45 | -0,13 | 2/8 | 1,00 | `NO_GO` |

La seule variable au-dessus de 0,50 ne montre ni stabilité suffisante ni
significativité. Les variables de niveau de clôture répliquent plutôt le signe
contrariant instable déjà observé dans les ticks de fin de séance.

## Résultats amplitude

| Feature | AUC extrême | Spearman amplitude | Stabilité | p corrigée | Verdict |
|---|---:|---:|---:|---:|---|
| volatilité réalisée 5 min | **0,56** | **+0,18** | **6/8** | **0,30** | `NO_GO` |
| range de séance | 0,54 | +0,15 | 6/8 | 1,00 | `NO_GO` |
| divergence matin/après-midi | 0,54 | +0,13 | 6/8 | 1,00 | `NO_GO` |
| part volume première heure | 0,51 | +0,04 | 3/8 | 1,00 | `NO_GO` |
| nombre de transactions | 0,50 | +0,11 | 5/8 | 1,00 | `NO_GO` |
| part volume dernière heure | 0,44 | -0,17 | 2/8 | 1,00 | `NO_GO` |

La volatilité réalisée est un quasi-signal descriptif d'amplitude, mais échoue
le contrôle statistique après les onze comparaisons. Elle ne doit pas être
ajoutée à `oracle.json`, ni combinée a posteriori avec le range pour fabriquer
un passage de gate.

## Décision

- aucun modèle directionnel ou d'amplitude ;
- aucune intégration Oracle ou Per-Symbol ;
- aucune table intraday applicative ;
- ne pas retester d'autres découpages de la même séance sur cette population ;
- conserver les Parquet comme preuve reproductible.

Une confirmation de la volatilité réalisée n'est pas ouverte : le protocole
exigeait le passage de tous les gates, y compris la multiplicité. La prochaine
piste doit fournir une information vraiment différente des prix/volumes du
sous-jacent.

