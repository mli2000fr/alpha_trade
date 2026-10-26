"""Registry scope inventory and archive-only feasibility; no outcome computation."""
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd

from scripts.research.us_options_equal_mix_20261026 import digest,write

ROOT=Path('artifacts/research/us_legacy_scope_inventory/20261026-v1')
REGISTRY=Path('doc/ml/experiences_done.md')
MODELS=Path('artifacts/research/us_h10_h20_frozen_comparison/20261019-v1')
PILOT=Path('artifacts/research/alpaca_options_history/20261010-volume-pilot')
DOC=Path('doc/ml/anciens_signaux_perimetres_et_reprises_20261026.md')
TEST=Path('tests/test_us_legacy_scope_inventory_20261026.py')

# Scientific families, not a fabricated count of independent experiments/runs.
FAMILIES=[
 ('options_volume_prospectif','Univers tradable, puis titres TOP10/20/50','DEJA_APPLIQUE','options_oracle_topn_resultats_20261026.md','Indice H5 TOP20, faible couverture et pas de validation prospective'),
 ('options_oi_prospectif','Univers tradable, puis titres TOP10/20/50','DEJA_APPLIQUE','options_oracle_topn_resultats_20261026.md','Même corpus que volume, ne pas compter deux confirmations'),
 ('options_mix_prospectif','Univers tradable, puis titres TOP10/20/50','DEJA_APPLIQUE','options_oracle_topn_resultats_20261026.md','Pas de nouvelle recherche de poids'),
 ('options_volume_jan2025','37 liquides dans univers, pas TOPN Oracle','VERIFIER_COUVERTURE','alpaca_options_historical_volume_pilot.md','AUC terminale H20 0,593, disponibilité historique supposée, pas certifiée'),
 ('options_volume_fevmars2024','Univers, puis Oracle TOP20 POURCENT','PAS_DE_SIGNAL_STABLE','alpaca_options_feb_mar_2024_directional_audit.md','Conditionnel H20 0,509 et stabilité faible, pas candidat prioritaire'),
 ('options_iv_prospectif','Univers tradable','PAS_DE_SIGNAL_STABLE','us_collectes_prospectives_direction_audit_20261010.md','AUC H5 0,522/H10 0,520, H10 change de sens entre moitiés'),
 ('eps_revisions_yahoo','Univers tradable, contrôles secteur/momentum','SOURCE_BLOQUEE','analyst_archive_restore_directional_20261010.md','Ne pas restaurer les tables ou réactiver la source'),
 ('eps_objectifs_recommandations','Univers tradable','SOURCE_BLOQUEE','analyst_archive_restore_directional_20261010.md','Objectifs instables, recommandations sans lift de tête, Yahoo bloqué'),
 ('consensus_eodhd','Univers, pilotes TOP10 et TOP20 POURCENT','ALIGNEMENT_INSUFFISANT','consensus_fiabilite_bilan_20261022.md','Recul court, sémantique/UTC, peu de dates Oracle communes'),
 ('surprise_eps_ddr5','Oracle TOP20 POURCENT','PIT_NON_QUALIFIE','signaux_directionnels_faibles_audit_20261014.md','Jointure earnings_date ne démontre pas estimation disponible avant décision'),
 ('e2_long_h3','Oracle TOP20 POURCENT, sélection TOP10 POURCENT du score','ARCHIVES_MANQUANTES','shared_directional_oracle_events.md','Petit signal initial puis confirmation insuffisante; pas TOP10 titres'),
 ('e3_long_pathaware','Oracle TOP20 POURCENT','ARCHIVES_MANQUANTES','shared_directional_oracle_events.md','Petit AUC, économie négative, autre lifecycle et anciens scores'),
 ('ranker_conditionnel','Oracle TOP20 POURCENT','AUTRE_CONTRAT','conditional_oracle_ranker.md','Ancien batch, complémentarité et consensus déjà testés, pas substitution au parcours actuel'),
 ('consensus_experts_oof','Oracle TOP20 POURCENT','DEJA_NEGATIF','oof_consensus_audit.md','Sept familles anciennes, IC inférieur au meilleur composant'),
 ('hierarchie_directionnelle','Oracle TOP20 POURCENT puis TOP10 titres','DEJA_APPLIQUE','direction_hierarchique_secteur_titre_20261018.md','Correction secteur/titre, trajectoires et tests TOP10 déjà faits'),
 ('catboost_trois_classes','TOP10 titres','DEJA_APPLIQUE','direction_top10_catboost_trois_classes_20261018.md','Pas de concentration D10 stable'),
 ('d10_plus_antid1','TOP10 titres, choisir trois','DEJA_APPLIQUE','complementarite_anciens_signaux_top10_20261018.md','Petit gain moyen, 2024 négatif, confirmation corrigée insuffisante'),
 ('momentum_volatilite_atr','Pool Oracle TOP20 POURCENT x ATR, puis TOP10 titres','DEJA_APPLIQUE','complementarite_anciens_signaux_top10_20261018.md','Ne pas confondre top10 du pool et top10 Oracle; reprise exacte déjà faite'),
 ('filtre_univarie_prix','TOP10/20/50 titres','DEJA_APPLIQUE','oracle_path_filtre_entree_separabilite_20261014.md','Aucune sonde passe les gates de confirmation'),
 ('tri_tendance_parcours','TOP10 titres, retenir trois/cinq','DEJA_APPLIQUE','oracle_tri_tendance_parcours_bilan_20261022.md','Vol20/vol60 favorable récent, validation 2022 défavorable'),
 ('news_positives','Univers tradable, H0…H20 et retards','PAS_DE_SIGNAL_STABLE','news_positives_parcours_h20_20261014.md','Pas d’avantage stable, timestamps historiques non certifiés'),
 ('news_gpt','TOP10 et TOP20 titres','DEJA_APPLIQUE','news_oracle_top10_janvier_2026.md','Plusieurs mois/années, résultats et limites déjà documentés'),
 ('news_post_entree','TOP10/20/50 titres','DEJA_APPLIQUE','news_post_entree_sortie_20261014.md','Sortie négative pas de gain transversal'),
 ('news_sensibilite_titre','Univers tradable puis sous-univers','PAS_DE_SIGNAL_STABLE','news_sensibilite_par_titre_bilan_20261022.md','Pas de sous-univers validé après corrections'),
 ('e23_sentiment_trajectoires','Oracle TOP20 POURCENT puis TOP10 descriptif','ARCHIVE_FILTREE_PAR_FUTUR','complementarite_anciens_signaux_top10_20261018.md','Disponibilité des scores conditionnée aux labels futurs, pas de recette'),
 ('global_ranking_dip_persistence','Global Ranking TOP/BOTTOM10','AUTRE_STRATEGIE','../experiences/archives_recherche/persistent_tail_price.md','Pas un Oracle d’amplitude; persistance Oracle TOP10 déjà négative'),
 ('e17_momentum_residuel','Univers H60/H120, TOP10 partiel','AUTRE_HORIZON','complementarite_anciens_signaux_top10_20261018.md','85dates communes, autres années absentes, pas substitution H20'),
 ('e19_valeur','Univers H60/H120','CONFIRMATION_NEGATIVE','fundamental_value_confirmation_e19c.md','Candidate initiale, confirmation verrouillée négative'),
 ('multi_horizon_rolling','Oracle multi-horizons, 284 titres','AUTRE_CONTRAT','multi_horizon_oracle_rolling_confirmation.md','Anciennes cibles et univers; challenger rolling négatif'),
 ('opening_e20','Oracle TOP20 POURCENT, décision J+1 10:00','AUTRE_INSTANT','oracle_opening_price_economic_replay_e20d.md','Direction connue après ouverture, coût d’attente absorbe effet'),
 ('intraday_signed_flow','Événements Oracle TOP20 POURCENT','CONFIRMATION_NEGATIVE','signed_trade_flow_pilot.md','AUC 0,567 initiale mais tests multiples/confirmation insuffisants'),
 ('options_eroya','Événements Oracle TOP20 POURCENT','CONFIRMATION_NEGATIVE','options_directional_poc.md','H3 0,619 porté par 2022 seulement; autre surface, pas réplication Alpaca'),
 ('form4_analyst_insights','Événements Oracle TOP20 POURCENT','PAS_DE_SIGNAL_STABLE','eroya_directional_poc.md','Ablations ou données strictes sans gain stable'),
 ('activisme_13d','Marché large, puis TOP20 POURCENT','CONFIRMATION_NEGATIVE','experiences_done.md','Pilote 2024 positif non confirmé en 2025/2026'),
 ('guidance_financement_sec','Événements, puis TOP10/TOP20 POURCENT','DONNEES_NON_PRETES','experiences_done.md','Qualifications documentaires, pas un signal directionnel validé'),
 ('regime_macro','Dates marché puis panier TOP10/20','DEJA_APPLIQUE','winner_anticipation_resultats_20261025.md','Aucune alerte robuste; pas de filtre retourné après observation'),
 ('winner_fmz_protections','TOP5/TOP10/TOP20/TOP50 titres','HORS_SELECTION_DIRECTIONNELLE','experiences_done.md','Lifecycle/risque, pas des AUC à recycler comme direction'),
]


