"""Routage allowlisté des connexions par marché.

Ce module interdit qu'un traitement CN choisisse librement un schéma ou
retombe silencieusement sur la base US. Les secrets restent en variables
d'environnement ; seuls les alias et noms de variables figurent en YAML.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from common.config_loader import load_market_registry
from common.market_context import MarketCompatibilityError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROUTING_CONFIG = ROOT / "config" / "databases.yaml"


@dataclass(frozen=True, slots=True)
class DatabaseRoute:
    alias: str
    database: str
    host: str
    user_env: str
    password_env: str
    fallback_user_env: str | None
    fallback_password_env: str | None
    allowed_markets: frozenset[str]


def _env_or_default(name: str | None, default: str) -> str:
    value = os.getenv(name or "", "").strip()
    return value or default


def _credential(primary: str, fallback: str | None) -> str:
    value = os.getenv(primary, "").strip()
    if value:
        return value
    if fallback:
        value = os.getenv(fallback, "").strip()
        if value:
            return value
    suffix = f" ou {fallback}" if fallback else ""
    raise RuntimeError(f"Variable d'environnement absente : {primary}{suffix}")


@lru_cache(maxsize=4)
def load_database_routes(path: str | Path = DEFAULT_ROUTING_CONFIG) -> dict[str, DatabaseRoute]:
    source = Path(path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if payload.get("schema_version") != 1 or not isinstance(payload.get("databases"), dict):
        raise RuntimeError(f"Configuration de bases invalide : {source}")
    routes: dict[str, DatabaseRoute] = {}
    for alias, raw in payload["databases"].items():
        if not isinstance(raw, dict):
            raise RuntimeError(f"Route invalide : {alias}")
        database = _env_or_default(raw.get("database_env"), str(raw.get("database") or ""))
        host = _env_or_default(raw.get("host_env"), str(raw.get("host") or "localhost"))
        allowed = frozenset(str(value).strip().upper() for value in raw.get("allowed_markets", []))
        if not database or not allowed:
            raise RuntimeError(f"Route incomplète : {alias}")
        routes[str(alias)] = DatabaseRoute(
            alias=str(alias),
            database=database,
            host=host,
            user_env=str(raw.get("user_env") or "LOGIN_DB"),
            password_env=str(raw.get("password_env") or "PASSWORD_DB"),
            fallback_user_env=str(raw["fallback_user_env"]) if raw.get("fallback_user_env") else None,
            fallback_password_env=(
                str(raw["fallback_password_env"]) if raw.get("fallback_password_env") else None
            ),
            allowed_markets=allowed,
        )
    return routes


def resolve_database_route(
    database_alias: str,
    market_code: str,
    *,
    config_path: str | Path = DEFAULT_ROUTING_CONFIG,
) -> DatabaseRoute:
    routes = load_database_routes(config_path)
    try:
        route = routes[database_alias]
    except KeyError as exc:
        raise MarketCompatibilityError(f"Alias de base non autorisé : {database_alias!r}") from exc
    normalized_market = str(market_code).strip().upper()
    if normalized_market not in route.allowed_markets:
        raise MarketCompatibilityError(
            f"{normalized_market} incompatible avec {database_alias!r}; "
            f"marchés autorisés={sorted(route.allowed_markets)}"
        )
    load_market_registry().assert_compatible(normalized_market, database_alias)
    return route


def build_database_url(
    database_alias: str,
    market_code: str,
    *,
    database_override: str | None = None,
    config_path: str | Path = DEFAULT_ROUTING_CONFIG,
) -> str:
    route = resolve_database_route(database_alias, market_code, config_path=config_path)
    username = _credential(route.user_env, route.fallback_user_env)
    password = _credential(route.password_env, route.fallback_password_env)
    database = database_override or route.database
    return (
        f"mysql+pymysql://{quote_plus(username)}:{quote_plus(password)}@"
        f"{route.host}/{database}?charset=utf8mb4"
    )


def get_market_engine(
    market_code: str,
    *,
    database_alias: str,
    url: str | None = None,
    verify_schema: bool = True,
    config_path: str | Path = DEFAULT_ROUTING_CONFIG,
    **engine_options: Any,
) -> Engine:
    route = resolve_database_route(database_alias, market_code, config_path=config_path)
    resolved_url = url or build_database_url(
        database_alias,
        market_code,
        config_path=config_path,
    )
    engine = create_engine(resolved_url, pool_pre_ping=True, pool_recycle=3600, **engine_options)
    if verify_schema and not str(resolved_url).startswith("sqlite"):
        with engine.connect() as conn:
            actual = str(conn.execute(text("SELECT DATABASE()" )).scalar() or "")
        if actual != route.database:
            engine.dispose()
            raise MarketCompatibilityError(
                f"Route {database_alias!r} attend {route.database!r}, connexion réelle={actual!r}"
            )
    return engine


__all__ = [
    "DatabaseRoute",
    "build_database_url",
    "get_market_engine",
    "load_database_routes",
    "resolve_database_route",
]
