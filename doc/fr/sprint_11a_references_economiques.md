# Sprint 11-A économique — références simples et aptitude au rejeu

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Mise à jour4 octobre2026 : [qualification partielle et scénario de coûts](sprint_12a_couts_taxes_operations_sur_titres.md).
Tarification générique configurée selon le choix utilisateur (1EUR/ordre,
spread complet5bps, slippage5bps) ; taux TTF historiques vérifiés et moteur
décomposé. Assujettissement ISIN et preuves CA/PIT restent ouverts.
Les coûts NULL ci-dessous décrivent le préflight11-A gelé, pas le nouveau
profil de scénario ; aucun ancien rapport n'est écrasé.

## Périmètre et résultat au 4 octobre 2026

Ce sous-projet répond au GO pour comparer ATR TOP20 LONG-only, Oracle TOP20
LONG-only et un contrôle de marché, après le NO-GO directionnel H5 du Sprint10.
Il anticipe une partie des Sprints12/13 économiques. Le Sprint11 du planning
initial concerne **les données événementielles** : il n'est ni supprimé ni
réputé réalisé par ce test. Cette distinction évite de confondre deux objectifs.

**Implémenté et exécuté :** protocole de comparaison, audit d'aptitude,
scoring Oracle de tous les candidats disponibles à la décision et export des
intentions de sélection. **Non exécuté :** transactions, portefeuille, frais,
PnL net, Sharpe ou drawdown. Verdict `BLOCKED_ECONOMIC_REPLAY`.

Rapport :
`artifacts/fr/research/economic_references_11a/preflight-20261004-v2/report.json`.
Le run v1 conserve le diagnostic avant correction des scores incomplets.
Tous les runs restent de recherche, sans écriture SQL, activation live ou
modification des anciens modèles/artefacts. Pas de performance2026 consultée.

## Le problème des scores ML et son traitement

Le pilote Oracle évalue uniquement les lignes dont la cible future est connue
et le chemin futur valide. C'est nécessaire pour calculer précision/AP, mais
ce sous-ensemble ne constitue pas un univers d'achat causal : on ne sait pas
à l'entrée qu'une observation future sera absente ou censurée.

Le préflight reconstruit les candidats à partir du panel de features,
`profile_row_ready` et du minimum de20 titres par séance, **sans lire les
labels**, le rendement futur, `path_state`, la qualification globale d'un
semestre ou les résultats de performance. Il vérifie la disponibilité des
features avant décision. Cela reste l'hypothèse **RESEARCH_J1** ; « sans
filtre futur de label » n'est pas une certification PIT historique.

| Fold / test | Dates | Candidats disponibles | Scores OOF archivés | Manquants |
|---|---|---:|---:|---:|
|6 |2024-07-29 →2025-01-23 |10 209 |10 200 |9 |
|7 |2025-01-24 →2025-07-23 |11 170 |11 127 |43 |

52 lignes sur21 379 n'étaient pas scorées. Elles ne sont pas supprimées.
Les deux modèles arbres gelés sont chargés sans fit et scorent **tous** les
candidats. Les scores existants sont comparés aux nouveaux à tolérance absolue
1e−12 ; une divergence arrête le traitement. Les hashes des modèles sont
conservés et vérifiés avant/après. **21 379 scores, zéro manquant, zéro fit**.

La branche Oracle arbres est fixée, pas choisie sur TEST. Le nouveau score
s'appelle `score_oracle_research`. Aucun calibrateur ni seuil directionnel ajouté.

## Comparaison pré-enregistrée

Configuration : `config/research_fr/economic_references_11a_v1.yaml`.

Uniquement les tests des folds6/7 déjà explorés : comparaison historique, pas
OOS final neuf. Horizon H5 ; entrée prévue à l'ouverture de décision après
disponibilité J+1 ; sortie prévue à la clôture cinq séances XPAR plus tard.
Ni stop, ni TP, ni trailing, ni optimisation du lifecycle. Les prix absents
ne permettront pas un fill inventé ; leur gestion relève du contrat d'exécution.

Intentions avant toute lecture du rendement futur :

1. ATR TOP20 LONG-only : `atr20_pct` décroissant ;
2. Oracle TOP20 LONG-only : score arbres décroissant ;
3. contrôle uniforme LONG-only : permutation déterministe du même univers
   par hash date/UID/seed17, sans tri par future performance.

