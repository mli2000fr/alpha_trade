# Politique de stabilité API v1.0

> Phase C / S18.2.

## Périmètre v1.0

Modules figés en API publique stable :

* `core/` — types fondamentaux, interfaces (`BrokerClient`, etc.).
* `service/` — adaptateurs broker, providers, cache (factory uniquement).
* `risk_management/` — moteur de risque (`PositionSizer`, `RiskConfig`,
  `CircuitBreaker`).

Modules **internes** (peuvent évoluer sans préavis) : `screener/`,
`selector/`, `ihm/`, `backtesting/`, `modelFactory/`, `corporate_actions/`,
`execution_engine/` (sauf `BrokerClient`).

## Versionnement

Semver strict :

* **MAJOR** : changement breaking d'API publique.
* **MINOR** : ajout d'API publique rétrocompatible.
* **PATCH** : bugfix sans changement d'API.

## Procédure de dépréciation

1. Marquer le symbole avec `@deprecated_v1(reason=, since=, removal="2.0")`.
2. Documenter dans `CHANGELOG.md`.
3. Maintenir au moins une version MINOR avant suppression.

```python
from core._deprecation import deprecated_v1

@deprecated_v1(reason="utilisez new_helper()", since="1.1")
def old_helper():
    ...
```

## Symboles privés exposés

Tout module `_private` ou symbole avec un underscore initial est
**privé**. L'usage hors du module d'origine déclenchera une
`DeprecationWarning` v1.x puis une suppression v2.0.

## Vérification CI

`tests/test_api_v1_stability.py` (golden file) verrouille les
signatures publiques. Tout changement non-rétrocompatible casse ce
test ⇒ revue obligatoire.

## Politique de support

| Version | Statut | Support |
|---|---|---|
| v1.x | actuelle | bugfix + sécurité |
| v0.x | obsolète | aucun |

