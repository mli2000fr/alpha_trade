# Phase 6 — Implémentation réalisée

Date: 2026-05-03

## Objectif Phase 6

La Phase 6 correspond à une **phase de consolidation research-grade et d’opérabilité** du backtest.

Contrairement aux Phases 2 à 5 et 7, elle n’introduit pas un nouveau flag `phase6_mode` unique. Elle regroupe un ensemble d’améliorations structurelles qui rendent le backtest :

- plus cohérent avec les presets capital du projet ;
- plus explicite sur ses coûts et paramètres ;
- plus utile pour la recherche avancée ;
- plus exploitable depuis l’IHM ;
- plus traçable dans ses rapports et artefacts.

Principe conservé :

- **zéro régression sur le pipeline live** ;
- **défauts neutres** côté backtest ;
- les nouvelles briques avancées restent soit opt-in, soit strictement neutres à leurs valeurs par défaut.

---

## Résumé des livrables Phase 6

### 1. Alignement capital preset entre backfill, backtest et IHM

Un module partagé a été introduit :

- `common/capital_presets.py`

Il fournit désormais un contrat commun pour :

- charger les presets depuis `config/capital_presets.yaml` ;
- résoudre automatiquement un preset depuis `equity`/`capital` ;
- imposer un preset explicite si l’utilisateur le demande ;
- calculer un `capital_preset_fingerprint` ;
- dériver les paramètres screener / selector / backtest à partir du preset.

### Effet côté backtesting

Le backtest et le backfill PIT peuvent maintenant partager une notion cohérente de :

- `capital_preset_key`
- `capital_preset_source`
- `capital_preset_fingerprint`

Cela réduit fortement l’écart entre :

- le backfill `stock_scores_history`,
- le backtest `run`,
- et l’IHM backtesting.

---

### 2. Backfill PIT piloté par preset

La commande :

- `python -m backtesting backfill-scores-history`

supporte désormais explicitement :

- `--capital`
- `--capital-preset-key`

et construit ses paramètres amont à partir du preset résolu.

### Effet

Le backfill PIT n’est plus implicitement figé sur un profil canonique unique. Il peut désormais reconstruire `stock_scores_history` dans un cadre cohérent avec le capital ciblé.

---

### 3. Backtest `run` aligné sur le preset capital

La commande :

- `python -m backtesting run`

porte aussi la notion de preset via :

- `--capital-preset-key`

Le run :

- résout un preset effectif ;
- l’applique aux contraintes backtest si l’utilisateur n’a pas déjà forcé les flags ;
- filtre le chargement PIT via `capital_preset_key` quand disponible ;
- expose le preset et son fingerprint dans `report.json`.

### Effet

Le portefeuille backtesté ne part plus d’un capital ou d’un type de compte potentiellement incohérent avec l’univers PIT chargé.

---

### 4. Coûts explicites et rétrocompatibilité `--fees`

Le backtest supporte maintenant explicitement :

- `--commission-bps`
- `--slippage-bps`

Le flag historique :

- `--fees`

est conservé, mais marqué comme **déprécié**.

### Effet

- les coûts deviennent plus lisibles et plus proches des briques exécution/TCA ;
- le comportement existant reste compatible ;
- le `fees_pct` effectif est dérivé de `commission_bps + slippage_bps`.

---

### 5. Profils backtest et préremplissage non destructif

Un mécanisme de profil a été branché côté CLI avec :

- `--profile`

et application via :

- `backtesting/profiles.py`

### Principe

Le profil peut préremplir certains paramètres, mais **les flags explicitement passés par l’utilisateur restent prioritaires**.

### Effet

On peut lancer un backtest avec un socle de configuration cohérent sans perdre le contrôle fin de la CLI.

---

### 6. Walk-forward et source de score explicite

Le run supporte maintenant :

- `--score-column`
- `--walk-forward-artifacts-dir`

Le replay sait :

- choisir explicitement une colonne de score ;
- privilégier `final_score_walk_forward` quand pertinent ;
- tracer la source effectivement utilisée (`score_source`).

### Effet

Le backtest peut exploiter plus proprement les artefacts de calibration walk-forward sans bricolage implicite.

---

### 7. Reporting enrichi : dividendes, risk-free rate, métriques avancées

Le reporting a été significativement étendu.

#### Nouveaux éléments supportés

- dividendes encaissés (`portfolio_cash_ledger`) ;
- rendement total avec dividendes ;
- `risk_free_rate` annualisé ;
- `Sortino` ;
- `Calmar` ;
- `Ulcer Index` ;
- conservation JSON-friendly de sentinels comme `inf`.

#### Fichiers concernés

- `backtesting/report.py`
- `backtesting/report_schema.py`
- `backtesting/report_schema_pydantic.py`

### Effet

Le `report.json` et l’affichage IHM deviennent nettement plus utiles pour une lecture PM / risk / research.

---

### 8. Métadonnées de reproductibilité

Le backtest supporte désormais :

- `--seed`
- `--risk-free-rate`

et consigne un bloc :

- `run_metadata`

via :

- `backtesting/run_metadata.py`

### Contenu typique

- seed ;
- version Python ;
- plateforme ;
- packages ;
- hash dataset ;
- timestamp de génération.

