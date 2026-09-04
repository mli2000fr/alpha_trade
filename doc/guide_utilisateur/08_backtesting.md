# Page Backtesting — fidélité, diagnostics et campagnes

## Positionnement

La page est un centre opérateur autour de plusieurs commandes du package
`backtesting`. Elle lance les processus en arrière-plan, conserve registre,
logs et artefacts, et partage un verrou avec le pipeline. Elle ne remplace pas
le protocole scientifique : l’utilisateur reste responsable du caractère PIT,
du contrat testé et de la séparation exploration/validation.

## Les neuf familles de travaux

| Onglet | Finalité |
|---|---|
| Backtest | simuler la stratégie complète |
| Backfill PIT | construire/compléter `stock_scores_history` |
| Diagnose screener | mesurer la qualité historique du screener |
| Recommend screener | produire des recommandations à partir du diagnostic |
| Calibrate sentiment | estimer les poids de sentiment |
| Walk-forward sentiment | évaluer ces poids dans le temps |
| Calibrate conviction | calibrer quant/ML et éventuellement Kelly |
| Walk-forward conviction | valider la conviction hors échantillon |
| analyse périodique | consolider les résultats selon la période exposée |

Chaque famille a son type de run. Un seul run actif d’un même type peut être
autorisé et le verrou global peut interdire toute campagne pendant un pipeline.

## Préconditions PIT

Un backtest fidèle doit résoudre à chaque date : univers tradable historique,
scores disponibles, prédictions dont `available_at` est admissible, paramètres
et positions. Les diagnostics de couverture exposés par l’IHM vérifient
notamment `stock_scores_history` et `model_predictions`.

Une couverture insuffisante ne doit pas être compensée silencieusement par les
données courantes. Les options de fallback ont un sens expérimental précis et
doivent apparaître dans le rapport.

## Configurer un backtest complet

### Période et capital

La date de début est obligatoire. Relire fin, calendrier, capital/preset,
contraintes de portefeuille et profondeur disponible. Les résultats absolus ne
sont comparables que si capital, fractionnement et coûts sont cohérents.

### Données, screener et ML

Le mode pipeline consomme les snapshots historisés. Si ML est actif, sélectionner
une campagne terminée compatible. Le batch Global Ranking/cascade et le batch
Oracle peuvent être sélectionnés distinctement. Une campagne Oracle-only ne
constitue pas nécessairement un batch exploitable par le ranking principal.

La page détecte une campagne manquante et peut désactiver le lancement. Même si
le bouton est disponible, contrôler la couverture effective sur toute la
période.

#### Ablation « macro entièrement absente »

La case **Simuler la macro entièrement absente (diagnostic)** ignore le provider
macro pour le run courant sans modifier les tables ni les fichiers sources. Le
bridge de risque reçoit alors la même absence de données que lors d'une panne
réelle, active automatiquement le fallback neutre et marque chaque séance
`data_quality=missing`. La commande correspondante contient
`--force-macro-missing` et
`--allow-neutral-fallback-on-missing-macro-data`.

Cette option est réservée aux comparaisons contrôlées. Elle ne supprime pas les
features macro déjà incorporées dans des prédictions ML persistées : elle isole
la couche macro du régime appliquée pendant le backtest. Elle doit rester
désactivée pour un run OOS normal disposant de sa macro PIT.

### Contrat de stratégie et d’exécution

Les paramètres de sélection, stop, TP, trailing, drawdown, exposition secteur,
gap d’entrée, volatilité cible et filtres doivent être enregistrés comme un
contrat. Certains défauts viennent des presets/configurations ; l’IHM peut
surclasser ces valeurs. Le rapport du run, et non le seul `config.yaml`, fait foi
pour ce qui a été testé.

Le filtre Persistent Rank DIP possède ses paramètres backtest propres :
activation, horizon de rang, seuil, persistance, dip, reclaim et attente. Ne pas
supposer qu’ils sont identiques au live.

## Lancement et centre de runs

Le lancement construit une commande explicite et crée un répertoire sous les
artefacts IHM. Le centre fusionne runs actifs et historique, suit les processus,
permet arrêt, inspection/téléchargement des logs et suppression ciblée.

Une fin de processus réussie signifie que la commande a retourné sans erreur ;
vérifier ensuite rapport, nombre de trades, couverture, tickets filtrés,
paramètres et éventuels avertissements.

## Lire les résultats

Au-delà du rendement : drawdown, distribution temporelle, nombre de trades,
turnover, exposition, coûts, stabilité par sous-période, concentration et
sensibilité aux gros gagnants. Relier les tickets filtrés/boostés aux règles qui
les produisent. Une amélioration de métrique globale peut venir d’une période ou
d’un petit groupe de titres.

## Diagnostic et calibration

Une calibration choisit des paramètres ; un walk-forward teste leur capacité à
se transporter. Ne pas appliquer directement le meilleur in-sample. Le Kelly
est particulièrement sensible à l’estimation du taux de gain et du payoff :
utiliser les plafonds et règles de risque, même lorsque le backtest brut suggère
une taille supérieure.

Les pages Calibrations poids et Diagnostic ML donnent ensuite une vue détaillée
des runs, timelines, tables et métriques par split/horizon/régime.

## Règles de promotion

1. hypothèse et métrique fixées avant la validation ;
2. contrat PROD clairement distingué du contrat de recherche ;
3. données PIT et couverture documentées ;
4. résultat stable sur plusieurs fenêtres/seeds lorsque pertinent ;
5. coûts et contraintes réalistes ;
6. comparaison à une baseline gelée ;
7. parité/replay avant mise en production ;
8. rollback préparé.

Voir [Backtesting](../12_backtesting_validation.md), [validation PIT](../backtesting/validation_statistique.md),
[anti-overfitting](../ml/validation_et_gouvernance.md) et les
[synthèses d’expériences](../experiences/README.md).
