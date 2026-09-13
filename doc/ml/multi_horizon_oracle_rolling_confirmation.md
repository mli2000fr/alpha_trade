# Multi-Horizon Oracle et confirmation rolling

## Statut

`RUN TERMINÉ — WEAK_SIGNAL, PHASE 2 NON OUVERTE`

## Résultat du run du 10 septembre 2026

Artefact :
`artifacts/research/multi_horizon_oracle_rolling/multi-horizon-rolling-20260910141708-d5b30f`.

- contrats et folds : valides, 100 % des lignes ont les mêmes bornes de fold ;
- intersection : 407 882 observations, 1 512 dates et 284 symboles ;
- période réellement couverte : 5 juillet 2018 au 9 juillet 2024 ;
- couverture croisée : 99,999 % du plus petit panel ;
- corrélations de Spearman entre horizons : 0,926 à 0,970 ;
- overlaps moyens MH0–MH3 : 0,80 à 0,92 ;
- tous les contrôles sélection contre REST ont un IC95 traversant zéro ;
- S6-LS : -0,303 % net, IC95 [-1,152 % ; +0,425 %], `NO_GO` ;
- S6-LS LONG : +1,527 % net, mais SHORT : -2,080 % net ; le prix à J+5 ne
  fournit donc pas une règle directionnelle symétrique exploitable ;
- MH3 gagnants J+5, confirmé contre non confirmé : avantage événementiel
  +1,379 %, mais l'écart quotidien a un IC95 [-0,427 % ; +2,528 %] ;
- MH0/H20 gagnants J+5 : écart quotidien +1,412 %, IC95
  [+0,238 % ; +2,738 %] ; c'est le signal exploratoire le plus intéressant ;
- 53,2 % du profit MH0 confirmé provient toutefois du meilleur 1 % des
  observations ; la stabilité annuelle est insuffisante.

Le `GO_RESEARCH` inscrit par la première version du rapport était trop
permissif : il testait le signe moyen et la stabilité, mais pas l'intervalle de
confiance de la valeur incrémentale quotidienne. Le gate a été corrigé pour les
runs suivants. Le verdict de référence de ce run est **WEAK_SIGNAL**.

La phase 2 complète n'est pas ouverte. La seule suite autorisée est un petit
replay challenger pré-enregistré `MH0/H20 + prix positif J+5 + confirmation
Oracle restante`, comparé à H20 seul, sur une période OOS plus récente et un
univers historique PIT. Aucun seuil supplémentaire ne doit être optimisé sur ce
run.

Cette expérience teste si quatre Oracle d'amplitude, entraînés aux horizons
H5, H10, H15 et H20, apportent une information complémentaire et si la
persistance de cette information aux checkpoints J+5/J+10/J+15 permet de mieux
décider de continuer ou d'abandonner un mouvement.

Le protocole complet et pré-enregistré se trouve dans
[`prompt/multi_horizon_oracle_rolling_confirmation_prompt.md`](../../prompt/multi_horizon_oracle_rolling_confirmation_prompt.md).
La section amendée en tête de ce document fait foi en cas de contradiction avec
la proposition historique.

## Ce que l'expérience démontre — et ne démontre pas

Les Oracle prédisent une **amplitude extrême**, sans direction. Les variantes
MH0 à MH3 et les diagnostics S0 à S5 sont donc LONG-only. Ils répondent à la
question : « après une entrée longue, le prix et la persistance de l'Oracle
permettent-ils de distinguer continuation et échec ? » Ils ne prouvent pas que
l'Oracle connaît le sens à J.

S6-LS est la seule branche symétrique : aucune entrée n'est prise à J ; le signe
du mouvement observé au close J+5 détermine LONG ou SHORT, l'Oracle restant doit
encore être confirmé, puis l'entrée a lieu à l'open suivant.

Ce premier run n'est pas un backtest portefeuille. Il n'applique ni allocation,
ni limite de positions, ni stop, ni TP. Son but est de vérifier le signal avant
d'introduire les nombreuses interactions du lifecycle.

## Batches gelés de la campagne

| Horizon | Batch | Features |
|---|---|---:|
| H5 | `model-factory-20260910052522-c1cb2b` | 168 |
| H10 | `model-factory-20260910052532-e60c4e` | 168 |
| H15 | `model-factory-20260910052544-54416f` | 168 |
| H20 | `model-factory-20260910052558-d5b30f` | 168 |

Le programme vérifie l'horizon déclaré dans chaque artefact et refuse le run si
un batch est branché au mauvais endroit. Il compare également les profils de
features, hors horizon, et exige leur identité.

## Univers

Le run utilise `config/univers/univers_filtred_equities.txt`, soit 1 798 actions
au 10 septembre 2026. Son chemin, son nombre de symboles et son SHA-256 sont
inscrits dans le rapport.

Cet univers est un univers courant appliqué à l'historique : il comporte donc un
biais de survivance. Il suffit pour décider si la piste mérite un replay plus
coûteux, mais ne permet pas un `STRONG_GO`. Une validation production exigera
les constituants et critères de tradabilité PIT à chaque date.

## Construction des scores

