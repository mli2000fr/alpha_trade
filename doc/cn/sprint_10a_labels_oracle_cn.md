# Sprint 10-A — Labels Oracle CN_A H5/H10/H15/H20

## Objet et frontières

Le Sprint 10-A construit des **cibles futures de recherche**, sans entraîner
de modèle, sans prédiction et sans backtest. La population est figée par les
panels annuels `cn_price_v1` validés au Sprint 9, eux-mêmes issus des
snapshots d'univers PIT du Sprint 8. Le code et la configuration refusent le
marché US et la base autre que `alpha_trade_cn`.

Sources :

- [politique de labels](../../config/labels_cn.yaml) ;
- [calcul et provenance](../../modelFactory/cn_oracle_labels.py) ;
- [commande](../../dataIntegrityEngine/cn_sprint10a_labels.py) ;
- [tests](../../tests/test_sprint10a_cn_labels.py).

Les labels sont des artefacts Parquet de recherche sous
`artifacts/cn/labels/cn_oracle_labels_v1/`. Aucune table n'est créée ou
modifiée ; aucune migration Alembic n'est nécessaire à cette étape.

## Temps du signal, prix et disponibilité

La décision du candidat a lieu **avant l'ouverture de J**, à partir des
features connues au plus tard à cette décision. Par conséquent, la cible
commence au **prix d'ouverture observé de J**. Pour H séances du calendrier
CN, la sortie est le **close de J+H**. Le label ne devient utilisable pour
l'entraînement qu'à l'ouverture de la **séance CN suivante**, J+H+1 :
`available_date` et `available_at_utc` sont conservés. Les folds futurs
devront imposer `available_at_utc < début du fold` pour toute ligne de
train. Aucun prix de J n'entre dans les features pré-ouverture du Sprint 9.

Ce retour est une **cible de prix**, pas un PnL réalisable : T+1, lots,
coûts, limites et liquidité relèvent du Sprint 12. Le retour brut
`close[J+H]/open[J]-1` est conservé pour audit. Le retour économique de
label compose `close[J]/open[J]` avec les `daily_return` canoniques de
J+1 à J+H. Ces derniers sont calculés par BaoStock
`close/pre_close-1`, donc tiennent compte du `pre_close` ajusté aux
événements de facteur. Les barres de toute la trajectoire, et les facteurs
effectivement consultés, doivent avoir été disponibles avant
`available_at_utc`.

## Ajustements, suspensions et limites

Un événement de facteur n'est **pas** un motif d'exclusion automatique :
cela censurerait ex post les actions à dividende ou division et fausserait
les déciles. Il est vérifié à sa date à partir du dernier close effectivement
négocié :

```text
pre_close attendu = dernier close négocié × facteur précédent / facteur nouveau
tolérance = max(0,02 CNY ; 0,5 % du pre_close attendu)
```

Si cette relation n'est pas vérifiable, le label est mis en quarantaine
`UNVERIFIED_FACTOR_ADJUSTMENT`. Si elle l'est, le label reste dans la coupe
transversale ; `path_factor_event` en conserve la trace. Les barres manquantes,
suspensions ou conflits de statut, rendements quotidiens absents et révisions
publiées trop tard sont aussi en quarantaine avec une raison explicite.
Les lignes de fin 2025 sans J+H ou sans séance de disponibilité restent dans
l'artefact mais ne reçoivent pas de label exploitable : ce n'est pas un
rendement nul.

Les limites CN sont **dérivées, non officielles**. Un verrouillage ou une
limite inconnue est enregistré dans les flags de trajectoire et dans
`execution_data_eligible`, mais **ne retire pas le retour du calcul
D1–D10** : supprimer après coup les limit-up/limit-down écarterait précisément
certains mouvements extrêmes. `execution_data_eligible` est un indicateur
de qualité d'exécution, pas une garantie de fill.

## Déciles et cible amplitude

Pour chaque séance J et horizon H, on classe uniquement les rendements dont
`target_quality_valid=1`. Une coupe de moins de 20 titres reçoit la raison
`INSUFFICIENT_RANK_UNIVERSE` et aucun décile. Les rangs percentiles sont
intra-date et intra-marché CN, jamais comparés aux actions US :

- `D1` : environ les 10 % de rendements les plus bas ;
- `D10` : environ les 10 % les plus hauts ;
- `oracle_extreme20` : D1 ou D10, cible d'amplitude sans sens directionnel.

Le calcul utilise les candidats PIT **avant** connaissance des labels. Les
motifs de quarantaine, la taille de la coupe et les dix effectifs de décile
sont publiés dans chaque rapport ; une couverture faible ne doit jamais être
masquée par le seul score Oracle.

## Lancement, provenance, reprise

Essai borné :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m dataIntegrityEngine.cn_sprint10a_labels --year 2024 --start-date 2024-06-03 --end-date 2024-06-07
```

Année complète :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m dataIntegrityEngine.cn_sprint10a_labels --year 2024
```

Chaque run émet quatre Parquet `h5/h10/h15/h20.parquet` et un
`report.json`. Le nom dépend de l'année, de la période, du SHA du panel de
features source, de la configuration et du code. Les SHA des quatre sorties
sont enregistrés. Une réexécution identique garde les artefacts ; un
contenu divergent au même emplacement est refusé.

## Gate avant Sprint 10-B

Le [bilan 2018–2025](./sprint_10a_validation_2018_2025.md) documente
l'audit consolidé `PASS_LABELS_PRICE_ONLY`, les effectifs par horizon et les
limites d'interprétation.

Construire les huit années 2018–2025, puis auditer : population identique
au Sprint 9 par année et horizon, disponibilité strictement postérieure
à l'issue, raisons de quarantaine, stabilité des déciles et couverture
des trajectoires mûres. Les derniers jours de 2025 seront censurés faute
de barres 2026. Après ce gate seulement : pré-enregistrement du protocole
walk-forward et entraînement Oracle/Ranking. Aucun résultat D1/D10 ou
performance de modèle n'est inféré des labels seuls.
