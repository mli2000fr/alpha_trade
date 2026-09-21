from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import requests

from service.tushare.errors import (
    TushareAuthenticationError,
    TushareQuotaError,
    TushareResponseError,
)
from service.tushare.models import TusharePage
from service.tushare.quota import QuotaBudget
from service.tushare.retry import RetryPolicy, with_retry


class TushareClient:
    BASE_URL = "https://api.tushare.pro"

    def __init__(
        self,
        token: str,
        *,
        session: requests.Session | None = None,
        quota: QuotaBudget | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout_seconds: float = 30.0,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        if not str(token).strip():
            raise TushareAuthenticationError("Token Tushare vide")
        self._token = str(token).strip()
        self.session = session or requests.Session()
        self.quota = quota or QuotaBudget()
        self.retry_policy = retry_policy or RetryPolicy()
        self.timeout_seconds = float(timeout_seconds)
        self._sleeper = sleeper

    def query(
        self,
        api_name: str,
        *,
        params: Mapping[str, Any] | None = None,
        fields: tuple[str, ...] | list[str] | str | None = None,
    ) -> TusharePage:
        field_text = fields if isinstance(fields, str) else ",".join(fields or ())
        request_payload = {
            "api_name": str(api_name),
            "token": self._token,
            "params": dict(params or {}),
            "fields": field_text,
        }

        def operation() -> TusharePage:
            self.quota.acquire()
            response = self.session.post(
                self.BASE_URL,
                json=request_payload,
                timeout=self.timeout_seconds,
            )
            if response.status_code == 429:
                raise TushareQuotaError("HTTP 429 Tushare")
            if response.status_code >= 500:
                raise requests.ConnectionError(f"HTTP {response.status_code} Tushare")
            if response.status_code >= 400:
                raise TushareResponseError(f"HTTP {response.status_code} Tushare")
            try:
                payload = response.json()
            except ValueError as exc:
                raise TushareResponseError("Réponse Tushare non JSON") from exc
            if not isinstance(payload, dict):
                raise TushareResponseError("Réponse Tushare invalide")
            code = int(payload.get("code") or 0)
            message = str(payload.get("msg") or "")
            if code != 0:
                lowered = message.lower()
                if any(term in lowered for term in ("token", "权限", "permission")):
                    raise TushareAuthenticationError(f"Tushare {code}: {message}")
                if any(term in lowered for term in ("频次", "quota", "limit", "积分")):
                    raise TushareQuotaError(f"Tushare {code}: {message}")
                raise TushareResponseError(f"Tushare {code}: {message}")
            data = payload.get("data") or {}
            raw_fields = data.get("fields") or []
            raw_items = data.get("items") or []
            if not isinstance(raw_fields, list) or not isinstance(raw_items, list):
                raise TushareResponseError("Schéma data.fields/items invalide")
            rows: list[dict[str, Any]] = []
            for item in raw_items:
                if not isinstance(item, list) or len(item) != len(raw_fields):
                    raise TushareResponseError("Ligne Tushare incompatible avec fields")
                rows.append(dict(zip(raw_fields, item, strict=True)))
            response_payload = {**payload, "request_token_redacted": True}
            return TusharePage(
                endpoint=str(api_name),
                fields=tuple(str(value) for value in raw_fields),
                rows=tuple(rows),
                request_payload={**request_payload, "token": "***"},
                response_payload=response_payload,
                http_status=response.status_code,
                provider_code=code,
            )

        kwargs = {"policy": self.retry_policy}
        if self._sleeper is not None:
            kwargs["sleeper"] = self._sleeper
        return with_retry(operation, **kwargs)


__all__ = ["TushareClient"]
