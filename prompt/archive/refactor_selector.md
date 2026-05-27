# Audit et plan de refactor — module `selector`

_Date : 2026-05-19_

## 1. Périmètre audité

Fichiers principaux relus :
- `selector/alpha_scanner.py`
- `selector/cli.py`
- `selector/config.py`
- `selector/scanner.py`
- `selector/db_io.py`
- `selector/factors.py`
- `selector/filters.py`
- `selector/ranking.py`
- `selector/regime_filters.py`
- `selector/run_summary.py`
- `selector/strict_filter_profiles.py`

Tests relus / exécutés :
- `tests/test_selector_alpha_scanner.py`
- `tests/test_alpha_scanner.py`
- `tests/test_alpha_scanner_sector_neutrality_property.py`
- `tests/test_selector_run_summaries.py`
- `tests/test_selector_regime_filters.py`
- `tests/test_selector_reference.py`

Historique consulté :
- `prompt/archive/refactor/audit_selector.md`

---

## 2. Résumé exécutif

Le module `selector` est globalement **bien structuré et plus sain qu’un orchestrateur monolithique classique** :
- l’extraction en sous-modules (`config`, `db_io`, `factors`, `filters`, `ranking`, `run_summary`, `scanner`, `cli`) est cohérente ;
- `AlphaScannerConfig` valide correctement les paramètres critiques ;
- l’orchestration dans `selector/scanner.py` est claire, testée et suffisamment découplée ;
- la télémétrie de rejet par filtre et le `run_summary` apportent une bonne observabilité ;
- le socle de tests unitaires est déjà solide.

### Conclusion
Le module est **fonctionnel, maintenable et sensiblement durci après 2 passes**.

Les améliorations majeures désormais effectivement en place sont :
1. **robustesse renforcée** des helpers `selector/regime_filters.py` ;
2. **cohérence d’outillage** restaurée entre tests property et dépendances déclarées ;
3. **data quality gate explicite** avant exécution du scanner pour les filtres externes critiques ;
4. **run summary versionné et plus traçable** (profil + version + statut de run + diagnostic data quality) ;
5. **package `selector/` nettoyé au niveau Ruff**.

---

## 3. Méthode d’audit

### Revue statique
- lecture des sources du module `selector` ;
- lecture de l’audit historique ;
- lecture des tests et des contrats d’usage ;
- vérification IDE sur les fichiers du module.

### Validation exécutée
- exécution ciblée des tests `selector` ;
- exécution de lint ciblé sur les fichiers modifiés.

### Commandes de validation utilisées

```powershell
Set-Location "F:\projets"
python -m pytest tests/test_selector_alpha_scanner.py tests/test_alpha_scanner.py tests/test_alpha_scanner_sector_neutrality_property.py tests/test_selector_run_summaries.py tests/test_selector_regime_filters.py tests/test_selector_reference.py --no-cov -q
```

```powershell
Set-Location "F:\projets"
python -m ruff check selector/regime_filters.py tests/test_selector_regime_filters.py tests/test_alpha_scanner_sector_neutrality_property.py pyproject.toml --output-format concise
```

Résultat final : **OK** sur ce périmètre ciblé.

> Note : un lancement de pytest sans `--no-cov` sur ce sous-ensemble tombe sur le `fail-under` global du dépôt. Ce n’est pas une anomalie spécifique à `selector`, mais une conséquence de la politique de couverture du repo entier.

### Validation complémentaire — 2e passe

```powershell
Set-Location "F:\projets"
python -m ruff check selector --output-format concise
```

```powershell
Set-Location "F:\projets"
python -m pytest tests/test_selector_alpha_scanner.py tests/test_alpha_scanner.py tests/test_alpha_scanner_sector_neutrality_property.py tests/test_selector_run_summaries.py tests/test_selector_regime_filters.py tests/test_selector_reference.py --no-cov -q
```

Résultat 2e passe :
- `ruff check selector` : **OK**
- batterie `selector` ciblée : **OK**

---

## 4. Cartographie fonctionnelle du module

## 4.1 Flux principal

`selector/cli.py`
→ construit `AlphaScannerConfig`
→ instancie `selector/scanner.py::AlphaScanner`
→ exécute `run()`
→ émet un `run_summary`
→ affiche le top sélectionné.

## 4.2 Répartition des responsabilités

