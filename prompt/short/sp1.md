# Sprint 1 — Synthèse

_Date : 2026-06-18_

## Objectif
Propager le champ `side` dans tout le pipeline risk pour que le système puisse
exprimer « ce ticker est une entrée short ». Valeur par défaut : `"buy"` (rétrocompatible).

## Livrables

### C1 — `side` dans les modèles risk
| Modèle | Fichier | Statut |
|---|---|---|
| `CandidateScore` | `risk_management/models.py` | ✅ `side: str = "buy"` |
| `EnrichedCandidate` | `risk_management/models.py` | ✅ `side: str = "buy"` |
| `PortfolioEntry` | `risk_management/models.py` | ✅ `side: str = "buy"` |
| `RiskDecisionRow` | `risk_management/models.py` | ✅ `side: str = "buy"` |
| `PortfolioTargetRow` | `risk_management/models.py` | ✅ `side: str = "buy"` |

### C2 — Persistance du `side`
| Fichier | Changement |
|---|---|
| `risk_management/audit.py` | `"side": e.side` dans `risk_decisions` et `portfolio_targets` |
| `risk_management/db_io.py` | `"side"` ajouté aux `canonical_columns` des deux writers |

### C3 — Propagation backtest
| Fichier | Changement |
|---|---|
| `backtesting/risk_bridge.py` | `"side"` dans `RISK_SIGNAL_COLUMNS` |
| `backtesting/risk_bridge.py` | `"side": entry.side` dans `portfolio_entries_to_signals()` |

### Propagation dans PortfolioBuilder
| Méthode | Changement |
|---|---|
| `_build_enriched_candidates()` | `side=candidate.side` propagé de CandidateScore → EnrichedCandidate |
| `build()` (main loop) | `side=ec.side` dans `PortfolioEntry(...)` |
| `_make_entry_v2()` | `side=ec.side` dans `PortfolioEntry(...)` |

## Backtest ✅
- `side` est dans les signaux exportés vers le simulateur
- Le simulateur ne le consomme pas encore (Sprint 2)
- Valeur par défaut `"buy"` → comportement long-only inchangé

## Live ✅
- `side` est persisté dans `risk_decisions` et `portfolio_targets`
- `execution_engine/db_io.load_portfolio_targets()` lit déjà la colonne `side` (contrat C2 honoré)
- L'exécution ne consomme pas encore le `side` pour les entrées (Sprint 3)

## Tests
✅ 42/42 existants passent (12 portfolio_builder + 30 regime_scoring)

## Fichiers modifiés
- `risk_management/models.py` — ajout `side` à 5 dataclasses
- `risk_management/portfolio_builder.py` — propagation `side` dans 3 constructeurs
- `risk_management/audit.py` — `side` dans les 2 writers
- `risk_management/db_io.py` — `side` dans les 2 canonical_columns
- `backtesting/risk_bridge.py` — `side` dans RISK_SIGNAL_COLUMNS + export

## Différé au Sprint 2
- Rendre les trackers de concentration side-aware
- Consommer `side` dans le simulateur backtest
- Rendre le sizing et les contraintes side-aware
- Rendre le `DrawdownCircuitBreaker.allocation_scale(side)` directionnel
