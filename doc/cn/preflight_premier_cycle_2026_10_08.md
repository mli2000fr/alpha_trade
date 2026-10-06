# Premier cycle CN du 8 octobre 2026 — contrôle avant ouverture

État au 1er octobre : **préparation terminée, cycle réel non encore observé**. Ce contrôle ne remplace ni les rapports D6/D9/D10, ni le gate de sept séances ouvertes de 17-C. Ne pas lancer les collecteurs hors de leur fenêtre pour fabriquer une preuve PIT.

## Horaires à surveiller

Le 8 octobre, Shanghai est à UTC+8 et Paris à UTC+2. Les tâches Windows sont déclenchées chaque heure à leur minute configurée ; le lanceur vérifie ensuite l'heure métier et le calendrier CN. Un `LastTaskResult = 0` sur un jour férié peut simplement signifier `SKIP_CLOSED`.

| Traitement | Heure Shanghai | Heure Paris | Preuve à vérifier |
|---|---:|---:|---|
| D6 `cn_dragon_tiger_before_open` | 08:30 | **02:30** | snapshot réellement observé avant 09:15 Shanghai |
| D10 `cn_dragon_tiger_daily_match` | 09:30 | **03:30** | appariement outcome-blind de la décision du 08/10 |
| D6 `cn_dragon_tiger_after_close` | 17:30 | **11:30** | snapshot de la séance du 08/10 |
| D9 `cn_oracle_prospective_daily` | 18:15 | **12:15** | lots complets du 08/10 et export pour le 09/10 |
| 17-C `cn_daily_quality_17c` | 23:30 | **17:30** | rapport de qualité des preuves du 08/10 |

Le PC doit être allumé, non en veille, avec la session Windows de l'utilisateur des tâches ouverte. Les cinq tâches sont `Ready`, utilisent le lanceur invisible et un principal `Interactive` au contrôle du 01/10 ; ce dernier point reste un risque opérationnel pour le passage de **02:30 Paris**. Vérifier veille, alimentation et connexion Windows la veille au soir. Ne pas interpréter l'état `Ready` comme une preuve de traitement effectué.

## Ce qui a été vérifié sans collecte réelle

- Les cinq sondes de calendrier exécutées le 01/10 retournent le code `10` (`SKIP_CLOSED`) ; elles n'ouvrent pas une collecte.
- Le calendrier explicite considère le 08/10 comme première séance ouverte après le 30/09. Les tests couvrent les cutoffs, jours fermés et l'échec fermé hors calendrier 2026.
- Les simulations isolées couvrent panne du flux officiel D6 puis reprise sans snapshot fabriqué ; lots D9 incomplets puis reprise sans publication Oracle anticipée ; candidat D10 absent puis appariement après disponibilité admissible ; 17-C critique et reprise des lots. Les rapports d'échec sont conservés séparément des rapports de succès.
- Le format de notification d'échec a été testé **sans SMTP ni réseau** : passage principal, compteurs, alertes et cause sont présents. Aucun faux mail « batch CN en échec » n'a été envoyé.
- La délivrance réelle a été testée avec l'événement explicitement nommé `TEST_CN_READINESS_FINAL_AUCUN_BATCH_EXECUTE` : SMTP a accepté le message et Telegram a confirmé l'envoi. Cela ne prouve pas la lecture par le destinataire. Un premier test Telegram avait révélé un échec TLS Python alors que le magasin Windows validait le certificat ; le [client Telegram](../../service/telegram.py) utilise maintenant un repli **avec vérification TLS par les racines Windows**, jamais `verify=False`.
- Le succès SMTP est désormais écrit dans le journal du lanceur via [le notificateur](../../scripts/send_batch_email.py). Un échec email ou Telegram demeure best-effort et **ne change pas** le statut métier du batch : surveiller également les journaux locaux.

## Vérifications la veille et le jour J

1. Le 07/10 au soir, confirmer le PC éveillé et la session Windows de l'utilisateur connectée pour 02:30 Paris. Vérifier les cinq tâches et leurs prochaines exécutions avec `Get-ScheduledTask` et `Get-ScheduledTaskInfo`. Ne pas réinstaller les tâches ni déplacer les catalogues avant le cycle.
2. Avant 03:15 Paris le 08/10, confirmer le rapport et l'horodatage D6 avant ouverture. Si absent, la seule reprise admissible est **avant 09:15 Shanghai** ; ensuite marquer la séance manquante.
3. Après 03:30 Paris, contrôler D10, les empreintes de l'export Oracle et des snapshots. Un `SKIP` ou un code Windows `0` ne suffit pas.
4. Après 11:30 puis 12:15 Paris, contrôler D6 après clôture et D9 : statut, lots complets, nombre de barres, preflight Oracle et export de la prochaine décision avant cutoff. Conserver tout échec et sa cause ; ne jamais rétro-dater le score.
5. Après 17:30 Paris, contrôler le rapport 17-C et ses checks nommés. Une séance incomplète bloque 17-D ; sept séances ouvertes consécutives sans anomalie critique inexpliquée restent nécessaires pour clôturer 17-C.
6. Sur chaque erreur, comparer le log métier au journal de notification. L'absence d'email/Telegram exige une investigation séparée ; elle ne transforme jamais un batch échoué en succès.

Les commandes et chemins de preuve détaillés sont dans le [TODO D7–D11](./TODO_reprise_oracle_dragon_tiger_D7_D11.md), le [TODO 18-C](./TODO_sprint_18c_post_cloture_2026_10_08.md) et la [préparation 17-D](./sprint_17d_preparation_bascule_catalogues.md).
