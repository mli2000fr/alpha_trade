"""Delayed SIP stock references for research collectors, never execution quotes."""
from datetime import datetime, timedelta, timezone

from common.market_calendar import get_market_calendar


def historical_sip_snapshots(session, symbols, headers, request_json, *, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=20)
    calendar = get_market_calendar("US_EQ", allow_us_weekday_fallback=False)
    sessions = [s for s in calendar.sessions(cutoff.date()-timedelta(days=15), cutoff.date())
                if s.is_open and s.open_at_utc < cutoff]
    if not sessions:
        raise RuntimeError("Aucune séance US disponible pour la référence SIP retardée")
    session_info = sessions[-1]
    end = min(cutoff, session_info.close_at_utc)
    start = max(session_info.open_at_utc, end-timedelta(minutes=30))
    params = {"symbols": ",".join(symbols), "feed": "sip", "timeframe": "1Min",
              "start": start.isoformat(), "end": end.isoformat(),
              "adjustment": "raw", "asof": "-", "limit": 10000, "sort": "desc"}
    payload, status = request_json(session, "https://data.alpaca.markets/v2/stocks/bars", params=params, headers=headers)
    if status != 200 or not isinstance(payload,dict) or not isinstance(payload.get("bars"),dict):
        raise RuntimeError(f"Référence SIP retardée indisponible HTTP {status}; aucun fallback IEX")
    if payload.get("next_page_token"):
        raise RuntimeError("Référence SIP tronquée : réduire le chunk, ne pas considérer les absences comme normales")
    references = {}
    for symbol, bars in payload["bars"].items():
        if symbol not in symbols:
            raise RuntimeError("Symbole inattendu dans la référence SIP")
        if bars:
            references[symbol] = {"minuteBar": max(bars,key=lambda r:r["t"]),
                                  "stock_reference_feed":"sip", "reference_request":params}
    return references, status
