# Plan Short / Long — Comparaison doc vs code

Date: 2026-07-03
Périmètre: scoring long/short, sentiment, ML, risk management, cohérence live/backtest

## 1. Résumé exécutif

Le document métier `doc/synthese_long_short.md` est globalement solide et reflète correctement l'intention du système.

Les points suivants sont bien alignés entre doc et code:

- Le score long repose bien sur la composition `trend/vcp + total_score + RSI` avec normalisation et neutralisation sectorielle.
- Le `short_score` dédié existe bien et n'est pas un simple bottom-N du score long.
- Le sentiment est bien fusionné dans une logique ternaire `quant + sentiment + macro`, avec poids par défaut `1.00 / 0.00 / 0.00`.
- Le backtest PIT consomme bien une cascade de score de type `walk_forward -> sentiment -> final_score`.
- La conviction long/short est bien implémentée avec un mix quant/ML en `70/30`.

En revanche, plusieurs écarts runtime rendent aujourd'hui le système moins cohérent que ne le laisse penser le document.

Le problème principal n'est pas l'architecture conceptuelle. Le problème principal est la fidélité entre l'intention métier et certains chemins d'exécution live/short.

## 2. Points cohérents doc / code

### 2.1 Score long

Constat:

- `selector/ranking.py` compose bien le score final à partir de `trend_score`, `vcp_score`, `total_score` et `relative_strength_index`.
- `selector/ranking.py` applique bien une neutralisation sectorielle cross-sectionnelle.
- `selector/ranking.py` réalise bien une sélection finale avec plafond sectoriel.

Conclusion:

La partie long du document est globalement fidèle au code.

### 2.2 Score short dédié

Constat:

- `selector/short_score.py` implémente bien un score baissier composite indépendant.
- `selector/ranking.py` contient bien `rank_and_select_short()`.
- `selector/scanner.py` enrichit bien les candidats avec `short_score` quand le contexte de prix est disponible.

Conclusion:

Le design short existe réellement et n'est pas cosmétique.

### 2.3 Sentiment et poids par défaut

Constat:

- `core/conviction.py` contient bien la fusion ternaire `fuse_sentiment()`.
- `event_sentiment/signal_aggregator.py` expose bien un `SentimentBoostConfig` avec:
  - `sentiment_weight = 0.00`
  - `macro_sector_weight = 0.00`
  - `quant_weight = 1.00`
- `event_sentiment/signal_aggregator.py` tient bien compte de `signal_active` et du fallback neutre quand le signal n'est pas actif.

Conclusion:

Le document est cohérent avec le code sur le fait que le sentiment est présent mais désactivé par défaut en production.

### 2.4 Backtest PIT

Constat:

- `backtesting/data_loader.py` charge bien `stock_scores_history` en priorité.
- `risk_management/db_io.py` charge bien les candidats PIT via `COALESCE(final_score_walk_forward, final_score_sentiment, final_score)`.
- `backtesting/data_loader.py` et `risk_management/db_io.py` matérialisent bien la logique de fallback décrite dans le document.

Conclusion:

Le socle PIT/backtest est crédible et bien pensé.

## 3. Anomalies et incohérences confirmées

### 3.1 Anomalie P0 — Kelly short potentiellement sizé avec la mauvaise probabilité — ✅ CORRIGÉ (2026-07-03)

**Fichier** : `risk_management/portfolio_builder.py` (lignes ~318-348)

**Correction** : Introduction d'une variable `effective_proba`. Shorts → `proba_short`, longs → `predicted_proba`. Effet cascade sur Kelly sizing (ligne 660) et audit (lignes 727-729).

Constat:- `risk_management/portfolio_builder.py` calcule bien la conviction short avec `proba_short`.
- Mais l'objet enrichi conserve `predicted_proba` générique.
- Le sizing Kelly appelle ensuite `KellySizer.compute(pi, ec.predicted_proba, ec.historical_win_rate)`.
- `risk_management/kelly.py` calcule `p_eff` à partir de cette seule `predicted_proba`.

Risque:

- En mode ternaire, si `predicted_proba` correspond à la proba long, un short peut être dimensionné avec un signal opposé à celui utilisé pour sa conviction.
- Cela casse la cohérence entre ranking, conviction et sizing.

Impact métier:

- Taille de position short potentiellement erronée.
- Risque de sous-allocation des bons shorts ou sur-allocation des mauvais shorts.

