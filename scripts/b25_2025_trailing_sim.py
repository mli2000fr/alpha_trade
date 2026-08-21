import pandas as pd
import numpy as np

tr = pd.read_csv("artifacts/backtesting/b25_2025_rankw/trades.csv")
ts = tr[tr["exit_reason"] == "trailing_stop"].copy()
ts["is_win"] = ts["return_pct"] > 0
ts["is_loss"] = ts["return_pct"] < 0

# Reconstruction du R-multiple : on n'a pas l'ATR par trade, mais on a entry/exit price
# et le trailing = 7% (ts=0.07) avec activation 0R.
# Pour un buy: le trailing sort si prix recule de 7% depuis le plus haut.
# Pour un sell: le trailing sort si prix monte de 7% depuis le plus bas.
# On ne peut pas savoir le pic atteint (intrabar), mais on peut estimer:
#   - les pertes <=2j sorties à ~-4/-6% => le prix n'a JAMAIS monté de 7% -> trailing
#     non activé "utilement", c'est un stop effectif serré.
# Hypothèse test: avec une activation différée (ex: trailing ne s'arme qu'après
# +1R / +2R), les trades qui n'ont jamais atteint ce seuil resteraient ouverts.

# On simule 3 scénarios d'activation différée sur les pertes trailing_stop:
#  - A: trailing arme dès le 1er jour en gain (implicitement déjà le cas)
#  - B: activation à +3% (avant d'activer le trailing, on laisse marge)
#  - C: activation à +5%
# Pour chaque perte, on regarde return_pct et holding_days: si le trade est sorti
# en perte <= 2j avec une perte ~>= 3%, c'est qu'il n'a probablement jamais monté
# de 3%+ -> avec activation B/C il ne serait PAS encore sorti (au pire time_stop).
# NB: approximation conservative (on n'a pas le pic intrabar).

losses = ts[ts["is_loss"]].copy()
print("=== 62 pertes trailing_stop ===")
print("pertes totales pnl:", losses["pnl"].sum())

def sim(activation_pct):
    # trades sortis en perte, dont la perte dépasse l'activation => n'ont pas atteint
    # le seuil d'activation => resteraient ouverts (on les retire des pertes)
    # Les autres (perte < activation) ont pu toucher le seuil et retomber -> inchangés
    # Approximation: on retire de la perte les trades dont |return| > activation ET <= 2j
    # (trop rapides pour avoir monté de activation avant de chuter)
    fast = losses[(losses["return_pct"] < -activation_pct) & (losses["holding_days"] <= 2)]
    return fast

for act in [0.03, 0.05, 0.07]:
    fast = sim(act)
    print(f"\n--- activation trailing à {act*100:.0f}% ---")
    print(f"  pertes qui n'auraient probablement PAS été activées (sorties <=2j, |perte|>={act*100:.0f}%): n={len(fast)}")
    print(f"  pnl de ces pertes: {fast['pnl'].sum():.0f}")
    print(f"  => pertes totales après retrait: {losses['pnl'].sum() - fast['pnl'].sum():.0f}")

# Détail: répartition des 62 pertes par signe du retour et délai
print("\n=== détail pertes trailing par holding ===")
for hb, sub in losses.groupby(pd.cut(losses["holding_days"], bins=[0,2,5,10,60], labels=["0-2j","3-5j","6-10j",">10j"]), observed=True):
    print(f"  {hb}: n={len(sub)} | pnl={sub['pnl'].sum():.0f} | return_moy={sub['return_pct'].mean():.2f}%")
