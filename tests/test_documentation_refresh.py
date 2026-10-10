"""Static documentation maintenance must not import business runners."""
import json
import re
from pathlib import Path
import sys

import pytest
import yaml

from scripts import refresh_documentation as refresh
from scripts import generate_doc_index as index


def test_monitoring_assets_parse_and_reference_current_exporter():
    root = Path(__file__).resolve().parents[1]
    assets = root / 'doc/operations/monitoring'
    rules = yaml.safe_load((assets / 'prometheus_alert_rules.yml').read_text('utf-8'))
    dashboard = json.loads((assets / 'grafana_dashboard_alpha_trade.json').read_text('utf-8'))
    expressions = [rule['expr'] for group in rules['groups'] for rule in group['rules']]
    expressions += [target['expr'] for panel in dashboard['panels'] for target in panel['targets']]
    exporter = (root / 'service/prometheus_metrics.py').read_text('utf-8')
    assert len(rules['groups'][0]['rules']) == 7
    for expression in expressions:
        metrics = re.findall(r'alpha_trade_[a-z_]+', expression)
        assert metrics and all(metric in exporter for metric in metrics)
    # Static names/schema only: no runtime PromQL evaluation or exporter start.


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh, "ROOT", tmp_path)
    monkeypatch.setattr(refresh, "DOC", tmp_path / "doc")
    monkeypatch.setattr(index, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(index, "DOC_DIR", tmp_path / "doc")
    monkeypatch.setattr(index, "INDEX_PATH", tmp_path / "doc/INDEX.md")
    (tmp_path / "doc").mkdir()
    return tmp_path


@pytest.mark.parametrize("name,expected", [
    ("README.md", "current"), ("api/service.md", "generated"),
    ("api/README.md", "current"), ("reference/batchs_generes.md", "generated"),
    ("sources_historiques/old.md", "archive"), ("experiences/old.md", "archive"),
    ("ml/experiences_done.md", "research"), ("ml/oracle/README.md", "current"),
    ("fr/TODO_reprise.md", "planning"), ("cn/doc_fonctionnel.md", "current"),
    ("fr/result.csv", "asset"),
])
def test_classification(workspace, name, expected):
    assert refresh.classification(workspace / "doc" / name) == expected


def test_ast_extracts_methods_and_conditional_definitions_without_execution(workspace):
    path = workspace / "module.py"
    path.write_text('''raise RuntimeError("DO NOT IMPORT")
class Sample(Base):
    def method(self, value: int = 2) -> str:
        def nested(): pass
        return str(value)
try:
    def normal(): pass
except ImportError:
    def fallback(): pass
finally:
    def finalizer(): pass
if True:
    async def conditional(*, flag=True): pass
''', encoding="utf-8")
    _, _, rows = refresh.signatures(path)
    names = [row[1] for row in rows]
    assert names == ["Sample", "Sample.method", "normal", "fallback", "finalizer", "conditional"]
    assert "value: int=2" in rows[1][2].replace(" = ", "=")


def test_local_links_decode_spaces_and_ignore_fenced_examples(workspace):
    doc = workspace / "doc/README.md"
    target = workspace / "doc/Étude locale.md"
    target.write_text("# Étude\n", encoding="utf-8")
    doc.write_text('[ok](%C3%89tude%20locale.md#section)\n[web](https://example.test)\n'
                   '```\n[example](absent.md)\n```\n', encoding="utf-8")
    assert refresh.audit_links() == {"checked": 1, "broken": []}


def test_absent_evidence_is_preserved_not_invented(workspace):
    path = workspace / "doc/README.md"
    path.write_text("# Report\n[Proof](../artifacts/missing/report.json)\nAUC=0.51\n", encoding="utf-8")
    refresh.repair_old_links([])
    body = path.read_text("utf-8")
    assert "AUC=0.51" in body and "../artifacts/missing/report.json" in body
    assert "référence historique absente localement" in body
    assert not refresh.audit_links()["broken"]


def test_generated_configuration_omits_secret_values(workspace):
    for name in ("config.yaml", "config_cn.yaml", "config_fr.yaml", "batch.yaml", "batch_cn.yaml", "batch_fr.yaml", "config/databases.yaml"):
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("secret_key: PRIVATE-SENTINEL\n", encoding="utf-8")
    output = refresh.config_inventory("2026-10-10")
    assert "secret_key" in output
    assert "PRIVATE-SENTINEL" not in output


def test_write_is_confined_to_documentation(workspace):
    with pytest.raises(ValueError, match="outside doc"):
        refresh.write(workspace / "config.yaml", "changed", [])


def test_notice_can_be_replaced_without_changing_historical_results(workspace):
    path = workspace / "doc/experiences/old.md"
    body = "# Result\n\n" + refresh.notice(path, "archive", "2026-10-10") + "Return=22%\n"
    assert refresh.clean_notice(body) == "# Result\n\nReturn=22%\n"


def test_batch_reference_does_not_call_providers_and_respects_defaults(workspace):
    for name in ("batch.yaml", "batch_cn.yaml", "batch_fr.yaml"):
        (workspace / name).write_text('defaults:\n  timezone: Europe/Paris\n  enabled: false\n'
            'demo:\n  run_hours: "20"\n  recovery_run_hours: "1"\n  api_key: PRIVATE-SENTINEL\n', encoding="utf-8")
    output = refresh.batch_inventory("2026-10-10")
    assert "Europe/Paris" in output and "conditionnel" in output and "False" in output
    assert "PRIVATE-SENTINEL" not in output


def test_index_ignores_status_notice_and_encodes_paths(workspace):
    path = workspace / "doc/Étude locale.md"
    path.write_text("# Étude\n\n" + refresh.notice(path, "current", "2026-10-10") + "Description originale.\n", encoding="utf-8")
    assert index._read_meta(path) == ("Étude", "Description originale.")
    output = index.generate()
    assert "%C3%89tude%20locale.md" in output
    assert "Statut documentaire" not in output


def test_full_refresh_is_idempotent(workspace, monkeypatch, capsys):
    for name in ("config.yaml", "config_cn.yaml", "config_fr.yaml", "batch.yaml", "batch_cn.yaml", "batch_fr.yaml", "config/databases.yaml"):
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    navigation = workspace / "ihm/services/navigation.py"
    navigation.parent.mkdir(parents=True)
    navigation.write_text("# no business imports\n", encoding="utf-8")
    for name in ("ETAT_ACTUEL_IMPLEMENTATION.md", "AUDIT_COMPLET_DOCUMENTATION_20261010.md", "INDEX.md", "README.md"):
        (workspace / "doc" / name).write_text("# Title\n\nOriginal content\n", encoding="utf-8")
    for name in ("18_reference_configuration.md", "guide_utilisateur/README.md", "database/migrations_et_transactions.md", "operations/catalogue_batchs_actuel.md"):
        path = workspace / "doc" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Target\n\nExisting guide\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["refresh", "--apply"])
    for _ in range(3):
        assert refresh.main() == 0
        result = json.loads(capsys.readouterr().out)
    assert result["changed"] == 0
    registry = (workspace / "doc/audit/registre_documentaire.md").read_text("utf-8")
    assert "audit/registre_documentaire.md" in registry
    assert "api/alembic_cn.md" in registry


def test_index_does_not_rebase_or_truncate_description_links(workspace):
    path = workspace / "doc/fr/report.md"
    path.parent.mkdir()
    path.write_text("# Report\n\nSee [other report](other.md)\n", encoding="utf-8")
    output = index.generate()
    assert "See other report" in output
    assert "](other.md)" not in output
