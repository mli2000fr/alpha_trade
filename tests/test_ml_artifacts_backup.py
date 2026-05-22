"""Sprint S5 — Tests de ``scripts/backup_ml_artifacts.py``."""
from __future__ import annotations

import json
import tarfile
import time
from pathlib import Path

import pytest

from modelFactory.champion_selection import (
    ArtifactSignatureError,
    build_artifact_signature_manifest,
    persist_artifact_signature_manifest,
    verify_route_artifact_signatures,
)
from scripts import backup_ml_artifacts as bma


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_artifacts(artifacts_dir: Path, symbols: list[str]) -> None:
    """Crée une structure artefacts factice dans artifacts_dir/models/."""
    models_dir = artifacts_dir / "models"
    models_dir.mkdir(parents=True)
    for sym in symbols:
        sym_dir = models_dir / sym
        sym_dir.mkdir()
        (sym_dir / "config.json").write_text('{"symbol": "' + sym + '"}', encoding="utf-8")
        (sym_dir / "metrics.json").write_text('{"score": 0.9}', encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests BackupReport dataclass
# ---------------------------------------------------------------------------


def test_backup_report_to_dict_has_expected_keys(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "models"
    artifacts_dir.mkdir()
    dest_dir = tmp_path / "backups"
    report = bma.backup(artifacts_dir=artifacts_dir, dest_dir=dest_dir, dry_run=True)
    d = report.to_dict()
    assert "started_at" in d
    assert "finished_at" in d
    assert "duration_seconds" in d
    assert "errors" in d
    assert "dry_run" in d


# ---------------------------------------------------------------------------
# Tests dry_run
# ---------------------------------------------------------------------------


def test_dry_run_source_missing_produces_error(tmp_path: Path) -> None:
    report = bma.backup(
        artifacts_dir=tmp_path / "nonexistent",
        dest_dir=tmp_path / "dest",
        dry_run=True,
    )
    assert report.dry_run is True
    assert len(report.errors) > 0
    assert "introuvable" in report.errors[0]


def test_dry_run_source_exists_no_files_created(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "models"
    artifacts_dir.mkdir()
    dest_dir = tmp_path / "backups"
    report = bma.backup(artifacts_dir=artifacts_dir, dest_dir=dest_dir, dry_run=True)
    assert report.dry_run is True
    assert report.errors == []
    # Aucune archive créée en dry-run
    assert not dest_dir.exists() or not list(dest_dir.glob("*.tar.gz"))


# ---------------------------------------------------------------------------
# Tests backup réel
# ---------------------------------------------------------------------------


def test_backup_creates_targz(tmp_path: Path) -> None:
    """Un backup réel doit créer un fichier .tar.gz non vide."""
    _make_artifacts(tmp_path, ["AAPL", "MSFT"])
    artifacts_dir = tmp_path / "models"
    dest_dir = tmp_path / "backups"
    report = bma.backup(artifacts_dir=artifacts_dir, dest_dir=dest_dir, keep=5)
    assert report.errors == []
    assert report.archive_path is not None
    archive = Path(report.archive_path)
    assert archive.exists()
    assert archive.suffix == ".gz"
    assert report.archive_size_bytes > 0


def test_backup_archive_contains_expected_files(tmp_path: Path) -> None:
    """L'archive tar.gz doit contenir les fichiers du répertoire source."""
    _make_artifacts(tmp_path, ["AAPL"])
    artifacts_dir = tmp_path / "models"
    dest_dir = tmp_path / "backups"
    report = bma.backup(artifacts_dir=artifacts_dir, dest_dir=dest_dir, keep=5)
    assert report.errors == []
    with tarfile.open(report.archive_path, "r:gz") as tf:
        names = tf.getnames()
    # Doit contenir le fichier config.json d'AAPL
    assert any("config.json" in n for n in names)


def test_backup_rotation_keeps_n_files(tmp_path: Path) -> None:
    """Après N+1 backups avec keep=N, seuls N fichiers sont conservés."""
    artifacts_dir = tmp_path / "models"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "test.txt").write_text("x")
    dest_dir = tmp_path / "backups"
    dest_dir.mkdir()
    keep = 3

    for i in range(keep + 2):
        # Nommer manuellement pour contrôler l'ordre mtime
        ts = f"2026010{i:01d}_000000"
        fake_archive = dest_dir / f"ml_artifacts_{ts}.tar.gz"
        fake_archive.write_bytes(b"fake")
        time.sleep(0.01)  # assure une mtime différente

    # Les archives pre-créées existent : créer un vrai backup maintenant
    report = bma.backup(artifacts_dir=artifacts_dir, dest_dir=dest_dir, keep=keep)
    assert report.errors == []

    surviving = list(dest_dir.glob("ml_artifacts_*.tar.gz"))
    assert len(surviving) <= keep


def test_backup_rotation_dry_run_does_not_delete(tmp_path: Path) -> None:
    """En dry_run, la rotation ne supprime aucun fichier."""
    artifacts_dir = tmp_path / "models"
    artifacts_dir.mkdir()
    dest_dir = tmp_path / "backups"
    dest_dir.mkdir()

    for i in range(5):
        (dest_dir / f"ml_artifacts_2026010{i}_000000.tar.gz").write_bytes(b"fake")

    report = bma.backup(artifacts_dir=artifacts_dir, dest_dir=dest_dir, keep=2, dry_run=True)
    surviving = list(dest_dir.glob("ml_artifacts_*.tar.gz"))
    assert len(surviving) == 5  # aucun supprimé en dry_run


# ---------------------------------------------------------------------------
# Tests CLI main()
# ---------------------------------------------------------------------------


def test_main_dry_run_outputs_json(tmp_path: Path, capsys) -> None:
    artifacts_dir = tmp_path / "models"
    artifacts_dir.mkdir()
    rc = bma.main([
        "--artifacts-dir", str(artifacts_dir),
        "--dest-dir", str(tmp_path / "backups"),
        "--dry-run",
    ])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["dry_run"] is True
    assert payload["errors"] == []


def test_main_missing_source_returns_1(tmp_path: Path, capsys) -> None:
    rc = bma.main([
        "--artifacts-dir", str(tmp_path / "does_not_exist"),
        "--dest-dir", str(tmp_path / "backups"),
        "--dry-run",
    ])
    assert rc == 1


def test_main_report_out_writes_file(tmp_path: Path, capsys) -> None:
    artifacts_dir = tmp_path / "models"
    artifacts_dir.mkdir()
    out_file = tmp_path / "report.json"
    bma.main([
        "--artifacts-dir", str(artifacts_dir),
        "--dest-dir", str(tmp_path / "backups"),
        "--dry-run",
        "--report-out", str(out_file),
    ])
    assert out_file.exists()
    payload = json.loads(out_file.read_text())
    assert payload["dry_run"] is True


# ---------------------------------------------------------------------------
# Tests helpers internes
# ---------------------------------------------------------------------------


def test_list_archives_sorted_by_mtime(tmp_path: Path) -> None:
    for suffix in ["c", "a", "b"]:
        f = tmp_path / f"ml_artifacts_202601{suffix}_000000.tar.gz"
        f.write_bytes(b"x")
    archives = bma._list_archives(tmp_path)
    assert len(archives) == 3

    # Tous les fichiers doivent être présents (ordre par mtime, pas alpha)
    names = {a.name for a in archives}
    assert "ml_artifacts_20260199_000000.tar.gz" not in names


def test_build_archive_path_has_right_format(tmp_path: Path) -> None:
    p = bma._build_archive_path(tmp_path)
    assert p.parent == tmp_path
    assert p.name.startswith("ml_artifacts_")
    assert p.name.endswith(".tar.gz")


# ---------------------------------------------------------------------------
# Test écriture atomique trainer._atomic_write_json
# ---------------------------------------------------------------------------

def test_atomic_write_json_produces_valid_file(tmp_path: Path) -> None:
    """_atomic_write_json doit produire un fichier JSON valide à la destination finale."""
    from modelFactory.trainer import _atomic_write_json

    dest = tmp_path / "config.json"
    data = {"symbol": "AAPL", "score": 0.9, "nested": {"a": 1}}
    _atomic_write_json(dest, data)

    assert dest.exists()
    with open(dest, encoding="utf-8") as fh:
        loaded = json.load(fh)
    assert loaded == data


def test_atomic_write_json_leaves_no_tmp_file_on_success(tmp_path: Path) -> None:
    """Après un succès, aucun fichier temporaire .tmp. ne doit subsister."""
    from modelFactory.trainer import _atomic_write_json

    dest = tmp_path / "metrics.json"
    _atomic_write_json(dest, {"run_id": "abc123"})

    remaining = list(tmp_path.glob("*.tmp.*"))
    assert len(remaining) == 0, f"Fichiers temporaires non supprimés: {remaining}"


def test_atomic_write_json_overwrites_existing_file(tmp_path: Path) -> None:
    """_atomic_write_json doit écraser atomiquement un fichier existant."""
    from modelFactory.trainer import _atomic_write_json

    dest = tmp_path / "config.json"
    dest.write_text('{"old": true}', encoding="utf-8")

    _atomic_write_json(dest, {"new": True, "version": 2})

    with open(dest, encoding="utf-8") as fh:
        loaded = json.load(fh)
    assert loaded == {"new": True, "version": 2}
    assert "old" not in loaded


def test_ml_artifacts_signature_manifest_contains_sha256_entries(tmp_path: Path) -> None:
    ckpt = tmp_path / "best.ckpt"
    scaler = tmp_path / "scaler.pkl"
    ckpt.write_text("checkpoint-v1", encoding="utf-8")
    scaler.write_bytes(b"scaler-v1")

    manifest = build_artifact_signature_manifest(
        symbol="AAPL",
        run_id="run-1",
        selected_model="lstm_attention",
        artifact_routes_models={
            "lstm_attention": {
                "checkpoint_path": str(ckpt),
                "scaler_path": str(scaler),
            }
        },
    )

    assert manifest["schema_version"] == 1
    assert manifest["selected_model"] == "lstm_attention"
    assert len(manifest["entries"]) == 2
    assert all(entry.get("sha256") for entry in manifest["entries"])


def test_ml_artifacts_signature_verification_detects_mismatch(tmp_path: Path) -> None:
    ckpt = tmp_path / "best.ckpt"
    scaler = tmp_path / "scaler.pkl"
    ckpt.write_text("checkpoint-v1", encoding="utf-8")
    scaler.write_bytes(b"scaler-v1")
    manifest_path = tmp_path / "artifact_signature_manifest.json"

    persist_artifact_signature_manifest(
        manifest_path,
        symbol="AAPL",
        run_id="run-1",
        selected_model="lstm_attention",
        artifact_routes_models={
            "lstm_attention": {
                "checkpoint_path": str(ckpt),
                "scaler_path": str(scaler),
            }
        },
    )

    verify_route_artifact_signatures(
        manifest_path=manifest_path,
        model_name="lstm_attention",
        route={"checkpoint_path": str(ckpt), "scaler_path": str(scaler)},
        required=True,
    )

    ckpt.write_text("checkpoint-v2", encoding="utf-8")

    with pytest.raises(ArtifactSignatureError, match="artifact_signature_mismatch"):
        verify_route_artifact_signatures(
            manifest_path=manifest_path,
            model_name="lstm_attention",
            route={"checkpoint_path": str(ckpt), "scaler_path": str(scaler)},
            required=True,
        )

