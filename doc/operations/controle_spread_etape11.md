# Étape 11 — contrôle optionnel des quotes et du spread

## Réglage

Depuis le 28 octobre 2026, dans `config.yaml` :

```yaml
risk_management:
  quote_spread_check_enabled: false
```

- `false` (défaut demandé) : le risque ne demande plus les dernières quotes SIP
  ou Tradier pour ce contrôle. Il n'exclut plus une entrée pour quote absente, périmée,
  invalide ou spread trop large à cette étape.
- `true` : rétablit la lecture des quotes pour le compte choisi et les refus
  existants, dont `quote_snapshot_manquant` si le fournisseur refuse la lecture.

Le fournisseur se choisit via `market_data.quotes_provider_live` : `alpaca`
(SIP) ou `tradier` (consolidé). Voir [le raccordement Tradier](tradier_quotes.md).
Alpaca reste sélectionné tant que l'accès Tradier n'est pas qualifié.

Le même chemin de l'étape 11 couvre le lancement manuel, `us_pipeline`, le
parcours Oracle seul et les parcours filtres options/LLM. Il faut un nouveau
processus de risque pour lire le réglage ; aucun rapport déjà publié n'est modifié.
La nouvelle valeur fait partie de l'empreinte de la configuration du risque.

Ce réglage ne désactive ni ADV/participation, ni estimation du slippage, ni
borrow pour les shorts, ni capital réel, ni caps du portefeuille. Sans spread
observé, le slippage conserve son estimation de secours existante : aucun
bid/ask ni spread nul n'est inventé. Il ne modifie pas la sélection des fournisseurs
de barres historiques, les critères de données options ou les contrôles d'univers.

Les contrôles distincts avant envoi d'ordre et du watcher restent actifs. Une
exception configurable existe pour l'entrée standard Winner avec
`confirmation_bars: 0` : voir [son réglage dédié](winner_standard_entry_quotes.md).
En dehors de cette exception explicite, une
décision de risque acceptée peut donc encore être bloquée avant achat faute de
quote récente qualifiée. Le réglage n'accorde pas l'accès SIP et ne constitue
pas une désactivation générale des gardes d'exécution.

## Pourquoi utiliser le spread ?

Le prix acheteur (bid) est celui proposé par un acheteur, le prix vendeur (ask)
celui demandé par un vendeur. Leur écart représente un coût immédiat potentiel
et un indice de liquidité. Les barres daily OHLCV ne décrivent pas cet écart
courant. Le contrôle sert à éviter une entrée dans un marché trop cher ou mal coté.

## Motif du HTTP 403 constaté

Une lecture réelle, uniquement GET, sur le compte `default` pour MRVL le
28 octobre a renvoyé **403**, message exact :
`subscription does not permit querying recent SIP data`.

Selon la [FAQ Alpaca](https://docs.alpaca.markets/us/docs/market-data-faq),
les trades/quotes SIP des quinze dernières minutes nécessitent un abonnement.
Le [plan Algo Trader Plus](https://docs.alpaca.markets/us/docs/about-market-data-api)
est affiché à **99 USD/mois** lors de cette vérification. Le plan Basic donne
accès au temps réel IEX et à l'historique SIP différé ; l'accès aux barres SIP
historiques ne donne donc pas accès aux dernières quotes SIP. Aucun abonnement
n'a été souscrit et aucun repli IEX n'a été ajouté.

## Audit et validation

Le résumé de risque conserve dans `liquidity_market_data` :

- `quote_spread_check_enabled` : réglage effectif ;
- `quote_spread_checked` : contrôle de quotes actif dans ce calcul ;
- `spread_symbols_loaded` : nombre de quotes chargées ;
- `liquidity_gate_active` : autres contrôles de liquidité toujours actifs.

Les décisions de liquidité exposent aussi `quote_spread_checked`. La combinaison
`spread_ok=true` et `quote_spread_checked=false` signifie « pas de veto spread,
contrôle non effectué », sans certification du spread.

Les tests vérifient l'absence totale d'appel quotes lorsque désactivé, le retour
du veto si activé sans quote, les quotes larges/périmées, la conservation des
refus ADV/participation/slippage/borrow et le maintien du contrôle avant envoi.
**319 tests passent** sur le nouveau réglage, la liquidité, la configuration,
le CLI risque, le capital broker, le portefeuille, les données opérationnelles
et les commandes de la page Pipeline.
Aucun ordre ni recalcul d'une ancienne décision n'a été lancé pour cette modification.
