"""Read-only review table with a real per-row Graphique button (no DOM hacks)."""
from datetime import date, datetime
import math

import pandas as pd
import streamlit as st
from streamlit.components.v2 import component

from ihm.components.local_symbol_bars_dialog import request_local_symbol_bars_dialog


CSS = """
.review-table-root {overflow:auto;max-height:460px;border:1px solid var(--st-border-color,#ddd);border-radius:8px;
 color:var(--st-text-color,#252525);background:var(--st-background-color,#fff);font:14px var(--st-font,sans-serif)}
table {border-collapse:separate;border-spacing:0;width:max-content;min-width:100%}
th,td {padding:9px 12px;border-bottom:1px solid var(--st-border-color,#ddd);text-align:left;max-width:330px;min-width:85px}
th {position:sticky;top:0;background:var(--st-secondary-background-color,#f4f5f7);z-index:2;white-space:nowrap}
td {white-space:pre-wrap;overflow-wrap:anywhere} td.numeric {text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
tbody tr:hover td {background:var(--st-secondary-background-color,#f4f5f7)}
th:nth-child(1),td:nth-child(1) {position:sticky;left:0;min-width:120px;width:120px;max-width:120px;box-sizing:border-box}
th:nth-child(2),td:nth-child(2) {position:sticky;left:120px;min-width:95px;width:95px;max-width:95px;box-sizing:border-box}
th:nth-child(3),td:nth-child(3) {position:sticky;left:215px;min-width:95px;width:95px;max-width:95px;box-sizing:border-box}
td:nth-child(-n+3) {background:var(--st-background-color,#fff);z-index:1}
th:nth-child(-n+3) {z-index:3}
button {font:inherit;cursor:pointer;color:inherit} button.sort {border:0;background:transparent;padding:0;font-weight:600;text-align:left}
button.graph {border:1px solid var(--st-border-color,#ccc);background:var(--st-background-color,#fff);border-radius:6px;padding:5px 8px;white-space:nowrap}
button.graph:hover {border-color:var(--st-primary-color,#f44);color:var(--st-primary-color,#f44)}
button:focus-visible {outline:2px solid var(--st-primary-color,#f44);outline-offset:2px}
"""

JS = """
export default function(component) {
 const {data, parentElement, setTriggerValue} = component;
 const root = parentElement.querySelector('.review-table-root');
 function draw() {
  const scrollLeft=root.scrollLeft, scrollTop=root.scrollTop;
  root.replaceChildren();
  const table=document.createElement('table'), head=document.createElement('thead'), body=document.createElement('tbody');
  const hr=document.createElement('tr');
  const state=root.reviewSort;
  data.columns.forEach((col,index)=>{
   const th=document.createElement('th');
   if(col.action) {th.textContent='Graphique';}
   else {
    const button=document.createElement('button'); button.className='sort'; button.type='button';
    button.textContent=col.label+(state?.index===index ? (state.asc ? ' ↑' : ' ↓') : '');
    button.onclick=()=>{root.reviewSort={index,asc:state?.index===index ? !state.asc : true};draw();};
    th.appendChild(button);
   }
   hr.appendChild(th);
  });
  head.appendChild(hr); table.appendChild(head);
  const rows=data.rows.slice();
  if(state) rows.sort((a,b)=>{
   const x=a.cells[state.index].sort, y=b.cells[state.index].sort;
   if(x===null || y===null) return x===y ? 0 : x===null ? 1 : -1;
   const cmp=typeof x==='number' && typeof y==='number' ? x-y : String(x).localeCompare(String(y),'fr');
   return state.asc ? cmp : -cmp;
  });
  rows.forEach(row=>{
   const tr=document.createElement('tr');
   data.columns.forEach((col,index)=>{
    const td=document.createElement('td');
    if(col.action) {
     const button=document.createElement('button'); button.type='button';button.className='graph';button.textContent='📈 Voir';
     button.setAttribute('aria-label','Afficher le graphique de '+row.symbol);
     button.title='Afficher les barres de '+row.symbol;
     button.onclick=()=>setTriggerValue('open_symbol',row.symbol);td.appendChild(button);
    } else {
     td.textContent=row.cells[index].text;td.title=row.cells[index].text;
     if(row.cells[index].numeric)td.className='numeric';
    }
    tr.appendChild(td);
   });body.appendChild(tr);
  });
  table.appendChild(body);root.appendChild(table);root.scrollLeft=scrollLeft;root.scrollTop=scrollTop;
 }
 draw();
}
"""

@st.cache_resource
def _registered_table_component():
    # Register once in the active app runtime, not during a bare-module import.
    return component('prediction_review_with_graphs',
        html='<div class="review-table-root" role="region" aria-label="Tableau de résultats et graphiques" tabindex="0"></div>',
        css=CSS,js=JS,isolate_styles=True)


def _table_component(**kwargs):
    return _registered_table_component()(**kwargs)


def _cell(value, column):
    if value is None or pd.isna(value):
        return dict(text='—',sort=None,numeric=False)
    if isinstance(value, bool):
        return dict(text='Oui' if value else 'Non',sort=int(value),numeric=False)
    if isinstance(value, (date,datetime,pd.Timestamp)):
        return dict(text=value.strftime('%d/%m/%Y'),sort=value.isoformat(),numeric=False)
    if isinstance(value, (int,float)):
        if not math.isfinite(value):
            return dict(text='—',sort=None,numeric=False)
        if column=='Rang Oracle':
            label=str(int(value))
        elif 'Confiance' in column:
            label=f'{value:.2f} %'
        elif '($)' in column:
            label=f'{value:,.2f} $' if 'Montant' in column else f'{value:,.4f} $'
        else:
            label=f'{value:.6f}'
        return dict(text=label,sort=value,numeric=True)
    return dict(text=str(value),sort=str(value),numeric=False)


def table_payload(frame):
    if 'Symbole' not in frame or frame['Symbole'].duplicated().any():
        raise ValueError('Un symbole unique par ligne est requis')
    columns=[]
    for key in frame.columns:
        columns.append(dict(key=key,label=key,action=False))
        if key=='Symbole':
            columns.append(dict(key='__graph',label='Graphique',action=True))
    rows=[]
    for row in frame.to_dict(orient='records'):
        rows.append(dict(symbol=row['Symbole'],cells=[dict(text='',sort=None,numeric=False) if col['action']
            else _cell(row[col['key']],col['key']) for col in columns]))
    return dict(columns=columns,rows=rows)


def render_prediction_review_table(frame, *, key, trade_date):
    if frame.empty:
        return
    # open_symbol is a transient trigger, not persistent component state.
    # A default with the same name masks every click in ComponentResult.
    # Version the key to discard that stale default in already-open sessions.
    result=_table_component(key=f'{key}_graph_v2',data=table_payload(frame),
        on_open_symbol_change=lambda:None,height='content',width='stretch')
    symbol=getattr(result,'open_symbol',None)
    if isinstance(symbol,str) and symbol in set(frame['Symbole']):
        row=frame.loc[frame['Symbole']==symbol].iloc[0]
        request_local_symbol_bars_dialog(symbol,trade_date,row.get('Nom de l’entreprise'))
