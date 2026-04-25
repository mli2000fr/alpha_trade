from ihm.components.alpha_scanner_dependency import build_alpha_scanner_dependency_rows


def test_build_alpha_scanner_dependency_rows_formats_shared_diagnostic_table() -> None:
	diagnostic = {
		"dependencies": {
			"sync_latest_quotes": {
				"label": "Sync Latest Quotes",
				"status": "green",
				"latest_date": "2026-04-25",
				"coverage_pct": 92.5,
				"covered_symbols": 185,
				"eligible_symbols": 200,
				"reason": "quotes disponibles pour le filtre de spread",
				"command": "python -m dataIntegrityEngine.sync_latest_quotes",
			},
			"sync_earnings_calendar": {
				"label": "Sync Earnings Calendar",
				"status": "orange",
				"latest_date": "2026-05-05",
				"coverage_pct": 6.0,
				"covered_symbols": 12,
				"eligible_symbols": 200,
				"reason": "couverture partielle (6.0%)",
				"command": "python -m dataIntegrityEngine.sync_earnings_calendar",
			},
		}
	}

	rows = build_alpha_scanner_dependency_rows(diagnostic)

	assert list(rows.columns) == [
		"Dépendance",
		"latest_date",
		"% couverture",
		"N symboles",
		"Univers",
		"Diagnostic",
		"Commande",
	]
	assert "Sync Latest Quotes" in rows.iloc[0]["Dépendance"]
	assert rows.iloc[0]["latest_date"] == "2026-04-25"
	assert rows.iloc[0]["% couverture"] == "92.5%"
	assert rows.iloc[1]["N symboles"] == "12"

