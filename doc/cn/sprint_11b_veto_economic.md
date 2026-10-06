# Sprint 11-B — Stress économique indicatif du veto D1 CN_A

## Décision

**Sprint 11-B exécuté ; déploiement non autorisé.** L'objectif était de
vérifier si le gain directionnel modeste du veto LightGBM du Sprint 11-A
survit à des contraintes élémentaires de négociabilité et à plusieurs
hypothèses de coûts, en le comparant à la réversion. Il survit **en
différence relative** sur les titres encore évaluables, mais ne constitue
pas un backtest de portefeuille ni une validation exécutable.

Le signal est toujours exploratoire : les dates 2022–2025 ont déjà été
consultées dans les Sprints 10 et 11-A. Le schéma
`market_execution_rules` existe dans le code du référentiel multi-marché,
mais **la table n'est pas présente dans la base `alpha_trade_cn` utilisée
pendant cet audit**. Les frais et lots ci-dessous sont donc des hypothèses
de recherche versionnées, **pas** une grille de courtage ou de marché
validée. Aucun code de trading, aucun serving et aucune table métier ne
sont modifiés.

## Contrat, données et protections contre les faux gains

Le [protocole figé](../../config/research_cn/sprint11b_veto_economic.yaml)
fixe avant exécution : les quatre horizons H5/H10/H15/H20, les huit folds
semestriels, un ticket de **10 000 CNY**, les politiques Oracle entier,
veto réversion 20 %, veto LightGBM 20 % et veto consensus 20 %, et trois
scénarios de coûts par côté :

| Scénario | Coût hypothétique par achat et vente |
| --- | --- |
| Zéro | 0 point de base, aucun minimum |
| Base proxy | 10 points de base, minimum 5 CNY par ordre |
| Stress proxy | 25 points de base, minimum 5 CNY par ordre |

