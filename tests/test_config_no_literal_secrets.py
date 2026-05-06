"""Sprint S5 (A-013) — tests pour le scanner de secrets en clair."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.secrets import (
    LITERAL_SECRET_PATTERNS,
    SecretConfigurationError,
    assert_no_plaintext_secrets,
    scan_repo_yaml_for_literal_secrets,
    scan_text_for_literal_secrets,
    scan_yaml_for_literal_secrets,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_YAML = ROOT / "config.yaml"


# ---------------------------------------------------------------------------
# Repo guards
# ---------------------------------------------------------------------------

def test_repo_config_yaml_has_no_literal_secrets():
    findings = scan_yaml_for_literal_secrets(CONFIG_YAML)
    assert findings == [], (
        f"config.yaml contient {len(findings)} secret(s) littéraux : "
        + "; ".join(f"L{f.lineno} {f.pattern_name}={f.masked_value}" for f in findings)
    )


def test_repo_yaml_tree_has_no_literal_secrets():
    findings = scan_repo_yaml_for_literal_secrets(ROOT)
    if findings:
        msg = "\n".join(
            f"  - {f.path}:{f.lineno} {f.pattern_name} {f.masked_value}"
            for f in findings
        )
        pytest.fail("Secrets littéraux détectés :\n" + msg)


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

def test_scanner_detects_alpaca_paper_key():
    yaml = 'alpaca:\n  api_key: "PKABCDEFGHIJKLMNOPQR"\n'
    f = scan_text_for_literal_secrets(yaml)
    assert any(x.pattern_name == "alpaca_paper_key" for x in f)


def test_scanner_detects_alpaca_live_key():
    yaml = 'alpaca:\n  api_key: "AKABCDEFGHIJKLMNOPQR"\n'
    f = scan_text_for_literal_secrets(yaml)
    assert any(x.pattern_name == "alpaca_live_key" for x in f)


def test_scanner_detects_alpaca_secret_b64():
    secret = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij1234567890"
    yaml = f'alpaca:\n  secret_key: "{secret}"\n'
    f = scan_text_for_literal_secrets(yaml)
    assert any(x.pattern_name == "alpaca_secret_b64" for x in f)


def test_scanner_detects_openai_key():
    yaml = 'openai:\n  api_key: "sk-abcdefghijklmnopqrstuvwx"\n'
    f = scan_text_for_literal_secrets(yaml)
    assert any(x.pattern_name == "openai_key" for x in f)


def test_scanner_ignores_env_placeholder():
    yaml = 'alpaca:\n  api_key: "${ALPACA_API_KEY}"\n  secret_key: "${ALPACA_SECRET_KEY}"\n'
    f = scan_text_for_literal_secrets(yaml)
    assert f == []


def test_scanner_whitelist_cache_dir():
    # cache_dir contient parfois des chaînes longues — ne doit PAS matcher
    yaml = 'eodhd:\n  cache_dir: artifacts/eodhd_cache_with_a_long_string_xyz1234567890\n'
    f = scan_text_for_literal_secrets(yaml)
    assert f == []


def test_scanner_noqa_marker_disables_scan():
    yaml = '  api_key: "PKABCDEFGHIJKLMNOPQR"  # noqa: secret-scan\n'
    f = scan_text_for_literal_secrets(yaml)
    assert f == []


def test_scanner_finding_masks_value():
    yaml = '  api_key: "PKABCDEFGHIJKLMNOPQR"\n'
    f = scan_text_for_literal_secrets(yaml)
    assert f, "expected at least one finding"
    assert "…" in f[0].masked_value
    assert "PKABCDEFGHIJKLMNOPQR" not in f[0].masked_value
    assert "PKAB" in f[0].masked_value


# ---------------------------------------------------------------------------
# assert_no_plaintext_secrets — heuristique étendue Sprint S5
# ---------------------------------------------------------------------------

def test_assert_no_plaintext_rejects_literal_alpaca_key():
    cfg = {"alpaca": {"api_key": "PKABCDEFGHIJKLMNOPQR", "secret_key": "${X}"}}
    with pytest.raises(SecretConfigurationError):
        assert_no_plaintext_secrets(cfg)


def test_assert_no_plaintext_accepts_placeholders():
    cfg = {
        "alpaca": {"api_key": "${ALPACA_API_KEY}", "secret_key": "${ALPACA_SECRET_KEY}"},
        "database": {"user": "${LOGIN_DB}", "password": "${PASSWORD_DB}"},
    }
    # Doit retourner sans erreur
    assert_no_plaintext_secrets(cfg)


def test_literal_secret_patterns_compiled():
    for name, pattern in LITERAL_SECRET_PATTERNS.items():
        assert isinstance(pattern, re.Pattern), name

