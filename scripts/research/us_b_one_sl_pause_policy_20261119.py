"""Research-only entry veto after an actually executed STOP/STOP_GAP."""
from contextlib import contextmanager
from unittest.mock import patch
import pandas as pd


class StopPause:
    def __init__(self, sessions, pause=100, enabled=True):
        self.sessions = list(sessions)
        self.index = {day:i for i,day in enumerate(self.sessions)}
        self.pause, self.enabled = pause, enabled
        self.pending, self.seen, self.until = [], set(), {}
        self.triggers, self.decisions, self.vetoes = [], [], []
        self.book = None

    @staticmethod
    def aware(stamp):
        value = pd.Timestamp(stamp)
        if value.tzinfo is None:
            raise ValueError('Pause availability/cutoff must be timezone aware')
        return value

    def observe(self, symbol, reason, stamp, campaign):
        stamp = self.aware(stamp)
        if campaign in self.seen:
            raise ValueError('Duplicate completed campaign')
        self.seen.add(campaign)
        if reason in ('STOP','STOP_GAP'):
            self.pending.append((stamp,str(symbol),str(campaign),reason))

    def blocked(self, cutoff):
        cutoff = self.aware(cutoff)
        ready = sorted([r for r in self.pending if r[0] <= cutoff])
        self.pending = [r for r in self.pending if r[0] > cutoff]
        for stamp,symbol,campaign,reason in ready:
            day = stamp.tz_convert('America/New_York').date()
            i = self.index[day]
            resume = i+self.pause+1
            if resume >= len(self.sessions):
                raise ValueError('Insufficient calendar for pause expiry')
            self.until[symbol] = max(self.until.get(symbol,0),resume)
            self.triggers.append(dict(symbol=symbol,campaign_id=campaign,reason=reason,
                known_at=stamp.isoformat(),trigger_session=str(day),pause_sessions=self.pause,
                resume_session=str(self.sessions[self.until[symbol]])))
        day = cutoff.tz_convert('America/New_York').date()
        blocked = {s for s,i in self.until.items() if self.index[day] < i}
        return blocked if self.enabled else set()

    def select(self, signal_day, rows, cutoff):
        blocked = self.blocked(cutoff)
        kept = rows.loc[~rows.symbol.isin(blocked),'symbol'].tolist()
        excluded = rows.loc[rows.symbol.isin(blocked),'symbol'].tolist()
        self.decisions.append(dict(signal_day=str(signal_day),decision_at=str(cutoff),
                                   excluded=excluded,selected=kept,paused=sorted(blocked)))
        return dict(incomplete=False,selected=kept)

    @contextmanager
    def installed(self):
        from backtesting.winner_intraday import ReplayBroker
        from execution_engine import winner_live_risk
        native_init,native_close = ReplayBroker.__init__,ReplayBroker.close
        native_concentration = winner_live_risk.concentration_allowed
        ledger = self

        def init(book,*args,**kwargs):
            native_init(book,*args,**kwargs)
            ledger.book = book

        def close(book,*args,**kwargs):
            before = len(book.trades)
            result = native_close(book,*args,**kwargs)
            for t in book.trades[before:]:
                if any(l['remaining'] for l in book.lots.values() if l['campaign_id']==t['campaign_id']):
                    raise ValueError('Partial exit unsupported by fixed full-position protocol')
                stamp = pd.Timestamp(book.now)
                # Intrabar STOP is observable only at the close of its 5m bar.
                if t['exit_reason']=='STOP':
                    stamp += pd.Timedelta(minutes=5)
                ledger.observe(t['symbol'],t['exit_reason'],stamp,t['campaign_id'])
            return result

        def concentration(fills,cfg,symbol,day,kind):
            native = native_concentration(fills,cfg,symbol,day,kind)
            paused = symbol in ledger.blocked(ledger.book.now)
            if paused:
                ledger.vetoes.append(dict(time=str(ledger.book.now),symbol=symbol,kind=kind))
            return native and not paused

        with patch.object(ReplayBroker,'__init__',init),patch.object(ReplayBroker,'close',close),\
                patch.object(winner_live_risk,'concentration_allowed',concentration):
            yield
