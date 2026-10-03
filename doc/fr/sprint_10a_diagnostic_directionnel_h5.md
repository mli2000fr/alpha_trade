# Sprint 10-A — Références directionnelles dans le TOP20 Oracle H5

## Protocole figé avant résultats de ce lot — 3 octobre 2026

Premier diagnostic du Sprint 10, pas un entraînement de modèle directionnel ni la clôture du sprint. H5 prix-only, folds 4/5/6 du Sprint 9-A ; H10/H20 et benchmark restent bloqués en couverture. 2026 demeure réservée. Les périodes de développement ont déjà été inspectées pour l'amplitude : ce n'est pas une confirmation finale indépendante.

L'Oracle 9-A n'a pas franchi son gate d'amélioration contre ATR. Le GO utilisateur pour 10-A autorise uniquement ce diagnostic exploratoire, pas sa promotion en production.

## Population et vérité terrain

Réutiliser les scores **test OOF** du champion choisi sur validation par fold au Sprint 9-A. Une décision n'utilise jamais sa propre cible pour scorer ou sélectionner un titre. Gate quotidien : ceil(20 % de l'univers Oracle), mêmes clés date/UID et départage SHA256 que 9-A. Jointure exacte avec les labels H5 et les features figés ; toute ligne absente, duplicate, hors fold, immature ou feature future bloque le run. Ne pas recalculer les déciles sur le TOP20 : D1/D10 restent ceux de la cross-section de vérité 8-A.

**FR Oracle mesure ici le TOP20 de valeur absolue du rendement terminal. Il n'est pas défini comme l'union D1/D10 US.** Les taux D1/D10 dans le pool ne sont donc ni garantis égaux ni proches de 50 % ; le reste des déciles doit être conservé.

D10 = meilleur décile relatif, pas nécessairement hausse ; D1 = pire décile relatif, pas nécessairement baisse. On mesure séparément l'appartenance aux déciles et le signe/rendement réalisé.

Contrôle de jointure avant toute lecture des performances : 12 déciles test sont `TIE_BOUNDARY` (4 par fold), indéterminés à une frontière de déciles. Ils restent dans le classement Oracle et les statistiques de rendement connu. L'évaluation d'appartenance D1/D10 ignore leur décile inconnu, **sans les convertir en classe négative**. Les effectifs de déciles connus sont affichés pour le pool et chaque sélection LONG/SHORT ; tout autre motif de décile manquant bloque le test. Il n'y a ni imputation ni recalcul des frontières.

## Références sans estimation

Scores fixés : aléatoire reproductible, `return_5`, `return_20`. Aucune sélection a posteriori d'une fenêtre, inversion ou seuil. Les rendements passés sont ceux du panel prix causal, pas les rendements futurs. Le modèle mutualisé et un éventuel ranking appris sont reportés au prochain lot : leur train doit être constitué d'événements Oracle eux-mêmes OOF, avec purge et support suffisant. On ne crée pas artificiellement ce train en scorant in-sample le train Oracle.

Pour chaque score et séance : 20 % du pool les mieux classés = sélection LONG diagnostique ; 20 % les moins bien classés = SHORT diagnostique. Au moins 4 candidats dans le pool, aucun chevauchement de sélections admis. Le départage des égalités utilise l'ordre inverse aux deux extrémités, pour garder des sélections disjointes même lorsque les scores sont constants. Le témoin « Oracle seul » conserve tout le pool : taux D1/D10, moyenne du rendement LONG et opposé pour SHORT. Il n'est pas traité comme un prédicteur de direction.

## Mesures

- AUC D10 contre D1 sur les seules deux queues réelles ; effectifs des deux classes toujours affichés.
- AUC D10 contre reste et D1 contre reste sur tout le pool ; le score SHORT est l'opposé du score de classement.
- IC Spearman quotidien score/rendement futur, nombre de séances calculables.
- Précision D10 LONG et D1 SHORT, prévalences correspondantes dans Oracle seul.
- Rendements bruts moyens sélection LONG et SHORT, proportions de signes favorables et spread LONG−rendement des titres SHORT. Le spread n'est pas une performance de portefeuille financé.
- Quintuples de score : fréquences D1/D10, signe et rendement. **Ce ne sont pas des courbes de calibration de probabilités** : ces scores ne sont pas des probabilités.
- Comptages/concentration par symbole ; outputs quotidiens exploitables pour lecture par semestre. Secteurs, taille et coûts ne sont pas disponibles ici ; aucune neutralisation n'est revendiquée.

