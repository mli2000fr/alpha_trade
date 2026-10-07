# US — Audit figé de capture des mouvements H20 ≥50 %

## Protocole enregistré avant le calcul — 6 octobre 2026

Objectif : vérifier si les grandes variations déjà visibles dans les listes
Oracle/ATR sont fiables, et mesurer leur détection avant de proposer une
nouvelle cible ML. Pas d'entraînement, pas de modification des exits, pas
de backtest économique ni de SQL d'écriture.

Batch `model-factory-20261003082853-e98332`, Oracle H20 ; fichier
`config/univers/univers_filtred_tradable.txt`, 2020-01-01 à 2026-09-30.
L'univers courant est statique : biais de survivance et absence de preuve
tradable historique à annoncer explicitement. Seuls les titres avec un score
Oracle fini entrent dans le dénominateur de capture ; ne pas revendiquer une
capture de tout le marché. Labels disponibles avant la date du calcul uniquement.

### Hypothèses et seuils figés

- Cible principale : `abs(future_return_H20) >= 0.50`.
- Description secondaire : ≥100 %, hausses et baisses séparées. Une baisse
  ≥100 % du prix d'une action est impossible ; elle signale un contrôle nécessaire.
- Baselines : tout le périmètre scoré, Oracle TOP20, ATR20/prix TOP20,
  intersection. Percentiles moyens, seuil inclusif ≥0,80 comme le service partagé.
- Classements : 10/20/50 premiers scores Oracle, 10/20/50 premiers ATR,
  10/20/50 premiers scores Oracle dans l'intersection. Ces effectifs sont
  **des nombres de titres**, distincts des TOP20 en pourcentage.
- Les égalités sont départagées par symbole. Aucune sélection ni aucun
  remplacement ne dépend de la présence du rendement futur.
- Comparaisons par année et globales. Ne pas choisir le meilleur K puis
  déclarer qu'il était présélectionné ; ce sont plusieurs descriptions exploratoires.

### Fiabilité et statistiques

Deux vues : labels déjà qualifiés, puis sensibilité aux contrôles locaux
d'extrémités : présence de prix ajustés positifs, accord du rendement reconstruit
avec le label à 10^-6 près, absence de barres synthétiques, volume positif aux
extrémités, pas de changement connu d'instrument, rendement supérieur à −100 %.
Un identifiant absent ne prouve pas la continuité. Les erreurs sont conservées
dans la vue principale et signalées ; aucune réparation de prix en base.

L'effet d'ajustement de plus de 5 points entre rendement brut et ajusté est
informatif : un split correctement ajusté n'est pas un faux rendement.
Les chemins complets des 100 plus grands rendements permettent de vérifier
sauts journaliers et jours sans volume. Ces contrôles ne remplacent pas une
source historique indépendante ni la qualification des actions sur titres.

`precision_pct` = mouvements extrêmes / candidats évaluables sélectionnés.
`capture_pct` = mouvements extrêmes sélectionnés / mouvements extrêmes
évaluables de tout le périmètre scoré. Les inconnus restent dans `selected`
et `unknown`, pas assimilés à zéro ni supprimés du classement initial.
`lift_vs_all` par année compare la précision à celle de la baseline.

Les fenêtres H20 se chevauchent. Une déduplication descriptive regroupe les
fenêtres d'un même titre et même signe dans la fenêtre du premier événement,
puis commence un nouveau groupe après sa date de sortie. Un groupe peut être
capté à n'importe quelle fenêtre : ce n'est pas une entrée simulée au début du
groupe, ni une preuve d'indépendance statistique. Aucun intervalle de confiance
i.i.d. ou nombre de trades n'en est déduit.

### Lineage et limites

Le run archive les dates d'entraînement du batch et les `fold_start` des scores.
Les années avant la fin d'entraînement ne deviennent pas OOS par simple
déclaration : une certification complète exige le train/val/test de chaque
champion. Les années après cette fin constituent une séparation temporelle
supplémentaire, pas une certification automatique du PIT. Les dates de prix
et labels peuvent être révisées depuis l'époque ; l'univers n'est pas PIT.

### Exécution et suivi

```powershell
python -u -m scripts.research.us_extreme50_capture --output artifacts/research/us_extreme50_capture/audit-20261006-v1
```

Le dossier doit être nouveau. Le script lit et archive une année à la fois,
avec `progress.json` puis `report.json` à la fin. Les instantanés parquet par
année permettent une inspection sans relire SQL. Il ne s'agit pas d'un batch
planifié et rien n'est ajouté dans `batch.yaml`. Un garde SQL refuse toute
instruction autre que SELECT/SHOW/DESCRIBE/EXPLAIN. Aucun modèle n'est chargé
pour être réentraîné, aucune opération de trading n'est exécutée.

Livrables : `year_policy_metrics.parquet`, `extreme_windows.parquet`,
`clusters.json`, `largest_paths.json`, `coverage.json`, `protocol.json`,
`report.json`. Les archives d'extrémités conservent les valeurs utilisées.

