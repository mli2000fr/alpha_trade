# Oracle parcours TOP5 — règles de protections dynamiques figées

14 octobre 2026. Expérience locale autorisée, pas une activation en production.

## Objectif

Comparer une seule règle de choix de protections à la référence fixe
**SL5 / trailing15 / TP20**. Mêmes trois modèles, scores TOP5, dates, prix,
capital 4 000 USD, plafond de levier ×2, financement et contraintes que la
[grille précédente](oracle_path_top5_levier_grid_20261014.md).
Pas d'entraînement, pas d'écriture SQL, pas d'appel ni d'ordre de courtier.

Cette première version choisit le profil **à l'entrée**, depuis le contexte connu
à la clôture J. Il est ancré au fill effectif J+1 puis conservé pour toute la
position. Le trailing suit ensuite son sommet selon les règles natives,
mais son pourcentage ne change pas au gré des jours. Ce n'est **pas encore**
une stratégie de remplacement quotidien des protections d'une position ouverte.
Le SL dur reste 5 % ; il n'est jamais élargi pour sauver une position perdante.
Pas de sortie forcée à H20, pas de liquidation terminale, pas de renforcement
d'un titre déjà détenu.

## Une règle, trois profils

| Profil | SL | Trailing | TP |
| --- | --- | --- | --- |
| REFERENCE | 5 % | 15 % | 20 % |
| DEFENSIVE | 5 % | 10 % | 10 % |
| TREND | 5 % | 20 % | 30 % |

Priorités, toutes figées avant le nouveau calcul de performance :

1. Donnée nécessaire manquante/non finie, ou couverture de breadth <80 % :
   REFERENCE et motif explicite. Pas de régime favorable inventé.
2. DEFENSIVE si au moins une condition : régime natif autre que `normal` ;
   VIX ≥30 ; breadth <40 % ; SPY sous sa SMA200 **et** breadth <50 %.
3. TREND seulement si toutes les conditions : VIX ≤20 ; SPY au-dessus de
   SMA200 ; rendement SPY sur vingt séances >0 ; breadth ≥60 % ; titre au-dessus
   de SMA50 ; rendement vingt séances du titre supérieur à celui de SPY.
4. Sinon REFERENCE.

Le régime est celui réellement reconstruit par le moteur à J, pas une étiquette
historique choisie après observation du résultat. Il conserve ses propres
restrictions macro et sizing. Les taux dix ans/MOVE/VXN ne reçoivent pas de
nouveaux seuils spécifiques dans cette expérience : seul le VIX entre directement
dans la règle, avec le régime natif. ATR reste dans les contrôles natifs.
Pas de règle secteur fondée sur une métadonnée actuelle présentée comme historique.

Breadth : proportion des **1 790 titres de l'univers figé complet** dont le close
dépasse leur moyenne mobile cinquante séances. Pas la proportion des cinq candidats.
Closes absents/non positifs, volume non positif et lignes `is_filled` sont masqués ;
SMA50 exige cinquante observations. Le dénominateur réellement qualifié et sa
proportion dans l'univers sont archivés pour chaque date. Aucun remplissage de prix.

## Temporalité et exécution

Les indicateurs emploient uniquement des fenêtres backward à J : SMA200 SPY,
SMA50 titre/univers, rendements vingt séances et VIX daté J. Le choix est
journalisé avec toutes les valeurs et le régime avant le fill de J+1.
L'ouverture J+1 sert à ancrer les prix des protections, pas à choisir le profil.

Application par symbole, y compris lorsque plusieurs profils sont présents dans
la même vague d'ordres. SL/TP/lifecycle sont raccordés aux mêmes composants
natifs que la référence. Le HIGH du jour ne relève pas rétroactivement le
stop contre le LOW de ce jour. Gaps, collision stop/TP conservatrice, frais,
rejets de budget et opérations sur titres restent inchangés.

Les sorties différentes libèrent le capital à des dates différentes : le risque,
les approbations, quantités et réinvestissements sont recalculés chronologiquement.
On compare deux véritables portefeuilles, **pas** un PnL sur quantités figées.
La politique de sizing est identique, pas nécessairement ses décisions finales.

## Protocole, sources et réserves

Six cas : FIXED et DYNAMIC pour 2024, 2025 et 2026 jusqu'au 30 septembre.
Source : `us_oracle_path_top5_leverage/20261014-v3` ; mêmes modèles annuels et
folds causaux que la grille, aucun choix de backend sur le profit.
Le témoin FIXED doit reproduire **exactement les trades et chaque point de
la courbe d'equity** des trois références archivées avant d'accepter le résultat.

Protocole canonical figé avant PnL :
`artifacts/research/us_oracle_path_dynamic_protections/20261014-v2/protocol.json`.
V1 n'a exécuté aucun replay ; préparation technique conservée, non canonique.
Le code, tests, contextes, sources et témoins sont identifiés par SHA-256.