Moyennes quotidiennes à poids égal, puis gate à poids égal par fold. Rendements H5 chevauchants et folds expanding : pas de p-value fondée sur l'indépendance quotidienne.

## Gates exploratoires

Support par fold : ≥30 dates et ≥30 D1 et D10 chacun. Sinon `BLOCKED_DIRECTION_SUPPORT` et pas de NO_GO scientifique.

Pour une référence fixée : AUC moyenne des folds ≥0,53 ; IC quotidien moyen ≥0,03 ; spread quotidien moyen ≥0,002 (0,20 point de rendement brut) ; au moins deux folds avec AUC>0,50, IC>0, spread>0. Tous requis pour `HEURISTIC_SIGNAL_REQUIRES_CONFIRMATION`, sinon `NO_GO_FROZEN_REFERENCE`. Aucun classement du « meilleur » sur test, aucun seuil de trading sélectionné. Un NO_GO de ces heuristiques ne rejette pas toute formulation supervisée FR.

## Utilisation, sorties et limites

`python -u -m modelFactory.fr_direction_h5_audit`

Configuration `config/research_fr/direction_h5_audit_v1.yaml`. Fichiers uniquement sous `artifacts/fr/research/direction_h5_audit/fr-direction-h5-<fingerprint>/`. Aucun SQL ni API fournisseur, aucun changement US/CN, IHM, batch, live ou serving. Le répertoire existant est préservé et une relance identique refusée.

`protocol.json` précède l'évaluation ; `oracle_pool.parquet` conserve les clés/labels/scores pour audit ; `daily_direction_metrics.parquet` les références par jour/fold/score ; `score_quintiles.parquet` les bandes descriptives ; `report.json` les résultats, gates et hashes de sources.

Réserves héritées : disponibilité J+1 de recherche, dividendes non réconciliés en rendement total, revue documentaire incomplète, radiés peu représentés, sélection sur labels matures du pilote d'amplitude. Aucun rendement n'est un PnL net commission/spread/fiscalité/slippage, et SHORT reste un diagnostic sans preuve de prêt ni route courtier FR.

## Résultats

Run final du 3 octobre 2026 : `artifacts/fr/research/direction_h5_audit/fr-direction-h5-fc987f322107/`. **5 362 candidats**, 339 séances utilisables, 75 UID distincts. SHA-256 du pool : `93294914df54f79cb3e221122681feda4d9854691d439770d3f5e11b28ff3ca8`. Aucun modèle entraîné. Le premier essai a été arrêté avant évaluation par le contrôle strict des déciles inconnus ; les 12 cas `TIE_BOUNDARY` ont ensuite été explicitement pris en charge, sans imputation ni exclusion du classement, avant le premier résultat de performance. Le premier run réussi `735a5bb58951` est préservé ; la relance après normalisation mécanique du code reproduit exactement les mêmes métriques et hash du pool.

### Support réellement évalué

| Fold | Séances | Candidats Oracle | D1 | D10 | Déciles inconnus dans le pool |
|---|---:|---:|---:|---:|---:|
| 4 | 104 | 1 494 | 321 | 296 | 1 |
| 5 | 109 | 1 777 | 315 | 372 | 0 |
| 6 | 126 | 2 091 | 429 | 406 | 1 |

Tous les folds passent les gates de support directionnel. Les déciles intermédiaires représentent le reste du pool : ne pas jeter ces candidats ou prétendre que l'Oracle les a tous classés D1/D10. Les 12 inconnus dans le test complet deviennent seulement deux inconnus dans les pools sélectionnés.

### Références fixées — moyennes à poids égal par fold

