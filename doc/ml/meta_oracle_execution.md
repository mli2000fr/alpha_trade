# Meta Oracle : implementation et execution

Le module `modelFactory.meta_oracle` implemente le noyau experimental A/B du
[protocole](meta_oracle.md). Il ne modifie ni tables, ni cascade, ni live.

## Premiere execution : controles F0

```powershell
python -u -m modelFactory.meta_oracle --stage a --batch-id model-factory-20260909051302-323684 --threads 4
```

Les scores Oracle seuls sont compares avec Logistic et CatBoost fixes.
Comparateurs : Oracle-score keep80, TOP16 a nombre quotidien identique dans
l'univers OOF complet, Random keep80 et placebo cible permutee par date.
Le quota entier est `floor(0.8*N)` : tous les comparateurs partagent le meme
arrondi. La precision primaire est une moyenne equiponderee par date.

## Deuxieme execution : F1 original

### Resultat du controle A — 14 septembre 2026

Artefact : `artifacts/research/meta_oracle/meta-oracle-a-20260914194645`.
Verdict `CONTROL_ONLY`, neuf folds du 4 aout 2020 au 6 fevrier 2025.
Le holdout shadow n'a pas ete charge ; aucune promotion n'est autorisee.

| Selection quotidienne a quota identique | Precision des vrais extremes, moyenne par date |
| --- | ---: |
| Oracle-score keep80 / comparateur TOP16 | 47,01 % |
| F0 Logistic, scores Oracle seuls | 47,01 % |
| F0 CatBoost, scores Oracle seuls | 46,99 % |
| Random keep80 | 44,73 % |
| Placebo, cible permutee par date | 44,66 % |

F0 Logistic reproduit la selection Oracle. F0 CatBoost perd 0,021 point,
avec intervalle a 95 % du delta [-0,052 ; +0,001] point : aucun gain F0.
Le placebo reste proche du hasard ; ce controle ne signale pas de gain
artificiel, sans prouver exhaustivement l'absence de fuite. Les dates de
disponibilite des labels train sont anterieures au test dans les neuf folds.

Retention effective 79,89 % (arrondi quotidien) : le veto Oracle retire
50 820 faux positifs mais aussi 27 974 vrais extremes ; il conserve 84,02 %
des vrais extremes. Ces chiffres mesurent l'amplitude, ni direction ni PnL.
Suite : tester F1 en B, sans ajuster de seuil sur le holdout. L'absence de
gain F0 ne rejette pas l'hypothese d'information additionnelle dans F1.

```powershell
python -u -m modelFactory.meta_oracle --stage b --batch-id model-factory-20260909051302-323684 --threads 4
```

Cette execution regenere les features du profil Oracle original, sur la
membership OOF complete, avant le filtrage de qualite future. Elle peut etre
longue. Elle ajoute F1 Logistic/CatBoost et le controle inverse universe-wide.
Elle ne reentraine pas l'Oracle. Les normalisations et imputations des modeles
sont ajustees uniquement sur le train. Aucun gap J+1 n'est utilise.

## Purge et sorties

Train expanding, minimum 504 seances ; test 126 seances ; purge nominale H20
et condition stricte `oracle_available_date < test_start`. Le holdout shadow
n'est jamais charge. Les intervalles utilisent des blocs de 21 dates pour
tenir compte du chevauchement H20.

Sous `artifacts/research/meta_oracle/meta-oracle-<stage>-<date>/` : rapport JSON
et texte, candidats Parquet, metriques folds, periodes annuelles, comparateurs
de veto, buckets Meta et bandes Oracle. Le produit Oracle x Meta, les familles
F2 dediees et les variantes M3/M6/M8/F3 restent a implementer seulement apres
l'audit du signal initial. Il ne faut pas annoncer la campagne entiere achevee
avant ces gates ; aucun GO ne vaut autorisation de production.

La regle initiale F1 CatBoost exige lift positif et significatif contre
Oracle-score keep80, gain contre TOP16 et random, au moins 60% de folds et
d'annees positifs, et 70% de transitions buckets non decroissantes. Les mesures
ML sont observation-weighted ; les precisions et deltas principaux sont
equal-date-weighted. Un audit independant des placebos et des bandes reste
obligatoire meme si le verdict automatique indique GO_RESEARCH.

## Resultat B — 14 septembre 2026 : NO_GO

Artefact : `artifacts/research/meta_oracle/meta-oracle-b-20260914201547`.
168 features d'origine, neuf folds, meme population et quotas que A.

| Variante | Precision equal-date | Delta contre Oracle keep80 |
| --- | ---: | ---: |
| Oracle keep80 / TOP16 a quota quotidien identique | 47,0106 % | reference |
| F1 Logistic | 46,9486 % | -0,0620 point |
| F1 CatBoost, politique primaire | 46,9707 % | -0,0398 point |
| Controle inverse universe-wide | 46,8458 % | -0,1648 point |

IC95 du delta F1 CatBoost : [-0,1675 ; +0,0955] point. Le gain est negatif
et non significatif ; seulement 4/9 folds et 1/6 annees affichent un gain.
Les annees 2020 et 2025 sont partielles. Le controle inverse est inferieur
a Oracle, avec IC95 [-0,2967 ; -0,0318] point. F1 CatBoost retire 50 710
faux positifs mais 28 084 vrais extremes, contre 50 820 et 27 974 pour Oracle.
Il ne filtre donc pas mieux les faux positifs a quota egal.

Le holdout reste ferme. Ces resultats rejettent la valeur incrementale du
contrat F1 teste, pas toutes les architectures Meta ni la detection Oracle.
Pas de promotion, de recherche de seuils ou de variantes lourdes M3/M6/M8
sur la base de ces resultats. F2/F3 restent non testees dans cette campagne.

L'anomalie initiale du diagnostic des bandes a ete corrigee le 14 septembre
2026 : le plafonnement de `extreme_pct * 20` a 3 est remplace par les bandes
[0,80 ; 0,85), [0,85 ; 0,90), [0,90 ; 0,95), [0,95 ; 1,00]. Les percentiles
exactement sur une borne rejoignent la bande superieure ; 1,00 reste dans
la derniere bande. Les percentiles invalides ou hors TOP20 sont rejetes.
Les bandes a une seule classe sont conservees avec `auc_valid=False` et
AUC vide, plutot que silencieusement omises.

Les artefacts A et B ont ete recalcules depuis `candidates.parquet` : seuls
`oracle_band_metrics.csv` et le nouveau `oracle_band_diagnostics.json`
(version, bornes, date, empreinte des candidats) sont ecrits. Aucun acces
base, entrainement ou changement des rapports primaires n'est necessaire.

```powershell
python -u -m modelFactory.meta_oracle --refresh-bands artifacts/research/meta_oracle/meta-oracle-b-20260914201547
```

Le fichier ajoute la taille, le nombre de dates, les vrais extremes et la
precision equal-date par bande. Sur B, les effectifs sont 97 843 / 97 749 /
97 788 / 98 389 evenements. Les AUC Oracle sont 0,5069 / 0,5089 / 0,5116 /
0,5440 ; F1 CatBoost donne 0,5110 / 0,5164 / 0,5228 / 0,5472. Ces petits
ecarts descriptifs ne sont pas des gains significatifs prouves par bande
et ne changent pas le NO_GO primaire a quota egal. Onze tests cibles passent.
