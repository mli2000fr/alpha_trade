# Dix plus grands mouvements H20 réellement observés — SL initial 7 %

## Contrat demandé le 7 octobre 2026

Simulation contrefactuelle : dix titres par date classés par valeur absolue du
rendement futur H20 ajusté (close J → close J+20), sur l'univers de 1 798 titres.
Ce n'est ni le TOP10 prédit ni les seuls rendements positifs. Les deux signes
sont achetés en LONG. Aucune intersection ATR n'est ajoutée. Le stop initial est
93 % du fill réel, avec les quatre variantes TP/trailing/échéance précédentes.
Sizing ATR, capital 4 000 USD, huit positions maximum et coûts restent conservés.

**Le futur sert volontairement à choisir ET ordonner les titres. Ce n'est pas
une stratégie réalisable ni une validation directionnelle.** Le champ requis
par l'adaptateur `proba_extreme` transporte ici `1-rang/1000`, une priorité
synthétique, pas une probabilité ni la sortie d'un modèle. Le contexte natif
`score_source=oracle_amplitude` n'a donc pas sa signification prédictive normale.
Les pondérations sensibles au score reçoivent cette priorité synthétique : le
comparatif ne constitue pas un changement du seul masque à scores identiques.

## Classement et couverture

Sources : archives complètes `labels_endpoint_checks.parquet` de 2025 et 2026,
dans `artifacts/research/us_extreme50_capture/audit-20261006-v1`.
Les rendements inconnus ne sont pas transformés en zéro. Le classement utilise
tous les labels finis disponibles de l'univers, pas uniquement le pool de
prédictions Oracle TOP20. Il reste conditionné à la couverture de ces labels.

- 419 dates classables jusqu'au 3 septembre 2026 ;
- 4 190 occurrences initiales dans les dix premiers ;
- 4 189 endpoints localement qualifiés, dont 3 133 positifs et 1 056 négatifs ;
- KLAC au signal du 20 mai 2026 : endpoint de sortie à volume nul le 18 juin,
  exclu après classement **sans remplacement**. Sa baisse apparente de 85,81 %
  n'est pas certifiée par ce diagnostic ; aucune conclusion de split ou de
  baisse authentique n'est tirée sans preuve complémentaire.

La période du portefeuille reste janvier 2025–septembre 2026 : après la dernière
date classable, aucune nouvelle sélection réelle H20 n'est inventée, mais les
positions continuent à être surveillées jusqu'à la fin. Ceci limite la
comparabilité avec des prédictions disponibles sur les dernières dates.

## Implémentation et contrôles

Script de recherche : `scripts/research/us_concentrated_realized_top10.py`.
Les barres de tous les noms sélectionnés sont archivées par SELECT, y compris
ceux absents des anciennes tapes du TOP20 prédit. Même macro, même référence
de secteurs actuels non PIT et même contrat risque sont contrôlés. Overlays
de volume BAND/GPRE appliqués uniquement s'ils concernent un titre chargé.
Aucune écriture SQL, collecte fournisseur, modification de modèle ou de batch.

Trois tests dédiés vérifient le classement absolu des deux signes, les labels
inconnus, les doublons et l'absence de remplacement après invalidation. Onze
tests ciblés sélection/stop passent.

## Premier smoke v1 : blocage de budget, aucun PnL final

Le smoke de trois séances échoue dans la première variante lors des achats du
3 janvier 2025 : `Replay quantity clipped by portfolio constraints: PGNY`.
Le portefeuille a déjà exécuté sept entrées. Le cash disponible vaut alors
384,69 USD, alors que l'ordre PGNY approuvé à J porte sur environ 23,1524 titres
à l'ouverture 17,75 USD, soit environ 410,96 USD hors frais. La règle stricte
de conservation de quantité ne permet ni ce dépassement ni un redimensionnement
silencieux ; le moteur refuse donc de poursuivre le replay partiellement muté.

Ce n'est pas un effet du stop 7 %, ni un résultat économique défavorable. Le
classement clairvoyant sélectionne un autre ensemble de titres et met en
évidence une saturation de budget qui ne s'était pas produite dans les replays
précédents. Ne pas réduire artificiellement les scores, augmenter le capital,
autoriser plus d'exposition ou abandonner les coûts pour faire passer ce cas.

Artefacts de diagnostic :
`artifacts/research/us_concentrated_replay/realized-top10-sl7-smoke-20261007-v1`.
Logs : `log/realized-top10-sl7-smoke-20261007-v1.log`.
Le script n'a pas lancé une campagne complète après cet échec.

