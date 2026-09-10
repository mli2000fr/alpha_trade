# E3-D — Direction par asymétrie du tail-risk

## Hypothèse

E3-D teste si les deux détecteurs de pertes extrêmes E3-A2 permettent de
choisir le sens d'un événement Oracle. Aucun modèle n'est réentraîné. Les
probabilités brutes n'étant pas directement comparables, elles sont converties
en rangs percentiles au sein de chaque journée :

```text
score = rang quotidien du risque SHORT - rang quotidien du risque LONG

score >= +marge -> LONG
score <= -marge -> SHORT
sinon           -> abstention
```

La marge primaire est fixée à 0,20. Les marges 0,00, 0,10 et 0,30 sont des
diagnostics et ne servent pas à sélectionner une politique après coup. Chaque
décision est comparée sur les mêmes événements à always-LONG, always-SHORT et
à l'espérance exacte d'un choix 50/50.

## Résultat du 6 septembre 2026

Source : `shared-path-utility-20260906071731-0802c8`.
Rapport : `shared-path-risk-direction-20260906075019/report.json`.

| Marge | Couverture | LONG | Rendement net | Lift vs 50/50 | Côté réellement meilleur | Pertes <= -20 % |
|---:|---:|---:|---:|---:|---:|---:|
| 0,00 | 96,2 % | 49,9 % | -0,18 % | -0,08 pt | 50,0 % | 2,47 % |
| 0,10 | 59,3 % | 50,7 % | -0,23 % | -0,08 pt | 50,1 % | 1,93 % |
| **0,20** | **36,9 %** | **49,7 %** | **-0,25 %** | **-0,10 pt** | **49,9 %** | **1,80 %** |
| 0,30 | 22,8 % | 48,8 % | -0,30 % | -0,15 pt | 49,5 % | 1,71 % |

La politique primaire ne produit un lift positif que dans 3/9 folds, un
rendement positif dans 2/9 et ne bat jamais le meilleur côté statique d'un
fold. Sa CVaR 5 % est -20,82 %, moins bonne que le benchmark 50/50 correspondant.
L'équilibre presque parfait entre LONG et SHORT n'est donc pas une preuve de
qualité : la direction choisie est réellement la meilleure dans seulement
49,9 % des cas.

Verdict : **NO-GO définitif pour E3-D**. Les modèles savent partiellement
identifier les observations dangereuses dans une direction donnée, mais la
différence entre leurs rangs ne contient aucune information exploitable sur
le sens futur. Le tail-risk peut rester un sujet de protection séparé ; il ne
doit pas être transformé en signal D1/D10.

## Gates

La politique devait simultanément conserver au moins 30 % des événements et
10 % de chaque côté, produire un rendement positif, un lift d'au moins 0,25
point contre 50/50, battre le meilleur côté statique, répéter ces avantages
dans au moins sept folds, ne pas dégrader le tail-risk ni la CVaR et conserver
une concentration raisonnable. Seuls les gates de couverture, d'équilibre des
côtés et de concentration sont passés.

## Commande reproductible

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.path_risk_direction --utility-artifact artifacts\models\shared_directional\shared-path-utility-20260906071731-0802c8 --log-level INFO
```

E3-D reste `research_only=true`, `serving_ready=false` et ne modifie aucune
prédiction persistée ni aucun flux de backtest.
