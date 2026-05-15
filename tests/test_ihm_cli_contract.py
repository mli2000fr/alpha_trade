"""Phase 6.2 — test contractuel IHM ↔ CLI.

Pour chaque ``PipelineStepDefinition``, on construit la commande exécutée par
l'IHM (``build_pipeline_command``) puis on vérifie que **tous les flags
``--xxx`` qu'elle fournit sont reconnus** par l'``argparse`` du CLI cible
correspondant.

Ainsi, si quelqu'un :
- supprime un flag CLI sans mettre à jour `pipeline_runner.py`, ou
- ajoute un flag dans le runner sans l'implémenter dans le CLI,
le test échoue immédiatement.

On exclut volontairement les sous-commandes qui font de l'I/O à l'import
(modelFactory, risk, execution, corporate_actions ``apply``…) pour rester
hermétique. La couverture des modules data/screener/selector/sentiment est
déjà très représentative.
"""
from __future__ import annotations

import argparse
import importlib
from typing import Iterable, Optional

import pytest

from ihm.services.pipeline_runner import (
    PIPELINE_AUXILIARY_STEPS,
    PIPELINE_STEPS,
    PipelineLaunchOptions,
    build_pipeline_command,
)


# Mapping step_key → (module python, fonction qui retourne argparse.ArgumentParser)
# Si la fonction n'est pas exposée, on tente plusieurs noms standards.
_PARSER_RESOLVERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "import_alpaca_assets": (
        "dataIntegrityEngine.import_alpaca_assets",
        ("_build_arg_parser", "build_arg_parser", "_build_parser", "build_parser"),
    ),
    "import_alpaca_bar": (
        "dataIntegrityEngine.import_alpaca_bar",
        ("_build_arg_parser", "build_arg_parser", "_build_parser", "build_parser"),
    ),
    "data_sanitizer_daily": (
        "dataIntegrityEngine.data_sanitizer_daily",
        ("_build_arg_parser", "build_arg_parser", "_build_parser", "build_parser"),
    ),
    "update_sector": (
        "dataIntegrityEngine.update_sector",
        ("_build_arg_parser", "build_arg_parser", "_build_parser", "build_parser"),
    ),
    "sync_latest_quotes": (
        "dataIntegrityEngine.sync_latest_quotes",
        ("_build_arg_parser", "build_arg_parser", "_build_parser", "build_parser"),
    ),
    "sync_earnings_calendar": (
        "dataIntegrityEngine.sync_earnings_calendar",
        ("_build_arg_parser", "build_arg_parser", "_build_parser", "build_parser"),
    ),
    "stock_screener": (
        "screener.stock_screener",
        ("_build_arg_parser", "build_arg_parser", "_build_parser", "build_parser"),
    ),
    "alpha_scanner": (
        "selector.alpha_scanner",
        ("_build_arg_parser", "build_arg_parser", "_build_parser", "build_parser"),
    ),
    "import_news": (
        "event_sentiment.importe_news",
        ("_build_arg_parser", "build_arg_parser", "_build_parser", "build_parser"),
    ),
}


def _resolve_step_parser_target(step_key: str, command: list[str]) -> tuple[str, tuple[str, ...]]:
    if step_key == "import_alpaca_bar" and len(command) >= 4 and command[2] == "-m":
        module_name = command[3]
        if module_name == "dataIntegrityEngine.import_eodhd_bar":
            return (
                "dataIntegrityEngine.import_eodhd_bar",
                ("_build_arg_parser", "build_arg_parser", "_build_parser", "build_parser"),
            )
    return _PARSER_RESOLVERS[step_key]


def _resolve_parser(module_name: str, candidates: Iterable[str]) -> Optional[argparse.ArgumentParser]:
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return None
    for name in candidates:
        fn = getattr(module, name, None)
        if callable(fn):
            try:
                parser = fn()
            except Exception:
                continue
            if isinstance(parser, argparse.ArgumentParser):
                return parser
    return None


def _extract_long_flags(command: list[str]) -> set[str]:
    """Récupère tous les ``--xxx`` (sans valeurs) d'une commande."""
    return {token for token in command if token.startswith("--")}


def _parser_known_flags(parser: argparse.ArgumentParser) -> set[str]:
    flags: set[str] = set()
    for action in parser._actions:
        for option in action.option_strings:
            if option.startswith("--"):
                flags.add(option)
    return flags


