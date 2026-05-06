# Onboarding opérateur — Walkthrough 60 minutes

> Phase C / S18.1. Substitut textuel à la vidéo onboarding (cf.
> `25_phase_C_execution_plan.md` — vidéo stubbée).

## T+0 → T+10 : Installation

```bash
git clone <repo>
cd alpha_trade
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
copy config.example.yaml config.yaml
# éditer config.yaml selon broker mode (paper / live)
```

Vérifier :

```bash
pytest tests/ -m "unit" --no-cov -q
python -m execution_engine.preflight --account default --skip-network
```

## T+10 → T+25 : Tour de l'IHM

```bash
streamlit run ihm/app.py
```

* **Cockpit** : vue d'ensemble PnL + positions ouvertes.
* **Execution Center** : ordres en cours, OCO actifs.
* **Risk Decisions** : drilldown derniers refus risk.
* **Backtesting** : lancer un backtest bouton.
* **Tax & Compliance** : wash sales détectées (S16.3).

## T+25 → T+40 : Lancer un pipeline complet en paper

```bash
python run.py --pipeline full --broker-mode paper
```

Logs : `log/<run_id>/`. Audit chain : `database.audit_chain`.

## T+40 → T+50 : Surveiller / debugger

* `python scripts/run_daily_parity.py` : vérifie cohérence backtest/live.
* `python scripts/verify_audit_chain.py` : intégrité signature HMAC.
* `python scripts/run_broker_reconciliation.py` : diff broker vs DB.

## T+50 → T+60 : Pour aller plus loin

* `doc/architecture/c4_*.md` : compréhension architecture.
* `doc/runbook_24_7.md` : procédures incident.
* `doc/formal_verification.md` : invariants prouvés (S15).
* `doc/mutation_testing.md` : qualité tests (S14).
* `prompt/tod/22_plan_10_10.md` : roadmap stratégique.

## Checklist "prêt à opérer"

* [ ] Pipeline paper exécuté avec succès (audit chain valide).
* [ ] IHM consultée sur 3 pages clés (cockpit, execution, risk).
* [ ] Procédure failover Alpaca → IBKR comprise (cf. runbook).
* [ ] Localisation backups DB + RPO/RTO connus.
* [ ] Slack `#alpha-trade-critical` rejoint.

