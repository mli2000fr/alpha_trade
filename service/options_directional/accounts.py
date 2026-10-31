"""Shared market selection, isolated PAPER consumer state, legacy default kept."""
import hashlib
import re

BINDING_PROTOCOL='options-account-binding-v2'


def account_key(account_id):
    if not isinstance(account_id,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',account_id):
        raise ValueError('Identifiant de compte explicite invalide')
    return account_id


def require_paper_account(account_id):
    account_id=account_key(account_id)
    from service.alpaca.accounts import AccountRegistry
    account=AccountRegistry.get().resolve(account_id)
    if account.account_id!=account_id or account.mode!='paper':
        raise ValueError('Filtre options : compte déclaré PAPER requis ; LIVE interdit')
    return account_id


def consumer_directory(run_id,account_id='default',*,root=None,create=False):
    from .store import directory
    account_id=account_key(account_id)
    base=directory(run_id,root)
    # Never move, reset or shadow old default claims/bindings. Existing
    # executions remain consumed at their original paths.
    folder=base if account_id=='default' else base/'accounts'/(
        'account-'+account_id+'-'+hashlib.sha256(account_id.encode()).hexdigest()[:12])
    if not folder.resolve().is_relative_to(base.resolve()):
        raise ValueError('Dossier compte hors analyse options')
    if create:
        folder.mkdir(parents=True,exist_ok=True)
    return folder


def shared_qualified(run_id,*,account_id='default',capital_preset_key=None,**context):
    from .store import qualified
    account_key(account_id)
    # Account/preset here describe the consumer, not the sealed market input.
    # Its archived universe preset is retained and never replaced for sizing.
    return qualified(run_id,account_id=None,**context)


def shared_latest_matching(*,account_id='default',capital_preset_key=None,**context):
    from .store import latest_matching
    account_key(account_id)
    return latest_matching(account_id=None,**context)


def validate_risk_binding(report,binding,summary,account_id):
    from .store import digest
    account_id=account_key(account_id)
    if (binding.get('account_id','default')!=account_id
            or summary.get('account_id','default')!=account_id
            or binding.get('report_sha256')!=digest(report)
            or binding.get('summary_sha256')!=digest(summary)
            or binding.get('risk_run_id')!=summary.get('run_id') or not summary.get('run_id')
            or summary.get('options_filter_run_id')!=report['run_id']
            or summary.get('run_mode')!='paper' or summary.get('dry_run')):
        raise ValueError('Lien risque/options hors compte ou altéré')
    if account_id!='default' and binding.get('binding_protocol')!=BINDING_PROTOCOL:
        raise ValueError('Lien risque multicomptes non qualifié')