| Score directionnel | AUC D10/D1 | IC quotidien | Spread brut H5 | Folds AUC>0,50 / IC>0 / spread>0 | Verdict |
|---|---:|---:|---:|---:|---|
| Aléatoire | 0,4838 | −0,0039 | +0,333 % | 1/3 | NO_GO_FROZEN_REFERENCE |
| Rendement passé 5 jours | 0,4887 | −0,0126 | +0,323 % | 1/3 | NO_GO_FROZEN_REFERENCE |
| Rendement passé 20 jours | 0,5194 | +0,0712 | +1,646 % | 3/3 | NO_GO_FROZEN_REFERENCE |

Le momentum 20 jours franchit les gates IC/spread/stabilité par fold mais **pas l'AUC moyenne minimale 0,53**. Ce n'est donc pas un GO. Le spread positif de l'aléatoire rappelle qu'un rendement brut moyen seul est trompeur : taille des sous-groupes, distributions asymétriques, événements extrêmes et horizons chevauchants peuvent produire ce résultat sans capacité directionnelle.

### Détail momentum 20 jours, sans sélection a posteriori d'une autre règle

| Fold | AUC D10/D1 | IC | Rendement LONG sélectionné | Rendement SHORT diagnostique | Spread |
|---|---:|---:|---:|---:|---:|
| 4 | 0,5085 | +0,1312 | +1,694 % | +1,819 % | +3,513 % |
| 5 | 0,5253 | +0,0350 | −0,473 % | +0,695 % | +0,222 % |
| 6 | 0,5245 | +0,0474 | +0,156 % | +1,047 % | +1,203 % |

SHORT = opposé du rendement des titres sélectionnés en bas, sans frais, prêt, financement ou fill. Une contribution SHORT positive ne garantit pas qu'une vente à découvert soit réalisable en France.

| Fold | D10 dans Oracle seul | D10 sélection LONG | D1 dans Oracle seul | D1 sélection SHORT |
|---|---:|---:|---:|---:|
| 4 | 20,24 % | 29,65 % | 22,09 % | 30,69 % |
| 5 | 21,08 % | 21,94 % | 17,49 % | 20,18 % |
| 6 | 19,39 % | 24,47 % | 20,52 % | 21,36 % |

Les précisions sont moyennées par séance, avec les seuls déciles connus dans leur dénominateur ; elles ne sont pas des probas calibrées. Le fold 5 illustre le risque : D10 relatif un peu mieux capturé, mais LONG sélectionné encore perdant.

### Stabilité temporelle et conclusion

Momentum 20 jours : IC moyen +0,1234 en 2023H2, +0,0616 en 2024H1, +0,0522 en 2024H2 ; la tranche partielle de janvier 2025 devient −0,0887 avec spread −0,952 %. Cette dernière tranche est courte, pas un semestre complet. Pas de validation robuste de généralisation, aucune lecture des rendements 2026.

**Sprint 10-A terminé : références et support établis, pas de direction FR exploitable démontrée.** Le signal faible de momentum 20 jours constitue une référence à battre dans un éventuel 10-B, pas une nouvelle règle à déployer. Un 10-B supervisé nécessitera d'abord des scores Oracle OOF disponibles sur son historique d'entraînement (les trois blocs test 9-A ne constituent pas un train directionnel long et indépendant). Pré-enregistrer un petit modèle mutualisé et son découpage chronologique avant tout fit ; si le support est insuffisant, produire `BLOCKED` plutôt que réutiliser des scores Oracle in-sample. H10/H20 restent bloqués.

Sept nouveaux tests ciblés vérifient sélection sans cible, invariance d'ordre, égalités disjointes, déciles inconnus non négatifs, distinction décile/signe, scores/clés invalides et distinction support bloqué/rejet scientifique. **85 tests ciblés FR passent** sur univers/features/labels/Oracle/direction ; Ruff passe pour les deux nouveaux fichiers Python. Ce n'est pas l'ensemble des tests de l'application. Le contrôle de conformité Oracle vérifie le champion VAL et l'effectif test de chaque fold. Ce module est exclusivement hors ligne et ne fait aucune écriture SQL ni activation de serving.
