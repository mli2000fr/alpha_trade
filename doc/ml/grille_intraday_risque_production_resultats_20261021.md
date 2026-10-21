# Grille intraday ×1 avec risque B4 : résultats vérifiés

## Statut et contrat

**576/576 simulations terminées, zéro échec, tous les audits passent.**
Durée : 1 282,56 secondes, soit environ 21 min 23 s. Dossier faisant foi :
`artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v2`.

Relecture après fin : empreintes des sources, entrées préparées, rapport final,
tableaux et fichiers de chacun des 576 cas vérifiées. 576 identifiants distincts
et 576 marqueurs `done.json`. Tous les audits portent
`PASS_PRODUCTION_RISK_CASH_EXITS`, revue finale
`PASS_COMPLETED_RISK_GRID_REVIEW`. Écart maximal de reconstruction :
1,46e-11 USD. Ce sont des contrôles techniques du même assistant, pas une
revue humaine indépendante.

Même cohorte conditionnelle de 213 campagnes, 72 titres, 119 campagnes 2025 et
94 en 2026 ; pas tout le TOP10 historique. Oracle PATH_H20 CatBoost de recherche,
pas substitution du champion live. Frais, financement, hypothèses SHORT et
maintenance identiques au protocole ; 144 politiques LONG et 144 SHORT par
année, plafond d'admission ×1. Chaque année démarre indépendamment à
**4 000 USD**, 2026 s'arrête au **30 septembre**. Aucun rendement composé
2025→2026 n'est calculé ici. Capital final incluant positions ouvertes MTM.

## Effet sur le profil de comparaison déjà suivi

LONG, SL fixe 7 %, trailing 15 %, sans TP, échéance J+20 de la campagne Oracle
(attente avant entrée comprise). Ce n'est pas automatiquement vingt séances
après le fill ; voir le [contrat de chronologie](grille_intraday_long_short_20261021.md).

| Mesure | 2025 sans B4 | 2025 avec B4 | 2026 sans B4 | 2026 avec B4 |
| --- | ---: | ---: | ---: | ---: |
| Rendement net / MTM | +33,15 % | +16,25 % | +31,67 % | +31,67 % |
| Capital final USD | 5 325,83 | 4 649,86 | 5 266,82 | 5 266,82 |
| DD maximal | 30,68 % | 26,93 % | 20,88 % | 20,88 % |
| Trades clôturés | 102 | 100 | 79 | 79 |
| Gagnants / perdants | 38 / 64 | 36 / 64 | 29 / 50 | 29 / 50 |
| Taux gagnant | 37,25 % | 36,00 % | 36,71 % | 36,71 % |
| Gain moyen d'un gagnant USD | +133,50 | +108,36 | +135,36 | +135,36 |
| Perte moyenne d'un perdant USD | −57,76 | −50,21 | −53,17 | −53,17 |
| Détention moyenne gagnant, séances | 15,45 | 15,50 | 14,62 | 14,62 |
| Détention moyenne perdant, séances | 5,25 | 5,25 | 5,42 | 5,42 |
| Capital brut moyen engagé USD | 2 992,38 | 2 317,86 | 2 784,57 | 2 784,57 |
| Moyenne du ratio engagé/equity | 62,16 % | 51,50 % | 55,83 % | 55,83 % |

Avec B4 : sept positions restent ouvertes fin 2025, latent −37,89 USD ; aucune
fin septembre 2026. Les moyennes de gains/pertes concernent seulement les
trades clôturés, pas les positions encore détenues.

**Interprétation :** en 2025, le DD diminue de 3,75 points mais le rendement
de 16,90 points. Un trip et 78 séances dégradées réduisent les tailles et le
capital utilisé. Aucune liquidation forcée à ce trip : les protections
préalables avaient déjà vidé les lignes éligibles. En 2026, aucun trip B4 sur
ce profil ; mêmes trades et courbe que le témoin, malgré sept observations
de perte journalière. La perte journalière 3 % n'est pas un hard halt dans
le chemin B4 examiné.