- `selector/config.py` : paramètres et validation métier.
- `selector/db_io.py` : I/O SQL et persistance.
- `selector/factors.py` : calcul des facteurs techniques.
- `selector/filters.py` : filtrage des candidats + stats de rejet.
- `selector/ranking.py` : fusion des scores, neutralisation, ranking final.
- `selector/regime_filters.py` : overlays liés au régime de marché.
- `selector/run_summary.py` : payloads d’observabilité.
- `selector/scanner.py` : orchestration multi-chunks et multi-threads.
- `selector/alpha_scanner.py` : shim de compatibilité.

### Appréciation
Cette séparation est bonne. Le refactor historique a clairement amélioré la lisibilité et réduit le risque systémique.

---

## 5. Points forts constatés

### 5.1 Configuration défensive
`selector/config.py` contient de bonnes validations :
- bornes de ratio/ATR/poids ;
- cohérence `max_spread_bps_iex >= max_spread_bps` ;
- validation du `sector_cap_ratio` ;
- somme des poids factoriels = 1.

### 5.2 Bonne observabilité métier
Le couple `selector/filters.py` + `selector/run_summary.py` fournit :
- des compteurs de rejet par filtre ;
- un diagnostic de run vide ;
- des métriques utiles pour l’IHM.

### 5.3 Orchestration globalement saine
`selector/scanner.py` reste fin et délègue bien :
- bonne isolation DB / logique pure ;
- agrégation cross-chunks des stats ;
- progression live exploitable.

### 5.4 Couverture de tests déjà sérieuse
Les cas importants sont couverts :
- config stricte ;
- filtres ;
- neutralisation sectorielle ;
- persistance DB ;
- run end-to-end ;
- run summaries ;
- property tests sur le round-robin sectoriel.

---

## 6. Anomalies détectées

## 6.1 Anomalie A1 — robustesse insuffisante de `selector/regime_filters.py`

### Symptôme
Les helpers de régime étaient sensibles à la casse et aux espaces sur :
- les symboles (`earnings_shielded_symbols`, `buyback_blackout_symbols`, `blocked_symbols`) ;
- les secteurs (`blocked_sectors`).

Ils pouvaient aussi provoquer un comportement fragile si la colonne `symbol` était absente.

### Impact
- faux négatifs de filtrage en production si les snapshots arrivent en minuscules ou avec espaces ;
- risque de `KeyError` / comportement inattendu sur DataFrame partiel ;
- comportement peu robuste pour des helpers censés être réutilisables dans plusieurs contextes.

### Correctif appliqué
Dans `selector/regime_filters.py` :
- normalisation `strip()/upper()` des symboles ;
- normalisation `strip()/casefold()` des secteurs ;
- garde-fous explicites quand les colonnes requises sont absentes ;
- contrat clarifié : retour systématique d’un `DataFrame`.

### Tests ajoutés
Dans `tests/test_selector_regime_filters.py` :
- normalisation de casse des symboles pour `earnings_shield` ;
- normalisation casse/espaces des secteurs pour `yield_filter` ;
- no-op propre si la colonne symbole est absente côté buyback blackout.

---

## 6.2 Anomalie A2 — log trompeur dans `apply_buyback_blackout_to_candidates`

### Symptôme
Le log final utilisait la variable `mult` de la dernière itération de boucle.

### Impact
Le message pouvait suggérer un multiplicateur unique alors que plusieurs symboles avaient potentiellement des multiplicateurs différents.

### Correctif appliqué
Le log a été simplifié pour refléter un fait exact :
- nombre total de candidats pénalisés.

---

## 6.3 Anomalie A3 — incohérence outillage/tests autour d’Hypothesis

### Symptôme
`tests/test_alpha_scanner_sector_neutrality_property.py` importait directement `hypothesis` au chargement.
En environnement local sans dépendance installée, la collecte pytest cassait immédiatement.

### Impact
- faux signal d’échec sur l’audit du module ;
- expérience développeur incohérente avec d’autres tests du dépôt qui utilisent `pytest.importorskip("hypothesis")`.

### Correctif appliqué
- le test property utilise désormais `pytest.importorskip("hypothesis")` ;
- les imports ont été réorganisés pour rester propres au lint.

### Bénéfice
Le test reste exécuté si la dépendance existe, mais ne casse plus la collecte si elle n’est pas présente.

