# Sprint 13-B2 — Remédiation des positions détenues

## Objet et garde-fous

Le diagnostic 13-B initial a produit 40/40 sous-runs, dont 8 invalides :
quatre politiques touchées par des facteurs inconnus en 2022H1, trois
en 2023H1 et un portefeuille LightGBM avec une position invendable à la
fin de 2025H1. Aucun de leurs rendements marqués ne valait un PnL
réalisable. B2 traite les **preuves économiques** et la **censure de
sortie**, sans exclure rétroactivement les titres ni modifier la base CN.

La preuve initiale A2 reste intacte. Le [constructeur B2](../../modelFactory/cn_economic_remediation_13b2.py)
lit la source BaoStock déjà archivée, les lignes canoniques en lecture
seule et le rapport A2 hashé ; il émet un nouveau dossier dont le nom
contient le hash de la preuve. La couverture candidate des quatre
politiques est recalculée, non recopiée. Le replay [13-B](../../modelFactory/cn_economic_replay_13b.py)
reçoit ce nouveau fichier via `--evidence` ; aucun seuil, signal, seed,
coût ou scénario de fill n'est modifié.

## Trois événements détenus

| Titre / ex-date | Constat | Décision B2 |
| --- | --- | --- |
| `sz.003038`, source 29/03/2022, facteur canonique daté 30/03 | Source : 0,30 CNY/action + 0,2 action/action ; record date 28/03. Avec le cours brut du 28/03, le ratio théorique et le facteur diffèrent de 0,0064 %. | Accepter uniquement l'événement canonique `19141` avec ex-date économique 29/03, conserver l'ex-date canonique originale et la raison de correction dans la preuve. Aucun décalage générique n'est autorisé. |
| `sz.300327`, 31/05/2022 | BaoStock donne 0,48 CNY/action + 0,1 action/action. Le facteur local 2,738 contredit le ratio théorique 1,109 : l'anomalie fournisseur reste ouverte. | Les **termes économiques**, pas le facteur, sont confirmés par le [rapport annuel officiel de l'émetteur, pp. 39 et 54](https://static.cninfo.com.cn/finalpage/2023-03-30/1216261135.PDF). Exception explicite `20367`, avec URL et contradiction conservées dans l'artefact. Le rapport publié en 2023 sert seulement à reconstruire ex-post le PnL 2022, jamais de feature PIT à l'entrée. |
| `sz.002919`, 31/05/2023 | BaoStock décrit `10转3` et donne 0,3 action/action ; cash vide, aucun cash dans le texte, facteur relatif cohérent. | Traiter le cash vide comme zéro **uniquement** pour un transfert d'actions explicite et réconcilié. Les termes incomplets ou mentionnant un dividende cash restent non résolus. |

Ces corrections sont spécifiques aux événements vérifiés ; elles ne
valident pas les 1 692 autres facteurs encore incertains. Les sommes cash
restent **avant impôt sur dividendes**. Le facteur contradictoire de
`sz.300327` n'est pas réparé dans `cn_corporate_actions` et doit faire
l'objet d'une investigation fournisseur distincte.

## Position suspendue `sz.300280` en 2025H1

La politique `lightgbm_long_top20` a acheté 800 actions à l'open du
10/03/2025, prix proxy 11,47 CNY. La sortie H20 a été programmée le
07/04, mais chaque tentative du 08/04 au 30/06 a rencontré une séance
suspendue ou non négociable. Le dernier cours constant 8,74 CNY pendant
la suspension n'est **pas** un prix de vente. Le premier volume positif
après cette période n'apparaît que le 07/07, avec open 6,99 CNY, hors
semestre ; cela ne prouve pas non plus un fill possible à ce prix
(limite et participation restent à contrôler).

La position reste ouverte et le run 2025H1 reste **censuré/invalide**.
On ne le supprime pas de la comparaison, on ne le valorise pas à zéro
par convention, on ne le vend pas à 8,74 CNY et on ne prolonge pas le
semestre en mélangeant des fenêtres de capital réinitialisées. Une
analyse séparée de continuité après 30/06 peut mesurer le coût de la
suspension, mais elle ne transforme pas 2025H1 en rendement réalisé.

Le [suivi séparé](../../modelFactory/cn_suspended_followthrough_13b2.py)
reproduit exactement la courbe du portefeuille jusqu'au 30/06, puis
n'ajoute **aucun** nouveau signal. Les premières séances après reprise
ne permettent toujours pas une vente selon les limites/prix/volume du
replay. Le premier fill de vente **hypothétique**, au sens des barres
quotidiennes et non d'un carnet d'ordres observé, a lieu le 10/07/2025
à l'open 3,61 CNY, pour 800 actions ; 2 888 CNY de notionnel avant
5 CNY de frais de sortie. Le journal alloue 9 185,176 CNY de coût
d'acquisition et calcule une perte réalisée proxy de 6 302,176 CNY
hors dividendes. Ce résultat démontre l'ampleur possible de
l'écart entre un mark suspendu à 8,74 CNY et un prix de sortie, mais ne
réécrit pas le rendement de 2025H1 et ne garantit pas un fill réel.
[Rapport de suivi](../../artifacts/cn/economic/sprint13b2/suspended-followthrough-2025h1/report.json).

## Exécution et décision

```powershell
python -m modelFactory.cn_economic_remediation_13b2
python -u -m modelFactory.cn_economic_replay_13b --evidence artifacts/cn/corporate_actions/sprint13b2/evidence-afd10e157ff253b7/evidence.json --semesters 2022H1 2023H1 --seeds 0 --scenarios base --cost-profiles cn_a_research
```

Le replay ciblé peut réhabiliter les semestres 2022H1/2023H1 si aucune
autre position bloquante n'apparaît. Il ne résout pas la censure 2025H1.
La campagne complète multi-seeds/fills/coûts et tout GO économique
restent suspendus tant qu'une règle de comparaison avec sortie censurée
n'est pas pré-enregistrée. Les huit semestres sont déjà OOS inspectés,
**pas** un holdout indépendant.

### Résultat du replay ciblé seed 0 / fill base / coût de recherche

Les **10/10 sous-runs** des semestres 2022H1 et 2023H1 sont désormais
`RESEARCH_MARK_VALID` avec la preuve B2 versionnée. Les rendements proxy
après coûts du moteur sont :

| Politique | 2022H1 | 2023H1 |
| --- | ---: | ---: |
| Oracle pur | −22,35 % | −8,40 % |
| Veto retournement | −14,14 % | +13,50 % |
| Veto LightGBM | −21,64 % | +15,25 % |
| LightGBM LONG top20 | −18,10 % | +9,53 % |
| Momentum même univers | −24,15 % | −20,87 % |

Artefact : [rapport ciblé](../../artifacts/cn/economic/sprint13b/sprint13b-df292fca30082922/report.json).
Ce résultat ne constitue toujours pas une sélection de politique : une
seule seed, un seul scénario de fill/coût, et 2025H1 censuré.

Le contrôle homogène **40 sous-runs / seed 0 / fill base / coût de
recherche** est terminé : **39 valides, 1 censuré**, uniquement
`lightgbm_long_top20` en 2025H1 sur les 800 actions de `sz.300280`.
[Rapport des 40 runs](../../artifacts/cn/economic/sprint13b/sprint13b-12ae0a162cc0ce16/report.json).

Pour les huit semestres complets, la moyenne *arithmétique* des
rendements semestriels avec capital réinitialisé est −2,63 % Oracle,
+3,67 % veto retournement et +1,85 % veto LightGBM. Les deux veto
dépassent Oracle respectivement sur 6/8 et 7/8 semestres, avec un écart
moyen apparié de +6,30 et +4,49 points. Le comparateur momentum atteint
−7,40 % en moyenne. Ce ne sont **ni** des rendements annualisés ou
composés **ni** des preuves statistiques sur plusieurs seeds.

`lightgbm_long_top20` dépasse Oracle sur ses 7 semestres valides, mais
son huitième semestre est précisément censuré par une position qui
subit une lourde perte lors de sa vente ultérieure. Présenter le 7/7
ou une moyenne sur les seuls survivants comme un verdict favorable
serait un **biais de sélection**. Cette vérification n'est pas la
campagne multi-seeds/stress pré-enregistrée ; `economic_go_allowed`
reste `false`.

La [suite B3](./sprint_13b3_audit_huit_blocages.md) a depuis exécuté les
cinq seeds et les scénarios prévus. Ses nouveaux cas censurés ne sont
pas rétrospectivement supprimés des résultats B2.