def registry_entries(text):
    result=[]
    for part in re.split(r'(?m)^## ',text)[1:]:
        title,_,body=part.partition('\n')
        # Mentions only, deliberately not a scientific scope assignment.
        mentions=sorted(set(re.findall(r'\bTOP\s*\d+\s*(?:%|POURCENT|titres)?',part,re.I)))
        result.append(dict(title=title.strip(),scope_mentions=mentions,
            mentions_are_not_verified_scope=True,body_sha256=__import__('hashlib').sha256(body.encode()).hexdigest()))
    return result


def select(scores,n):
    """Rebuild original ranks BEFORE joining any option or future label."""
    f=scores[['date','symbol','score','rank','scored_count']].copy()
    if f.duplicated(['date','symbol']).any():raise ValueError('Duplicate Oracle key')
    if not (np.isfinite(f.score)&f.score.between(0,1)).all():raise ValueError('Invalid score')
    f=f.sort_values(['date','score','symbol'],ascending=[True,False,True],kind='stable')
    expected=f.groupby('date').cumcount()+1
    if not f['rank'].eq(expected).all():raise ValueError('Saved rank disagrees with full universe')
    if not f.scored_count.eq(f.groupby('date').symbol.transform('size')).all():raise ValueError('Incomplete score universe')
    return f[f['rank'].le(n)].copy()


