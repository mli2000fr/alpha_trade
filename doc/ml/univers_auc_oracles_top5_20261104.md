# Deux univers AUC > 0,60 : Oracles dédiés et TOP5 LONG

**Précision : les résultats de cette page portent sur le TOP5 du score
d'amplitude Oracle, acheté LONG sans classement directionnel quotidien.**
La [campagne corrigée TOP20Oracle → TOP5LONGper-symbol](univers_auc_per_symbol_top5_20261104.md)
est séparée et conserve ces résultats comme contrôles.

Suite demandée : [comparaison confirmation Winner et DD15/B4](univers_auc_winner_dd15_20261104.md).
Sa référence est recalculée en intraday sur un périmètre fortement restreint
par la qualification des bougies ; les rendements ne sont pas directement
comparables aux chiffres daily conservés ci-dessous.

**Terminé le 4 novembre 2026 : six entraînements annuels, huit simulations.**
Travail demandé : entraîner un Oracle sur chacun des deux fichiers, puis acheter
les cinq premiers scores quotidiens en LONG sur 2024–2026 avec leurs horizons
respectifs. L'utilisateur a confirmé pour H20 : **SL5 %, sans TP ni trailing,
sortie à l'ouverture de la 21e séance**. H10 : mêmes protections, sortie open11.

## Périmètre et réserve essentielle

- H10 : `config/univers_batch/symbols_winner_h10_auc_gt060.txt`, **32 titres**.
- H20 : `config/univers_batch/symbols_parcours_h20_auc_gt060.txt`, **37 titres**.
- Ces listes proviennent du TOP100 par AUC historique, avec AUC2023–2025 et
  AUC2026 toutes deux strictement >0,60. Elles ont donc été sélectionnées avec
  les résultats des années testées, dont2026. **Les résultats économiques sont
  rétrospectifs ; aucun avantage hors échantillon de ces univers n'est démontré.**
- Sources : archives de la campagne `us_predictable_symbols/20261103-v1`.
  Aucun nouveau téléchargement ou accès SQL. Les données récentes sont bornées
  au **19 octobre 2026**, dernière séance récente commune aux archives.
  Les cas2024 et2025 couvrent leurs années entières ;2026 est partiel.
- Aucune conversion ou promotion du modèle pipeline existant. Les nouveaux
  poids LightGBM sont des artefacts de recherche, pas des bundles de serving
  Model Factory enregistrés en production.

Le nom technique `winner_h10` rappelle la cible de l'audit précédent, **pas
l'activation du moteur Winner** dans ces simulations. Le replay est daily,
sans attente2×5minutes ni renforcement. Le module risque de production et son
coupe-circuit DD15 ne sont pas rejoués ; les limites de sizing ci-dessous sont
explicites. Ce test ne remplace pas un backtest natif Winner/risque.

## Oracle et séparation temporelle

Un modèle global propre à chacun des deux petits univers, renouvelé avant
chaque année2024/2025/2026, **LightGBM CPU**. Même définition que l'Oracle
parcours natif, avec horizon10 ou20 : TOP20 % quotidien de l'amplitude absolue
des high/low futurs J+1…J+H depuis la clôture J. Label disponible à J+H+1,
minimum20titres observables et95 % de chemins qualifiés. Les égalités au seuil
sont traitées par le labeler natif, sans tri arbitraire par symbole.

**L'Oracle prédit l'amplitude, pas LONG/SHORT.** LONG est la politique imposée
pour les achats. Ses AUC ci-dessous ne mesurent pas la même cible que les AUC
directionnelles ayant servi à sélectionner les deux fichiers.

Vingt-quatre variables prix, tendance, volatilité, volume et SPY déjà archivées
à J ; aucun label, maximum futur, score directionnel2026, identifiant de titre
ou donnée actuelle de consensus injecté dans les variables. Éligibilité par les
features à J avant qualification future des labels.

Pour tester l'année Y :

1. Fit sur les dates et labels disponibles strictement avant le 1er janvierY−1.
2. Validation sur Y−1, avec labels disponibles strictement avant le 1er janvierY.
3. Prédictions sur Y, **y compris les dates sans label futur encore qualifié**.

Les fenêtres à cheval sur les frontières sont purgées. Early stopping uniquement
sur validation ; aucun choix du nombre d'arbres sur le résultat de portefeuille.
Paramètres fixes :200arbres maximum, profondeur5,31feuilles, learning_rate0,03,
min_child150, L1/L2=0,1, échantillonnage lignes/colonnes0,8/0,7, patience20,
deux threads, seed20261104. Aucun essai de grille ou nouveau choix a posteriori.