---

## 6.4 Anomalie A4 — `pyproject.toml` incomplet pour l’extra `dev`

### Symptôme
L’extra `dev` de `pyproject.toml` ne listait pas toutes les dépendances de test réellement utilisées par ce périmètre :
- `hypothesis`
- `pytest-benchmark`

Alors que `requirements-dev.txt` les contenait déjà.

### Impact
- divergence entre `pip install -r requirements-dev.txt` et `pip install -e ".[dev]"` ;
- environnement de dev partiellement fonctionnel ;
- risque de tests cassés selon la méthode d’installation.

### Correctif appliqué
Ajout de :
- `hypothesis>=6`
- `pytest-benchmark>=4`

à l’extra `dev` de `pyproject.toml`.

---

## 6.5 Amélioration A5 — data quality gate explicite avant run

### Besoin
Le prompt demandait un durcissement explicite de la qualité des données externes critiques, en particulier pour :
- `stock_quote_snapshots` si le filtre de spread est actif ;
- `stock_earnings_calendar` si le filtre `earnings_blackout` est actif.

### Implémentation réalisée
Ajout d’un **préflight data-quality structuré** :
- `selector/db_io.py` construit un payload `data_quality_gate` ;
- `selector/scanner.py` exécute ce préflight avant le scan ;
- en cas de blocage, le scanner lève `SelectorDataQualityError` ;
- `selector/cli.py` transforme ce blocage en `run_summary` structuré avec `run_status="blocked"`.

### Couverture ajoutée
- test CLI de blocage avec `run_summary` explicite ;
- test d’intégration sur données `quotes` et `earnings` périmées.

### Bénéfice
Le module n’échoue plus silencieusement dans un contexte de données externes manifestement impropres à l’exécution des filtres activés.

---

## 6.6 Amélioration A6 — run summary davantage professionnalisé

### Implémentation réalisée
Le payload `selector` expose désormais explicitement :
- `schema_version` ;
- `run_status` ;
- `failure_reason` ;
- `preset_profile` ;
- `preset_profile_version` ;
- `data_quality_gate` ;
- `small_selected_sectors`.

### Bénéfice
La lecture IHM / monitoring / post-mortem devient plus explicite et plus stable contractuellement.

---

## 6.7 Amélioration A7 — invariance fonctionnelle renforcée

### Implémentation réalisée
Ajout d’un test d’intégration vérifiant que, sur un même univers et à `max_workers=1`, la sélection finale reste identique malgré un changement de `chunk_size`.

### Bénéfice
Cela sécurise l’invariant cross-chunks qui était identifié comme un risque de maintenabilité dans l’audit historique.

---

## 7. Risques résiduels / non bloquants

## 7.1 Données externes toujours critiques
Les risques identifiés dans l’audit historique restent valides :
- `market_cap` et sa fraîcheur ;
- `spread_bps` / snapshots IEX ;
- `earnings_blackout` si la source calendrier est incomplète.

### Recommandation
Ajouter un **data quality gate explicite** avant le run :
- si source périmée ou absente, soit bloquer le run,
- soit désactiver explicitement le filtre concerné avec trace claire.

---

## 7.2 Lint / modernisation Python encore partiels
Un passage `ruff` sur l’ensemble de `selector` remonte surtout des points non bloquants :
- tri/imports ;
- annotations modernes (`UP037`, `UP045`, `UP017`) ;
- quelques nettoyages de style.

### Recommandation
Prévoir un sprint court de normalisation Ruff sur tout `selector/` sans changer le comportement métier.

Priorité : **faible à moyenne**.

---

## 7.3 Traçabilité métier encore perfectible
Aujourd’hui, `run_summary` donne de bons compteurs agrégés mais on ne conserve pas toute l’explicabilité au niveau candidat.

### Recommandation
Étendre progressivement :
- persistance de quelques facteurs additionnels (`atr_pct_20`, `weekly_trend_score`, `high_52w_proximity`) ;
- meilleure traçabilité du profil de filtres utilisé (nom + version).

---

## 7.4 Neutralisation sectorielle : manque d’alerte sur petits groupes
La neutralisation intra-secteur reste pertinente, mais sur les très petits groupes sectoriels elle peut devenir peu informative.

