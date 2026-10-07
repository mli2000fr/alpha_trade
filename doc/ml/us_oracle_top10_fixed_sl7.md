# TOP10 Oracle sans filtre directionnel — stop initial fixe à 7 %

## Expérience du 7 octobre 2026

Demande : refaire le replay des dix premiers titres prédits chaque jour par
l'Oracle, positifs et négatifs compris, en remplaçant le stop initial ATR par
un stop de 7 %. Aucun filtre utilisant le futur n'est appliqué.

La sélection est le **TOP10 original complet**, pas le TOP10 à labels observables
de l'expérience [direction parfaite](us_oracle_top10_perfect_direction.md).
Sa référence est le replay `live-portfolio-oracle_top10-20261007-v2`.
Les candidats sans label futur restent éligibles : la décision n'a pas besoin
du rendement futur pour cette simulation.

## Ce qui change exactement

Pour chaque LONG réellement exécuté :

```text
stop initial = prix de fill réel × 0,93
```

Cette formule remplace le niveau issu de 2,5 × ATR. Elle est appliquée après
l'exécution Phase 3 et avant la validation/consommation des protections Phase 4.
Le niveau est synchronisé dans les signaux, le tableau de protections et les
ordres enfant de stop initial. Les entrées rejetées restent rejetées.

**La perte n'est pas garantie inférieure à 7 %** : un gap défavorable déclenche
une sortie à l'ouverture disponible, potentiellement sous le stop. Les coûts
ajoutent également une perte nette au-delà de la distance du seuil.

## Ce qui ne change pas

- Capital initial 4 000 USD, huit positions maximum, mêmes contraintes et régime.
- Sizing et contrôles avant exécution inchangés : ils continuent à utiliser les
  règles ATR historiques. Il s'agit d'un test isolé de sortie, pas d'une mise
  en cohérence complète du sizing avec un risque de 7 % par action.
- TP inchangé lorsqu'actif : min(3 × ATR, 7 %).
- Paramètres et activation du trailing inchangés lorsqu'actif ; dans ces
  variantes, le stop n'est donc pas immobile pendant toute la position.
- Quatre variantes : TP/trailing sans échéance ; TP/trailing avec échéance
  vingt séances après entrée ; sans TP/stop initial seul avec cette échéance ;
  sans TP/trailing avec cette échéance.
- Même univers 1 798 titres, mêmes tapes, mêmes overlays fournisseur BAND/GPRE.
- Secteurs actuels non PIT acceptés, macro quotidienne non certifiée par vintage,
  fills OHLC simulés et coûts du contrat précédent conservés.

La variante **sans TP / stop initial seul / vingt séances après entrée** est
celle où le stop reste réellement fixe à −7 %, sans trailing.
L'échéance est comptée après l'entrée J+1, pas après le signal J.
Toutes les positions restantes sont liquidées en fin de période.

## Implémentation isolée et tests

Le sous-type de recherche `FixedInitialStopLedger` remplace uniquement la
construction du stop. Le ledger par défaut continue à produire les protections
natives si l'option n'est pas fournie. Ni config de production, modèle, base de
données ni batch existant n'est modifié.

Tests dédiés : niveau fondé sur le fill plutôt que le signal, conservation
TP/trailing, cohérence des trois représentations, absence de mutation de l'objet
original, paramètres invalides, déclenchement intraday et gap sous le stop.
25 tests ciblés de sélection/orchestration/stop passent.

## Lancement et surveillance

```powershell
python -u -m scripts.research.us_concentrated_live_portfolio --output artifacts/research/us_concentrated_replay/fixed-sl7-oracle_top10-20261007-v1 --policy ORACLE_TOP10 --initial-stop-pct 0.07 --volume-overlay artifacts/research/us_concentrated_replay/gpre-volume-refresh-20261007-v1/volume-overlay.parquet
```

Période : janvier 2025 à septembre 2026, 437 séances.
Le calcul complet a été lancé le 7 octobre, avec quatre variantes successives.

```powershell
Get-Content artifacts/research/us_concentrated_replay/fixed-sl7-oracle_top10-20261007-v1/progress.json
Get-Content artifacts/research/us_concentrated_replay/fixed-sl7-oracle_top10-20261007-v1/stderr.log -Tail 10
```

`report.json` à la racine n'est créé qu'une fois les quatre simulations terminées.
Chaque variante possède également sa progression et son rapport individuel.
Comparer rendement net, drawdown, exposition, trades et années séparées à la
référence TOP10 complet correspondante ; ne pas comparer uniquement des win rates.

## Résultats terminés

### Contrôle supplémentaire Oracle × ATR, lancé le 7 octobre 2026

À la demande de l'utilisateur, nouveau replay avec la sélection archivée
`INTERSECTION_ORACLE_TOP10` : intersection des TOP20 % Oracle et ATR20%, puis
les dix scores Oracle les plus élevés dans cette intersection. Cela ne signifie
ni TOP10 % ni intersection des dix titres Oracle avec les dix titres ATR.

