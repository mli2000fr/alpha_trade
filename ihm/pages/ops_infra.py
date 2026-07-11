"""ihm/pages/ops_infra.py — Infra & Backups (Sprint S5).

Page dédiée aux composants infra du Sprint S5 :

- **T5.1** — Métriques Prometheus pipeline (common.metrics) : vue live des
  compteurs, jauges et histogrammes émis par le pipeline.
- **T5.3** — Backup artefacts ML (scripts/backup_ml_artifacts.py) :
  archive tar.gz + rotation.
- **T5.4** — Backup base de données (scripts/backup_db.py) :
  mysqldump compressé + rotation.

Note : T5.2 (flows/daily_pipeline.py) est disponible en CLI/Prefect mais
n'est pas exposé ici — la page Pipeline couvre déjà l'orchestration
interactive complète (12 étapes, suivi temps réel, registre IHM).
"""
from __future__ import annotations

import datetime
from pathlib import Path

import streamlit as st

from ihm.components.ops_command_panel import render_ops_command_panel
from ihm.pages import run_page_if_standalone
from ihm.services.db import get_runtime_db_config

# ---------------------------------------------------------------------------
# Constantes session_state
# ---------------------------------------------------------------------------
_PREFIX = "ops_infra_"

BACKUP_ML_DIR_KEY = f"{_PREFIX}backup_ml_dir"
BACKUP_ML_DEST_KEY = f"{_PREFIX}backup_ml_dest"
BACKUP_ML_KEEP_KEY = f"{_PREFIX}backup_ml_keep"
BACKUP_ML_DRY_RUN_KEY = f"{_PREFIX}backup_ml_dry_run"

BACKUP_DB_HOST_KEY = f"{_PREFIX}backup_db_host"
BACKUP_DB_NAME_KEY = f"{_PREFIX}backup_db_name"
BACKUP_DB_DEST_KEY = f"{_PREFIX}backup_db_dest"
BACKUP_DB_KEEP_KEY = f"{_PREFIX}backup_db_keep"
BACKUP_DB_DRY_RUN_KEY = f"{_PREFIX}backup_db_dry_run"


# ---------------------------------------------------------------------------
# Section T5.1 — Métriques Prometheus pipeline
# ---------------------------------------------------------------------------


