"""Durable frozen LONG campaigns; CAS versions + unique active account/symbol.

No table or state is created merely by importing or leaving the feature off.
Never delete history to allow a retry. Ambiguous submissions remain reserved.
"""
import json
import hashlib
from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.mysql import LONGTEXT

metadata = MetaData()
campaigns = Table('execution_winner_campaigns', metadata,
    Column('campaign_id', String(64), primary_key=True),
    Column('active_key', String(190), unique=True, nullable=True),
    Column('account_id', String(64), nullable=False), Column('broker_mode', String(12), nullable=False),
    Column('symbol', String(32), nullable=False), Column('risk_run_id', String(128), nullable=False),
    Column('version', Integer, nullable=False), Column('state_json', Text().with_variant(LONGTEXT(), 'mysql'), nullable=False),
    Column('updated_at_utc', String(40), nullable=False))

account_guards = Table('execution_winner_account_guards', metadata,
    Column('account_id', String(64), primary_key=True), Column('broker_mode', String(12), primary_key=True),
    Column('version', Integer, nullable=False),
    Column('state_json', Text().with_variant(LONGTEXT(), 'mysql'), nullable=False),
    Column('updated_at_utc', String(40), nullable=False))


class WinnerCampaignStore:
    def __init__(self, engine):
        self.engine = engine

    def exists(self):
        return inspect(self.engine).has_table(campaigns.name)

    def ensure(self):
        if self.engine.dialect.name == 'mysql' and self.engine.url.database != 'alpha_trade':
            raise ValueError('Winner campaigns require alpha_trade US; FR/CN forbidden')
        metadata.create_all(self.engine)

    def create(self, state, account, broker_mode, risk_run_id):
        if broker_mode not in ('paper', 'live') or not account or not risk_run_id:
            raise ValueError('Explicit account, mode and risk approval required')
        self.ensure()
        state.update(account_id=account, broker_mode=broker_mode, risk_run_id=risk_run_id)
        row = dict(campaign_id=state['campaign_id'], active_key=f'{account}|{broker_mode}|{state["symbol"]}',
            account_id=account, broker_mode=broker_mode, symbol=state['symbol'], risk_run_id=risk_run_id,
            version=0, state_json=json.dumps(state, allow_nan=False, default=str), updated_at_utc=datetime.now(UTC).isoformat())
        try:
            with self.engine.begin() as conn:
                conn.execute(campaigns.insert(), row)
        except IntegrityError:
            return False
        return True

    def rows(self, account=None, broker_mode=None, active_only=True):
        if not self.exists():
            return []
        query = select(campaigns)
        if active_only:
            query = query.where(campaigns.c.active_key.is_not(None))
        if account is not None:
            query = query.where(campaigns.c.account_id == account)
        if broker_mode is not None:
            query = query.where(campaigns.c.broker_mode == broker_mode)
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [dict(state=json.loads(r['state_json']), version=r['version']) for r in rows]

    def by_parent(self, parent):
        return next((r for r in self.rows() if parent in r['state'].get('parents', {})), None)

    def get(self, campaign_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(campaigns.c.state_json, campaigns.c.version).where(
                campaigns.c.campaign_id == campaign_id)).mappings().first()
        return dict(state=json.loads(row['state_json']), version=row['version']) if row else None

    def get_guard(self, account, mode):
        with self.engine.connect() as conn:
            row = conn.execute(select(account_guards).where(account_guards.c.account_id == account,
                account_guards.c.broker_mode == mode)).mappings().first()
        return (json.loads(row['state_json']), row['version']) if row else (None, None)

    def save_guard(self, account, mode, state, version):
        # Caller holds the same account lock as execution / campaign purchases.
        values = dict(state_json=json.dumps(state, allow_nan=False, default=str),
            updated_at_utc=datetime.now(UTC).isoformat())
        with self.engine.begin() as conn:
            if version is None:
                conn.execute(account_guards.insert(), dict(account_id=account, broker_mode=mode, version=0, **values))
                return 0
            result = conn.execute(update(account_guards).where(account_guards.c.account_id == account,
                account_guards.c.broker_mode == mode, account_guards.c.version == version).values(version=version+1, **values))
            if result.rowcount != 1:
                raise RuntimeError('Risk state changed concurrently; campaign purchase forbidden')
        return version+1

    def by_risk(self, account, mode, risk, symbol):
        return next((r for r in self.rows(account, mode) if r['state']['risk_run_id'] == risk
            and r['state']['symbol'] == symbol), None)

    def save(self, state, version):
        with self.engine.begin() as conn:
            previous = conn.execute(select(campaigns.c.state_json, campaigns.c.version).where(
                campaigns.c.campaign_id == state['campaign_id'])).mappings().first()
            if previous is None or previous['version'] != version:
                raise RuntimeError('Campaign changed concurrently; broker submission forbidden')
            old = json.loads(previous['state_json'])
            # A trailing update or restart must not change the risk admission.
            for key in ('campaign_id', 'symbol', 'account_id', 'broker_mode', 'risk_run_id',
                    'policy', 'policy_amendments', 'account_policy', 'entry_policy', 'full_quantity', 'initial_quantity', 'risk_budget', 'target',
                    'exec_run_id', 'signal_date', 'created_at', 'earliest_entry_open', 'entry_expires_at'):
                if json.dumps(old.get(key), sort_keys=True, default=str) != json.dumps(state.get(key), sort_keys=True, default=str):
                    raise ValueError(f'Frozen campaign field cannot change: {key}')
            for key in ('first_fill_at', 'due_open'):
                if old.get(key) is not None and old.get(key) != state.get(key):
                    raise ValueError(f'First actual fill freezes {key}; reinforcement cannot reset it')
            if old['status'] in ('CLOSED', 'CANCELED', 'EXPIRED') and state['status'] != old['status']:
                raise ValueError('Terminal campaign cannot be reactivated')
            if state['status'] in ('CLOSED', 'CANCELED', 'EXPIRED') and any(l['remaining'] > 0 for l in state['lots']):
                raise ValueError('Held lots prevent campaign release')
            if any(l['remaining'] < 0 or l['remaining'] > l['quantity'] for l in state['lots']):
                raise ValueError('Invalid remaining quantity')
            if len(state.get('operations', [])) < len(old.get('operations', [])):
                raise ValueError('Order operation history cannot be removed')
            changed = conn.execute(update(campaigns).where(campaigns.c.campaign_id == state['campaign_id'],
                campaigns.c.version == version).values(version=version+1,
                active_key=None if state['status'] in ('CLOSED', 'EXPIRED', 'CANCELED') else f'{state["account_id"]}|{state["broker_mode"]}|{state["symbol"]}',
                state_json=json.dumps(state, allow_nan=False, default=str), updated_at_utc=datetime.now(UTC).isoformat())).rowcount
        if changed != 1:
            raise RuntimeError('Campaign changed concurrently; broker submission forbidden')
        return version+1

    def disable_trailing(self, campaign_id, version, *, account_id, authorization,
            protection_proof_sha256):
        """Explicit audited PAPER amendment; only trailing -> None may change.

        Caller holds the canonical account lock and verifies standing broker
        protections first. Current lot stops (including earlier ratchets), TP,
        quantities, deadlines and all other frozen admission terms are retained.
        Ordinary save() still rejects arbitrary policy or audit mutations.
        """
        if (not isinstance(authorization,str) or not authorization.strip()
                or not isinstance(protection_proof_sha256,str) or len(protection_proof_sha256)!=64
                or any(c not in '0123456789abcdef' for c in protection_proof_sha256)):
            raise ValueError('Explicit authorization and protection evidence required')
        from common.winner_pyramiding import WinnerPyramidingConfig
        with self.engine.begin() as conn:
            row=conn.execute(select(campaigns).where(campaigns.c.campaign_id==campaign_id)
                .with_for_update()).mappings().first()
            if row is None or row['version']!=version:
                raise RuntimeError('Campaign changed; trailing amendment refused')
            old=json.loads(row['state_json'])
            if (old['broker_mode']!='paper' or old['account_id']!=account_id or old['status']!='OPEN'
                    or not any(l['remaining']>0 for l in old['lots'])
                    or any(o['status'] in ('RESERVED','UNKNOWN','SUBMITTED') for o in old['operations'])):
                raise ValueError('Open, reconciled PAPER campaign for exact account required')
            if old['policy']['trailing_stop_pct'] is None:
                return dict(changed=False,version=version,state=old)
            new=deepcopy(old)
            new['policy']['trailing_stop_pct']=None
            WinnerPyramidingConfig(**new['policy'])
            stamp=datetime.now(UTC).isoformat()
            policy_hash=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
            new.setdefault('policy_amendments',[]).append(dict(kind='DISABLE_TRAILING',
                previous_trailing_stop_pct=old['policy']['trailing_stop_pct'],trailing_stop_pct=None,
                observed_at=stamp,authorization=authorization.strip(),
                previous_policy_sha256=policy_hash(old['policy']),new_policy_sha256=policy_hash(new['policy']),
                protection_proof_sha256=protection_proof_sha256))
            result=conn.execute(update(campaigns).where(campaigns.c.campaign_id==campaign_id,
                campaigns.c.version==version).values(version=version+1,
                state_json=json.dumps(new,allow_nan=False),updated_at_utc=stamp))
            if result.rowcount!=1:
                raise RuntimeError('Campaign changed; trailing amendment refused')
        return dict(changed=True,version=version+1,state=new)
