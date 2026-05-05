# Roadmap détaillée par sprint — Backtest vs Live

Date: 2026-05-04

## Hypothèse de planning

Roadmap proposée sur **6 sprints de 2 semaines**.

Objectif global : faire évoluer le backtest depuis un replay daily instrumenté vers un mode **pipeline-fidèle mesurable**, tout en conservant :

- un chemin `research` rapide ;
- zéro régression sur le pipeline live ;
- des activations explicites et testables.

---

## Vision cible

À la fin de cette roadmap, on veut pouvoir dire :

1. le backtest sait expliquer **ce qu’il relit** vs **ce qu’il recalcule** ;
2. les écarts au live sont **mesurés** et non seulement décrits ;
3. l’exécution simulée est plus proche des sémantiques broker réelles ;
4. quelques fenêtres de référence sont rejouables comme un **digital twin partiel**.

---

# Sprint 1 — Cadrer le replay PIT et la traçabilité

## Objectif

Rendre explicite, pour chaque run pipeline-fidèle, la provenance des entrées critiques utilisées par le backtest.

## Problème visé

Aujourd’hui, le backtest est PIT-aware, mais il n’expose pas encore de façon suffisamment fine :

- ce qui vient de données déjà persistées ;
- ce qui a été reconstruit ;
- ce qui est manquant ;
- et où se situent exactement les zones d’écart au live.

## Périmètre

- `backtesting/fidelity.py`
- `backtesting/data_loader.py`
- `backtesting/cli/_impl.py`
- `backtesting/report.py`
- `backtesting/report_schema.py`
- `backtesting/report_schema_pydantic.py`

## Livrables

- schéma détaillé du **manifest de replay par séance** ;
- matrice de provenance des étapes live 1→10 ;
- journal structuré : relu / reconstruit / fallback / absent ;
- bloc enrichi dans `report.json`.

## Tâches

- formaliser un objet “session replay provenance” ;
- ajouter une granularité par composant : bars, scores, sentiment, ML, walk-forward ;
- expliciter les dégradations dans les artefacts ;
- préparer les champs nécessaires aux sprints suivants.

## Critères d’acceptation

- un run `--engine-mode pipeline` expose clairement la provenance de chaque input critique ;
- aucun fallback important n’est silencieux ;
- le rapport permet déjà d’identifier les principaux trous de fidélité.

## Risques / dépendances

- disponibilité réelle de `stock_scores_history` ;
- présence ou non de `model_predictions` PIT cohérents ;
- granularité parfois insuffisante des artefacts amont existants.

---

# Sprint 2 — Rejouer davantage la chaîne amont 1→5

## Objectif

Réduire l’écart entre :

- un backtest qui consomme des données persistées ;
- et un pipeline live qui exécute réellement les briques amont.

## Périmètre

- `dataIntegrityEngine/*` (lecture des sorties utiles)
- `screener/*`
- `selector/*`
- `event_sentiment/*`
- nouveau service cible : `backtesting/pipeline_replay.py`

## Livrables

- design d’un orchestrateur de replay PIT par séance ;
- contrat séance par séance pour :
  - universe
  - screener
  - selector
  - sentiment
- artefacts intermédiaires datés J ;
- diagnostics d’écart entre snapshots persistés et recalculs.

## Tâches

- définir ce qui peut être rejoué proprement à date J ;
- produire des artefacts intermédiaires par séance ;
- supporter une fenêtre courte de replay (ex. 5 à 20 séances) ;
- journaliser les composants non rejouables proprement.

## Critères d’acceptation

- sur une fenêtre courte, le système sait produire des snapshots amont par date ;
- on peut comparer `persisté` vs `rejoué` pour les candidats/scores avant risk ;
- les écarts sont attribués par composant.

## Risques / dépendances

- trous historiques dans certaines features ;
- dépendances implicites dans la chaîne sentiment ;
- coût de calcul si on rejoue trop large trop tôt.

---

# Sprint 3 — Rejouer l’amont 6→10 jusqu’aux targets risk

## Objectif

Faire converger la chaîne **conviction + risk** pour que les targets backtest soient comparables aux targets live sur fenêtre gelée.

## Périmètre

- `core/conviction.py`
- `backtesting/signal_replay.py`
- `backtesting/risk_bridge.py`
- `risk_management/db_io.py`
- `risk_management/portfolio_builder.py`
- artefacts `modelFactory/*`

## Livrables

- convention unique de fusion conviction backtest/live ;
- contrat `candidate -> target` rejouable ;
- matrice d’écart :
  - candidats
  - conviction
  - poids
  - tailles
  - contraintes
- premier rapport d’écart centré sur les targets risk.

## Tâches

- stabiliser la source de score et la fusion de conviction ;
- aligner la lecture des candidats PIT ;
- comparer les targets produites avec celles du chemin live quand disponibles ;
- instrumenter les motifs de rejet / caps / sizing.

## Critères d’acceptation

- sur des fenêtres de référence, les différences de targets sont mesurables ;
- on sait dire si la divergence vient de la donnée, de la conviction ou du risk ;
- les outputs sont exploitables par un futur `compare-to-live`.

## Risques / dépendances

- leakage ML si la stratégie PIT n’est pas bien bornée ;
- divergence de config entre preset capital, walk-forward et risk ;
- difficulté à aligner exactement l’état compte live historique.

