from pathlib import Path
import re

from sqlalchemy import create_engine,event


def sqlite_primary(path):
    engine=create_engine('sqlite:///'+str(path))
    @event.listens_for(engine,'connect')
    def enable_foreign_keys(conn,record):
        conn.execute('PRAGMA foreign_keys=ON')
    with engine.begin() as c:
        for name in ('0009_mifir_options_research','0010_batch_research_storage','0011_public_option_oi','0012_sql_primary'):
            source=Path('database/sql/fr/migration_fr_'+name+'.sql').read_text()
            source=re.sub(r'--[^\n]*','',source)
            source=re.sub(r'\) ENGINE=[^;]+;',');',source)
            source=re.sub(r'^[ \t]+KEY [^\n]+\n','',source,flags=re.M)
            source=re.sub(r'UNIQUE KEY \w+ \(', 'UNIQUE (',source)
            source=source.replace(' UNSIGNED','').replace('LONGBLOB','BLOB').replace('MEDIUMBLOB','BLOB')
            source=re.sub(r',\s*\)',')',source)
            for statement in source.split(';'):
                if statement.strip(): c.exec_driver_sql(statement)
    return engine
