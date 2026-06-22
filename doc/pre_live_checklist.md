# Recette pré-live (Sprint S5 — A-013 + A-008)

> **Audience** : opérateur en charge d'une bascule d'un compte Alpaca de
> `paper` vers `live`.
> **Objectif** : éliminer les risques opérationnels (creds en clair, kill
> switch oublié, ML drifté, dry-run absent) avant tout ordre live.
> **Outils** : `python -m execution_engine.preflight` (checks programmatiques),
> `python scripts/run_pre_live_checklist.py` (wrapper qui archive le rapport).
> **Doctrine launcher** : `run_execution.py` = launcher canonique du flux
> `run` ; `python -m execution_engine` = compatibilité `run` + `cancel-all`
> natif.

---

## 1. À faire la veille (J-1)

- [ ] **Run paper complet** vert exécuté dans la journée
      (`python run_execution.py paper --account <id>`).
- [ ] **Dry-run live** validé (`python run_execution.py live --account <id> --dry-run`).
- [ ] **Snapshot DB** récent (sauvegarde `alpha_trade.sql` ou équivalent).
- [ ] **Drift ML OK** : dernier `ml_drift_runs` n'est pas en `ALERT`
      (`SELECT status, payload FROM ml_drift_runs ORDER BY computed_at DESC LIMIT 1;`).
- [ ] **Watcher de protection** prêt à être lancé
      (`python run_execution_protection_watch.py`).
- [ ] **Filet TP/SL S26 vérifié** : aucune position `entry/buy FILLED`
      sans `take_profit` + `initial_stop`/`trailing_stop` ouverts (cf.
      requête SQL dans `doc/manuel/08_page_execution.md` §Cas marché
      fermé). Si non vide → relancer le watcher avant la bascule.

## 2. À faire le jour J (avant ouverture)

- [ ] Variables d'environnement présentes pour le compte cible :
      `ALPACA_<ID>_API_KEY`, `ALPACA_<ID>_SECRET_KEY`, `LOGIN_DB`, `PASSWORD_DB`.
- [ ] **Variables d'environnement alerting** (Sprint S9) configurées :
      `ALPHA_TRADE_SLACK_WEBHOOK`, `ALPHA_TRADE_TELEGRAM_BOT_TOKEN`/`CHAT_ID`,
      `ALPHA_TRADE_DISCORD_WEBHOOK`, `TWILIO_*`, `NUM_SMS_ALERT`.
      Voir `doc/service.md` §10 pour la liste complète.
- [ ] Compte Alpaca live déclaré dans `config.yaml` avec `mode: live` et
      placeholders `${VAR}` (jamais de littéral).
- [ ] Aucun verrou pipeline IHM actif (cf. dashboard Pipeline).
- [ ] **Kill switch global** dispo et testé en paper :
      `python -m execution_engine cancel-all --account <id> --broker-mode paper --dry-run`.
- [ ] Capital alloué au compte vérifié (cohérent avec preset `capital_presets.yaml`).
- [ ] Opérateur disponible pendant toute la séance (ou astreinte définie).

## 3. Validation programmatique (étape **bloquante**)

Lancer :

```powershell
python scripts/run_pre_live_checklist.py --account <id>
```

Effets :

- Exécute les 6 checks listés au §4.
- Écrit un rapport JSON horodaté dans
  `artifacts/pre_live_checks/<YYYYMMDDTHHMMSSZ>_<account>.json`
  (incluant `git_sha`, `config_fingerprint`, `host`, `user`).
- Exit code `0` si tous les checks `ok|warn|skip`, `1` dès un `fail`.

**Aucune bascule live n'est autorisée tant que le checklist n'est pas
PASSED**. Conserver le rapport JSON pour l'audit.

## 4. Détail des 6 checks programmatiques

| # | Check | Source de vérité | Statut FAIL si… |
|---|---|---|---|
| 1 | `no_literal_secrets` | `core.secrets.scan_yaml_for_literal_secrets("config.yaml")` | clé/secret littéral détecté |
| 2 | `alpaca_credentials` | `AccountRegistry` + `client.get_account()` | compte introuvable, mauvais `mode`, ping HTTP échoue |
| 3 | `kill_switch_inactive` | `execution_kill_switch_runs` | enregistrement < 24 h pour le compte |
| 4 | `recent_dry_run` | `execution_runs` | aucun run paper/dry-run `completed` < 24 h |
| 5 | `ml_drift_gate` | `ml_drift_runs.payload.gate_action` | dernier run = `kill_switch_ml` ou `status='ALERT'` |
| 6 | `no_pipeline_lock_held` | `ihm.services.pipeline_lock.list_active_locks()` | un verrou actif IHM |

> En CI / dev offline, utiliser `--skip-network` pour ne pas pinger Alpaca.

## 5. Après la séance

- [ ] Run watcher arrêté proprement (kill switch consigné si nécessaire).
- [ ] Reconciliation DB ↔ broker exécutée
      (`python -m execution_engine.reconciliation`).
- [ ] Rapport pre-live archivé dans le repo d'audit (rétention 365 j —
      cf. `doc/artifacts_retention_policy.md`).
- [ ] Toute anomalie reportée dans `prompt/tod/03_anomalies_register.md`.

---

**Réf.** : `prompt/tod/08_sprint_plan.md` Sprint S5 ; `core/secrets.py` ;
`execution_engine/preflight.py` ; `scripts/run_pre_live_checklist.py` ;
`prompt/tod/15_sprint_S5_delivery_report.md`.

