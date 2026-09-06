# Modèle directionnel mutualisé sur les événements Oracle

## Statut

Ce module est une **expérience Walk-Forward non servable**. Il ne remplace pas
encore le bundle Oracle + deux branches Per-Symbol dans la prédiction, l’IHM ou
le backtest. La promotion est interdite tant que les gates OOS ci-dessous ne
sont pas satisfaits sur plusieurs périodes indépendantes.

## Pourquoi un modèle mutualisé

Les modèles Per-Symbol conditionnels disposent de peu d’événements Oracle par
ticker. Sur 2026H1, prolonger l’entraînement jusqu’à fin 2025 n’a pas réparé la
branche LONG : le classement directionnel reste négatif avant même le sizing et
les exits. Le modèle mutualisé regroupe au contraire tous les événements Oracle
de tous les symboles dans un seul dataset et peut apprendre des régularités
communes tout en conservant `symbol` et `secteur` comme contexte catégoriel.

## Contrat de population

```text
Univers historique complet
        │
        ▼
Oracle Extreme Walk-Forward strictement OOF
        │
        ▼ top 20 % quotidien par proba_extreme
Événements autorisés pour la direction
        │
        ├── D1  → SHORT (classe 0)
        ├── D10 → LONG  (classe 1)
        └── D2…D9 exclus du fit, mais conservés au test
```

`proba_extreme` est un **gate**, jamais une feature directionnelle. Cette règle
évite que le second modèle réapprenne seulement l’amplitude. Le cache
`_oracle_oof_gate.parquet` est obligatoire ; une ligne non OOF ne peut pas être
utilisée.

## Cible et pondération

La cible binaire répond directement à la mission :

- `0` : futur D1, candidat SHORT ;
- `1` : futur D10, candidat LONG ;
- D2 à D9 : cible absente, donc rejet du fit.

Les lignes D1/D10 sont pondérées par l’amplitude absolue du rendement H20. Le
poids est normalisé par l’amplitude médiane puis borné entre `0,5` et `3,0` pour
éviter qu’un petit nombre de chocs domine entièrement l’apprentissage.

## Features

Le profil canonique V1 se trouve dans
`config/features/shared_direction/shared.json`. Il contient des variables
signées de momentum, tendance, position, RSI, force relative, contexte marché et
rangs cross-sectionnels. Sont explicitement interdits : rendement futur, décile
futur, score Oracle, Global Rank et toute cible.

Deux catégories sont ajoutées :

- `symbol_context` : identité du ticker ;
- `sector_context` : secteur GICS normalisé, `UNKNOWN` si absent.

CatBoost les traite nativement ; aucun entier ordinal artificiel n’est assigné
aux symboles ou secteurs.

Le paramètre expérimental `--context-mode` accepte `symbol_sector`, `sector` ou
`none`. Il sert à détecter une mémorisation excessive des identités. L’option
`--no-amplitude-weighting` constitue l’ablation de la pondération des chocs.

## Walk-Forward et anti-fuite

Les folds sont construits par dates de marché : 504 dates minimales de train,
126 de validation, 126 de test, pas 126, maximum 12. La validation pilote
l’early stopping. Le test produit uniquement les prédictions OOF. La garde
`oracle_available_date` garantit que le rendement H20 d’une ligne de train est
connu avant la validation suivante.

Le modèle final utilise le nombre médian d’itérations choisi dans les folds et
est réentraîné sur toutes les lignes D1/D10 autorisées. Il reste marqué
`research_only=true` et `serving_ready=false`.

## Abstention native

Le modèle brut produit `p = P(D10 | D1 ou D10)`. Pour un futur contrat ternaire :

```text
confiance directionnelle = |2p - 1|
P(FLAT)  = 1 - confiance
P(LONG)  = confiance si p >= 0,5, sinon 0
P(SHORT) = confiance si p <  0,5, sinon 0
```

Les trois valeurs somment à un. Une valeur proche de 0,5 devient donc une vraie
abstention et non un LONG/SHORT faible.