| Année | AUC amplitude H10 | Précision TOP5 vrais extrêmes H10 | AUC amplitude H20 | Précision TOP5 vrais extrêmes H20 |
|---|---:|---:|---:|---:|
| 2024 | 0,9024 | 74,05 % | 0,8769 | 80,16 % |
| 2025 | 0,8911 | 69,44 % | 0,8737 | 72,16 % |
| 2026 partiel | 0,8434 | 56,05 % | 0,8278 | 62,50 % |

Ces diagnostics d'amplitude emploient les dates matures calculables et des
observations chevauchantes. Ils ne sont ni des taux gagnants ni une preuve
directionnelle. Les conditions de sélection de l'univers restent rétrospectives.

## Exécution et comptabilité

Capital **4 000 USD**, exposition brute maximale1×, LONG uniquement. Classement
quotidien par score Oracle décroissant, symbole croissant en cas d'égalité.
TOP5 figé avant exclusions, aucun remplacement depuis le rang6. Les titres
déjà détenus ne sont pas rachetés ; pas de renforcement. Entrée au next open,
quantités entières, capital disponible,20positions maximum,50USD minimum.
Notionnel par nouvelle position plafonné à20 % de l'equity et au budget de
risque1,25 % divisé par SL5 % plus réserve des deux frais. Pas d'utilisation
anticipée des produits d'un stop intraday pour financer un achat à l'ouverture.

SL fixé à95 % du prix d'achat, actif dès la séance d'entrée ; gap sous stop
vendu au cours d'ouverture défavorable. Sans TP ni trailing. Après H séances
de détention, vente à l'ouverture de H+1, avant lecture du high/low de ce jour.
Les positions encore ouvertes à la fin sont valorisées à la clôture, **sans
vente artificielle avant leur échéance**. Frais estimés canoniques8bps par
achat et8bps par vente (0,08 % chaque jambe, spread/commission/slippage inclus).
Pas d'intérêts de marge puisque pas de levier.

Daily OHLC sur la convention d'ajustement archivée ; absence de certification
PIT des corrections, pas de dividende cash crédité séparément. Ni carnets,
cotations bid/ask historiques réelles, contraintes facteurs/secteurs/corrélation,
ni liquidation globale DD15. Les DD sont calculés aux clôtures, avec le dépôt
initial inclus, et peuvent sous-estimer le DD intraday.

## Résultats annuels — 4 000 USD remis au départ de chaque année

| Univers / horizon | Année | Capital final valorisé | Rendement net | DD max | Trades clos | Gagnants |
|---|---|---:|---:|---:|---:|---:|
| 32 titres / H10 | 2024 | 4 392,56 $ | +9,81 % | −26,78 % | 264 | 22,73 % |
| 32 titres / H10 | 2025 | 2 861,37 $ | −28,47 % | −43,68 % | 287 | 22,30 % |
| 32 titres / H10 | 2026 au19/10 | 4 343,51 $ | +8,59 % | −19,29 % | 189 | 26,98 % |
| 37 titres / H20 | 2024 | 6 480,25 $ | +62,01 % | −28,99 % | 189 | 19,05 % |
| 37 titres / H20 | 2025 | 6 630,44 $ | +65,76 % | −40,83 % | 209 | 17,22 % |
| 37 titres / H20 | 2026 au19/10 | 3 755,89 $ | −6,10 % | −34,57 % | 138 | 14,49 % |

Les capitaux finaux comprennent quatre/cinq positions ouvertes selon les cas.
Le taux gagnant porte exclusivement sur les trades clôturés.

## Compte continu 2024–19 octobre2026 — sans remise à zéro

| Mesure | 32 titres / H10 | 37 titres / H20 |
|---|---:|---:|
| Capital initial | 4 000 $ | 4 000 $ |
| Capital final valorisé | **2 999,50 $** | **10 684,29 $** |
| Rendement net | **−25,01 %** | **+167,11 %** |
| DD maximal clôture | **−58,68 %** | **−45,17 %** |
| Trades clos | 747 | 534 |
| Gagnants / perdants | 177 /570 | 94 /440 |
| Taux gagnant | 23,69 % | 17,60 % |
| Somme des PnL des gagnants, après frais | +18 935,09 $ | +37 442,13 $ |
| Somme des PnL des perdants, après frais | −20 158,20 $ | −30 785,49 $ |
| Gain moyen gagnant | +106,98 $ | +398,32 $ |
| Perte moyenne perdant | −35,37 $ | −69,97 $ |
| Détention moyenne gagnants | 10,00 séances | 20,00 séances |
| Détention moyenne perdants | 3,22 séances | 4,13 séances |
| Capital engagé moyen | 2 993,11 $ | 6 969,48 $ |
| Engagement moyen / equity courante | 81,34 % | 86,37 % |
| Capital engagé maximal | 5 793,23 $ | 15 452,17 $ |
| Frais estimés cumulés | 793,15 $ | 1 116,96 $ |
| PnL réalisé | −1 223,11 $ | +6 656,65 $ |
| PnL latent net des frais d'achat | +222,61 $ | +27,65 $ |
| Positions ouvertes finales | 4 | 5 |

