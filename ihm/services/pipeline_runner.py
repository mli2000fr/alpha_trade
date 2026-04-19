"""Services d'orchestration légère des pipelines depuis l'IHM Streamlit."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

PROJECT_ROOT = Path(__file__).resolve().parents[2]

AccountUsage = Literal["none", "alpaca"]
PipelineExecutionStatus = Literal["starting", "running", "completed", "failed", "timeout"]


@dataclass(frozen=True, slots=True)
class PipelineLaunchOptions:
    """Options saisies dans l'IHM pour lancer une étape du pipeline."""

    account_id: str | None = None
    trade_date: str | None = None
    risk_account_equity: float = 100_000.0
    execution_mode: Literal["simulate", "paper", "live"] = "simulate"
    execution_run_id: str | None = None
    allow_outside_rth: bool = False
    auto_rebalance: bool = False


@dataclass(frozen=True, slots=True)
class PipelineStepDefinition:
    """Description d'une étape affichée dans la page Pipeline."""

    key: str
    num: str
    name: str
    desc: str
    tables: str
    deps: str
    account_usage: AccountUsage = "none"


@dataclass(frozen=True, slots=True)
class PipelineRunResult:
    """Résultat d'exécution d'une étape lancée depuis l'IHM."""

    step_key: str
    command: list[str]
    command_display: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    executed_at: str
    account_id: str | None = None

    def to_state(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PipelineLiveSnapshot:
    """État live d'un sous-processus exécuté depuis l'IHM."""

    step_key: str
    command_display: str
    status: PipelineExecutionStatus
    stdout: str
    stderr: str
    duration_seconds: float
    executed_at: str
    account_id: str | None = None
    returncode: int | None = None
    stdout_lines: int = 0
    stderr_lines: int = 0


PIPELINE_STEPS: tuple[PipelineStepDefinition, ...] = (
    PipelineStepDefinition(
        key="import_alpaca_bar",
        num="1",
        name="Import Alpaca Bar",
        desc="Ingestion des barres OHLCV journalières depuis Alpaca Market Data.",
        tables="stock_bars",
        deps="—",
    ),
    PipelineStepDefinition(
        key="data_sanitizer_daily",
        num="2",
        name="Data Sanitizer Daily",
        desc="Nettoyage, alignement calendrier, détection d'anomalies sur les barres brutes.",
        tables="stock_bars_daily, cleaning_audit_log",
        deps="import_alpaca_bar",
    ),
    PipelineStepDefinition(
        key="stock_screener",
        num="3",
        name="Stock Screener",
        desc="Scores de base : liquidité 30j, force relative 6m vs SPY, range 10 ans.",
        tables="stock_scores",
        deps="data_sanitizer_daily",
    ),
    PipelineStepDefinition(
        key="alpha_scanner",
        num="4",
        name="Alpha Scanner",
        desc="Scoring avancé Minervini/VCP + neutralisation sectorielle + sélection Top N.",
        tables="stock_scores (update)",
        deps="stock_screener",
    ),
    PipelineStepDefinition(
        key="sentiment_pipeline",
        num="5",
        name="Sentiment Pipeline",
        desc="Ingestion news → scoring FinBERT → features ticker/secteur journalières.",
        tables="ticker_daily_sentiment_features, sector_daily_sentiment_features",
        deps="alpha_scanner",
    ),
    PipelineStepDefinition(
        key="signal_aggregator",
        num="6",
        name="Signal Aggregator",
        desc="Fusion quant (75%) + sentiment ticker (15%) + macro sectoriel (10%) → final_score_sentiment.",
        tables="stock_scores (update final_score_sentiment)",
        deps="sentiment_pipeline",
    ),
    PipelineStepDefinition(
        key="ml_train",
        num="7",
        name="ML Train (LSTM)",
        desc="Entraînement des modèles LSTM+Attention par symbole candidat. Périodique (hebdomadaire recommandé).",
        tables="model_registry, model_training_run, model_metrics",
        deps="signal_aggregator (is_candidate=1)",
    ),
    PipelineStepDefinition(
        key="ml_predict",
        num="8",
        name="ML Predict",
        desc="Inférence LSTM → predicted_proba par symbole candidat. Quotidien, alimente le score de conviction du risk.",
        tables="model_predictions",
        deps="ml_train (modèle entraîné requis)",
    ),
    PipelineStepDefinition(
        key="risk_management",
        num="9",
        name="Risk Management",
        desc="Sizing ATR/Kelly, contraintes portefeuille, circuit breaker → portefeuille cible. Utilise les prédictions ML pour le score de conviction.",
        tables="risk_decisions, portfolio_targets",
        deps="ml_predict, signal_aggregator",
        account_usage="alpaca",
    ),
    PipelineStepDefinition(
        key="execution",
        num="10",
        name="Execution",
        desc="Soumission ordres Alpaca (market/limit), bracket synthétique TP+TS, réconciliation, TCA. Photographie les positions broker après exécution.",
        tables="execution_runs, execution_orders, execution_fills, execution_events, broker_positions_snapshots",
        deps="run_risk",
        account_usage="alpaca",
    ),
    PipelineStepDefinition(
        key="corporate_actions_sync",
        num="11",
        name="Corporate Actions Sync",
        desc="Récupère les dividendes/splits depuis Alpaca uniquement pour les symboles détenus en portefeuille (après exécution du jour).",
        tables="corporate_actions_events",
        deps="execution (broker_positions_snapshots requis)",
        account_usage="alpaca",
    ),
    PipelineStepDefinition(
        key="corporate_actions_apply",
        num="12",
        name="Corporate Actions Apply",
        desc="Application des dividendes/splits sur les positions existantes. Se fait APRÈS la sync et l'exécution.",
        tables="corporate_actions_applications, portfolio_cash_ledger",
        deps="corporate_actions_sync",
        account_usage="alpaca",
    ),
)


def get_pipeline_steps() -> tuple[PipelineStepDefinition, ...]:
    return PIPELINE_STEPS


def _normalize_trade_date(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _normalize_run_id(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def build_pipeline_command(step_key: str, options: PipelineLaunchOptions) -> list[str]:
    """Construit la commande subprocess correspondant à une étape."""
    trade_date = _normalize_trade_date(options.trade_date)
    run_id = _normalize_run_id(options.execution_run_id)
    account_id = (options.account_id or "").strip() or None

    if step_key == "import_alpaca_bar":
        return [sys.executable, "-m", "dataIntegrityEngine.import_alpaca_bar"]

    if step_key == "corporate_actions_sync":
        # --portfolio-only : sync uniquement les symboles détenus en portefeuille
        # pas de --skip-existing : on re-interroge Alpaca à chaque fois pour ne rater aucun nouvel événement
        command = [sys.executable, "-m", "corporate_actions", "sync", "--portfolio-only"]
        if account_id:
            command.extend(["--account", account_id])
        return command

    if step_key == "data_sanitizer_daily":
        return [sys.executable, "-m", "dataIntegrityEngine.data_sanitizer_daily"]

    if step_key == "stock_screener":
        return [sys.executable, "-m", "screener.stock_screener"]

    if step_key == "alpha_scanner":
        return [sys.executable, "-m", "selector.alpha_scanner"]

    if step_key == "sentiment_pipeline":
        return [sys.executable, "-m", "event_sentiment"]

    if step_key == "signal_aggregator":
        command = [sys.executable, "-m", "event_sentiment.signal_aggregator"]
        if trade_date:
            command.extend(["--trade-date", trade_date])
        return command

    if step_key == "ml_train":
        return [sys.executable, "-m", "modelFactory", "--mode", "train", "--include-sentiment"]

    if step_key == "ml_predict":
        return [sys.executable, "-m", "modelFactory", "--mode", "predict"]

    if step_key == "risk_management":
        command = [
            sys.executable,
            "-m",
            "risk_management",
            "--account-equity",
            str(options.risk_account_equity),
        ]
        if trade_date:
            command.extend(["--trade-date", trade_date])
        if account_id:
            command.extend(["--account", account_id])
        return command

    if step_key == "execution":
        command = [sys.executable, str(PROJECT_ROOT / "run_execution.py"), options.execution_mode]
        if trade_date:
            command.extend(["--date", trade_date])
        if run_id:
            command.extend(["--run-id", run_id])
        if options.allow_outside_rth:
            command.append("--allow-outside-rth")
        if options.auto_rebalance:
            command.append("--auto-rebalance")
        if account_id:
            command.extend(["--account", account_id])
        return command

    if step_key == "corporate_actions_apply":
        command = [sys.executable, "-m", "corporate_actions", "apply"]
        if trade_date:
            command.extend(["--as-of", trade_date])
        if account_id:
            command.extend(["--account", account_id])
        return command

    raise KeyError(f"Étape de pipeline inconnue : {step_key}")


def format_command_for_display(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def build_subprocess_env(
    db_config: dict[str, str | None] | None = None,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Construit l'environnement d'un sous-processus déclenché depuis l'IHM."""
    env = dict(base_env or os.environ)

    pythonpath_entries = [str(PROJECT_ROOT)]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)

    if db_config:
        host = db_config.get("host")
        name = db_config.get("name")
        user = db_config.get("user")
        password = db_config.get("password")
        if host:
            env["DB_HOST"] = str(host)
        if name:
            env["DB_NAME"] = str(name)
        if user:
            env["LOGIN_DB"] = str(user)
        if password:
            env["PASSWORD_DB"] = str(password)

    return env


def _build_live_snapshot(
    *,
    step_key: str,
    command_display: str,
    status: PipelineExecutionStatus,
    stdout_lines: list[str],
    stderr_lines: list[str],
    started_at: datetime,
    started_perf: float,
    account_id: str | None,
    returncode: int | None = None,
) -> PipelineLiveSnapshot:
    return PipelineLiveSnapshot(
        step_key=step_key,
        command_display=command_display,
        status=status,
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
        duration_seconds=round(time.perf_counter() - started_perf, 2),
        executed_at=started_at.isoformat(timespec="seconds"),
        account_id=account_id,
        returncode=returncode,
        stdout_lines=len(stdout_lines),
        stderr_lines=len(stderr_lines),
    )


def _stream_subprocess(
    command: list[str],
    *,
    step_key: str,
    account_id: str | None,
    env: dict[str, str],
    cwd: Path,
    timeout_seconds: int | None = None,
    on_update: Callable[[PipelineLiveSnapshot], None] | None = None,
) -> PipelineRunResult:
    command_display = format_command_for_display(command)
    started_at = datetime.now()
    started_perf = time.perf_counter()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    events: queue.Queue[tuple[str, str]] = queue.Queue()

    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def _reader(stream: subprocess.PIPE | None, stream_name: str) -> None:  # type: ignore[type-arg]
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                events.put((stream_name, line))
        finally:
            stream.close()

    stdout_thread = threading.Thread(target=_reader, args=(process.stdout, "stdout"), daemon=True)
    stderr_thread = threading.Thread(target=_reader, args=(process.stderr, "stderr"), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    if on_update is not None:
        on_update(
            _build_live_snapshot(
                step_key=step_key,
                command_display=command_display,
                status="starting",
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
                started_at=started_at,
                started_perf=started_perf,
                account_id=account_id,
            )
        )

    timed_out = False
    last_push = 0.0

    while True:
        drained = False
        while True:
            try:
                stream_name, line = events.get_nowait()
            except queue.Empty:
                break
            drained = True
            if stream_name == "stdout":
                stdout_lines.append(line)
            else:
                stderr_lines.append(line)

        elapsed = time.perf_counter() - started_perf
        current_returncode = process.poll()

        if timeout_seconds is not None and elapsed > timeout_seconds and current_returncode is None:
            process.kill()
            timed_out = True
            stderr_lines.append("\nTimeout d'exécution dépassé.\n")
            current_returncode = -2

        if on_update is not None and (drained or (time.perf_counter() - last_push) >= 0.5):
            live_status: PipelineExecutionStatus = "timeout" if timed_out else "running"
            if current_returncode is not None and not timed_out:
                live_status = "completed" if current_returncode == 0 else "failed"
            on_update(
                _build_live_snapshot(
                    step_key=step_key,
                    command_display=command_display,
                    status=live_status,
                    stdout_lines=stdout_lines,
                    stderr_lines=stderr_lines,
                    started_at=started_at,
                    started_perf=started_perf,
                    account_id=account_id,
                    returncode=current_returncode,
                )
            )
            last_push = time.perf_counter()

        if current_returncode is not None and events.empty() and not stdout_thread.is_alive() and not stderr_thread.is_alive():
            break

        time.sleep(0.1)

    process.wait()
    final_returncode = -2 if timed_out else process.returncode

    return PipelineRunResult(
        step_key=step_key,
        command=command,
        command_display=command_display,
        returncode=final_returncode,
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
        duration_seconds=round(time.perf_counter() - started_perf, 2),
        executed_at=started_at.isoformat(timespec="seconds"),
        account_id=account_id,
    )


def run_pipeline_step(
    step_key: str,
    options: PipelineLaunchOptions,
    *,
    db_config: dict[str, str | None] | None = None,
    timeout_seconds: int | None = None,
    on_update: Callable[[PipelineLiveSnapshot], None] | None = None,
) -> PipelineRunResult:
    """Exécute une étape de pipeline et capture stdout/stderr."""
    command = build_pipeline_command(step_key, options)
    env = build_subprocess_env(db_config=db_config)
    try:
        return _stream_subprocess(
            command,
            step_key=step_key,
            account_id=options.account_id,
            env=env,
            cwd=PROJECT_ROOT,
            timeout_seconds=timeout_seconds,
            on_update=on_update,
        )
    except Exception as exc:
        return PipelineRunResult(
            step_key=step_key,
            command=command,
            command_display=format_command_for_display(command),
            returncode=-1,
            stdout="",
            stderr=str(exc),
            duration_seconds=0.0,
            executed_at=datetime.now().isoformat(timespec="seconds"),
            account_id=options.account_id,
        )

