from __future__ import annotations

from backtesting.cli._impl import _build_parser


def test_backtesting_run_parser_accepts_allow_fractional_shares_flag() -> None:
    parser = _build_parser()

    args = parser.parse_args([
        "run",
        "--start",
        "2025-01-01",
        "--allow-fractional-shares",
    ])

    assert args.command == "run"
    assert args.allow_fractional_shares is True


def test_backtesting_run_parser_defaults_allow_fractional_shares_to_false() -> None:
    parser = _build_parser()

    args = parser.parse_args([
        "run",
        "--start",
        "2025-01-01",
    ])

    assert args.command == "run"
    assert args.allow_fractional_shares is False

