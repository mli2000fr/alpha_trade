# Sprint 18-B — Shadow d'exécution CN_A, sans broker

## Ce qui est livré

Le module `service/market/cn_shadow_execution_18b.py` permet de produire une **preuve prospective, en trois temps**, pour une intention CN_A explicite. Il n'importe aucun client Alpaca, n'appelle aucune API d'ordres, ne modifie aucune table et n'est pas planifié. Il réutilise le contrat daté CN du Sprint 12-A ; le replay de portefeuille historique 12-B reste séparé.

```text
Signal daté J (source_ref, instrument_id, marché, MIC, board)
  → plan_shadow_intent : QUEUED ou REJECTED, sans barre J+1
  → séance cible J+1 : assess_shadow_attempt, seulement après observation de la barre
       REJECTED | DEFERRED_T1 | UNVERIFIABLE | NOT_FILLED | HYPOTHETICAL_FILL
  → séance ultérieure : mark_shadow_attempt, comparaison de prix seulement
  → write_shadow_audit : preuve JSON exclusive, jamais écrasée
```

La sortie `HYPOTHETICAL_FILL` signifie uniquement qu'une hypothèse de participation à la barre quotidienne passe les contrôles. Elle ne prouve **ni une transaction, ni le prix d'ouverture accessible, ni le volume disponible à l'ouverture**. Il n'existe pas de méthode `submit_order` dans ce module. Le routeur 18-A continue de refuser `CN_A` pour paper/live.

## Contrat des données et temporalité

`ShadowIntent` contient une identité stable, `market_code=CN_A`, MIC `XSHG` ou `XSHE`, board, horodatage de signal avec fuseau, séance cible strictement postérieure au signal, côté, budget ou quantité et référence de provenance. Un achat nécessite un budget CNY positif sans quantité imposée ; une vente nécessite l'inventaire connu et éventuellement une quantité. Le signal daté J n'utilise jamais la barre de J+1 pour être admis.

`plan_shadow_intent` applique `assess_pretrade` avec les seuls statuts et limites dont `available_at <= signal_at`. Une suspension découverte plus tard ne réécrit pas le plan. Une date de radiation future exige elle aussi une preuve `delisting_available_at`; sans cette preuve le plan échoue fermé plutôt que d'utiliser une information connue a posteriori. La date de radiation est inclusive selon le contrat CN existant.

`ShadowBar` porte la séance cible, l'instrument, le marché explicite `CN_A`, une référence de provenance, `observed_at` horodaté, open/close CNY, volume, statut, politique de limite, indicateurs de verrouillage et drapeau d'événement de facteur non résolu. Une barre US associée par erreur au même ID numérique est refusée. `assess_shadow_attempt` exige une observation **à partir de 15 h Shanghai** de la séance cible : l'open, le volume total et les limites constatées sont des éléments ex post, jamais des features du plan J. L'absence de barre, de volume ou de prix fiable reste visible et ne crée aucun fill.

Les `ExecutionRule` et `CostProfile` doivent être résolus pour le MIC, le board et la date de tentative, idéalement par `resolve_rule` et `resolve_cost_profile` depuis la base CN isolée. Aucune règle 2025 ne se prolonge implicitement sur 2026. Les règles `research_only` et les coûts `RESEARCH_PROXY` demandent chacun un opt-in explicite. La preuve consigne IDs, version de règle, clé et type de profil, empreintes de la décision et de la barre, prix, notionnel, frais détaillés et scénario de participation.

## Décision de tentative

1. Refus de marché/MIC/board étrangers, horaires naïfs, signal le jour même, absence de provenance ou plan altéré.
2. Refus de règle/coût hors période ou d'un proxy sans opt-in.
3. Séance suspendue : `NOT_FILLED`. Limite inconnue/verrouillée, facteur non résolu, open hors tick ou volume indisponible : `UNVERIFIABLE`.
4. Achat : `prepare_buy` arrondit au lot et inclut les frais dans le budget et le cash disponibles. Vente : `prepare_sell` vérifie l'inventaire, la quantité résiduelle et le T+1 ; une vente J de titres acquis J est `DEFERRED_T1`.
5. Si la quantité dépasse la participation hypothétique au volume quotidien (1 % conservateur, 5 % base, 10 % permissif), résultat `NOT_FILLED / PARTICIPATION_CAP`.
6. Sinon, état `HYPOTHETICAL_FILL` uniquement, avec prix proxy open et estimation de frais. Aucun portefeuille réel ou paper n'est modifié.

Un résultat `REJECTED`, `UNVERIFIABLE` ou `NOT_FILLED` ne signifie pas toujours que l'ordre aurait été rejeté par un courtier : ce sont les états **du simulateur** au niveau de preuve disponible. L'absence de carnet d'ordres interdit de conclure à la probabilité réelle d'exécution.

## Rapprochement et audit

`mark_shadow_attempt` exige un `HYPOTHETICAL_FILL`, une **séance ultérieure distincte**, un close observé après clôture, le même instrument, un statut négocié et aucun facteur non résolu. `directional_move_pct` est le mouvement post-tentative favorable à l'achat (`BUY`) ou à la sortie (`SELL`). Ce n'est **pas un PnL réalisé**, ni le rendement d'un portefeuille, ni une confirmation du fill. Les frais de la tentative sont enregistrés séparément.

`write_shadow_audit` écrit un JSON avec `schema_version=cn_shadow_18b_v1`, `not_broker_execution=true`, plan, tentative, barre source complète et marque éventuelle. Le nom de fichier doit être neuf : l'ouverture exclusive refuse tout écrasement. Les empreintes et l'identité de l'intention et de la barre sont revérifiées avant écriture. La persistance d'un vrai journal opérationnel, l'idempotence inter-journées et le rapprochement automatique avec des observations de marché quotidiennes restent à intégrer dans une étape distincte.

## Portée réelle et blocages

18-B livre le **moteur shadow pur et testé**, pas une campagne de trading CN. Aucun signal CN n'est choisi automatiquement : les replays économiques Sprint 13 n'ont pas donné de GO production. Les règles/coûts datés disponibles doivent couvrir chaque nouvelle séance ; un shadow prospectif 2026 ne doit pas reprendre silencieusement des proxys périmés. La collecte 17-C et la migration 17-D conservent leurs gates propres. Il serait prématuré d'installer un batch shadow quotidien ou de connecter le moteur OMS US à CN.

Avant un essai prospectif sur données réelles : définir une politique de signaux figée, qualifier les contrats 2026 et les droits de données, produire les intentions **avant** les observations J+1, archiver chaque preuve sous un ID de run unique, puis rapprocher séparément les barres ultérieures. Un broker CN et toute permission live restent hors périmètre.

## Vérification

`tests/test_cn_shadow_execution_18b.py` couvre le fill proxy, les frais/lot, l'horodatage PIT, la radiation annoncée tard, l'absence de barre, les suspensions/limites, la participation, le T+1, l'opt-in recherche, la règle datée, le rapprochement ultérieur et le refus d'écraser l'audit. Les tests des contrats 12-A, du replay 12-B, du routeur 18-A et de l'exécution US sont exécutés séparément pour éviter une régression.