![Évolution des deux comptes continus](../../artifacts/research/us_selected_universe_oracle/20261104-v2/capital-continuous.png)

La plupart des achats perdent ; quelques gains beaucoup plus grands que les
pertes soutiennent H20. Ses cinq meilleurs trades représentent24,73 % du PnL
positif brut agrégé après frais. Les résultats annuels indépendants ne doivent
pas être multipliés pour reproduire le compte continu : capital courant,
arrondis, positions à cheval sur les années et admissions diffèrent.

## Qualité et restrictions de2026

Le contrôle conservateur impose un fournisseur et une identité stables durant
la fenêtre de détention observée, tronquée à la fin de simulation. Il rejette
**la date d'entrée concernée**, jamais tout le titre sur toutes les années.
Ce contrôle regarde l'existence/continuité des barres futures : **réserve de
sélection rétrospective**, pas un filtre disponible en live.

Dans ces résultats, les exclusions ne sont pas des trous OHLC : les prix sont
présents mais le fournisseur change entre EODHD et SIP au sein de la fenêtre.
Le sélecteur canonique choisit EODHD lorsque les deux lignes existent, selon
`market_data.daily_bars_preferred_source`. Il ne mélange pas leurs champs.

- 2024/2025 : aucune exclusion de fenêtre sur les entrées proposées.
- H10 en2026 et continu :37 dates d'entrée rejetées, sept titres.
- H20 en2026 seul :82 dates d'entrée rejetées ; continu76, huit titres.
  Les compteurs diffèrent parce qu'un titre déjà détenu n'est pas proposé à nouveau.

Les cas2026 et continus sont **INCOMPLETE_COVERAGE_EXPLORATORY**. Les lignes
`missing-entry-days.csv` portent le code générique du replay ; les fichiers
`data-quality-entry-exclusions.csv` précisent `PROVIDER_CHANGE`, les deux
fournisseurs et l'absence de dates manquantes. Aucun de ces cas n'est présenté
comme entièrement qualifié ou identique au live.

## Artefacts, vérification et conclusion

Dossier : `artifacts/research/us_selected_universe_oracle/20261104-v2/`.
Le v1 a échoué **avant tout entraînement**, sur une paire EODHD/SIP non encore
sélectionnée dans l'export brut. Il est conservé comme diagnostic ; v2 applique
le sélecteur canonique et n'altère pas les exports d'origine.

- `protocol.json`, `progress.json`, `report.json`, `summary.csv`.
- Sous chaque univers : `dataset.parquet`, `source-hashes.json`, trois poids
  `oracle-path-H{10,20}-{2024,2025,2026}.txt`, reçus de fit et
  `training-report.json`, `all-scores.parquet`, `daily-top5.csv`.
- Sous `2024/2025/2026/continuous` : `report.json`, `equity.csv`, `trades.csv`,
  `entry-audit.csv`, exclusions détaillées par date et fournisseur.
- `verification.json` : **PASS**, six modèles et leurs dates contrôlés,
  **47 555 prévisions reproduites**, huit replays entièrement reproduits,
  2 557 trades contrôlés (comptes annuels et continus comprenant des doublons
  économiques entre simulations), cash/PnL, frais, stop, gaps et horizons vérifiés.
- **12 tests ciblés passent**, dont chronologie/purge, inférence sans label
  futur, classement indépendant des résultats, frais, chronologie de cash,
  stop d'entrée, gap, horizon et exclusion par seule date d'entrée.
- Scripts `scripts/research/us_selected_universe_oracle_20261104.py` et
  `us_selected_universe_oracle_review_20261104.py`. Même assistant, pas revue
  humaine indépendante. Zéro SQL, fournisseur/LLM, ordre ou promotion.

**H20 produit le meilleur résultat rétrospectif, mais avec un drawdown élevé
et une année2026 négative. H10 ne démontre pas d'avantage économique continu.**
L'utilisation de2026 pour choisir les univers empêche de promouvoir ces gains
comme preuve d'un univers prédictible. Aucun changement de pipeline proposé
automatiquement à l'issue de cet audit.
