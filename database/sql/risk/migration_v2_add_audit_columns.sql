-- Migration V2 : ajout des colonnes d'audit pour le module risk_management.
-- Migration additive — aucun DROP.

ALTER TABLE risk_decisions
  ADD COLUMN conviction_score    DOUBLE       NULL AFTER sector,
  ADD COLUMN predicted_proba     DOUBLE       NULL AFTER conviction_score,
  ADD COLUMN historical_win_rate DOUBLE       NULL AFTER predicted_proba,
  ADD COLUMN effective_probability DOUBLE     NULL AFTER historical_win_rate,
  ADD COLUMN kelly_fraction      DOUBLE       NULL AFTER effective_probability,
  ADD COLUMN sizing_method       VARCHAR(20)  NULL AFTER kelly_fraction,
  ADD COLUMN correlation_blocker VARCHAR(20)  NULL AFTER sizing_method,
  ADD COLUMN correlation_value   DOUBLE       NULL AFTER correlation_blocker;

ALTER TABLE portfolio_targets
  ADD COLUMN conviction_score    DOUBLE       NULL AFTER score_source,
  ADD COLUMN sizing_method       VARCHAR(20)  NULL AFTER conviction_score,
  ADD COLUMN kelly_fraction      DOUBLE       NULL AFTER sizing_method;

