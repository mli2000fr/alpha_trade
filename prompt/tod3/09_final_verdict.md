# 09 — Verdict final

## Note globale : **7.4 / 10**

## Positionnement

| Référentiel | Note typique | Alpha Trade | Positionnement |
|---|---:|---:|---|
| Application amateur sérieuse | 4–5 | 7.4 | **Très au-dessus** |
| Application indé avancée | 5–7 | 7.4 | **Au-dessus** |
| Application pro buy-side / prop / desk swing | 7–8.5 | 7.4 | **Au pied** |
| Application institutionnelle très mature | 9–10 | 7.4 | **Encore loin** |

## Verdict : **quasi-pro / pro-grade partiel**

Alpha Trade est nettement plus mature que la moyenne des projets
indépendants de trading algorithmique. Le découpage modulaire, la
discipline des conventions (split-only, ledger séparé pour les
dividendes, contraintes SQL bloquantes, scanner secrets, recette
pré-live), l'ampleur de la couverture de tests (~280 fichiers) et la
profondeur des audits historiques internes (`prompt/refactor/`,
`doc/audit/`, `doc/external_audit/`) le placent dans le **haut du panier
indé / bas du panier pro**.

Les éléments qui empêchent encore le grade "pro plein" pour un usage
live argent réel intensif sont identifiés et tous **adressables en
6 sprints structurants** (cf. `08_sprint_plan.md`), sans refactor lourd :

- limitation des **quotes IEX biaisées** (A-004) ;
- **réconciliation J+1** vs broker statement non exposée (A-005) ;
- **ordre `event_sentiment`** non verrouillé (A-003) ;
- **presets micro-compte agressifs** (A-001, A-008) ;
- **double point d'entrée d'exécution** à clarifier (A-002) ;
- **fallback silencieux OHLCV** sans alerting (A-013) ;
- **parité backtest/live** non garantie avec sentiment+ML+macro (A-009).

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
| Opérateur débutant 0–5 k$ | Mode discovery / paper uniquement, attendre Sprint S1 et S3 livrés. |
| Opérateur intermédiaire 10–25 k$ | **Utilisable en live mesuré** après Sprint S2 (verrou sentiment) et S3 (réconciliation J+1). |
| Opérateur avancé 50 k$+ | Utilisable en live discipliné dès maintenant en mode paper d'abord, live après Sprint S3. |
| Opérateur pro 100 k$+ | Utilisable après Sprint S3 + S5 (signature artefacts, doctrine broker failover). |

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

