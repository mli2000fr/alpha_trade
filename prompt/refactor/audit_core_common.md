# Audit — `core` & `common`

> Périmètre : `core/__init__.py`, `core/interfaces.py`, `common/utils.py`.
> Sources : code listé.

> Note : modules transverses minimalistes. Cet audit est court.

---

## 1. Résumé exécutif

`core/` et `common/` sont les **modules transverses bas niveau** :
- `core/interfaces.py` : interfaces Protocol partagées (`BrokerPort`,
  `MarketDataPort`, etc. — à confirmer dans le code).
- `common/utils.py` : helpers utilitaires (`configure_root_logging`, helpers de
  date marché, etc.).

État global : **fondations correctes mais sous-utilisées**. La doc
`DOC_TECHNIQUE.md` mentionne `core/interfaces.py` comme l'emplacement
recommandé pour les futures interfaces de découplage (cf. dette technique P2).
Aujourd'hui, beaucoup de modules importent directement les implémentations
concrètes au lieu de Protocols → couplage fort.

Principaux risques :

1. **`core/interfaces.py` peu peuplé / peu utilisé** : les Protocols qui devraient
   exister (`BrokerPort`, `MarketDataPort`, `BarsRepository`, `OrderExecutor`)
   ne sont pas tous matérialisés ou pas tous consommés.
2. **`common/utils.py` est un fourre-tout** : risque de dérive en "utility hell".
3. **Pas de documentation dédiée** (`doc/core.md`, `doc/common.md` n'existent pas).

Priorités immédiates :
- Inventorier les Protocols utiles à introduire.
- Découper `common/utils.py` par responsabilité (`common/logging.py`,
  `common/calendar.py`).

---

## 2. Constat détaillé

### 2.1 `core/interfaces.py`

| Constat | Doit héberger les Protocols permettant le découplage entre couches métier
et infrastructures (broker, market data, repositories). Aujourd'hui peu peuplé. |
| Risque | **Architecture / maintenabilité** : sans Protocols, un changement de
broker ou d'API data demande un refactor cross-modules. |
| Recommandation | Introduire au minimum :
  - `BrokerPort` (consommé par `execution_engine`)
  - `MarketDataPort` (consommé par `dataIntegrityEngine`, `screener`,
    `selector`, `backtesting`)
  - `BarsRepository` (consommé par tous)
  - `ScoresRepository`, `RiskRepository`, `ExecutionRepository`
  - `NewsProvider` (consommé par `event_sentiment`)
  - `CorporateActionProvider` (consommé par `corporate_actions`).
  Chacune mockable en test. |

### 2.2 `common/utils.py`

| Constat | Helpers dont `configure_root_logging`, helpers de marché. |
| Risque | **Maintenabilité** : si plusieurs concepts cohabitent (logging + dates
+ chemins + ...), le module devient un dépotoir. |
| Recommandation | Découper :
  - `common/logging.py` : configuration logs.
  - `common/calendar.py` : helpers dates marché (déjà en partie redondant avec
    `event_sentiment/trading_calendar.py` — à dédupliquer).
  - `common/io.py` : helpers fichiers / artefacts.
  - `common/types.py` : types communs (`AccountId`, `Symbol`, `RiskRunId`...). |

### 2.3 Absence de doc

| Constat | Pas de `doc/core.md` ni `doc/common.md`. |
| Recommandation | Documenter formellement les Protocols et leur usage (cf. plan
d'action global). |

---

## 3. Risques prioritaires

### Élevé
- Couplage fort entre couches métier et implémentations (faute de Protocols matérialisés).

### Modéré
- `common/utils.py` fourre-tout.
- Pas de documentation dédiée.

### Faible
- Pas de versioning des interfaces.

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

`core` et `common` n'ingèrent pas de données. Mais c'est **précisément** dans
`core/interfaces.py` qu'il faut formaliser le `MarketDataPort` qui permettra de
brancher une seconde source (Stooq, Yahoo) en complément d'Alpaca IEX (cf.
audits `dataIntegrityEngine`, `service`, `backtesting`).

---

## 5. Choix recommandé `split_adjusted` vs `all`

Sans impact direct, mais le `MarketDataPort` doit exposer ce paramètre :

```python
# core/interfaces.py
class MarketDataPort(Protocol):
    def fetch_bars(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        *,
        adjustment: Literal["split", "all", "raw"] = "split",
        feed: Literal["iex", "sip"] = "iex",
    ) -> list[Bar]: ...
```

Cela rend le choix `split_adjusted` explicite et typed.

---

## 6. Quick wins

1. **Introduire les Protocols clés** dans `core/interfaces.py`.
2. **Découper `common/utils.py`** en sous-modules.
3. **Créer `doc/core.md`** documentant les Protocols.
4. **Centraliser `common/types.py`** (`AccountId`, `Symbol`, etc.).
5. **Dédupliquer `trading_calendar`** entre `event_sentiment` et `common`.

## 7. Recommandations structurelles

1. **Discipline d'usage** : tout nouveau module métier importe **les Protocols**,
   jamais les implémentations directes. À enforcer en revue de code.
2. **Tests "Protocol contracts"** : un test générique par Protocol qui vérifie
   que toute implémentation respecte la sémantique attendue.

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 3, 4, 5.

### Moyen terme
- Tests contracts Protocol.
- Discipline d'import enforcée (linter custom ou import-linter).

### Long terme
- Inversion de dépendance complète : `database/`, `service/` n'ont **plus** d'API
  publique consommée directement par les modules métier ; tout passe par
  `core/interfaces.py`.

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Probablement minimalistes. **Manque** :
  - tests Protocol contracts.
  - tests d'import-linter (interdire `from execution_engine.broker_adapter import
    AlpacaTradingClient` dans un module métier).

### Documentation
- **Manque** complètement :
  - `doc/core.md` listant les Protocols et leur usage.
  - `doc/common.md` documentant `configure_root_logging` et autres utils.



---

## Statut Phase 2.1 (refactor) � termine

- core/interfaces.py : Protocols centralises (BrokerPort, MarketDataPort, BarsRepository, ScoresRepository, RiskRepository, ExecutionRepository, NewsProvider, CorporateActionProvider, ConvictionAggregator) corrige en Phase 2.1.
- core/conviction.py : formule de fusion partagee corrige en Phase 2.1.
- core/filter_profiles.py : profil partage (re-export STRICT_SWING_CASH_FILTERS) corrige en Phase 2.1.
- common/utils.py decoupe en common/logging_setup.py + common/market_calendar.py + common/config_loader.py (facade retrocompatible) corrige en Phase 2.1.
- doc/core_common.md cree (Phase 2.1).
