# Actions ordinaires : audit de fiabilité TOP100

Audit terminé le 4 novembre 2026, à la demande de réduire les listes de
1 500 à **100 titres par source et par cible**. Cette variante reprend les
scores sauvegardés du [protocole initial](univers_predictibilite_20261103.md) :
5 254 actions ordinaires, 21 944 modèles annuels déjà entraînés. Aucun nouvel
entraînement, appel fournisseur/LLM, ordre ou changement de production.

## Méthode et période

Les 100 premiers de chaque classement de fiabilité **2023–2025 hors
entraînement** sont conservés dans leur ordre initial. Les modèles restent
renouvelés annuellement. Les prévisions 2026 jusqu'au 2 novembre servent au
contrôle, jamais au reclassement. Les périodes ont déjà été explorées : ce
n'est pas une nouvelle épreuve indépendante.

Deux cibles séparées :

- **H10** : proxy daily LONG, entrée à l'ouverture suivante, SL5 %, sans TP ni
  trailing, sortie open11, positif après frais. Ce n'est pas le replay Winner
  avec confirmation intraday, capital et portefeuille.
- **Parcours H20** : le pic haussier dépasse en amplitude absolue le pic
  baissier pendant vingt séances, depuis l'ouverture suivante. Il ne s'agit
  pas d'un rendement réalisable. Les deux pics et leur ordre restent sauvegardés ;
  l'ordre intraday de deux pics le même jour est inconnu.

## Contrôle 2026 non chevauchant

Les AUC et écarts de précision ci-dessous sont des **médianes par titre**.
Une AUC de 0,50 correspond à l'absence de discrimination observée.

| Mesure | H10 TOP100 | H10 TOP1500 antérieur | H20 TOP100 | H20 TOP1500 antérieur |
|---|---:|---:|---:|---:|
| Titres sélectionnés | 100 | 1 500 | 100 | 1 500 |
| Titres avec AUC calculable | 97 | 1 477 | 100 | 1 478 |
| AUC médiane | **0,4800** | 0,5111 | **0,5000** | 0,5000 |
| Titres avec AUC > 0,50 | 44,33 % | 50,98 % | 44,00 % | 48,04 % |
| Écart médian de précision LONG à la fréquence propre au titre | 0,00 point | +0,66 point | −4,44 points | +4,17 points |
| Fenêtres non chevauchantes médianes par titre | 19 | 18 | 9 | 9 |

Dans les autres titres historiquement qualifiés, l'AUC médiane est de 0,5111
pour H10 et 0,5000 pour H20. **Restreindre aux 100 premiers n'apporte pas
d'amélioration observée en 2026.** Cela ne prouve pas une absence universelle
de signal ; les échantillons par titre sont petits et les comparaisons nombreuses.

Sur l'ensemble des fenêtres LONG retenues du TOP100 :

| Cible | Fenêtres retenues | Positives | Négatives | Part positive | Fréquence positive dans toutes les fenêtres du TOP100 |
|---|---:|---:|---:|---:|---:|
| H10 | 552 | 201 | 351 | 36,41 % | 37,06 % |
| Parcours H20 | 271 | 119 | 152 | 43,91 % | 46,67 % |

Ces comptes sont des observations titre/fenêtre, **pas des trades d'un
portefeuille Winner**. L'absence de chevauchement temporel par titre n'élimine
pas la dépendance entre actions exposées au même marché. Aucun rendement,
capital final ou drawdown n'est calculé par cette variante.

## Options, consensus et intersections

Les minima de qualification restent inchangés : **20 fenêtres matures
non chevauchantes par titre et source** avant de tenter un classement de
fiabilité. Le fait de demander 100 noms au lieu de 1 500 ne crée pas ce recul.

| Source dans les listes modèles TOP100 | H10 | H20 |
|---|---:|---:|
| Options : source présente, historique insuffisant | 80 | 82 |
| Options : source absente | 20 | 18 |
| Consensus : historique insuffisant | 100 | 100 |
| Borne optimiste maximale de fenêtres indépendantes options | 3 | 1 |
| Borne optimiste maximale de fenêtres indépendantes consensus | 1 | 0 |

Les listes fiables options et consensus restent donc vides, pour les deux
cibles. Les deux intersections demandées restent également vides et portent
le statut **UNQUALIFIED_EMPTY_DO_NOT_USE_FOR_TRADING**. Ce n'est pas la preuve
qu'aucun titre ne se trouverait dans les trois listes avec un historique suffisant.
Les deux candidats H10 répondant au contrôle de cohérence exploratoire
2023–2025, FTS et HOMB, restent présents ; leurs quelques signaux 2026 ne
suffisent pas à certifier leur robustesse. Aucun candidat équivalent pour H20.

## Fichiers et vérification

Résultats : `artifacts/research/us_predictable_symbols/20261104-top100-v1/`.

- `winner_h10-model-top100.txt` et `parcours_h20-model-top100.txt` : listes
  modèles exploratoires de 100 noms, séparés par des virgules.
- `{cible}-top100-audit.csv` : rang, fiabilité historique et contrôle 2026.
  `check_2026_auc_all_overlapping` est l'ancienne AUC toutes dates ; `auc`
  est l'AUC non chevauchante utilisée dans ce bilan.