### Recommandation
Ajouter dans le `run_summary` :
- nombre de secteurs avec effectif faible post-filtrage ;
- éventuellement un seuil pour désactiver la neutralisation sur secteurs trop petits.

---

## 8. Plan d’amélioration priorisé

## P0 — déjà corrigé
- [x] Durcir `selector/regime_filters.py` sur la normalisation symboles/secteurs.
- [x] Corriger le log buyback trompeur.
- [x] Rendre les tests property `selector` tolérants à l’absence d’Hypothesis.
- [x] Aligner `pyproject.toml` sur les dépendances de test réellement utilisées.

## P1 — recommandé court terme
- [x] Ajouter un `data quality gate` avant exécution du scanner.
- [x] Versionner explicitement le profil de filtres dans le `run_summary`.
- [x] Ajouter un test d’invariance du résultat au `chunk_size` / au découpage cross-chunks.
- [x] Ajouter un test d’intégration simulant données quotes/earnings périmées.

## P2 — recommandé moyen terme
- [x] Normaliser tout `selector/` via Ruff sans changement métier.
- [x] Persister davantage de facteurs utiles au post-mortem.
- [x] Enrichir `run_summary` avec alertes secteurs trop petits et diagnostics data quality.

## P3 — recommandé plus long terme
- [x] Introduire un mode de fallback explicite configurable par filtre externe (spread, earnings, market cap freshness).
- [x] Industrialiser l’ablation de filtres / A-B tests de profils.
- [x] Documenter un workflow standard “ajout d’un nouveau filtre” (code + tests + observabilité).

---

## 9. État final après corrections

### Fichiers modifiés
- `core/filter_profiles.py`
- `selector/regime_filters.py`
- `selector/config.py`
- `selector/run_summary.py`
- `selector/db_io.py`
- `selector/scanner.py`
- `selector/cli.py`
- `selector/alpha_scanner.py`
- `tests/test_selector_regime_filters.py`
- `tests/test_alpha_scanner_sector_neutrality_property.py`
- `tests/test_selector_run_summaries.py`
- `tests/test_selector_alpha_scanner.py`
- `tests/test_alpha_scanner.py`
- `pyproject.toml`

### Validation finale
- tests ciblés `selector` : **passent** ;
- lint ciblé des fichiers modifiés : **passe** ;
- `ruff check selector` : **passe**.

### Verdict
Le module `selector` est désormais **nettement plus professionnel** :
- propre au lint sur tout le package ;
- mieux contracté côté `run_summary` ;
- protégé contre les exécutions sur données externes manifestement périmées ;
- mieux couvert sur les invariants d’orchestration.

Les prochains gains de valeur se situent désormais surtout sur :
- la **persistance de facteurs supplémentaires** pour le post-mortem ;
- l’**industrialisation des profils/versioning avancé** ;
- l’**explicabilité fine par candidat**.

---

## 10. 3e passe — orientée « expert production »

### Objectif
Cette 3e passe a ciblé explicitement :
- la **persistance de facteurs additionnels** dans `stock_scores` et `stock_scores_history` ;
- l’**explicabilité par candidat** ;
- la **compatibilité de persistance PIT** malgré une migration de schéma progressive.

### Implémentation réalisée

#### 10.1 Persistance enrichie dans `stock_scores`
Le payload selector persisté contient désormais, en plus des colonnes historiques :
- `candidate_rank`
- `raw_final_score`
- `normalized_total_score`
- `normalized_rsi`
- `total_score_neutralized`
- `relative_strength_index_neutralized`
- `trend_vcp_component`
- `total_score_component`
- `rsi_component`
- `atr_pct_20`
- `weekly_trend_score`
- `high_52w_proximity`
- `volatility_ratio`
- `selector_signal_mode`
- `selection_explanation`

Bénéfices :
- meilleur post-mortem quantitatif ;
- meilleure lecture des composantes du score final ;
- meilleure auditabilité des runs selector et des snapshots PIT.

#### 10.2 Explicabilité par candidat
Le module `selector/ranking.py` produit maintenant une **décomposition explicite du score final** :
- contribution `trend_vcp_component`
- contribution `total_score_component`
- contribution `rsi_component`
- mode de score (`factor_only`, `multi_factor`, `sector_neutralized`)
- résumé texte compact via `selection_explanation`

Le `run_summary` expose aussi `top_candidate_explanations` pour les premiers candidats sélectionnés.

