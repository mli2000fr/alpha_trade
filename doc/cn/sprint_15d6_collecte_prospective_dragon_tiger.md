# Sprint 15-D6 — Observations Dragon/Tiger prospectives, deux passages CN

Mise en place le 30 septembre 2026. **Deux tâches Windows de recherche sont installées ; aucun modèle, label, table CN/US, backtest ou serving n'est alimenté par ces observations.** Le premier passage manuel avant ouverture est terminé. La qualification PIT et les droits d'exploitation restent ouverts.

## Horaires et calendrier

La [règle de négociation SSE 2026](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml) place la clôture des enchères à 15:00 et l'ouverture de l'enchère du matin à 09:15, heure de Shanghai. Les tâches font donc deux lectures distinctes :

| Batch | Heure Shanghai | Date d'événement lue | But |
| --- | --- | --- | --- |
| cn_dragon_tiger_after_close | 17:30 le jour J ouvert | J | Première observation après clôture |
| cn_dragon_tiger_before_open | 08:30 le prochain jour ouvert | Dernière séance ouverte J | Retards, ajouts, corrections avant le seuil prudent 09:15 |

Le calendrier [SSE](https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml)/[SZSE](https://www.szse.cn/disclosure/notice/t20251222_618087.html) 2026 est matérialisé dans [un fichier dédié](../../config/research_cn/sprint15d6_cn_calendar_2026.yaml) : week-ends et plages de fermeture officielles. Exemple important : après le 30 septembre, la prochaine séance ouverte est le **8 octobre**. Une année non explicitement chargée, notamment 2027, échoue fermée ; le calendrier doit être renouvelé, pas deviné. Le planificateur Windows utilise son identifiant de fuseau China Standard Time, équivalent à Asia/Shanghai pour les heures de ce contrat ; le calcul métier utilise Asia/Shanghai.

Chaque tâche est enregistrée par [batch.yaml](../../batch.yaml) et visible dans Workflow & Orchestration → Batch, avec son propre journal et ses commandes. Le lanceur Windows est caché. L'installation n'a créé que AlphaTrade-CnDragonTigerAfterClose et AlphaTrade-CnDragonTigerBeforeOpen ; les batchs US existants n'ont pas été réinstallés. Les déclencheurs Windows se réveillent à la minute 30, puis le lanceur ne fait réellement une requête qu'à l'heure Shanghai prévue. Un préflight local supprime aussi les notifications de doublon lorsqu'un passage valide de même phase a déjà été capturé.

## Ce que le journal prouve — et ne prouve pas

Chaque passage enregistre dans un **nouveau fichier** : l'heure UTC réellement observée, la phase, la séance source, la séance suivante et le seuil 09:15, les empreintes des réponses officielles, les identités code/bourse/motif et des empreintes de contenu. Les noms et montants de sièges ne sont pas persistés, pas plus que les rendements futurs. Les passages précédents restent intacts ; le rapport compte nouvelles lignes, retraits et changements de contenu. Un compte de lignes incohérent fait échouer le contrôle du snapshot.

La propriété observed_before_decision_cutoff vérifie uniquement que **notre lecture s'est achevée** avant 09:15 de la prochaine séance. Elle ne reconstitue ni l'heure de première publication officielle ni les données telles qu'un autre opérateur les aurait vues auparavant. Même une observation ponctuelle correcte conserve historical_pit_certified=false et pit_usable=false. Les droits d'utilisation de données restent RESEARCH_REVIEW_PENDING. Aucune feature ou décision d'achat/vente ne lit ce journal.

Le collecteur est isolé de service.forward_pit.batch et de la table US pit_collection_runs. La page Batch lit ses rapports fichiers pour afficher la dernière collecte. En cas d'échec, un rapport FAILED conserve le message et le lanceur commun envoie les notifications email/Telegram best-effort. Une tâche installée en mode Interactive ne tourne pas si la session Windows nécessaire est fermée ; un passage manqué ne peut pas être renommé « PIT » après rattrapage.

## Premier passage réel et vérifications

Un lancement manuel de cn_dragon_tiger_before_open a observé la séance du **29/09/2026** le **30/09/2026 à 06:54 Shanghai**, donc avant le seuil prudent 09:15 : **64 lignes de motifs reçues et enregistrées**, zéro échec fournisseur, zéro correction détectée à ce premier passage. Ce ne sont pas forcément 64 titres uniques. Le rapport est [ici](../../artifacts/research/cn_dragon_tiger_15d6/observations/runs/run-20260929T225411336561Z-b0e43cb5.json). Le passage automatique de 08:30 sur la même phase et la même séance doit être sauté comme doublon ; le passage après clôture du 30/09 est indépendant.

Les tests ciblés couvrent calendrier, fête nationale, horodatage, refus 2027, idempotence, routage IHM et masquage des secrets de notification. **76 tests ciblés passent** au jalon D6.

Le smoke a également révélé un échec de certificat TLS du canal Telegram local ; la collecte et le rapport ont réussi. La vérification HTTPS **n'a pas été désactivée**. Le gestionnaire d'erreur Telegram a été corrigé pour ne plus inscrire l'URL contenant le jeton dans les journaux, et l'occurrence de ce journal a été masquée. Il reste à rétablir une chaîne de certification valide pour recevoir les messages Telegram.

## Suite et gate

Laisser tourner plusieurs semaines de séances ouvertes, surveiller les deux phases et les éventuelles corrections, puis mesurer la couverture effective avant le seuil de décision. Avant une ablation directionnelle : clarifier les droits de réutilisation, fixer le protocole d'appariement date/board/score Oracle/mouvement antérieur, séparer D1-veto de D10-LONG, corriger la dépendance des observations répétées et garder les semestres OOF de confirmation hors choix de seuil. Aucun entraînement ou promotion automatique n'est prévu par 15-D6.

Code : [ordonnanceur](../../service/market/cn_dragon_tiger_schedule_15d6.py), [journal d'observations](../../service/market/cn_dragon_tiger_prospective_15d5.py), [lanceur Windows](../../scripts/windows/cn_dragon_tiger_launcher_15d6.ps1), [tests](../../tests/test_cn_dragon_tiger_schedule_15d6.py).