### Effet

Deux runs deviennent beaucoup plus comparables et auditables.

---

### 9. Microstructure research-grade (Phase B refactor)

Le simulateur supporte désormais un bundle microstructure dédié :

- `backtesting/microstructure.py`

#### Capacités ajoutées

- slippage volume-aware (`fixed`, `linear`, `sqrt`) ;
- `initial_stop_pct` dur ;
- filtre de gap d’ouverture ;
- résolution intra-bar TP/TS avec politiques explicites :
  - `conservative`
  - `tp_first`
  - `ts_first`
  - `random`

### Effet

Le backtest peut modéliser des hypothèses d’exécution plus réalistes tout en restant neutre par défaut.

---

### 10. Risk overlays research-grade (Phase C refactor)

Un bundle dédié a été ajouté :

- `backtesting/risk_overlay.py`

#### Capacités ajoutées

- sizing `equal_weight` / `conviction_weighted` ;
- volatility targeting portefeuille ;
- filtre régime SMA ;
- cap sectoriel ;
- circuit breaker drawdown.

### Effet

Le simulateur peut maintenant tester des variantes de portefeuille plus proches d’un cadre PM réel, sans modifier la pile live.

---

### 11. Analytics, cache, validation statistique

Des briques complémentaires ont été ajoutées ou stabilisées pour la recherche :

- `backtesting/analytics.py`
- `backtesting/cache.py`
- `backtesting/statistical_validation.py`

#### Exemples couverts

- analytics benchmark ;
- attribution sectorielle ;
- tail analytics ;
- cache parquet ;
- bootstrap sur trades ;
- sensibilité paramétrique.

### Effet

Le backtest n’est plus seulement un moteur PnL : il devient un outil de validation research plus complet.

---

### 12. IHM backtesting enrichie

La page `ihm/pages/backtesting.py` et le runner `ihm/services/backtesting_runner.py` exposent désormais les éléments Phase 6, notamment :

- preset capital ;
- score column / walk-forward artifacts ;
- mode moteur ;
- stratégie ML PIT ;
- risk-free rate / seed ;
- microstructure ;
- risk overlays ;
- coûts et output dir.

### Effet

L’IHM backtesting devient un vrai cockpit opérateur/research, sans activer implicitement les modes avancés.

---

## Fichiers principaux concernés

### Créés ou fortement structurants

- `common/capital_presets.py`
- `backtesting/microstructure.py`
- `backtesting/risk_overlay.py`
- `backtesting/run_metadata.py`
- `backtesting/analytics.py`
- `backtesting/cache.py`
- `backtesting/statistical_validation.py`
- `tests/test_backtesting_refactor.py`
- `prompt/backtest/phase6.md`

### Modifiés de façon notable

- `backtesting/cli/_impl.py`
- `backtesting/data_loader.py`
- `backtesting/resilience.py`
- `backtesting/report.py`
- `backtesting/report_schema.py`
- `backtesting/report_schema_pydantic.py`
- `ihm/services/backtesting_runner.py`
- `ihm/pages/backtesting.py`
- `tests/test_backtesting.py`
- `tests/test_ihm_backtesting_runner.py`
- `tests/test_pages_backtesting.py`

---

## Validation exécutée

### Suite refactor exécutée

```powershell
pytest tests/test_backtesting_refactor.py -q --no-cov
```

### Suites ciblées complémentaires déjà validées dans cette séquence

```powershell
pytest tests/test_ihm_backtesting_runner.py tests/test_pages_backtesting.py tests/test_phase2_bridges.py tests/test_backtesting.py -q --no-cov
```

### Résultat

- refactor backtesting : **vert**
- CLI / IHM / bridges / backtesting ciblé : **vert**

---

## Garanties de non-régression live

La Phase 6 reste compatible avec le pipeline live parce que :

1. elle agit principalement sur `backtesting/`, `common/` et l’IHM backtesting ;
2. ses nouveautés sont soit neutres par défaut, soit opt-in ;
3. elle ne remplace pas le runtime live de `risk_management` ni de `execution_engine` ;
4. elle améliore surtout la cohérence documentaire, la traçabilité, le contrôle opérateur et le réalisme research.

---

## Limites connues à la fin de la Phase 6

Malgré cette consolidation, le backtest n’est toujours pas un jumeau live complet.

### Il manque encore notamment

- un replay intraday complet ;
- la microstructure broker réelle ;
- les rejets / latences / états broker exacts ;
- le full lifecycle OMS/EMS avec persistance live native dans la boucle de PnL ;
- la reconstruction complète des étapes live 1→10 à chaque séance de backtest.

---

## Conclusion

La Phase 6 marque une **forte montée en maturité opérationnelle** du backtest.

À ce stade, le projet dispose désormais d’un moteur qui est :

- plus cohérent avec les presets capital du projet ;
- plus explicite sur ses coûts et diagnostics ;
- plus riche pour la recherche ;
- mieux instrumenté pour l’IHM ;
- plus robuste côté reporting, reproductibilité et analyse.

La suite logique après cette consolidation est la **Phase 7**, qui complète le rapprochement execution/backtest en rejouant l’issue terminale explicite des exits et l’annulation OCO du sibling.