#### 10.3 Compatibilité schéma / rollout progressif
La persistance selector et l’archivage `stock_scores_history` ont été durcis pour rester compatibles :
- avec une table déjà migrée ;
- avec une table encore partiellement legacy ;
- avec un archivage PIT exécuté avant/après migration complète.

Concrètement :
- `selector/db_io.py` fait des `UPDATE` dynamiques selon les colonnes réellement présentes ;
- `selector/db_io.py::reset_selector_outputs` ne réinitialise que les colonnes existantes ;
- `screener/db_io.py::archive_scores_snapshot` construit un `INSERT ... SELECT` dynamique basé sur l’intersection des colonnes source/cible.

Cela réduit le risque opérationnel lors d’un déploiement par étapes.

### Artefacts ajoutés
- migration Alembic : `alembic/versions/0029_selector_explainability_persistence.py`
- SQL d’upgrade manuel : `database/sql/stock/stock_scores_selector_explainability_upgrade.sql`

### Fichiers modifiés / ajoutés — 3e passe
- `selector/ranking.py`
- `selector/db_io.py`
- `selector/scanner.py`
- `selector/run_summary.py`
- `screener/db_io.py`
- `database/sql/stock/stock_scores.sql`
- `database/sql/stock/stock_scores_history.sql`
- `database/sql/stock/stock_scores_selector_explainability_upgrade.sql`
- `alembic/versions/0029_selector_explainability_persistence.py`
- `tests/test_alpha_scanner.py`
- `tests/test_selector_run_summaries.py`

### Validation exécutée — 3e passe

```powershell
Set-Location "F:\projets"
python -m pytest tests/test_alpha_scanner.py tests/test_selector_run_summaries.py tests/test_screener_db_io.py --no-cov -q
```

```powershell
Set-Location "F:\projets"
python -m pytest tests/test_selector_alpha_scanner.py tests/test_alpha_scanner.py tests/test_alpha_scanner_sector_neutrality_property.py tests/test_selector_run_summaries.py tests/test_selector_regime_filters.py tests/test_selector_reference.py --no-cov -q
```

```powershell
Set-Location "F:\projets"
python -m ruff check selector\ranking.py selector\db_io.py selector\scanner.py selector\run_summary.py tests\test_alpha_scanner.py tests\test_selector_run_summaries.py alembic\versions\0029_selector_explainability_persistence.py --output-format concise
```

Résultat :
- tests ciblés 3e passe : **OK** ;
- batterie selector ciblée : **OK** ;
- lint Ruff périmètre selector + migration : **OK**.

> Note : `screener/db_io.py` a été durci fonctionnellement pour l’archivage PIT, mais n’a pas été inclus dans le lint strict final de cette passe car ce fichier historique reste tabulé et ferait remonter des warnings de style hérités non spécifiques à cette évolution.

## 11. 4e passe — exposition IHM/API d’un payload d’explicabilité candidat complet

### Axe retenu
Pour cette 4e passe, l’axe retenu a été :

- **exposition IHM/API d’un `candidate explainability payload` complet**.

Ce choix est le plus cohérent avec l’état atteint en 3e passe :
- `selector/ranking.py` calcule déjà les composantes détaillées du score ;
- `selector/db_io.py` les persiste dans `stock_scores` ;
- `selector/run_summary.py` exposait déjà une version partielle via `top_candidate_explanations`.

### Implémentation réalisée

#### 11.1 Contrat canonique partagé
Ajout du helper partagé :

- `selector/explainability.py::build_candidate_explainability_payload()`

Le payload canonique regroupe désormais explicitement :
- `identity`
- `score_inputs`
- `score_components`
- `score_outputs`
- `technical_context`
- `risk_context`
- `earnings_context`
- `quality_context`
- `selection_context`

Objectif : éviter toute divergence entre le live selector, la lecture IHM depuis `stock_scores` et une future exposition API dédiée.

#### 11.2 Run summary enrichi
`selector/run_summary.py` enrichit maintenant chaque entrée de `top_candidate_explanations` avec :

- `candidate_explainability_payload`

tout en conservant les champs plats historiques (`symbol`, `final_score`, `trend_vcp_component`, `selection_explanation`, etc.) pour compatibilité ascendante.

#### 11.3 Lecture IHM/API `stock_scores` durcie
`ihm/services/queries.py::get_stock_scores()` a été rendu :

