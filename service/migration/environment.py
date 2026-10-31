"""Export application variables only; values never appear in public reports."""
import ast
import os
from pathlib import Path
import re

NAME=re.compile(r'^[A-Z][A-Z0-9_]{2,100}$')
EXCLUDED={'PATH','HOME','USERPROFILE','USERNAME','COMPUTERNAME','TEMP','TMP','SYSTEMROOT',
    'APPDATA','LOCALAPPDATA','PROGRAMFILES','PROGRAMDATA','VIRTUAL_ENV','PYTHONPATH','PYTHONHOME','CODEX_HOME',
    'WINDIR','OS','COMSPEC','PATHEXT','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE','PROCESSOR_IDENTIFIER'}
PREFIXES=('ALPACA_','EODHD_','TUSHARE_','TRADING212_','FINNHUB_','OPENAI_','DEEPSEEK_',
          'ALPHA_TRADE_','TELEGRAM_','FRED_','LOGIN_DB','PASSWORD_DB','DB_HOST','DB_NAME')


def discover_names(root,files):
    names={'LOGIN_DB','PASSWORD_DB','ALPHA_TRADE_AUDIT_HMAC_KEY','ALPHA_TRADE_AUDIT_KEY_VERSION'}
    for relative in files:
        path=Path(root)/relative
        if path.suffix not in ('.py','.yaml','.yml','.ps1','.json','.toml','.env'):continue
        try:source=path.read_text(encoding='utf-8-sig')
        except (UnicodeError,OSError):continue
        names.update(re.findall(r'\$\{([A-Z][A-Z0-9_]+)\}|\$env:([A-Z][A-Z0-9_]+)',source))
        names={item for value in names for item in (value if isinstance(value,tuple) else (value,)) if item}
        names.update(re.findall(r'\b\w*_env\s*:\s*[\x22\x27]?([A-Z][A-Z0-9_]+)',source))
        if path.suffix!='.py':continue
        try:tree=ast.parse(source)
        except SyntaxError:continue
        constants={}
        for node in ast.walk(tree):
            if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
                for target in node.targets:
                    if isinstance(target,ast.Name):constants[target.id]=node.value.value
        def name(node):
            return node.value if isinstance(node,ast.Constant) else constants.get(node.id) if isinstance(node,ast.Name) else None
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and node.args:
                func=ast.unparse(node.func)
                if 'env' in func.rsplit('.',1)[-1].lower() or 'environ.' in func:
                    candidate=name(node.args[0])
                    if isinstance(candidate,str):names.add(candidate)
            if isinstance(node,ast.Subscript) and ast.unparse(node.value).endswith('environ'):
                candidate=name(node.slice)
                if isinstance(candidate,str):names.add(candidate)
    return {n for n in names if NAME.fullmatch(n) and n not in EXCLUDED}


def registry_values(scope):
    if os.name!='nt':return {}
    import winreg
    hive,path=(winreg.HKEY_CURRENT_USER,'Environment') if scope=='User' else (
        winreg.HKEY_LOCAL_MACHINE,r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')
    values={}
    try:
        with winreg.OpenKey(hive,path) as handle:
            for i in range(winreg.QueryInfoKey(handle)[1]):
                name,value,_=winreg.EnumValue(handle,i)
                if isinstance(value,str):values[name]=value
    except FileNotFoundError:pass
    return values


def capture(root,files,*,process=None,user=None,machine=None):
    process=dict(os.environ if process is None else process)
    user=registry_values('User') if user is None else user
    machine=registry_values('Machine') if machine is None else machine
    names=discover_names(root,files)
    effective={**machine,**user,**process}
    names.update(n for n in effective if n.startswith(PREFIXES) and NAME.fullmatch(n) and n not in EXCLUDED)
    selected={n:effective[n] for n in sorted(names) if n in effective}
    def external_path(n):
        if n not in selected:return False
        path=Path(selected[n])
        return path.is_absolute() and not path.is_relative_to(Path(root).absolute())
    metadata=[dict(name=n,present=n in selected,external_path=external_path(n),
        scope='Process' if n in process else 'User' if n in user else 'Machine' if n in machine else 'MISSING') for n in sorted(names)]
    return dict(values=selected,variables=metadata)


def write_user(values):
    """Only explicitly selected application names, never PATH/system variables."""
    if os.name!='nt':raise ValueError('Restauration des variables utilisateur réservée à Windows')
    import winreg
    if any(not NAME.fullmatch(n) or n in EXCLUDED for n in values):raise ValueError('Variable système interdite')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,'Environment') as handle:
        for name,value in values.items():
            if value is None:
                try:winreg.DeleteValue(handle,name)
                except FileNotFoundError:pass
            else:winreg.SetValueEx(handle,name,0,winreg.REG_SZ,str(value))
    # New processes must reload the environment; running interpreters retain
    # their old values. Never silently mutate a running broker session.


def rebase(values,source_root,target_root):
    result={}
    source=source_root.rstrip('/\\');target=str(target_root).rstrip('/\\')
    for name,value in values.items():
        if name in EXCLUDED or not NAME.fullmatch(name):raise ValueError('Variable environnement non autorisée')
        if value.casefold()==source.casefold() or value.casefold().startswith(source.casefold()) and value[len(source):len(source)+1] in ('/','\\'):
            value=target+value[len(source):]
        result[name]=value
    return result
