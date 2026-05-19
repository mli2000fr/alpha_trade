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
- [ ] Persister davantage de facteurs utiles au post-mortem.
- [x] Enrichir `run_summary` avec alertes secteurs trop petits et diagnostics data quality.

## P3 — recommandé plus long terme
- [ ] Introduire un mode de fallback explicite configurable par filtre externe (spread, earnings, market cap freshness).
- [ ] Industrialiser l’ablation de filtres / A-B tests de profils.
- [ ] Documenter un workflow standard “ajout d’un nouveau filtre” (code + tests + observabilité).

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

