# Audit rapide — cohérence presets capital vs backtesting

Date: 2026-05-02

## Constat actuel

### Pipeline IHM
- Les presets de `config/capital_presets.yaml` sont effectivement chargés et appliqués dans l’IHM pipeline.
- Source de vérité actuelle: `ihm/services/capital_presets.py`.
- Les valeurs preset pilotent réellement les commandes backend `stock_screener`, `alpha_scanner`, `risk_management` et `execution`.

### Backfill `backfill-scores-history`
- Le backfill PIT n’utilise pas `config/capital_presets.yaml`.
- Il instancie aujourd’hui:
  - `ScreenerConfig(chunk_size=args.chunk_size)`
  - `AlphaScannerConfig.strict_swing_cash(chunk_size=args.chunk_size, selection_size=args.selection_size)`
- Donc il reconstruit `stock_scores_history` avec un profil quasi canonique strict, indépendant du capital saisi dans l’IHM backtesting.

### Backtest `run`
- Le backtest utilise bien `equity`, `account_type`, `swing_only`, `max_positions`, etc.
- Mais il lit les candidats depuis `stock_scores_history` sans notion de preset capital.
- Donc le moteur portefeuille peut être configuré pour 2k$ tandis que l’univers PIT provient d’un historique reconstruit avec des filtres plus proches d’un profil 50k–100k / strict.

## Conclusion métier

Oui, il existe une incohérence structurelle live/backfill/backtest.

Le vrai problème n’est pas seulement l’absence d’un champ `capital` dans `backfill-scores-history`, mais le fait que `stock_scores_history` n’est pas versionné par preset et que `backtesting run` ne filtre pas l’historique PIT sur un preset cohérent.

## Option retenue: Option B

Objectif: rendre `backfill-scores-history`, `backtesting run` et l’IHM backtesting cohérents avec `config/capital_presets.yaml`.

## Changements minimaux recommandés

### Schéma
Ajouter à `stock_scores_history`:
- `capital_preset_key`
- `config_fingerprint`

Et faire évoluer l’unicité logique vers:
- `(snapshot_date, capital_preset_key, symbol)`

### Backend / CLI
1. Introduire un module partagé de presets capital, non dépendant de l’IHM Streamlit.
2. Permettre à `backfill-scores-history` d’accepter:
   - `--capital`
   - `--capital-preset-key`
3. Résoudre le preset selon la règle:
   - `capital_preset_key` explicite > résolution par capital > fallback canonique
4. Construire `ScreenerConfig` et `AlphaScannerConfig` depuis le preset.
5. Permettre à `backtesting run` de porter la même notion de preset et de filtrer `load_scores()` sur `capital_preset_key`.

### IHM backtesting
- Ajouter la sélection / résolution de preset dans l’onglet backfill.
- Ajouter la sélection / résolution de preset dans l’onglet backtest.
- Aligner les paramètres visibles clés sur le preset sélectionné quand l’utilisateur ne force pas manuellement autre chose.

## Point de vigilance

Le lecteur `risk_management.db_io.load_candidates_asof()` lit aussi `stock_scores_history` sans filtre de preset. Ce n’est pas le périmètre principal demandé ici, mais il faut éviter qu’un changement de schéma casse son comportement. Une compatibilité legacy explicite devra être conservée.

## Ordre d’implémentation

1. Module partagé `common/capital_presets.py`
2. Colonnes + migration `stock_scores_history`
3. Service backfill PIT + persistance preset/fingerprint
4. CLI `backfill-scores-history`
5. `load_scores()` + CLI `backtesting run`
6. IHM backtesting
7. Tests ciblés