## Résultats

Run terminé : `artifacts/research/us_extreme50_capture/audit-20261006-v1`.
3 005 716 couples titre/date scorés ; 2 971 504 labels évaluables et
34 212 inconnus/invalides. 14 316 fenêtres H20 présentent une variation absolue
≥50 %, soit 0,482 % de tout le périmètre évaluable. Elles ne sont pas des
transactions indépendantes. 8 519 de ces fenêtres se situent en 2020 :
**59,5 % du total**, ce qui rend la moyenne globale très sensible à cette année.

### Capture et concentration — ≥50 %

Vue des labels valides avant sensibilité aux contrôles d'extrémités :

| Sélection | Fenêtres évaluables | Fenêtres ≥50 % | Précision ≥50 % | Capture des ≥50 % du périmètre |
|---|---:|---:|---:|---:|
| Tous les titres scorés | 2 971 504 | 14 316 | 0,482 % | 100 % |
| Oracle TOP20 % | 595 035 | 9 694 | 1,629 % | 67,71 % |
| ATR TOP20 % | 595 097 | 9 459 | 1,589 % | 66,07 % |
| Intersection Oracle × ATR | 462 257 | 8 668 | 1,875 % | 60,55 % |
| 10 premiers scores Oracle | 16 760 | 1 099 | 6,557 % | 7,68 % |
| 20 premiers scores Oracle | 33 520 | 1 770 | 5,280 % | 12,36 % |
| 50 premiers scores Oracle | 83 799 | 3 296 | 3,933 % | 23,02 % |
| 10 premiers ATR | 16 749 | 1 065 | 6,359 % | 7,44 % |

La concentration et la capture sont deux objectifs différents. L'intersection
améliore la fréquence des extrêmes parmi les candidats, mais perd une partie
des vrais événements par rapport à Oracle seul. Les dix meilleurs scores
concentrent davantage les extrêmes absolus, tout en en manquant plus de 92 %.
Ce résultat ne signifie pas 6,557 % de rendement ni 6,557 % de trades gagnants.

### Variabilité annuelle

Chaque cellule ci-dessous est la **précision ≥50 %**, pas la capture :

| Année | Tout le périmètre | Oracle TOP20 % | Intersection | 10 premiers Oracle |
|---|---:|---:|---:|---:|
| 2020 | 1,983 % | 5,907 % | 6,552 % | 20,672 % |
| 2021 | 0,237 % | 0,990 % | 1,168 % | 6,111 % |
| 2022 | 0,262 % | 1,111 % | 1,256 % | 6,016 % |
| 2023 | 0,167 % | 0,621 % | 0,723 % | 3,400 % |
| 2024 | 0,108 % | 0,421 % | 0,480 % | 0,516 % |
| 2025 | 0,214 % | 0,887 % | 1,031 % | 3,880 % |
| 2026, labels disponibles | 0,458 % | 1,668 % | 1,917 % | 4,524 % |

En 2025, Oracle TOP20 capture 82,95 % des fenêtres ≥50 %, contre 71,93 %
pour l'intersection et 10,08 % pour les dix meilleurs scores. En 2026,
ces captures sont respectivement 72,94 %, 63,31 % et 5,54 %.
La direction n'est pas apprise par ce classement d'amplitude : il concentre
aussi des pertes. L'ATR ne fournit pas de certification directionnelle.

Pour 2026, 187 dates sont scorées, mais les labels valides portent seulement
sur 168 dates, du 2 janvier au **2 septembre 2026**. Les 34 206 labels
inconnus/invalides de cette année ne sont pas transformés en mouvements nuls.
Il ne faut pas comparer « année 2026 entière » à 2025 entière.

Les champs `fold_start` montrent plusieurs champions historiques avant 2024,
puis `2024-01-08` pour tous les scores 2025/2026. Le batch déclare une fin
d'entraînement au 31 décembre 2024. Ces deux informations sont archivées ;
elles n'autorisent pas à déclarer tous les résultats historiques strictement
OOF sans qualification du train/validation de chaque champion.

### ≥100 %, signe et répétitions

865 fenêtres présentent ≥100 % ; toutes correspondent nécessairement à des
hausses pour un rendement de prix long valide. Oracle TOP20 en contient 797
(capture 92,14 %, précision 0,134 %). L'intersection en contient 756
(87,40 %, précision 0,164 %). Les dix premiers Oracle en contiennent 210
(24,28 %, précision 1,253 %). Cela reste rare parmi les candidats.

Pour le seuil ≥50 %, les 14 316 fenêtres se répartissent en 9 450 hausses et
4 866 baisses. Dans les dix premiers Oracle, 928 hausses et 171 baisses
dépassent ce seuil. **Ce ratio conditionnel parmi les extrêmes ne prédit pas
le signe de tous les autres candidats** et ne constitue pas un win rate.
La plupart des candidats n'atteignent pas ±50 % ; leur rendement et le
chemin de risque restent indispensables avant toute proposition économique.