Ce sont des **stress de friction**, non des tarifs officiels ; la taxe,
les frais de transfert et les conditions du courtier ne sont pas modélisés
individuellement. Les hypothèses de lots sont 100 actions par achat
SH_MAIN/SZ_MAIN/CHINEXT ; STAR exige au moins 200 actions dans ce proxy.
Les règles effectives peuvent dépendre de la date, du board et de l'ordre.
Les références de place confirment la nécessité de vérifier les tailles
d'ordre et la possibilité de revente avant d'industrialiser :
[règles SZSE](https://www.szse.cn/English/rules/siteRule/P020240911598586572526.pdf),
[mécanisme SSE](https://english.sse.com.cn/start/trading/mechanism/).

Le [moteur](../../modelFactory/cn_veto_economic_replay.py) reprend les
prédictions OOS vérifiées du Sprint 10-C et les prix/flags des labels CN
annuels vérifiés par SHA. L'appariement impose l'identité du marché, des
dates, titres, labels, rendements et indicateurs d'exécution. La décision
de veto est calculée **avant** la lecture des labels. L'entrée est l'open
théorique de la séance de décision et la sortie le close de J+H. Pour
H≥5, l'écart de séances exclut une vente le jour de l'achat au niveau de
ce contrat ; cela **ne suffit pas** à garantir une exécution réelle ou la
gestion d'une sortie empêchée.

Un aller-retour n'entre dans le sous-échantillon de coûts que si le label
est valide/mûr, le chemin n'a pas d'événement de facteur non simulé,
l'entrée et la sortie ne sont pas verrouillées ou inconnues, les prix sont
cohérents avec le rendement brut, le board a une hypothèse de lot et le
ticket permet d'acheter la quantité minimale. Les sorties bloquées sont
classées **non résolues** : ni profit, ni rendement zéro, ni vente au close
impossible. Les coûts sont appliqués au notionnel réellement acheté et
vendu après arrondi au lot, avec minimum par ordre.

Cette quarantaine utilise certaines informations de J+H pour **évaluer la
qualité du replay**, jamais pour sélectionner ex ante des candidats.
Néanmoins, mesurer seulement les aller-retours possibles crée un risque
de sélection favorable : les cas difficiles peuvent précisément être les
perdants. Le rapport montre donc toujours le nombre de candidats exclus.

## Résultats

Les 32 couples horizon–semestre sont terminés. Le
[rapport intégral](../../artifacts/cn/directional/sprint11b/sprint11b-a4e1a03943871cb2/report.json)
conserve aussi les résultats par semestre et tous les motifs d'exclusion.
Chaque moyenne ci-dessous est un **rendement par signal sur les seuls
aller-retours proxy évaluables**, non un rendement de portefeuille. Les
signaux se chevauchent dans le temps ; capital, cash, capacité, risque et
nombre de positions ne sont pas simulés.

| Horizon | Politique | Aller-retours proxy / sélectionnés | Brut moyen | Net base proxy | Net stress proxy |
| --- | --- | ---: | ---: | ---: | ---: |
| H5 | Oracle entier | 826 663 / 958 676 (86,2 %) | −0,10 % | −0,30 % | −0,59 % |
| H5 | Réversion veto 20 % | 659 402 / 766 547 (86,0 %) | +0,11 % | −0,09 % | −0,39 % |
| H5 | LightGBM veto 20 % | 658 675 / 766 547 (85,9 %) | +0,19 % | −0,01 % | −0,31 % |
| H10 | Réversion veto 20 % | 639 599 / 766 547 (83,4 %) | +0,14 % | −0,06 % | −0,36 % |
| H10 | LightGBM veto 20 % | 638 838 / 766 547 (83,3 %) | +0,24 % | +0,04 % | −0,26 % |
| H15 | Réversion veto 20 % | 621 320 / 766 547 (81,1 %) | +0,21 % | +0,01 % | −0,29 % |
| H15 | LightGBM veto 20 % | 620 705 / 766 547 (81,0 %) | +0,35 % | +0,15 % | −0,15 % |
| H20 | Réversion veto 20 % | 605 600 / 766 547 (79,0 %) | +0,26 % | +0,06 % | −0,24 % |
| H20 | LightGBM veto 20 % | 605 356 / 766 547 (79,0 %) | +0,41 % | +0,21 % | −0,09 % |

À H20, l'avantage net **relatif** du veto LightGBM sur la réversion est
d'environ **+0,16 point par signal évalué** dans les scénarios base et
stress. Il est positif sur **6 des 8 semestres**, pas les huit. Les deux
politiques perdent nettement sur 2022H1, 2022H2, 2023H2 et 2024H1 ;
le bon agrégat dépend surtout des périodes favorables de fin 2024 et 2025.
En scénario stress, **les deux rendements agrégés H20 sont négatifs**.

L'attrition H20 du veto LightGBM est essentielle :

| Motif | Candidats |
| --- | ---: |
| Aller-retour proxy évalué | 605 356 |
| Ticket 10 000 CNY insuffisant pour le lot supposé | 84 510 |
| Événement de facteur/corporate action non rejoué | 42 509 |
| Label invalide ou non mûr | 28 791 |
| Entrée verrouillée/inconnue | 3 147 |
| Sortie verrouillée/inconnue, **position non résolue** | 2 057 |
| Rendement brut et ajusté divergent malgré absence de facteur classé | 160 |
| Limite entrée/sortie inconnue | 17 |

La population « évaluable » ne représente que **79,0 %** des candidats
veto H20. Les 84 510 cas de lot inaccessible montrent aussi qu'un seul
ticket fixe modifie matériellement l'univers. Une analyse de coûts
conditionnelle à ces seuls cas ne permet pas de déclarer la stratégie
rentable.

## Verdict et suite nécessaire

Le veto LightGBM garde un petit avantage descriptif sur la réversion,
mais **NO-GO trading / NO-GO activation du veto** :

1. avantage de rendement net faible face à la baseline simple ;
2. quatre semestres H20 négatifs et scénario de friction stress négatif ;
3. cas non résolus à la sortie et 21 % du pool veto sans aller-retour proxy ;
4. absence de règles d'exécution CN datées dans la base d'étude ;
5. aucune preuve sur une période CN indépendante ni simulation du capital,
   des positions simultanées et des fills.

La prochaine pièce n'est pas un nouveau seuil : il faut d'abord le moteur
de backtest CN du Sprint 12, des règles et frais datés, puis une période
CN jamais consultée pour une décision de déploiement. Le contrat doit
gérer l'inventaire T+1, les lots réels, les limites et suspensions avec
report/annulation d'ordres, les corporate actions, les coûts du courtier
et les positions non clôturées. Le replay présent sert uniquement à
prioriser ce travail.

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.cn_veto_economic_replay
```