## Métriques de décision

F1 macro n’est pas la métrique souveraine. Le rapport mesure :

1. AUC D10 contre D1 ;
2. IC Spearman quotidien entre score et rendement futur dans le TOP20 Oracle ;
3. précision D10 et contamination D1 du décile LONG ;
4. précision D1 et contamination D10 du décile SHORT ;
5. rendements signés LONG et SHORT ;
6. couverture et exactitude après abstention ;
7. résultats de chaque fold, pas seulement l’agrégat.

Une moyenne positive portée par un seul symbole ou une seule période ne suffit
pas. La promotion exige un IC positif, une purification symétrique D1/D10 et une
majorité de folds favorables, puis une confirmation sur une période non utilisée
pour choisir les paramètres.

## Lancement

Exemple utilisant un batch Oracle déjà entraîné :

```powershell
python -m modelFactory.shared_directional --oracle-batch-id <BATCH_ID> --start-date 2016-01-01 --end-date 2025-12-31 --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12
```

Les artefacts sont écrits sous
`artifacts/models/shared_directional/shared-direction-...` : modèle CatBoost,
contrat, profil, métriques détaillées et prédictions OOF.

## Campagne initiale du 5 septembre 2026

La campagne a utilisé l’Oracle OOF du batch
`model-factory-20260904192500-0802c8` : 127 256 événements TOP20, 268 symboles,
1 764 dates et 9 folds valides. Quatre contrats ne différant que par le contexte
catégoriel ou la pondération ont été comparés.

| Variante | AUC D10/D1 | IC quotidien | LONG D10/D1 | SHORT D1/D10 | Rendement SHORT signé |
|---|---:|---:|---:|---:|---:|
| symbole + secteur, amplitude pondérée | 0,466 | -0,039 | 19,99 % / 19,87 % | 18,66 % / 24,46 % | -3,33 % |
| aucun contexte, amplitude pondérée | **0,503** | **+0,004** | 21,89 % / 19,51 % | 19,17 % / 20,19 % | -2,25 % |
| secteur seul, amplitude pondérée | 0,489 | -0,032 | 21,31 % / 20,39 % | 18,76 % / 24,44 % | -3,62 % |
| symbole + secteur, sans pondération | 0,446 | -0,060 | 17,72 % / 21,71 % | 17,81 % / 26,46 % | -4,45 % |

Verdict : **NO-GO pour les features de prix actuellement disponibles**. Le
contexte symbole/secteur accentue la dérive ; son retrait ramène le modèle au
hasard mais ne crée pas de signal. La pondération d’amplitude n’est pas la cause
du défaut. Le rendement LONG positif de certaines variantes reflète surtout le
biais haussier moyen du pool : l’IC proche de zéro et l’absence de purification
symétrique montrent que le score n’ordonne pas correctement D1/D10.

Le module reste utile pour tester de nouvelles données signées PIT — révisions
d’analystes, flux/options, short interest, surprises et pré-market — sans refaire
le protocole. Le modèle actuel ne doit pas être exposé au serving.

### Objectif pairwise

La variante `--objective pairwise_ranker` remplace la log-loss pointwise par
`PairLogit` groupé par date. Elle demande directement que chaque D10 soit classé
au-dessus des D1 observés le même jour. Son score est un rang brut, pas une
probabilité : l’abstention probabiliste reste donc désactivée jusqu’à une
éventuelle calibration OOS séparée.

La relance finale sans contexte catégoriel, avec le contrat `PairLogit` corrigé,
obtient AUC `0,500`, IC quotidien `+0,006`, D10/D1 du décile LONG
`20,58 % / 19,42 %` et D1/D10 du décile SHORT `22,39 % / 19,51 %`.
Les rendements signés restent insuffisants : `+1,42 %` côté LONG et `-1,51 %`
côté SHORT. Six folds sur neuf dépassent 0,50 en AUC, mais seulement six ont un
IC positif et les rendements changent fréquemment de signe entre les folds. Cette faible
purification instable ne passe pas le gate de promotion. `PairLogit` ne supporte
pas les poids individuels : la pondération d’amplitude est explicitement inactive
pour cet objectif.

