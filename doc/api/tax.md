# Inventaire API — tax

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `tax/__init__.py`

Source SHA-256 : `24b0c1fe8f12192159fb25e16f427a2d9a0f3eb236edb8bc6566073dcd874a0f`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `tax/wash_sale.py`

Source SHA-256 : `d4996766de6975ed713579093e4f8e67cd98ed4eb372699d8ad201a1d18afa65`

- [Lot](../../tax/wash_sale.py) — ligne 27 : `class Lot`
- [Lot.is_acquisition](../../tax/wash_sale.py) — ligne 36 : `def is_acquisition(self) -> bool`
- [Lot.is_disposition](../../tax/wash_sale.py) — ligne 40 : `def is_disposition(self) -> bool`
- [WashSaleAdjustment](../../tax/wash_sale.py) — ligne 45 : `class WashSaleAdjustment`
- [WashSaleReport](../../tax/wash_sale.py) — ligne 55 : `class WashSaleReport`
- [WashSaleReport.total_disallowed_loss](../../tax/wash_sale.py) — ligne 60 : `def total_disallowed_loss(self) -> float`
- [detect_wash_sales](../../tax/wash_sale.py) — ligne 64 : `def detect_wash_sales(lots: list[Lot], realized_pnl_per_sale: dict[str, float] | None=None) -> WashSaleReport`
