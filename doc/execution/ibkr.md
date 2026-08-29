# Adaptateur Interactive Brokers (IBKR)

## Statut actuel

`service/ibkr/client.py` utilise `ib_insync`. L’instanciation lève `IBKRUnavailableError` si package ou TWS/Gateway manque. Le défaut `readonly=True` convient au failover. Le code sait aussi soumettre et annuler avec `readonly=False`; cette capacité ne prouve pas une qualification production.

## Connexion

`service/ibkr/credentials.py` lit `IBKR_HOST` (`127.0.0.1`), `IBKR_PORT` (7497) et `IBKR_CLIENT_ID` (1). TWS/Gateway doit autoriser l’API et le client id ne doit pas être en conflit. Ne pas déduire paper/live du port : vérifier la session et le compte retourné.

## Lectures

- compte : NetLiquidation, TotalCashValue, BuyingPower, devise et code ;
- positions : quantité signée, coût moyen, side ;
- ordres : ouverts ou trades, statuts normalisés ;
- flux : callback `orderStatusEvent` avec fonction de désabonnement.

La `market_value` d’une position est coût moyen × quantité absolue dans cet adaptateur ; ce n’est pas un mark-to-market temps réel.

## Écritures

En non-readonly, market, limit, stop et stop-limit sont supportés. Limit/stop exigent leurs prix ; `client_order_id` devient `orderRef`. Un `extra.bracket` avec `take_profit` et `stop_loss` utilise `IB.bracketOrder()` et place les jambes. Vérifier enfants, flags transmit, quantités et OCO dans TWS.

`cancel_order()` cherche un `orderId` entier dans les trades ouverts. Statuts : submitted→accepted, presubmitted→pending, filled→filled, cancelled/API-cancelled→canceled, inactive→rejected, sinon unknown. `unknown` doit bloquer toute automatisation d’écriture.

## Qualification

1. connexion paper readonly et identité compte ;
2. parité compte/positions/ordres ;
3. `tests/test_ibkr_adapter_paper.py` ;
4. écritures paper isolées via `tests/test_ibkr_submit_order_paper.py` ;
5. partial fills, rejets, annulation, reconnect ;
6. bracket/OCO et protections ;
7. réconciliation/kill switch ;
8. revue humaine avant `readonly=False` hors paper.

Voir [failover broker](../operations/broker_failover.md).