def _render_metrics_panel() -> None:
    """Affiche les valeurs courantes des métriques Prometheus pipeline (T5.1)."""
    st.subheader("📊 T5.1 — Métriques Prometheus pipeline")
    st.caption(
        "Valeurs lues depuis `common.metrics` (en mémoire dans ce process Streamlit). "
        "Ces métriques sont alimentées en temps réel par l'orchestrateur (`flows.daily_pipeline`) "
        "et les scripts de backup. Pour un monitoring global multi-processus, "
        "activer `prometheus_client` et pointer Grafana sur `/metrics` (port `ALPHA_TRADE_METRICS_PORT`)."
    )

    try:
        import common.metrics as cm

        available = cm.is_available()

        if not available:
            st.info(
                "ℹ️ `prometheus_client` non installé — les métriques sont en mode no-op. "
                "Pour activer : `pip install 'alpha-trade[observability]'`",
                icon="ℹ️",
            )

        # Affichage des métriques sous forme de colonnes informatives
        col1, col2, col3 = st.columns(3)
        with col1:
            with st.container(border=True):
                st.markdown("**`alpha_pipeline_steps_total`**")
                st.caption("Counter — nombre d'étapes exécutées par (step, status)")
                st.code("pipeline_steps_total.labels(step='screener', status='OK').inc()", language="python")
                if available:
                    try:
                        # Tentative de lecture de la valeur réelle
                        from prometheus_client import REGISTRY  # type: ignore[import-not-found]
                        val = None
                        for metric in REGISTRY.collect():
                            if metric.name == "alpha_pipeline_steps_total":
                                total = sum(s.value for s in metric.samples if s.name.endswith("_total"))
                                val = int(total)
                                break
                        st.metric("Valeur totale", val if val is not None else "—")
                    except Exception:
                        st.metric("Statut", "✅ Actif (no-op)")
                else:
                    st.metric("Statut", "⚪ No-op")

        with col2:
            with st.container(border=True):
                st.markdown("**`alpha_selections_count`**")
                st.caption("Gauge — candidats sélectionnés après AlphaScanner")
                st.code("selections_count.set(42)", language="python")
                if available:
                    try:
                        from prometheus_client import REGISTRY  # type: ignore[import-not-found]
                        val = None
                        for metric in REGISTRY.collect():
                            if metric.name == "alpha_selections_count":
                                for s in metric.samples:
                                    if s.name == "alpha_selections_count":
                                        val = int(s.value)
                                        break
                                break
                        st.metric("Valeur actuelle", val if val is not None else "—")
                    except Exception:
                        st.metric("Statut", "✅ Actif (no-op)")
                else:
                    st.metric("Statut", "⚪ No-op")

        with col3:
            with st.container(border=True):
                st.markdown("**`alpha_pipeline_duration_seconds`**")
                st.caption("Histogram — durée de chaque étape pipeline")
                st.code("with record_pipeline_step('screener'):\n    ...", language="python")
                if available:
                    try:
                        from prometheus_client import REGISTRY  # type: ignore[import-not-found]
                        count = None
                        for metric in REGISTRY.collect():
                            if metric.name == "alpha_pipeline_duration_seconds":
                                for s in metric.samples:
                                    if s.name.endswith("_count"):
                                        count = int(s.value)
                                        break
                                break
                        st.metric("Observations", count if count is not None else "—")
                    except Exception:
                        st.metric("Statut", "✅ Actif (no-op)")
                else:
                    st.metric("Statut", "⚪ No-op")

        # Métriques backup
        col4, col5, col6 = st.columns(3)
        with col4:
            with st.container(border=True):
                st.markdown("**`alpha_db_backup_total`**")
                st.caption("Counter — backups DB (OK/ERROR)")
                try:
                    from prometheus_client import REGISTRY  # type: ignore[import-not-found]
                    val = None
                    for metric in REGISTRY.collect():
                        if metric.name == "alpha_db_backup_total":
                            total = sum(s.value for s in metric.samples if s.name.endswith("_total"))
                            val = int(total)
                            break
                    st.metric("Total runs", val if val is not None else "—")
                except Exception:
                    st.metric("Statut", "⚪ No-op / inactif")

        with col5:
            with st.container(border=True):
                st.markdown("**`alpha_ml_backup_total`**")
                st.caption("Counter — backups ML (OK/ERROR)")
                try:
                    from prometheus_client import REGISTRY  # type: ignore[import-not-found]
                    val = None
                    for metric in REGISTRY.collect():
                        if metric.name == "alpha_ml_backup_total":
                            total = sum(s.value for s in metric.samples if s.name.endswith("_total"))
                            val = int(total)
                            break
                    st.metric("Total runs", val if val is not None else "—")
                except Exception:
                    st.metric("Statut", "⚪ No-op / inactif")

        with col6:
            with st.container(border=True):
                st.markdown("**`alpha_ml_train_duration_seconds`**")
                st.caption("Histogram — durée d'entraînement par symbole")
                try:
                    from prometheus_client import REGISTRY  # type: ignore[import-not-found]
                    count = None
                    for metric in REGISTRY.collect():
                        if metric.name == "alpha_ml_train_duration_seconds":
                            for s in metric.samples:
                                if s.name.endswith("_count"):
                                    count = int(s.value)
                                    break
                            break
                    st.metric("Observations", count if count is not None else "—")
                except Exception:
                    st.metric("Statut", "⚪ No-op / inactif")

    except ImportError:
        st.error("Module `common.metrics` introuvable.")

    with st.expander("ℹ️ Comment utiliser T5.1 — Prometheus dans votre code", expanded=False):
        st.markdown("""
**Dans vos scripts ou modules Python :**
```python
from common.metrics import pipeline_steps_total, selections_count, record_pipeline_step

# Incrémenter un counter manuellement
pipeline_steps_total.labels(step="screener", status="OK").inc()

# Modifier une jauge
selections_count.set(42)

# Context-manager automatique (mesure durée + status)
with record_pipeline_step("import_bars"):
    run_import_bars(date)  # durée et OK/ERROR émis automatiquement
```

**Pour exposer les métriques à Prometheus/Grafana :**
```bash
export ALPHA_TRADE_METRICS_PORT=9100
# Toute application appelant core.metrics.start_metrics_server() démarrera /metrics sur ce port
```
        """)



# ---------------------------------------------------------------------------
# Section T5.3 — Backup artefacts ML
# ---------------------------------------------------------------------------