**Avant lancement, les sélections sont identiques : 4 370 occurrences dans
chacune, aucun désaccord sur les 437 séances.** Le percentile ATR minimal parmi
les dix premiers Oracle est 0,847608, donc tous dépassent le seuil 0,8.
Cela ne prouve pas une équivalence générale des deux méthodes, seulement celle
observée sur ces tapes. Aucun seuil ATR plus strict n'a été ajouté pour forcer
une différence.

Les quatre variantes, le SL initial 7 %, les coûts, le sizing et la période
sont conservés. Sorties dans
`artifacts/research/us_concentrated_replay/fixed-sl7-oracle_atr_top10-20261007-v1`.
Le nouveau run est terminé : les quatre variantes terminent leurs 437 séances.
Les parquets de trajectoire quotidienne **et de trades sont strictement égaux**
à ceux du TOP10 Oracle seul pour chaque variante ; toutes les métriques sont
identiques hors nom de politique. Contrats de risque/régime/sources/overlays et
archive macro également identiques. Réconciliation cash meilleure que 1e-6 USD
et aucun fill Phase 3 oublié. Les rendements sont donc respectivement −8,38 %,
−7,86 %, +27,88 % et +21,57 % dans l'ordre des variantes du tableau ci-dessous.
Ce filtre ATR n'apporte aucune différence sur cette sélection concentrée ;
cela ne contredit pas les différences constatées sur des pools plus larges.
Commande :

```powershell
python -u -m scripts.research.us_concentrated_live_portfolio --output artifacts/research/us_concentrated_replay/fixed-sl7-oracle_atr_top10-20261007-v1 --policy INTERSECTION_ORACLE_TOP10 --initial-stop-pct 0.07 --volume-overlay artifacts/research/us_concentrated_replay/gpre-volume-refresh-20261007-v1/volume-overlay.parquet
```

Deux nouveaux tests vérifient le classement dans l'intersection et le cas où
un premier Oracle de faible ATR est exclu au profit d'un autre de l'intersection.
Les dix tests ciblés sélection/stop passent.

### Résultats du TOP10 Oracle complet de référence

Les quatre runs terminent leurs 437 séances. Réconciliation cash/PnL meilleure
que 1e-6 USD, aucune position restante et aucun fill Phase 3 oublié.
Le niveau de stop initial archivé dans tous les trades correspond à 93 % du
prix de fill (écart maximal numérique 1,14e-13 USD). Les contrats risque, régime,
variantes, sources, secteurs et overlays sont identiques à la référence ;
le contenu du parquet macro est également identique.

Rendements cumulés nets des coûts simulés, non annualisés :

| Sorties | Ancien stop 2,5 × ATR | Nouveau stop initial 7 % | Capital final | Drawdown nouveau | Sharpe nouveau |
|---|---:|---:|---:|---:|---:|
| TP + trailing, sans échéance | −9,74 % | −8,38 % | 3 664,92 $ | −17,40 % | −0,50 |
| TP + trailing, échéance 20 séances | −9,02 % | −7,86 % | 3 685,61 $ | −17,80 % | −0,44 |
| Sans TP, sans trailing, échéance 20 séances | −2,52 % | **+27,88 %** | **5 115,19 $** | −13,30 % | 0,80 |
| Sans TP, avec trailing, échéance 20 séances | +4,23 % | **+21,57 %** | **4 862,77 $** | −14,93 % | 0,70 |

| Sorties | 2025 | Janvier–septembre 2026 | Trades | Gagnants | Profit factor | Exposition brute moyenne / equity |
|---|---:|---:|---:|---:|---:|---:|
| TP + trailing, sans échéance | −10,31 % | +2,16 % | 213 | 59,15 % | 0,85 | 13,32 % |
| TP + trailing, échéance 20 séances | −11,16 % | +3,71 % | 225 | 59,56 % | 0,86 | 13,80 % |
| Sans TP, sans trailing, échéance 20 séances | +1,20 % | +26,36 % | 300 | 28,00 % | 1,25 | 41,67 % |
| Sans TP, avec trailing, échéance 20 séances | +10,11 % | +10,41 % | 223 | 41,26 % | 1,22 | 41,39 % |

Le capital n'est pas réinitialisé entre années. Ces chiffres portent sur
janvier–septembre 2026, pas uniquement 2026H1.

### Rejeu demandé jusqu'au 3 septembre 2026 — TOP10 prédit

Le run `fixed-sl7-predicted-oracle-top10-end0903-20261007-v1` sélectionne les
dix scores Oracle prédits les plus élevés, sans filtre sur le signe futur,
du 1er janvier 2025 au 3 septembre 2026. Toutes les entrées sont LONG.
Capital initial 4 000 USD, SL initial fixe 7 %, mêmes quatre variantes,
liquidation terminale à la fin de la période. Le sizing reste fondé sur ATR ;
aucun filtre de sélection ATR n'est ajouté. Les rendements futurs ne figurent
pas dans les colonnes de décision autorisées par `decision_rows`.

