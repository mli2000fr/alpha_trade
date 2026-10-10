# Sprint 15-B2 — Éligibilité historique et contrat PIT de financement/prêt

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Suite exécutée : [15-B3 — qualification des blocages](./sprint_15b3_qualification_blocages.md), avec extension aux listes Shenzhen des 40 séances et réconciliation des mêmes mesures détail/résumé. Les constats ci-dessous restent ceux de B2.

Audit exécuté le 28 septembre 2026. **Audit terminé ; qualification PIT stricte non obtenue.** Ce document complète [15-B1](./sprint_15b1_backfill_pilote_margin_lending.md), sans transformer ses archives en données immédiatement utilisables par le ML.

## Objectif et périmètre réellement vérifié

Le financement sur marge (`融资`) et le prêt de titres (`融券`) donnent des mesures d'activité, pas des probabilités de hausse ou de baisse. Avant de tester leur valeur directionnelle, il faut savoir quels titres étaient dans le périmètre, quand l'information était disponible et si les flux se réconcilient avec les encours.

Le service de recherche `service/market/cn_margin_lending_contract_audit.py` :

- télécharge les listes officielles Shenzhen aux **16 dates d'ancrage juin/décembre 2018–2025** du pilote ;
- les rapproche des détails déjà collectés et des actions historiquement cotées du référentiel CN ;
- vérifie les empreintes des bruts 15-B1 avant réutilisation ;
- contrôle les transitions Shanghai des **40 séances de juin**, uniquement entre séances de marché consécutives ;
- conserve un rapport et les cas non réconciliés dans les artefacts de recherche.

Il ne construit **pas encore un calendrier exhaustif quotidien d'éligibilité 2018–2025**. Aucun entraînement, aucune migration, aucun batch planifié et aucune écriture métier en base ne sont effectués. La base `alpha_trade_cn` est consultée en lecture pour le calendrier et le référentiel.

## Shenzhen : rapprochement daté

