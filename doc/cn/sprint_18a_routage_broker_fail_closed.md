# Sprint 18-A — Contrat broker et verrou de marché

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Résultat et périmètre

Le moteur d'ordres existant reste **US_EQ / Alpaca**. Un contrat d'exécution minimal et un routeur de marché explicite sont introduits dans `execution_engine/broker_router.py`. Une demande `CN_A`, `CN_BJ`, française ou sans marché est refusée **avant** de construire un client broker. L'adaptateur Alpaca applique aussi son propre verrou `US_EQ`, afin qu'un appel direct ne contourne pas le routeur.

Ce sprint ne crée **aucune** route paper/live CN, ne choisit pas de broker chinois et ne change ni les ordres US ni les règles de portefeuille. Le `BrokerClient` partagé de `core/interfaces.py` reste le contrat compte/positions/ordres de la couche service ; `ExecutionBrokerPort` représente le minimum du moteur OMS (intention, consultation, annulation). Les types ne sont pas encore interchangeables : l'OMS possède toujours des méthodes supplémentaires spécifiques à Alpaca (OCO, watcher, prix, synchronisation). Il serait dangereux de prétendre que le seul contrat minimal suffit à les remplacer.

## Chemin actuel

```text
run_execution / cancel-all / watcher
  -> ExecutionConfig(market_code="US_EQ" par défaut)
  -> BrokerRouter.validate() avant création du client
      -> US_EQ + paper/live : adaptateur Alpaca historique
      -> CN_A ou autre : BrokerRouteError, aucun client construit
  -> BrokerAdapter (second verrou US_EQ)
  -> AlpacaTradingClient
```

Le routeur expose aussi `resolve()` pour les nouveaux appelants qui injectent une factory. Le chemin historique `run_execution` conserve l'instanciation de son adaptateur afin de préserver ses doubles de test et son comportement US ; il appelle `validate()` **avant** l'instanciation du client. `cancel-all` et le watcher passent par `resolve()` après cette validation.

Le routeur n'infère jamais un marché à partir d'un ticker : un code explicite est nécessaire. Le marché de configuration est par défaut `US_EQ` uniquement pour garder la compatibilité de l'ancienne CLI US ; ceci **n'autorise pas** à passer une intention CN dans un run US. Le verrou parent marché/instrument des flux d'amont demeure indispensable. Les commandes US existantes ne reçoivent aucun nouveau drapeau.

## Sécurité vérifiée

- La factory US n'est jamais invoquée si le code marché est `CN_A`, `CN_BJ`, `FR_EQ` ou vide.
- Un adaptateur Alpaca instancié directement avec une configuration CN refuse immédiatement.
- Une factory qui ne satisfait pas le contrat de base ou annonce un autre marché est refusée.
- Les modes inconnus sont rejetés par `ExecutionConfig` avant la construction du routeur.
- Aucune configuration live CN n'est activée ; aucun batch, tâche Windows, compte ni ordonnanceur n'est modifié.

## Suite : Sprint 18-B

Le [shadow CN autonome de 18-B](./sprint_18b_shadow_execution_cn.md) est maintenant livré comme moteur pur d'intentions datées, contrôles de lots/inventaire T+1/suspensions/limites, résultat hypothétique et rapprochement des prix suivants. Il faudra encore élargir le contrat OMS aux opérations réellement consommées par le watcher avant toute substitution par `MockBrokerAdapter`/`ReplayBrokerAdapter`. Un shadow n'est ni un paper broker ni une autorisation live.

Le [Sprint 18-D](./sprint_18d_port_oms_et_doubles.md) a depuis étendu `ExecutionBrokerPort` aux opérations effectivement consommées par l'OMS et le watcher et ajouté des doubles mock/replay inertes. Le routeur refuse ces doubles en paper/live. Cela ne choisit toujours pas de broker CN et ne change pas les gates du Sprint 19 : économie, données et droits, broker, rapprochement et décision humaine explicite.
