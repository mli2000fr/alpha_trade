# -*- coding: utf-8 -*-
"""Vérification d'intégrité du benchmark OOS 2026 (P23 m8) — B25 + P14 + m8.

Usage:  python -m scripts.verify_oos2026_benchmark [--manifest PATH]

Re-hashé tous les fichiers du dossier d'archive et compare au _MANIFEST.json.
Si un fichier diffère -> le benchmark a été modifié (violation).
"""
import argparse
import hashlib
import json
import os
import sys

DEFAULT_MANIFEST = r"F:\projets\artifacts\benchmarks\OOS2026_B25_P14_m8_v1\_MANIFEST.json"


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    args = ap.parse_args()

    if not os.path.exists(args.manifest):
        print(f"ERREUR: manifeste introuvable: {args.manifest}")
        return 1

    manifest = json.load(open(args.manifest, encoding="utf-8"))
    bench_dir = os.path.dirname(args.manifest)
    expected = manifest.get("files", {})
    ok, bad = 0, []
    missing = []

    for name, exp_hash in sorted(expected.items()):
        p = os.path.join(bench_dir, name)
        if not os.path.exists(p):
            missing.append(name)
            continue
        cur = sha256(p)
        if cur == exp_hash:
            ok += 1
        else:
            bad.append(name)

    print(f"Benchmark: {manifest.get('benchmark_id')}")
    print(f"  Créé le : {manifest.get('created_at')}")
    print(f"  Status  : {manifest.get('status')}")
    print(f"  Fichiers OK      : {ok}/{len(expected)}")
    if missing:
        print(f"  Fichiers MANQUANTS: {missing}")
    if bad:
        print(f"  ⚠️ Fichiers MODIFIÉS (violation): {bad}")
    else:
        print("  ✅ INTÉGRITÉ CONFIRMÉE — aucun fichier modifié depuis l'archivage.")
    return 0 if (ok == len(expected) and not bad) else 2


if __name__ == "__main__":
    sys.exit(main())
