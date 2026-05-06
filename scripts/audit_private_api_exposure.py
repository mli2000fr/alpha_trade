"""Sprint S25.4 — Audit des symboles privés exposés.

Parcourt ``core/``, ``service/``, ``risk_management/`` :

1. Liste tous les symboles **publics** définis (sans underscore initial)
   via AST → constitue le set de l'API publique de fait.
2. Détecte les usages externes de symboles **privés** (avec underscore
   initial) — un import ``from pkg import _foo`` depuis un module hors
   du package ``pkg`` est suspect.

Sortie : ``artifacts/api_audit/<date>/exposure.json`` + diff vs
``doc/api_v1_public_symbols.txt`` (golden file).

Mode ``--apply`` : ajoute automatiquement le décorateur
``@deprecated_v1(reason=..., since="1.0")`` au-dessus des symboles
privés exposés (revue humaine recommandée avant commit).
"""
from __future__ import annotations

import argparse
import ast
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCANNED_PACKAGES = ("core", "service", "risk_management")
GOLDEN_FILE = PROJECT_ROOT / "doc" / "api_v1_public_symbols.txt"


@dataclass
class PublicSymbol:
    package: str
    module: str
    name: str
    kind: str  # "function" | "class" | "constant"

    def qualname(self) -> str:
        return f"{self.module}.{self.name}"


@dataclass
class PrivateExposure:
    importing_module: str
    source_module: str
    symbol: str

    def to_dict(self) -> dict:
        return {
            "importing_module": self.importing_module,
            "source_module": self.source_module,
            "symbol": self.symbol,
        }


def _module_name(path: Path) -> str:
    rel = path.relative_to(PROJECT_ROOT).with_suffix("")
    parts = rel.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _iter_python_files(packages: Iterable[str]) -> Iterable[Path]:
    for pkg in packages:
        root = PROJECT_ROOT / pkg
        if not root.exists():
            continue
        yield from root.rglob("*.py")


def _collect_public_symbols(packages: Iterable[str]) -> list[PublicSymbol]:
    results: list[PublicSymbol] = []
    for pkg in packages:
        root = PROJECT_ROOT / pkg
        if not root.exists():
            continue
        for py in root.rglob("*.py"):
            if any(part.startswith("_") and part != "__init__.py"
                   for part in py.relative_to(root).parts):
                continue  # module privé
            module = _module_name(py)
            try:
                tree = ast.parse(py.read_text("utf-8"))
            except Exception:  # pragma: no cover
                continue
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith("_"):
                        results.append(PublicSymbol(pkg, module, node.name, "function"))
                elif isinstance(node, ast.ClassDef):
                    if not node.name.startswith("_"):
                        results.append(PublicSymbol(pkg, module, node.name, "class"))
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and not target.id.startswith("_"):
                            if target.id.isupper():
                                results.append(
                                    PublicSymbol(pkg, module, target.id, "constant")
                                )
    return results


def _collect_private_exposures(packages: Iterable[str]) -> list[PrivateExposure]:
    """Scan TOUTE la codebase à la recherche d'imports de symboles privés
    venant des packages surveillés."""
    targets = set(packages)
    results: list[PrivateExposure] = []
    for py in PROJECT_ROOT.rglob("*.py"):
        try:
            rel = py.relative_to(PROJECT_ROOT)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] in {"htmlcov", "alpha_trade.egg-info",
                                           ".venv", "venv", "build", "dist"}:
            continue
        try:
            tree = ast.parse(py.read_text("utf-8"))
        except Exception:
            continue
        importer = _module_name(py)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                root_pkg = node.module.split(".")[0]
                if root_pkg not in targets:
                    continue
                # Importer doit être hors du même package racine.
                if importer.split(".")[0] == root_pkg:
                    continue
                for alias in node.names:
                    if alias.name.startswith("_") and alias.name != "__all__":
                        results.append(PrivateExposure(
                            importing_module=importer,
                            source_module=node.module,
                            symbol=alias.name,
                        ))
    return results


def _load_golden() -> set[str]:
    if not GOLDEN_FILE.exists():
        return set()
    return {
        line.strip() for line in GOLDEN_FILE.read_text("utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def write_report(
    public: list[PublicSymbol],
    private: list[PrivateExposure],
    out_dir: Path,
) -> Path:
    date_dir = out_dir / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    target = date_dir / "exposure.json"
    golden = _load_golden()
    public_qnames = sorted({s.qualname() for s in public})
    new_public = sorted(set(public_qnames) - golden) if golden else []
    removed_public = sorted(golden - set(public_qnames)) if golden else []
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scanned_packages": list(SCANNED_PACKAGES),
        "n_public": len(public_qnames),
        "n_private_exposures": len(private),
        "golden_loaded": bool(golden),
        "new_public_symbols": new_public,
        "removed_public_symbols": removed_public,
        "private_exposures": [p.to_dict() for p in private],
        "public_symbols": [
            {"qualname": s.qualname(), "kind": s.kind, "package": s.package}
            for s in public
        ],
    }
    target.write_text(json.dumps(payload, indent=2), "utf-8")
    return target


