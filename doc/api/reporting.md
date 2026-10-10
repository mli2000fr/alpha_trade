# Inventaire API — reporting

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `reporting/__init__.py`

Source SHA-256 : `17065f3a3d1ca99acf094610262bb1b4112d23eb80ccf80407bfdb22f9482fd2`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `reporting/json_schema.py`

Source SHA-256 : `f5808a0445d2a6470febedbf7b7692952f7af958de53549059cec7cd8993bdc2`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `reporting/monthly_report.py`

Source SHA-256 : `14ab08ba9cc9c66152650bf01499b74e0d0fe13e15025f33c807344e35af248f`

- [FillRow](../../reporting/monthly_report.py) — ligne 23 : `class FillRow`
- [CashEvent](../../reporting/monthly_report.py) — ligne 33 : `class CashEvent`
- [MonthlyReportInputs](../../reporting/monthly_report.py) — ligne 41 : `class MonthlyReportInputs`
- [MonthlyReport](../../reporting/monthly_report.py) — ligne 52 : `class MonthlyReport`
- [MonthlyReport.to_dict](../../reporting/monthly_report.py) — ligne 66 : `def to_dict(self) -> dict`
- [MonthlyReport.to_json](../../reporting/monthly_report.py) — ligne 69 : `def to_json(self, *, indent: int | None=2) -> str`
- [_slippage_bps](../../reporting/monthly_report.py) — ligne 73 : `def _slippage_bps(fill: FillRow) -> float`
- [_canonical_payload](../../reporting/monthly_report.py) — ligne 79 : `def _canonical_payload(d: dict) -> bytes`
- [sign_report](../../reporting/monthly_report.py) — ligne 85 : `def sign_report(report: dict, secret: bytes) -> dict`
- [verify_signature](../../reporting/monthly_report.py) — ligne 91 : `def verify_signature(report_dict: dict, secret: bytes) -> bool`
- [build_monthly_report](../../reporting/monthly_report.py) — ligne 101 : `def build_monthly_report(inputs: MonthlyReportInputs, *, secret: bytes) -> MonthlyReport`

## `reporting/pdf_renderer.py`

Source SHA-256 : `1dc407e27d8dda51159f5f0d6494a698fab9d5bccd94228ddb180e7674a71b82`

- [render_text](../../reporting/pdf_renderer.py) — ligne 11 : `def render_text(report_dict: dict) -> str`
- [render_pdf](../../reporting/pdf_renderer.py) — ligne 31 : `def render_pdf(report_dict: dict, output: Path) -> Path`
