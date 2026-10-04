"""Rejeu LONG FR de recherche, sans SQL, fitting ou promotion de serving.

Inputs are an explicitly qualified execution tape, NOT forward-label-filtered
candidates. Encountered unknown execution evidence aborts the replay, never
silently removes a losing candidate. Decimal cash; prices remain unadjusted.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from service.fr.execution_costs import execution_costs, resolve_liability


class ReplayBlocked(ValueError):
    """Incomplete evidence: partial ledgers are diagnostic, not performance."""

    def __init__(self, message, ledger):
        super().__init__(message)
        self.ledger = ledger


def amount(value):
    value = Decimal(str(value))
    if not value.is_finite() or value < 0:
        raise ValueError("Montant non négatif fini requis")
    return value


def replay(tape: dict, cost_profile: dict, eligibility_path, *, stress_multiplier=Decimal(1)) -> dict:
    """Independent cash portfolio per policy/fold; explicit settlement evidence.

    Schema described in doc/fr/sprint_12b_moteur_rejeu_economique.md. No automatic
    T+2 from an exchange calendar. Tape must contain all open sessions until exit
    and dividend payment. No shorts, fractional shares, stacking or daily resets.
    """
    if tape.get("schema_version") != 1 or tape.get("market_code") != "FR_EQ" or tape.get("currency") != "EUR":
        raise ValueError("Tape FR/EUR version 1 requis")
    if tape.get("canonical_writes_enabled") is not False or tape.get("serving_enabled") is not False:
        raise ValueError("Recherche uniquement")
    sessions = tape["sessions"]
    if not sessions or sessions != sorted(set(sessions)):
        raise ValueError("Sessions uniques ordonnées requises")
    if any(date.fromisoformat(d) > date(2025, 12, 31) for d in sessions):
        raise ValueError("Performance 2026 réservée")
    if not tape.get("calendar_evidence"):
        raise ValueError("Preuve du calendrier de séances requise")
    horizon, maximum = tape["horizon"], tape["max_positions"]
    if type(horizon) is not int or horizon < 1 or type(maximum) is not int or maximum < 1:
        raise ValueError("Horizon/capacité entiers positifs requis")
    cash = amount(tape["initial_equity"])
    if not cash:
        raise ValueError("Capital positif requis")
    initial = cash
    instruments = tape["instruments"]
    if len({i["isin"] for i in instruments.values()}) != len(instruments):
        raise ValueError("Plusieurs identités pour un ISIN : netting non supporté")
    # Economic coverage is input evidence, never a derived ex-ante selection gate.
    coverage = tape["corporate_action_coverage"]
    candidates = {}
    seen = set()
    for item in tape["candidates"]:
        day, uid = item["session"], item["uid"]
        if (day, uid) in seen or day not in sessions or uid not in instruments:
            raise ValueError("Candidat dupliqué/hors calendrier ou identité absente")
        seen.add((day, uid))
        available = datetime.fromisoformat(item["available_at"])
        decision = datetime.fromisoformat(tape["decision_at"][day])
        entry = datetime.fromisoformat(tape["entry_at"][day])
        if available.tzinfo is None or decision.tzinfo is None or entry.tzinfo is None or available > decision or decision > entry:
            raise ValueError("Candidat non disponible à la décision")
        rank = item["rank"]
        if type(rank) is not int or rank < 1:
            raise ValueError("Rang causal entier positif requis")
        candidates.setdefault(day, []).append(item)
    for group in candidates.values():
        if len({c["rank"] for c in group}) != len(group):
            raise ValueError("Rangs ambigus")
    events = tape["events"]
    if len({e["id"] for e in events}) != len(events):
        raise ValueError("Événement dupliqué")
    by_day = {}
    for e in events:
        if e["uid"] not in instruments or e["session"] not in sessions:
            raise ValueError("Événement hors tape/identité")
        by_day.setdefault(e["session"], []).append(e)
    # A dividend and split on the same date require a qualified event ordering;
    # this v1 refuses to guess the unit used for the dividend amount.
    if len({(e["session"], e["uid"]) for e in events}) != len(events):
        raise ValueError("Plusieurs événements instrument/jour : ordre non qualifié")
    ledger = {"orders": [], "cash_movements": [], "equity": [], "receivables": [], "trades": []}
    positions, claims = {}, []
    totals = {k: Decimal(0) for k in ("commission", "spread", "slippage", "taxes")}

    def block(message):
        raise ReplayBlocked(message, ledger)

    def price(day, uid, field):
        bar = tape["bars"].get(day, {}).get(uid)
        if not bar or bar.get("economic_verified") is not True or not bar.get("evidence"):
            block(f"Prix non qualifié {uid}/{day}")
        if bar.get("tradable") is not True:
            block(f"Suspension/statut non exécutable {uid}/{day}")
        try:
            result = amount(bar[field])
        except (ValueError, KeyError, InvalidOperation, TypeError):
            block(f"Prix invalide {uid}/{day}/{field}")
        if not result:
            block(f"Prix nul {uid}/{day}")
        return result

    def fees(day, uid, side, qty, reference):
        if side == "BUY":
            settlement = tape["settlements"].get(day)
            if not settlement or not settlement.get("evidence"):
                block(f"Règlement non qualifié {day}")
            settlement_day = date.fromisoformat(settlement["date"])
            if settlement_day < date.fromisoformat(day):
                block(f"Règlement avant transaction {day}")
            if settlement_day > date(2025, 12, 31):
                block(f"Règlement fiscal hors périmètre qualifié {day}")
            try:
                liability = resolve_liability(eligibility_path, isin=instruments[uid]["isin"],
                                              ticker=instruments[uid]["ticker"], settlement_date=settlement_day)
            except ValueError as exc:
                block(str(exc))
        else:
            settlement_day, liability = None, None
        return execution_costs(cost_profile, side=side, quantity=qty, reference_price=reference,
                               settlement_date=settlement_day, issuer_liability=liability,
                               stress_multiplier=stress_multiplier)

    def fill(day, uid, side, qty, reference, costs):
        nonlocal cash
        notional = reference * qty
        delta = (-notional if side == "BUY" else notional) - costs["total"]
        cash += delta
        for key in totals:
            totals[key] += costs[key]
        order = {"session": day, "uid": uid, "side": side, "quantity": qty,
                 "reference_price": reference, "notional": notional, **costs, "cash_after": cash}
        ledger["orders"].append(order)
        ledger["cash_movements"].append({"session": day, "uid": uid, "kind": side, "amount": delta})
        return order

    for index, day in enumerate(sessions):
        # Corporate actions at start of session apply only to existing positions.
        for event in by_day.get(day, []):
            uid = event["uid"]
            if uid not in positions:
                continue
            if event.get("verified") is not True or not event.get("evidence"):
                block(f"Événement non qualifié {event['id']}")
            p = positions[uid]
            if event["kind"] == "SPLIT":
                numerator, denominator = event["numerator"], event["denominator"]
                if type(numerator) is not int or type(denominator) is not int or min(numerator, denominator) <= 0:
                    block("Ratio split invalide")
                if p["quantity"] * numerator % denominator:
                    block("Split avec rompus : cash-in-lieu non implémenté")
                p["quantity"] = p["quantity"] * numerator // denominator
            elif event["kind"] == "DIVIDEND":
                payment = event["payment_session"]
                if event["currency"] != "EUR" or payment < day or payment not in sessions:
                    block("Dividende devise/date de paiement non supportée")
                claim = {"id": event["id"], "uid": uid, "ex_session": day, "payment_session": payment,
                         "amount": p["quantity"] * amount(event["cash_per_share"]), "paid": False}
                claims.append(claim)
                p["dividend_entitlement"] += claim["amount"]
                ledger["receivables"].append(claim)
            else:
                block(f"Opération complexe non supportée {event['kind']}")
        for claim in claims:
            if not claim["paid"] and claim["payment_session"] == day:
                cash += claim["amount"]
                claim["paid"] = True
                ledger["cash_movements"].append({"session": day, "uid": claim["uid"],
                                                "kind": "DIVIDEND_PAYMENT", "amount": claim["amount"]})
        # Opening budget excludes all closing sale proceeds. Cash only: no margin.
        opened = {}
        for uid, p in positions.items():
            opened[uid] = price(day, uid, "open") * p["quantity"]
        opening_equity = cash + sum(opened.values()) + sum(c["amount"] for c in claims if not c["paid"])
        ticket_budget = min(opening_equity / maximum, cash)
        for item in sorted(candidates.get(day, []), key=lambda c: c["rank"]):
            uid = item["uid"]
            reason = "ALREADY_HELD" if uid in positions else "CAPACITY" if len(positions) >= maximum else None
            if reason:
                ledger["orders"].append({"session": day, "uid": uid, "side": "SKIP", "reason": reason})
                continue
            # Recorded outcome of the opening attempt, not an ex-ante universe
            # filter. No cash/fees/position: future CA/tax need not be guessed
            # for an order which provably did not execute. Unknowns still block.
            bar = tape["bars"].get(day, {}).get(uid)
            opening = (bar or {}).get("opening_execution", {})
            if opening.get("status") == "NO_OPENING_TRANSACTION":
                if (not bar or bar.get("economic_verified") is not True or not bar.get("evidence")
                        or not opening.get("evidence") or bar.get("open") is not None):
                    block(f"Absence d'ouverture non qualifiée {uid}/{day}")
                ledger["orders"].append({"session": day, "uid": uid, "side": "REJECT",
                                         "reason": "NO_OPENING_TRANSACTION", "rank": item["rank"],
                                         "evidence": opening["evidence"], "cash_after": cash})
                continue
            if index + horizon >= len(sessions):
                block(f"Calendrier incomplet jusqu'à sortie {uid}/{day}")
            ca = coverage.get(uid)
            exit_day = sessions[index + horizon]
            if not ca or ca.get("verified") is not True or not ca.get("evidence") or ca["from"] > day or ca["to"] < exit_day:
                block(f"Couverture opérations sur titres non qualifiée {uid}/{day}")
            reference = price(day, uid, "open")
            budget = min(ticket_budget, cash)
            qty = int(budget // reference)
            costs = None
            while qty > 0:
                costs = fees(day, uid, "BUY", qty, reference)
                if reference * qty + costs["total"] <= budget:
                    break
                qty -= 1
            if qty == 0:
                ledger["orders"].append({"session": day, "uid": uid, "side": "SKIP", "reason": "INSUFFICIENT_CASH"})
                continue
            order = fill(day, uid, "BUY", qty, reference, costs)
            positions[uid] = {"entry_session": day, "exit_session": exit_day, "quantity": qty,
                              "entry_notional": order["notional"], "entry_cost": costs["total"],
                              "dividend_entitlement": Decimal(0)}
        for uid, p in list(positions.items()):
            close = price(day, uid, "close")
            if p["exit_session"] == day:
                costs = fees(day, uid, "SELL", p["quantity"], close)
                order = fill(day, uid, "SELL", p["quantity"], close, costs)
                gross = order["notional"] - p["entry_notional"] + p["dividend_entitlement"]
                ledger["trades"].append({"uid": uid, "entry_session": p["entry_session"], "exit_session": day,
                                         "gross_pnl": gross, "net_pnl": gross - p["entry_cost"] - costs["total"]})
                del positions[uid]
        exposure = sum(price(day, uid, "close") * p["quantity"] for uid, p in positions.items())
        receivable = sum(c["amount"] for c in claims if not c["paid"])
        equity = cash + exposure + receivable
        if cash < 0:
            block("Cash négatif : invariant violé")
        ledger["equity"].append({"session": day, "cash": cash, "market_value": exposure,
                                 "dividend_receivable": receivable, "equity": equity,
                                 "gross_exposure_ratio": exposure / equity if equity else Decimal(0),
                                 "positions": len(positions)})
    if positions or any(not c["paid"] for c in claims):
        block("Positions/créances non liquidées en fin de tape")
    net = cash - initial
    if sum(t["net_pnl"] for t in ledger["trades"]) != net:
        block("Réconciliation cash/trades incorrecte")
    return {"status": "COMPLETED_ASSUMED_COST_RESEARCH", "initial_equity": initial, "final_equity": cash,
            "net_pnl": net, "gross_pnl": net + sum(totals.values()), "costs": totals,
            "trades": len(ledger["trades"]), "ledger": ledger,
            "canonical_writes": False, "serving_enabled": False, "economic_go_allowed": False}
