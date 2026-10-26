# P01 — bilan : amélioration 2025, pas de confirmation transversale

22 octobre 2026. **TERMINÉ / NO_GO_P01_NOT_CONFIRMED / PAS DE PROMOTION.**

Le filtre compression→expansion→cassure a été testé sans optimiser ses seuils.
Il améliore le portefeuille en2025, mais reste perdant en2026 et fait nettement
moins bien que Winner sans filtre cette année-là. Ne pas le brancher en production
sur cette seule preuve. Ce résultat rejette cette règle figée sur ce périmètre,
pas toutes les stratégies de compression.

[Protocole figé avant calcul](oracle_compression_p01_20261022.md).
Dossier canonique : `artifacts/research/us_oracle_compression_p01/20261022-v2`.
Sources du concept, au commit lu :
[BB/Keltner Squeeze](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/BB-Keltner-Squeeze%E4%BA%A4%E6%98%93%E7%AD%96%E7%95%A5BB-Keltner-Squeeze-Trading-Strategy.md)
et [Squeeze Momentum](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/Squeeze-Momentum-Indicator.md).
Adaptation causale actions proposée par Alpha Trade, pas reproduction ni
validation des performances annoncées par ces scripts.

## Population et contrôles

213 campagnes LONG TOP10 CatBoost PATH H20 de recherche étaient candidates.
**200 campagnes, 69 titres** restent dans le périmètre commun : huit réserves
pour chemins intraday manquants et cinq pour maturité insuffisante. Les réserves
s'appliquent aux trois bras, même si l'un serait sorti avant le trou. Aucun titre
de remplacement. Les occasions sans signal restent en cash et ne disparaissent
pas du dénominateur unitaire.

2024 n'est pas simulée : pas de couverture intraday dans cette archive figée.
2026 va jusqu'au30septembre. L'univers est conditionnel à des chemins futurs
complets et aux survivants ; ce n'est ni tout le TOP10 quotidien ni le modèle
LightGBM de production. Les deux années avaient déjà été étudiées.

Trois comparaisons : Winner usuel ; Winner après warmup des indicateurs, sans
filtre de compression ; P01 avec trois barres de compression et libération
dans les six barres avant la première clôture de cassure. Même SL7/TR15,
pas de TP/renforcement, vingt séances depuis l'entrée puis vente à l'open21.
Même capital initial4 000USD, demi-cible, plafond d'admission1x et B4DD15.

Les statistiques unitaires groupent les occasions par année **du signal Oracle**.
Les portefeuilles annuels groupent les entrées par année **d'exécution** : neuf
signaux bras/campagne issus de fin2025 entrent en2026 (MP, SRPT, FUN, RARE).
Ce n'est pas neuf sociétés différentes ni une discordance de comptage.

## Portefeuille : friction normale de 8bps par jambe

| Année | Variante | Capital final USD | Rendement net | DD max | Trades fermés | Gagnants | Capital utilisé moyen USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025 | Winner | 4 803,41 | +20,09 % | 18,79 % | 90 | 33,33 % | 2 262,00 |
| 2025 | Attente/warmup seule | 4 871,16 | +21,78 % | 18,41 % | 91 | 29,67 % | 2 079,72 |
| 2025 | P01 | 5 552,64 | **+38,82 %** | 16,58 % | 48 | 33,33 % | 1 598,34 |
| 2026 | Winner | 4 077,42 | **+1,94 %** | 18,60 % | 61 | 36,07 % | 1 563,60 |
| 2026 | Attente/warmup seule | 3 366,32 | −15,84 % | 21,80 % | 47 | 25,53 % | 786,44 |
| 2026 | P01 | 3 511,24 | **−12,22 %** | 18,76 % | 39 | 28,21 % | 797,52 |

Les quantités sont recalculées avec la même formule, pas maintenues identiques
après divergence du cash et de B4. En2025, six/six/trois positions restent ouvertes
à la borne annuelle : le capital final inclut leur valorisation, pas un rendement
réalisé fictif ni une liquidation inventée. Aucun ouvert à finseptembre2026.
Le taux gagnant ne concerne que les trades fermés.

P01 réalise sur les trades fermés :

- 2025 :16gagnants/32perdants ; gains cumulés+3 576,03USD, pertes−1 904,53USD ;
  gain moyen+223,50USD, perte moyenne−59,52USD.
- 2026 :11gagnants/28perdants ; gains+532,63USD, pertes−1 021,39USD ;
  gain moyen+48,42USD, perte moyenne−36,48USD.

