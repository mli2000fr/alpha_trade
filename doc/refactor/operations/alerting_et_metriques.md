# Alerting multicanal, notifications IHM et métriques

Retour : [IHM et opérations](../16_ihm_et_operations.md)

## Trois chemins de notification

Le dépôt contient plusieurs mécanismes distincts :

1. `service/alerting.py` : alerting système multicanal ;
2. `ihm/services/notifications.py` : email de fin de step/workflow avec préférences IHM et marqueur anti-doublon ;
3. `ihm/services/email_notifier.py` : notifier email opérationnel léger, activé explicitement.

Ils partagent certains noms de variables SMTP mais n’ont pas le même contrat. Avant modification, identifier le caller et ne pas supposer qu’une préférence IHM configure automatiquement l’alerting système.

## Alerting système

`Notifier.send(subject, body, severity)` accepte `info|warning|critical`. Les implémentations sont log, Slack webhook, SMTP, Telegram Bot, Discord webhook et SMS Twilio. Tous les imports réseau sont lazy.

`build_notifiers_from_env()` construit tous les canaux complètement configurés. S’il n’en trouve aucun, `LogNotifier` garantit une trace. `build_notifier_from_env()` retourne seulement le premier canal, avec priorité induite par l’ordre de construction.

| Canal | Variables essentielles |
|---|---|
| Slack | `ALPHA_TRADE_SLACK_WEBHOOK` |
| SMTP | `ALPHA_TRADE_SMTP_HOST/PORT/FROM/TO/USER/PASSWORD` |
| Telegram | `ALPHA_TRADE_TELEGRAM_BOT_TOKEN/CHAT_ID` |
| Discord | `ALPHA_TRADE_DISCORD_WEBHOOK` |
| Twilio | `TWILIO_ACCOUNT_SID/AUTH_TOKEN/PHONE_NUMBER`, `NUM_SMS_ALERT` |

Les canaux sont best-effort : une exception déclenche le fallback log et n’est pas propagée au job. Discord tronque le body, SMS condense le message, SMTP utilise STARTTLS par défaut.

`send_system_alert()` diffuse à tous les canaux et déduplique par hash de `event + str(payload)` pendant 300 secondes par défaut. Le cache est local au processus et limité/nettoyé ; il ne déduplique pas plusieurs workers. L’ordre d’un dict dans sa représentation peut influencer la signature : fournir des payloads stables.

## Notifications de workflow IHM

`ihm/services/notifications.py` est appelé par le registre à la finalisation des steps/workflows. Les statuts terminaux sont completed, failed, timeout et stopped. Un fichier `notification_sent.flag` est posé dans le dossier du run seulement après succès ; en cas d’échec, une nouvelle tentative reste possible.

La configuration SMTP donne priorité aux variables d’environnement, puis à `notifications.smtp` dans YAML. Elle supporte TLS, SSL et CA. Les emails peuvent inclure la fin des logs et une pièce jointe bornée à 5 Mio. Ne pas joindre un log contenant des secrets.

Les préférences sont persistées sous `artifacts/ihm_preferences/notifications.json` : enabled, destinataires et statuts. Les adresses sont validées, dédupliquées sans tenir compte de la casse et conservées dans l’ordre.

Le code contient actuellement une liste de destinataires par défaut. Dans un déploiement partagé, remplacer cette valeur par une configuration contrôlée et vérifier qu’aucune donnée d’un autre environnement n’est envoyée.

## Notifier email léger

`ihm/services/email_notifier.py` exige `ALPHA_TRADE_EMAIL_ENABLED=1`. Il utilise `ALPHA_TRADE_EMAIL_FROM/TO/SUBJECT_PREFIX` en plus des variables SMTP. L’API retourne False si désactivée, True si l’envoi a été tenté ; True ne garantit pas la livraison, car les erreurs SMTP sont journalisées sans être relancées.

## Prometheus

`service/prometheus_metrics.py` maintient un registre thread-safe en mémoire. Il expose compteurs d’erreurs API, runs et alertes, ainsi que gauges circuit breaker, heartbeat stale, univers vide, kill switch, drift ML et alignement cash.

Deux sorties existent :

- fichier textfile atomique, défaut `artifacts/metrics/alpha_trade.prom`, configurable via `ALPHA_TRADE_PROMETHEUS_FILE` ;
- serveur HTTP minimal `/metrics`, port `ALPHA_TRADE_PROMETHEUS_PORT` ou 9090.

Le registre est local au processus et repart à zéro au redémarrage. Plusieurs workers n’agrègent pas automatiquement leurs compteurs. Le serveur HTTP n’intègre ni TLS ni authentification : limiter son écoute/réseau.

## Exploitation

Une alerte indique environnement, compte non secret, run id, date, statut, conséquence et action. Le payload reste minimal. Les règles Prometheus historiques sous `doc/monitoring/` sont des sources à vérifier contre les noms de métriques actuels avant déploiement.

Une panne de notification est un incident d’observabilité, pas une preuve d’échec métier. Un run critique peut toutefois être déclaré non exploitable si la politique opérationnelle exige un canal sain : cette décision appartient au caller, pas aux notifiers best-effort.

## Tests

Tester factory avec configurations partielles, fallback log, timeout/HTTP non-2xx, destinataires SMTP, cooldown, cache multi-signatures, marqueur succès/échec, statuts filtrés, taille de pièce jointe, TLS/SSL, écriture Prometheus atomique et endpoint autre que `/metrics`.