- **schema-aware** via `SHOW COLUMNS FROM stock_scores` ;
- compatible **legacy / post-migration** ;
- enrichi d’une colonne :
  - `candidate_explainability_payload`

Ainsi l’IHM n’échoue pas si certaines colonnes d’explicabilité ne sont pas encore présentes ; elle dégrade proprement le payload avec des champs `null` là où le schéma n’est pas encore migré.

#### 11.4 Exposition opérateur dans la page `Screening`
`ihm/pages/screening.py` expose maintenant :

- un tableau principal plus compact pour l’opérateur ;
- un panneau **"Explainability candidat"** alimenté par la ligne sélectionnée ;
- affichage direct du payload complet via `st.json(...)`.

Cela fournit une vraie lecture post-mortem / investigation sans devoir aller relire la base manuellement.

#### 11.5 Exposition complémentaire dans les détails de run summary IHM
`ihm/services/run_summary.py` ajoute aussi des lignes de détail Alpha Scanner pour les top candidats, par exemple :

- rang/symbole
- mode de scoring
- score final
- composantes principales
- synthèse `selection_explanation`

### Fichiers modifiés — 4e passe
- `selector/explainability.py`
- `selector/run_summary.py`
- `ihm/services/queries.py`
- `ihm/services/run_summary.py`
- `ihm/pages/screening.py`
- `tests/test_selector_run_summaries.py`
- `tests/test_ihm_run_summary.py`
- `tests/test_services_queries.py`
- `tests/test_pages_screening.py`

### Validation exécutée — 4e passe

```powershell
Set-Location "F:\projets"
python -m ruff check selector\explainability.py selector\run_summary.py ihm\services\queries.py ihm\services\run_summary.py ihm\pages\screening.py tests\test_selector_run_summaries.py tests\test_ihm_run_summary.py tests\test_services_queries.py tests\test_pages_screening.py --output-format concise
```

```powershell
Set-Location "F:\projets"
python -m pytest tests\test_selector_run_summaries.py tests\test_ihm_run_summary.py tests\test_services_queries.py tests\test_pages_screening.py tests\test_alpha_scanner.py --no-cov -q
```

```powershell
Set-Location "F:\projets"
python -m pytest tests\test_selector_alpha_scanner.py tests\test_selector_run_summaries.py tests\test_ihm_run_summary.py tests\test_ihm_run_summary_component.py tests\test_services_queries.py tests\test_pages_screening.py tests\test_alpha_scanner.py tests\test_selector_reference.py --no-cov -q
```

Résultat :
- lint Ruff du périmètre modifié : **OK** ;
- tests ciblés 4e passe : **OK** ;
- validation élargie selector/IHM impactée : **OK**.

### Verdict 4e passe
Le module `selector` franchit un cran supplémentaire côté usage production :

- l’explicabilité candidat est désormais **contractualisée** ;
- elle est visible à la fois dans le `run_summary` et dans l’IHM `Screening` ;
- l’exposition est **compatibile migration progressive** grâce à la lecture dynamique du schéma ;
- le terrain est prêt pour une future **API dédiée** sans redéfinir le contrat métier.

## 12. 5e passe — rejets de pré-sélection persistés + fallback data-quality configurable

### Axe retenu
Pour cette 5e passe, les deux chantiers restants les plus rentables ont été traités ensemble :

- **persistance de l’explicabilité des rejets de pré-sélection SQL** ;
- **fallback data-quality configurable par filtre** (`block` / `warn_skip_filter`).

### 12.1 Vérification du prompt restant
À l’issue de cette passe, l’état du prompt est le suivant :

- persistance de facteurs post-mortem : **faite** ;
- payload complet d’explicabilité candidat IHM/API : **fait** ;
- fallback data-quality configurable : **fait** ;
- documentation du workflow “ajout d’un nouveau filtre” : **faite** ;
- industrialisation des ablations/A-B tests de profils : **reste le principal point ouvert**.

### 12.2 Persistance des rejets de pré-sélection
Ajout de `selector/db_io.py::build_preselection_rejection_audit()`.