TOP20 = `ceil(0,20 × nombre de candidats)` ; départage déterministe.
Le contrôle uniforme garde le pool entier avec un ordre de priorité aléatoire
reproductible. Le moteur futur ouvrira uniquement les positions autorisées
par le budget/la capacité. Un pool de candidats **n'est pas** un carnet de fills.

Portefeuille prévu identique :4000EUR,8 positions maximum, exposition brute
≤100 %, LONG-only, sans levier, actions entières, notionnel égal à l'entrée,
pas d'empilement du même symbole ; réentrée au plus tôt la séance suivante
après sortie ; pas de réutilisation d'une vente de clôture pour un achat à
l'ouverture du même jour. Contraintes verrouillées mais pas encore simulées.

### Équipondération et contraintes identiques

Un indice équipondéré de **tout** l'univers ne respecte pas une limite de8
positions physiques. Il sera une référence descriptive distincte, pas un
portefeuille présenté comme ayant les mêmes frais/contraintes. Le contrôle
uniforme limité par la même capacité permettra une comparaison équitable.
Ne pas appeler cet échantillon un indice de marché complet. Aucun rendement
de ces références n'est encore calculé.

## Blocages constatés

Les21 379 barres sources des candidats sont retrouvées dans le nouveau
manifeste hashé. Aucune n'a de flags historiques PIT, corporate action
économique ou rendement économique validés.

| Contrôle | Résultat | Conséquence |
|---|---|---|
| Scores sans sélection sur cible future |Pass après rescoring |Blocage technique levé |
| PIT historique officiel |21 379 sources non qualifiées |Recherche J+1 seulement |
| Opérations sur titres / rendement économique |21 379 sources non qualifiées |Pas de PnL qualifié |
| Commission, spread/slippage FR |`fr_research_pending`, valeurs NULL |Pas de coûts implicitement nuls |
| Taxe instrument/date |Calendrier non qualifié |Pas de taux universel inventé |

« Non qualifié » ne veut pas dire21 379 opérations présentes : les preuves
manquent. Le contrôle des seules barres sources ne valide pas tous les chemins
H5, dividendes, splits, suspensions ou radiations futurs. Les coûts devront être
communs puis stressés ×2. Un scénario hypothétique explicitement défini ne
devient pas un coût réel de courtier ou un GO économique. Le moteur US n'est
pas utilisé avec ses frais Alpaca par défaut pour XPAR.

## Implémentation et sorties

- `service/fr/economic_preflight_11a.py` : contrat, provenance, candidats sans
  filtre de label futur, audit du manifeste, scoring gelé et intentions.
- `modelFactory/fr_economic_references_11a.py` : CLI/orchestration.
- `decision_candidates_scored.parquet` : tous les candidats et scores.
  `oracle_score_missing` décrit l'ancien manque, pas le score recalculé.
- `missing_oracle_scores.parquet` :52 candidats initialement absents.
- `selection_intents.parquet` : classement avec `INTENT_NOT_FILL` et
  `future_label_used=false`.
- `report.json` : hashes, compteurs, contrôles ; PnL/Sharpe/drawdown NULL,
  `trades_executed=0`.

Commande reproductible dans un **nouveau** dossier :

```powershell
python -u -m modelFactory.fr_economic_references_11a --output artifacts/fr/research/economic_references_11a/preflight-nouveau-run
```

Les tests protègent le candidat au futur inconnu, refusent fuite/doublons,
vérifient les scores connus et l'invariance de sélection au rendement futur,
gardent les coûts inconnus bloquants et interdisent performance2026/activation.

## Déblocage nécessaire

1. Formaliser le contrat d'exécution FR prévu au Sprint12 : fills/absences,
   calendrier, actions entières, budget et liquidation.
2. Qualifier dividendes, opérations sur titres et chemins utilisés ; conserver
   explicitement événements inconnus et radiations.
3. Qualifier commissions, spread/slippage et taxes instrument/date.
4. Implémenter le portefeuille commun, exécuter les politiques à règles
   identiques, puis coûts×2 et attribution de concentration.
5. Garder2026 réservée ; ne pas modifier les politiques après résultats pour
   présenter ce test comme confirmation vierge.

11-A ne démontre **aucun gain ou perte net**. Son préflight est réalisé, mais
la comparaison économique demandée reste bloquée. Le GO ne permet pas de
lever arbitrairement les gates ou d'inventer les preuves/coûts manquants.
