# Sprint 14-A — Consultation France isolée dans l'IHM et la CLI

5 octobre 2026. GO du propriétaire pour commencer le Sprint 14.
Cette première tranche est implémentée et désormais complétée par le
[14-B : lancement et suivi des replays](sprint_14b_lancement_replay_et_suivi.md).

## Parcours opérateur

Dans Pipeline, Diagnostic ML et Backtesting, sélectionner
« France — recherche uniquement » dans Marché. Le défaut reste US ; le choix
est propre à chaque page, sans changer la connexion active US.

La vue indique FR_EQ, alpha_trade_fr, EUR, XPAR et H5. Elle consulte les
artefacts de recherche existants, pas une table US renommée. Le 14-B ajoute
le lancement d'un replay figé ; aucun entraînement ou serving n'est activé.
Les boutons paper/live et les étapes quotidiennes US sont absents.

Dans Workflow & Orchestration → Batch, sélectionner le périmètre France.
La vue initiale 14-A était un emplacement réservé, sans catalogue prospectif.
Depuis le [Sprint 15-A](sprint_15a_catalogue_et_orchestration.md), elle charge
`batch_fr.yaml` et présente les tâches FR, leurs prérequis et leurs commandes.
Elle ne charge ni n'installe les tâches US/CN. Les collecteurs fournisseur FR
restent désactivés tant qu'ils ne sont pas qualifiés. Le catalogue US/CN
existant demeure inchangé et sélectionné par défaut.

## Campagnes et interprétation

Le catalogue est explicite dans `service/fr/research_catalog_14a.py` :

- Oracle H5 après réparation du fold 7 ;
- direction mutualisée H5 après cette réparation ;
- pilotes antérieurs, identifiés comme archives ;
- robustesse économique 13-D, 96 scénarios exploratoires.

On ne choisit pas automatiquement le dossier le plus récent. Le rapport
sélectionné affiche son chemin, son SHA-256, son verdict, le manifeste et
ses folds. Les fichiers source absents ou incompatibles donnent une erreur,
jamais un remplacement par une campagne US/CN.

Le tableau économique distingue politique, fold, variante, scénario fiscal,
scénario de coûts, PnL EUR, rendement net, Sharpe, drawdown, exposition,
nombre de trades, win rate et commission/spread/slippage/taxes en EUR.
Une valeur inconnue reste absente, elle n'est pas remplacée par zéro.
Le win rate est une fraction : 0,40 signifie 40 %.

Les folds sont des portefeuilles indépendants. Le fold 6 couvre les entrées
du 29 juillet 2024 au 23 janvier 2025 ; le fold 7 du 24 janvier au 23 juillet
2025. Leurs rendements ne doivent pas être additionnés. Une tape peut se
poursuivre après la dernière entrée pour finaliser sorties et cashflows.
La confirmation 2026 n'est pas consultée.

Le NO-GO directionnel/économique et les réserves strictes restent visibles.
La présence de résultats dans l'IHM n'est ni une validation du modèle ni une
autorisation de production. Spread/slippage restent des hypothèses ; les
éligibilités fiscales inconnues restent des scénarios, pas des exonérations.

## CLI de consultation et export

Depuis la racine du projet :

```powershell
python -m service.fr.research_catalog_14a --campaign robustness_13d
python -m service.fr.research_catalog_14a --campaign oracle_h5_repaired
python -m service.fr.research_catalog_14a --campaign direction_h5_repaired
```

La CLI affiche du JSON sans SQL, réseau, entraînement ou écriture d'artefact.
Le bouton IHM télécharge ce diagnostic, avec `FR_EQ_EUR` dans le nom, le
rapport complet, les limites, les sources et les paramètres. Il ne télécharge
pas un modèle servable.

## Implémentation et contrôles

Les trois pages font un retour anticipé sous FR_EQ avant configuration DB,
requête de métriques US et construction de commandes legacy. Le sélecteur
US/CN conserve ses clés, l'ordre des deux choix et le défaut US ; FR est ajouté
en troisième position. Le service FR partagé vérifie les indicateurs
`serving_enabled=false`, `canonical_writes=false`, le contrat FR H5 des
modèles et les limites du replay exploratoire. Pour le replay, le hash du
protocole est vérifié. Ce contrôle n'est **pas** une requalification complète
des prix, des preuves fiscales ou de tous les ledgers.

Tests : `tests/test_fr_research_ui_14a.py` et non-régressions CN/Batch.
45 tests ciblés passent avec `--no-cov` ; la couverture globale de toute
l'application n'est pas évaluée par cette sélection. Smoke de consultation
des cinq rapports réels réussi, sans entraînement ni écriture SQL.

## Validation finale du Sprint 14

Les points suivants de 14-A sont réalisés par le 14-B :

1. Raccorder un lancement FR spécifique et gelé au gestionnaire de processus,
   sans réutiliser le formulaire backtest US.
2. Historique FR séparé avec ID, état, stdout/stderr, échec et arrêt contrôlé.
3. Progression réelle par jalons observés, pas pourcentage temporel inventé.
4. Démonstration de bout en bout d'un petit replay recherche depuis l'IHM,
   puis retrouver et exporter son résultat ; tests US/CN complémentaires.

Les deux lancements du propriétaire sont vérifiés dans le
[bilan final opérateur](sprint_14_bilan_validation_operateur.md). Le périmètre
livré consultation/replay figé de recherche est clôturé, sans activation de
training général, ingestion ou serving depuis la vue France.

Les contraintes des [Sprints 12](TODO_sprint_12_reste_a_faire.md) et
[13](sprint_13_bilan_et_conditions_reprise.md) restent ouvertes. La tranche
14-B est une amélioration opérateur, pas une nouvelle recherche
sur les seuils ni une promotion économique.
