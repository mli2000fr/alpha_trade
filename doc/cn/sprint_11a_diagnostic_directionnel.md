# Sprint 11-A — Diagnostic directionnel après Oracle CN_A

## Décision et portée

**Étude terminée, exploratoire seulement.** Le ranking du Sprint 10-C avait
franchi son gate face au momentum, mais la comparaison *post-hoc* avec une
simple réversion révélait un avantage faible, surtout sur D10. Ce sprint
répond donc à une question plus opérationnelle, sans entraîner de nouveau
modèle : parmi les candidats Oracle TOP20, vaut-il mieux **éviter les D1**
plutôt que prétendre choisir les D10 pour acheter ?

Les huit semestres 2022H1–2025H2 ont **déjà été inspectés** pendant les
Sprints 10-B/10-C. Les mesures ci-dessous sont OOS au sens des entraînements
Walk-Forward, mais **ne constituent pas une confirmation indépendante de
l'hypothèse Sprint 11-A**. Aucun seuil n'a été optimisé sur eux ; aucun modèle
n'est promu en serving et aucun backtest portefeuille n'est exécuté.

## Contrat de l'expérience

Le [protocole figé](../../config/research_cn/sprint11a_directional_diagnostic.yaml)
est relu strictement par le [moteur de diagnostic](../../modelFactory/cn_directional_diagnostic.py).
Les 64 Parquet OOS du Sprint 10-C sont appariés deux à deux par date et
instrument, avec contrôle des hashes du protocole, du code, des labels et
des prédictions. Leurs labels, rendements, scores de baseline et appartenances
Oracle doivent être identiques entre LightGBM et CatBoost. Un artefact
incomplet ou divergent arrête l'analyse.

Pour chaque H5/H10/H15/H20 et date, l'univers de décision est le **TOP20
Oracle déjà prédit OOS**. Il est fixé *avant* de regarder la validité des
labels. Seules les séances comptant au moins 20 candidats sont retenues.
Les cinq scores comparés sont :

| Score | Définition |
| --- | --- |
| Momentum | Rendement relatif à 20 séances du titre, déjà PIT à la décision |
| Réversion | Opposé exact du momentum relatif |
| LightGBM | Score ordinal OOS Sprint 10-C, élevé vers D10 |
| CatBoost | Même cible, autre famille de modèle |
| Consensus | Moyenne des rangs percentiles journaliers des deux modèles, sans utiliser les labels |

La valeur brute des deux modèles n'est pas additionnée : le consensus
travaille sur leurs *rangs* dans le pool Oracle du jour. Chaque politique
est appliquée **avant le filtrage des labels invalides** et le dénominateur
de couverture conserve donc ces cas.

Les politiques fixées sont : Oracle seul (100 % du pool) ; **veto du bas
20 %** pour chaque score (80 % conservés) ; sélection LONG du haut **10 %,
20 % ou 30 %** avec abstention sur les autres. Les fractions 10/20/30 ne
sont pas un sweep visant à choisir a posteriori un seuil gagnant : elles
décrivent la courbe couverture/qualité. Le rapport conserve chaque
semestre, board et régime de breadth. Une sensibilité distincte ne regarde
que les lignes avec `execution_data_eligible` : cette variable dépend
également de conditions futures à la sortie et **ne sert jamais à décider
ex ante** ; elle ne doit pas être prise pour une simulation d'exécution.