Verdict:

- Bug de cohérence fonctionnelle probable.

### 3.2 Anomalie P0 — Rescoring régime live reconstruit des facteurs vides — ✅ CORRIGÉ (2026-07-03)

**Fichier** : `risk_management/portfolio_builder.py` (lignes ~137-198 supprimées)

**Correction** : Suppression du bloc de rescoring factice (−60 lignes). Le régime directionnel est déjà appliqué en amont par le selector avec de vraies colonnes. Le PortfolioBuilder conserve uniquement les filtres événementiels (`earnings_shield`, `buyback_blackout`, `yield_filter`).

Constat:

- `risk_management/portfolio_builder.py` reconstruit un DataFrame intermédiaire avant `apply_regime_weights()`.
- Ce DataFrame injecte notamment:
  - `trend_score = 0.0`
  - `vcp_score = 0.0`
  - `relative_strength_index = 0.0`
  - `market_cap = None`
  - `beta_126 = None`
  - `volatility_ratio = None`
- `selector/regime_scoring.py` attend précisément ces colonnes pour recalculer les composantes directionnelles et défensives du score.

Risque:

- Le rescoring de régime live ne reflète pas réellement le design décrit dans le document.
- Les poids de régime peuvent s'appliquer à des colonnes nulles ou artificielles.

Impact métier:

- L'effet du régime en live est probablement plus faible, plus bruité, ou tout simplement faux.
- Le document surestime la fidélité de cette brique côté runtime live.

Verdict:

- Incohérence d'implémentation importante entre intention et exécution.

### 3.3 Anomalie P1 — Un chemin live short dégrade le `short_score`

Constat:

- `selector/short_score.py` n'active les jambes `prix < SMA50` et `prix < SMA200` que si les SMA et `last_close` sont présents.
- `selector/scanner.py` enrichit correctement le `short_score` quand `close_df` et `trade_day` sont disponibles.
- Mais `risk_management/cli.py` appelle `enrich_with_short_score(candidates_df)` sur un DataFrame minimal contenant seulement `symbol`, `sector`, `score`, `side`, `predicted_side`.

Risque:

- Dans ce chemin live, les deux composantes SMA du `short_score` ne sont probablement pas actives.
- Le score short devient un score partiel centré sur trend/RSI.

Impact métier:

- Divergence entre score short live, score short backtest et score short documenté.
- Sélection short moins stable et moins explicable.

Verdict:

- Incohérence réelle entre plusieurs pipelines short.

### 3.4 Anomalie P1 — Multiplication des chemins short

Constat:

- Le short est construit à plusieurs endroits:
  - `selector/scanner.py`
  - `backtesting/risk_bridge.py`
  - `risk_management/cli.py`
  - ~~`_tag_short_candidates()` dans `backtesting/risk_bridge.py`~~ → ✅ DÉPLACÉ vers `selector/short_score.py:tag_short_candidates()` (2026-07-03)
- Ces chemins n'ont pas exactement les mêmes inputs ni les mêmes enrichissements.

Risque:

- Une correction dans un pipeline peut ne pas corriger les autres.
- Le comportement long/short devient difficile à auditer et à tester.

Impact métier:

- Écarts live/backtest.
- Explicabilité réduite.
- Risque de régression élevé.

Verdict:

- Dette d'intégration importante.

## 4. Avis professionnel

### 4.1 Ce qui est bon

- L'architecture globale est sérieuse.
- La séparation entre live, backtest et calibration est mature.
- La logique PIT est bien comprise et correctement matérialisée dans les loaders.
- Le document métier est riche, précis, et généralement mieux structuré que beaucoup de codebases comparables.
- La prudence sur le sentiment et le poids du ML est saine.

### 4.2 Ce qui doit être corrigé

- Le système souffre moins d'un problème de modèle que d'un problème de cohérence entre chemins runtime.
- Le short n'est pas encore suffisamment unifié.
- Le rescoring de régime côté portefeuille live doit être durci ou simplifié.
- Les signaux utilisés pour conviction, sélection, sizing et audit doivent être alignés de bout en bout.

### 4.3 Jugement global

Mon avis professionnel est positif sur la vision produit et la qualité du design métier.

Mon avis est plus réservé sur la fiabilité opérationnelle de certains chemins live/short. En l'état, le document décrit correctement l'intention du système, mais pas toujours son comportement effectif sur tous les flux d'exécution.

