# E3-R — Veto de risque path-aware après Oracle Extreme

## Objectif et statut

E3-R évalue si les classifieurs de pertes extrêmes issus d'E3-A2 peuvent être
utilisés comme protection. Il ne prédit pas la direction, ne retourne jamais
un signal LONG en SHORT et ne crée aucun trade. Il peut uniquement rejeter une
décision déjà produite par Oracle ou par un modèle directionnel.

Cette expérience est strictement `research_only=true` et
`serving_ready=false`. Elle travaille exclusivement sur les prédictions OOF
déjà produites ; aucun modèle n'est réentraîné.

## Contrat préfixé

Pour chaque date et chaque côté, les candidats sont classés par probabilité de
subir un rendement net inférieur ou égal à -20 %. Le veto principal rejette
les 20 % les plus risqués du pool Oracle, sans remplacer les lignes rejetées.
Les variantes 10 % et 30 % sont uniquement diagnostiques.

Trois politiques sources sont mesurées séparément :

```text
oracle_pool          = tous les événements Oracle TOP20 OOF
oracle_top           = top 10 % quotidien par score Oracle
path_probability_top = top 10 % quotidien par P(LONG) ou P(SHORT) E3-A
```

Les gates du veto 20 % exigent : couverture d'au moins 70 %, réduction des
pertes extrêmes d'au moins 40 %, amélioration de CVaR d'au moins 0,25 point,
dégradation du rendement limitée à 0,10 point, amélioration du taux de pertes
et de la CVaR dans au moins sept folds, préservation du rendement dans au moins
sept folds, et concentration du premier symbole inférieure ou égale à 35 %.

## Exécution du 6 septembre 2026

Sources :

- E3-A2 : `shared-path-utility-20260906071731-0802c8` ;
- E3-A : `shared-path-aware-20260906064548-0802c8`.

Rapport corrigé : `shared-path-risk-veto-20260906074041/report.json`.

### Pool Oracle complet

| Côté | Veto | Couverture | Delta rendement | Réduction pertes <= -20 % | Delta CVaR 5 % |
|---|---:|---:|---:|---:|---:|
| LONG | 10 % | 89,4 % | -0,02 pt | 28,8 % | +1,16 pt |
| LONG | **20 %** | **79,4 %** | **-0,03 pt** | **41,5 %** | **+1,70 pt** |
| LONG | 30 % | 69,3 % | -0,06 pt | 51,1 % | +2,12 pt |
| SHORT | 10 % | 89,4 % | +0,01 pt | 22,7 % | +1,58 pt |
| SHORT | **20 %** | **79,4 %** | **+0,01 pt** | **34,5 %** | **+2,21 pt** |
| SHORT | 30 % | 69,3 % | 0,00 pt | 42,0 % | +2,68 pt |

La protection est temporellement stable : taux de pertes extrêmes et CVaR
s'améliorent dans 9/9 folds pour les deux côtés. LONG échoue seulement au gate
de préservation du rendement par fold, avec 6/9 au lieu de 7/9. SHORT préserve
le rendement dans 7/9 folds mais manque le seuil préfixé de réduction des
pertes extrêmes, 34,5 % au lieu de 40 %.

### Application après la sélection des candidats

Conformément à l'architecture, le veto des politiques `oracle_top` et
`path_probability_top` est recalculé parmi leurs candidats finaux. Il ne
réutilise pas le seuil des 20 % du pool. L'arrondi quotidien conserve 73,5 %
des candidats pour le veto principal :

| Politique/côté | Couverture | Delta rendement | Réduction pertes <= -20 % | Delta CVaR 5 % |
|---|---:|---:|---:|---:|
| Oracle top LONG | 73,5 % | +0,02 pt | 12,0 % | +2,02 pt |
| Oracle top SHORT | 73,5 % | -0,22 pt | 11,1 % | +2,95 pt |
| E3-A top LONG | 73,5 % | -0,04 pt | 30,1 % | +2,66 pt |
| E3-A top SHORT | 73,5 % | -0,14 pt | 19,6 % | +1,98 pt |

La CVaR s'améliore dans 8/9 folds sur les quatre variantes, mais le rendement
n'est préservé que dans 4/9 folds pour Oracle LONG, 5/9 pour Oracle SHORT,
3/9 pour E3-A LONG et 4/9 pour E3-A SHORT. Aucune politique top ne passe donc
les gates.

Verdict : **NO-GO production**. Le détecteur de risque reste une piste sérieuse
de protection, mais le veto dur calculé sur tout le pool entre en conflit avec
les sélections de tête. Toute suite devra tester une politique de contrôle du
risque attachée à un portefeuille concret, sans choisir a posteriori 10 %,
20 % ou 30 % sur ces mêmes données.

## Commande reproductible

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.path_risk_veto --utility-artifact artifacts\models\shared_directional\shared-path-utility-20260906071731-0802c8 --directional-artifact artifacts\models\shared_directional\shared-path-aware-20260906064548-0802c8 --log-level INFO
```

La sortie `report.json` contient les résultats complets par politique, côté,
fraction de veto, fold et semestre ainsi que chaque gate individuel.
