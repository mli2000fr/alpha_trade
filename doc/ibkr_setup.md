# Configuration TWS / IB Gateway pour Alpha Trade — Sprint S21.3

Ce document décrit la qualification d'un environnement Interactive Brokers
**paper trading** afin d'exécuter le test live
[`tests/test_ibkr_submit_order_paper.py`](../tests/test_ibkr_submit_order_paper.py)
et plus largement l'adapter [`service/ibkr/client.py`](../service/ibkr/client.py).

---

## 1. Pré-requis

| Composant | Version recommandée |
|---|---|
| Trader Workstation (TWS) ou IB Gateway | ≥ 10.19 (paper) |
| Compte IBKR **paper** activé | gratuit via `Account Management → Settings → Paper Trading Account` |
| Python | 3.11+ |
| Dépendance Python | `pip install ib_insync>=0.9.86` |

> **Hors-périmètre** : market data subscriptions IBKR (l'adapter ne les
> requiert pas pour `submit_order` / `cancel_order` ; les ordres sont
> placés sans cotation temps-réel).

---

## 2. Configuration TWS / Gateway

### 2.1 Activer l'API

`File → Global Configuration → API → Settings`

- ✅ `Enable ActiveX and Socket Clients`
- ❌ `Read-Only API` (sinon `submit_order` est bloqué côté serveur)
- `Socket port` :
  - **TWS paper** : `7497`
  - **TWS live** : `7496`
  - **IB Gateway paper** : `4002`
  - **IB Gateway live** : `4001`
- ✅ `Allow connections from localhost only` (recommandé)
- `Master API client ID` : laisser vide ; on choisira par variable d'env.
- ✅ `Bypass Order Precautions for API Orders` (paper uniquement, pour
  contourner les confirmations modales TWS).

### 2.2 Trusted IPs (si exécution distante)

Ajouter l'IP du runner CI dans `Trusted IPs` puis redémarrer TWS.

### 2.3 Auto-restart quotidien

TWS impose une déconnexion quotidienne (~23h UTC). Configurer
`Lock and Exit → Auto restart` pour éviter une coupure manuelle.

---

## 3. Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `IBKR_PAPER_HOST` | _absent → test skip_ | Host TWS (ex. `127.0.0.1`). |
| `IBKR_PAPER_PORT` | `7497` | Port socket. |
| `IBKR_PAPER_CLIENT_ID` | `11` | `clientId` unique par session (ne pas réutiliser un id occupé). |

PowerShell :

```powershell
$Env:IBKR_PAPER_HOST = "127.0.0.1"
$Env:IBKR_PAPER_PORT = "7497"
$Env:IBKR_PAPER_CLIENT_ID = "11"
```

---

## 4. Exécution du test paper

```powershell
pytest -m live tests/test_ibkr_submit_order_paper.py -v
```

Le test :

1. Soumet un ordre **limit BUY 1 AAPL @ 1.00 USD** (hors marché — ne
   se remplira jamais).
2. Vérifie que le `BrokerOrderSnapshot` retourné a un `order_id` et un
   statut dans `{new, accepted, pending}`.
3. Annule l'ordre via `cancel_order(snap.order_id)`.
4. Vérifie que l'annulation est confirmée.

---

## 5. API supportée

| Méthode | Statut | Notes |
|---|---|---|
| `get_account` | ✅ | `accountSummary` agrégé |
| `get_positions` | ✅ | `positions()` |
| `get_orders` | ✅ | `openTrades()` / `trades()` |
| `submit_order` | ✅ S21.3 | `market`, `limit`, `stop`, `stop_limit` ; bracket via `request.extra["bracket"]` |
| `cancel_order` | ✅ S21.3 | par `orderId` numérique |
| `stream_trades` | ✅ S21.3 | abonnement à `orderStatusEvent` |

### 5.1 Bracket OCO IBKR natif

```python
from decimal import Decimal
from core.broker_models import OrderRequest

req = OrderRequest(
    symbol="AAPL",
    qty=Decimal("10"),
    side="buy",
    type="limit",
    limit_price=Decimal("180.00"),
    time_in_force="day",
    extra={"bracket": {"take_profit": 200.0, "stop_loss": 170.0}},
)
client.submit_order(req)
```

L'adapter délègue à `ib_insync.IB.bracketOrder()` qui crée 3 ordres
chaînés (parent limit + take-profit + stop-loss) — l'OCO est gérée
côté serveur IBKR.

---

## 6. Limitations connues

- **Pas de fractional shares** sur les ordres IBKR paper avant
  `Account Management → Configure → Allow fractional shares for paper`.
- **TIF `opg`/`cls`** : non testés (réservés à `OPG` MOO/MOC).
- **Combos / FX / Futures** : `_build_contract` est limité à `STK` ;
  pour étendre, surcharger via une factory custom.
- **Multi-account** : `accountSummary()` agrège le compte par défaut ;
  pour un sous-compte, utiliser `clientId` distinct.

---

## 7. Dépannage rapide

| Symptôme | Cause probable | Action |
|---|---|---|
| `IBKRUnavailableError: ib_insync` | paquet absent | `pip install ib_insync` |
| `Connexion TWS impossible` | TWS fermé / port mauvais | Vérifier section 2.1 |
| `Read-Only API` | option API en lecture seule | Décocher dans TWS |
| `Order rejected: 200` | symbole inconnu | Vérifier `primaryExchange` |
| `Already connected with clientId=N` | clientId réutilisé | Choisir un autre `IBKR_PAPER_CLIENT_ID` |

---

## 8. Références

- ib_insync docs : <https://ib-insync.readthedocs.io/>
- IBKR API guide : <https://interactivebrokers.github.io/tws-api/>
- Plan parent : `prompt/tod/28_plan_10_10_2.md` §3 S21.3.

