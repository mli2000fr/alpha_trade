# Batch US — Pipeline quotidien configurable 1 à 12

## Périmètre

`us_pipeline`, déclaré dans `batch.yaml`, enchaîne les étapes sélectionnées dans
`config.yaml → us_pipeline.steps`, dans le même moteur de workflow que la page
Pipeline. Le défaut reste **1 à 9** ; les étapes 10–12 ne sont pas activées par
le renommage. T1 (entraînement), 13 et 14 sont toujours exclus.

```yaml
us_pipeline:
  steps: [1, 2, 3, 4, 5, 6, 7, 8, 9]
  execution_mode: paper
  account_id: default
```

Pour sélectionner toutes les étapes, ajouter `10, 11, 12` à cette liste.
La liste doit être non vide, contenir des entiers uniques entre 1 et 12 ;
l'exécution suit toujours l'ordre numérique, même si la liste est désordonnée.
Une étape omise n'est pas ajoutée automatiquement : ses prérequis doivent
être disponibles. Une configuration invalide bloque avant le workflow.

**Sécurité :** le mode LIVE est refusé pour ce batch. `execution_mode` accepte
uniquement `simulate` ou `paper` ; la configuration actuelle choisit `paper`.
Si ce champ est absent, le fallback de compatibilité est `simulate`.
`account_id` désigne le compte Alpaca transmis au risque et à l'exécution
(fallback `default`). Pour les étapes 11 ou 12 en PAPER, le registre local est
relu et le compte doit être configuré en `paper` ; compte inconnu, credentials
manquantes ou compte réel bloquent avant le workflow. Aucun appel au courtier
n'est nécessaire pour cette vérification. Aucun ordre n'est lancé si 12 est omis.
La sélection des étapes ne constitue pas un changement de mode d'exécution.
Le filtre GPT n'est pas implicitement
activé par la checkbox par défaut de l'IHM : les options fraîches du batch
restent indépendantes de l'état d'une session interactive.

| Étape | Traitement |
|---|---|
| 1 | Import des barres et rattrapage, selon le fournisseur configuré dans l'application |
| 2 | Nettoyage quotidien des données |
| 3 | Stock Screener |
| 4 | Synchronisation des quotes |
| 5 | Calendrier des résultats |
| 6 | Publication de l'univers tradable |
| 7 | Alpha Scanner |
| 8 | Pipeline news/sentiment : import, pertinence, scoring standard/contextuel et agrégation des features |
| 9 | Agrégation des signaux |
| 10 | Prédiction ML, optionnelle |
| 11 | Risk Management, optionnel |
| 12 | Exécution, optionnelle ; mode `simulate` ou `paper` de config.yaml |

Un échec interrompt l'enchaînement : les étapes suivantes ne sont pas lancées. Les écritures des étapes déjà réussies ne sont pas annulées. La reprise reste celle des traitements concernés ; ce batch n'ajoute pas de reprise automatique à partir d'une étape arbitraire.

## Horaire et séance

- Heure principale : **22:45 Europe/Paris**, du lundi au vendredi.
- Le service vérifie le calendrier US strict, sans supposer qu'un lundi–vendredi est forcément négociable. Un jour férié US est ignoré.
- La séance doit être clôturée. 22:45 Paris est postérieure à la clôture régulière US, y compris pendant les semaines de décalage entre les changements d'heure européens et américains.
- La date de séance New York est figée au début du traitement, même si le workflow passe minuit à Paris.
- Le rabattement automatique vers un ancien snapshot est désactivé pour ce batch quotidien. C'est la seule adaptation volontaire par rapport à cette option de la page interactive.
- Aucun second passage n'est ajouté. Les modalités Windows existantes (session utilisateur, démarrage différé, limite de durée) restent celles de l'installeur commun.

Un lancement manuel avant la clôture ou un jour non négociable est également ignoré par ce service. `-Force` contourne l'horaire du launcher, pas la validation de séance.

## Valeurs par défaut partagées avec l'IHM