Le précédent run `realized-top10-sl7-end0903-20261007-v1` répondait à une
sélection clairvoyante différente : **ses +89,58 % ne sont pas le résultat
du modèle prédit et ne répondent pas à cette demande**.

Correction ATEX : EODHD relu le 7 octobre 2026 fournit un volume de **801 820**
pour le 18 juin 2026, au lieu du zéro local, avec OHLC inchangés :
79,20 / 80,635 / 70,78 / 74,53. Preuve et overlay dans
`artifacts/research/us_concentrated_replay/atex-volume-refresh-20261007-v1`.
La réponse brute et l'overlay sont hachés ; le lecteur vérifie les pièces et
leur cohérence avant application. Correction fournisseur observée après coup,
**non PIT et non certification indépendante**. Aucune modification SQL ni
écrasement des archives source ; seuls les replays explicitement munis de
cet overlay en bénéficient. Les anciens runs FAILED restent inchangés.

### Résultats du TOP10 prédit, fin au 3 septembre 2026

Run `fixed-sl7-predicted-oracle-top10-end0903-20261007-v1` : quatre variantes
COMPLETED, 419 séances, aucune écriture SQL ni entraînement. Les chiffres
ci-dessous remplacent toute interprétation des +89,58 % clairvoyants pour
cette demande. Les frais simulés sont inclus ; capital continu de 4 000 USD.

| Variante | Rendement net | Capital final USD | Drawdown max | Sharpe | Trades | Gagnants |
|---|---:|---:|---:|---:|---:|---:|
| TP + trailing sans échéance | −9,21 % | 3 631,58 | −17,40 % | −0,57 | 205 | 58,54 % |
| TP + trailing, vingt séances | −8,51 % | 3 659,72 | −17,80 % | −0,50 | 215 | 59,07 % |
| Sans TP ni trailing, vingt séances | +25,59 % | 5 023,67 | −13,30 % | 0,77 | 289 | 27,68 % |
| Sans TP avec trailing, vingt séances | +21,91 % | 4 876,28 | −14,93 % | 0,73 | 214 | 41,59 % |

| Variante | 2025 | 2026 au 3 septembre | Exposition moyenne / equity | Profit factor |
|---|---:|---:|---:|---:|
| TP + trailing sans échéance | −10,31 % | +1,23 % | 13,66 % | 0,83 |
| TP + trailing, vingt séances | −11,16 % | +2,98 % | 14,15 % | 0,85 |
| Sans TP ni trailing, vingt séances | +1,20 % | +24,10 % | 41,90 % | 1,24 |
| Sans TP avec trailing, vingt séances | +10,11 % | +10,71 % | 41,16 % | 1,24 |

Concentration : les cinq meilleurs trades rapportent 1 197,49 USD pour un
gain global de 1 023,67 USD sans TP/trailing ; avec trailing, 1 055,12 USD
pour un gain global de 876,28 USD. Le gain dépend donc fortement de quelques
positions, et le faible taux de réussite de la première variante n'empêche
pas un résultat positif grâce à l'asymétrie des gains/pertes.
Réconciliation cash inférieure à 4e-12 USD, zéro fill non commité, zéro ordre
refusé au commit pour budget incompatible, intérêts de marge nuls.
Les sorties au stop en gap restent possibles au-delà de 7 % de perte.
Ces résultats sont exploratoires sur historique déjà étudié : pas une
confirmation OOS indépendante ni une recommandation de déploiement.

### Lecture et réserves

Sans TP/sans trailing, le gain moyen est 66,79 USD par trade gagnant contre
−20,81 USD par perdant : 28 % de gagnants peuvent donc suffire ici. Parmi les
300 sorties, 184 sont au stop initial et 26 au stop en gap ; 81 à échéance,
huit à la fin de période et une par liquidation de régime.

Le résultat demeure concentré : les cinq meilleurs trades totalisent
1 197,49 USD, contre un PnL net global de 1 115,19 USD. Pour la variante avec
trailing sans TP, ils totalisent 1 055,12 USD contre 862,77 USD de PnL global.
Il s'agit d'une attribution descriptive, pas d'un nouveau replay excluant ces
trades (qui aurait modifié tout le parcours du portefeuille).

**Conclusion : remplacer le stop ATR par un stop initial 7 % améliore les quatre
variantes sur cet historique, surtout lorsque le TP est désactivé.** Les sorties
avec TP restent perdantes. Ce test ne démontre pas une capacité directionnelle,
ni une robustesse future : il s'agit d'une nouvelle variante étudiée sur un
historique déjà examiné. Ne pas promouvoir directement en production ; une
confirmation figée sur données non utilisées et une analyse de concentration
restent nécessaires. Le sizing ATR conservé doit également être distingué
d'un sizing qui viserait explicitement le risque monétaire du stop 7 %.