def coverage_case(scores,features,n):
    top=select(scores,n)
    joined=top.merge(features[['day','symbol']],left_on=['date','symbol'],right_on=['day','symbol'],validate='one_to_one')
    return dict(N=n,oracle_candidates=len(top),oracle_dates=int(top.date.nunique()),paired=len(joined),
        paired_symbols=int(joined.symbol.nunique()),paired_dates=int(joined.date.nunique()),
        fraction_covered=len(joined)/len(top) if len(top) else None,
        symbols=sorted(joined.symbol.unique().tolist()),no_outcomes_computed=True)


def referenced_oof_paths(value):
    result=[]
    if isinstance(value,dict):
        for k,v in value.items():
            if k=='path' and isinstance(v,str):result.append(v)
            else:result+=referenced_oof_paths(v)
    elif isinstance(value,list):
        for v in value:result+=referenced_oof_paths(v)
    return result


def run(output=ROOT):
    output.mkdir(parents=True,exist_ok=False)
    raw=REGISTRY.read_text(encoding='utf-8');entries=registry_entries(raw)
    (output/'registry-snapshot.md').write_text(raw,encoding='utf-8')
    sources={str(p):digest(p) for p in [Path(__file__),TEST,DOC,
        PILOT/'features.parquet',PILOT/'protocol.json',PILOT/'report.json',
        MODELS/'final-audit.json',MODELS/'protocol.json']}
    historical={}
    features=pd.read_parquet(PILOT/'features.parquet',columns=['day','symbol'])
    if features.duplicated(['day','symbol']).any():raise ValueError('Duplicate features')
    dates=pd.to_datetime(features.day)
    for h in [10,20]:
        file=MODELS/f'2025-H{h}-scores.parquet';contract=MODELS/f'models/2025/H{h}/contract.json'
        sources[str(file)]=digest(file);sources[str(contract)]=digest(contract)
        c=json.loads(contract.read_text(encoding='utf-8'))
        weight=MODELS/c['model_file'];sources[str(weight)]=digest(weight)
        if c['target_horizon']!=h or sources[str(weight)]!=c['model_sha256']:raise ValueError('Model mismatch')
        if pd.Timestamp(c['max_val_available'])>=dates.min() or pd.Timestamp(c['max_train_available'])>=dates.min():
            raise ValueError('Future train/validation data')
        # Do not read targets, amplitudes, selected or any future path from this file.
        scores=pd.read_parquet(file,columns=['date','symbol','score','rank','scored_count'])
        scores=scores[scores.date.between(dates.min(),dates.max())].copy()
        historical[str(h)]=[coverage_case(scores,features,n) for n in [10,20,50]]
    manifest=Path('config/research/oof_consensus_0802c8.json')
    sources[str(manifest)]=digest(manifest)
    paths=sorted(set(referenced_oof_paths(json.loads(manifest.read_text(encoding='utf-8')))))
    oof={p:Path(p).is_file() for p in paths}
    h10paths=[]
    for y in [2024,2025,2026]:
        c=MODELS/f'models/{y}/H10/contract.json';d=json.loads(c.read_text(encoding='utf-8'))
        file=MODELS/f'{y}-H10-scores.parquet'
        # Metadata date range, no outcomes; research H10 is not a production model.
        f=pd.read_parquet(file,columns=['date'])
        h10paths.append(dict(year=y,contract=str(c),target_horizon=d['target_horizon'],
            first_signal=str(f.date.min().date()),last_signal=str(f.date.max().date()),
            serving_ready=False))
        sources[str(c)]=digest(c);sources[str(file)]=digest(file)
    cases=[dict(id=i,scope=scope,decision=status,document='doc/ml/'+doc,reason=reason,
                document_exists=Path('doc/ml',doc).is_file()) for i,scope,status,doc,reason in FAMILIES]
    for case in cases:
        p=Path(case['document'])
        if not p.is_file():raise ValueError('Missing documentary evidence '+str(p))
        if p.resolve()!=REGISTRY.resolve():sources[str(p)]=digest(p)
    report=dict(status='COMPLETED_SCOPE_AND_FEASIBILITY_ONLY',family_count=len(cases),
        registry_section_count=len(entries),registry_sections_not_independent_experiments=True,
        families=cases,scope_index=entries,old_oof_paths=oof,
        historical_options_technical_overlap=historical,research_h10_models=h10paths,
        no_outcomes_computed=True,no_training=True,no_new_inference=True,
        SQL_reads=0,SQL_writes=0,provider_calls=0,LLM_calls=0,
        conclusion='No new confirmatory retest qualified; archived historical volume technically alignable but not strict PIT and only 2-5 securities',
        inherited_archive_readiness='Technically alignable is not historically available; no vintage invented',sources=sources)
    write(output/'report.json',report)
    write(output/'seal.json',dict(files={p.name:digest(p) for p in output.iterdir() if p.is_file()},sources=sources))
    print(json.dumps(dict(status=report['status'],families=len(cases),registry_sections=len(entries),
        old_oof_references=len(oof),old_oof_present=sum(oof.values()),historical_overlap=historical),indent=2))


if __name__=='__main__':run()