En synthèse:

- Le document est globalement crédible.
- Le backtest paraît plus fidèle que certains chemins live.
- Les corrections prioritaires doivent cibler la cohérence short et la cohérence du rescoring régime.

## 5. Plan d'action priorisé

### P0 — Corriger la cohérence short conviction / sizing

Objectif:

- Garantir qu'un short utilise la même information ML pour la conviction et pour le sizing.

Actions:

1. Étendre le modèle de données enrichi pour porter explicitement:
   - `predicted_proba_long`
   - `predicted_proba_short`
   - éventuellement `predicted_side`
2. Modifier `risk_management/portfolio_builder.py` pour que:
   - les longs passent `proba_long` au Kelly
   - les shorts passent `proba_short` au Kelly
3. Modifier l'audit de sortie pour journaliser la probabilité réellement utilisée au sizing.

Tests requis:

1. Test unitaire: short ternaire avec `proba_short=0.72` et `proba_long=0.18`.
   Le Kelly doit utiliser `0.72`.
2. Test unitaire: long ternaire avec `proba_long=0.68`.
   Le Kelly doit utiliser `0.68`.
3. Test de non-régression binaire: le comportement long ne doit pas changer.

Critère de réussite:

- La probabilité utilisée pour la conviction et celle utilisée pour le sizing sont identiques par direction.

### P0 — Corriger ou neutraliser le rescoring régime live

Objectif:

- Supprimer le faux rescoring de régime à partir de colonnes reconstruites artificiellement.

Actions possibles:

Option A — Recommandée:

1. Faire porter aux `CandidateScore` les colonnes nécessaires au rescoring réel:
   - `trend_score`
   - `vcp_score`
   - `relative_strength_index`
   - `total_score`
   - `market_cap`
   - `beta_126`
   - `volatility_ratio`
   - `spread_bps`
   - `atr_pct_20`
2. Propager ces champs depuis la source PIT/live jusqu'au `PortfolioBuilder`.
3. Laisser `apply_regime_weights()` travailler sur de vraies données.

Option B — Acceptable si refactor plus long:

1. Désactiver le rescoring régime dans `PortfolioBuilder`.
2. Ne garder côté portefeuille que:
   - filtres événementiels
   - garde-fous de régime
3. Déplacer le rescoring complet plus amont, dans le selector uniquement.

Tests requis:

1. Test unitaire: `capital_preservation` doit modifier `final_score` à partir de vraies colonnes.
2. Test d'intégration live: les composantes défensives doivent être non nulles quand les données existent.
3. Test de cohérence: même entrée de facteurs, même `final_score` en selector et en portefeuille.

Critère de réussite:

- Le régime ne s'applique plus à des colonnes artificielles.

### P1 — Unifier le calcul short

Objectif:

- Avoir une seule vérité pour le `short_score` et son tagging, en live comme en backtest.

Actions:

1. Extraire un service unique de préparation short, par exemple:
   - `selector/short_pipeline.py`
2. Faire consommer ce service par:
   - `selector/scanner.py`
   - `risk_management/cli.py`
   - `backtesting/risk_bridge.py`
3. Interdire les enrichissements short partiels sans SMA/prix, sauf fallback explicite et loggé.
4. Ajouter un champ d'audit indiquant si le `short_score` est:
   - `full`
   - `partial_missing_price`
   - `partial_missing_sma`

Tests requis:

1. Même dataset d'entrée, même `short_score` en live et en backtest.
2. Test de fallback: si SMA absentes, le système doit soit refuser le score short, soit le logger comme partiel.

Critère de réussite:

- Un seul comportement short observable pour une même entrée.

### P1 — Réduire la dispersion des chemins de décision  ✅ FAIT (2026-07-03)

Objectif:

- Limiter la logique de sélection directionnelle à un petit nombre de modules canoniques.

Actions:

1. ✅ Définir explicitement les responsabilités:
   - selector = score et ranking
   - risk = conviction, filtres, sizing
   - backtest = replay fidèle, pas logique alternative
