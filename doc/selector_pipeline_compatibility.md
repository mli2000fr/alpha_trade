# Compatibilité pipeline `screener` → `selector` → `modelFactory`

## 1. Objet

Cette note synthétise l’état de compatibilité autour des enrichissements récents du `selector` :

- mode d’ablation shadow ;
- data quality gate / `skipped_filters` ;
- colonnes d’explicabilité persistées dans `stock_scores` / `stock_scores_history`.

## 2. Amont : compatibilité `screener` → `selector`

### Compatible

- Le `screener` et le `selector` restent alignés sur la même source de vérité métier pour le preset strict via `core/filter_profiles.py`.
- `screener/db_io.py` archive déjà les colonnes selector enrichies lorsqu’elles existent dans `stock_scores` **et** `stock_scores_history`.
- L’archivage est tolérant au schéma courant grâce à l’introspection SQL : seules les colonnes présentes des deux côtés sont copiées.
- `selector/db_io.py` persiste lui aussi de manière tolérante au schéma via introspection, donc un schéma partiellement migré ne casse pas le run par défaut.

### Point d’attention

- Le contrat opérationnel reste : **`screener` doit précéder `selector`** dans le pipeline quotidien.
- Si on relance `screener` seul après un run `selector`, les colonnes selector déjà présentes dans `stock_scores` ne sont pas explicitement remises à zéro par `screener` ; elles seront réécrites proprement au prochain run `selector`.

## 3. Aval : compatibilité `selector` → `modelFactory`

### Compatible

- `modelFactory` charge aujourd’hui son univers via `stock_scores.is_candidate = 1`.
- Le module aval n’échoue pas quand `stock_scores` contient plus de colonnes : les colonnes selector supplémentaires sont donc **compatibles schéma**.
- Le chargement de l’univers d’entraînement reste piloté par :
  - `database.stock_scores.list_candidate_symbols(...)`
  - `modelFactory.db_registry.load_candidate_symbols(...)`

### Exploitabilité actuelle

Les nouveaux champs selector sont désormais directement chargeables pour l’univers candidat via :

- `database.stock_scores.load_candidate_selector_context(...)`
- `modelFactory.db_registry.load_candidate_selector_context(...)`

Champs exposés si présents dans le schéma courant :

- `trend_score`, `vcp_score`, `final_score`
- `market_cap`, `beta_126`, `spread_bps`
- `earnings_date`, `days_to_earnings`, `earnings_blackout`
- `candidate_rank`, `raw_final_score`
- `normalized_total_score`, `normalized_rsi`
- `total_score_neutralized`, `relative_strength_index_neutralized`
- `trend_vcp_component`, `total_score_component`, `rsi_component`
- `atr_pct_20`, `weekly_trend_score`, `high_52w_proximity`, `volatility_ratio`
- `selector_signal_mode`, `selection_explanation`

## 4. Conclusion

- **`screener` → `selector` : compatible** dans l’ordre de pipeline prévu.
- **`selector` → `modelFactory` : compatible schéma**, avec lecture de l’univers inchangée.
- **Les nouveaux champs selector sont exploitables côté `modelFactory`**, mais ils ne sont pas encore branchés automatiquement dans la feature engineering ou l’orchestration d’entraînement : une utilisation métier ultérieure devra les connecter explicitement aux features / labels concernés.