## E1 — Rendement signé continu multi-horizons

La cible `signed_return` répond à une question différente de D1/D10 : parmi
tous les événements du TOP20 Oracle OOF, quel titre aura le rendement futur le
plus positif ou le plus négatif à H3, H5, H10 et H20 ? D2–D9 ne sont donc plus
retirés. Pour chaque horizon, le module conserve quatre valeurs distinctes :

1. rendement futur brut ajusté ;
2. rendement futur du SPY ;
3. excess return au SPY ;
4. résidu secteur = excess return moins la médiane excess-SPY du secteur.

Un secteur doit contenir au moins cinq membres à la date considérée. Sinon, la
cible retombe sur l'excess-SPY. Le score Oracle reste exclusivement un gate et
n'est jamais présenté au régresseur.

Les événements GME, SMMT et TAL ont montré que les rendements extrêmes réels
peuvent dépasser plusieurs centaines de pourcents. Une régression RMSE brute
était alors dominée par quelques observations et pouvait produire des scores
supérieurs à 100. Le contrat corrigé winsorise la cible aux quantiles 1 %/99 %,
calculés uniquement sur le train de chaque fold. Les bornes du test ne sont
jamais utilisées pour ajuster le modèle. Les rendements bruts OOS restent non
tronqués dans toutes les métriques économiques.

Commande canonique :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.shared_directional --oracle-batch-id model-factory-20260904192500-0802c8 --start-date 2016-01-01 --end-date 2025-12-31 --target signed_return --horizons 3,5,10,20 --return-residualization spy_sector --sector-min-members 5 --target-winsor-lower 0.01 --target-winsor-upper 0.99 --context-mode none --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12 --iterations 600 --depth 6 --learning-rate 0.03 --log-level INFO
```

Chaque horizon produit son modèle, ses prédictions OOF, ses métriques par fold,
par semestre et par décile de score. Le fichier `campaign.json` regroupe les
quatre contrats. Comme les autres variantes de ce module, E1 reste
`research_only` et `serving_ready=false` tant que les gates OOS ne sont pas
franchis.

### Résultat E1 corrigé du 5 septembre 2026

La campagne `shared-signed-return-20260904234239-0802c8` couvre 86 256
prédictions OOF par horizon et neuf folds. La winsorisation train-only ramène
les scores dans une plage cohérente : de -7,65 % à +17,20 % au maximum sur
H20, contre des scores aberrants dépassant +100 avant correction.

| Horizon | IC brut | IC cible | exactitude signe | rendement LONG | rendement SHORT | folds IC positifs |
|---|---:|---:|---:|---:|---:|---:|
| H3 | -0,000 | -0,002 | 49,31 % | +0,53 % | -0,38 % | 3/9 |
| H5 | -0,008 | -0,008 | 49,36 % | +0,69 % | -0,87 % | 2/9 |
| H10 | +0,004 | +0,003 | 49,56 % | +1,68 % | -0,77 % | 5/9 |
| H20 | +0,001 | -0,006 | 49,56 % | +3,26 % | -1,89 % | 4/9 |

Le rendement moyen du pool Oracle est déjà positif : +0,33 %, +0,54 %,
+1,01 % et +1,85 % respectivement. Après winsorisation des seuls rendements
d'évaluation pour le contrôle de robustesse, le gain du décile LONG sur le pool
n'est plus que 0,00 % à H3, +0,12 % à H5, +0,15 % à H10 et +0,42 % à H20.
La branche SHORT ne produit aucun avantage stable. Le taux de signe correct
reste inférieur à 50 % à tous les horizons et les semestres changent
fréquemment de signe.

Verdict : **NO-GO E1**. Le petit effet LONG H20 ne satisfait ni la stabilité
temporelle, ni l'IC, ni la symétrie LONG/SHORT. Il ne doit pas être promu au
serving et ne justifie pas une recherche de seuil sur la période OOS.

## E2 — Deux probabilités directionnelles indépendantes

E2 remplace la régression moyenne par deux classifieurs mutualisés entraînés
sur exactement les mêmes événements Oracle OOF :

```text
tête LONG  = P(rendement ajusté terminal Hx >= +3 %)
tête SHORT = P(rendement ajusté terminal Hx <= -3 %)
```

Les deux modèles partagent le profil de features et les folds, mais possèdent
des paramètres et artefacts séparés. Les journées comprises entre -3 % et +3 %
sont négatives pour les deux têtes. Il ne s'agit pas encore d'une cible
intraday « premier seuil touché » : cette question appartient à l'expérience
lifecycle suivante.

Le score directionnel de classement est `P(LONG) - P(SHORT)`. En plus des AUC,
Brier scores, courbes de fiabilité, rendements des queues et résultats par
semestre, le rapport évalue automatiquement une grille d'abstention :

```text
probabilité minimale = 0,50 / 0,55 / 0,60 / 0,65 / 0,70
marge minimale       = 0,00 / 0,05 / 0,10 / 0,15 / 0,20
```

Une décision LONG exige simultanément `P(LONG) >= probabilité minimale` et
`P(LONG)-P(SHORT) >= marge`. La règle SHORT est symétrique. Ces grilles sont des
diagnostics préfixés ; elles ne doivent pas servir à choisir a posteriori un
seuil sur une seule période.

Commande canonique E2 :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.shared_directional --oracle-batch-id model-factory-20260904192500-0802c8 --start-date 2016-01-01 --end-date 2025-12-31 --target dual_threshold --horizons 3,5,10,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --context-mode none --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12 --iterations 600 --depth 6 --learning-rate 0.03 --log-level INFO
```

