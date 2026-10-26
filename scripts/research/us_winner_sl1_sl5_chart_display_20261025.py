"""Display correction only: literal dollar signs, no mathematical text parsing."""
from pathlib import Path

from scripts.research import us_winner_sl1_sl5_chart_20261025 as chart


if __name__=='__main__':
    chart.OUTPUT=Path('artifacts/research/us_winner_sl1_sl5_visuals/20261025-v2')
    chart.plt.rcParams['text.parse_math']=False
    chart.main()