@pytest.mark.parametrize("step", [s for s in (*PIPELINE_STEPS, *PIPELINE_AUXILIARY_STEPS) if s.key in _PARSER_RESOLVERS])
def test_ihm_cli_contract_flags_are_known_by_target_argparse(step) -> None:
    options = PipelineLaunchOptions()
    command = build_pipeline_command(step.key, options)
    assert command[1] == "-u", (
        f"build_pipeline_command({step.key}) doit invoquer `python -u ...`; got {command[:4]}"
    )

    module_name, candidates = _resolve_step_parser_target(step.key, command)
    parser = _resolve_parser(module_name, candidates)
    if parser is None:
        pytest.skip(f"{module_name} : aucun build_parser exposé (parser introspection indisponible)")

    used_flags = _extract_long_flags(command)
    known_flags = _parser_known_flags(parser)
    unknown = used_flags - known_flags
    assert not unknown, (
        f"Step {step.key} (module {module_name}) : flags utilisés par l'IHM mais inconnus du CLI: {sorted(unknown)}.\n"
        f"  Flags CLI disponibles : {sorted(known_flags)}"
    )


def test_ihm_cli_contract_pipeline_steps_emit_python_module_invocations() -> None:
    """Garde-fou : tous les steps construisent une commande Python valide.

    Forme acceptée : ``python -u -m <module>`` ou ``python -u <script.py>``.
    """
    options = PipelineLaunchOptions()
    for step in (*PIPELINE_STEPS, *PIPELINE_AUXILIARY_STEPS):
        command = build_pipeline_command(step.key, options)
        assert command, f"Step {step.key} : commande vide"
        assert command[1] == "-u", f"Step {step.key} : second token doit être `-u`, got {command[1]}"
        # Soit `-m <module>`, soit un chemin vers un script.
        third = command[2]
        assert third == "-m" or third.endswith(".py"), (
            f"Step {step.key} : forme attendue `-m <module>` ou `<script.py>`, got {third!r}"
        )


# ---------------------------------------------------------------------------
# Sprint S26 — couverture des commandes ops (`ihm.services.ops_runner`).
# ---------------------------------------------------------------------------

from ihm.services.ops_runner import OPS_COMMAND_CATALOG, build_ops_command

# kwargs minimaux pour les commandes qui exigent des paramètres obligatoires.
_OPS_DEFAULT_KWARGS: dict[str, dict[str, object]] = {
    "execution_kill_switch": {"account": "paper-test"},
    "pre_live_checklist": {"account": "paper-test"},
    "daily_parity": {"account": "paper-test"},
    "restore_from_backup": {"backup_path": "dummy.sql"},
}


@pytest.mark.parametrize("ops_key", sorted(OPS_COMMAND_CATALOG.keys()))
def test_ihm_cli_contract_ops_commands_emit_python_invocations(ops_key: str) -> None:
    """Chaque commande ops doit produire une commande `python -u …` exploitable."""
    kwargs = _OPS_DEFAULT_KWARGS.get(ops_key, {})
    command = build_ops_command(ops_key, **kwargs)  # type: ignore[arg-type]
    assert command, f"Ops `{ops_key}` : commande vide"
    assert command[1] == "-u", (
        f"Ops `{ops_key}` : second token doit être `-u`, got {command[1]!r}"
    )
    third = command[2]
    assert third == "-m" or third.endswith(".py"), (
        f"Ops `{ops_key}` : forme attendue `-m <module>` ou `<script.py>`, got {third!r}"
    )


def test_ihm_cli_contract_ops_kill_switch_flags_known_by_execution_engine() -> None:
    """Garde-fou IHM↔CLI sur la sous-commande `execution_engine cancel-all`."""
    command = build_ops_command(
        "execution_kill_switch",
        account="paper-test",
        broker_mode="paper",
        confirm_account="paper-test",
        reason="test",
        dry_run=True,
    )
    parser = _resolve_parser(
        "execution_engine.cli",
        ("_build_arg_parser", "build_arg_parser", "_build_parser", "build_parser"),
    )
    if parser is None:
        pytest.skip("execution_engine.cli : aucun build_parser exposé.")
    # On retire le flag de la sous-commande (`cancel-all`) qui n'est pas un long flag.
    used = _extract_long_flags(command)
    # Récupère les flags de tous les sous-parsers.
    known: set[str] = set(_parser_known_flags(parser))
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):  # type: ignore[attr-defined]
            for sub in action.choices.values():
                known.update(_parser_known_flags(sub))
    unknown = used - known
    assert not unknown, (
        f"Ops kill switch : flags inconnus de `execution_engine` : {sorted(unknown)}.\n"
        f"  Flags connus : {sorted(known)}"
    )



