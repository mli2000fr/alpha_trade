# Sprint 17-C — Propriétaire unique de la collecte CN et qualité quotidienne

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

État du 1er octobre 2026. Le code, la configuration et la tâche de contrôle sont installés ; **la preuve de sept séances réelles consécutives n'existe pas encore**. Le marché CN est fermé du 1er au 7 octobre dans le [calendrier opérationnel 2026](../../config/research_cn/sprint15d6_cn_calendar_2026.yaml). La première séance éligible est le **8 octobre 2026**. Aucune tâche D6/D9/D10 n'a été réinstallée ou déplacée par ce sprint.

## Décision d'architecture : D9 écrit, 17-C observe

**Mise à jour du 10 octobre :** le contrôle est désormais à **20:30 Paris**,
soit le lendemain civil à 02:30/03:30 Shanghai. Il audite la veille CN grâce à
`audit_previous_day_before_open: true`, sans choisir une vieille séance durant
les congés. Voir [planning et durées](../operations/horaires_fr_cn_presence_pc.md).
Les mentions 23:30 ci-dessous décrivent l'installation initiale, pas l'horaire
actuel. D9/D6 sont actuellement bloqués pour droits : ce déplacement ne les
active pas et ne certifie aucun cycle réussi.

Le propriétaire **unique des écritures canoniques quotidiennes prospectives** est `cn_oracle_prospective_daily` (D9, [code](../../service/market/cn_oracle_daily_15d9.py), [configuration](../../batch.yaml)). Après clôture d'une séance ouverte, D9 :

1. fixe la séance J et la prochaine séance de décision K à partir du calendrier CN ; aucune prévision rétroactive après le cutoff de 09:15 Shanghai ;
2. prépare le référentiel BaoStock `stock_basic`, le calendrier `trade_cal` et les quatre indices `index_daily`, puis un manifeste de **toutes** les actions CN, y compris les radiées lorsqu'elles sont pertinentes ;
3. coupe l'univers en lots de 25 titres, collecte `daily` et `adj_factor` avec état reprenable et retry réseau borné ;
4. promeut les données vers `market_sessions`, `stock_bars_daily`, `instrument_adjustment_factors`, statuts et limites de prix ; les écritures incrémentales 2026 sont insert-only sur la matière historique déjà figée ;
5. exige tous les lots terminés et le préflight Oracle avant de publier l'export TOP20 de K. Il garde les horodatages observés/disponibles et refuse une publication postérieure au cutoff.

`cn_daily_market_data_sync`, dans [batch_cn.yaml](../../batch_cn.yaml), reste **désactivé** (`DISABLED_DUPLICATE_D9`). Il ne ferait que `daily`, `adj_factor`, `index_daily` sur une fenêtre J−10/J avec `include_inactive: false` ; il n'assure ni la préparation du master/calendrier, ni la publication Oracle, ni le même univers. L'activer parallèlement créerait deux propriétaires des lignes staging et potentiellement du canonique. Son lookback pourrait réparer des barres manquantes, **jamais** recréer une prévision Oracle qui n'était pas disponible avant la décision. Un rattrapage canonique manuel reste possible avec la procédure 7-C, mais doit être identifié comme tel et ne valide pas rétrospectivement D9.

Le contrôle historique `cn_staging_quality_daily` reste également désactivé (`SUPERSEDED_BY_17C`) : il vérifie seulement présence et âge calendaire de quelques endpoints, ce qui peut produire des faux échecs pendant les congés et ne couvre pas D6/D9/D10. Son `min_daily_rows` ancien n'entre pas dans ses gates. Le nouveau [contrôle 17-C](../../service/market/cn_daily_quality_17c.py) est **strictement en lecture seule** côté MySQL et n'effectue aucun téléchargement, entraînement, serving ou ordre.