2. ✅ Déplacer `_tag_short_candidates()` vers un module canonique partagé — FAIT (2026-07-03) : fonction renommée `tag_short_candidates()`, réside dans `selector/short_score.py`. Imports mis à jour dans `backtesting/risk_bridge.py` et `risk_management/cli.py`.
3. ✅ Éviter les logiques embarquées dans le CLI quand elles décident le comportement métier — FAIT (2026-07-03) : tous les helpers de décision extraits dans `selector/short_score.py` :
   - `ShortTrigger` (dataclass) + `resolve_short_trigger()` : détection unifiée des déclencheurs (régime, rotation, longs bloqués)
   - `resolve_regime_adaptive_short_params()` : boost capital_preservation unifié (max→4, min→0.20)
   - `inject_predicted_side()` : injection ML unifiée
   - Suppression du `score_col` fallback mort dans `risk_bridge.py` (~7 lignes)
   - `~70 lignes` de logique métier dupliquée retirées du CLI

Architecture résultante :

```
selector/short_score.py  ←  module canonique UNIQUE
├── ShortTrigger (dataclass)
├── resolve_short_trigger()
├── resolve_regime_adaptive_short_params()
├── inject_predicted_side()
├── compute_short_score()
├── enrich_with_short_score()
├── tag_short_candidates()
├── compute_sma_column()
└── _get_close()

Appelants (tous passent par le même module) :
├── selector/scanner.py         → enrich_with_short_score
├── backtesting/risk_bridge.py  → resolve_short_trigger + resolve_regime_adaptive_short_params
│                                  + inject_predicted_side + enrich + tag_short_candidates
└── risk_management/cli.py      → resolve_short_trigger + resolve_regime_adaptive_short_params
                                   + enrich + tag_short_candidates
```

⌛ Reste à faire (non bloquant) : remonter les defaults `MomentumRotationState(lookback_weeks=4, threshold=-0.03)` dans `RiskConfig` au lieu de les hardcoder dans les 2 appelants.

Tests requis:

1. Tests d'intégration sur 3 flux:
   - selector live
   - risk live
   - backtest
2. Les décisions de side doivent être stables à entrée égale.

Critère de réussite:

- ✅ Les règles short ne vivent plus en parallèle dans plusieurs couches.
- ⚠️ Couverture de tests complète encore incomplète au moment de cette vérification. La correction code est présente, mais la non-régression 3-flux n'est pas encore totalement démontrée par tests d'intégration dédiés.

### P2 — Rendre le document encore plus exact — FAIT

**Fichier** : `doc/synthese_long_short.md` (nouvelle §15)

**Ajouts** :
- §15.1 — Tableau « Source of truth par brique » (16 composants, fidélité, mode, notes)
- §15.2 — Corrections appliquées (P0-1, P0-2 avec fichiers et descriptions)
- §15.3 — Reste à faire priorisé (P1 × 2, P2)

**Impact** : Le document devient un outil de contrôle d'intégration. On peut maintenant auditer en un coup d'œil quelles briques sont fiables et lesquelles ont des écarts connus.

## 6. Ordre recommandé d'exécution

1. ✅ ~~Corriger le Kelly short~~ — Fait (2026-07-03)
2. ✅ ~~Corriger ou neutraliser le rescoring régime live~~ — Fait (2026-07-03)
3. Unifier le calcul short.
4. Ajouter les tests de cohérence multi-chemins.
5. ✅ ~~Mettre à jour la documentation métier~~ — Fait (2026-07-03, §15)

## 7. Définition de done

Le système sera considéré cohérent quand les conditions suivantes seront vraies:

1. ✅ Un short utilise la même proba directionnelle pour conviction, sizing et audit — Fait (P0-1)
2. ✅ Le régime live s'applique uniquement sur de vraies données de facteurs, ou n'est plus appliqué à ce niveau — Fait (P0-2)
3. Le `short_score` est identique entre selector live, risk live et backtest à dataset équivalent.
4. Les chemins live/backtest journalisent la source exacte du score et des probabilités utilisées.
5. Les tests d'intégration couvrent les cas long, short, ternaire, PIT et régime défensif.
Statut au 2026-07-03 : couverture ciblée OK, couverture d'intégration complète encore partielle.

## 8. Recommandation finale

Ne pas repartir d'une refonte large.

La bonne stratégie est une correction ciblée, en quatre étapes:

1. réparer les incohérences de données transportées,
2. unifier les chemins short,
3. verrouiller la cohérence avec des tests,
4. seulement ensuite raffiner la documentation et les calibrations.

Le design actuel mérite d'être consolidé, pas remplacé.