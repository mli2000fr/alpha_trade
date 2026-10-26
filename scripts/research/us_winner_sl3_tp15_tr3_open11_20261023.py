"""TP15-only amendment of sealed SL3/TP7/TR3/open11, no old source edits."""
from contextlib import contextmanager
from pathlib import Path
import argparse
import logging
import pandas as pd

from scripts.research import us_winner_sl3_tp7_tr3_open11_20261023 as base
from scripts.research import us_winner_sl3_tp7_tr3_open11_audit_20261023 as auditor

ROOT=Path('artifacts/research/us_winner_sl3_tp15_tr3_open11/20261023-v1')
REFERENCE=base.ROOT
DOC=Path('doc/ml/winner_sl3_tp15_tr3_open11_protocole_20261023.md')
ARM='SL3_TP15_TR3_OPEN11'
RULE={**base.RULE,'take_profit_pct':.15}
ORIGINAL_SCALAR=auditor.scalar_exit


def scalar_tp15(path,entry_time,entry,due,**kwargs):
    if 'tp' in kwargs and kwargs['tp']!=.15:raise ValueError('Frozen TP15 required')
    return ORIGINAL_SCALAR(path,entry_time,entry,due,**dict(kwargs,tp=.15))


def reference_sources():
    read,digest,verify=base.source.read,base.source.digest,base.source.verify
    p=read(REFERENCE/'protocol.json');verify(p['sources'])
    r=read(REFERENCE/'report.json');a=read(REFERENCE/'final-audit.json')
    if a['report_sha256']!=digest(REFERENCE/'report.json') or a['accounts']!=2:raise ValueError('Audited TP7 reference required')
    verify({str(REFERENCE/k):v for k,v in r['files'].items()})
    files=[REFERENCE/'protocol.json',REFERENCE/'report.json',REFERENCE/'final-audit.json',REFERENCE/'annual-summary.csv']
    for case in r['cases']:
        folder=REFERENCE/f"{case['year']}-{case['arm']}"
        verify({str(folder/k):v for k,v in case['files'].items()})
        files.extend([folder/'report.json',*(folder/k for k in case['files'])])
    return {str(x):digest(x) for x in files}


@contextmanager
def tp15_adapter():
    old_rule,old_arm,old_doc=base.RULE,base.ARM,base.DOC
    old_save,old_scalar,old_audit_save=base.source.save_new,auditor.scalar_exit,auditor.save_new
    refs=reference_sources()
    def seal(path,value):
        if Path(path).name=='protocol.json':
            extra=[Path(__file__),DOC,Path('tests/test_us_winner_sl3_tp15_tr3_open11_20261023.py')]
            value['sources'].update(refs)
            value['sources'].update({str(x):base.source.digest(x) for x in extra})
            value.update(tp7_reference=str(REFERENCE),only_changed_vs_tp7=['take_profit_pct'],
                scalar_exit_explicit_tp=.15,old_sources_edited=False)
        return old_save(path,value)
    def seal_audit(path,value):
        if Path(path).name=='final-audit.json':
            value.update(explicit_tp=.15,tp_adapter_sha256=base.source.digest(__file__))
        return old_audit_save(path,value)
    base.RULE=RULE;base.ARM=ARM;base.DOC=DOC;base.source.save_new=seal
    auditor.scalar_exit=scalar_tp15;auditor.save_new=seal_audit
    try:yield
    finally:
        base.RULE=old_rule;base.ARM=old_arm;base.DOC=old_doc;base.source.save_new=old_save
        auditor.scalar_exit=old_scalar;auditor.save_new=old_audit_save


def comparison(root):
    read,digest,verify,save=base.source.read,base.source.digest,base.source.verify,base.source.save_new
    p=read(root/'protocol.json');verify(p['sources'])
    r=read(root/'report.json');a=read(root/'final-audit.json')
    if a['report_sha256']!=digest(root/'report.json') or a['explicit_tp']!=.15:raise ValueError('TP15 audit absent')
    old=read(REFERENCE/'report.json');rows=[]
    for c in r['cases']:
        b=next(x for x in old['cases'] if x['year']==c['year'])
        for label,case in [('TP7',b),('TP15',c)]:
            row={k:v for k,v in case.items() if not isinstance(v,(dict,list))}
            row.update(tp_variant=label,reference_tp7_return_pct=b['return_pct'],
                return_delta_vs_tp7_pp=case['return_pct']-b['return_pct'],
                win_delta_vs_tp7_pp=case['win_pct']-b['win_pct'],
                dd_delta_vs_tp7_pp=case['max_drawdown_pct']-b['max_drawdown_pct'])
            rows.append(row)
    frame=pd.DataFrame(rows);frame.to_csv(root/'comparison-tp7-tp15.csv',index=False)
    save(root/'comparison-audit.json',dict(status='PASS_AUDITED_TP_ONLY_COMPARISON',
        report_sha256=digest(root/'report.json'),tp7_report_sha256=digest(REFERENCE/'report.json'),
        tp15_audit_sha256=digest(root/'final-audit.json'),comparison_sha256=digest(root/'comparison-tp7-tp15.csv'),
        years=p['years'],old_reference_reused=True,independent_holdout=False))


def run(root,*,smoke=False,phase='all'):
    with tp15_adapter():
        if phase in ('prepare','all'):base.prepare(root,smoke=smoke)
        if phase in ('run','all'):
            if bool(base.source.read(root/'protocol.json')['smoke'])!=smoke:
                raise ValueError('Smoke flag must match the sealed protocol')
            base.run(root)
    if phase in ('run','all') and not smoke:comparison(root)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT)
    parser.add_argument('--phase',choices=['prepare','run','all'],default='all');parser.add_argument('--smoke',action='store_true');a=parser.parse_args()
    logging.basicConfig(level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden(*a,**k):raise RuntimeError('Offline research; HTTP forbidden')
    requests.Session.request=forbidden
    run(a.output,smoke=a.smoke,phase=a.phase)
