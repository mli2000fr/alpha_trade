# 09 — Verdict final

## Note globale

- **Audit initial** : **7.4 / 10**
- **Réévaluation de suivi (remédiations vérifiées au 2026-05-22)** : **8.0 / 10**

## Positionnement

| Référentiel | Note typique | Alpha Trade (suivi) | Positionnement |
|---|---:|---:|---|
| Application amateur sérieuse | 4–5 | 8.0 | **Très au-dessus** |
| Application indé avancée | 5–7 | 8.0 | **Au-dessus** |
| Application pro buy-side / prop / desk swing | 7–8.5 | 8.0 | **Dans la zone basse mais crédible** |
| Application institutionnelle très mature | 9–10 | 8.0 | **Encore loin** |

## Verdict : **quasi-pro / pro-grade partiel**

Alpha Trade est nettement plus mature que la moyenne des projets
indépendants de trading algorithmique. Le découpage modulaire, la
discipline des conventions (split-only, ledger séparé pour les
dividendes, contraintes SQL bloquantes, scanner secrets, recette
pré-live), l'ampleur de la couverture de tests (~280 fichiers) et la
profondeur des audits historiques internes (`prompt/refactor/`,
`doc/audit/`, `doc/external_audit/`) le placent dans le **haut du panier
indé / bas du panier pro**.

Depuis l'audit initial, plusieurs remédiations structurantes ont été
vérifiées dans le code :

- signatures SHA256 d'artefacts ML avec vérification au chargement ;
- doctrine failover broker rendue visible à l'opérateur + runbook dédié ;
- preflight `simulate` ramené au bon contrat (`WARN` visible, non bloquant) ;
- activation Kelly conditionnelle à partir de 25 k$ ;
- `macro_provider` par défaut passé à `composite` ;
- bannière IHM explicite en absence de configuration SMTP.

Les éléments qui empêchent encore le grade "pro plein" pour un usage
live argent réel intensif sont identifiés et restent **adressables sans
refactor lourd** :

- limitation des **quotes IEX biaisées** (A-004) ;
- industrialisation complète de la **réconciliation J+1** (CSV OK, PDF natif optionnel) ;
- publication d'un runbook explicite pour **incident sentiment provider** (A-023) ;
- profil **DB read-only** dédié IHM + rotation des secrets davantage formalisée ;
- **parité backtest/live** encore à pousser jusqu'au nightly full-stack sur 10 jours (A-009) ;
- production de la métrique **`quote_iex_vs_consolidated_bps`** et exposition IHM (A-004).

## Niveau de confiance

**Moyen-élevé.** L'auditeur a lu en intégralité : `README.md`,
`config.yaml`, `config/capital_presets.yaml`, `corporate_actions/engine.py`
(en-tête + docstring conventions), `dataIntegrityEngine/import_alpaca_bar.py`
(en-tête + constantes), `dataIntegrityEngine/import_eodhd_bar.py`
(shim complet), `core/conviction.py`, `run_execution.py` (en-tête + check
env), `doc/data_lineage_matrix.md` (sections data + risk),
`doc/dataIntegrityEngine.md` (bandeau).

L'auditeur a cartographié tous les packages racines + `tests/` (~280 fichiers).
Certains modules (modelFactory en profondeur, backtesting/simulator, IHM
pages individuelles, intra-modules `event_sentiment`) n'ont pas été lus
ligne par ligne. **Marge d'erreur estimée : ±0.4 point.**

## Recommandation opérateur

| Profil | Recommandation |
|---|---|
| Opérateur débutant 0–5 k$ | Mode discovery / paper privilégié ; S1 est livré mais la petite taille de compte reste structurellement délicate. |
| Opérateur intermédiaire 10–25 k$ | **Utilisable en live mesuré** ; le verrou sentiment est présent, la réconciliation J+1 est déjà avancée. |
| Opérateur avancé 50 k$+ | Utilisable en live discipliné, avec meilleure lisibilité ops grâce aux signatures ML et au failover doctrine panel. |
| Opérateur pro 100 k$+ | Utilisable en régime discipliné ; reliquats principaux = qualité de quotes IEX, DB RO IHM, runbook sentiment provider. |

## Décision finale

> 🟢 **L'application est techniquement saine et fonctionnellement
> appropriée pour le swing trading actions US.** Elle n'est pas encore
> "pro-grade plein" mais elle se rapproche d'un niveau buy-side discret
> à mesure que les sprints S1→S6 sont exécutés. Le ratio
> "investissement nécessaire / niveau atteint" est très favorable.
>
> Le **risque opérationnel principal restant** est la qualité des
> **quotes IEX** côté microstructure, non résoluble par du code seul
> (nécessite un plug Alpaca SIP / Polygon).

