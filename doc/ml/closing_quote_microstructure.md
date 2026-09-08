# Microstructure de clôture après Oracle TOP20

## Statut et verdict

Expérience terminée le 7 septembre 2026 sur H3, H5, H10 et H20.

**Verdict : `NO_GO_CLOSING_QUOTE_IEX`.** La couverture est excellente, mais
aucune famille microstructure directionnelle indépendante ne franchit les gates.
La dernière quote IEX de la séance ne permet pas de séparer D1 de D10 dans le
pool Oracle TOP20 avec une force exploitable.

Ce verdict ferme uniquement les snapshots quotidiens actuels. Il ne ferme pas
une future piste fondée sur trades signés, NBBO/SIP séquentiel, carnet d'ordres,
pré-market ou opening range, car ces données ne sont pas présentes localement.

## Question testée

Après que l'Oracle a identifié les 20 % de candidats à plus forte amplitude,
les informations de la dernière quote disponible à la clôture J apportent-elles
un indice stable sur le sens du rendement futur ?

Le contrat causal est :

```text
dernière quote IEX de la séance J, horodatée au plus tard à 16:00 ET
        ↓
calcul du signal après clôture J
        ↓
première entrée autorisée à J+1
        ↓
direction réalisée à H3 / H5 / H10 / H20
```

Aucune information postérieure à 16:00 ET n'est admise. Une quote dont la date
locale ne correspond pas à la séance ou dont le timestamp dépasse la clôture
est invalidée.

## Sources et population

| Élément | Contrat |
|---|---|
| Pool | Oracle TOP20 OOF du batch `model-factory-20260904192500-0802c8` |
| Panel Oracle | `oracle_top20_screener_panel.parquet`, déjà pré-sélectionné ; aucun second ranking |
| Labels | exports Parquet recalculés avec le correctif qualité |
| Quotes | `stock_quote_snapshots`, Alpaca/IEX, une dernière quote par symbole et séance |
| Fenêtre | 2022-01-01 au 2025-12-31 |
| Population | 68 660 couples date/symbole, 883 séances |
| Quotes chargées | 391 976 |
| Couverture valide | 88,80 % |
| Couverture à moins de 15 minutes de la clôture | 87,54 % |

Couverture par année :

| Année | Lignes du pool | Quotes valides | Couverture | ≤ 15 min clôture |
|---:|---:|---:|---:|---:|
| 2022 | 18 833 | 15 509 | 82,35 % | 81,70 % |
| 2023 | 19 534 | 16 773 | 85,87 % | 85,18 % |
| 2024 | 19 908 | 18 486 | 92,86 % | 90,36 % |
| 2025 | 10 385 | 10 199 | 98,21 % | 97,13 % |

## Features évaluées

Sept variables brutes, leur z-score temporel causal sur 60 séances — moyenne et
écart-type calculés uniquement sur les jours antérieurs — et leur rang
cross-sectionnel du jour, soit 21 features :

- `spread_bps` : coût instantané bid/ask ;
- `size_imbalance = (bid_size-ask_size)/(bid_size+ask_size)` ;
- `microprice_minus_mid_bps` : déplacement du microprice par rapport au mid ;
- `bid_depth_share` : part de la profondeur affichée au bid ;
- `log_quoted_depth_usd` : niveau de profondeur cotée ;
- `quote_mid_minus_close_bps` : désalignement entre mid IEX et close consolidé ;
- `quote_age_seconds` : ancienneté de la dernière quote avant 16:00 ET.

`bid_depth_share`, `size_imbalance` et `microprice` sont fortement liés et sont
comptés comme une seule famille. Le niveau brut de profondeur et son rang sont
des contrôles de liquidité ; ils ne peuvent pas, à eux seuls, valider une alpha
microstructure. Seul leur z-score intra-symbole est admissible comme dynamique.

## Gates préfixés

Une découverte exige simultanément :

1. couverture globale ≥ 60 % ;
2. couverture de chaque année ≥ 40 % ;
3. au moins trois folds avec IC calculable ;
4. signe de l'IC stable ;
5. `abs(IC décile) >= 0,02` ;
6. `abs(AUC direction - 0,50) >= 0,015` ;
7. au moins deux familles indépendantes satisfaisant ces seuils.