### Étape requise avant de poursuivre

Fixer et vérifier la politique d'ouverture lorsque les gaps et frais rendent
les quantités approuvées incompatibles avec le budget disponible : refus
explicite de l'ordre ou redimensionnement contrôlé. L'appliquer de façon
cohérente au replay et à la référence, avec tests et audit des ordres, plutôt
que masquer cette divergence. Repartir du début dans un nouveau dossier :
la progression n'est pas un checkpoint complet du portefeuille.

## Correctif autorisé et relance v2 — 7 octobre 2026

Après GO explicite, politique **refus intégral de l'ordre**, sans resize :
`reject_constrained_replay_entries=True`. Si les frais, le budget disponible ou
la capacité d'exposition à l'ouverture imposeraient une réduction de la quantité
approuvée, l'ordre est refusé avant débit de cash et création de position. Les
ordres suivants sont encore évalués. La politique par défaut reste l'arrêt
strict : pas d'activation en production ni de changement de configuration live.

Le motif `approved_quantity_exceeds_opening_constraints` archive quantité
approuvée, quantité maximale contrainte, coût unitaire, budget restant, equity
et exposition. Aucun ordre refusé ne crée de protection détenue ou de trade.
Les fills Phase 3 sont ici des **tentatives synthétiques** ; les refus au commit
portefeuille sont distingués des fills oubliés. `entry_rejections.json` et
`executions.json` conservent ces refus explicitement, le rapport les compte.

Quatre tests supplémentaires : contrat strict inchangé, refus sans mutation de
cash, poursuite vers un ordre suivant abordable sans resize, frais seuls rendant
l'ordre non abordable. **72 tests ciblés passent.** Smoke v2 de trois séances
terminé sur les quatre variantes, y compris refus PGNY et cash réconcilié.

Deux campagnes complètes sont relancées depuis le début :

- réel TOP10 : `artifacts/research/us_concentrated_replay/realized-top10-sl7-20261007-v2` ;
- référence TOP10 prédit avec la même politique de refus :
  `artifacts/research/us_concentrated_replay/fixed-sl7-oracle_top10-budget-reject-20261007-v2`.

La référence est recalculée pour ne pas mélanger deux contrats d'ouverture.
Les réserves de prix/volume restent bloquantes : ce correctif ne permet pas de
contourner une barre détenue non qualifiée. Le classement et l'exclusion unique
KLAC sans remplacement restent inchangés. Les anciens artefacts sont conservés.

Surveillance :

```powershell
Get-Content artifacts/research/us_concentrated_replay/realized-top10-sl7-20261007-v2/progress.json
Get-Content log/batch/realized-top10-sl7-20261007-v2/realized.stderr.log -Tail 10
Get-Content artifacts/research/us_concentrated_replay/fixed-sl7-oracle_top10-budget-reject-20261007-v2/progress.json
```

Chaque variante possède aussi son `progress.json` quotidien. Le rapport global
apparaît après les quatre variantes ; un `failure.json` signale un arrêt du
script réel TOP10. Aucun rendement complet v2 n'est annoncé avant vérification.

## Résultats partiels vérifiés de la campagne v2

Le processus est arrêté, **pas complètement réussi** : deux variantes terminées,
troisième arrêtée, quatrième non lancée. La référence TOP10 prédit termine les
quatre variantes ; ses résultats sont inchangés et aucun refus d'ordre n'y est
survenu. Ce correctif n'altère donc pas les performances précédemment remises
pour cette référence.

| Sorties | TOP10 prédit, même contrat | TOP10 réel clairvoyant | Capital final réel |
|---|---:|---:|---:|
| TP + trailing, sans échéance | −8,38 % | +89,97 % | 7 598,63 USD |
| TP + trailing, échéance 20 séances | −7,86 % | +89,97 % | 7 598,63 USD |
| Sans TP, stop fixe, échéance 20 séances | +27,88 % | BLOQUÉ après 365/437 séances | Non disponible |
| Sans TP, trailing, échéance 20 séances | +21,57 % | NON LANCÉ | Non disponible |

Pour les deux runs réels terminés : 520 trades, 76,15 % gagnants, profit factor
1,26, Sharpe 1,47, exposition moyenne 40,93 % de l'equity et drawdown maximal
**−36,65 %**. Rendement 2025 +94,74 %, janvier–septembre 2026 −2,45 % ; capital
non réinitialisé entre années. Dix-neuf ordres refusés explicitement au commit
à l'ouverture, zéro fill oublié, zéro position finale et réconciliation cash
à environ 1e-11 USD. Tous les stops initiaux archivés valent 93 % du fill réel.

