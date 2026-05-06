"""Phase C / S16.2 — Tests Brinson-Fachler."""
from __future__ import annotations

import pytest

from backtesting.brinson_fachler import SectorBucket, compute_brinson_fachler


def test_brinson_fachler_identity():
    buckets = [
        SectorBucket("Tech", 0.6, 0.4, 0.10, 0.08),
        SectorBucket("Energy", 0.4, 0.6, 0.05, 0.06),
    ]
    res = compute_brinson_fachler(buckets)
    # somme des 3 effets = active return
    total_decomp = res.total_allocation + res.total_selection + res.total_interaction
    assert abs(total_decomp - res.total_active_return) < 1e-9


def test_brinson_fachler_per_sector_total_consistent():
    buckets = [
        SectorBucket("A", 0.5, 0.5, 0.05, 0.04),
        SectorBucket("B", 0.5, 0.5, 0.02, 0.03),
    ]
    res = compute_brinson_fachler(buckets)
    s = sum(a.total for a in res.sectors)
    assert abs(s - (res.portfolio_return - res.benchmark_return)) < 1e-9


def test_weight_normalization_required():
    buckets = [
        SectorBucket("A", 0.5, 0.4, 0.1, 0.1),  # poids ne somment pas à 1
    ]
    with pytest.raises(ValueError):
        compute_brinson_fachler(buckets)


def test_pure_allocation_effect():
    """Sélection nulle si returns sectoriels = benchmark."""
    buckets = [
        SectorBucket("Tech", 0.7, 0.3, 0.10, 0.10),
        SectorBucket("Energy", 0.3, 0.7, 0.02, 0.02),
    ]
    res = compute_brinson_fachler(buckets)
    assert all(abs(a.selection) < 1e-12 for a in res.sectors)
    assert all(abs(a.interaction) < 1e-12 for a in res.sectors)

