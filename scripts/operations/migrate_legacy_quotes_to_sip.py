"""Resumable actual SIP replacement of legacy quotes. Never relabel old data.

Only UPDATE existing stock_quote_snapshots keys. No orders, model or universe
publication, no bar modification. Each tranche is backed up before its commit.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import json
import logging
from pathlib import Path
import shutil
import time
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from sqlalchemy import bindparam, text

from common.market_calendar import get_nyse_session_bounds
from common.quote_quality import ARCHIVE_ROOT, archive_quote, quote_invalid_reason
from common.verified_http import verified_session
from dataIntegrityEngine.sync_latest_quotes import _build_quote_snapshot_row
from database.connection import get_sqlalchemy_engine
from service.alpaca.accounts import AccountRegistry
from service.market.intraday_backfill import atomic_json, run_lock

LOG = logging.getLogger(__name__)
ENDPOINT = "https://data.alpaca.markets/v2/stocks/quotes"
LEGACY = "(feed IS NULL OR feed <> 'sip')"


class MigrationBlocked(RuntimeError):
    pass


def _get_page(http, params, headers, stats, pause):
    """Retry only transient failures, never entitlement/quota refusals."""
    for attempt in range(3):
        time.sleep(pause if attempt == 0 else max(pause, 2 ** attempt))
        stats["requests_this_process"] += 1
        try:
            response = http.get(ENDPOINT, params=params, headers=headers, timeout=(10,30))
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 2:
                raise MigrationBlocked("SIP network failure after 3 attempts; tranche not written") from None
            LOG.warning("Transient SIP network failure; retry %s/3", attempt+2)
            continue
        if response.status_code in (500,502,503,504) and attempt < 2:
            LOG.warning("Transient SIP HTTP %s; retry %s/3", response.status_code, attempt+2)
            continue
        if response.status_code != 200:
            raise MigrationBlocked(f"SIP HTTP {response.status_code}; no fallback, tranche not written")
        return response


def save_progress(path, state):
    state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    atomic_json(path, state)


def save_gzip(path, payload):
    raw = gzip.compress(json.dumps(payload, sort_keys=True, default=str, allow_nan=False).encode(), mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
    return hashlib.sha256(raw).hexdigest()


def fetch_last_quotes(http, symbols, day, headers, root, stats, pause):
    """Progressively widen only absent symbols; preserve the latest, even invalid.

    No substitution of an earlier valid quote for a later crossed one. Pagination
    must finish before a tranche can be written. No symbol remapping (asof=-).
    """
    _, close = get_nyse_session_bounds(day)
    selected = {}
    for seconds in (1, 60, 900):
        missing = [s for s in symbols if s not in selected]
        if not missing:
            break
        params = dict(symbols=",".join(missing), feed="sip", asof="-", sort="desc", limit=10000,
                      start=(close-timedelta(seconds=seconds)).isoformat(), end=close.isoformat())
        seen = set()
        for _ in range(50):
            response = _get_page(http,params,headers,stats,pause)
            # Do not archive authenticated request objects or exception text.
            if response.status_code != 200:
                raise MigrationBlocked(f"SIP HTTP {response.status_code}; no fallback, tranche not written")
            payload = response.json()
            if not isinstance(payload,dict) or not isinstance(payload.get("quotes"),dict):
                raise MigrationBlocked("Invalid SIP quotes payload")
            request = {"endpoint":ENDPOINT,"params":dict(params),"retrieved_at_utc":datetime.now(timezone.utc).isoformat(),"payload":payload}
            identity = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
            raw_path = root/"raw"/str(day)/(identity+".json.gz")
            page_hash = save_gzip(raw_path, request)
            context = {"endpoint":ENDPOINT,"params":dict(params),"raw_page_path":str(raw_path),"raw_page_sha256":page_hash}
            for symbol, items in payload["quotes"].items():
                if symbol not in missing or not isinstance(items,list):
                    raise MigrationBlocked("Unexpected symbol or invalid quote list")
                for quote in items:
                    stamp = pd.Timestamp(quote["t"])
                    if stamp.tzinfo is None:
                        raise MigrationBlocked("SIP timestamp without timezone")
                    if symbol not in selected or stamp.value > selected[symbol][0]:
                        selected[symbol] = (stamp.value, quote, context)
            token = payload.get("next_page_token")
            if not token:
                break
            if token in seen:
                raise MigrationBlocked("Repeated pagination token; tranche not written")
            seen.add(token); params["page_token"] = token
        else:
            raise MigrationBlocked("Truncated SIP pagination; tranche not written")
    return selected


def replacement_rows(selected, day):
    good, invalid = [], []
    for symbol, (_, quote, context) in selected.items():
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        row = _build_quote_snapshot_row(symbol,quote,fallback_utc_now=now)
        row["quote_date"] = day
        evidence = archive_quote(symbol,day,"sip",quote,now,request_context=context)
        reason = quote_invalid_reason(row,day)
        if reason:
            invalid.append({"symbol":symbol,"reason":reason,"raw_payload_path":evidence["raw_payload_path"]})
        else:
            row.update(evidence,quality_status="VALID_RTH",source_timestamp=row["quote_timestamp"])
            good.append(row)
    return good, invalid


FIELDS = ("quote_timestamp","bid_price","ask_price","bid_size","ask_size","spread_bps",
          "provider","feed","quality_status","collected_at","source_timestamp","raw_payload_sha256","raw_payload_path")
UPDATE = text("UPDATE stock_quote_snapshots SET " + ",".join(f"`{f}`=:{f}" for f in FIELDS) +
              ", last_updated=CURRENT_TIMESTAMP WHERE symbol=:symbol AND quote_date=:quote_date AND " + LEGACY)


def run(args):
    if args.chunk_size not in range(1,501) or args.pause < .35 or args.max_seconds < 1 or args.start_date > args.end_date:
        raise ValueError("Invalid tranche, request pause or duration")
    root = Path(args.output).resolve(); root.mkdir(parents=True,exist_ok=True)
    engine = get_sqlalchemy_engine()
    if engine.url.database != "alpha_trade":
        raise ValueError("US alpha_trade only")
    protocol = {"version":1,"table":"stock_quote_snapshots","start":str(args.start_date),"end":str(args.end_date),
                "feed":"sip","asof":"-","chunk_size":args.chunk_size,"canonical_publication":False}
    started = time.monotonic()
    with run_lock(root):
        path = root/"protocol.json"
        if path.exists() and json.loads(path.read_text()) != protocol:
            raise ValueError("Different frozen protocol; use another output directory")
        if not path.exists(): atomic_json(path,protocol)
        state_path = root/"progress.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else dict(
            status="PLANNED",tranches_done=0,rows_replaced=0,rows_missing=0,rows_invalid=0)
        # Repair counters if the process stopped after SQL/task commit but
        # before the aggregate progress file was replaced.
        committed = [json.loads(p.read_text()) for p in (root/"tasks").glob("*.json")]
        committed = [t for t in committed if t.get("status")=="COMMITTED"]
        state.update(tranches_done=len(committed),rows_replaced=sum(t["rows_replaced"] for t in committed),
                     rows_missing=sum(len(t["missing"]) for t in committed),rows_invalid=sum(len(t["invalid"]) for t in committed))
        state.update(status="RUNNING" if args.write else "PLANNED",requests_this_process=0,
                     started_at_utc=datetime.now(timezone.utc).isoformat())
        state.pop("error", None); state.pop("error_type", None)
        with engine.connect() as c:
            days = c.execute(text("SELECT DISTINCT quote_date FROM stock_quote_snapshots WHERE quote_date BETWEEN :start AND :end ORDER BY quote_date DESC"),
                             {"start":args.start_date,"end":args.end_date}).scalars().all()
        save_progress(root/"progress.json",state)
        if not args.write:
            return state
        key,secret = AccountRegistry.get().get_credentials("default")
        headers={"APCA-API-KEY-ID":key,"APCA-API-SECRET-KEY":secret}
        try:
            attempted = 0
            with verified_session() as http:
                for raw_day in days:
                    day = raw_day if isinstance(raw_day,date) else date.fromisoformat(raw_day)
                    _, close = get_nyse_session_bounds(day)
                    if close > datetime.now(timezone.utc)-timedelta(minutes=20):
                        raise MigrationBlocked("Session too recent for historical SIP")
                    manifest_path = root/"days"/(str(day)+".json")
                    manifest_path.parent.mkdir(exist_ok=True)
                    if manifest_path.exists():
                        symbols = json.loads(manifest_path.read_text())["symbols"]
                    else:
                        with engine.connect() as c:
                            symbols = c.execute(text("SELECT symbol FROM stock_quote_snapshots WHERE quote_date=:day AND "+LEGACY+" ORDER BY symbol"),{"day":day}).scalars().all()
                        atomic_json(manifest_path,{"day":str(day),"symbols":symbols})
                    for offset in range(0,len(symbols),args.chunk_size):
                        local = datetime.now(ZoneInfo("Europe/Paris"))
                        if (root/"STOP").exists() or 7 <= local.hour < 20 or time.monotonic()-started >= args.max_seconds:
                            state["status"] = "PAUSED_SAFE_WINDOW_OR_LIMIT"; return state
                        if shutil.disk_usage(root).free < 50*1024**3:
                            state["status"]="PAUSED_DISK_RESERVE"; return state
                        task_path = root/"tasks"/f"{day}-{offset:06}.json"
                        task_path.parent.mkdir(exist_ok=True)
                        if task_path.exists() and json.loads(task_path.read_text()).get("status")=="COMMITTED":
                            continue
                        chunk = symbols[offset:offset+args.chunk_size]
                        state["current"]={"day":str(day),"offset":offset,"symbols":len(chunk)}
                        save_progress(state_path,state)
                        stmt=text("SELECT * FROM stock_quote_snapshots WHERE quote_date=:day AND symbol IN :symbols AND "+LEGACY).bindparams(bindparam("symbols",expanding=True))
                        with engine.connect() as c:
                            original=[dict(r) for r in c.execute(stmt,{"day":day,"symbols":chunk}).mappings()]
                        targets=[r["symbol"] for r in original]
                        selected=fetch_last_quotes(http,targets,day,headers,root,state,args.pause) if targets else {}
                        rows,invalid=replacement_rows(selected,day)
                        backup=root/"before"/f"{day}-{offset:06}-{datetime.now(timezone.utc).strftime('%H%M%S%f')}.json.gz"
                        backup_hash=save_gzip(backup,original)
                        with engine.begin() as c:
                            replaced=c.execute(UPDATE,rows).rowcount if rows else 0
                        missing=sorted(set(targets)-set(selected))
                        task={"status":"COMMITTED","rows_replaced":replaced,"missing":missing,"invalid":invalid,
                              "backup":str(backup),"backup_sha256":backup_hash,"day":str(day),"targets":len(targets)}
                        atomic_json(task_path,task)  # checkpoint only after SQL commit
                        attempted += 1
                        state["tranches_done"]+=1;state["rows_replaced"]+=replaced
                        state["rows_missing"]+=len(missing);state["rows_invalid"]+=len(invalid)
                        save_progress(state_path,state)
                        LOG.info("SIP migration day=%s chunk=%s replaced=%s missing=%s invalid=%s total_replaced=%s",
                                 day,offset,replaced,len(missing),len(invalid),state["rows_replaced"])
                        if args.max_tasks and attempted>=args.max_tasks:
                            state["status"]="PAUSED_TASK_LIMIT"; return state
            state["status"]="PARTIAL_UNRESOLVED" if state["rows_missing"] or state["rows_invalid"] else "COMPLETED"
            return state
        except Exception as exc:
            state.update(status="BLOCKED",error_type=type(exc).__name__,error=str(exc) if isinstance(exc,MigrationBlocked) else "Technical failure; no fallback or publication")
            raise
        finally:
            state["updated_at_utc"]=datetime.now(timezone.utc).isoformat()
            atomic_json(state_path,state);atomic_json(root/"report.json",state)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date",type=date.fromisoformat,default=date(2020,7,27))
    parser.add_argument("--end-date",type=date.fromisoformat,default=date(2026,10,16))
    parser.add_argument("--output",required=True)
    parser.add_argument("--write",action="store_true")
    parser.add_argument("--chunk-size",type=int,default=500)
    parser.add_argument("--pause",type=float,default=.5)
    parser.add_argument("--max-seconds",type=float,default=21600)
    parser.add_argument("--max-tasks",type=int)
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    print(json.dumps(run(parser.parse_args()),default=str))