La fonction `pipeline_page_default_options(trade_date=...)` de `ihm/services/pipeline_runner.py` construit les options à partir des valeurs par défaut communes, du preset **capital_2001_5000** et des défauts sentiment partagés avec la page Pipeline. Le générateur de commandes est le même que celui de l'IHM.

Cela désigne une page fraîche, et non les modifications temporaires conservées dans une session Streamlit : cocher un autre univers dans sa session ne reconfigure pas implicitement le batch Windows. Les paramètres de screener/sélection du preset sont repris. Les exceptions d'exploitation et d'univers autorisées sont décrites ci-dessous ; les réglages interactifs restent inchangés.

### Univers commun et collectes intégrées — évolution du 7 octobre 2026

`us_pipeline.symbols_file` désigne **config/univers_batch/univers_filtred_tradable.txt**. Le batch le transmet aux étapes capables de recevoir ce choix :

| Étape | Application du fichier |
|---|---|
| 3 — Screener | `--custom-universe-file`, prioritaire sur l'univers du screener dans config.yaml |
| 4 — Quotes | `--symbol-source universe-file:config/univers_batch/univers_filtred_tradable.txt` ; fenêtre J−7/J, lot 200 |
| 5 — Earnings | Même source ; Finnhub, J−7/J+30, lot 50, reprise activée |
| 8 — News/sentiment | Import brut, pertinence, scoring standard/contextuel et features ticker sur ce fichier |
| 10 — Prédiction | Même fichier commun via `--symbol-source` si cette étape est sélectionnée |

L'import de barres (1) et le nettoyage (2) ne reçoivent pas de nouveau paramètre d'univers par ce raccordement. La publication (6), la sélection (7) et l'agrégation (9) conservent leurs périmètres dérivés/natifs. Les features secteur du traitement sentiment conservent leur agrégation historique par fournisseur : ce changement ne purge ni ne restreint rétroactivement l'historique déjà importé.

Les fenêtres quotes/earnings sont calculées depuis la séance J figée, pas depuis une horloge qui pourrait passer minuit au milieu du workflow. Les blocs `quotes_collection` et `earnings_collection` dans batch.yaml portent leurs réglages ; le fichier commun est prioritaire. Des ancres YAML partagent les valeurs avec les anciennes sections autonomes.

Les sections `latest_quotes_sync` et `earnings_calendar_sync` restent visibles mais
sont **désactivées**, avec le statut `INTEGRATED_IN_US_PIPELINE`. Si les étapes 4
ou 5 sont retirées de la liste, ces collectes ne seront plus exécutées par le
pipeline ; leurs anciennes planifications ne sont pas réactivées automatiquement.
Ne pas réactiver les anciennes planifications en parallèle.

Les collecteurs CLI restent utilisables manuellement en cas de besoin :

```powershell
python -u -m dataIntegrityEngine.sync_latest_quotes --symbol-source universe-file:config/univers_batch/univers_filtred_tradable.txt --batch-size 200 --from-date YYYY-MM-DD --to-date YYYY-MM-DD
python -u -m dataIntegrityEngine.sync_earnings_calendar --symbol-source universe-file:config/univers_batch/univers_filtred_tradable.txt --batch-size 50 --sleep-seconds 1.1 --log-every 25 --from-date YYYY-MM-DD --to-date YYYY-MM-DD --resume
```

Remplacer les dates avant lancement. Le launcher quotes respecte `enabled: false`, même avec `-Force` ; utiliser directement son collecteur pour une intervention manuelle. Le launcher historique earnings ignore la planification désactivée, mais conserve son lancement manuel explicite `-Force`, hors blocage juridique. Le batch Pipeline ne contourne aucun statut fournisseur bloqué.

Le sentiment utilise notamment le scoring standard + contextuel, les checkpoints de reprise et les valeurs partagées de taille de lots. Les poids de l'agrégateur restent ceux des défauts Pipeline ; activer la collecte/scoring ne signifie pas augmenter automatiquement le poids du sentiment dans la sélection.

Le plan exact (date, options, numéros sélectionnés et commandes) est archivé avant exécution :

`artifacts/operations/us_pipeline/<run_id>/plan.json`

