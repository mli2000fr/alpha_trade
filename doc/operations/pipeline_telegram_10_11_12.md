# Notifications Telegram — étapes US 10, 11 et 12

Implémentation du 17 octobre 2026. Ces messages complètent les notifications
de fin de batch existantes, sans modifier les modèles, la sélection, le risque
ou les ordres. Ils fonctionnent depuis la page Pipeline et depuis `us_pipeline`.

## Contenu et déclenchement

| Étape | Déclenchement | Informations |
| --- | --- | --- |
| 10 — ML Predict | Filtre GPT/DeepSeek activé, après la tentative Oracle + LLM | Fournisseur et modèle archivés, date de séance, identifiant d’analyse, titres réellement sélectionnés dans l’ordre de sélection, LONG/SHORT et note de confiance. |
| 11 — Risk Management | Fin d’un risque US PAPER non simulé à blanc | Cibles effectivement publiées pour le run, le compte et la date exacts : symbole, LONG/SHORT, quantité cible ; motifs de rejet disponibles. Avec ou sans filtre LLM. |
| 12 — Execution | Fin d’une exécution US PAPER non simulée à blanc | État du run, ordres soumis/échoués, détail OMS par ordre : symbole, sens de position, quantité réellement remplie, prix moyen observé et montant brut en USD. Liste des nouvelles entrées/plans retenus : prix de référence, quantité, capital alloué indicatif et total par compte. Avec ou sans filtre LLM, y compris le parcours Q051/B + anti-SL. |

Si aucun titre n’est retenu à l’étape 10, le message distingue :

- abstention valide du LLM, avec ses arguments haussier/baissier archivés ;
- sources récentes insuffisantes, sources exclues/non traçables, confiance
  sous le seuil ou SHORT interdit par la configuration ;
- échec technique / réponses invalides : aucune sélection n’est publiée,
  même si certaines réponses individuelles étaient directionnelles ;
- échec avant archivage ou résultat inaccessible : aucune nouvelle sélection
  confirmée, sans réutiliser le résultat d’une ancienne tentative.

La note de confiance est déclarée par le LLM ; ce n’est pas une probabilité
calibrée. Les arguments rapportés ne constituent pas une validation indépendante.
L’étape 11 reste indispensable avant tout ordre.

## Ordre envoyé ≠ ordre exécuté

Un ordre soumis après la clôture peut rester en attente. Le message indique
alors son état et la quantité demandée, **sans transformer le prix de décision
ou le prix limite en prix d’exécution**. Un remplissage partiel utilise uniquement
la quantité déjà remplie et le prix moyen observé. Si le prix n’est pas qualifié,
le montant est signalé indisponible et exclu du total qualifié.

Le montant par ordre vaut quantité remplie × prix moyen. Le total est un volume
brut d’exécutions **hors frais**, pas un PnL ni une exposition nette. LONG/SHORT
est déterminé avec le rôle de l’ordre : une vente de sortie/stop/TP d’un LONG
est une clôture/réduction LONG, pas une nouvelle position SHORT. Un rôle inconnu
reste explicitement non qualifié.

Le message est une **photographie de fin d’étape**. Il ne promet pas de nouveau
Telegram pour un fill arrivé plus tard dans le watcher. Si le wrapper LLM évite
l’exécution faute de sélection ou de cible risque, il envoie un message « aucun
ordre envoyé » avec ce motif. Un échec avant la production du résumé risque ou
exécution conserve les mécanismes d’erreur existants, pas un faux bilan réussi.

### Capital alloué — évolution du 19 novembre 2026

La liste des nouvelles entrées distingue le prix de référence archivé dans
`execution_order_requests.decision_price` du prix exécuté. Le capital alloué
indicatif vaut quantité demandée × prix de référence, hors frais ; ce n'est
pas le capital déjà débité. La liste ne compte qu'une fois chaque demande OMS,
exclut les stops/TP et les ordres refusés/annulés sans remplissage. Pour un ordre
annulé après un remplissage partiel, seule la partie exécutée est retenue.

Si Winner a publié un nouveau `PLAN_ARMED` sans demande OMS, la notification
indique la quantité initiale du plan et le prix du snapshot d'exécution du même
run/compte/séance. Le montant reste conditionnel : « plan Winner publié,
soumission non confirmée ». Un plan préexistant n'est pas annoncé comme nouveau.
Un prix absent reste indisponible et n'entre pas dans le total renseigné.
Les champs `submitted_orders` et `submitted` des deux parcours sont acceptés.

Exemple de ligne, avant exécution :

`• ABC — LONG — prix de référence 12.5 USD — quantité 10 — capital alloué indicatif 125.00 USD — ordre soumis`

Cette évolution s'applique aux prochaines notifications. Les messages déjà
figés dans l'outbox ne sont ni réécrits ni renvoyés automatiquement.

## Configuration et fiabilité

Utilise le service Telegram déjà présent et les variables d’environnement
`TOKEN_TELEGRAM_BOT` et `TELEGRAM_CHAT_ID`, sans nouvelle clé dans `config.yaml`.
Sans configuration ou si la livraison échoue, un avertissement est journalisé ;
le résultat métier et les étapes suivantes ne sont pas changés par Telegram.
Les branches LIVE, shadow, backtest et dry-run ne déclenchent pas ces messages
de risque/exécution PAPER. Les bases FR/CN ne sont pas concernées.

Les détails sont lus dans les archives `llm_directional_*`, `portfolio_targets`,
`execution_order_requests` et les observations courantes `execution_broker_orders`,
toujours avec le run/compte exacts. Aucune écriture SQL ni nouvel appel LLM ou
courtier n’est ajouté pour notifier. Une indisponibilité SQL est journalisée,
jamais traduite en « zéro exécution ».

L’outbox locale se trouve dans `artifacts/notifications/pipeline_telegram/<hash>/` :

- `payload.json` fige le texte et les parties, sans token ni clé API ;
- `sent-N.flag` marque chaque partie acceptée par Telegram ;
- `delivery.lock` porte un verrou système libéré si le processus s’arrête.

Les textes longs sont découpés, pas tronqués. Un nouvel appel de notification
pour la même étape/run/compte ne renvoie pas les parties déjà confirmées. Il
n’existe pas de relance périodique automatique des messages échoués. Un timeout
après acceptation côté Telegram peut néanmoins produire un doublon lors d’une
nouvelle tentative : Telegram ne fournit pas de garantie exactly-once.
Ne jamais relancer des ordres uniquement pour tenter de renvoyer un Telegram.

## Vérification

Tests locaux dans `tests/test_pipeline_telegram.py` : messages GPT/DeepSeek,
abstentions/erreurs, isolation run/compte/date, LONG/SHORT et clôtures, remplissages
partiels, absence de prix inventé, découpage et anti-doublon, échec de transport
sans effet métier. Transport simulé, SQLite en mémoire ; aucun ordre, appel
LLM ou vrai message Telegram nécessaire.

Code : `service/pipeline_telegram.py`, `service/llm_directional/pipeline.py`,
`risk_management/cli.py`, `run_execution.py`.
