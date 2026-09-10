from __future__ import annotations

import json

from modelFactory.eroya_directional_poc import (
    DATASETS,
    EroyaClient,
    _normalize_api_url,
    _request_for,
    probe_entitlements,
)


class _Response:
    def __init__(self, status: int, payload: dict) -> None:
        self.status_code = status
        self._payload = payload
        self.headers = {}

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def json(self):
        return self._payload


class _Session:
    def __init__(self, responses: list[_Response]) -> None:
        self.headers = {}
        self.responses = list(responses)

    def get(self, url, **kwargs):
        return self.responses.pop(0)


def test_partner_ticker_gets_us_suffix_and_key_never_enters_params() -> None:
    path, params = _request_for(DATASETS["eps_revisions"], "aapl", start_date=None, end_date=None, probe=True)
    assert path == "fundamentals/us-eps-revisions"
    assert params["ticker"] == "AAPL.US"
    assert "apiKey" not in params


def test_short_volume_collection_request_is_date_bounded() -> None:
    path, params = _request_for(DATASETS["short_volume"], "AAPL", start_date="2020-01-01", end_date="2024-01-01", probe=False)
    assert path == "stocks/short-volume"
    assert params["date.gte"] == "2020-01-01"
    assert params["date.lte"] == "2024-01-01"


def test_analyst_insights_collection_request_is_date_bounded() -> None:
    path, params = _request_for(
        DATASETS["analyst_insights"], "AAPL", start_date="2020-01-01",
        end_date="2025-12-31", probe=False)
    assert path == "benzinga/analyst-insights"
    assert params["ticker"] == "AAPL"
    assert params["date.gte"] == "2020-01-01"
    assert params["date.lte"] == "2025-12-31"


def test_form4_collection_uses_plural_tickers_and_filing_date() -> None:
    path, params = _request_for(
        DATASETS["form4_raw"], "AAPL", start_date="2022-01-01",
        end_date="2025-12-31", probe=False)
    assert path == "stocks/filings/form-4"
    assert params["tickers"] == "AAPL"
    assert params["filing_date.gte"] == "2022-01-01"
    assert params["filing_date.lte"] == "2025-12-31"


def test_form8k_disclosures_uses_plural_tickers_and_filing_date() -> None:
    path, params = _request_for(
        DATASETS["form8k_disclosures"], "AAPL", start_date="2018-01-01",
        end_date="2025-12-31", probe=False)
    assert path == "stocks/filings/8-K/disclosures"
    assert params["tickers"] == "AAPL"
    assert params["filing_date.gte"] == "2018-01-01"
    assert params["filing_date.lte"] == "2025-12-31"


def test_probe_reports_entitlement_without_persisting_payload_or_key() -> None:
    session = _Session([_Response(451, {"error": "provider unavailable"})])
    client = EroyaClient("secret-value", session=session, max_retries=0)
    rows = probe_entitlements(client, ["short_interest"])
    encoded = json.dumps(rows)
    assert rows[0]["http_status"] == 451
    assert not rows[0]["accessible"]
    assert "secret-value" not in encoded
    assert "Authorization" not in encoded


def test_provider_pagination_url_is_rewritten_through_eroya() -> None:
    url = _normalize_api_url(
        "https://api.massive.com/v3/snapshot/options/AAPL?cursor=next&apiKey=provider-secret")
    assert url == "https://api.eroya.co/v1/snapshot/options/AAPL?cursor=next"
    assert "provider-secret" not in url


def test_provider_form4_vx_pagination_is_rewritten_through_eroya() -> None:
    url = _normalize_api_url(
        "https://api.massive.com/stocks/filings/vX/form-4?cursor=next")
    assert url == "https://api.eroya.co/v1/stocks/filings/form-4?cursor=next"


def test_eroya_pagination_url_keeps_cursor_but_removes_embedded_key() -> None:
    url = _normalize_api_url(
        "https://api.eroya.co/v1/stocks/short-volume?cursor=next&api_key=secret")
    assert url == "https://api.eroya.co/v1/stocks/short-volume?cursor=next"