Chaque répertoire `h3`, `h5`, `h10` et `h20` contient `long_model.cbm`,
`short_model.cbm`, les prédictions OOF, les métriques et le contrat. E2 reste
`research_only` et ne modifie ni le serving ni le backtest existants.

### Résultat E2 du 5 septembre 2026

La campagne `shared-dual-threshold-20260905063934-0802c8` couvre 86 256
prédictions OOF et neuf folds par horizon. Les AUC ci-dessous sont les moyennes
des AUC calculées séparément dans chaque fold ; elles sont préférées à une AUC
obtenue en concaténant des probabilités dont l'échelle varie entre folds.

| Horizon | AUC LONG moyenne | folds AUC-L > 0,50 | lift précision LONG | rendement LONG | AUC SHORT moyenne | rendement SHORT |
|---|---:|---:|---:|---:|---:|---:|
| H3 | **0,544** | **9/9** | **+2,16 points** | +0,66 % (7/9 folds positifs) | 0,498 | -0,33 % |
| H5 | 0,525 | 7/9 | +0,06 point | +0,84 % (8/9) | 0,488 | -0,29 % |
| H10 | 0,514 | 6/9 | -0,26 point | +1,55 % (7/9) | 0,500 | -1,04 % |
| H20 | 0,504 | 5/9 | -0,59 point | +1,81 % (7/9) | 0,496 | -0,81 % |

La tête SHORT est rejetée à tous les horizons. H3 LONG constitue en revanche
le premier signal directionnel répétable de la campagne : AUC supérieure à
0,50 dans les neuf folds, dispersion faible (écart-type 0,015, minimum 0,509)
et enrichissement du taux d'événement de 29,81 % à 31,97 % dans le décile haut.
L'effet reste faible et ne constitue pas encore une autorisation de serving.

Les probabilités brutes sont mal calibrées : à H3, le grand groupe prédit en
moyenne autour de 44,8 % n'observe qu'environ 30,6 % de hausses >= 3 %. Il ne
faut donc ni réutiliser directement un seuil 0,55, ni sélectionner un seuil sur
ces mêmes tests. La suite préfixée est une calibration imbriquée ajustée sur la
validation de chaque fold, puis une confirmation gelée de H3 LONG sur une
période jamais utilisée. Aucun développement supplémentaire de la tête SHORT
n'est justifié avant l'apport de nouvelles features signées.

