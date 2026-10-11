# Inventaire API — flows

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `flows/__init__.py`

Source SHA-256 : `4d10d0c29bff22e692008ff1a4c4351f74234696b57ef097901e9f86d6ddbbbc`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `flows/daily_pipeline.py`

Source SHA-256 : `fb6f33aaa2c9e1c9e4290a3329879438208eb43bd3848cb42e7444c0163c3693`

- [_pf_flow](../../flows/daily_pipeline.py) — ligne 55 : `def _pf_flow(fn: Callable | None=None, **_kw: Any) -> Any`
- [_pf_task](../../flows/daily_pipeline.py) — ligne 60 : `def _pf_task(fn: Callable | None=None, **_kw: Any) -> Any`
- [flow](../../flows/daily_pipeline.py) — ligne 66 : `def flow(fn: Callable | None=None, **kw: Any) -> Any`
- [task](../../flows/daily_pipeline.py) — ligne 71 : `def task(fn: Callable | None=None, **kw: Any) -> Any`
- [_Noop](../../flows/daily_pipeline.py) — ligne 91 : `class _Noop`
- [_Noop.labels](../../flows/daily_pipeline.py) — ligne 92 : `def labels(self, *_a: Any, **_kw: Any) -> '_Noop'`
- [_Noop.inc](../../flows/daily_pipeline.py) — ligne 95 : `def inc(self, *_a: Any, **_kw: Any) -> None`
- [_Noop.set](../../flows/daily_pipeline.py) — ligne 98 : `def set(self, *_a: Any, **_kw: Any) -> None`
- [_Noop.observe](../../flows/daily_pipeline.py) — ligne 101 : `def observe(self, *_a: Any, **_kw: Any) -> None`
- [StepResult](../../flows/daily_pipeline.py) — ligne 115 : `class StepResult`
- [StepResult.to_dict](../../flows/daily_pipeline.py) — ligne 124 : `def to_dict(self) -> dict[str, Any]`
- [FlowResult](../../flows/daily_pipeline.py) — ligne 129 : `class FlowResult`
- [FlowResult.to_dict](../../flows/daily_pipeline.py) — ligne 141 : `def to_dict(self) -> dict[str, Any]`
- [_safe_import_step](../../flows/daily_pipeline.py) — ligne 150 : `def _safe_import_step(module_path: str, fn_name: str) -> Callable | None`
- [_run_step](../../flows/daily_pipeline.py) — ligne 162 : `def _run_step(step_name: str, fn: Callable | None, *args: Any, **kwargs: Any) -> StepResult`
- [daily_pipeline](../../flows/daily_pipeline.py) — ligne 214 : `def daily_pipeline(run_date: date, account_id: str, *, steps_override: tuple[tuple[str, str, str], ...] | None=None, dry_run: bool=False, config_path: str | Path | None=None) -> FlowResult`
- [_build_parser](../../flows/daily_pipeline.py) — ligne 312 : `def _build_parser() -> argparse.ArgumentParser`
- [main](../../flows/daily_pipeline.py) — ligne 346 : `def main(argv: list[str] | None=None) -> int`
