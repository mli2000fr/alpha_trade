"""Plot only audited min70/4k completed accounts and a transparent SPY price benchmark.

No rerun, SQL, provider download, source changes, or extrapolation of active runs.
SPY: fractional buy-and-hold at 2020Jan2 open, 8bp entry fee, marked daily,
no liquidation fee at the end (open holding), dividends NOT included.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np
import pandas as pd

OUTPUT = Path('artifacts/research/us_winner_completed_spy_visuals/20261026-v1')
INPUTS = Path('artifacts/research/us_winner_monthly_selector/20261024-v1/inputs')
CASES = [
    ('SL1 · sans pause', 'us_winner_sl1_min70/20261025-v1', '#2176c1', '--', .01),
    ('SL3 · sans pause', 'us_winner_sl3_min70/20261025-v1', '#bd4040', '-.', .03),
    ('SL5 · sans pause', 'us_winner_min70_4000/20261025-v1', '#cf6016', '-', .05),
    ('SL5 · DD15 / pause 3 mois', 'us_winner_cycle15_min70/20261025-v1', '#7652a1', '-', .05),
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def money(value):
    return f'{value:,.2f}'.replace(',', ' ').replace('.', ',')


def load_cases():
    series, sources, summaries = [], {}, []
    for label, relative, color, style, stop in CASES:
        root = Path('artifacts/research') / relative
        payload = read(root/'report.json')
        if payload['status'] != 'COMPLETED_AUDITED_EXPLORATORY':
            raise ValueError(f'Incomplete study: {root}')
        case = payload['case']
        if (case['start'], case['end'], case['initial_equity'], case['minimum_notional']) != (
                '2020-01-02', '2024-12-31', 4000., 70.):
            raise ValueError('Incompatible period, capital, or minimum')
        policy = case['actual_campaign_policy']
        if (policy['stop_loss_pct'], policy['take_profit_pct'], policy['trailing_stop_pct'],
                policy['horizon_sessions'], policy['initial_position_fraction'], policy['reinforcement_enabled']) != (
                    stop, None, None, 20, 1., False):
            raise ValueError('Incompatible entry/exit policy')
        if not str(case['audit']['status']).startswith('PASS'):
            raise ValueError('Missing output audit')
        candidates = list((root/'cases').glob('*/equity-daily.parquet'))
        if len(candidates) != 1:
            raise ValueError('Ambiguous capital curve')
        file = candidates[0]
        if digest(file) != case['files'][file.name]:
            raise ValueError('Capital curve checksum mismatch')
        values = pd.read_parquet(file)['equity']
        values.index = pd.to_datetime(values.index)
        if (values.index.has_duplicates or not values.index.is_monotonic_increasing
                or not np.isfinite(values).all() or (values <= 0).any()):
            raise ValueError('Invalid daily curve')
        if (len(values) != 1258 or str(values.index[0].date()) != case['start']
                or str(values.index[-1].date()) != case['end']):
            raise ValueError('Unexpected daily calendar')
        np.testing.assert_allclose(values.iloc[-1], case['final_equity'], rtol=0, atol=1e-7)
        if series and not series[0][1].index.equals(values.index):
            raise ValueError('Mismatched account dates')
        sources[str(file)] = digest(file)
        sources[str(root/'report.json')] = digest(root/'report.json')
        series.append((label, values, color, style))
        summaries.append(dict(label=label, final_equity=case['final_equity'], return_pct=case['return_pct'],
            max_drawdown_intraday_pct=case['max_drawdown_pct'], source=str(root)))
    return series, summaries, sources


def spy_curve(index):
    file = INPUTS/'symbols/SPY/daily.parquet'
    manifest = read(INPUTS/'manifest.json')
    key = next(k for k in manifest['files'] if str(k).replace('\\', '/') == 'symbols/SPY/daily.parquet')
    if digest(file) != manifest['files'][key]:
        raise ValueError('SPY archive checksum mismatch')
    frame = pd.read_parquet(file)
    frame['date'] = pd.to_datetime(frame.date)
    frame = frame[frame.date.isin(index)].set_index('date').sort_index()
    if (not frame.index.equals(index) or not frame.symbol.eq('SPY').all()
            or not frame.data_adjustment.eq('split').all() or not frame.is_filled.eq(0).all()
            or frame.data_source.str.contains('iex', case=False, na=True).any()):
        raise ValueError('SPY incomplete or unqualified daily history')
    if not np.isfinite(frame[['open', 'close']]).all().all() or (frame[['open', 'close']] <= 0).any().any():
        raise ValueError('Invalid SPY prices')
    quantity = 4000. / (float(frame.open.iloc[0]) * 1.0008)
    curve = quantity * frame.close
    curve.name = 'SPY · achat-conservation (hors dividendes)'
    return curve, dict(initial_equity=4000., entry_date=str(index[0].date()),
        entry_price=float(frame.open.iloc[0]), fractional_quantity=quantity, entry_fee_rate=.0008,
        final_equity=float(curve.iloc[-1]), return_pct=float(100 * (curve.iloc[-1]/4000. - 1)),
        dividends_included=False, exit_fee=False, marked_open_holding=True,
        source=str(file), data_source=sorted(frame.data_source.unique().tolist())), {
            str(file):digest(file), str(INPUTS/'manifest.json'):digest(INPUTS/'manifest.json')}


def main():
    series, summaries, sources = load_cases()
    spy, benchmark, other_sources = spy_curve(series[0][1].index)
    sources.update(other_sources)
    series.append(('SPY · hors dividendes', spy, '#424b57', ':'))
    summaries.append(dict(label=series[-1][0], final_equity=benchmark['final_equity'],
        return_pct=benchmark['return_pct'], max_drawdown_intraday_pct=None, source=benchmark['source']))
    OUTPUT.mkdir(parents=True, exist_ok=False)
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':12, 'text.parse_math':False,
        'axes.spines.top':False, 'axes.spines.right':False, 'axes.edgecolor':'#b8c1cd',
        'xtick.color':'#475467', 'ytick.color':'#475467', 'savefig.facecolor':'white'})
    fig, ax = plt.subplots(figsize=(14, 10), dpi=155)
    fig.subplots_adjust(left=.09, right=.96, top=.77, bottom=.32)
    fig.text(.09, .95, 'Évolution du capital — variantes terminées et SPY',
        fontsize=21, weight='bold', color='#172b4d')
    fig.text(.09, .904, '02/01/2020 → 31/12/2024 · capital initial 4 000 $ · sans levier', color='#344054')
    fig.text(.09, .869, 'Oracle TOP20 : positions complètes · minimum 70 $ · sans TP ni trailing · sortie open21',
        color='#475467', fontsize=11)
    for label, values, color, style in series:
        ax.plot(values.index, values.values, label=label, color=color, lw=1.65, linestyle=style)
    ax.axhline(4000., color='#98a2b3', lw=.9, linestyle=':', zorder=0)
    ax.set_ylim(bottom=0)
    ax.set_xlim(series[0][1].index[0], series[0][1].index[-1])
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f'{v:,.0f}'.replace(',', ' ')))
    ax.set_ylabel('Capital valorisé ($)', labelpad=12)
    ax.set_xlabel('Date', labelpad=8)
    ax.grid(axis='y', color='#e4e7ec', lw=.7)
    ax.set_axisbelow(True)
    ax.legend(loc='lower left', bbox_to_anchor=(-.005, 1.015), ncol=3, frameon=False, fontsize=11)
    fig.text(.09, .235, 'Variante', color='#475467', fontsize=11)
    fig.text(.70, .235, 'Capital final', color='#475467', fontsize=11, ha='right')
    fig.text(.91, .235, 'Rendement cumulé', color='#475467', fontsize=11, ha='right')
    for i, ((label, _, color, style), summary) in enumerate(zip(series, summaries)):
        y = .205 - i * .028
        fig.lines.append(plt.Line2D([.09,.12], [y,y], transform=fig.transFigure, color=color, linestyle=style, lw=2))
        fig.text(.13, y, label, va='center', fontsize=11, color='#344054')
        fig.text(.70, y, money(summary['final_equity'])+' $', va='center', ha='right', fontsize=11, color='#344054')
        fig.text(.91, y, f"{summary['return_pct']:+.2f} %".replace('.', ','), va='center', ha='right', fontsize=11, color='#344054')
    fig.text(.09, .047, 'Clôtures quotidiennes : cash + positions ouvertes ; frais de stratégie inclus. SPY : achat à l’ouverture initiale,',
        fontsize=10, color='#475467')
    fig.text(.09, .026, 'frais d’entrée 0,08 %, dividendes exclus. Variantes pause20 encore en cours, non affichées. Études exploratoires.',
        fontsize=10, color='#475467')
    png = OUTPUT/'variantes-terminees-et-spy.png'
    svg = OUTPUT/'variantes-terminees-et-spy.svg'
    fig.savefig(png, dpi=155)
    fig.savefig(svg)
    plt.close(fig)
    daily = pd.DataFrame({label:values for label,values,_,_ in series})
    daily.to_csv(OUTPUT/'capital-daily.csv', index_label='date')
    pd.DataFrame(summaries).to_csv(OUTPUT/'summary.csv', index=False)
    receipt = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
        source_script={str(Path(__file__)):digest(__file__)}, currency='USD', daily_points=len(daily),
        benchmark=benchmark, summary=summaries, includes_open_positions=True, no_new_backtest=True,
        completed_variants_only=True, comparable_minimum_notional=70.,
        files={p.name:digest(p) for p in OUTPUT.iterdir() if p.is_file()})
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(dict(image=str(png.resolve()), summary=summaries), ensure_ascii=False))


if __name__ == '__main__':
    main()
