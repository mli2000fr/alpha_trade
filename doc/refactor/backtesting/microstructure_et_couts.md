# Microstructure, coûts et résolution intrabar

Retour : [références Backtesting](README.md)

`ExecutionModelConfig`, `SlippageConfig` et `MicrostructureConfig` figent le contrat. `compute_adv_usd` mesure la capacité. `should_skip_entry_for_gap` bloque un open trop éloigné. `compute_execution_price` applique spread et impact contre le trader. `should_split_order` borne la participation.

`resolve_intrabar_exit` traite une barre touchant stop et TP. En mode conservative, il choisit l'issue défavorable. Avec OHLC daily, l'ordre des touches est inconnu : le rapport doit annoncer cette hypothèse.

Les coûts incluent spread réel/fallback, slippage volume-aware et commissions. Appliquer à entrées/sorties, longs/shorts et sorties forcées. Un fallback doit être sérialisé. Le gap filter, initial stop, TP, trailing, activation, time-stop et entry timing constituent ensemble le lifecycle.

Tests minimaux : gap seuil, achat/vente orientation, stop+TP même barre, volume nul, ordre au-dessus capacité, fractional, commission tier et gap à travers stop.

