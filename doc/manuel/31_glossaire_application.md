# 31. Glossaire technique de l'application

> Termes spécifiques au code, à la base de données et aux artefacts.

| Terme | Définition |
|---|---|
| `run_id` | Identifiant unique d'une exécution (ex. `pipeline-20260506-220123-a1b2`). |
| `step_key` | Clé d'une étape pipeline (ex. `alpha_scanner`, `risk_management`). |
| `final_score` | Score 0-100 calculé par le Selector (technique). |
| `final_score_sentiment` | `final_score` ajusté par le sentiment news. |
| `is_candidate` | `True` si le symbole passe tous les filtres Selector. |
| `candidates` | Table des candidats du jour. |
| `stock_scores` | Table de sortie du Screener. |
| `ml_predictions` | Table des prédictions ML (probabilité long). |
| `risk_decisions` | Table des décisions risk par symbole. |
| `portfolio_targets` | Portefeuille cible calculé par Risk. |
| `execution_runs` | Table des runs d'exécution. |
| `execution_orders` | Ordres envoyés au broker. |
| `execution_fills` | Fills (exécutions réelles). |
| `protection_watcher` | Processus 24/7 vérifiant les ordres protecteurs. |
| `run_summary` | Résumé JSON d'un run (KPI, business summary). |
| `business_summary` | Phrase synthétique générée par module. |
| `capital_preset` | Bouquet de paramètres par tranche de capital. |
| `fingerprint` | Hash SHA256 court d'une config (preset, modèle…). |
| `simulate` / `paper` / `live` | 3 modes d'exécution. |
| `walk-forward` | Méthode backtest fenêtres glissantes. |
| `champion` / `challenger` | Modèle ML actif vs concurrents. |
| `kill switch` | `cancel-all` du module execution_engine. |
| `audit chain` | Chaîne SHA256 cryptographique des décisions. |
| `cash ledger` | Suivi du cash (dividendes, frais…). |
| `parity report` | Comparaison backtest ↔ live. |
| `reconciliation` | Vérification positions broker ↔ DB. |
| `account_id` | Identifiant Alpaca du compte. |
| `trade_date` | Date trading US (ferme à 22h00 heure FR). |
| `as_of` | Date de référence d'une opération (ex. apply CA). |
| `artifacts/` | Dossier des sorties (modèles, runs, caches). |

