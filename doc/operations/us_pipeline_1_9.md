# Batch US — Pipeline quotidien 1 à 9

## Périmètre

`us_pipeline_1_9`, déclaré dans `batch.yaml`, enchaîne les neuf premières étapes numérotées de la page Pipeline, dans le même moteur de workflow. Il ne lance ni entraînement ML (T1), ni prédiction (10), ni moteur de risque (11), ni exécution d'ordres (12).

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

`us_pipeline_1_9.symbols_file` désigne **config/univers_batch/univers_filtred_tradable.txt**. Le batch le transmet aux étapes capables de recevoir ce choix :

| Étape | Application du fichier |
|---|---|
| 3 — Screener | `--custom-universe-file`, prioritaire sur l'univers du screener dans config.yaml |
| 4 — Quotes | `--symbol-source universe-file:config/univers_batch/univers_filtred_tradable.txt` ; fenêtre J−7/J, lot 200 |
| 5 — Earnings | Même source ; Finnhub, J−7/J+30, lot 50, reprise activée |
| 8 — News/sentiment | Import brut, pertinence, scoring standard/contextuel et features ticker sur ce fichier |

L'import de barres (1) et le nettoyage (2) ne reçoivent pas de nouveau paramètre d'univers par ce raccordement. La publication (6), la sélection (7) et l'agrégation (9) conservent leurs périmètres dérivés/natifs. Les features secteur du traitement sentiment conservent leur agrégation historique par fournisseur : ce changement ne purge ni ne restreint rétroactivement l'historique déjà importé.

Les fenêtres quotes/earnings sont calculées depuis la séance J figée, pas depuis une horloge qui pourrait passer minuit au milieu du workflow. Les blocs `quotes_collection` et `earnings_collection` dans batch.yaml portent leurs réglages ; le fichier commun est prioritaire. Des ancres YAML partagent les valeurs avec les anciennes sections autonomes.

Les sections `latest_quotes_sync` et `earnings_calendar_sync` restent visibles mais sont **désactivées**, avec le statut `INTEGRATED_IN_US_PIPELINE` et une explication dans l'IHM. Le 7 octobre 2026, leurs tâches Windows ont également été désactivées, sans arrêter le run earnings déjà actif. La tâche `AlphaTrade-UsPipeline19` installée reste active. Il ne faut pas réactiver les anciennes planifications en parallèle.

Les collecteurs CLI restent utilisables manuellement en cas de besoin :

```powershell
python -u -m dataIntegrityEngine.sync_latest_quotes --symbol-source universe-file:config/univers_batch/univers_filtred_tradable.txt --batch-size 200 --from-date YYYY-MM-DD --to-date YYYY-MM-DD
python -u -m dataIntegrityEngine.sync_earnings_calendar --symbol-source universe-file:config/univers_batch/univers_filtred_tradable.txt --batch-size 50 --sleep-seconds 1.1 --log-every 25 --from-date YYYY-MM-DD --to-date YYYY-MM-DD --resume
```

Remplacer les dates avant lancement. Le launcher quotes respecte `enabled: false`, même avec `-Force` ; utiliser directement son collecteur pour une intervention manuelle. Le launcher historique earnings ignore la planification désactivée, mais conserve son lancement manuel explicite `-Force`, hors blocage juridique. Le batch Pipeline ne contourne aucun statut fournisseur bloqué.

Le sentiment utilise notamment le scoring standard + contextuel, les checkpoints de reprise et les valeurs partagées de taille de lots. Les poids de l'agrégateur restent ceux des défauts Pipeline ; activer la collecte/scoring ne signifie pas augmenter automatiquement le poids du sentiment dans la sélection.

Le plan exact (date, options et neuf commandes) est archivé avant exécution :

`artifacts/operations/us_pipeline_1_9/<run_id>/plan.json`

Les options archivées peuvent contenir des réglages des étapes ML/risque/exécution du conteneur commun, mais seules les neuf commandes listées sont exécutées.

## Installation et utilisation

Dans **Workflow & Orchestration → Batch → US**, chercher `us_pipeline_1_9`, puis **Installer / réinstaller**. La section est activée dans `batch.yaml`, mais sa présence dans le fichier ne crée pas automatiquement la tâche Windows.

Installation en ligne de commande, depuis la racine du projet :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_forward_pit_task.ps1 -BatchName us_pipeline_1_9
```

Vérification sans exécuter les étapes, sans écrire en base ni créer de workflow :

```powershell
python -u -m service.forward_pit.batch --batch us_pipeline_1_9 --dry-run
```

Exécution immédiate réelle, après clôture d'une séance US :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\forward_pit_launcher.ps1 -BatchName us_pipeline_1_9 -Force
```

Le batch nécessite les mêmes accès fournisseurs, tables et dépendances que les neuf traitements interactifs. Il exige `US_EQ` et la base `alpha_trade` ; une connexion CN/FR est refusée. Aucune nouvelle table ni migration n'est nécessaire.

## Suivi, concurrence et notifications

Le workflow utilise le registre et le verrou partagés avec l'IHM : il ne contourne pas un pipeline déjà actif. Son identifiant est enregistré dans le détail du run du batch. Les journaux et l'avancement des étapes restent consultables via le registre Pipeline, et le résumé apparaît dans la page Batch.

Journal du launcher : `log/batch/us_pipeline_1_9.txt`. Le détail du run conserve également le chemin du journal du workflow et, en cas d'échec d'une étape, son identifiant et son code retour.

Les notifications email et Telegram passent par le launcher commun, avec statut et message d'erreur. **L'unité des compteurs de ce batch est l'étape**, pas le nombre de lignes SQL :

- demandés : 9 ;
- reçus / persistés : nombre d'étapes terminées avec succès ;
- échecs : 1 si le workflow ne peut pas commencer ou s'interrompt ;
- alertes : avertissements du résumé du batch, pas une addition implicite des avertissements de chaque sous-traitement.

Les notifications propres aux sous-traitements et au workflow existant peuvent s'ajouter à celle du batch. Pour suspendre la planification, désactiver la section et/ou désinstaller sa tâche depuis la page Batch ; les historiques sont conservés.

## Vérification de livraison

Le 7 octobre 2026, le mode `--dry-run` a construit les neuf commandes avec la date de séance US du jour et a terminé en `DRY_RUN`. Après harmonisation, une génération à blanc a confirmé le fichier commun sur 3/4/5/8. Aucun traitement réel ni écriture SQL n'a été déclenché pendant ces vérifications. Les tests couvrent l'ordre des étapes, l'exclusion ML/ordres, les défauts partagés, les jours fériés, le décalage Paris/New York, le refus d'une autre base, les compteurs d'échec, le verrou partagé, les fenêtres et l'univers commun, ainsi que la conservation des scopes interactifs par défaut.