Les probabilités brutes des horizons ne sont jamais moyennées directement.
Le programme :

1. conserve uniquement les prédictions OOF (`fold_start` renseigné) ;
2. filtre l'univers demandé ;
3. prend l'intersection commune `(date, symbol)` aux quatre batches ;
4. recalcule les percentiles de chaque horizon sur cette même coupe quotidienne ;
5. refuse une intersection inférieure à 70 % du plus petit panel source.

Les entrées sont ensuite définies comme suit :

| Variante | Règle |
|---|---|
| MH0 | percentile H20 ≥ 0,80 |
| MH1 | H5, H10, H15 et H20 tous ≥ 0,80 |
| MH2 | au moins trois horizons sur quatre ≥ 0,80 |
| MH3 | percentile du consensus moyen des quatre horizons ≥ 0,80 |

Une seule position théorique par symbole est admise jusqu'à la liquidation H20.
Un nouveau signal quotidien du même symbole est ignoré pendant cet intervalle.

## Horloge et prix

```text
close J     : score et sélection observables
open J+1    : entrée théorique
close J+5   : checkpoint 5 ; décision exécutée open J+6
close J+10  : checkpoint 10 ; décision exécutée open J+11
close J+15  : checkpoint 15 ; décision exécutée open J+16
open J+21   : liquidation après vingt séances de détention
```

Les OHLC sont ajustés avec le facteur `adj_close / close` afin de neutraliser
les discontinuités de split. Les tableaux publient les rendements bruts, les
rendements nets d'un aller-retour et l'excès contre SPY sur la même horloge.
Les coûts par défaut sont 1 bp de commission et 2 bps de slippage par côté.

## Confirmation rolling

La règle principale est le TOP20 du consensus encore pertinent :

| Checkpoint | Consensus restant |
|---|---|
| J+5 | moyenne des percentiles H5/H10/H15, puis rang quotidien |
| J+10 | moyenne H5/H10, puis rang quotidien |
| J+15 | percentile H5 |

La confirmation vaut vrai quand ce rang est au moins égal à 0,80. Le rapport
conserve aussi l'intersection stricte et `oracle_rank_change`. Ce dernier mesure
une variation de position relative ; il ne doit pas être interprété comme une
baisse absolue de probabilité.

## Artefacts produits

Chaque run crée un dossier sous
`artifacts/research/multi_horizon_oracle_rolling/` contenant :

| Fichier | Contenu |
|---|---|
| `report.json` | manifeste, contrats, couverture, S6-LS, gates et verdict |
| `report.md` | synthèse immédiatement lisible |
| `aligned_predictions.parquet` | quatre scores, percentiles et consensus communs |
| `fixed_origin_events.parquet` | chemins de prix et Oracle aux checkpoints |
| `event_study.csv` | groupes perdant/faible/fort × confirmation rolling |
| `selection_vs_rest_control.csv` | comparaison quotidienne sélection vs REST |
| `score_correlations.csv` | corrélations de Spearman entre horizons |
| `selection_overlaps.csv` | Jaccard quotidien entre MH0–MH3 |
| `s6_ls_events.parquet` | entrées retardées LONG/SHORT et rendement signé |

Aucune table SQL, aucun batch de serving et aucun fichier de configuration ne
sont modifiés.

## Interprétation du verdict

- `EXPERIMENT_INVALID` : contrat d'horizon/profil ou couverture non conforme ;
- `NO_GO` : la confirmation rolling ne fournit pas d'avantage exploitable ;
- `WEAK_SIGNAL` : résultat intéressant mais incomplet ou instable ;
- `GO_RESEARCH` : signal net positif, incrémental, suffisamment soutenu et
  stable par semestre ; il autorise un replay portefeuille de phase 2 ;
- `STRONG_GO` : impossible avec l'univers courant non PIT.

Un `GO_RESEARCH` n'autorise ni le live ni la production. Il ouvre seulement
l'implémentation du replay OHLC avec lifecycle canonique, comparaison cohorte
fixe/survivants, capacité, turnover et coûts complets.

## Commande de la campagne gelée

La commande est volontairement lourde : elle lit quatre panels OOF et les bars
de l'intersection sur toute la période. Elle doit être lancée depuis la racine
du projet dans l'environnement virtuel habituel.

```powershell
python -u -m modelFactory.multi_horizon_oracle_rolling --h5-batch-id model-factory-20260910052522-c1cb2b --h10-batch-id model-factory-20260910052532-e60c4e --h15-batch-id model-factory-20260910052544-54416f --h20-batch-id model-factory-20260910052558-d5b30f --universe-file config/univers/univers_filtred_equities.txt --start-date 2016-01-01 --end-date 2025-12-31 --commission-bps 1 --slippage-bps 2 --bootstrap-samples 2000 --log-level INFO
```

Le programme affiche le chemin du dossier résultat à la fin. La présence de
`report.json` dans ce dossier signifie que le traitement est terminé.

## Variante 2 — maintien rolling H5 jusqu'au TP

Cette variante est un **challenger de recherche isolé**. Elle ne change ni le
backtest principal, ni le live, ni les tables. Elle part uniquement du signal
exploratoire observé sur les événements H20 encore confirmés après cinq séances.

