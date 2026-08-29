# Inventaire API — corporate_actions

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `corporate_actions/cli.py`

- ligne 126 — `def _build_parser() -> argparse.ArgumentParser:`
- ligne 199 — `def _resolve_provider_name(provider: object) -> str:`
- ligne 207 — `def _validate_sync_scope_or_raise(provider: object, symbols: list[str] | None) -> None:`
- ligne 215 — `def _build_apply_preflight(`
- ligne 23 — `def _run_cross_check_yahoo(`
- ligne 256 — `def _load_pending_events_list(engine: object, *, as_of: date) -> list[object]:`
- ligne 271 — `def _resolve_sync_symbols_portfolio(repo: CorporateActionRepository, account_id: str | None = None) -> list[str]:`
- ligne 309 — `def _resolve_sync_symbols(args: argparse.Namespace, repo: CorporateActionRepository, account_id: str | None = None) -> list[str] | None:`
- ligne 349 — `def _resolve_sync_symbols_bar(args: argparse.Namespace, repo: CorporateActionRepository, account_id: str | None = None) -> list[str] | None:`
- ligne 390 — `def _run_sync(args: argparse.Namespace) -> None:`
- ligne 455 — `def _run_apply(args: argparse.Namespace) -> None:`
- ligne 535 — `def _run_status(_args: argparse.Namespace) -> None:`
- ligne 560 — `def _run_all(args: argparse.Namespace) -> None:`
- ligne 72 — `def _emit_and_persist_summary(`
- ligne 771 — `def main() -> None:`
## `corporate_actions/corporate_action_run.py`

- ligne 9 — `def main():`
## `corporate_actions/cross_check_yahoo.py`

- ligne 144 — `def diff_dividends(`
- ligne 30 — `class YahooDividendCrossCheckProvider(CorporateActionProvider):`
## `corporate_actions/db_io.py`

- ligne 24 — `class CorporateActionRepository:`
## `corporate_actions/engine.py`

- ligne 25 — `class CorporateActionEngine:`
## `corporate_actions/models.py`

- ligne 130 — `class CorporateActionApplication:`
- ligne 14 — `class CaType:`
- ligne 148 — `class CashLedgerEntry:`
- ligne 163 — `class PositionSnapshot:`
- ligne 22 — `class CaStatus:`
- ligne 34 — `class CorporateActionEvent:`
## `corporate_actions/processors.py`

- ligne 22 — `def process_dividend(`
- ligne 68 — `def process_split(`
## `corporate_actions/provider.py`

- ligne 234 — `class EodhdCorporateActionProvider(CorporateActionProvider):`
- ligne 33 — `class CorporateActionProvider(ABC):`
- ligne 389 — `def _safe_iso_date(value: Any) -> date | None:`
- ligne 402 — `def build_corporate_action_provider(`
- ligne 51 — `class AlpacaCorporateActionProvider(CorporateActionProvider):`
## `corporate_actions/reconciliation.py`

- ligne 18 — `class CaReconcileDiff:`
- ligne 27 — `def reconcile_after_corporate_actions(`

