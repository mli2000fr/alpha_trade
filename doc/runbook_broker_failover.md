# Runbook — Broker failover primaire / secondaire

> **Audience** : opérateur Alpha Trade.
> **Périmètre** : incident broker primaire, bascule lecture seule sur broker secondaire.

---

## 1. Doctrine opératoire

- **Broker primaire** : Alpaca.
- **Broker secondaire** : IBKR (lecture seule / secours).
- **Seuil de déclenchement** : 3 erreurs consécutives sur les opérations de lecture critiques.
- **Effet de la bascule** :
  - les **lectures** peuvent être servies par le secondaire ;
  - les **écritures** (`submit_order`, `cancel_order`) restent **suspendues** ;
  - la reprise nécessite une **validation humaine explicite**.

La sentinelle de reprise attendue par le wrapper failover est :

```text
artifacts/failover/RESUME
```

---

## 2. Détection

### Symptômes typiques

- erreurs répétées sur `get_account`, `get_positions` ou `get_orders` côté broker primaire ;
- message critique dans les logs signalant une bascule sur le secondaire ;
- bannière IHM dans `Comptes Alpaca` indiquant que les écritures restent suspendues.

### Vérifications rapides

```powershell
Set-Location "F:\projets"
python -m pytest -o addopts="--tb=short" tests/test_failover_alpaca_to_ibkr.py
Get-ChildItem "F:\projets\artifacts\failover" | Out-String
```

---

## 3. Conduite à tenir

1. **Ne pas relancer d'ordres manuels** tant que le failover est actif.
2. Vérifier si l'incident est limité à Alpaca ou plus large (réseau, DNS, credentials, compte suspendu).
3. Contrôler l'état du compte et des positions via les lectures disponibles.
4. Si la situation reste instable, conserver le mode lecture seule et documenter l'incident.
5. Une fois le primaire redevenu sain, autoriser la reprise en créant explicitement la sentinelle `RESUME`.

---

## 4. Reprise contrôlée

Créer la sentinelle seulement après validation humaine :

```powershell
Set-Location "F:\projets"
New-Item -ItemType Directory -Force -Path ".\artifacts\failover" | Out-Null
Set-Content -Path ".\artifacts\failover\RESUME" -Value "approved=$(Get-Date -Format s)"
```

Le wrapper consomme ensuite cette sentinelle et réarme le circuit breaker.

---

## 5. Post-mortem minimal

Consigner :

- horodatage début/fin d'incident ;
- broker primaire impacté ;
- nombre d'erreurs avant déclenchement ;
- existence ou non d'ordres en attente ;
- justification de la reprise ;
- actions préventives décidées.