Ce helper :
- reconstruit l’univers brut `stock_bars_daily` + `stock_metadata` avant le scan chunké ;
- classe chaque symbole rejeté selon une **raison exclusive** cohérente avec la pré-sélection SQL ;
- persiste dans le `run_summary` un payload `preselection_rejections` contenant :
  - `input_symbols`
  - `eligible_symbols`
  - `rejected_symbols`
  - `eligible_ratio`
  - `reason_counts`
  - `sample_symbols_by_reason`
  - `top_reasons`

Les rejets typiques explicités sont par exemple :
- `metadata_missing`
- `non_us_equity`
- `history_status_blocked`
- `insufficient_history`
- `below_min_close`
- `below_liquidity_threshold`

Conséquence : le run history/IHM ne contient plus seulement les rejets **post-fusion pandas**, mais aussi une trace exploitable des pertes d’univers **avant même le chargement multi-chunks**.

### 12.3 Fallback data-quality configurable par filtre
`AlphaScannerConfig` expose désormais trois modes indépendants :

- `spread_data_quality_mode`
- `earnings_data_quality_mode`
- `market_cap_filter_data_quality_mode`

Valeurs supportées :
- `block`
- `warn_skip_filter`

Comportement mis en place :
- si le mode est `block`, le `preflight` échoue comme avant ;
- si le mode est `warn_skip_filter`, le `preflight` passe en état `warning`, le `run_summary` liste `skipped_filters`, et le scanner désactive **uniquement** le filtre concerné pour ce run ;
- la fraîcheur `market_cap` TTL adopte par défaut le mode **`warn_skip_filter`** pour rester compatible avec les environnements progressivement migrés.

Le `data_quality_gate` couvre maintenant explicitement :
- `quotes` / filtre `spread`
- `earnings` / filtre `earnings_blackout`
- `market_cap` / filtre `market_cap_ttl`

### 12.4 Exposition IHM
`ihm/services/run_summary.py` expose maintenant aussi pour `alpha_scanner` :

- une ligne de détail sur les **filtres sautés** par fallback data-quality ;
- une ligne synthétique sur la **pré-sélection SQL** avec ratios, top raisons et échantillons de symboles.

### 12.5 Documentation
`doc/selector.md` a été remis à jour pour :

- refléter la persistance réelle des facteurs selector ;
- documenter les nouveaux flags CLI de fallback data-quality ;
- ajouter un workflow standard “ajout d’un nouveau filtre”.

### Fichiers modifiés — 5e passe
- `selector/config.py`
- `selector/cli.py`
- `selector/db_io.py`
- `selector/scanner.py`
- `selector/run_summary.py`
- `ihm/services/run_summary.py`
- `tests/test_selector_alpha_scanner.py`
- `tests/test_alpha_scanner.py`
- `tests/test_selector_run_summaries.py`
- `tests/test_ihm_run_summary.py`
- `doc/selector.md`

### Validation exécutée — 5e passe

```powershell
Set-Location "F:\projets"
python -m ruff check selector\config.py selector\cli.py selector\db_io.py selector\scanner.py selector\run_summary.py ihm\services\run_summary.py tests\test_selector_alpha_scanner.py tests\test_alpha_scanner.py tests\test_selector_run_summaries.py tests\test_ihm_run_summary.py --output-format concise
```

```powershell
Set-Location "F:\projets"
python -m pytest tests\test_selector_alpha_scanner.py tests\test_alpha_scanner.py tests\test_selector_run_summaries.py tests\test_ihm_run_summary.py --no-cov -q
```

```powershell
Set-Location "F:\projets"
python -m pytest tests\test_selector_alpha_scanner.py tests\test_selector_run_summaries.py tests\test_ihm_run_summary.py tests\test_ihm_run_summary_component.py tests\test_services_queries.py tests\test_pages_screening.py tests\test_alpha_scanner.py tests\test_selector_reference.py --no-cov -q
```

### Verdict 5e passe
Le module `selector` couvre désormais l’essentiel des points concrets du prompt initial :

- observabilité plus complète sur l’entrée d’univers ;
- comportement data-quality plus fin et plus opérable ;
- compatibilité préservée avec un rollout progressif des sources externes ;
- documentation métier/technique réalignée sur l’état réel du code.

Le prompt initial `selector` est désormais couvert sur ses gros chantiers structurants.

## 13. 6e passe — industrialisation d’un mode d’ablation / A-B des filtres

### Axe retenu
Pour cette 6e passe, le dernier gros point restant a été traité :