## Bilan des 144 politiques par sens et année

| Mesure | LONG 2025 | LONG 2026 | SHORT 2025 | SHORT 2026 |
| --- | ---: | ---: | ---: | ---: |
| Profils rentables avec B4 | 25/144 | 128/144 | 0/144 | 0/144 |
| DD inférieur au témoin sans B4 | 100/144 | 9/144 | 124/144 | 144/144 |
| Rendement supérieur au témoin | 33/144 | 6/144 | 105/144 | 108/144 |
| DD et rendement tous deux meilleurs | 33/144 | 6/144 | 105/144 | 108/144 |

23 profils LONG sont positifs sur les deux périodes. En SHORT, améliorer le
témoin signifie souvent **perdre moins**, pas gagner. Par exemple
SL7/trailing15/H20/sansTP : −33,49 % → −25,76 % en 2025, et
−48,03 % → −31,38 % en 2026.

Le B4 n'est pas universellement favorable. Médiane du changement apparié LONG
2025 : DD −1,49 point et rendement −1,91 point ; en 2026, les deux médianes
sont nulles. Réduire l'exposition peut réduire pertes et gains ; le contrôle
ne suffit pas à démontrer une meilleure sélection.

## Comparaisons descriptives, pas choix d'un champion

Trois profils LONG observés, tous SL7 et sans TP :

| Trailing / échéance | Rendement 2025 / 2026 | DD 2025 / 2026 | Capital final USD 2025 / 2026 |
| --- | ---: | ---: | ---: |
| 15 % / H15 | +20,91 % / +21,73 % | 26,61 % / 19,14 % | 4 836,51 / 4 869,22 |
| 15 % / H20, référence suivie | +16,25 % / +31,67 % | 26,93 % / 20,88 % | 4 649,86 / 5 266,82 |
| 20 % / H20 | +19,40 % / +32,80 % | 24,13 % / 22,63 % | 4 776,19 / 5 312,03 |

H15 a le meilleur **minimum de rendement annuel** des 144 profils LONG de
cette grille. Il s'agit d'un classement après observation des résultats,
pas d'une preuve hors échantillon supplémentaire ni d'un meilleur profil
selon tout critère. Les périodes sont déjà connues, les profils corrélés et
les horizons partagent des campagnes. Pas de promotion ou nouveau test lancé.

## Pourquoi le DD peut dépasser 20 %

420 des 576 comptes dépassent 20 % de DD intraday mesuré. Le contrôle global
rejoué intervient une fois par séance, avec pic quotidien, allocation
adaptative et éventuelle fermeture partielle des positions. Il n'est ni une
assurance contre les gaps, ni un watcher continu, ni une liquidation intégrale
au seuil. Il peut manquer un pic/creux intraday et les sorties précèdent ou
suivent d'autres protections selon le contrat figé.

Les réserves sur le raccordement complet de PortfolioBuilder, les secteurs,
les corrélations, les quotes et les fills réels restent inchangées. Voir le
[protocole B4 et les passages de production examinés](grille_intraday_risque_production_20261021.md).
Le correctif numérique ne prétend pas résoudre ces limites.

## Fichiers disponibles et suite proposée

- `annual-summary.csv` : toutes les mesures annuelles, y compris taux gagnant,
  gains/pertes moyens, détention, capital utilisé, positions ouvertes et coûts.
- `comparison-risk-vs-baseline.csv` : mêmes politiques avec/sans B4, trips,
  liquidations, séances dégradées et pertes journalières observées.
- `cases/*/production-risk-events.json`, `audit.json`, `trades.parquet`,
  `marks.parquet` : détails de chaque simulation.
- `final-review.json` : clôture technique et empreintes vérifiées.

Suite recommandée, **non lancée ici** : contrôler robustesse/voisinages et
concentration des résultats avant de choisir un profil. Ensuite seulement,
éventuelle expérience limitée du contrôle de corrélation sur le même panier,
avec témoin d'exposition comparable. Ne pas sélectionner le meilleur résultat
isolé puis présenter 2025/2026 comme une validation neuve.