Le regroupement descriptif donne 2 366 groupes titre/signe au lieu de
14 316 fenêtres. Oracle TOP20 recoupe au moins une fenêtre dans 71,22 %
des groupes, l'intersection 65,00 %, les dix premiers Oracle 10,23 %.
Ces groupes ne sont pas indépendants, surtout pendant les chocs de marché.
CAR, BTU, SM, HOV, PR et NBR reviennent notamment dans les fenêtres répétées.

### Qualité des prix : réserve réelle, pas invalidation de tous les mouvements

39 des fenêtres ≥50 % ont un volume nul à une extrémité ; elles sont signalées,
pas effacées. Aucun désaccord supérieur à 10^-6 entre rendement du label et
rendement des deux prix ajustés locaux : **cela prouve la cohérence interne,
pas l'exactitude du fournisseur**. Aucune divergence d'identité connue dans
ces fenêtres n'a été détectée, ce qui ne certifie pas les identités manquantes.

La sensibilité aux contrôles d'extrémités change peu les résultats globaux :
intersection 1,874 % de précision / 60,64 % de capture ; dix premiers Oracle
6,558 % / 7,70 %. Il reste toutefois des anomalies que cette sensibilité
ne suffit pas à traiter. Sur les 100 plus grands chemins archivés :
3 comportent des journées à volume nul et **60 un saut journalier >50 %**.
Un tel saut peut être réel (annonce, choc) : il n'est pas supprimé automatiquement.

INDV est un exemple réservé détaillé ci-dessous. À l'inverse, CAR du
23 mars au 21 avril 2026 indique +565,52 % avec des volumes positifs sur
les 21 barres et aucun saut journalier >23,70 %. Le chemin semble cohérent
localement, mais sa vérification indépendante reste à faire. On ne peut
donc ni certifier tous les très grands rendements, ni les déclarer tous faux.

### Conclusion et suite autorisée

**L'amplitude est déjà partiellement captée par Oracle ; le classement des
scores peut la concentrer davantage. Aucun gain directionnel ou profit net
n'est démontré ici.** L'ajout d'ATR améliore la précision du pool, pas sa
capture totale ; il ne garantit pas le sens.

Priorité avant un nouveau modèle : traiter les réserves d'identité et de prix
des plus grands chemins, puis, avec un nouveau GO et un protocole distinct,
évaluer les rendements signés, le risque et les coûts de sélections plus
concentrées. Une nouvelle cible absolue ≥50 % n'est pas encore entraînée.
Il serait prématuré de modifier les exits ou le serving sur ces seules statistiques.

58 tests ciblés passent avec les tests Oracle/ATR existants. Aucun SQL
d'écriture, entraînement, téléchargement massif, modèle ou batch planifié
n'a été modifié pendant le run.

### Premier cas vérifié : INDV, novembre–décembre 2022

Le label du 23 novembre 2022 indique +602,875 % à H20 : prix locaux 3,13 à
22,00. Le 28 novembre apparaît un saut 3,13 →21,03 et de nombreuses barres
présentent un volume nul, bien que `is_filled=0` et `adj_close=close`.
Le drapeau `target_quality_valid=1` ne suffit donc pas à certifier ce rendement
ni la possibilité de le négocier.

L'émetteur indique un regroupement 5:1 effectif le 10 octobre 2022 dans son
[communiqué officiel](https://www.indivior.com/latest/category/news/2022/indv-2022-gm-approval),
et le début de sa cotation Nasdaq seulement le 12 juin 2023 dans son
[annonce de cotation](https://ir.indivior.com/news-releases/news-release-details/indivior-commence-trading-nasdaq-0).
Ces dates imposent de vérifier quel instrument et quelle place représentent
les anciennes barres US/ADR. Elles ne prouvent pas à elles seules la cause
exacte du saut du 28 novembre : ne pas diviser les prix par cinq sans reconstituer
les ratios ADR/actions, dates et corrections du fournisseur.

Le cas est conservé dans les résultats principaux et signalé dans la
sensibilité locale. Aucune correction SQL ni exclusion rétroactive de
l'univers n'est appliquée pendant cette expérience.

### Qualification complémentaire des prix — 6 octobre 2026

La [revue des prix suspects](us_extreme50_price_qualification.md) examine
les 100 plus grands chemins (19 titres). Elle confirme une composante de
split non neutralisée sur INDV en octobre 2022, sans résoudre son saut de
novembre. La comparaison EODHD conserve les rendements de KNTK et REPX ;
un prix CLDX est corroboré par un dépôt SEC. La sensibilité qui rend
inconnus les cas INDV pré-Nasdaq et GRND traversant sa combinaison
d'entreprises conserve l'effet de concentration. Cela ne certifie pas tous
les chemins ni un profit net. Aucun test économique n'est lancé ici.
