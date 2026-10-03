# Sprint 8-A — Labels France et contrat d'évaluation

Réalisé le 3 octobre 2026. **GO limité aux labels bruts de recherche**, pas aux rendements économiques ni à l'entraînement. Ce lot complète les panels [prix figé](sprint_7a2_profil_prix_fige_par_periode.md) et [benchmark relatif](sprint_7b_features_relatives_benchmark.md). Aucune base, IHM, tâche planifiée, pipeline US/CN ou modèle de serving n'est modifié.

## 1. Convention temporelle et rendement

Pour une ligne candidate dont la décision est à l'ouverture de J, les features ont pour dernière séance source J−1. La cible est calculée indépendamment des features :

```text
features jusqu'à J−1 → décision / entrée ouverte à J
                   → sortie à la clôture J+H
                   → label disponible à l'ouverture J+H+1
```

H prend les valeurs 5, 10 et 20, en décalages de séances officielles XPAR. Le chemin contient **H+1 barres, J comprise** : cette convention n'est pas « sortie après H barres en comptant J comme première barre ». Elle est figée dans `config/labels_fr/fr_labels_v1.yaml`.

`future_return = close(J+H) / open(J) - 1`. Les prix sont bruts ; pas de frais, spread, slippage, taxes, dividendes réinvestis ou règlements de radiation. L'ouverture archivée est un prix de référence de recherche, **pas une garantie de fill exécutable**. La disponibilité du label est la prochaine ouverture officielle ; une cible dont la publication reconstruite dépasserait le 2 octobre 2026 est `IMMATURE`, même si son prix de sortie existe.

La convention de disponibilité héritée reste `RESEARCH_J1_HYPOTHESIS_NOT_VERIFIED_PUBLICATION`. L'absence de preuve historique de réception interdit une promotion live implicite.

## 2. Censure du chemin

Chaque séance de J à J+H doit :

- exister dans le manifeste Sprint 5 et être `research_j1_eligible` ;
- porter le même ISIN que l'identité de recherche ;
- posséder une barre OHLCV archivée dont le payload est vérifié par SHA-256 ;
- avoir quatre prix positifs finis et un volume positif fini ;
- respecter `low ≤ open/close ≤ high`.

Une barre absente, une quarantaine, une identité différente ou une donnée invalide censure tout le chemin. On n'utilise ni la dernière clôture disponible, ni la prochaine cotation, ni un prix de radiation supposé nul. Un titre n'a pas besoin de rester au-dessus du seuil de liquidité d'entrée pendant toute la détention : le filtre d'entrée est celui du panel candidat à J ; le futur chemin demande l'admissibilité observable, pas une future sélection de portefeuille.

Les historiques avec splits non validés restent exclus selon le manifeste. Les corporate actions ne sont **pas** nouvellement réconciliées par ce module. Sans flux officiel de suspension, les trous et volumes nuls sont censurés, mais on ne prétend pas identifier toutes les suspensions. La censure peut être informative, particulièrement lors d'une radiation ou d'une crise : il faut toujours publier ses effectifs et ne pas présenter le sous-ensemble complet comme exempt de biais de survie.

Chaque ligne conserve `path_state`, `censor_reason`, dates d'entrée/sortie/disponibilité, prix et rendement ; les lignes censurées et immatures restent dans le fichier avec cible manquante.

## 3. Univers des rangs et sens des déciles

Le dénominateur initial est l'ensemble des **170 046 candidates PIT d'entrée du panel 7-A2**, non le sous-ensemble dont les features benchmark sont complètes et non une liste de titres survivants. Pour chaque date et horizon :

1. compter toutes les candidates ;
2. compter les chemins VALID ;
3. exiger au moins 20 chemins valides et une couverture VALID/candidates d'au moins 80 % ;
4. calculer les rangs uniquement parmi ces chemins valides, en conservant le taux de censure.

Le nombre de candidats, de chemins valides et leur ratio sont répétés dans les labels. Si le gate échoue, les rendements individuels observables peuvent subsister, mais les cibles de classement sont manquantes. Les rendements censurés ne reçoivent jamais un rang.

