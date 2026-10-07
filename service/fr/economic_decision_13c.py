"""Descriptive audit of fixed supplier ledgers; no optimization or confirmation."""
import argparse
import json
from decimal import Decimal
from pathlib import Path

from service.fr.exploitable_scope_12e import sha
from service.fr.provider_exploratory_metrics_13b import ledger_metrics


def attribution(result,instruments):
    by_symbol={}
    trades=result['ledger']['trades']
    for t in trades:
        ticker=instruments[t['uid']]['ticker']
        by_symbol[ticker]=by_symbol.get(ticker,Decimal(0))+Decimal(t['net_pnl'])
    positives=sum((v for v in by_symbol.values() if v>0),Decimal(0))
    top=sorted(by_symbol.items(),key=lambda x:x[1],reverse=True)
    best=max((Decimal(t['net_pnl']) for t in trades),default=Decimal(0))
    net=Decimal(result['net_pnl'])
    return {'net_pnl_eur':str(net),'gross_pnl_eur':result['gross_pnl'],
        'top_symbols':[{'symbol':s,'net_pnl_eur':str(v)} for s,v in top[:5]],
        'top_positive_symbol_share_of_positive_contributions':float(top[0][1]/positives) if positives and top else None,
        'best_trade_net_eur':str(best),
        'net_minus_best_trade_eur_attribution_only':str(net-best),
        'net_minus_best_symbol_eur_attribution_only':str(net-top[0][1]) if top else None,
        'subtraction_is_not_a_replayed_policy':True,'distinct_traded_symbols':len(by_symbol),
        'skip_counts':{reason:sum(o.get('reason')==reason for o in result['ledger']['orders'])
                       for reason in sorted({o['reason'] for o in result['ledger']['orders'] if 'reason' in o})}}


def run(source,output):
    output.mkdir(parents=True,exist_ok=False)
    report=json.loads((source/'report.json').read_text(encoding='utf-8'))
    for name,value in report['output_hashes'].items():
        if sha(source/name)!=value:
            raise ValueError('Archived output changed')
    if len(report['cells'])!=24 or report['blocked_cells'] or report['confirmation_2026_evaluated']:
        raise ValueError('Complete fixed development comparison required')
    records=[]
    for cell in report['cells']:
        name=f"{cell['fold']}-{cell['policy']}-{cell['tax_scenario']}-{cell['cost_scenario']}-ledger.json"
        result=json.loads((source/name).read_text(encoding='utf-8'))
        shared=json.loads((source/f"fold-{cell['fold']}-supplier-shared.json").read_text(encoding='utf-8'))
        if ledger_metrics(result,data_kind='EXPLORATORY_PROVIDER_ASSUMED')!=cell['metrics']:
            raise ValueError('Metric replay mismatch')
        records.append({**cell,'attribution':attribution(result,shared['instruments'])})
    comparisons=[]
    for oracle in [r for r in records if r['policy']=='oracle_top20_long']:
        for reference in ['atr_top20_long','uniform_control_long']:
            other=next(r for r in records if r['policy']==reference and all(r[k]==oracle[k] for k in ['fold','tax_scenario','cost_scenario']))
            comparisons.append({k:oracle[k] for k in ['fold','tax_scenario','cost_scenario']} | {
                'reference':reference,'oracle_minus_reference_return_pp':oracle['metrics']['net_return_pct']-other['metrics']['net_return_pct']})
    decision={'status':'EXPLORATORY_COMPARISON_COMPLETE_STRICT_VALIDATION_BLOCKED',
        'source_report_sha256':sha(source/'report.json'),'implementation_sha256':sha(Path(__file__)),
        'cells':records,'paired_comparisons':comparisons,
        'economic_go_allowed':False,'serving_enabled':False,'canonical_writes':False,
        'confirmation_2026_evaluated':False,'model_selection_or_retuning':False,
        'sprint13_exploratory_complete':True,'sprint13_strict_complete':False,
        'decision':'NO_GO_SHADOW_FOR_THIS_FROZEN_LONG_H5_POLICY',
        'reasons':['Loss-making first fold across all scenarios',
            'Oracle underperforms uniform control on fold 6; advantage not consistent across folds',
            'Fold 7 positive Oracle PnL dominated by one ABVX trade; subtraction is attribution, not a replay',
            'Independent price/CA/PIT/tax and total-return benchmark gates remain open'],
        'amplitude_model_rejected':False,'directional_edge_proven':False,
        'unperformed':['Qualified total-return benchmark','Qualified strict tapes',
            'Sector/size/segment PIT sensitivities','Pre-registered entry-delay replay',
            'Reserved 2026 confirmation: no eligible robust policy promoted']}
    (output/'report.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2),encoding='utf-8')
    return decision

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    print(run(args.source,args.output)['status'])