def _emit_suggested_patches(
    private: list[PrivateExposure],
    out_dir: Path,
) -> Path:
    """Mode `--apply` (dry-run, option B) — Sprint S25.4.

    Pour chaque exposition de symbole privé, calcule le patch suggéré
    (insertion d'un `from core._deprecation import deprecated_v1` puis
    décorateur `@deprecated_v1(reason=..., since="1.0")` au-dessus de la
    définition) et l'écrit dans ``suggested_patches.json``. Aucune
    modification de fichier source — la décision de migration vs
    dépréciation reste manuelle (audit-friendly).
    """
    suggestions: list[dict] = []
    for exp in private:
        # On localise la *définition* du symbole privé dans le module
        # source. Si introuvable, on émet un patch « consommateur »
        # uniquement (ajout import + suggestion de migration vers API
        # publique).
        src_module_path = PROJECT_ROOT / Path(*exp.source_module.split("."))
        candidates = [
            src_module_path.with_suffix(".py"),
            src_module_path / "__init__.py",
        ]
        target_file = next((c for c in candidates if c.exists()), None)
        line_no = None
        if target_file is not None:
            try:
                tree = ast.parse(target_file.read_text("utf-8"))
                for node in ast.walk(tree):
                    if isinstance(
                        node,
                        (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                    ) and node.name == exp.symbol:
                        line_no = node.lineno
                        break
            except Exception:  # pragma: no cover - lecture défensive
                line_no = None
        suggestions.append({
            "importing_module": exp.importing_module,
            "source_module": exp.source_module,
            "symbol": exp.symbol,
            "target_file": (
                str(target_file.relative_to(PROJECT_ROOT))
                if target_file else None
            ),
            "definition_line": line_no,
            "suggested_patch": {
                "insert_import": (
                    "from core._deprecation import deprecated_v1"
                ),
                "decorator": (
                    f'@deprecated_v1(reason="exposed via {exp.importing_module}", '
                    f'since="1.0")'
                ),
                "rationale": (
                    "Ce symbole privé est consommé hors de son package. "
                    "Choisir : (a) le promouvoir API publique, "
                    "(b) migrer le consommateur vers l'API publique, "
                    "(c) appliquer @deprecated_v1 (revue humaine requise)."
                ),
            },
        })
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "suggested_patches.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run",
        "n_suggestions": len(suggestions),
        "suggestions": suggestions,
    }
    target.write_text(json.dumps(payload, indent=2), "utf-8")
    return target


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Audit API publique v1.0.")
    p.add_argument("--out", type=Path,
                   default=PROJECT_ROOT / "artifacts" / "api_audit")
    p.add_argument("--update-golden", action="store_true",
                   help="Met à jour doc/api_v1_public_symbols.txt avec "
                        "le snapshot courant.")
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 si nouveaux symboles publics non listés.")
    p.add_argument("--apply", action="store_true",
                   help="Mode dry-run : génère un patch suggéré "
                        "(décorateur @deprecated_v1) pour chaque symbole "
                        "privé exposé sans modifier les fichiers source. "
                        "Le patch est écrit dans "
                        "artifacts/api_audit/<date>/suggested_patches.json. "
                        "L'application réelle doit être validée par "
                        "revue humaine avant commit.")
    args = p.parse_args(argv)

    public = _collect_public_symbols(SCANNED_PACKAGES)
    private = _collect_private_exposures(SCANNED_PACKAGES)
    target = write_report(public, private, args.out)

    qnames = sorted({s.qualname() for s in public})
    print(f"[api_audit] public={len(qnames)} private_exposures={len(private)} -> {target}")

    if args.apply:
        patch_path = _emit_suggested_patches(private, target.parent)
        print(f"[api_audit] suggested patches (dry-run) écrit : {patch_path}")

    if args.update_golden:
        GOLDEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        header = (
            "# Liste figée des symboles publics v1.0 d'Alpha Trade.\n"
            "# Générée par scripts/audit_private_api_exposure.py --update-golden.\n"
            "# Toute addition/suppression non validée fait échouer "
            "tests/test_api_v1_stability.py.\n"
        )
        GOLDEN_FILE.write_text(header + "\n".join(qnames) + "\n", "utf-8")
        print(f"[api_audit] golden file mis à jour : {GOLDEN_FILE}")
        return 0

    if args.strict:
        golden = _load_golden()
        if golden:
            new = set(qnames) - golden
            if new:
                print("[api_audit] STRICT FAIL — symboles non listés :")
                for q in sorted(new):
                    print(f"  + {q}")
                return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

