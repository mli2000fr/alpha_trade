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