Le filtre n'augmente donc pas le taux gagnant de façon transversale. En2025,
MP représente+807,62USD, MLTX+510,85USD et KSS+370,33USD de PnL fermé agrégé par
titre : les gains sont concentrés, pas une amélioration uniforme de chaque trade.
Ce constat n'est pas une raison d'exclure ces titres a posteriori ou de sélectionner
seulement leur régime gagnant.

## Stress : 25bps par jambe

| Année | Winner | Attente/warmup seule | P01 | DD max P01 |
| --- | ---: | ---: | ---: | ---: |
| 2025 | +25,72 % | +21,10 % | +35,25 % | 16,51 % |
| 2026 | −0,24 % | −16,02 % | −12,84 % | 19,08 % |

Avec B4 et réinvestissement, plus de frais peut changer les admissions et les
dates de réduction/reprise du risque. Le Winner2025 à25bps n'est donc pas une
simple soustraction de frais sur les mêmes trades :87trades contre90à8bps.
Ce résultat non monotone ne signifie pas que les frais créent un avantage ;
sur les mêmes chemins unitaires, le coût supplémentaire réduit bien le rendement.

## Le filtre aide-t-il, au-delà du simple retard ?

P01 fait mieux que le témoin **warmup** dans les quatre portefeuilles annuels
année×friction : surplus de+17,04/+3,62points en2025/2026 à8bps, puis
+14,15/+3,18points à25bps. Mais **le retard seul dégrade fortement2026**,
et P01 ne retrouve pas le résultat Winner initial cette année-là.

Le délai médian d'entrée passe de3à7séances en2025, et de3à8en2026.
La réduction d'exposition et les interactions avec B4 peuvent améliorer un
portefeuille sans améliorer le rendement d'une occasion sélectionnée.

Contrôle sans chevauchement par titre, blocage conservateur OracleJ+40 :

| Année Oracle | Occasions | Signaux P01 / titres | Surplus unitaire d'occasion P01−warmup | Intervalle95 % bootstrap mensuel |
| --- | ---: | ---: | ---: | --- |
| 2025 | 80 | 41 / 33 | **−0,81point** | [−3,36 ; +1,62] |
| 2026 | 59 | 38 / 24 | +0,44point | [−1,56 ; +1,88] |

Les minimums de30signaux/10titres par année passent, mais pas les critères
de confirmation : surplus2025 négatif, intervalles recouvrant zéro, surplus
2026 juillet–septembre négatif (−0,49point ; janvier–juin+0,61).
Pas de seuil retouché, de modèle entraîné ou de régime choisi après ces pertes.

## Vérifications et limites

**120 tests ciblés passent.** Vérification arithmétique distincte de **504 signaux**
(première entrée de chaque bras incluse), **1 008 rendements unitaires** aux deux
frictions et **12 portefeuilles**. Reconstruction séparée des sorties, gaps,
cash, frais, valorisations et traces B4 ; empreintes des sources et archives
revérifiées avant/après calcul. Même assistant, pas revue humaine indépendante.

Le premier passage v1 n'est pas validé : un demi-cent GLW a révélé l'écart entre
les expressions flottantes `1-0,07` et `0,93`. Adaptateur et reconstruction
alignés sur le contrat Winner existant ; tests de non-régression, puis rejeu
complet v2, sans changer la stratégie ni modifier la production.

OHLC5m et frais hypothétiques ne certifient ni NBBO, ni ordre des ticks, ni fills
réels. B4 ne garantit pas un DD maximal de15 % : des résultats dépassant ce seuil
ne sont pas contradictoires avec son fonctionnement. Couverture et opérations
sur titres non exhaustivement certifiées ; biais de sélection future/survivants.
Aucun entraînement, téléchargement fournisseur, accès/écriture SQL, ordre ou
changement de modèle, de batch ou de configuration de production.

## Fichiers de résultat

- `annual-summary.csv` : tous les rendements, DD, taux gagnants/perdants,
  gains/pertes moyens, durées et capital utilisé.
- `report.json` : exclusions, critères et douze bilans complets.
- `final-audit.json` : verdict de la vérification séparée.
- `signals.parquet`, `unit-results.parquet`, `nonoverlap.parquet` : décisions
  et résultats conservés sans nouvelle sélection.
- Sous-dossiers de chaque bras/friction/année : trades, courbes, refus et risque.

Conclusion : **ne pas promouvoir P01**. Garder ce résultat pour éviter une
nouvelle optimisation opportuniste de la même piste. Aucune autre piste lancée.