## E2-B — Confirmation LONG H3 avec calibration imbriquée

E2-B isole uniquement le signal retenu par E2 : la tête LONG à horizon H3.
Cette expérience ne développe plus la branche SHORT et ne recherche aucun
seuil sur les données de test. La population reste le TOP20 Oracle calculé à
partir des prédictions OOF persistées. Le score Oracle sert au gate et au
benchmark, jamais comme feature du modèle directionnel.

Pour chaque fold Walk-Forward, l'ordre des opérations est figé :

```text
train antérieur -> apprentissage CatBoost LONG H3
validation       -> early stopping + ajustement Platt
test postérieur  -> évaluation unique du modèle et du calibrateur
```

Le calibrateur ne voit donc jamais le test. Sa pente doit être strictement
positive. Si la validation suggère une inversion du classement, le système ne
retourne pas artificiellement les probabilités : il utilise une probabilité
constante égale à la prévalence de validation. Cette règle conserve
l'abstention scientifique en cas de fold non calibrable.

Les politiques économiques sont fixées avant l'exécution : top 5 %, top 10 %
et top 20 % quotidiens selon la probabilité LONG. La politique primaire est le
top 10 %. Chacune est comparée à deux références calculées sur la même journée
et avec le même nombre de lignes : les plus fortes amplitudes Oracle, puis
l'espérance d'un tirage dans le pool Oracle. Les seuils calibrés 0,30 à 0,50
sont publiés uniquement comme diagnostics de fiabilité ; ils ne déterminent
pas la politique candidate.

Les gates de développement figés sont :

- AUC moyenne par fold au moins égale à 0,53 ;
- au moins 7 folds avec une AUC supérieure à 0,50 ;
- lift de précision top 10 d'au moins 2 points de pourcentage ;
- lift de rendement top 10 d'au moins 0,25 point de pourcentage ;
- lift de rendement positif dans au moins 7 folds ;
- Brier calibré meilleur que la prédiction constante.

La commande de développement produit un paquet
`shared-long-h3-confirm-*`. Après les folds OOF, le modèle final réserve les
126 dernières dates de développement pour son calibrateur Platt et purge les
trois sessions précédentes. Le contrat sauvegarde les dates, la liste exacte
des features, les seuils de cible, la taille du pool, les politiques et les
artefacts. Il reste explicitement `research_only` et `serving_ready=false`.

Commande de développement E2-B :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.shared_directional --oracle-batch-id model-factory-20260904192500-0802c8 --start-date 2016-01-01 --end-date 2025-12-31 --target long_h3_confirmation --target-up-threshold 0.03 --target-down-threshold -0.03 --context-mode none --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12 --iterations 600 --depth 6 --learning-rate 0.03 --calibration-max-iter 100 --log-level INFO
```

La confirmation est ensuite une commande séparée. Elle recharge le modèle, le
calibrateur et le contrat sans réentraînement, exige une date strictement
postérieure à la calibration finale et utilise les prédictions Oracle déjà
persistées. Elle reconstruit exactement les features du contrat et refuse une
différence de schéma. Pour le batch actuellement étudié, la période intacte
est 2026-01-01 à 2026-06-30 :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.shared_directional --oracle-batch-id model-factory-20260904192500-0802c8 --target long_h3_confirmation --confirmation-artifact artifacts\models\shared_directional\shared-long-h3-confirm-AAAAMMJJHHMMSS-0802c8 --start-date 2026-01-01 --end-date 2026-06-30 --log-level INFO
```

Il faut remplacer `AAAAMMJJHHMMSS` par le répertoire affiché à la fin de la
première commande. Ne pas relancer ni ajuster E2-B après consultation de cette
confirmation : elle constitue l'unique test intact. Un smoke technique limité
à 50 symboles et deux folds a déjà validé le chemin complet, mais ses métriques
ne sont pas une preuve statistique et ne doivent pas guider la décision.

