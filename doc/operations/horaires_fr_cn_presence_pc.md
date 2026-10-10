# Horaires FR/CN — présence du PC, 10 octobre 2026

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

Le PC est disponible avant 07:30 et à partir de **20:00 Europe/Paris**.
Les horaires ci-dessous concernent les batchs actifs ; les collecteurs bloqués
pour droits/prudence restent désactivés. `us_pipeline` reste à 22:45, inchangé.

## France

Tous ces horaires sont en Europe/Paris. Les jours configurés restent inchangés.

| Batch | Passage | Plus longue durée locale observée | Marge de planification |
| --- | --- | --- | --- |
| fr_calendar_snapshot | dimanche 06:00 (anciennement 07:00) | 0,6 s | 45 min |
| fr_security_master_sync | lundi–vendredi 05:00 (anciennement 07:00) | 73 s | 120 min |
| fr_daily_bars_sync | lundi–vendredi 22:00 | 254 s, échec inclus | 45 min |
| fr_corporate_actions_sync | lundi–vendredi 23:00 | 461 s | 50 min |
| fr_amf_short_sync | lundi–vendredi 21:00 | 2 s | 45 min |
| fr_dila_disclosures_sync | lundi–vendredi 21:30 | 1,6 s | 45 min |
| fr_options_mifir_trade_sync | lundi–samedi 06:00 (anciennement 07:00) | 42 s, échec inclus | 45 min |
| fr_db_backup | dimanche 03:00 | pas de run quotidien archivé observé | 90 min, provision |
| fr_artifacts_backup | samedi 02:00 | 23 min 51 s | 90 min |

Audit en lecture seule des fichiers `artifacts/fr/operations/runs` : échantillon
encore court (1 à 8 runs pour les batchs actifs observés). Les budgets sont des
marges de planification, **pas des délais maximaux forcés ni une garantie**.
Les fins budgétées sont au plus à 07:00, avec 30 minutes avant le départ.

Les collectes de barres restent après leur borne de 22:00, sans changement
de J−7/J ni de leurs dates métier. ESMA reste jusqu'à J−1, avec recouvrement.
L'avancement de 07:00 à 05:00 peut manquer une publication ESMA tardive :
elle attendra la prochaine collecte, sans fausse preuve disponible avant décision.
MiFIR vise toujours le fichier du précédent jour de négociation ; si non publié
à 06:00, la collecte peut manquer. Sa rétention courte ne garantit aucun rattrapage.
Ce changement répond à la disponibilité du PC, pas à une certification de couverture.

## Chine

| Batch actif | Horaire | Conversion / séance |
| --- | --- | --- |
| cn_db_backup | dimanche 04:00 Paris, inchangé | maximum observé 7 min 28 s ; budget 50 min |
| cn_dragon_tiger_daily_match | séance CN à 09:30 Shanghai, inchangé | 03:30 Paris été / 02:30 hiver ; budget provisionnel 45 min |
| cn_daily_quality_17c | lundi–vendredi **20:30 Paris** | lendemain civil Shanghai à 02:30 été / 03:30 hiver ; contrôle de la veille CN ; budget provisionnel 45 min |

Le contrôle 17-C était à 23:30 Shanghai, donc 17:30/16:30 Paris,
pendant l'absence. `audit_previous_day_before_open: true` autorise son audit
après minuit Shanghai **avant 09:15** : la séance cible est la veille civile,
jamais une vieille séance substituée durant un congé. Ainsi vendredi 20:30
Paris contrôle vendredi CN, même si Shanghai est déjà samedi. Le cutoff,
le calendrier CN, les preuves réellement disponibles et leurs dates ne changent pas.
La collecte D9, les modèles, le serving et les ordres ne sont pas modifiés.

Attention : D9 et les deux collectes D6 sont actuellement désactivés/bloqués.
Déplacer 17-C ne lève pas leur blocage et ne fabrique pas leurs preuves : le
contrôle reste bloquant si son propriétaire D9 requis est désactivé.
Aucun nouveau passage de secours n'est ajouté ; les entrées FR/CN actives
n'en avaient pas. Les anciens paramètres de collecteurs désactivés ne sont
pas des horaires d'exécution autorisée.

## Planification et vérification

Les tâches Windows installées ont été lues sans modification : déclencheurs
horaires `:00` ou `:30`, launcher relisant le YAML à chaque lancement.
Les minutes utiles sont conservées : **pas de réinstallation nécessaire pour
ces tâches existantes**. Aucun run ni service n'a été arrêté ou lancé.
Mail/Telegram et les mécanismes de reprise restent inchangés.

Les tests de calendrier balayent 2025–2027, conversions été/hiver comprises,
pour tous les batchs FR/CN actifs et leurs éventuels horaires de secours.
Les tests métier CN couvrent aussi vendredi après minuit, congés chinois et
cutoff 09:15. Ces tests d'horaires ne qualifient pas le calendrier métier 2027.
Validation locale : **192 tests réussis**, un avertissement pandas de parsing
sur une date volontairement invalide. Le cas `partial` avec zéro manquant et
résultat `COMPLETE` est aussi couvert ; aucune écriture SQL réalisée par l'audit.

Références : [configuration FR](../../batch_fr.yaml),
[configuration CN](../../batch_cn.yaml),
[tests des horaires](../../tests/test_fr_cn_batch_schedules.py),
[tests de la séance CN](../../tests/test_cn_daily_quality_17c.py).