| Flux | Univers/séances | Données collectées | Écritures canoniques | État 17-C |
|---|---|---|---|---|
| D9 | Une séance ouverte J, univers CN complet PIT ; environ 209 lots à la taille actuelle | master, calendrier, indices, barres, facteurs | Oui ; seul propriétaire planifié | Actif, inchangé |
| `cn_daily_market_data_sync` | J−10/J, titres actifs seulement | barres, facteurs, indices | Staging générique ; pourrait concurrencer D9 | Désactivé |
| 7-C manuel | Dates de rattrapage explicitement choisies | idem D9 selon commande | Oui, mais identifié hors cycle D9 | Aucun planificateur ajouté |
| `cn_daily_quality_17c` | Une séance ouverte J après D9 | Aucune | Non | Actif, lecture seule |

## Gates quotidiens à 23:30 Shanghai

La nouvelle entrée `cn_daily_quality_17c` de [batch_cn.yaml](../../batch_cn.yaml) est planifiée du lundi au vendredi à **23:30 Asia/Shanghai / China Standard Time** (17:30 en France en été, 16:30 en hiver). D9 démarre à 18:15 Shanghai : cet écart de 5 h 15 laisse le temps à sa collecte de plusieurs milliers de titres de se terminer, sans confondre un run encore actif avec une panne. Un D9 toujours incomplet à 23:30 reste un échec du gate. Le [lanceur](../../scripts/windows/cn_daily_quality_launcher_17c.ps1) demande un préflight au calendrier : jour fermé → `SKIP_CLOSED`, sans alerte ni requête MySQL. Un calendrier hors année 2026 échoue explicitement ; il faudra qualifier 2027 avant de prolonger le service. La tâche Windows `AlphaTrade-CnDailyQuality17c` est installée en mode `Interactive` ; comme D9, elle ne tourne pas si la session Windows est fermée.

Pour une séance ouverte J, les gates **critiques** sont :

- manifeste non vide et identique à l'index des lots ; chaque lot présent et `COMPLETED`, aucun `FAILED` ; rapport D9 de J `COMPLETED_RESEARCH_ONLY` ;
- séance canonique `open`, couverture des barres d'actions ≥ **99,5 %** du manifeste et présence des **4 indices** ; pas de doublon instrument/jour ;
- OHLC/volume/montant valides, suspension sans volume positif, empreinte source et `available_at` présents, aucune disponibilité avant clôture ou dans le futur ;
- staging `daily` couvrant les barres actions, `index_daily` couvrant les indices ; chaque facteur `adj_factor` observé relié à un facteur canonique ;
- limite de prix présente pour chaque action ayant une barre, aucune politique inconnue parmi celles-ci ;
- export Oracle TOP20 valide pour la prochaine séance K, empreinte de parquet et horodatages antérieurs à l'heure du contrôle et au cutoff K ;
- appariement D10 de J outcome-blind, rapport et parquet présents, empreintes concordantes avec son journal de run, candidat Oracle de J identique, aucune écriture DB.

Les snapshots officiels D6 `before_open` et `after_close` sont contrôlés avec leur phase, séance cible, horodatage d'observation et cutoff. Leur absence apparaît comme **avertissement** : les annonces officielles et leur publication sont indépendantes de la collecte des barres, mais l'absence doit être suivie et expliquée. Un gate critique échoué donne `FAILED`, un avertissement seul `COMPLETED_WITH_WARNINGS`, sinon `COMPLETED`. Le runner conserve les compteurs et les erreurs dans un nouveau JSON sous `artifacts/research/cn_daily_quality_17c/runs/` ; le lanceur commun alimente logs et notifications email/Telegram. Les requêtes MySQL sont bornées à la séance et utilisent les index date ou endpoint/date, sans scan de toute l'histoire.

La page **Workflow & Orchestration → Batch → `cn_daily_quality_17c`** affiche en lecture seule les dernières séances distinctes contrôlées, le statut, les gates passés et les noms des contrôles critiques ou en avertissement. Plusieurs tentatives de la même séance n'apparaissent qu'une fois, avec la tentative la plus récente. Cette vue facilite l'audit mais **ne certifie pas automatiquement sept séances ouvertes consécutives** ; il faut vérifier le calendrier et les rapports complets avant de clore le gate.