`D1` désigne le décile des rendements les plus faibles ; `D10` celui des rendements les plus élevés. Un rang croissant r parmi n observations donne `ceil(10*r/n)`. Les tailles de bins peuvent différer d'une unité si n n'est pas divisible par dix. **D10 ne garantit pas un rendement positif et D1 ne garantit pas un rendement négatif** : ils expriment un classement relatif.

Pour les égalités, on calcule le rang minimum et le rang maximum du groupe d'ex aequo. Une cible n'est connue que si ces deux rangs appartiennent au même décile ; sinon `decile_state=TIE_BOUNDARY`, cible NULL. Ni symbole ni UUID ne servent à départager arbitrairement les rendements identiques.

## 4. Oracle amplitude distinct de D1/D10

Cette version définit l'amplitude par **la valeur absolue du rendement terminal**, `abs(future_return)`, et non par MFE/MAE, range high-low ou premier franchissement de barrière. Un trajet très mouvementé revenu à son prix d'entrée peut donc ne pas être Extreme selon cette cible.

Le label Oracle vaut 1 pour les `ceil(0.20*n)` rendements absolus les plus élevés, 0 pour les autres. Les deux sens sont possibles. En présence d'une égalité à la frontière TOP20, tout le groupe traversant cette frontière reçoit `oracle_state=TIE_BOUNDARY` et cible NULL : on ne force pas exactement 20 % de positifs. L'arrondi supérieur peut produire légèrement plus de 20 % de positifs sur une petite cross-section ; publier le taux réel.

Les labels sont définis sur l'univers candidat FR complet de la date. Une future expérience conditionnelle Oracle doit utiliser les **scores Oracle OOF**, pas la cible Oracle réelle pour sélectionner artificiellement les titres accessibles à une stratégie.

## 5. Résultats de construction

| Horizon | Candidates | Chemins VALID | Censurés | Immatures | Oracle connu | Oracle positif |
|---|---:|---:|---:|---:|---:|---:|
| H5 | 170 046 | 162 139 | 7 353 | 554 | 161 053 | 32 969 |
| H10 | 170 046 | 155 654 | 13 379 | 1 013 | 153 698 | 31 478 |
| H20 | 170 046 | 144 254 | 23 977 | 1 815 | 139 755 | 28 635 |
| Total | 510 138 | 462 047 | 44 709 | 3 382 | 454 506 | 93 082 |

454 303 cibles de décile sont connues. Le rapport détaille chaque horizon par année, semestre et statut fournisseur actuel, ainsi que les effectifs D1/D10 et les journées de cross-section qualifiée. Les états de rang et les cibles permettent de recalculer les fréquences quotidiennement sans perdre les dénominateurs.

**Réserve radiés : cinq symboles seulement** parmi les 168 du panel entraînable sont actuellement classés delisted par le fournisseur : ALPRO.PA, AMPLI.PA, EIFF.PA, NOKIA.PA et TKTT.PA. Ensemble, ils représentent 86 observations par horizon ; leurs chemins VALID sont respectivement 65 en H5, 53 en H10 et 43 en H20. Le statut actuel est une métadonnée d'audit, pas une feature ni une preuve PIT du jour de radiation. Le dossier amont comprend davantage de radiés, mais les gates observabilité/historique/liquidité réduisent fortement leur présence ici. **Aucune robustesse radiés n'est démontrée.**

L'audit secteur/taille demeure `BLOCKED_NO_VALIDATED_HISTORICAL_MEMBERSHIPS_OR_SIZE`. Les classes inconnues ne sont pas remplies avec les valeurs actuelles.

## 6. Plan chronologique — pas encore des folds entraînables validés

Le manifeste propose huit fenêtres expanding sur les séances de décision, avec :

- minimum 504 séances de train ;
- 21 séances de séparation avant validation (H20 + publication J+1) ;
- validation 126 séances, test 126 séances, pas 126 séances ;
- train : aucune cible disponible à ou après l'ouverture du début de validation ;
- validation : aucune cible disponible à ou après l'ouverture du début de test ;
- test développement : publication de cible au plus tard le 31 décembre 2025 ;
- confirmation réservée à partir du 1er janvier 2026, non utilisée pour ajuster les modèles ou seuils.