Source : [liste officielle SZSE](https://www.szse.cn/disclosure/margin/object/index.html), export XLSX `ShowReport`, `CATALOGID=1834_xxpl`, `txtDate=YYYY-MM-DD`, `TABKEY=tab1`. Les fichiers sont conservés avec leur SHA-256.

Quatre indicateurs distincts sont lus et validés comme `Y/N` :

| Indicateur | Sens |
|---|---|
| 融资标的 | Appartenance à la liste des titres de financement |
| 融券标的 | Appartenance à la liste des titres de prêt |
| 当日可融资 | Financement autorisé pour cette journée |
| 当日可融券 | Prêt autorisé pour cette journée |

Appartenance et autorisation du jour ne sont pas interchangeables. Le fichier du 31 décembre 2020 contient un titre dont le prêt est désactivé pour la journée ; les autres fichiers échantillonnés n'ont pas cette désactivation. Ce résultat ne préjuge pas des jours non téléchargés.

| Date | Instruments dans la liste | Instruments dans le détail | Actions éligibles du référentiel présentes dans le détail |
|---|---:|---:|---:|
| 2018-06-29 | 435 | 435 | 425 |
| 2018-12-28 | 438 | 438 | 425 |
| 2019-06-28 | 443 | 443 | 425 |
| 2019-12-31 | 819 | 819 | 800 |
| 2020-06-30 | 818 | 818 | 788 |
| 2020-12-31 | 902 | 902 | 863 |
| 2021-06-30 | 981 | 981 | 936 |
| 2021-12-31 | 1116 | 1116 | 1062 |
| 2022-06-30 | 1185 | 1185 | 1119 |
| 2022-12-30 | 1692 | 1692 | 1612 |
| 2023-06-30 | 1750 | 1750 | 1656 |
| 2023-12-29 | 1831 | 1831 | 1735 |
| 2024-06-28 | 1833 | 1833 | 1724 |
| 2024-12-31 | 1898 | 1898 | 1779 |
| 2025-06-30 | 1953 | 1953 | 1790 |
| 2025-12-31 | 2041 | 2040 | 1826 |

**Couverture des actions éligibles du référentiel : 100 % sur chacun des 16 ancrages.** Aucun code du détail n'est extérieur à la liste éligible correspondante. Cela remplace le mauvais dénominateur « toutes les actions cotées » pour mesurer la complétude du détail ; cela ne prouve ni la complétude de notre référentiel ni celle des séances intermédiaires.

Le seul instrument de la liste sans détail, au 31 décembre 2025, est `159200`, nommé `科创债ETF富国` dans le XLSX officiel : c'est un ETF, hors du périmètre actions de l'application. Son absence reste enregistrée, sans la convertir en valeur zéro. Sa cause n'est pas démontrée.

## Shanghai : éligibilité encore inconnue

La [page officielle SSE des titres de prêt](https://www.sse.com.cn/services/tradingservice/margin/info/againstmargin/) inspectée sert une liste courante datée du 28 septembre 2026. La requête embarquée ne fournit pas de paramètre historique dans le tableau inspecté. **La liste 2026 ne doit jamais être projetée en 2018–2025.**

Il reste à retrouver et dater les listes historiques complètes, ou à reconstruire leurs changements à partir d'annonces officielles avec une chaîne de preuves. Une ligne observée dans le détail reste exploitable comme observation brute ; l'absence d'une ligne Shanghai ne permet pas de trancher entre inéligibilité et donnée manquante.

## Comptabilité : quarantaine, pas réparation

Le contrôle Shanghai compare, sur les mêmes titres présents aux deux séances :

```text
résidu financement = encours J − encours J−1 − achats J + remboursements J
résidu prêt = quantité J − quantité J−1 − ventes prêtées J + restitutions J
```

Sur les **39 808 transitions** du pilote 15-B1 :

- **2 972** résidus de financement dépassent 1 CNY ;
- **378** résidus de prêt dépassent une unité ;
- leur union représente **3 019 transitions**, conservées avec code, dates et deux résidus dans `quarantined_transitions.json`.

Les cas reçoivent `QUARANTINE_UNRECONCILED_TRANSITION`. La quarantaine concerne les features dérivées de ces transitions ; elle ne supprime ni les fichiers bruts ni les observations originales.

La [définition officielle SSE](https://www.sse.com.cn/market/othersdata/margin/sum/) inclut plusieurs composantes dans les remboursements/restitutions. **Ce n'est pas une explication démontrée des résidus** : remplacer un flux publié par une différence d'encours masquerait le problème. Les quatre épisodes concentrés identifiés en 15-B1 restent à expliquer.

Les écarts détail/résumé restent également ouverts. SSE avertit que le résumé peut inclure les encours de titres sortis du périmètre du détail : cela interdit d'imposer artificiellement l'égalité. Le résidu SZSE d'environ 0,95 % au 30 juin 2025 n'est pas expliqué par le rapprochement des listes.

## Contrat de disponibilité conservateur

L'audit produit `research_available_at_proxy` à la **clôture de la deuxième séance ouverte suivant la date du relevé**. C'est un choix de protocole de recherche, pas une heure officielle de publication et pas un `available_at` canonique.

Exemple : un relevé du vendredi, si lundi et mardi sont ouverts, reçoit un proxy mardi à la clôture. Il ne peut servir à une décision mardi matin. Pour une entrée à l'ouverture, la première séance utilisable est la suivante. Le calcul utilise le calendrier CN et ses clôtures UTC, jamais « date + deux jours calendaires ».

Si deux séances futures ne sont pas disponibles dans le calendrier, le proxy reste `null` et le cas est bloqué (`BLOCKED_CALENDAR_END`). C'est le cas du relevé du 31 décembre 2025 dans le calendrier actuellement chargé. Aucune date fictive n'est ajoutée.

La date `audited_at` décrit l'audit effectué aujourd'hui. Elle ne prouve pas une observation historique. Même un retard de deux séances ne neutralise **pas** les corrections ultérieures d'une archive. Le statut reste `PIT_PROXY_NOT_CERTIFIED` et `strict_ml_allowed=false`.

### Vintages et absences

Une future ingestion prospective devra conserver chaque réponse immuable avec son hash, son instant de réception et la source. Un changement de valeur crée un nouveau vintage, pas un remplacement silencieux. Pour une jointure PIT, on choisit exclusivement la version reçue avant la décision.

| État | Traitement |
|---|---|
| OBSERVED | Valeur effectivement présente ; disponibilité à contrôler séparément |
| OBSERVED_ZERO | Zéro réellement publié, et non imputé |
| INELIGIBLE | Absence et inéligibilité établies par une liste datée |
| MISSING_SOURCE | Titre éligible mais ligne absente |
| UNKNOWN_ELIGIBILITY | Absence sans liste historique probante |
| OBSERVED_OUTSIDE_ELIGIBLE_LIST | Observation hors liste : investigation requise, pas effacement |

Un encours résiduel d'un titre retiré nécessitera un état métier dédié, une preuve de retrait et une définition du périmètre fournisseur. L'audit n'invente pas cette classification à partir d'une absence.

## Reproduction et preuves

```powershell
python -u -m service.market.cn_margin_lending_contract_audit
python -m pytest tests/test_cn_margin_lending_contract_audit.py tests/test_cn_margin_lending_pilot.py -q --no-cov
```

Sorties : `artifacts/research/cn_margin_lending/sprint15b2_contract/report.json`, les 16 XLSX d'éligibilité et `quarantined_transitions.json`. Une seconde exécution réutilise les XLSX locaux et reproduit les rapprochements sans écriture en base.

Les tests ciblés vérifient les absences non imputées à zéro, le dénominateur éligible, le retard en séances, les calendriers incomplets et le rejet des indicateurs inconnus. Ils ne valident pas l'ensemble de l'application ni la disponibilité historique des sources.

## Décision et prochaine étape

Verdict exécuté : **NO_GO_STRICT_PIT_UNRESOLVED_SSE_AND_VINTAGES**.

La faisabilité de collecte et le rapprochement Shenzhen progressent ; aucune performance LONG/D1/D10 n'est mesurée. Les critères de sortie initialement envisagés pour 15-B2 ne sont donc pas tous satisfaits.

Prochaine tranche proposée : **15-B3, qualification ciblée des blocages**, avant tout ML :

1. rechercher les listes historiques Shanghai et leurs dates effectives ;
2. expliquer les quatre épisodes de résidus et l'écart de résumé SZSE à partir de sources indépendantes/officielles ;
3. documenter les corrections/vintages et étendre les listes Shenzhen aux séances nécessaires ;
4. seulement ensuite décider d'une expérience explicitement sous proxy, ou rester bloqué pour une expérience PIT stricte.

Ne pas confondre `融券` avec `转融券`, suspendu en juillet 2024 ; prévoir une analyse réglementaire séparée. Un indicateur de prêt ne rend pas les shorts exécutables dans le moteur CN_A actuel.