Cette séparation évite de confondre « données présentes après coup » avec « décision PIT réellement prise à temps ». Le contrôle compare les dates de publication des preuves au moment d'audit ; aucun fichier créé ultérieurement ne peut valider rétrospectivement une exécution précédente.

## Vérification en lecture seule du 30/09/2026

Le smoke sur cette séance a observé **5 224 actions + 4 indices**, 39 facteurs staging tous appariés au canonique, 5 224 limites de prix, zéro OHLC invalide, zéro suspension/volume contradictoire et zéro violation de lineage temporel. L'état de rattrapage manuel contient **209 lots terminés**. Cependant, il est stocké dans `sprint7c_chunks_2026-09-30`, et non dans le chemin propre aux runs D9 `sprint7c_daily_chunks/2026-09-30` ; aucun rapport de run D9 pour cette séance n'existe. L'export Oracle pour la décision du 08/10 existe et est valide, mais l'appariement D10 du 30/09 est absent. Le contrôle signale donc **trois échecs critiques** (`chunks_complete`, `d9_owner_completed`, `d10_outcome_blind_match`) pour cette observation historique. Il serait erroné de compter ce rattrapage comme un cycle D9 complet.

Le smoke n'a modifié ni données CN/US ni tâches planifiées. La commande quotidienne en simulation sur le 01/10 répond `SKIP_CLOSED` ; elle n'a produit aucune fausse alerte malgré la semaine de congé.

Le [rapport d'audit 17-A actualisé](../../artifacts/research/cn_operations_17a/audit-20261001-after-17c.json) ne signale plus l'ancien collecteur et l'ancien contrôle désactivés comme des lacunes : D9 et 17-C sont leurs remplaçants actifs. Son unique avertissement restant concerne les quatre tâches de recherche CN encore déclarées dans `batch.yaml` ; leur migration est réservée à 17-D après validation réelle, sans double installation prématurée.

## Critère de clôture opérationnelle

Sept séances **ouvertes** consécutives avec un rapport 17-C, D9 complet, Oracle et D10 cohérents, sans anomalie critique inexpliquée sont nécessaires. Selon le calendrier 2026, les sept premières séances candidates sont **8, 9, 12, 13, 14, 15 et 16 octobre**. Un échec ou une séance manquée interrompt la série ; un backfill de prix ne répare pas la preuve prospective. Les avertissements D6 doivent être examinés avant de conclure, même s'ils ne bloquent pas à eux seuls la donnée canonique.

Contrôles opérateur :

```powershell
# Vérifier configuration, heure et prochaine activation Windows.
Get-ScheduledTask -TaskName AlphaTrade-CnDailyQuality17c | Select-Object TaskName,State,Actions
Get-ScheduledTaskInfo -TaskName AlphaTrade-CnDailyQuality17c | Select-Object LastRunTime,LastTaskResult,NextRunTime

# Vérifier sans accéder à la base si le contrôle est dû (code 10 = fermeture/non dû).
.\.venv\Scripts\python.exe -m service.market.cn_daily_quality_17c --batch cn_daily_quality_17c --probe

# Lire les preuves de séance et les alertes ; ne pas transformer un échec en PASS manuel.
Get-ChildItem artifacts/research/cn_daily_quality_17c/runs -Filter 'run-*.json' | Sort-Object LastWriteTime -Descending | Select-Object -First 7 Name,LastWriteTime
Get-Content log/batch_cn/cn_daily_quality_17c.txt -Tail 40
```

Les [tests 17-C](../../tests/test_cn_daily_quality_17c.py) couvrent jours fermés, reprise de lots, absence de propriétaire D9, panne source, violation PIT, facteur non promu, D10 absent, persistence des erreurs et interdiction d'un deuxième collecteur actif. Les tests D9/D10 existants ont également été rejoués. **Aucun succès réel 17-C ne doit être affirmé avant les sept prochains cycles.**
