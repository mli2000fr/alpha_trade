# Sprint 13-C — Décision économique sur les replays CN_A figés

## Statut

Audit descriptif en lecture seule terminé le 27/09/2026. Le
[replay homogène B5](../../artifacts/cn/economic/sprint13b5/full/sprint13b-fcc5a4b464c50832/report.json)
contient 480 cellules : 462 valides et 18 censurées. Le
[replay momentum homogène](../../artifacts/cn/economic/sprint13c/momentum/sprint13b-bee0868177af846b/report.json)
contient 160 cellules, dont **138 valides et 22 censurées**. Les deux
campagnes ont les mêmes hashes de protocole, de preuve B5 et de
prédictions OOS. L'[audit final
13-C](../../artifacts/cn/economic/sprint13c/decision/decision-d1745c4c96351267/report.json)
porte le statut `COMPLETE_DESCRIPTIVE`. Son verdict pour ces quatre
politiques sur l'échantillon déjà inspecté est **NO GO économique pour
une activation**, avec `economic_go_allowed=false`,
`serving_enabled=false` et `live_enabled=false`.

Ce travail ne modifie ni les prédictions, ni les labels, ni les coûts,
ni les seuils, ni les tables CN. Les fenêtres 2022–2025 ont déjà été
inspectées : elles ne sont pas un nouveau holdout indépendant.

## Contrat et garde-fous

L'[auditeur 13-C](../../modelFactory/cn_economic_decision_13c.py)
exige exactement huit semestres, cinq seeds, deux scénarios de fill et
deux profils de coûts pour chaque politique. Il vérifie les hashes du
protocole, de la preuve d'actions et des prédictions OOS avant toute
comparaison. Il refuse un comparateur momentum d'une ancienne version
de preuve ou incomplet. Il ignore entièrement le rendement marqué de
toute cellule invalide ; ni zéro arbitraire ni vente fictive ne sont
injectés.

Chaque configuration est comparée sur des cohortes appariées
semestre × seed. Les quatre politiques doivent être valides dans la
même cohorte ; sinon toute la cohorte est
exclue de **cette** comparaison, et le décompte est explicite. Les cinq
seeds partagent les mêmes dates de marché : elles ne sont pas cinq
périodes OOS indépendantes. Le CSI 300 est un indice brut contextuel,
pas un ETF rejoué avec les mêmes frais, contraintes et règles de fill.

L'audit consigne rendement semestriel marqué, drawdown, exposition
brute moyenne, turnover, Sharpe/Sortino de marks valides, win rate,
payoff, profit factor, nombre de fills et commissions. Il compare
les autres politiques à Oracle seul par différence appariée,
avec le détail par semestre. Il donne aussi, pour les cohortes
censurées, **l'écart moyen manquant qui annulerait la somme observée** :
c'est une sensibilité algébrique, jamais une estimation de rendement
réalisé. Les droits de dividende restent un majorant avant retenue
fiscale inconnue.

## Lecture intermédiaire à trois politiques

Pour le scénario `base` et le coût `cn_a_research`, 39 des 40 cohortes
possèdent les trois politiques valides. Oracle seul a un rendement
semestriel marqué moyen de **−3,06 %** et un drawdown marqué moyen de
**−19,30 %**. Le veto retournement fait **−1,41 %** et le veto LightGBM
**−1,77 %**, soit des écarts appariés moyens de **+1,65** et **+1,30
point**. Mais le retournement n'améliore Oracle que sur **5 semestres
sur 8**, LightGBM sur **4 sur 8**. Sous coût stress, les écarts tombent
à **+1,45** et **+1,16 point**, sur 38 cohortes valides. En scénario
`conservative`, les valeurs agrégées observées sont identiques au
scénario `base` pour ces portefeuilles ; cela ne crée pas une nouvelle
preuve OOS indépendante.

Les 18 cellules invalides correspondent à six cohortes appariées :
quatre pour la position `sz.000046` radiée en 2023H2/seed 2, deux pour
la fraction d'action `sh.688175` en 2024H1/seed 0 sous coût stress.
L'écart de rendement absolu de ces cohortes reste inconnu. Pour le
scénario de base au coût standard, l'unique cohorte manquante devrait
avoir un écart veto−Oracle d'environ **−64,39 points** (retournement)
ou **−50,52 points** (LightGBM) pour annuler la somme des 39 écarts
observés. Ce calcul ne résout pas le PnL absolu de la position radiée,
ni le défaut de stabilité des veto entre semestres. Surtout, ces
39 cohortes ne sont **pas** les mêmes que les 34 cohortes où momentum
est également valide : comparer les moyennes de ces deux sélections
serait biaisé.

## Comparaison finale à quatre politiques