def _list_existing_archives(dest_dir_str: str, pattern: str = "*.tar.gz") -> list[Path]:
    """Retourne les archives existantes triées par mtime décroissant."""
    try:
        d = Path(dest_dir_str)
        if not d.exists():
            return []
        return sorted(d.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        return []


def _render_backup_ml_panel(*, db_config: dict) -> None:
    """Panel de backup artefacts ML (T5.3)."""
    st.subheader("🤖 T5.3 — Backup artefacts ML")
    st.caption(
        "Archive le répertoire `artifacts/models/` en `.tar.gz` horodaté. "
        "Rotation automatique : seules les N dernières archives sont conservées."
    )

    with st.expander("ℹ️ Comment utiliser T5.3 — Backup ML", expanded=False):
        st.markdown("""
**En ligne de commande :**
```bash
# Backup standard (7 archives conservées)
python scripts/backup_ml_artifacts.py \\
    --artifacts-dir artifacts/models \\
    --dest-dir backups/ml \\
    --keep 7

# Dry-run : rapport sans écriture
python scripts/backup_ml_artifacts.py --artifacts-dir artifacts/models --dry-run

# Sauvegarder sur un disque externe
python scripts/backup_ml_artifacts.py \\
    --artifacts-dir artifacts/models \\
    --dest-dir D:/alpha_trade_backups/ml \\
    --keep 30
```

**Automatisation via Windows Task Scheduler :**
```
Action : python scripts/backup_ml_artifacts.py --artifacts-dir artifacts/models --dest-dir backups/ml
Déclencheur : tous les jours à 03h00
```

**Structure de l'archive :**
```
backups/ml/ml_artifacts_20260517_030000.tar.gz
  └── models/
       ├── AAPL/config.json, metrics.json, lightgbm_model.pkl...
       ├── MSFT/...
       └── __GLOBAL__/...
```

**Restauration :**
```bash
tar -xzf backups/ml/ml_artifacts_20260517_030000.tar.gz -C artifacts/
```
        """)

    col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
    artifacts_dir = col1.text_input(
        "Répertoire source (artifacts)",
        value="artifacts/models",
        key=BACKUP_ML_DIR_KEY,
        help="Chemin vers artifacts/models/ à archiver.",
    )
    dest_dir = col2.text_input(
        "Répertoire destination",
        value="backups/ml",
        key=BACKUP_ML_DEST_KEY,
        help="Où stocker les archives .tar.gz.",
    )
    keep = col3.number_input(
        "Garder N",
        min_value=1,
        value=7,
        step=1,
        key=BACKUP_ML_KEEP_KEY,
        help="Nombre d'archives à conserver (les plus anciennes sont supprimées).",
    )
    dry_run = col4.checkbox(
        "Dry-run",
        value=False,
        key=BACKUP_ML_DRY_RUN_KEY,
        help="Simule sans créer d'archive ni supprimer.",
    )

    render_ops_command_panel(
        "backup_ml_artifacts",
        db_config=db_config,
        command_kwargs={
            "artifacts_dir": artifacts_dir,
            "dest_dir": dest_dir,
            "keep": int(keep),
            "dry_run": dry_run,
        },
    )

    # Liste des archives existantes
    archives = _list_existing_archives(dest_dir, "ml_artifacts_*.tar.gz")
    if archives:
        with st.expander(f"📦 {len(archives)} archive(s) existante(s) dans `{dest_dir}`", expanded=False):
            for arch in archives[:20]:
                size_mb = arch.stat().st_size / 1024 / 1024
                mtime = datetime.datetime.fromtimestamp(arch.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                st.markdown(f"- `{arch.name}` — {size_mb:.1f} MB — {mtime}")
    else:
        st.caption(f"Aucune archive dans `{dest_dir}` pour l'instant.")


# ---------------------------------------------------------------------------
# Section T5.4 — Backup DB
# ---------------------------------------------------------------------------


def _render_backup_db_panel(*, db_config: dict) -> None:
    """Panel de backup base de données (T5.4)."""
    st.subheader("🗄️ T5.4 — Backup base de données")
    st.caption(
        "Exécute `mysqldump` et compresse le dump en `.sql.gz` horodaté. "
        "Rotation automatique : seuls les N derniers dumps sont conservés. "
        "Requiert `LOGIN_DB` / `PASSWORD_DB` dans l'environnement."
    )

    with st.expander("ℹ️ Comment utiliser T5.4 — Backup DB", expanded=False):
        st.markdown("""
**Prérequis :**
- `mysqldump` installé et dans le PATH (fourni avec MySQL Server)
- Variables d'environnement `LOGIN_DB` et `PASSWORD_DB` définies

**En ligne de commande :**
```bash
# Backup standard (30 dumps conservés)
LOGIN_DB=alpha_user PASSWORD_DB=secret python scripts/backup_db.py \\
    --host localhost \\
    --db alpha_trade \\
    --dest-dir backups/db \\
    --keep 30

# Dry-run : rapport sans exécuter mysqldump
python scripts/backup_db.py --dry-run

# Vérifier que mysqldump est disponible
where mysqldump  # Windows
which mysqldump  # Linux/Mac
```

**Automatisation via Windows Task Scheduler :**
```
Action : python scripts/backup_db.py --host localhost --db alpha_trade --dest-dir backups/db
Déclencheur : tous les jours à 02h00
Variables env : LOGIN_DB, PASSWORD_DB
```

**Structure du dump :**
```
backups/db/alpha_trade_20260517_020000.sql.gz
```

**Restauration (via scripts/restore_from_backup.py) :**
```bash
python scripts/restore_from_backup.py \\
    --dump-path backups/db/alpha_trade_20260517_020000.sql.gz \\
    --target-host localhost \\
    --target-db alpha_trade
```
        """)

    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
    db_host = col1.text_input(
        "Hôte MySQL",
        value=db_config.get("host") or "localhost",
        key=BACKUP_DB_HOST_KEY,
        help="Hôte du serveur MySQL.",
    )
    db_name = col2.text_input(
        "Base de données",
        value=db_config.get("db") or "alpha_trade",
        key=BACKUP_DB_NAME_KEY,
        help="Nom de la base à sauvegarder.",
    )
    dest_dir = col3.text_input(
        "Répertoire destination",
        value="backups/db",
        key=BACKUP_DB_DEST_KEY,
        help="Où stocker les dumps .sql.gz.",
    )
    keep = col4.number_input(
        "Garder N",
        min_value=1,
        value=30,
        step=1,
        key=BACKUP_DB_KEEP_KEY,
        help="Nombre de dumps à conserver.",
    )
    dry_run = col5.checkbox(
        "Dry-run",
        value=True,
        key=BACKUP_DB_DRY_RUN_KEY,
        help="Simule sans exécuter mysqldump.",
    )

    render_ops_command_panel(
        "backup_db",
        db_config=db_config,
        command_kwargs={
            "host": db_host,
            "db": db_name,
            "dest_dir": dest_dir,
            "keep": int(keep),
            "dry_run": dry_run,
        },
    )

    # Liste des dumps existants
    dumps = _list_existing_archives(dest_dir, "*.sql.gz")
    if dumps:
        with st.expander(f"🗃️ {len(dumps)} dump(s) existant(s) dans `{dest_dir}`", expanded=False):
            for dump in dumps[:20]:
                size_mb = dump.stat().st_size / 1024 / 1024
                mtime = datetime.datetime.fromtimestamp(dump.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                st.markdown(f"- `{dump.name}` — {size_mb:.1f} MB — {mtime}")
    else:
        st.caption(f"Aucun dump dans `{dest_dir}` pour l'instant.")


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    st.header("🔧 Infra & Backups (Sprint S5)")
    st.caption(
        "Supervision et lancement des composants infra pro-grade : "
        "métriques Prometheus pipeline, backup artefacts ML et backup base de données. "
        "Pour l'orchestration interactive du pipeline complet, utiliser la page **Pipeline**."
    )

    db_config = get_runtime_db_config()
    account_id = st.session_state.get("selected_account_id")

    # ── T5.1 — Métriques ─────────────────────────────────────────────────────
    with st.container(border=True):
        _render_metrics_panel()


    # ── T5.3 — Backup ML ──────────────────────────────────────────────────────
    with st.container(border=True):
        _render_backup_ml_panel(db_config=db_config)

    # ── T5.4 — Backup DB ──────────────────────────────────────────────────────
    with st.container(border=True):
        _render_backup_db_panel(db_config=db_config)

    # ── Guide rapide opérateur ────────────────────────────────────────────────
    with st.expander("📋 Guide rapide opérateur — automatisation quotidienne", expanded=False):
        st.markdown("""
## Flux quotidien recommandé

| Heure | Action | Commande |
|---|---|---|
| 02h00 | Backup DB | `python scripts/backup_db.py --keep 30` |
| 03h00 | Backup ML | `python scripts/backup_ml_artifacts.py --keep 7` |
| 06h30 | Pipeline complet | Via la page **Pipeline** → Workflow complet configurable |

> Pour un lancement en batch/cron sans IHM :
> `python -m flows.daily_pipeline --date $(date +%Y-%m-%d) --account-id paper1`

## Vérification des backups

```bash
# Lister les archives ML
dir backups\\ml\\

# Lister les dumps DB
dir backups\\db\\

# Tester l'intégrité d'une archive ML
python -c "import tarfile; tf=tarfile.open('backups/ml/ml_artifacts_XXX.tar.gz'); print(len(tf.getnames()), 'fichiers')"
```
        """)


run_page_if_standalone(__name__, render)