Passer ce gate aurait seulement autorisé une validation OOF multivariée, jamais
une intégration production directe.

## Résultats multi-horizons

Les variables véritablement signées restent pratiquement au hasard :

| Horizon | AUC size imbalance | AUC microprice | Meilleure dynamique admissible | AUC | IC | Stabilité |
|---:|---:|---:|---|---:|---:|---|
| H3 | 0,4977 | 0,4978 | âge quote z60 | 0,5040 | 0,0070 | oui, mais effet trop faible |
| H5 | 0,4953 | 0,4955 | âge quote z60 | 0,5040 | 0,0078 | non |
| H10 | 0,4979 | 0,4982 | âge quote z60 | 0,5078 | 0,0135 | non |
| H20 | 0,4966 | 0,4970 | âge quote z60 | 0,5068 | 0,0154 | non |

Aucun horizon ne produit une famille qualifiée, encore moins deux familles
indépendantes. Le gate final échoue donc quatre fois.

## Le faux positif de profondeur

À H20, `log_quoted_depth_usd` brut donne une AUC de 0,4761, soit 0,5239 si on
inverse son orientation, avec un IC de -0,0483 stable sur quatre années. Son
rang cross-sectionnel montre la même chose.

Ce résultat ne valide pas la microstructure :

- les deux colonnes décrivent la même variable ;
- la profondeur brute encode surtout taille, prix et liquidité du symbole ;
- son z-score temporel intra-symbole retombe à AUC 0,4979, IC -0,0035, signe
  instable ;
- les vrais indicateurs signés de carnet restent autour de 0,50.

Le premier gate, qui comptait naïvement niveau et rang comme deux features, a
été corrigé et couvert par un test de non-régression.

## Artefacts

- [H3](../../artifacts/research/microstructure_directional/closing-quote-h3-20260907-0802c8/report.json)
- [H5](../../artifacts/research/microstructure_directional/closing-quote-h5-20260907-0802c8/report.json)
- [H10](../../artifacts/research/microstructure_directional/closing-quote-h10-20260907-0802c8/report.json)
- [H20](../../artifacts/research/microstructure_directional/closing-quote-20260907050454-0802c8/report.json)
- [Labels corrigés](../../artifacts/research/label_quality/model-factory-20260904192500-0802c8-h20-quality.parquet)

Le harnais reproductible est
`modelFactory/directional_data_research/closing_quote_microstructure.py`.

## Décision

- Ne pas ajouter ces 21 features aux modèles LONG/SHORT.
- Ne pas entraîner un modèle multivarié sur ces snapshots : le gate univarié
  préalable échoue sur tous les horizons.
- Conserver la profondeur cotée comme variable de liquidité/qualité d'exécution,
  pas comme signal directionnel.
- Les séquences NBBO/SIP et trades signés de clôture ont depuis été collectées
  via Eroya puis rejetées : le flux simple/accéléré échoue les gates et le score
  d'épuisement 5 minutes ne se réplique pas sur 400 dates disjointes. Voir
  [flux signé](signed_trade_flow_pilot.md) et
  [prix/liquidité tick](tick_price_liquidity_audit.md).
- L'expérience distincte sur les barres Eroya 5 minutes de la séance complète
  est terminée. Sur 330 séances exploitables, aucun signal directionnel ne
  passe ; la volatilité réalisée atteint AUC amplitude 0,56 et IC 0,18 mais
  échoue la correction Bonferroni à 0,30. Voir [trajectoire intraday de
  séance](intraday_session_path_pilot.md). EODHD ne justifie plus de répéter le
  même contrat avec une autre source.
- Les messages d'auction imbalance MOC/LOC seraient une autre donnée nouvelle,
  mais ils ne figurent pas dans le catalogue Eroya actuel et ne doivent pas
  être approximés à partir du NBBO.
- Le contexte intraday commun SPY/QQQ/IWM/VXX a également été testé : aucune
  direction et aucune amplitude ne passent les gates corrigés. Voir
  [contexte intraday marché](intraday_market_context_pilot.md).
