"""Historical closing quotes: explicit feed, evidence and fail-closed validation."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

from common.market_calendar import get_nyse_session_bounds

PROVENANCE_COLUMNS = {"provider", "feed", "quality_status", "collected_at",
                      "raw_payload_sha256", "raw_payload_path", "source_timestamp"}
ARCHIVE_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "quotes"


@lru_cache(maxsize=4096)
def quote_session_bounds(session_day):
    """One calendar lookup per day, not twice for every historical quote."""
    return get_nyse_session_bounds(session_day)


def historical_quote_feed(override=None):
    from common.config_loader import load_config
    value = override if override is not None else (load_config().get("market_data") or {}).get("quotes_historical_feed", "sip")
    value = str(value).strip().lower()
    if value != "sip":
        raise ValueError("market_data.quotes_historical_feed doit être sip (aucun fallback IEX)")
    return value


def quote_invalid_reason(row, session_day: date):
    try:
        bid, ask, bs, ass = [float(row.get(k)) for k in ("bid_price", "ask_price", "bid_size", "ask_size")]
        if not all(math.isfinite(v) for v in (bid, ask, bs, ass)) or bid <= 0 or ask < bid or min(bs, ass) <= 0:
            return "invalid_bid_ask_or_size"
        spread = float(row.get("spread_bps"))
        computed = (ask-bid)/((ask+bid)/2)*10000
        if not math.isfinite(spread) or not math.isclose(spread, computed, rel_tol=0, abs_tol=1e-6):
            return "invalid_spread"
        stamp = row.get("source_timestamp") or row.get("quote_timestamp")
        if not isinstance(stamp, datetime):
            stamp = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
        opening, closing = quote_session_bounds(session_day)
        if not opening <= stamp <= closing:
            return "outside_requested_session"
        if closing - stamp > timedelta(minutes=15):
            return "stale_closing_quote"
    except (ValueError, TypeError, OverflowError):
        return "missing_or_invalid_quote"
    return None


def qualified_quote(row, session_day: date, feed="sip"):
    return (row.get("provider") == "alpaca" and row.get("feed") == feed
            and row.get("quality_status") == "VALID_RTH"
            and bool(row.get("raw_payload_path"))
            and len(str(row.get("raw_payload_sha256") or "")) == 64
            and row.get("collected_at") is not None
            and quote_invalid_reason(row, session_day) is None
            and quote_evidence_valid(row))


def quote_evidence_valid(row):
    root = ARCHIVE_ROOT.parent.parent.resolve()
    try:
        path = (root / row["raw_payload_path"]).resolve()
        if not path.is_relative_to(ARCHIVE_ROOT.resolve()):
            return False
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["raw_payload_sha256"]:
            return False
        evidence = json.loads(raw)
        if (evidence["provider"] != row["provider"] or evidence["feed"] != row["feed"]
                or evidence["symbol"] != row["symbol"]
                or evidence["session_date"] != str(row["quote_date"])[:10]):
            return False
        for stored, source in [("bid_price", "bp"), ("ask_price", "ap"),
                               ("bid_size", "bs"), ("ask_size", "as")]:
            if float(row[stored]) != float(evidence["quote"][source]):
                return False
        raw_timestamp = datetime.fromisoformat(evidence["quote"]["t"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
        stored_timestamp = row.get("source_timestamp")
        if not isinstance(stored_timestamp, datetime):
            stored_timestamp = datetime.fromisoformat(str(stored_timestamp))
        return stored_timestamp == raw_timestamp
    except (OSError, TypeError, ValueError, KeyError):
        return False


def archive_quote(symbol, session_day, feed, quote, collected_at, *, request_context=None):
    opening, closing = quote_session_bounds(session_day)
    payload = {"provider": "alpaca", "feed": feed, "symbol": symbol,
               "session_date": session_day.isoformat(), "collected_at_utc": collected_at.isoformat(),
               "request": request_context or {"start": opening.isoformat(), "end": closing.isoformat(),
                           "sort": "desc", "limit": 1, "feed": feed}, "quote": quote}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()
    digest = hashlib.sha256(raw).hexdigest()
    path = ARCHIVE_ROOT / "alpaca" / feed / session_day.isoformat() / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise RuntimeError("Collision d'archive quote")
    return {"provider": "alpaca", "feed": feed, "collected_at": collected_at,
            "raw_payload_sha256": digest, "raw_payload_path": str(path.relative_to(ARCHIVE_ROOT.parent.parent))}