Couverture des entrées candidates : VIX présent sur 1 260/1 260 lignes 2024,
1 250/1 250 lignes 2025, 935/935 lignes 2026. Minimum de couverture breadth :
99,89 %, 99,89 %, 90,84 % respectivement. Une autre variable absente peut encore
déclencher le fallback, qui est journalisé au lieu d'être remplacé implicitement.
Un seul fallback effectivement rencontré : KLAC le 29 juillet 2026, donnée
de contexte manquante, candidat non approuvé. Il n'a donc créé aucune entrée.

Ces périodes et les profils ont déjà été inspectés dans la grille. Le protocole
est maintenant figé, mais **ce n'est pas un nouvel échantillon indépendant**.
Les données sont utilisées causalement par date, sans certification des vintages
macro ni de l'ensemble des dates de disponibilité historiques des prix.
Univers de survivants/secteurs actuels, prix ajustés fournisseur, spreads/fills
simulés, dividendes incomplets et marginabilité historique non certifiée demeurent
réservés. Pas de revendication de rendement total ni de parité courtier réelle.

## Tests et suivi

40 tests ciblés réussis : parité du contrôle, limites de marge, financement,
choix de profils, priorité/fallback, SL5, TP et trailing effectifs, contexte connu
avant entrée, maintien du profil malgré changement ultérieur du VIX et invariance
des indicateurs lorsqu'on tronque ou modifie toutes les données futures.

Run canonique : `artifacts/research/us_oracle_path_dynamic_protections/20261014-v2`.
**Six portefeuilles terminés, zéro échec**. Sources, contextes et fichiers résultats
revérifiés après le calcul. Les trois témoins FIXED reproduisent exactement les
trades et toutes les valeurs des courbes d'equity des références archivées.

## Résultats — NO_GO pour cette règle

| Période | Rendement FIXED | Rendement DYNAMIC | Écart dynamique en points | DD FIXED | DD DYNAMIC |
| --- | --- | --- | --- | --- | --- |
| 2024 | −16,74 % | −25,96 % | −9,22 | −32,83 % | −35,26 % |
| 2025 | +9,93 % | −1,75 % | −11,69 | −20,91 % | −28,40 % |
| 2026 janvier–septembre | +36,14 % | −21,31 % | −57,46 | −26,19 % | −39,68 % |

Capital de départ 4 000 USD par cas. La règle dynamique dégrade le rendement
**et** le drawdown dans les trois périodes. Aucun gain transversal ni réduction
de perte démontrés ; ne pas remplacer la référence fixe par cette règle.

| DYNAMIC | Capital final USD | Positions clôturées | Taux gagnant clôturé | PnL réalisé USD | PnL latent USD | Intérêts USD | Positions ouvertes | Levier moyen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 | 2 961,70 | 134 | 21,64 % | −1 002,54 | +41,61 | 77,37 | 2 | ×1,043 |
| 2025 | 3 929,85 | 140 | 25,71 % | −184,31 | +147,61 | 33,45 | 2 | ×0,615 |
| 2026 janvier–septembre | 3 147,52 | 105 | 20,95 % | −829,74 | −7,24 | 15,50 | 2 | ×0,487 |

Le taux gagnant s'améliore légèrement en 2024 (20,53 →21,64 %) mais l'equity
se dégrade : plus de trades gagnants en proportion ne signifie pas meilleur PnL.
Le résultat 2026 n'est pas expliqué par la seule valorisation terminale : son PnL
réalisé passe de +1 257,15 USD dans FIXED à −829,74 USD dans DYNAMIC.

Tentatives de fills synthétiques par profil (avant confirmation du commit du
portefeuille, pas le nombre garanti de positions réellement ouvertes) :

| DYNAMIC | REFERENCE | TREND | DEFENSIVE |
| --- | --- | --- | --- |
| 2024 | 131 | 23 | 5 |
| 2025 | 107 | 15 | 22 |
| 2026 | 81 | 24 | 5 |

Ces comptes montrent que la règle n'est pas restée partout identique au contrôle.
La performance est une conséquence de portefeuille complet : protection choisie,
durée de détention, capital disponible, réentrées et risques ; le tableau ne permet
pas d'attribuer causalement tout l'écart à une seule branche sans ablation distincte.
La qualité du régime ou l'idée générale de protections adaptatives ne sont pas
invalidées par une seule règle qui échoue. En revanche, **cette version ne doit
pas être promue**, ni ses seuils réajustés sur les mêmes pertes puis déclarés OOS.
Aucun modèle, paramètre de production, batch ou ordre modifié.

```powershell
Get-Content F:\projets\artifacts\research\us_oracle_path_dynamic_protections\20261014-v2\progress.json
```

Par cas : `profiles.json` (candidats/approbations), `fill-profiles.json`
(tentatives synthétiques à rapprocher des commits dans `executions.json`),
`trades.parquet`, `daily.parquet`, `open-positions.json`, `maintenance.json`.
Le résultat final sépare PnL réalisé et latent, intérêts, rendement, DD, taux de
réussite clôturé et exposition réelle ; `report.json` compare FIXED/DYNAMIC par année.
Les décisions non exécutées ne sont pas comptées comme des positions réelles.

Aucun seuil ne sera ajusté après constat des pertes pour présenter une capacité
d'anticipation. Une éventuelle promotion exige une confirmation indépendante.
