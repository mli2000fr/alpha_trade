# Microstructure, coûts et résolution intrabar

Retour : [références Backtesting](README.md)

`ExecutionModelConfig`, `SlippageConfig` et `MicrostructureConfig` figent le contrat. `compute_adv_usd` mesure la capacité. `should_skip_entry_for_gap` bloque un open trop éloigné. `compute_execution_price` applique spread et impact contre le trader. `should_split_order` borne la participation.

`resolve_intrabar_exit` traite une barre touchant stop et TP. En mode conservative, il choisit l'issue défavorable. Avec OHLC daily, l'ordre des touches est inconnu : le rapport doit annoncer cette hypothèse.

Les coûts incluent spread réel/fallback, slippage volume-aware et commissions. Appliquer à entrées/sorties, longs/shorts et sorties forcées. Un fallback doit être sérialisé. Le gap filter, initial stop, TP, trailing, activation, time-stop et entry timing constituent ensemble le lifecycle.

Tests minimaux : gap seuil, achat/vente orientation, stop+TP même barre, volume nul, ordre au-dessus capacité, fractional, commission tier et gap à travers stop.

## Configuration

`ExecutionModelConfig` définit timing/prix et hypothèses de fill. `SlippageConfig` porte spread/impact. `MicrostructureConfig` agrège capacité, gap et intrabar. Toutes les valeurs effectives doivent apparaître dans `microstructure_params` du report.

## ADV et participation

`compute_adv_usd` calcule une moyenne de `close * volume` sur la fenêtre disponible avant décision. Une ADV nulle/manquante ne peut pas justifier une grosse taille ; fallback reject/cap doit être explicite. La participation est notional/ADV.

## Gap d'entrée

Le gap compare prix d'ouverture/exécution à la référence décisionnelle avec orientation selon côté. Au-delà du seuil, l'entrée est skipped. Un seuil 0 peut signifier désactivation selon contrat ; le report doit le préciser.

## Spread

Avec bid/ask, le prix acheteur subit ask/half-spread et vendeur bid. Sans quote, un fallback bps configuré peut s'appliquer. Spread zéro par défaut non annoncé surévalue la stratégie.

## Impact volume-aware

L'impact augmente avec la participation et se déplace contre l'ordre. Les paramètres doivent être calibrés sur TCA et bornés. Un impact symétrique en bps produit des signes opposés achat/vente mais toujours un coût économique.

## Fractionnement

`should_split_order` décide selon taille/ADV. Un ordre fractionné doit répartir quantité et coûts sur des fills/séances conformément au modèle ; il ne peut pas bénéficier du prix complet du premier jour si le volume est insuffisant.

## Intrabar

`IntraBarResolution` formalise la politique. Cas long : low touche stop et high touche TP dans la même barre ; conservative prend le stop. Cas short inverse. Un gap à travers stop se remplit au prix de marché/gap selon modèle, pas forcément au stop théorique.

## Commissions

Les tiers dépendent du notionnel/quantité selon configuration. Appliquer one-way à chaque fill, y compris exits et cash-in-lieu si le modèle le prévoit. Éviter de compter spread deux fois si le prix simulé est déjà bid/ask.

## Rapport de coûts

Séparer commission, spread, slippage impact, gap et total. Agréger dollars, bps, par côté, symbole, période et participation. Comparer aux TCA paper/live pour recalibrer.

## Sensibilité

Tester au moins base, spread/impact x2, capacité réduite, gap plus strict et intrabar conservative. Une stratégie rentable uniquement avec coûts nuls ne passe pas la promotion.
