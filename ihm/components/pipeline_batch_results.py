"""Always-visible daily steps11/12, exact account archives, no broker/API call."""
import json

import pandas as pd
import streamlit as st


def load_risk(path,record,account):
    from service.q051_paper.pipeline import digest
    folder=path.parent/'accounts'/account
    risk_path=folder/'risk.json'
    if not risk_path.is_file():return None
    risk=json.loads(risk_path.read_text(encoding='utf-8'))
    seal=json.loads((folder/'risk.seal.json').read_text(encoding='utf-8'))
    if (seal['risk_sha256']!=digest(risk_path) or risk['selection_sha256']!=digest(path)
            or risk['q051_run_id']!=record['run_id'] or risk['account_id']!=account
            or risk['trade_date']!=record['trade_date']):
        raise ValueError('Décisions du risque incompatibles avec la sélection affichée')
    if risk.get('human_selection_sha256'):
        if risk['human_selection_sha256']!=digest(path.parent/'human_selection.json'):
            raise ValueError('Validation humaine différente du risque publié')
    return risk


def execution_rows(execution,risk):
    decisions={r['symbol']:r for r in risk['decisions'] if r.get('approved_shares',0)>0}
    runtime=execution.get('winner_standard_entry',{})
    rows=[]
    for order in runtime.get('standard_orders',[]):
        symbol=order['symbol']
        if symbol not in decisions:raise ValueError('Ordre extérieur aux cibles de ce risque')
        reference=decisions[symbol]
        rows.append(dict(Symbole=symbol,Sens='LONG',État=order.get('status'),
            Quantité_demandée=order.get('requested_quantity'),Quantité_exécutée=order.get('filled_quantity',0),
            Prix_de_référence=reference.get('entry_price'),Montant_cible=reference.get('target_notional'),
            Ordre_broker=order.get('broker_order_id')))
    return pd.DataFrame(rows).rename(columns=lambda s:s.replace('_',' '))


def _render_execution(path,record,account,risk):
    if path is None:
        st.info('En attente de la sélection de l’étape10, puis de la validation et du risque.')
        return
    if risk is None:
        st.info(f'En attente du bilan de risque exact de {account} ; aucun résultat d’exécution à afficher.')
        return
    folder=path.parent/'accounts'/account
    execution_path=folder/'execution.json'
    if not execution_path.is_file():
        if not risk.get('targets'):
            st.info('Aucune cible approuvée par le risque : aucun ordre attendu pour cette sélection.')
        elif (folder/'execution.claim.json').is_file():
            st.warning('Tentative d’exécution enregistrée, bilan non publié. Consulter les logs pour son état ; aucun rejeu automatique.')
        else:
            st.info(f'Étape12 en attente pour {account} ; aucune exécution publiée pour cette sélection.')
        return
    value=json.loads(execution_path.read_text(encoding='utf-8'))
    if (value['risk_run_id']!=risk['risk_run_id'] or value['account_id']!=account
            or value['trade_date']!=record['trade_date'] or value['profile_sha256']!=risk['profile_sha256']
            or value['targets']!=risk['targets']):
        raise ValueError('Exécution incompatible avec le risque exact du compte et de la sélection')
    st.caption(f'Exécution archivée : {value["exec_run_id"]} · compte {account} · séance {value["trade_date"]} · '
               f'état {value["status"]} · {value.get("submitted",0)} ordre(s) soumis.')
    rows=execution_rows(value,risk)
    if rows.empty:
        st.info('Aucun détail d’ordre publié dans ce bilan ; ne pas en déduire un achat exécuté.')
    else:
        st.dataframe(rows,hide_index=True,use_container_width=True)
    st.caption('Photographie de fin d’étape : un ordre soumis peut rester en attente. '
               'Prix de référence et montant cible proviennent du risque ; ce ne sont pas les prix et montants exécutés.')
    if value.get('plans'):
        with st.expander('Plans Winner enregistrés',expanded=False):st.dataframe(pd.DataFrame(value['plans']),hide_index=True)


def render_account_stages(view,path,record):
    opts=view.options
    expanded=bool(opts.llm_filter_enabled or st.session_state.get('pipeline_q051_manual_llm_filter')
                  or (record or {}).get('llm_filter'))
    risk=None
    with st.expander('11. Risk Management — décisions par compte',expanded=expanded):
        accounts=(opts.account_id or 'default',*view.other_accounts)
        account=st.selectbox('Compte à consulter',accounts,key='pipeline_us_defaults_review_account')
        if path is None:
            st.info('En attente du résultat de l’étape10 et de votre validation si GPT/DeepSeek est activé.')
        else:
            try:
                risk=load_risk(path,record,account)
                if risk is None:
                    st.info(f'Aucune décision du risque publiée pour {account} et cette sélection. '
                            'Avec GPT/DeepSeek, valider d’abord les titres dans le bloc10.')
                else:
                    st.caption(f'Risque archivé : {risk["risk_run_id"]} · capital {risk["equity"]:,.2f} $ · '
                               f'{risk["approved_count"]} approuvé(s), {risk["rejected_count"]} refusé(s). '
                               'Une approbation du risque ne prouve pas un remplissage broker.')
                    decisions=pd.DataFrame(risk['decisions'])
                    names={'symbol':'Symbole','decision':'Décision','reason':'Motif','approved_shares':'Quantité',
                           'entry_price':'Prix de référence','target_notional':'Montant cible','score_used':'Score LONG'}
                    if decisions.empty:st.info('Aucune cible de risque pour cette sélection.')
                    else:st.dataframe(decisions[[k for k in names if k in decisions]].rename(columns=names),
                                      hide_index=True,use_container_width=True)
            except (OSError,ValueError,KeyError) as exc:
                risk=None;st.warning(f'Décisions du risque indisponibles : {exc}')
    with st.expander('12. Execution — résultat par compte',expanded=expanded):
        try:_render_execution(path,record,account,risk)
        except (OSError,ValueError,KeyError) as exc:st.warning(f'Résultat d’exécution indisponible : {exc}')
