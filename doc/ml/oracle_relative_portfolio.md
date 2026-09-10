# Portefeuille relatif dans le pool Oracle TOP20

## Statut

**Expérience terminée — `NO_GO`, aucun replay portefeuille autorisé.**

Cette expérience est isolée du serving, de la cascade ML et du backtest de
production. Elle vérifie si le faible classement du ranker conditionnel Oracle
peut être exploité sous forme de portefeuille relatif, même lorsque les
directions LONG et SHORT absolues ne sont pas fiables.

Code : `modelFactory/oracle_relative_portfolio.py`.

Artefacts :
`artifacts/research/oracle_relative_portfolio/relative-precheck-20260907222827/`.

## Hypothèse et construction

```text
Univers quotidien
  -> Oracle Extreme OOF
  -> TOP20 % par amplitude probable
  -> score OOF du ranker conditionnel
  -> 20 % supérieurs du pool : jambe LONG
  -> 20 % inférieurs du pool : jambe SHORT
  -> portefeuille 50 % LONG / 50 % SHORT
```

La sélection utilise uniquement le score OOF. Le rendement futur sert à
l'évaluation après sélection et n'entre jamais dans la décision.

Le pré-gate consomme la campagne
`conditional-oracle-ranker-20260907221309-0e94ac`, construite sur le batch
Oracle finalisé `model-factory-20260907170018-0e94ac`.

## Contrat figé

| Paramètre | Valeur |
|---|---:|
| Pool initial | TOP20 % Oracle OOF |
| Fraction de chaque jambe | 20 % du pool |
| Pondération | 50 % LONG / 50 % SHORT |
| Commission | 1 bp par transaction |
| Slippage | 2 bps par transaction |
| Borrow fee annuel | 0,30 % |
| Coût aller-retour commission + slippage | 6 bps |
| Gate rendement net moyen | au moins +0,10 % par cohorte |
| Gate folds positifs | au moins 75 % |
| Gate semestres positifs | au moins 60 % |

Le borrow est appliqué à la moitié SHORT au prorata de l'horizon. Ce pré-gate
ne simule ni fills, ni spread observé, ni disponibilité réelle du borrow.

## Résultats

Les deux horizons couvrent 1 134 cohortes quotidiennes et neuf folds OOF.

| Horizon | LONG brut | Queue basse brute | Spread | Portefeuille brut | Portefeuille net | Folds positifs | Semestres positifs | Verdict |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| H3 | +0,340 % | +0,211 % | +0,129 % | +0,064 % | **+0,003 %** | 4/9 | 5/10 | `NO_GO` |
| H20 | +2,229 % | +1,477 % | +0,752 % | +0,376 % | **+0,304 %** | 4/9 | 6/10 | `NO_GO` |

H3 devient pratiquement nul après coûts et échoue tous les gates.

H20 passe le rendement net agrégé et atteint exactement le minimum de 60 % de
semestres positifs. Il échoue cependant le contrôle principal : quatre folds
positifs sur neuf, contre sept requis. Les trois premiers folds sont positifs,
les folds 3 et 4 s'inversent, le fold 5 rebondit, puis les folds 6 à 8 sont de
nouveau négatifs. Le résultat est surtout porté par les premières fenêtres.

La queue basse H20 monte elle-même de **+1,477 %** en moyenne. Elle ne constitue
donc pas un SHORT absolu ; le gain théorique provient uniquement de l'écart
relatif avec la jambe haute.

## Comparaison avec la campagne précédente

| Horizon | Ancien IC / spread | Nouvel IC / spread | Lecture |
|---:|---:|---:|---|
| H3 | +0,0136 / +0,21 % | +0,0148 / +0,12 % | IC quasi inchangé, spread dégradé |
| H20 | +0,0266 / +0,54 % | +0,0260 / +0,67 % | spread meilleur, stabilité toujours insuffisante |

L'actualisation du batch et la correction de qualité des labels ne résolvent
pas le défaut structurel de stabilité temporelle.

## Limites

- Les rendements H20 des cohortes quotidiennes se chevauchent. Ils ne doivent
  être ni additionnés, ni annualisés, ni présentés comme une courbe de capital.
- Un replay OHLC serait nécessaire pour mesurer turnover, fills, gap d'entrée,
  spread réel, borrow, contraintes sectorielles et positions simultanées.
- `2025H2` ne contient que huit dates OOF et n'est pas une confirmation robuste.
- La période a déjà été observée dans plusieurs expériences et n'est plus une
  confirmation finale intacte.

## Décision

`replay_authorized=false` pour H3 et H20. Aucun raccordement au backtest, aucun
sweep de fractions et aucune optimisation des coûts ou horizons ne sont
justifiés. La piste ne pourra être rouverte qu'avec une information PIT
réellement nouvelle ou un ranker stable sur une confirmation indépendante.
