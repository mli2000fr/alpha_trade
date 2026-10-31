"""Verify and consolidate the eight research reports without refitting anything."""
from pathlib import Path
import argparse
import json

import pandas as pd

from scripts.research.us_weak_topn_2020_2024_campaign import verified_completed
from scripts.research.us_weak_topn_2020_2024_experiments import digest,write,pmath,PMATH_CONFIG

ROOT=Path('artifacts/research/us_weak_topn_2020_2024/20261029-v1')
PRIMARY={'VOL60':'D1_VS_D10','E2':'LONG_H3','E3':'LONG_NET_POSITIVE','PMATH0':'D1_VS_REST'}


def weighted_auc(rows,value='auc_daily_mean',count='auc_daily_dates'):
    usable=[r for r in rows if r.get(value) is not None and r.get(count,0)>0]
    total=sum(r[count] for r in usable)
    return sum(r[value]*r[count] for r in usable)/total if total else None


def run(root=ROOT):
    root=Path(root);output=root/'summary';output.mkdir(exist_ok=False)
    sources={};annual=[];summary=[];joint_pmath={}
    for method,task in PRIMARY.items():
        for top in (20,50):
            folder=root/'experiments'/f'{method}-TOP{top}'
            if verified_completed(folder)!='COMPLETED_EXPLORATORY':
                raise ValueError('Incomplete experiment: '+str(folder))
            sources[str(folder/'report.json')]=digest(folder/'report.json')
            report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
            if method=='PMATH0':
                joint_pmath.update({f'TOP{top}:{task_name}':details for task_name,details
                    in report['nonparametric_task_summaries'].items()})
            annual.extend(report['annual'])
            primary=[r for r in report['annual'] if r['task']==task]
            if sorted(r['year'] for r in primary)!=list(range(2020,2025)):
                raise ValueError('Missing/duplicate primary years')
            summary.append(dict(method=method,top=top,task=task,
                auc_daily_mean=weighted_auc(primary),daily_dates=sum(r['auc_daily_dates'] for r in primary),
                auc_h_spaced_mean=weighted_auc(primary,'auc_h_spaced_mean','auc_h_spaced_dates'),
                h_spaced_dates=sum(r['auc_h_spaced_dates'] for r in primary),
                years_above_half=sum(r['auc_daily_mean'] is not None and r['auc_daily_mean']>.5 for r in primary),
                annual={str(r['year']):r['auc_daily_mean'] for r in primary},
                candidate_rows=sum(r['rows'] for r in primary),known_rows=sum(r['known_rows'] for r in primary),
                task_coverage=sum(r['known_rows'] for r in primary)/sum(r['rows'] for r in primary)))
    pd.DataFrame(annual).to_csv(output/'annual-summary.csv',index=False)
    # The individual reports correct within each TOP. The consolidated view
    # also treats both TOPs as one family of24 statistical comparisons.
    if joint_pmath:
        pmath.apply_global_gates(joint_pmath,json.loads(PMATH_CONFIG.read_text(encoding='utf-8'))['gates'])
        write(output/'pmath-joint-checks.json',dict(correction='HOLM_ALL_24_TOP_TASK_METHOD_COMPARISONS',
            tasks=joint_pmath,original_reports_unchanged=True))
    pd.DataFrame([{k:v for k,v in row.items() if k!='annual'} for row in summary]).to_csv(output/'primary-summary.csv',index=False)
    lines=['# TOP20/TOP50 Oracle : quatre signaux faibles, 2020–2024','',
        'AUC quotidienne, moyenne pondérée par les dates informatives. Cibles différentes selon méthode. '
        'AUC ≠ taux de trades gagnants. Historique exploratoire déjà examiné.','',
        '| Méthode | TOP | 2020 | 2021 | 2022 | 2023 | 2024 | Moyenne | H-espacé | Années > 0,50 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    fmt=lambda v:'—' if v is None else f'{v:.4f}'.replace('.',',')
    for r in summary:
        values=[r['method'],str(r['top']),*[fmt(r['annual'][str(y)]) for y in range(2020,2025)],
            fmt(r['auc_daily_mean']),fmt(r['auc_h_spaced_mean']),str(r['years_above_half'])+'/5']
        lines.append('| '+' | '.join(values)+' |')
    lines.extend(['','VOL60 : D10/D1 terminal H20. E2 : hausse terminale H3 ≥3 %. '
        'E3 : rentabilité LONG nette du parcours ATR corrigé. P-MATH : mauvais extrême D1 contre le reste.',
        '', '2023 complétée par le modèle causal de janvier2023 figé, sans réentraînement Oracle. '
        '252 dates minimum de train/63 de validation, nouvelles fenêtres explicites. '
        'E3 corrige ATRJ+1 et bougie d’entrée ignorée de l’ancien helper. '
        'Pas un rejeu exact des anciens modèles ni une validation sur années vierges.',
        '', 'Les colonnes secondaires et les preuves non paramétriques sont dans les rapports individuels. '
        'Aucune combinaison, inversion de score, optimisation de seuil ni promotion automatique.'])
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for path,sha in sources.items():
        if digest(path)!=sha:raise ValueError('Experiment changed during consolidation')
    report=dict(status='COMPLETED_VERIFIED_RESEARCH_SUMMARY',experiments=8,years=list(range(2020,2025)),
        summary=summary,source_reports=sources,
        dataset_manifest_sha256=digest(root/'dataset/manifest.json'),
        labels_report_sha256=digest(root/'labels/report.json'),
        no_refit=True,no_provider_call=True,no_SQL=True,no_orders=True,no_promotion=True,
        files={p.name:digest(p) for p in output.iterdir() if p.is_file()})
    write(output/'report.json',report)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    run(parser.parse_args().root)