Pour chaque groupe : couverture, couverture des labels, taux D1 et D10,
fraction des D1 et D10 de l'Oracle encore présents après filtre, proportion
de rendements positifs et rendement moyen du label. Le rendement est celui
du contrat de label CN (open théorique à la séance de décision vers close
à l'horizon, avec ajustement de trajectoire). **Il ne contient pas frais,
slippage, non-fill, contraintes T+1, liquidité ni portefeuille**.

## Résultats OOS descriptifs

Le [rapport complet](../../artifacts/cn/directional/sprint11a/sprint11a-a43c1071751aa8a6/report.json)
contient 32 paires horizon–semestre, soit les 64 prédictions modèle
appariées. À H20, le pool compte **958 676** candidats, dont **923 582**
labels évaluables ; Oracle seul contient **24,24 % de D1** et **13,93 %
de D10**. Cette asymétrie est une caractéristique de la population Oracle
testée, pas une probabilité universelle.

| H20, politique | Part conservée | D1 parmi les conservés | D10 parmi les conservés | D1 Oracle encore présents | D10 Oracle encore présents |
| --- | ---: | ---: | ---: | ---: | ---: |
| Oracle seul | 100 % | 24,24 % | 13,93 % | 100 % | 100 % |
| Réversion, veto bas 20 % | 80 % | 21,83 % | 13,82 % | 72,06 % | 79,39 % |
| LightGBM, veto bas 20 % | 80 % | **21,27 %** | **14,14 %** | **70,12 %** | **81,10 %** |
| Consensus, veto bas 20 % | 80 % | 21,31 % | 14,10 % | 70,22 % | 80,90 % |
| Réversion, LONG haut 20 % | 20 % | 19,66 % | **15,08 %** | 16,18 % | 21,61 % |
| LightGBM, LONG haut 20 % | 20 % | **18,25 %** | 15,04 % | 14,86 % | 21,31 % |

Les parts de D1/D10 ont pour dénominateur les **sélections à label valide**.
Les colonnes de rétention, elles, indiquent la fraction de tous les vrais
D1/D10 du pool encore sélectionnée. Ainsi, le veto LightGBM élimine environ
**29,9 % des D1** mais élimine aussi **18,9 % des D10**. Son gain sur la
réversion n'est que de **0,56 point** de taux D1 parmi les conservés et
**1,71 point** de rétention D10. Ce n'est pas encore une justification
économique d'intégration.

| Horizon | D1 Oracle seul | D1 après veto réversion | D1 après veto LightGBM | D10 du haut 20 % réversion / LightGBM |
| --- | ---: | ---: | ---: | ---: |
| H5 | 24,70 % | 22,40 % | **21,77 %** | **17,12 %** / 16,02 % |
| H10 | 24,63 % | 22,19 % | **21,64 %** | **16,39 %** / 15,42 % |
| H15 | 24,47 % | 22,00 % | **21,42 %** | **15,78 %** / 15,22 % |
| H20 | 24,24 % | 21,83 % | **21,27 %** | **15,08 %** / 15,04 % |

À H20, le veto LightGBM est meilleur que la réversion sur la part D1 dans
**8/8 semestres** ; c'est **8/8 à H5**, **7/8 à H10** et **7/8 à H15**.
En revanche, la sélection LONG LightGBM ne dépasse la réversion en taux
D10 que sur **2/8, 4/8, 5/8 et 5/8 semestres** respectivement. Elle est
moins bonne en D10 agrégé à chaque horizon. Les résultats sur les seules
lignes `execution_data_eligible` changent peu la lecture à H20 : D1
restants 21,16 % pour le veto LightGBM contre 21,74 % pour la réversion.
Il s'agit toujours d'un filtre rétrospectif de sensibilité, pas d'une
politique de trading.

## Conclusion et prochaine preuve nécessaire

**D10/LONG autonome : NO-GO.** Le ranking améliore le rejet de certains
D1, mais n'améliore pas la précision D10 face à une simple réversion. Une
forte abstention ne crée donc pas ici de preuve suffisante de capacité à
acheter les vrais gagnants.

**Veto D1 : piste de recherche, pas activation.** La réduction de D1 est
présente sur plusieurs horizons et semestres, mais son incrément face à la
réversion est petit et il rejette aussi des D10. La prochaine preuve doit
figer la politique et la baseline réversion **avant** d'observer une
nouvelle période CN ; seulement ensuite, mesurer le bénéfice économique
avec prix d'entrée réalisable, T+1, limites, suspensions et frais. Faute de
dates nouvelles, tout autre raffinement sur 2022–2025 restera exploratoire.

Commande de reproduction (refuse d'écraser un rapport identique) :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.cn_directional_diagnostic
```
