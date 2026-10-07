"""Collecte bornée de pièces fiscales et CA ; aucune promotion automatique."""
import argparse
import json
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from service.fr.execution_evidence_12c import collect_source


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    sources = {}
    targets = {"ttf_scope": "https://bofip.impots.gouv.fr/bofip/7570-PGP.html/identifiant=BOI-TCA-FIN-10-10-20151221",
               "xfab_ir": "https://www.xfab.com/investors/",
               "nexity_agm_2025": "https://media.nexity.fr/upload/ged/pdf/Assemblee-generale---22-mai-2025_Vdef_mel2.pdf",
               "nexity_halfyear_2024": "https://pressroom.nexity.fr/download-pdf/66a26028aa81b4f03708bb74"}
    for name, url in targets.items():
        try:
            suffix = ".pdf" if name.startswith("nexity_") else ".html"
            sources[name] = {**collect_source(url, output / f"{name}{suffix}"), "status": "ARCHIVED_NOT_PROMOTED"}
        except Exception as exc:
            sources[name] = {"url": url, "status": "UNAVAILABLE", "error": str(exc)}
    page = sources.get("xfab_ir", {})
    if page.get("path"):
        soup = BeautifulSoup(Path(page["path"]).read_text(encoding="utf-8"), "html.parser")
        for year in (2023, 2024, 2025):
            matches = {urljoin(page["url"], a["href"]) for a in soup.select("a[href]")
                       if f"X-FAB_Annual_Report_{year}_ENG.pdf" in a["href"]}
            if len(matches) != 1:
                sources[f"xfab_{year}"] = {"status": "AMBIGUOUS_OR_MISSING_LINK", "matches": sorted(matches)}
                continue
            url = next(iter(matches))
            try:
                row = collect_source(url, output / f"xfab_{year}.pdf")
                if not Path(row["path"]).read_bytes().startswith(b"%PDF"):
                    raise ValueError("Document non PDF")
                sources[f"xfab_{year}"] = {**row, "status": "ARCHIVED_NOT_PROMOTED"}
            except Exception as exc:
                sources[f"xfab_{year}"] = {"url": url, "status": "UNAVAILABLE", "error": str(exc)}
    result = {"status": "PRIORITY_SOURCES_COLLECTED_NOT_FISCAL_OR_CA_GO", "sources": sources,
              "canonical_writes": False, "economic_qualified_paths": 0, "models_refit": 0}
    (output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    print(json.dumps(run(parser.parse_args().output)))