Le replay B5 initial ne comprenait pas la politique momentum. La
comparer à son ancien run, établi avec une preuve d'actions différente,
serait une erreur. Le replay momentum **avec la preuve B5** est
maintenant terminé. Ses 22 censures correspondent à des positions
touchées par des actions non résolues ; elles ne sont pas imputées.
La comparaison commune à quatre politiques porte sur **34/40**
cohortes au coût standard et **33/40** sous coût stress, pour chaque
scénario de fill.

| Scénario / coûts | Cohortes | Oracle | Veto retournement | Veto LightGBM | Momentum |
| --- | ---: | ---: | ---: | ---: | ---: |
| base / standard | 34 | −1,88 % | −1,02 % | −2,04 % | −3,86 % |
| base / stress | 33 | −2,58 % | −1,98 % | −2,93 % | −4,65 % |
| conservative / standard | 34 | −1,88 % | −1,02 % | −2,04 % | −3,86 % |
| conservative / stress | 33 | −2,58 % | −1,98 % | −2,93 % | −4,65 % |

Le détail par semestre, toujours sur les mêmes cohortes valides
(`base`/`cn_a_research`), rend visible la variation de régime :

| Semestre | Seeds comparables | Oracle | Veto retournement | Veto LightGBM | Momentum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022H1 | 5 | −16,67 % | −15,41 % | −18,35 % | −20,66 % |
| 2022H2 | 5 | −10,94 % | −9,01 % | −13,43 % | −12,01 % |
| 2023H1 | 5 | −2,17 % | +2,23 % | +2,14 % | −5,69 % |
| 2023H2 | 3 | −17,14 % | −20,37 % | −14,04 % | −4,28 % |
| 2024H1 | 3 | −22,04 % | −20,34 % | −15,61 % | −23,05 % |
| 2024H2 | 4 | +25,23 % | +30,74 % | +23,37 % | +20,72 % |
| 2025H1 | 5 | +11,49 % | +9,53 % | +9,59 % | +2,66 % |
| 2025H2 | 4 | +11,05 % | +6,93 % | +6,61 % | +11,56 % |

Ce sont des **moyennes arithmétiques de rendements semestriels marqués**
sur les mêmes cohortes, et non un rendement composé. Au coût standard,
le veto retournement dépasse Oracle de **+0,85 point** en moyenne
(17 cohortes meilleures, 17 pires), LightGBM est à **−0,16 point**
(18 meilleures, 16 pires) et momentum à **−1,99 point**
(15 meilleures, 19 pires). Sous stress, ces écarts deviennent
respectivement **+0,60**, **−0,35** et **−2,07 points**. Le veto
retournement est meilleur sur 5 semestres sur 8 ; LightGBM sur 3 ;
momentum sur 2. Il n'y a donc pas de domination stable.

Au scénario base/coût standard, les drawdowns marqués moyens sont
respectivement **−18,87 %**, **−19,33 %**, **−18,38 %** et
**−17,86 %**. Le léger gain de rendement du veto retournement ne
s'accompagne donc pas d'une réduction du drawdown moyen. Les
expositions brutes moyennes restent proches (environ 67 %), de même
que le nombre d'achats (environ 44 par semestre). Ces politiques
restent perdantes en moyenne sur ces cohortes, avant même la retenue
fiscale inconnue sur les dividendes. Le CSI 300 brut est uniquement
contextuel : il n'a pas subi ces mêmes règles de portefeuille ou coûts.

L'exclusion n'est pas aléatoire : momentum a 22 cellules invalides,
notamment en 2024H1. L'avantage ou le désavantage sur les 26 cohortes
non comparables à quatre politiques est inconnu ; il serait incorrect
d'extrapoler les moyennes du tableau aux 160 cohortes. Les cinq seeds
ne sont pas cinq marchés indépendants. Le statut `COMPLETE_DESCRIPTIVE`
signifie que **l'audit** est achevé, pas que le signal est validé.

## Reproduction et décision

```powershell
F:\projets\.venv\Scripts\python.exe -m modelFactory.cn_economic_decision_13c --momentum-report F:\projets\artifacts\cn\economic\sprint13c\momentum\sprint13b-bee0868177af846b\report.json
```

Pour les politiques gelées, **NO_GO_ECONOMIC sur les cohortes valides
inspectées** ; la validité économique exhaustive reste limitée par les
censures. Cela ne prouve pas qu'aucune politique CN ne peut fonctionner.
Le gate Sprint 13 reste fermé : aucune activation serving/live, aucun
réglage de seuil sur 2022–2025. Toute démonstration indépendante d'une
politique choisie maintenant réclamera de nouvelles dates non encore
inspectées. Le référentiel historique du symbole `302132` reste à
auditer avant tout usage de production.