- **industrialiser un mode d’ablation / A-B des filtres et profils dans `selector`**.

### 13.1 Design retenu
Le choix retenu est un mode **`shadow`** à faible risque :

- la variante **primaire** garde le contrat métier live et la persistance DB ;
- les variantes secondaires s’exécutent **en shadow** sur le même run ;
- elles partagent la préparation des chunks (prices/scores/metadata/overlays) puis appliquent leur propre config de filtre/ranking ;
- seules leurs sorties d’observabilité sont persistées dans le `run_summary` + un artefact JSON hors base.

Ce design évite de casser `stock_scores`, `stock_scores_history` et toute la chaîne aval (`risk_management`, `execution`) tout en fournissant un vrai A/B exploitable.

### 13.2 Contrat de configuration
Ajout dans `selector/config.py` de :

- `SelectorVariantSpec`
- `SelectorAblationPlan`
- modes `off` / `shadow`
- chargement depuis fichier JSON/YAML (`load_selector_ablation_plan_from_file`)

Chaque variante peut :

- désactiver explicitement un ou plusieurs filtres supportés (`disabled_filters`) ;
- ou surcharger certains seuils via `config_overrides`.

### 13.3 Runtime scanner
`selector/scanner.py` supporte maintenant :

- la résolution d’une liste de variantes runtime à partir du primaire ;
- l’exécution multi-variantes **sur une préparation de chunk partagée** ;
- la conservation de l’agrégat `rejected_by_filter` du primaire ;
- un getter `get_last_ablation_summary()`.

Garde-fou important :

- une variante shadow **ne peut pas réactiver** un filtre déjà désactivé sur le primaire par le `data_quality_gate`.

### 13.4 Observabilité et artefacts
Le `run_summary` selector expose désormais un bloc `ablation` contenant notamment :

- `mode`
- `variant_count`
- `artifact_path`
- `primary`
- `variants[]`
  - `variant_id`
  - `disabled_filters`
  - `skipped_filters`
  - `config_diff`
  - `selected_candidates`
  - `top_symbols`
  - `overlap_with_primary`
  - `selection_diff`
  - `rejected_by_filter`

En complément, un artefact JSON détaillé est écrit dans :

- `artifacts/selector/ablation/*.json`

### 13.5 IHM et documentation
L’IHM `run_summary` alpha scanner affiche maintenant aussi :

- le nombre de variantes shadow ;
- le chemin de l’artefact ;
- les ajouts / retraits principaux par variante ;
- l’overlap avec le primaire.

`doc/selector.md` a été enrichi avec :

- les flags CLI `--ablation-mode` / `--ablation-config` ;
- un exemple de fichier JSON ;
- la liste des filtres désactivables ;
- le contrat d’observabilité associé.

### 13.6 Fichiers modifiés — 6e passe
- `selector/config.py`
- `selector/ablation.py`
- `selector/scanner.py`
- `selector/run_summary.py`
- `selector/cli.py`
- `selector/alpha_scanner.py`
- `ihm/services/run_summary.py`
- `tests/test_selector_alpha_scanner.py`
- `tests/test_alpha_scanner.py`
- `tests/test_selector_run_summaries.py`
- `tests/test_ihm_run_summary.py`
- `doc/selector.md`

### 13.7 Validation exécutée — 6e passe

```powershell
Set-Location "F:\projets"
python -m ruff check selector\config.py selector\ablation.py selector\scanner.py selector\run_summary.py selector\cli.py selector\alpha_scanner.py ihm\services\run_summary.py tests\test_selector_alpha_scanner.py tests\test_alpha_scanner.py tests\test_selector_run_summaries.py tests\test_ihm_run_summary.py --output-format concise
```

```powershell
Set-Location "F:\projets"
python -m pytest tests\test_selector_alpha_scanner.py tests\test_alpha_scanner.py tests\test_selector_run_summaries.py tests\test_ihm_run_summary.py --no-cov -q
```

```powershell
Set-Location "F:\projets"
python -m pytest tests\test_selector_alpha_scanner.py tests\test_selector_run_summaries.py tests\test_ihm_run_summary.py tests\test_ihm_run_summary_component.py tests\test_ihm_pipeline_runner.py tests\test_services_queries.py tests\test_pages_screening.py tests\test_alpha_scanner.py tests\test_selector_reference.py --no-cov -q
```