## E3 — Deux têtes de rentabilité conditionnelles au chemin

E3 corrige l'alignement entre la cible ML et le trade réellement simulé. E1 et
E2 utilisaient le rendement terminal : un titre pouvait toucher un objectif,
se retourner puis recevoir un label opposé à l'opportunité tradable. E3 rejoue
donc chaque événement Oracle TOP20 deux fois, une fois LONG et une fois SHORT,
depuis l'open de la séance suivante.

Le premier contrat est nommé `barrier_race_v1` :

```text
signal Oracle OOF au close J
    -> rejet si |open J+1 / close J - 1| > 3 %
    -> entrée open J+1
    -> stop initial 2,5 ATR
    -> TP min(3 ATR, 7 %)
    -> stop prioritaire si stop et TP sont touchés dans la même barre
    -> sortie au close après 20 séances si aucune barrière n'est touchée
    -> spread 5 bps + commission 1 bp + slippage 2 bps par côté
    -> coût d'emprunt SHORT 0,30 % annualisé
```

Le label LONG vaut un lorsque le rendement net du replay LONG est positif. Le
label SHORT suit la même règle sur le replay SHORT. Les deux têtes sont
indépendantes : une ligne peut avoir deux échecs, ou deux succès si son chemin
oscille assez pour rendre les deux replays rentables. Le modèle n'est donc
jamais forcé de choisir une direction.

Les deux CatBoost sont mutualisés sur tous les événements du pool Oracle OOF.
Le score Oracle reste un gate et n'entre pas dans les features. Les folds sont
chronologiques et purgés de 20 séances. L'évaluation porte sur :

- AUC et Brier séparés LONG/SHORT ;
- top 10 % quotidien de chaque probabilité ;
- rendement net et lift contre le pool Oracle des mêmes dates ;
- résultats par semestre et par fold ;
- concentration du PnL par symbole ;
- politiques diagnostiques combinant probabilité et marge LONG-SHORT.

Les gates sont séparés par côté : AUC moyenne >= 0,53, au moins sept folds avec
AUC > 0,50, lift net >= 0,25 point, au moins sept folds avec lift et rendement
positifs, et premier contributeur <= 35 % des contributions positives. Un GO
LONG n'autorise jamais automatiquement la branche SHORT.

`barrier_race_v1` est volontairement **research-only** et non conforme au
lifecycle PROD complet : il inclut une sortie H20 et désactive le trailing
risk-based afin d'isoler la prédictibilité du sens. Un passage des gates
autoriserait une E3-B utilisant un replay complet du lifecycle ; il ne permet
pas à lui seul une promotion serving.

Le smoke du 6 septembre 2026 a exercé la chaîne réelle sur 30 symboles et un
fold : 8 437 événements labellisés, AUC LONG 0,582 et AUC SHORT 0,449. Le top
10 % LONG affiche +0,88 % net et +0,55 point de lift ; le SHORT affiche -0,65 %.
Ce smoke vérifie uniquement le fonctionnement. Sa petite population et son
fold unique interdisent toute conclusion ML.

Commande de campagne complète :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.path_aware_directional --oracle-batch-id model-factory-20260904192500-0802c8 --start-date 2016-01-01 --end-date 2025-12-31 --stop-atr-mult 2.5 --tp-atr-mult 3.0 --tp-max-pct 0.07 --max-sessions 20 --max-entry-gap-pct 0.03 --spread-bps 5 --commission-bps 1 --slippage-bps 2 --borrow-fee-annual 0.003 --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12 --iterations 600 --depth 6 --learning-rate 0.03 --context-mode none --log-level INFO
```

Le répertoire `shared-path-aware-*` persiste les deux modèles, les prédictions
OOF ligne à ligne, les métriques, le profil de features et le contrat complet.
Il porte systématiquement `research_only=true` et `serving_ready=false`.
