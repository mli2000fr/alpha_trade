"""Read-only source inventory and reproducible documentation maintenance.

Never import business runners or connect to a provider/database. --apply only
writes generated documentation and mechanical status notices under doc/.
Historical bodies/metrics are preserved. A notice is not semantic certification.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, quote

import yaml
if __package__:
    from scripts import generate_doc_index as doc_index
else:
    import generate_doc_index as doc_index

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "doc"
PACKAGES = tuple("core common database dataIntegrityEngine screener selector event_sentiment analyst_research modelFactory risk_management execution_engine backtesting corporate_actions service ihm flows lineage reporting formal tax scripts alembic alembic_cn alembic_fr entrypoints".split())
NOTICE_START = "<!-- doc-status:start -->"
NOTICE_END = "<!-- doc-status:end -->"
GENERATED = {"INDEX.md", "audit/registre_documentaire.md", "audit/inventaire_sources.json", "audit/controle_liens.json", "reference/configuration_generee.md", "reference/navigation_generee.md", "reference/schema_et_migrations_generes.md", "reference/modules_generes.md", "reference/batchs_generes.md"}
ML_CURRENT = set("README features_et_labels features_et_dataset orchestration_train_predict ordre_execution_et_dependances entrainement_serving_et_gouvernance validation_et_gouvernance qualite_couverture_et_fallbacks cascade_et_fallbacks recalibration_et_promotion global_ranking_reference oracle_extreme_reference modeles_per_symbol_et_per_sector oracle_llm_directional_filter correctif_pipeline_historique_filtre_gpt oracle_atr_amplitude_gate oracle_atr_market_regime_daily new_entry_data_guard market_cap_sec_edgar oracle_tradable_top20_backtest_live oracle_universe_selection_playbook oracle_numeric_feature_corrections".split())
MARKET_CURRENT = {
    "cn": set("README doc_fonctionnel architecture_bases_batchs_configuration_cn contrat_univers_tradable_pit sprint_planning_integration_marche_chinois roadmap_integration_marche_chinois_audit_code".split()),
    "fr": set("README runbook_exploitation_fr sprint_planning_integration_marche_francais publication_quotidienne_staging_sql options_mifir_collecte_quotidienne inpi_univers_collecte_securisee consensus_collecte_quotidienne catalogue_sources_gratuites_validation_historique".split()),
}


def rel(path):
    return path.relative_to(ROOT).as_posix()


def digest(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def clean_notice(body):
    return re.sub(re.escape(NOTICE_START) + r".*?" + re.escape(NOTICE_END) + r"\s*", "", body, flags=re.S)


def classification(path):
    parts = path.relative_to(DOC).parts
    if path.suffix != ".md":
        return "asset"
    if parts[0] in ("sources_historiques", "experiences"):
        return "archive"
    if parts[0] == "api" and path.stem not in ("README", "stabilite_v1_et_deprecation"):
        return "generated"
    if path.relative_to(DOC).as_posix() in GENERATED or parts[0] == "reference":
        return "generated"
    if parts[0] in ("fr", "cn"):
        if path.stem.startswith(("TODO", "todo_", "sprint_planning", "roadmap_")):
            return "planning"
        return "current" if path.stem in MARKET_CURRENT[parts[0]] else "research"
    if parts[0] == "ml":
        return "current" if len(parts) > 2 or path.stem in ML_CURRENT else "research"
    if parts[0] in ("research",):
        return "research"
    if path.stem.startswith(("AUDIT_", "MIGRATION_", "COUVERTURE_DOCUMENTS")):
        return "archive"
    return "current"


def signatures(path):
    text = path.read_text("utf-8-sig")
    tree = ast.parse(text, filename=rel(path))
    rows = []
    def visit(body, prefix=""):
        for node in body:
            if isinstance(node, ast.ClassDef):
                bases = ", ".join(ast.unparse(b) for b in node.bases)
                rows.append((node.lineno, prefix + node.name, f"class {node.name}" + (f"({bases})" if bases else "")))
                visit(node.body, prefix + node.name + ".")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                signature = ("async " if isinstance(node, ast.AsyncFunctionDef) else "") + f"def {node.name}({ast.unparse(node.args)})"
                if node.returns:
                    signature += " -> " + ast.unparse(node.returns)
                rows.append((node.lineno, prefix + node.name, signature))
            elif isinstance(node, (ast.If, ast.Try)):
                visit(node.body, prefix)
                visit(node.orelse, prefix)
                if isinstance(node, ast.Try):
                    for handler in node.handlers:
                        visit(handler.body, prefix)
                    visit(node.finalbody, prefix)
    visit(tree.body)
    return text, tree, rows


def source_inventory():
    items, errors = [], []
    for package in PACKAGES:
        paths = ROOT.glob("*.py") if package == "entrypoints" else (ROOT / package).rglob("*.py")
        for path in sorted(paths):
            if "__pycache__" in path.parts:
                continue
            try:
                text, tree, rows = signatures(path)
                items.append({"path": rel(path), "package": package, "sha256": digest(text), "symbols": [{"line": line, "name": name, "signature": sig} for line, name, sig in rows]})
            except (SyntaxError, UnicodeError) as exc:
                errors.append({"path": rel(path), "error": str(exc)})
    return items, errors


def links(body):
    # Ignore fenced examples: their pseudo-paths are not navigation hyperlinks.
    body = re.sub(r"```.*?```|~~~.*?~~~", "", body, flags=re.S)
    pattern = re.compile(r"\[[^\]\n]*\]\((<[^>\n]+>|[^\s()]+(?:\([^()]*\)[^\s()]*)*)(?:\s+\"[^\"]*\")?\)")
    yield from (m.group(1).strip("<>") for m in pattern.finditer(body))


def resolve_link(path, target):
    decoded = unquote(target.split("#", 1)[0])
    if not decoded:
        return path
    if re.match(r"^[A-Za-z]:[/\\]", decoded):
        return Path(decoded)
    if decoded.startswith("/"):
        return ROOT / decoded.lstrip("/")
    return (path.parent / decoded).resolve()


def audit_links():
    failures, total = [], 0
    for path in sorted(DOC.rglob("*.md")):
        for target in links(path.read_text("utf-8-sig")):
            if re.match(r"^(?:https?|mailto|plugin|codex|data):", target, re.I):
                continue
            total += 1
            resolved = resolve_link(path, target)
            if not resolved.exists():
                failures.append({"source": rel(path), "target": target, "status": classification(path)})
    return {"checked": total, "broken": failures}


def notice(path, kind, date):
    anchor = DOC / "ETAT_ACTUEL_IMPLEMENTATION.md"
    if kind in ("research", "planning") and path.parent.name in ("fr", "cn"):
        anchor = path.parent / "README.md"
    elif kind == "research" and path.parent.name == "ml":
        anchor = DOC / "ml/experiences_done.md"
    url = quote(os.path.relpath(anchor, path.parent).replace(os.sep, "/"), safe="/.")
    if kind == "archive":
        message = "Archive conservée pour traçabilité : les commandes, paramètres et promotions ci-dessous décrivent leur époque, pas une consigne actuelle. Ne pas réactiver un batch sur la base de ce texte."
    elif kind == "research":
        message = "Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels."
    elif kind == "planning":
        message = "Plan / TODO : ne vaut ni validation des données, ni autorisation broker. Les dépendances et blocages actuels priment sur l'ordre des sprints."
    else:
        message = "Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle."
    return f"{NOTICE_START}\n> Statut documentaire au {date} — {message} [Référence actuelle]({url}).\n{NOTICE_END}\n\n"


def write(path, content, changed):
    path = path.resolve()
    if not path.is_relative_to(DOC.resolve()):
        raise ValueError(f"Documentation target outside doc: {path}")
    previous = path.read_text("utf-8-sig") if path.exists() else None
    if previous != content:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        changed.append(rel(path))


def render_api(package, items, date):
    lines = [f"# Inventaire API — {package}", "", f"Extraction AST du {date} ; aucune importation ni exécution métier.", "", "Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.", "Les symboles `_...` sont internes. Signature présente ≠ API publique stable.", ""]
    for item in items:
        if item["package"] != package:
            continue
        lines.extend([f"## `{item['path']}`", "", f"Source SHA-256 : `{item['sha256']}`", ""])
        for symbol in item["symbols"]:
            signature = symbol["signature"].replace("`", "\\`").replace("\n", " ")
            target = quote("../../" + item["path"], safe="/.")
            lines.append(f"- [{symbol['name']}]({target}) — ligne {symbol['line']} : `{signature}`")
        if not item["symbols"]:
            lines.append("Module sans déclaration publique/privée de classe ou fonction au niveau module.")
        lines.append("")
    return "\n".join(lines)


def flat_keys(value, prefix=""):
    if isinstance(value, dict):
        for key, child in value.items():
            path = prefix + "." + str(key) if prefix else str(key)
            yield path, type(child).__name__
            yield from flat_keys(child, path)
    elif isinstance(value, list) and value and isinstance(value[0], dict):
        yield from flat_keys(value[0], prefix + "[]")


def config_inventory(date):
    names = ["config.yaml", "config_cn.yaml", "config_fr.yaml", "batch.yaml", "batch_cn.yaml", "batch_fr.yaml", "config/databases.yaml"]
    names += [rel(p) for p in sorted((ROOT / "config/markets").glob("*.yaml"))]
    lines = ["# Inventaire des clés de configuration", "", f"Généré depuis les fichiers du dépôt au {date}. Valeurs et secrets volontairement omis.", "Un type YAML observé n'est pas une validation de consommation ni un default Python.", "Priorités et contrats : [guide configuration](../18_reference_configuration.md).", ""]
    for name in names:
        path = ROOT / name
        value = yaml.safe_load(path.read_text("utf-8-sig")) or {}
        lines.extend([f"## `{name}`", "", "| Clé | Type présent |", "| --- | --- |"])
        for key, kind in flat_keys(value):
            lines.append(f"| `{key}` | {kind} |")
        lines.append("")
    return "\n".join(lines)


def navigation_inventory(date):
    path = ROOT / "ihm/services/navigation.py"
    tree = ast.parse(path.read_text("utf-8-sig"))
    lines = ["# Pages IHM déclarées", "", f"Extraction statique au {date}, depuis `ihm/services/navigation.py`.", "La colonne groupe est le groupe legacy de la déclaration ; la sidebar est organisée par get_navigation_sections().", "[Guide utilisateur](../guide_utilisateur/README.md).", "", "| Clé | Libellé | Module | Groupe legacy |", "| --- | --- | --- | --- |"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "NavigationPage":
            values = [ast.literal_eval(arg) for arg in node.args]
            lines.append(f"| `{values[1]}` | {values[0]} | `{values[2]}` | {values[3]} |")
    return "\n".join(lines) + "\n"


def schema_inventory(date):
    lines = ["# DDL et graphe des migrations présents dans le dépôt", "", f"Inventaire statique au {date}, **pas un schéma déployé**. Aucun SQL exécuté.", "Les tables peuvent être définies à plusieurs endroits ou migrées depuis un DDL initial.", "Le graphe des révisions et les ALTER ultérieurs priment sur un CREATE isolé.", "Les migrations US ne s'appliquent pas automatiquement aux bases CN/FR.", "[Contrat migrations](../database/migrations_et_transactions.md).", "", "## Révisions Alembic", "", "| Fichier | revision | down_revision |", "| --- | --- | --- |"]
    migration_paths = [p for package in ("alembic", "alembic_cn", "alembic_fr") for p in (ROOT / package / "versions").glob("*.py")]
    for path in sorted(migration_paths):
        values = {}
        tree = ast.parse(path.read_text("utf-8-sig"))
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in names:
                    if isinstance(target, ast.Name) and target.id in ("revision", "down_revision"):
                        try:
                            values[target.id] = ast.literal_eval(node.value)
                        except (ValueError, TypeError):
                            values[target.id] = "expression dynamique"
        if values:
            link = quote("../../" + rel(path), safe="/.")
            lines.append(f"| [{rel(path)}]({link}) | `{values.get('revision')}` | `{values.get('down_revision')}` |")
    lines += ["", "## Tables nommées dans les DDL SQL", "", "| Table | DDL présent |", "| --- | --- |"]
    tables = defaultdict(list)
    sql_files = list((ROOT / "database").rglob("*.sql")) + list((ROOT / "alembic").rglob("*.sql"))
    for path in sorted(set(sql_files)):
        text = path.read_text("utf-8-sig")
        for match in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w`.]+)", text, re.I):
            tables[match.group(1).replace("`", "")].append(rel(path))
    for table, names in sorted(tables.items()):
        refs = ", ".join(f"[{name}](../../{quote(name, safe='/.' )})" for name in dict.fromkeys(names))
        lines.append(f"| `{table}` | {refs} |")
    return "\n".join(lines) + "\n"


def table_cell(value):
    return " ".join(str(value).replace("|", r"\|").split())


def batch_inventory(date):
    """Declared catalog values only, not effective env overrides nor task state."""
    lines = ["# Catalogues de batchs déclarés — référence générée", "",
        f"Extraction YAML au {date}, sans importer le service ni interroger Windows/SQL.",
        "Les valeurs sont déclaratives : enabled ne prouve ni exécutable ni installé.",
        "Le catalogue IHM applique aussi ses blocages et, pour les familles CN non raccordées, sa mise en sommeil.",
        "Les noms d'état BLOCKED/PENDING priment ; aucune consigne de réactivation n'est déduite ici.",
        "[Contrats et état effectif du catalogue](../operations/catalogue_batchs_actuel.md).", ""]
    for name in ("batch.yaml", "batch_cn.yaml", "batch_fr.yaml"):
        config = yaml.safe_load((ROOT / name).read_text("utf-8-sig")) or {}
        defaults = config.get("defaults") or {}
        lines += [f"## `{name}`", "", "| Batch | enabled déclaré | Statut déclaré | Priorité | Principal (heures/minutes ; jours ; fuseau) | Secours | Reprise déclarée |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for key, section in config.items():
            if key in ("defaults", "schema_version") or not isinstance(section, dict):
                continue
            cfg = {**defaults, **section}
            enabled = cfg.get("enabled", True)
            schedule = f"{cfg.get('run_hours', '—')} / {cfg.get('run_minutes', '0')} ; {cfg.get('run_days', 'tous')} ; {cfg.get('timezone', 'Windows local')}"
            recovery = f"{cfg.get('recovery_run_hours')} / {cfg.get('recovery_run_minutes', '0')} (conditionnel)" if cfg.get("recovery_run_hours") else "—"
            window = cfg.get("coverage_description") or f"lookback_days={cfg.get('lookback_days', '—')} ; lookahead_days={cfg.get('lookahead_days', '—')}"
            values = [f"`{key}`", enabled, cfg.get("status") or ("ACTIVE" if enabled else "DISABLED"), cfg.get("priority", "—"), schedule, recovery, window]
            lines.append("| " + " | ".join(table_cell(v) for v in values) + " |")
        lines.append("")
    return "\n".join(lines)


def module_inventory(items, date):
    lines = ["# Couverture statique du code Python", "", f"Inventaire au {date}. Chaque module est localisable dans son inventaire API.", "Cette couverture des déclarations n'est pas une certification de chaque algorithme.", "Les scripts CLI de recherche sont référencés dans leurs comptes rendus ; ne pas les exécuter pour lire la documentation.", "", "| Package | Modules Python analysés | Déclarations | Référence |", "| --- | ---: | ---: | --- |"]
    for package in PACKAGES:
        members = [item for item in items if item["package"] == package]
        lines.append(f"| `{package}` | {len(members)} | {sum(len(m['symbols']) for m in members)} | [API](../api/{package}.md) |")
    lines += ["", "Le registre machine [inventaire_sources.json](../audit/inventaire_sources.json)", "porte les chemins, signatures, lignes et SHA-256 pour détecter une dérive ultérieure.", ""]
    return "\n".join(lines)


def registry(date):
    files = sorted(p for p in DOC.rglob("*") if p.is_file())
    lines = ["# Registre exhaustif des fichiers documentaires", "", f"Classement de tous les fichiers sous doc au {date}.", "Un contrôle structurel de tous les fichiers n'est pas une revue humaine de chaque assertion.", "Archives et résultats gardent leurs chiffres d'origine ; les liens vers le contrat courant évitent de les prendre pour des consignes de production.", "[Bilan de révision](../AUDIT_COMPLET_DOCUMENTATION_20261010.md).", "", "| Fichier | Statut |", "| --- | --- |"]
    for path in files:
        name = path.relative_to(DOC).as_posix()
        lines.append(f"| [{name}](../{quote(name, safe='/.' )}) | {classification(path)} |")
    return "\n".join(lines) + "\n"


def repair_old_links(changed):
    """Repair moved references, without inventing absent experimental evidence."""
    manual = {
        "runbook_24_7.md": "doc/operations/us_pipeline.md",
        "pre_live_checklist.md": "doc/operations/pre_live_et_progression.md",
        "preset_petit_capital_2000eur.md": "doc/risk/capital_sizing_et_fractionnement.md",
        "matrice_ihm_cli.md": "doc/guide_utilisateur/COUVERTURE_PAGES_IHM.md",
        "onboarding_operator.md": "doc/guide_utilisateur/README.md",
        "perf_pipeline.md": "doc/operations/performance_et_capacite.md",
        "perf_hotspots.md": "doc/operations/performance_et_capacite.md",
        "sandbox_health_runbook.md": "doc/operations/sandbox_health.md",
        "disaster_recovery.md": "doc/operations/sauvegarde_reprise_et_retention.md",
        "external_audit_checklist.md": "doc/operations/compliance_et_audit.md",
        "external_audit_engagement.md": "doc/operations/compliance_et_audit.md",
        "pre_audit_findings.md": "doc/operations/compliance_et_audit.md",
        "artifacts_retention_policy.md": "doc/operations/sauvegarde_reprise_et_retention.md",
        "synthese_long_short.md": "doc/experiences/archives_ml/synthese_long_short.md",
        "analyse_ml.md": "doc/ml/README.md",
    }
    current_failures = audit_links()["broken"]
    by_source = defaultdict(list)
    for problem in current_failures:
        by_source[problem["source"]].append(problem["target"])
    by_name = defaultdict(list)
    for path in DOC.rglob("*.md"):
        by_name[path.name].append(path)
    for source, targets in by_source.items():
        path = ROOT / source
        body = path.read_text("utf-8-sig")
        for target in dict.fromkeys(targets):
            base = unquote(target.split("#", 1)[0]).replace("\\", "/").split("/")[-1]
            candidates = by_name[base]
            replacement = ROOT / manual[base] if base in manual else candidates[0] if len(candidates) == 1 else None
            if base == "architecture" or target.endswith("architecture/"):
                replacement = DOC / "02_architecture_globale.md"
            if replacement is None and base.endswith(".py"):
                name = unquote(target.split("#", 1)[0])
                for package in PACKAGES:
                    marker = package + "/"
                    if marker in name:
                        candidate = ROOT / name[name.rfind(marker):]
                        if candidate.exists():
                            replacement = candidate
                            break
            if replacement is not None and replacement.exists():
                url = quote(os.path.relpath(replacement, path.parent).replace(os.sep, "/"), safe="/.")
                # Old section anchors are deliberately dropped after a move/merge.
                body = body.replace("(" + target + ")", "(" + url + ")")
            else:
                # Keep the evidence identifier, but do not publish a dead link.
                pattern = re.compile(r"\[([^\]]+)\]\(" + re.escape(target) + r"\)")
                body = pattern.sub(lambda m: m.group(1) + f" — référence historique absente localement : `{target}`", body)
        write(path, body, changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--date", default="2026-10-10")
    parser.add_argument("--audit-links", action="store_true")
    args = parser.parse_args()
    if args.audit_links:
        result = audit_links()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(bool(result["broken"]))
    items, errors = source_inventory()
    changed = []
    if args.apply:
        if errors:
            raise RuntimeError(f"AST failures: {errors}")
        for package in PACKAGES:
            write(DOC / f"api/{package}.md", render_api(package, items, args.date), changed)
        write(DOC / "reference/configuration_generee.md", config_inventory(args.date), changed)
        write(DOC / "reference/navigation_generee.md", navigation_inventory(args.date), changed)
        write(DOC / "reference/schema_et_migrations_generes.md", schema_inventory(args.date), changed)
        write(DOC / "reference/batchs_generes.md", batch_inventory(args.date), changed)
        write(DOC / "reference/modules_generes.md", module_inventory(items, args.date), changed)
        write(DOC / "audit/inventaire_sources.json", json.dumps({"date": args.date, "scope": "static AST, no business execution", "sources": items, "errors": errors}, ensure_ascii=False, indent=2) + "\n", changed)
        # Create generated targets before repairing links to avoid treating a
        # newly added reference as missing historical evidence.
        write(DOC / "INDEX.md", doc_index.generate(), changed)
        repair_old_links(changed)
        for path in sorted(DOC.rglob("*.md")):
            kind = classification(path)
            if kind == "generated":
                continue
            body = clean_notice(path.read_text("utf-8-sig"))
            title = re.search(r"^# .+$", body, re.M)
            if title:
                end = title.end()
                body = body[:end] + "\n\n" + notice(path, kind, args.date) + body[end:].lstrip("\n")
            else:
                body = notice(path, kind, args.date) + body
            write(path, body, changed)
        # Include the audit file and the registry itself in the final full census.
        write(DOC / "audit/controle_liens.json", json.dumps(audit_links(), ensure_ascii=False, indent=2) + "\n", changed)
        write(DOC / "audit/registre_documentaire.md", registry(args.date), changed)
        write(DOC / "INDEX.md", doc_index.generate(), changed)
        write(DOC / "audit/controle_liens.json", json.dumps(audit_links(), ensure_ascii=False, indent=2) + "\n", changed)
    classes = Counter(classification(p) for p in DOC.rglob("*") if p.is_file())
    print(json.dumps({"documents": dict(classes), "python_modules": len(items), "declarations": sum(len(x['symbols']) for x in items), "ast_errors": errors, "changed": len(changed), "links": audit_links()}, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