Les parquets de trades des deux variantes avec TP sont strictement identiques :
aucune sortie `expiry_20_after_entry` n'a été déclenchée. Les positions ont été
fermées par TP ou stop avant que cette échéance ne change la trajectoire.

### Nouveau blocage : ATEX, volume nul le 18 juin 2026

Le replay `NO_TP_FIXED_SL_20_AFTER_ENTRY` détient ATEX à cette date. Archive :
open 79,20, high 80,635, low 70,78, close 74,53, volume **0**, is_filled 0.
Le 17 juin a un volume 469 878 et le 22 juin 454 401. Cette contradiction doit
être qualifiée ; ces observations ne prouvent pas à elles seules un volume
correct ni une erreur fournisseur. Aucun volume n'est inventé, aucun titre
n'est retiré rétrospectivement pour poursuivre.

Avant reprise : obtenir une réponse fournisseur archivée bornée, vérifier
l'identité des OHLC et qualifier un éventuel overlay de volume, comme GPRE.
Si la source reste contradictoire, conserver le blocage. Rejouer ensuite les
variantes concernées depuis le début, sans reprendre au compteur 366.

### Conclusion limitée

Connaître les plus grandes amplitudes futures aide ici les variantes avec TP,
mais ne fournit pas la direction : les deux signes sont toujours achetés LONG,
et le drawdown demeure élevé. Aucune conclusion sur la variante sans TP n'est
possible avant résolution d'ATEX. Les rendements positifs sont **clairvoyants**,
non déployables, et restent conditionnés aux limites de prix, secteurs, scores
synthétiques et couverture H20 déjà documentées. L'écart avec la référence
ne mesure pas une amélioration prédictive réalisée par le modèle.

### Rejeu borné au 3 septembre 2026 — lancé le 7 octobre 2026

Dossier : `artifacts/research/us_concentrated_replay/realized-top10-sl7-end0903-20261007-v1`.
Période demandée : **2025-01-01 au 2026-09-03**, capital continu de 4 000 USD.
Les dix titres sont classés par amplitude H20 **réalisée**, les hausses et les
baisses sont toutes achetées LONG : **aucun filtre positif**. Ce n'est ni le
TOP10 du score prédit, ni dix pour cent de l'univers. Simulation clairvoyante
non déployable ; les labels futurs servent délibérément à la sélection.

SL initial fixe à 7 % du fill ; sizing, coûts, risque et les quatre variantes
restent inchangés. Les positions restantes sont liquidées à la dernière séance
du calendrier borné, même avant vingt séances depuis l'entrée. Les refus
d'ordres incompatibles avec le budget sont explicites, sans redimensionnement.
Les archives vérifiées du rejeu réel précédent sont réutilisées, sans lecture
ni écriture SQL et sans entraînement. Les contrôles de qualité sont maintenus,
notamment le volume nul ATEX du 18 juin 2026 : un échec ne produit pas de PnL
final validé. Chaque variante indépendante est tentée malgré un échec précédent.

Les dates sont désormais paramétrables dans les scripts de recherche ; les
valeurs par défaut restent celles des anciens essais (fin au 30 septembre).
Validation ciblée : **37 tests passants**, dont clôture anticipée à la borne
de fin pour les quatre variantes et rejet d'un intervalle inversé.

```powershell
python -u -m scripts.research.us_concentrated_realized_top10 --output artifacts/research/us_concentrated_replay/realized-top10-sl7-end0903-20261007-v1 --start-date 2025-01-01 --end-date 2026-09-03 --market-archive artifacts/research/us_concentrated_replay/realized-top10-sl7-20261007-v2 --continue-after-variant-error
```

Suivi : `progress.json` à la racine indique la variante active, chaque
sous-répertoire contient son avancement par séance ; le `report.json` racine
n'est écrit qu'après les quatre tentatives. `PARTIAL_FAILED` signifie qu'au
moins une variante reste bloquée, pas que toutes ont terminé avec un PnL.
Logs : `log/batch/realized-top10-sl7-end0903-20261007-v1/stderr.log`.

Commande du smoke (ne pas réutiliser le dossier déjà créé) :

```powershell
python -u -m scripts.research.us_concentrated_realized_top10 --output artifacts/research/us_concentrated_replay/realized-top10-sl7-smoke-20261007-v1 --max-days 3
```
