# 5. Page 📊 Screening — l'univers des candidats

## À quoi sert cette page

Consulter la table `stock_scores` produite par les étapes Screener +
Selector du pipeline. Vous voyez, classés par score, les actions que
l'application juge intéressantes pour les prochains jours.

## Quand l'utiliser

- Le matin pour comprendre **pourquoi** telle action est en haut du classement.
- Avant un backtest, pour vérifier que l'univers n'est pas vide.
- Quand votre Risk renvoie 0 décision : peut-être qu'il n'y a aucun candidat.

## Lecture du tableau principal

Colonnes principales :

| Colonne | Signification |
|---|---|
| `symbol` | Ticker (ex. AAPL, MSFT) |
| `final_score` | Score 0-100 du Selector (technique pure) |
| `final_score_sentiment` | `final_score` ajusté par le sentiment news |
| `is_candidate` | `True` = passe tous les filtres |
| `close` | Dernier cours de clôture |
| `dollar_volume_20d` | Liquidité moyenne 20 jours (USD) |
| `atr_pct_20` | Volatilité moyenne 20 jours en % |
| `rsi_relative_strength` | Force relative vs SPY (100 = même perf) |
| `high_52w_proximity` | À quel point on est proche du plus haut 52 semaines (1.0 = au plus haut) |
| `sector` | Secteur GICS (Technology, Health Care…) |

> 💡 Cliquez sur l'en-tête d'une colonne pour trier.

## Filtres rapides

En haut du tableau :
- **Secteur** : ne montrer qu'un secteur précis.
- **Score min** : seuil sur `final_score`.
- **Recherche** : tapez un ticker.

## Recommandations automatiques

Encart **« 🎯 Recommandations screener »** : si l'application détecte que vos
filtres sont trop stricts, elle propose des seuils alternatifs (ex.
« Baisser `min_relative_strength_index` de 100 à 95 ferait passer 47
candidats supplémentaires »).

## Cas « Page vide »

Si le tableau est vide :

1. **Vérifiez que le pipeline a tourné aujourd'hui** :
   - Page **🏠 Vue d'ensemble** → bloc « Dernier pipeline ».
   - S'il est ⚪ ou 🔴 : relancer (cf. [04_page_pipeline.md](04_page_pipeline.md)).
2. **Vérifiez votre preset de capital** :
   - Avec `capital_0_2000` vous aurez ~50-150 candidats.
   - Avec `capital_50001_100000` vous pouvez tomber à 5-10 si le marché est baissier.
3. **Date du marché** : vérifiez en haut « Date trade : YYYY-MM-DD ». Si
   c'est un jour férié US, il n'y a pas de nouvelles barres.

## Termes financiers à connaître

- **Liquidité** : capacité à acheter/vendre sans bouger le prix. Mesurée
  ici par `dollar_volume_20d`.
- **Volatilité (ATR)** : amplitude moyenne des variations de prix. Un ATR
  élevé = stock nerveux.
- **Force relative** : performance vs un indice de référence (SPY).
- **Proximité 52w high** : 1.0 = on touche le plus haut de l'année.

> Voir [30_glossaire_financier.md](30_glossaire_financier.md) pour plus de
> définitions.

## Pour aller plus loin

- Modifier les filtres : page **⚙️ Paramètres / Santé** → onglet « Selector ».
- Comprendre le score : [doc technique selector](../backup/selector.md).