### Contrat causal gelé

```text
close J       : H20 appartient au TOP20 ; aucune position n'est ouverte
close J+5     : le prix J→J+5 est positif ET H5/H10/H15 confirment encore
open J+6      : entrée LONG si le gap absolu ne dépasse pas 3 %
chaque 5 jours: conserver seulement si le PnL net de liquidation reste positif
                ET si le nouvel Oracle H5 du jour appartient encore au TOP20
open suivant  : sortir si l'une des deux conditions échoue
intraday      : stop initial, trailing et TP restent prioritaires
60 séances    : liquidation de sécurité si aucun exit n'est intervenu
```

Le lifecycle appliqué après l'entrée est celui du contrat PROD : stop initial
`2,5×ATR`, TP `min(3×ATR, 7 %)`, trailing risk-based `2,5×ATR` actif à partir de
la séance suivant l'entrée, résolution intrabar conservative, commission 1 bp
et slippage 2 bps par côté. L'ATR est connu avant l'entrée.

### Comparaison obligatoire

Les mêmes entrées sont rejouées avec trois politiques appariées :

1. `fixed_h20` : sortie après 20 séances de détention ;
2. `extended_60_no_rolling` : simple prolongation jusqu'à 60 séances ;
3. `rolling_h5_60` : prolongation jusqu'à 60 séances avec le veto prix + H5.

La valeur du rolling se mesure contre `extended_60_no_rolling`, et non seulement
contre H20. Cela sépare l'effet « laisser davantage de temps au trade » de
l'effet propre de la confirmation H5. Un candidat sans couverture H5 complète
jusqu'à la borne de 60 séances est exclu de la comparaison appariée ; une donnée
manquante n'est jamais interprétée comme un rejet Oracle.

Le verdict `GO_RESEARCH` exige un delta net moyen positif de `rolling_h5_60`
contre `extended_60_no_rolling` et une borne basse de l'intervalle bootstrap
par blocs de dates strictement positive. Le replay reste trade-level : il ne
modélise pas encore capacité, collisions entre positions ou allocation du
portefeuille.

### Commande

```powershell
python -u -m modelFactory.oracle_rolling_lifecycle --phase1-artifact artifacts/research/multi_horizon_oracle_rolling/multi-horizon-rolling-20260910141708-d5b30f --max-holding-sessions 60 --bootstrap-samples 2000 --log-level INFO
```

Le résultat est écrit sous
`artifacts/research/oracle_rolling_lifecycle/oracle-rolling-lifecycle-*`.
Le run est terminé lorsque `report.json` existe.

### Résultat du run du 10 septembre 2026 — `NO_GO`

Artefact canonique :
`oracle-rolling-lifecycle-20260910154636`. Sur 34 972 candidats initiaux,
30 566 disposent du contrat complet commun aux trois politiques ; 3 063 sont
rejetés par le gap d'entrée et 1 343 par une fenêtre future incomplète.

| Politique | Rendement net moyen/trade | Win rate | Détention moyenne |
|---|---:|---:|---:|
| H20 fixe | +0,109 % | 56,52 % | 7,53 séances |
| Extension passive 60 | +0,120 % | 56,88 % | 7,89 séances |
| Rolling prix + H5 | -0,097 % | 47,76 % | 4,94 séances |

L'extension passive contre H20 n'ajoute que `+0,010 %` par trade ; son delta
quotidien apparié est `+0,045 %`, avec IC95 `[-0,013 % ; +0,115 %]`. Elle ne
constitue donc pas une amélioration démontrée. En outre, 95,5 % des trades ont
exactement le même résultat : les stops, trailing ou TP interviennent avant que
la borne H20 contre H60 ne puisse faire une différence.

Le rolling perd `-0,217 %` par trade contre la même extension passive. Le delta
quotidien apparié vaut `-0,286 %`, IC95 `[-0,568 % ; -0,043 %]` : l'infériorité
est statistiquement détectable selon le gate pré-enregistré. La règle rolling
n'améliore le résultat que pour 24,0 % des trades.

L'attribution distingue les deux veto :

- 11 219 sorties `rolling_price_nonpositive`, rendement moyen `-3,92 %` ; les
  conserver comme dans l'extension passive aurait donné `-3,32 %`, soit une
  perte incrémentale de `-0,60 %` sur cette population ;
- 1 597 sorties `rolling_h5_not_confirmed`, encore gagnantes de `+2,61 %` en
  moyenne ; contre l'extension passive, le veto H5 ajoute légèrement `+0,085 %`
  sur cette population, effet trop faible pour promouvoir une règle ;
- 12 171 TP à `+6,94 %` et 5 532 trailing stops à `-8,52 %` sont identiques à
  l'extension passive.

Le principal échec vient donc de la condition **prix net positif obligatoire**,
pas d'une preuve que le rang H5 détruit directement la valeur. La politique
complète est toutefois rejetée. Elle est négative sur 6 semestres sur 12 et son
avantage éventuel n'est ni généralisé ni suffisamment stable. Aucun branchement
dans le backtest, le live ou le serving n'est autorisé.
