"""Enforced child-process isolation for read-only US simulations.

No broker/maintenance entry points. Shared SQL is read-only; Python application
file writes stay in the run workspace. Violations remain fatal if caught by a
best-effort helper. This is an application guard, not an OS security sandbox.
"""
from contextlib import contextmanager
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import sys

_ACTIVE = None
_AUDIT_INSTALLED = False


class IsolationViolation(RuntimeError):
    pass


def active():
    return _ACTIVE is not None


def local_path(*parts):
    if _ACTIVE is None:
        raise RuntimeError('No isolated replay active')
    return _ACTIVE.root.joinpath(*parts)


def readonly_run_options(kind, options):
    """Fail closed on unknown jobs; rebuilds/calibrations stay exclusive."""
    if kind!='run':return False
    from ihm.services.backtesting_runner import BacktestRunOptions
    if not isinstance(options,BacktestRunOptions):return False
    return (options.winner_enabled or
        options.ml_mode in ('auto','off') and options.sentiment_mode in ('auto','off')
        and options.ml_pit_strategy in ('auto','use-persisted'))


def read_statement(statement):
    """Restricted SQL grammar, never accepts stacked statements or SQL hints."""
    sql=str(statement).strip().rstrip(';').strip()
    if not sql or ';' in sql or '/*' in sql or '--' in sql or '#' in sql:
        return False
    # Literal contents and quoted identifiers are not SQL verbs.
    tokens=re.sub(r"'(?:''|\\.|[^'])*'|\"(?:\"\"|\\.|[^\"])*\"|`(?:``|[^`])*`",' VALUE ',sql).upper()
    normalized=' '.join(tokens.split())
    if re.fullmatch(r'SHOW CREATE (?:TABLE|VIEW) [A-Z0-9_. ]+',normalized):return True
    if re.fullmatch(r'SET (?:SESSION )?TRANSACTION (?:ISOLATION LEVEL REPEATABLE READ,? )?READ ONLY',normalized):
        return True
    if re.fullmatch(r'SET NAMES (?:UTF8MB4|UTF8|VALUE)(?: COLLATE [A-Z0-9_]+)?',normalized):return True
    if not re.match(r'^(SELECT|WITH|SHOW|DESCRIBE|DESC)\b',normalized):return False
    if re.search(r'\b(INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER|TRUNCATE|CALL|DO|LOAD|HANDLER|'
                 r'GRANT|REVOKE|INTO|GET_LOCK|RELEASE_LOCK|RELEASE_ALL_LOCKS|LAST_INSERT_ID|'
                 r'BENCHMARK|SLEEP|SET)\b|:=|\bLOCK\s+IN\b',normalized):return False
    return True


def _audit(event,args):
    guard=_ACTIVE
    if guard is None:return
    if event=='open':
        path,mode,flags=args
        write=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags,int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
        if write:guard.require_path(path)
    elif event in ('os.remove','os.rmdir','os.mkdir','os.chmod','os.chown','os.utime','os.truncate'):
        guard.require_path(args[0])
    elif event in ('os.rename','os.replace'):
        guard.require_path(args[0]);guard.require_path(args[1])
    elif event in ('os.symlink','os.link','os.system','os.exec','os.fork','os.posix_spawn'):
        guard.reject('UNQUALIFIED_PROCESS_OR_LINK',event)
    elif event=='subprocess.Popen':
        command=args[1]
        # Metadata only; no hooks, refresh or optional index locks.
        allowed=command in (['git','rev-parse','HEAD'],['git','rev-parse','--abbrev-ref','HEAD'],
                           'git rev-parse HEAD','git rev-parse --abbrev-ref HEAD')
        allowed=allowed and (args[0] is None or Path(args[0]).name.lower() in ('git','git.exe'))
        if not allowed:guard.reject('UNQUALIFIED_SUBPROCESS','subprocess')