---

# Sprint 4 — Rendre l’exécution plus broker-like

## Objectif

Passer d’un backtest “execution-aware” à une simulation d’exécution beaucoup plus proche des états d’un broker réel.

## Périmètre

- `backtesting/execution_replay.py`
- `backtesting/execution_lifecycle_replay.py`
- `backtesting/protection_watcher_replay.py`
- `backtesting/exit_lifecycle_replay.py`
- `execution_engine/executor.py`
- `execution_engine/reconciliation.py`
- `execution_engine/order_intents.py`
- nouveau composant cible : adapter/repository broker-like simulé

## Livrables

- modèle d’état des ordres simulés :
  - new
  - acknowledged
  - partial
  - filled
  - canceled
  - rejected
- règles de partial fills / retries / cancel ;
- simulation plus riche de l’état compte dans la boucle PnL ;
- extension des artefacts execution pour refléter ce lifecycle.

## Tâches

- définir le contrat d’un adapter broker-like de simulation ;
- intégrer une notion de fills partiels ;
- rapprocher la réconciliation simulée du schéma live ;
- rendre le watcher/exits compatibles avec ces nouveaux états.

## Critères d’acceptation

- un ordre rejoué peut suivre un lifecycle proche du live ;
- les exits/protections/OCO restent cohérents avec les nouveaux états ;
- le rapport explique mieux la divergence d’exécution.

## Risques / dépendances

- manque de données intraday réelles ;
- complexité de calibration des partial fills ;
- risque de sur-ingénierie si l’on veut simuler trop finement trop tôt.

---

# Sprint 5 — Construire le mode `compare-to-live`

## Objectif

Mesurer la dérive réelle entre un run backtest et un run live comparable.

## Périmètre

- `backtesting/report.py`
- `backtesting/report_schema.py`
- `backtesting/report_schema_pydantic.py`
- `database/run_business_summaries.py`
- données persistées `risk_management` / `execution_engine`
- nouveau rapport cible : `fidelity_compare_report`

## Livrables

- comparateur structuré par niveau :
  - candidats
  - targets
  - ordres
  - fills
  - exits
  - PnL
- attribution des écarts par composant ;
- score global de confiance / fidélité ;
- export JSON/Markdown lisible par l’IHM.

## Tâches

- définir les clés de matching entre runs live et backtest ;
- construire les premières métriques d’écart ;
- produire une synthèse courte + une version détaillée ;
- préparer une visualisation IHM simple.

## Critères d’acceptation

- pour une fenêtre où un run live existe, le système sort un rapport unique d’écart ;
- les top divergences sont attribuées et ordonnées ;
- le rapport est lisible sans investigation manuelle dans la DB.

## Risques / dépendances

- difficulté de matching exact des runs ;
- granularité variable des logs historiques ;
- trous éventuels dans les snapshots live anciens.

---

# Sprint 6 — Digital twin partiel et non-régression de fidélité

## Objectif

Figer quelques fenêtres de référence et empêcher que la fidélité recule sans alerte.

## Périmètre

- `tests/*`
- `prompt/backtest/*`
- futurs snapshots de référence
- nouvelles suites de non-régression fidelity

## Livrables

- 3 à 5 fenêtres de référence rejouables :
  - bull
  - volatile
  - small caps
  - cash account
  - margin account
- seuils de divergence acceptables ;
- suite de tests de non-régression fidelity ;
- procédure de promotion d’une nouvelle baseline.

## Tâches

- figer des snapshots complets (données + scores + targets + events) ;
- écrire des tests de divergence max acceptable ;
- documenter la procédure de mise à jour des références ;
- intégrer ces contrôles dans la routine de validation projet.

## Critères d’acceptation

- chaque fenêtre se rejoue de manière stable ;
- les écarts critiques sont bornés ;
- une régression de fidélité devient détectable automatiquement.

## Risques / dépendances

- maintenance des snapshots ;
- volume des artefacts ;
- arbitrage entre stabilité de baseline et évolution fonctionnelle.

---

## Recommandations de pilotage

## Ordre conseillé

1. Sprint 1
2. Sprint 2
3. Sprint 3
4. Sprint 4
5. Sprint 5
6. Sprint 6

## Pourquoi cet ordre

- il faut d’abord savoir **ce qu’on relit / reconstruit** ;
- ensuite rapprocher l’amont ;
- puis stabiliser le risque ;
- puis raffiner l’exécution ;
- ensuite seulement mesurer proprement l’écart ;
- enfin figer des fenêtres de référence.

---

## Version courte pour arbitrage produit

### Si je veux maximiser la valeur rapidement

Faire d’abord :

- Sprint 1
- Sprint 3
- Sprint 5

### Si je veux maximiser la fidélité execution

Faire d’abord :

- Sprint 1
- Sprint 4
- Sprint 5

### Si je veux industrialiser la non-régression

Faire d’abord :

- Sprint 1
- Sprint 5
- Sprint 6

---

## Conclusion

Cette roadmap transforme le plan d’action initial en une trajectoire exécutable par sprint.

La logique directrice reste :

- **mieux tracer** ;
- **mieux rejouer** ;
- **mieux comparer** ;
- **mieux verrouiller**.

Autrement dit : on passe progressivement d’un backtest enrichi à un **système de fidélité mesurable vis-à-vis du live**.