Première fenêtre : train 2019-01-31–2021-01-20, validation 2021-02-19–2021-08-17, test 2021-08-18–2022-02-09. Dernière : train jusqu'au 2024-06-27, validation 2024-07-29–2025-01-23, test 2025-01-24–2025-07-23. La fin de 2025 non couverte par ces tests complets n'est pas artificiellement ajoutée à un fold court.

Chaque fold est marqué **`PLAN_ONLY_SUPPORT_NOT_YET_VALIDATED`**. Les supports Oracle/déciles après contrôle de maturité sont calculés, mais ils ne sont pas encore croisés avec les masques prix/benchmark, ni soumis à des gates de stabilité des classes. Les quatre semestres du benchmark ne doivent pas être recollés en une série continue. Pour chaque entraînement futur, vérifier la disponibilité réelle de chaque cible, pas seulement la séparation des dates de décision.

Ce lot ne change pas le planning global : après la clôture des gates labels du Sprint 8, les modèles Oracle relèvent du Sprint 9. Le terme « 8-B » peut désigner la revue complémentaire des labels/supports, **pas une permission d'entraîner tant que les réserves bloquantes ne sont pas traitées**.

## 7. Reproduction et contrôle

- Configuration : `config/labels_fr/fr_labels_v1.yaml`.
- Implémentation : `modelFactory/fr_labels.py`.
- Tests : `tests/test_fr_labels.py`.
- Artefact final : `artifacts/fr/labels/fr_labels_v1/fr-labels-v1-a8f5acc2804c/`.
- `labels.parquet` : cibles, prix, disponibilité, censure, dénominateurs et états de classement.
- `report.json` : règles figées, sources, empreintes des 168 payloads, audits, contrôle des ratios et plan de folds.

```powershell
python -u -m modelFactory.fr_labels --verify-rebuild
```

Deux constructions identiques : hash labels `f8c845aba3fa37bdc06ad51020ef8aecdf4d9016de2a75a7729ed353cbe4ab68`. Les sources prix et manifeste sont vérifiées, les identités et leurs liens aux candidats sont contrôlés, et les changements de contrat imposent une nouvelle version. Un fichier divergent n'écrase pas l'artefact précédent.

492 ratios ont été recalculés à partir des prix archivés, au moins une première observation valide par paire symbole/horizon lorsque disponible. **Ce recalcul n'est pas une validation indépendante des prix par un second fournisseur**, ni une revue humaine des corporate actions. La revue des chemins et actions sur titres demeure `PENDING_REVIEW_OF_PRICE_PATHS_AND_CORPORATE_ACTIONS`.

176 tests ciblés passent, dont 12 nouveaux cas : entrée/sortie/publication, immaturité même si sortie connue, trou, quarantaine, changement ISIN, volume nul, OHLC incohérent, D1/D10, Oracle dans les deux sens, égalités, couverture minimale, invariance après modification d'un prix hors horizon et séparation des folds. Ruff passe. Il ne s'agit pas de l'ensemble des tests de l'application.

## 8. Gate et suite

Le [Sprint 8-B — revue des chemins et support des folds](sprint_8b_revue_chemins_et_support_folds.md) est réalisé. Il retrouve trois folds H5 prix-only suffisamment couverts (4/5/6), aucun fold complet H10/H20 ou benchmark, et produit 325 cas de revue. Les cibles 8-A restent inchangées ; aucune validation économique ou levée générale des réserves n'est impliquée.

**GO_RAW_RESEARCH_LABELS_ONLY** : construction traçable, censure et maturité testées. **Pas de GO économique/live et pas d'entraînement lancé.** Le Sprint 8 complet n'est pas clos : revue ciblée des chemins extrêmes et corporate actions, faibles effectifs radiés, supports prix/benchmark des folds et réserves PIT restent à examiner avant le Sprint 9. Ne pas transformer les rendements bruts en promesse de PnL net.