class ReadOnlyReplay:
    def __init__(self,root):
        self.root=Path(root).resolve()
        project=Path(__file__).resolve().parents[1]
        if self.root==project or project.is_relative_to(self.root):
            raise ValueError('Dedicated run workspace required')
        self.violations=[]
        self.engines=set()

    def reject(self,kind,detail):
        self.violations.append(dict(kind=kind,detail=str(detail)[:200]))
        raise IsolationViolation(f'Isolated replay: {kind} ({detail})')

    def require_path(self,path):
        if isinstance(path,int):return  # inherited log/stdout descriptors
        if os.fspath(path)==os.devnull:return
        # Managed Windows TLS instrumentation uses an inherited OS pipe, not
        # an application file. Preserve it without enabling arbitrary keylogs.
        raw=os.fspath(path)
        if raw==os.environ.get('SSLKEYLOGFILE') and raw.startswith('\\\\.\\nllMonFltProxy\\'):
            return
        if not Path(path).resolve().is_relative_to(self.root):
            self.reject('SHARED_FILE_WRITE',str(path))

    def sql(self,conn,cursor,statement,parameters,context,executemany):
        url=conn.engine.url
        self.engines.add(conn.engine)
        if url.get_backend_name()=='sqlite':
            database=url.database
            if not database or database==':memory:' or Path(database).resolve().is_relative_to(self.root):
                return
            # SQLAlchemy introspection is read-only, unlike arbitrary PRAGMA.
            if re.match(r'^PRAGMA (?:main\.|temp\.)?(?:table_info|table_xinfo|index_list|index_info|foreign_key_list)\(',statement,re.I):return
        if not read_statement(statement):self.reject('SHARED_SQL_WRITE','statement rejected: '+str(statement).strip().split()[0])

    @contextmanager
    def install(self):
        global _ACTIVE,_AUDIT_INSTALLED
        if _ACTIVE is not None:raise RuntimeError('Nested replay isolation forbidden')
        self.root.mkdir(parents=True,exist_ok=True)
        runtime=self.root/'.runtime';runtime.mkdir(exist_ok=True)
        old_env={name:os.environ.get(name) for name in (
            'TMP','TEMP','TMPDIR','MPLCONFIGDIR','NUMBA_CACHE_DIR','TORCH_HOME','XDG_CACHE_HOME',
            'TORCHINDUCTOR_CACHE_DIR','TRITON_CACHE_DIR','TORCH_EXTENSIONS_DIR','CUDA_CACHE_PATH',
            'PYTHONDONTWRITEBYTECODE','GIT_OPTIONAL_LOCKS','ALPHA_BACKTEST_ISOLATION_ROOT')}
        for name,folder in [('TMP','tmp'),('TEMP','tmp'),('TMPDIR','tmp'),('MPLCONFIGDIR','matplotlib'),
                            ('NUMBA_CACHE_DIR','numba'),('TORCH_HOME','torch'),('XDG_CACHE_HOME','cache'),
                            ('TORCHINDUCTOR_CACHE_DIR','torchinductor'),('TRITON_CACHE_DIR','triton'),
                            ('TORCH_EXTENSIONS_DIR','torch-extensions'),('CUDA_CACHE_PATH','cuda')]:
            path=runtime/folder;path.mkdir(exist_ok=True);os.environ[name]=str(path)
        os.environ.update(PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',ALPHA_BACKTEST_ISOLATION_ROOT=str(self.root))
        import tempfile
        old_temp=tempfile.tempdir;tempfile.tempdir=str(runtime/'tmp')
        old_bytecode=sys.dont_write_bytecode;sys.dont_write_bytecode=True
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        import pymysql.connections
        import http.client
        original_init=pymysql.connections.Connection.__init__
        original_query=pymysql.connections.Connection.query
        original_http=http.client.HTTPConnection.putrequest
        def init(connection,*args,**kwargs):
            if kwargs.get('init_command') not in (None,'SET SESSION TRANSACTION READ ONLY'):
                self.reject('MYSQL_INIT_WRITE','custom init command')
            kwargs['init_command']='SET SESSION TRANSACTION READ ONLY'
            return original_init(connection,*args,**kwargs)
        def query(connection,sql,*args,**kwargs):
            value=sql.decode('utf-8') if isinstance(sql,bytes) else sql
            if not read_statement(value):self.reject('SHARED_SQL_WRITE','DBAPI statement rejected')
            return original_query(connection,sql,*args,**kwargs)
        def http_request(connection,method,url,*args,**kwargs):
            host=(getattr(connection,'_tunnel_host',None) or connection.host).split(':')[0].lower()
            if method.upper() not in ('GET','HEAD') or host not in (
                    'data.alpaca.markets','eodhd.com','query1.finance.yahoo.com','query2.finance.yahoo.com'):
                self.reject('UNQUALIFIED_HTTP',f'{method} {host}')
            return original_http(connection,method,url,*args,**kwargs)
        pymysql.connections.Connection.__init__=init
        pymysql.connections.Connection.query=query
        http.client.HTTPConnection.putrequest=http_request
        event.listen(Engine,'before_cursor_execute',self.sql)
        if not _AUDIT_INSTALLED:
            sys.addaudithook(_audit);_AUDIT_INSTALLED=True
        _ACTIVE=self
        failure=None
        try:
            (self.root/'isolation.json').write_text(json.dumps(dict(mode='READ_ONLY_ISOLATED',
                status='RUNNING',file_writes=str(self.root),violations=[])),encoding='utf-8')
            yield self
        except BaseException as exc:
            failure=exc if not isinstance(exc,SystemExit) or exc.code not in (None,0) else None
            raise
        finally:
            _ACTIVE=None
            event.remove(Engine,'before_cursor_execute',self.sql)
            pymysql.connections.Connection.__init__=original_init
            pymysql.connections.Connection.query=original_query
            http.client.HTTPConnection.putrequest=original_http
            # Connections with session READ ONLY never return to another mode.
            for engine in self.engines:engine.dispose()
            tempfile.tempdir=old_temp;sys.dont_write_bytecode=old_bytecode
            for name,value in old_env.items():
                if value is None:os.environ.pop(name,None)
                else:os.environ[name]=value
            receipt=dict(mode='READ_ONLY_ISOLATED',status='FAILED' if failure or self.violations else 'COMPLETED',
                shared_mysql='SESSION TRANSACTION READ ONLY + SQL guard including DBAPI',
                file_writes=str(self.root),violations=self.violations,
                observation_policy='Independent read transactions; not a globally frozen database snapshot',
                updated_at_utc=datetime.now(UTC).isoformat())
            (self.root/'isolation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
            if self.violations and failure is None:
                raise IsolationViolation('A helper caught an isolation violation; replay remains failed')
