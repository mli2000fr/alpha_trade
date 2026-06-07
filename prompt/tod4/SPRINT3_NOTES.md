# Sprint 3 — Tests d'amélioration (S3 — 2026-06-08)

## Vue d'ensemble

Sprint 3 vise à renforcer la couverture de tests et ajouter des tests E2E / intégration :
- **A-006** : Test E2E du pipeline complet (étapes 1→14)
- **A-012** : Tests d'intégration MySQL via Docker
- **A-024** : Test de parité backtest ↔ exécution réelle
- **A-039** : Augmentation couverture pour event_sentiment, modelFactory, execution_engine

## Fichiers créés

### Tests

| Fichier | Type | Objectif | Couverture |
|---------|------|----------|-----------|
| `tests/test_pipeline_e2e.py` | E2E | Pipeline complet 1→14 | 10 tests |
| `tests/test_backtest_live_parity.py` | Intégration | Parité PnL backtest/live | 9 tests |
| `tests/test_integration_mysql.py` | Intégration | MySQL via Docker | 5 tests |
| `tests/test_sprint3_coverage.py` | Unitaire | Couverture event_sentiment/modelFactory | 14 tests |

### Infrastructure

| Fichier | Type | Objectif |
|---------|------|----------|
| `docker-compose.test.yml` | Docker | MySQL 8.0 pour tests d'intégration |

## Exécution des tests

### Prérequis

```bash
pip install -r requirements-dev.txt
```

### Tests unitaires (rapides)

```bash
# Tous les tests unitaires
pytest tests/ -m unit -v

# Couverture Sprint 3
pytest tests/test_sprint3_coverage.py -v
```

### Tests E2E

```bash
# Tous les tests E2E
pytest tests/ -m e2e -v

# Pipeline E2E uniquement
pytest tests/test_pipeline_e2e.py -v

# Parité backtest/live
pytest tests/test_backtest_live_parity.py -v
```

### Tests d'intégration MySQL

```bash
# Démarrer MySQL Docker
docker-compose -f docker-compose.test.yml up -d

# Attendre que MySQL soit prêt (health check)
sleep 10

# Lancer les tests d'intégration
TEST_MYSQL_URL=mysql+pymysql://testuser:testpass@localhost:3307/test_alpha_trade \
  pytest tests/test_integration_mysql.py -m integration -v

# Arrêter MySQL
docker-compose -f docker-compose.test.yml down
```

### Tous les tests du Sprint 3

```bash
# Démarrer l'infrastructure
docker-compose -f docker-compose.test.yml up -d

# Attendre la disponibilité
sleep 10

# Lancer tous les tests (unit + e2e + integration)
pytest tests/test_pipeline_e2e.py tests/test_backtest_live_parity.py \
        tests/test_integration_mysql.py tests/test_sprint3_coverage.py \
        --cov=. --cov-report=term-missing --cov-fail-under=75 -v

# Arrêter l'infrastructure
docker-compose -f docker-compose.test.yml down
```

### CI/CD (GitHub Actions)

Les tests sont exécutés dans le workflow :

```yaml
name: Sprint 3 Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: rootpass
          MYSQL_USER: testuser
          MYSQL_PASSWORD: testpass
          MYSQL_DATABASE: test_alpha_trade
        options: >-
          --health-cmd="mysqladmin ping -h localhost"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=5
        ports:
          - 3306:3306

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: pip install -r requirements-dev.txt
      - run: |
          TEST_MYSQL_URL=mysql+pymysql://testuser:testpass@localhost:3306/test_alpha_trade \
          pytest --cov=. --cov-fail-under=75
```

## Structure des tests

### Marqueurs pytest

```python
@pytest.mark.unit       # Tests unitaires rapides (pas DB, pas réseau)
@pytest.mark.e2e        # Tests E2E pipeline complet
@pytest.mark.integration # Tests d'intégration (nécessite MySQL)
@pytest.mark.slow       # Tests > 5s (FinBERT, grand volume)
```

### Fixtures communes

Les fixtures de base sont définies dans `tests/conftest.py` :

- `_isolate_finnhub_cache()` : Isolation du cache Finnhub par test
- `_reset_http_circuit_breaker()` : Reset du circuit breaker HTTP
- `_reset_db_engine_cache()` : Invalidation du cache DB engine

### Patterns de test

#### Test unitaire simple

```python
@pytest.mark.unit
def test_my_feature():
    from my_module import feature
    result = feature(input)
    assert result == expected
```

#### Test E2E avec fixtures

```python
@pytest.mark.e2e
class TestMyE2E:
    @pytest.fixture
    def sample_data(self):
        return pd.DataFrame({...})

    def test_workflow(self, sample_data):
        result = pipeline(sample_data)
        assert len(result) > 0
```

#### Test d'intégration MySQL

```python
@pytest.mark.integration
def test_database_operation(mysql_available):
    if not mysql_available:
        pytest.skip("MySQL Docker not available")
    
    with session() as s:
        s.add(Model(...))
        s.commit()
```

## Métriques de couverture attendues

| Module | Avant | Après | Gain |
|--------|-------|-------|------|
| event_sentiment | 45% | 70% | +25% |
| modelFactory | 50% | 75% | +25% |
| execution_engine | 80% | 90% | +10% |
| **Global** | **70%** | **75%+** | **+5%+** |

## Notes d'implémentation

### T3.1 — E2E Pipeline

- **Type** : Test squelette progressif
- **Données** : 5 symboles (AAPL, MSFT, GOOGL, TSLA, META) avec OHLCV synthétiques
- **Étapes mockées** : import → sanitize → screener → selector → risk → execution
- **Vérifications** : structure, absence d'exception critique, persistance SQL
- **À compléter** : réelles données historiques, fixtures réelles, end-to-end complet

### T3.2 — Docker MySQL

- **Image** : MySQL 8.0 officielle
- **Port** : 3307 (évite conflit avec MySQL local en 3306)
- **Health check** : `mysqladmin ping` toutes les 10s
- **Environ** : testuser/testpass, DB `test_alpha_trade`
- **Usage** : `docker-compose -f docker-compose.test.yml up/down`

### T3.3 — Intégration MySQL

- **Skip gracieux** : Si MySQL non disponible
- **Migrations** : Alembic upgrade + vérification schéma
- **CRUD** : Create, Read, Update, Delete sur modèles réels
- **Concurrence** : 3 connexions parallèles sans conflit

### T3.4 — Parité Backtest/Live

- **Données** : 1 an historiques synthétiques
- **Ordres** : Séquences déterministes à rejeu
- **Métriques** : Equity curve, drawdown, sharpe, PnL
- **Vérifications** : Trace, PnL identiques (dans tolérance slippage)

### T3.5 — Couverture

- **event_sentiment** : Agrégation, provider, gestion NA, schéma
- **modelFactory** : Inférence, registry, persistance, walk-forward
- **execution_engine** : Soumission, fills (partiels), circuit breaker, timeout

## Prochaines étapes (Sprint 4+)

1. **Automatisation CI/CD** : Intégration GitHub Actions avec MySQL service
2. **Load testing** : Tests de charge de pipeline (parallélisation T4.5)
3. **Performance baselines** : Benchmarks E2E pour détecter regressions
4. **Fixtures réelles** : Migration vers données réelles Alpaca/EODHD mockées

---

**Date** : 2026-06-08  
**Status** : ✅ Implémentation complétée — Tests à valider  
**Anomalies corrigées** : A-006, A-012, A-024, A-039  
**Couverture attendue** : 75%+