Seules les commandes des étapes sélectionnées sont exécutées. La configuration
est relue à chaque lancement puis le plan est figé pour la durée du run.

## Installation et utilisation

Dans **Workflow & Orchestration → Batch → US**, chercher `us_pipeline`, puis **Installer / réinstaller**. La section est activée dans `batch.yaml`, mais sa présence dans le fichier ne crée pas automatiquement la tâche Windows.

Après le renommage, **réinstaller** pour remplacer l'ancienne tâche
`AlphaTrade-UsPipeline19` par `AlphaTrade-UsPipeline`. L'installeur ne retire
l'ancienne tâche que si elle appartient à ce workspace et n'est pas en cours.
Les anciens logs, artefacts et lignes SQL d'historique ne sont pas renommés :
ils conservent leur provenance. Aucun changement de tâche Windows n'est effectué
simplement en éditant les fichiers du projet.

Installation en ligne de commande, depuis la racine du projet :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_forward_pit_task.ps1 -BatchName us_pipeline
```

Vérification sans exécuter les étapes, sans écrire en base ni créer de workflow :

```powershell
python -u -m service.forward_pit.batch --batch us_pipeline --dry-run
```

Exécution immédiate réelle, après clôture d'une séance US :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\forward_pit_launcher.ps1 -BatchName us_pipeline -Force
```

Le batch nécessite les mêmes accès fournisseurs, tables et dépendances que les
traitements sélectionnés. Il exige `US_EQ` et la base `alpha_trade` ; une
connexion CN/FR est refusée. Aucune nouvelle table ni migration n'est nécessaire.

## Suivi, concurrence et notifications

Le workflow utilise le registre et le verrou partagés avec l'IHM : il ne contourne pas un pipeline déjà actif. Son identifiant est enregistré dans le détail du run du batch. Les journaux et l'avancement des étapes restent consultables via le registre Pipeline, et le résumé apparaît dans la page Batch.

Journal du launcher : `log/batch/us_pipeline.txt`. Le détail du run conserve également le chemin du journal du workflow et, en cas d'échec d'une étape, son identifiant et son code retour.

Les notifications email et Telegram passent par le launcher commun, avec statut et message d'erreur. **L'unité des compteurs de ce batch est l'étape**, pas le nombre de lignes SQL :

- demandés : nombre d'étapes sélectionnées (9 par défaut, 12 au maximum) ;
- reçus / persistés : nombre d'étapes terminées avec succès ;
- échecs : 1 si le workflow ne peut pas commencer ou s'interrompt ;
- alertes : avertissements du résumé du batch, pas une addition implicite des avertissements de chaque sous-traitement.

Les notifications propres aux sous-traitements et au workflow existant peuvent s'ajouter à celle du batch. Pour suspendre la planification, désactiver la section et/ou désinstaller sa tâche depuis la page Batch ; les historiques sont conservés.

## Vérification de l'évolution du 9 octobre 2026

156 tests ciblés réussis : pipeline US, handlers Forward PIT, configuration et
catalogue IHM. Couverture des sélections invalides, ordre numérique, plans 12
étapes sans lancement réel, compteurs partiels/12 étapes, relecture à chaque
lancement, interdiction LIVE et protections de migration Windows. Syntaxe
PowerShell de l'installeur vérifiée. Aucun pipeline ni ordre réel lancé pour ces
tests ; la migration de la tâche existante sera appliquée à sa réinstallation.

## Vérification de livraison

Le 7 octobre 2026, le mode `--dry-run` a construit les neuf commandes avec la date de séance US du jour et a terminé en `DRY_RUN`. Après harmonisation, une génération à blanc a confirmé le fichier commun sur 3/4/5/8. Aucun traitement réel ni écriture SQL n'a été déclenché pendant ces vérifications. Les tests couvrent l'ordre des étapes, l'exclusion ML/ordres, les défauts partagés, les jours fériés, le décalage Paris/New York, le refus d'une autre base, les compteurs d'échec, le verrou partagé, les fenêtres et l'univers commun, ainsi que la conservation des scopes interactifs par défaut.
