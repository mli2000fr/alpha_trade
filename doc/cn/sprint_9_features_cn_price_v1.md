# Sprint 9 — Panel de features CN_A `cn_price_v1`

## Périmètre et état

Le Sprint 9 construit un **panel de recherche price-only, point-in-time**, à partir de
l'univers quotidien validé au Sprint 8. Il ne lance ni entraînement, ni prédiction,
ni backtest et n'altère aucune table métier. L'artefact est un Parquet accompagné
d'un rapport JSON. Le marché US n'est pas interrogé : le routeur exige
`CN_A/cn_primary` et la base `alpha_trade_cn`.

Implémentation : [moteur](../../modelFactory/cn_feature_panel.py),
[CLI](../../dataIntegrityEngine/cn_sprint9_features.py),
[profil](../../config/features_cn/cn_price_v1.yaml) et
[tests](../../tests/test_sprint9_cn_features.py).

## Contrat de temps et population

Pour une décision d'univers prise avant l'ouverture de la séance J, seules les
lignes `cn_universe_decisions` de statut `CANDIDATE` du run `COMPLETED`
ayant l'empreinte de la politique `config/universe_cn.yaml` sont retenues.
La barre du titre et celle du CSI 300 proviennent du **jour de bourse antérieur**,
jamais de J. Le moteur rejette un `asof_date >= session_date`, une décision
d'univers publiée tardivement, une barre du titre ou du benchmark dont
`available_at > decision_at`, ainsi que des clés `(session_date,instrument_id)`
dupliquées. Les limites de prix du jour précédent sont masquées si leur
`available_at` dépasse le moment de décision.

L'historique de 252 séances précédentes est chargé pour les fenêtres longues.
Les opérations de rolling sont faites séparément par `instrument_id`. Les
rangs, breadth et dispersion sont recalculés par **date J sur les seuls candidats
de cette date**. L'identité de l'artefact incorpore les paramètres, la période,
la liste des runs d'univers source ainsi que les SHA du code et des profils.
Une réexécution à entrées identiques vise le même répertoire ; si le Parquet y
diffère, le moteur refuse de l'écraser. Son SHA-256 est publié.

## Familles de features

| Famille | Colonnes | Construction et prudence |
| --- | --- | --- |
| Rendements/momentum | `return_1/3/5/10/20/60` | Composition des `daily_return` passés, pas de close futur. |
| Tendance | `sma20/50/200_distance` | Prix brut relatif à sa moyenne ; fenêtre masquée si événement de facteur non classifié. |
| Volatilité/range | `atr20_pct`, `realized_vol20`, `range20_position`, `position_52w` | ATR/range et volatilité des 20 séances, position dans la fenêtre de 252 séances ; les positions prix sont masquées autour des facteurs. |
| Volume/liquidité | `volume_ratio20`, `amount_mean20_cny` | Rapport volume/moyenne et montant négocié moyen en CNY. |
| Gap | `overnight_gap` | Open connu à J−1 rapporté au pre-close de J−1 ; signal destiné à la décision J. |
| Marché relatif | `benchmark_return_20`, `benchmark_vol20`, `relative_return_20` | CSI 300 BaoStock `sh.000300` uniquement. Aucune référence implicite à SPY. |
| Coupe transversale CN | `cn_return20_rank`, `cn_vol20_rank`, `cn_breadth_1`, `cn_dispersion_1` | Rang et statistiques parmi les candidats PIT de la séance ; masqués si effectif insuffisant. |
| Microstructure quotidienne | `prior_limit_unknown`, `prior_limit_locked`, `prior_suspended`, `prior_st` | État connu sur la barre/limite précédente ; `prior_st` lit `is_special_treatment`. Une limite dérivée n'est pas présentée comme règle officielle. |
| Board | `board_code`, `board_sh_main/sz_main/star/chinext` | Déduit du code BaoStock, sans l'employer comme identifiant de titre. |
| Secteur | `sector_code`, `sector_return20_rank`, `mask_sector` | **Indisponible.** `SW_2021` est déclaré comme taxonomie cible, mais aucune appartenance sectorielle historique PIT n'existe. Champs NULL/NaN et masque 0. |

Les masques `mask_price20`, `mask_benchmark` et `mask_sector` permettent
de distinguer une observation valide d'une valeur imputée. Les flags
`factor_event_recent20/252` signalent les fenêtres affectées par un
ajustement de prix. Aucun remplissage par zéro d'une feature manquante.
Le taux de rotation des actions (`turnover` en pourcentage du flottant) n'est
**pas** produit : la table canonique possède volume et montant en CNY, mais
pas de nombre d'actions flottantes PIT fiable pour former le dénominateur.

## Lancement et sorties

Exemple borné :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m dataIntegrityEngine.cn_sprint9_features --start-date 2024-06-03 --end-date 2024-06-07
```

Pour l'historique complet, lancer **une année à la fois** afin de borner
la mémoire. Les fichiers sont sous
`artifacts/cn/features/cn_price_v1/cn-feature-AAAAMMJJ-AAAAMMJJ-<empreinte>/` :
`panel.parquet` et `report.json`. Le rapport détaille effectifs, couverture
des familles, taux de NaN, boards, colonnes constantes et SHA-256. Les colonnes
de provenance conservent `decision_at`, `source_available_at`,
`bar_available_at`, `benchmark_available_at` et `limit_available_at`.
Les corrections éventuelles d'une barre historique sont également couvertes
par `max_input_available_at` et `benchmark_max_input_available_at` : toutes
les entrées de la fenêtre doivent être connues avant la décision.

Après avoir produit les années 2018–2025, exécuter :

```powershell
F:\projets\.venv\Scripts\python.exe -m dataIntegrityEngine.cn_sprint9_audit
```

L'audit recherche exactement un artefact par année pour la version courante
du moteur, revérifie chaque SHA-256, l'identité du schéma, l'absence de clés
dupliquées ou de données tardives et les seuils minimaux prix/benchmark.
Il écrit aussi `artifacts/cn/features/sprint9_audit_2018_2025.json`.
Le verdict `PASS_PRICE_ONLY` **ne valide ni le secteur ni le turnover**.

## Limites et gate

Le panel est **une baseline de recherche**. Le secteur PIT reste bloquant pour
toute affirmation de neutralisation sectorielle ; il ne faut pas le reconstruire
à partir de la classification actuelle. Les moyennes et positions de prix bruts
peuvent avoir une faible couverture lorsque des facteurs d'ajustement sont
présents : contrôler `missing_fraction` et `factor_event_recent252_fraction`
avant l'entraînement. Le rapport `research_ready_price_only` n'affirme que
la couverture minimale prix/benchmark, pas une performance ML.

Gate avant Sprint 10 : années 2018–2025 construites, SHA reproductibles,
absence de doublons et de fuite PIT, qualité ventilée par année et board,
et décision explicite sur les familles à forte indisponibilité. Aucun résultat
directionnel D1/D10 n'est déduit du présent sprint.
