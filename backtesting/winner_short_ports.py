"""Validated replay-only integration ports, not a live execution adapter."""
from backtesting.winner_short import is_short,short_plan,ShortReplayCoordinator
from execution_engine.winner_runtime import WinnerCampaignRuntime
from execution_engine.winner_plans import stage_targets


class ReplayCoordinator:
    """Same calling interface as LONG runtime, exclusively for the local book."""
    def __init__(self,store,repo,book,config,**kwargs):
        if not getattr(book,'is_winner_replay',False):raise ValueError('Mixed runtime requires the isolated replay book')
        self.store,self.repo,self.book,self.config,self.kwargs=store,repo,book,config,kwargs

    def run(self,records):
        return coordinate(records,self.store,self.repo,self.book,self.config,**self.kwargs)


def coordinate(records,store,repo,book,config,**kwargs):
    """One capital pool, incoming selection order, existing LONG runtime."""
    if not any(is_short(row['state']) for row in records):
        return WinnerCampaignRuntime(store,repo,book,config,**kwargs).run(records)
    result=dict(winner_details=[],winner_failures=0)
    for row in records:
        runtime=(ShortReplayCoordinator(store,book,config,**kwargs) if is_short(row['state']) else
                 WinnerCampaignRuntime(store,repo,book,config,**kwargs))
        observed=runtime.run([row]);result['winner_details'].extend(observed['winner_details'])
        result['winner_failures']+=observed['winner_failures']
    return result


def stage(targets,store,config,*,now,calendar):
    for target in targets:
        if str(target.side).lower() in ('short','sell'):
            state=short_plan(target,config,now=now,calendar=calendar)
            store.create(state,config.resolved_account_id,config.broker_mode,target.risk_run_id)
        else:stage_targets(store,[target],config,'winner-replay',now=now,calendar=calendar)


def concentration_allowed(book,cfg,symbol,today,kind):
    from risk_management.concentration import SymbolTradeTracker,ConsecutiveLossTracker
    trades=SymbolTradeTracker(cfg.concentration_max_trades_per_symbol,cfg.concentration_window_calendar_days)
    losses=ConsecutiveLossTracker(cfg.concentration_max_consecutive_losses,cfg.concentration_blacklist_duration_days)
    for key,lot in sorted(book.lots.items(),key=lambda x:x[1]['entry_time']):
        if lot['symbol']!=symbol or lot.get('side')!='short':continue
        trades.record(symbol,lot['entry_time'].date(),side='sell')
        exits=[t for t in book.trades if t['campaign_id']==lot['campaign_id'] and t['entry_date']==lot['entry_time']]
        if not lot['remaining'] and exits:
            losses.record(symbol,sum(t['pnl'] for t in exits),max(t['exit_date'] for t in exits).date(),side='sell')
    return (kind=='ADD' or trades.allow_entry(symbol,today,side='sell')) and not losses.is_blacklisted(symbol,today,side='sell')


def close_campaign(record,store,book,config,stamp,event_id):
    coordinator=ShortReplayCoordinator(store,book,config,market=lambda *_:{},risk=lambda *_:{},now=stamp)
    row=store.get(record['state']['campaign_id']);coordinator.state,coordinator.version=row['state'],row['version']
    coordinator.sync()
    quantity=sum(l['remaining'] for l in coordinator.state['lots'])
    position=next((p for p in book.positions() if p['symbol']==coordinator.state['symbol']),None)
    if quantity and (position is None or position['side']!='short' or position['qty']!=quantity):
        raise ValueError('SHORT liquidation quantity mismatch')
    coordinator.close('GLOBAL_DRAWDOWN')
    if any(l['remaining'] for l in coordinator.state['lots']):raise ValueError('SHORT global liquidation incomplete')
    coordinator.state['status']='CLOSED';coordinator.save()
    return quantity