- `{cible}-top100-source-gates.csv` : motifs de non-qualification des sources.
- `{cible}-2026-nonoverlap-observations.parquet` : prévisions et résultats
  utilisés pour compter les fenêtres retenues.
- `report.json`, `protocol.json`, `verification.json` : métriques, empreintes
  des entrées et assertions de cohérence.
- `previous-requested-outputs/` : reçus et intersections précédents préservés.

Les sorties `config/univers_batch/symbol_trade_winner_h10.txt` et
`symbol_trade_parcours_h20.txt` restent vides ; leurs reçus `.audit.json`
pointent désormais vers ce TOP100. Elles ne sont raccordées à aucun batch.

Vérification **PASS** : listes distinctes et préfixes exacts des TOP1500,
appartenance au fichier source, CHRD/WFRD toujours exclus pour identité,
reproduction des métriques TOP1500, empreintes initiales inchangées et aucune
sélection selon 2026. Même assistant : pas de revue humaine indépendante.

## Complément demandé : dix meilleures AUC historiques

Tri alternatif demandé après les résultats précédents : tous les titres
historiquement qualifiés (2 392 H10 / 1 996 H20), par AUC non chevauchante
2023–2025 décroissante, symbole croissant en cas d'égalité exacte. Ce tri ne
reprend pas le critère initial des bornes de précision LONG. Aucun tri sur2026.
Les CSV `winner_h10-top10-by-historical-auc.csv` et
`parcours_h20-top10-by-historical-auc.csv` sont ajoutés au dossier TOP100 ;
aucune liste modèle ou intersection précédente n'est remplacée.

| Rang | H10 | AUC 2023–2025 | Contrôle 2026 | H20 | AUC 2023–2025 | Contrôle 2026 |
|---|---|---:|---:|---|---:|---:|
| 1 | AG | 0,748 | 0,378 | LAUR | 0,857 | 0,944 |
| 2 | RIGL | 0,713 | 0,667 | PLUG | 0,797 | 0,600 |
| 3 | NXST | 0,709 | 0,400 | TPC | 0,772 | 0,333 |
| 4 | NTB | 0,701 | 0,667 | PLCE | 0,772 | 0,643 |
| 5 | SCHW | 0,700 | 0,386 | AG | 0,763 | 0,500 |
| 6 | HL | 0,693 | 0,111 | WHF | 0,761 | 0,700 |
| 7 | HOMB | 0,689 | 0,614 | CACI | 0,748 | 0,778 |
| 8 | FNKO | 0,687 | 0,532 | L | 0,748 | 0,550 |
| 9 | CBIO | 0,682 | 0,511 | NKTR | 0,737 | 0,650 |
| 10 | ADTN | 0,681 | 0,354 | FLG | 0,734 | 0,600 |

Historique : 75 observations non chevauchantes par titre H10, 37 H20.
Contrôle2026 : 10–19 observations H10, 8–9 H20. Les AUC historiques élevées
ont été sélectionnées parmi des milliers de titres ; elles ne sont pas des
taux de trades gagnants. Les meilleurs H10 ne se maintiennent pas tous en2026.
Plusieurs H20 gardent une AUC élevée, mais huit/neuf observations ne suffisent
pas à démontrer une fiabilité durable. Variante exploratoire supplémentaire,
sans test économique ni promotion en production.

## Complément : AUC historique et AUC2026 toutes deux > 0,60

Filtre demandé sur le TOP100. Pour rendre explicite la différence entre le
TOP100 initial de fiabilité et le classement par AUC demandé ensuite, les
deux variantes sont conservées séparément, sans remplacer les listes précédentes.
Le filtre porte sur les AUC **non chevauchantes**, historique agrégé2023–2025
et contrôle2026, chacune strictement supérieure à0,60. Une AUC exactement0,60
est exclue. Arrondi technique à12décimales pour ne pas admettre0,6000000000000001.

| Origine des100titres | H10 retenus | H20 retenus |
|---|---:|---:|
| TOP100 par AUC historique décroissante | **32** | **37** |
| TOP100 initial par fiabilité LONG | **7** | **20** |

Dossier : `artifacts/research/us_predictable_symbols/20261104-top100-auc060-v1/`.
Les fichiers `{cible}-{historical_auc_top100,original_reliability_top100}-both-auc-gt060.txt`
contiennent les noms séparés par virgules. Les CSV correspondants conservent
les deux AUC, les effectifs et les rangs. `report.json` décrit les règles,
empreintes et exclusions à la borne. Script reproductible :
`scripts/research/us_predictable_symbols_auc_filter_20261104.py`.

Dans la variante par AUC historique, le contrôle2026 porte sur7–19fenêtres
H10 et5–9H20 par titre retenu. Dans la variante initiale :10–19H10 et9H20.
PLUG, dont l'AUC2026 vaut mathématiquement0,60, n'est pas retenu.

**La sélection utilise désormais les résultats de2026** : cette année cesse
d'être une validation pour les noms ainsi retenus. Les bons chiffres de2026
sont une condition de sélection, pas une preuve hors échantillon de cet univers.
Il faut le confirmer sur une période suivante non utilisée pour choisir les noms.
Aucune nouvelle mesure de performance de portefeuille ni modification des
intersections options/consensus ou du trading. Vérification PASS, fichiers
sources inchangés ; zéro réentraînement, appel fournisseur/LLM, écritureSQL ou ordre.
