# US — Audit des discontinuités restantes après cinq exclusions

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

Date : 7 octobre 2026. Statut : contrôle terminé, réserves historiques ouvertes.

## Conclusion

Après retrait de KNTK, AMTB, DEC, TALO et INDV, les énormes valeurs précédemment
identifiées disparaissent. Cela ne signifie pas que tous les historiques sont
qualifiés. Trois raccordements restent prioritaires : **BASFY, PECO et FBRT**.
EVVTY et ASTH nécessitent aussi une qualification de leur historique peu liquide.
Les autres grandes variations ne doivent pas être automatiquement supprimées :
une annonce clinique, une crise de liquidité ou une fusion peuvent produire un
mouvement réellement très important.

Aucun retrait supplémentaire, aucune écriture SQL, aucun entraînement et aucune
intervention sur les batchs en cours n'ont été réalisés pour ce contrôle.

## Périmètre et méthode

- Univers courant : `config/univers/univers_filtred_tradable.txt`, 1 793 titres.
- Lecture : 4 957 887 barres, du 27 décembre 2012 au 31 décembre 2024.
- Mesures examinées à partir du 1er janvier 2016 : rendement quotidien, gap
  overnight et volatilité glissante sur 20 observations, reconstruits sur le
  chemin de prix ajusté du projet.
- Détection : rendement quotidien ou gap d'amplitude supérieure à 100 %.
- Résultat : 18 observations sur 14 titres. Ce sont des alertes à examiner,
  **pas 18 erreurs de prix démontrées**.
- Relecture fournisseur : une fenêtre de ±20 jours calendaires autour d'un
  événement par titre, plus les splits disponibles, pour chacun des 14 titres.
  Les réponses sont archivées avant reconstruction selon l'adaptateur du projet.

Les 14 relectures ont reçu des données. Elles reproduisent les grands sauts ;
ASTH présente une petite différence numérique, sans disparition du phénomène.
Un fournisseur qui reproduit sa propre série n'est pas une preuve indépendante.
Les quatre autres dates de titres déjà présents dans la liste ne disposent pas
d'un rapport individuel de relecture dédié.

Le champ `suspects: []` du rapport n'est **pas** un certificat de qualité : son
seuil distinct vise les valeurs supérieures à 100 en unité de rendement, soit
10 000 %. La liste `large-jumps.parquet` reste le résultat utile ici.

## Maxima observés

| Mesure | Titre et date | Valeur |
|---|---|---:|
| Rendement quotidien | BASFY, 09/10/2017 | +299,43 % |
| Gap overnight | BASFY, 09/10/2017 | +299,64 % |
| Volatilité glissante 20 observations | PECO, 15/07/2021 | 0,781388 |

La volatilité est dans l'unité de la formule utilisée, non annualisée ; ne pas
la présenter comme une volatilité annuelle. Cet audit ne reconstitue pas
l'intégralité des lignes exactes consommées par un ancien entraînement.

## Trois raccordements prioritaires

### BASFY — ratio ADR et décalage de date

Le 9 octobre 2017, la clôture passe de 6,61625 à 26,4275, soit +299,43 %.
La relecture fournisseur reproduit ces valeurs. Son calendrier de splits
mentionne un ratio 4:1 le **17 octobre**, huit jours après le saut observé.

Le [communiqué BNY Mellon du 11 octobre 2017](https://www.prnewswire.com/news-releases/bny-mellon-named-successor-depositary-bank-by-two-european-blue-chips-basf-and-orange-300533069.html)
annonce le passage d'une action ordinaire par ADR à un quart d'action par ADR
au 17 octobre. Le voisinage d'un facteur quatre suggère un problème de raccordement
ou d'ajustement, mais ne prouve pas à lui seul quelle ligne doit être corrigée.

À résoudre : identifier le ratio applicable à chaque date et vérifier des cours
indépendants avant/après le 9 et le 17 octobre. Ne pas déplacer arbitrairement
le split pour faire disparaître la variation.

### PECO — ancienne classe non cotée et nouvelle action de l'IPO

Deux alertes : +200 % le 6 juillet 2021 avec volume nul, puis +281,76 % le
15 juillet, de 7,29 à 27,83. Les réponses fournisseur conservent le second saut
et indiquent un regroupement 1:3 au 6 juillet.

La [documentation de l'agent de transfert](https://www.phillipsedison.com/node/96)
distingue l'ancienne action, reclassée en Class B après le regroupement, de
l'action introduite en Bourse le 15 juillet 2021. La Class B ne devient
convertible que plus tard. Les CUSIP sont distincts : ancienne action
71844V102, Class B 71844V300, nouvelle action cotée 71844V201.
Le [communiqué SEC du 2 juillet 2021](https://www.sec.gov/Archives/edgar/data/1476204/000147620421000128/ex-991july20218xkpressrele.htm)
documente le regroupement et la reclassification.

Une série portant le ticker actuel ne suffit donc pas à établir une trajectoire
tradable continue avant l'IPO. Il faut séparer les classes et leur négociabilité,
pas simplement corriger la clôture du 15 juillet par un facteur choisi.

### FBRT — échange CMO/FBRT et espèces

Le 19 octobre 2021, la série produit +163,08 %, reproduit par le fournisseur.
Son calendrier de splits reçu est vide, ce qui ne signifie pas absence
d'opération sur titres.

Le [communiqué officiel déposé à la SEC](https://www.sec.gov/Archives/edgar/data/1562528/000110465921125478/tm2129839d1_ex99-1.htm)
prévoit, pour une action Capstead CMO, **0,3288 action FBRT et 0,94 dollar
en espèces**. CMO cesse de coter le 18 octobre et FBRT commence le 19 octobre.
Comparer directement une unité CMO à une unité FBRT ne mesure donc pas le
rendement de l'actionnaire. Le ratio, les espèces, les fractions et l'identité
doivent être pris en compte.

À résoudre : confirmer la provenance exacte des prix pré-fusion et reconstruire
le raccordement économique. Ne pas appliquer à CMO un regroupement concernant
une autre classe ou l'ancienne société FBRT.

## Liste complète des alertes

Les pourcentages ci-dessous sont des variations reconstruites, pas des rendements
économiques certifiés. Les deux événements supplémentaires de KALV et REPX,
ainsi que celui d'EVVTY en septembre, restent sans relecture dédiée.

| Titre | Date | Rendement quotidien | Gap | Lecture prudente |
|---|---|---:|---:|---|
| ANAB | 10/10/2017 | +101,17 % | +52,03 % | Mouvement à qualifier, pas d'erreur démontrée |
| ASTH | 01/12/2016 | +106,67 % | +100,00 % | Historique prédécesseur/OTC, seulement 2 200 titres échangés |
| AXSM | 07/01/2019 | +161,22 % | +168,82 % | Annonce clinique contemporaine |
| BASFY | 09/10/2017 | +299,43 % | +299,64 % | Ratio ADR/raccordement prioritaire |
| CAR | 02/11/2021 | +108,31 % | +1,66 % | Pas d'erreur démontrée par la relecture |
| EVVTY | 06/06/2019 | +117,33 % | ≈0 % | ADR, split non standard reçu, volume de 9 |
| EVVTY | 04/09/2019 | +113,01 % | +4,26 % | Faible liquidité, volume de 869 |
| FBRT | 19/10/2021 | +163,08 % | +161,54 % | Échange d'actions et espèces |
| GRND | 18/11/2022 | +213,84 % | +45,31 % | Combinaison SPAC/cotation le même jour |
| KALV | 10/10/2017 | +38,64 % | +105,44 % | Alerte sur le gap, pas une hausse close/close de 100 % |
| KALV | 09/02/2021 | +114,61 % | +159,64 % | Pas d'erreur démontrée par la relecture |
| KRYS | 29/11/2021 | +121,65 % | +129,09 % | Pas d'erreur démontrée par la relecture |
| MFA | 25/03/2020 | +216,67 % | +100,00 % | Stress de liquidité COVID documenté |
| PECO | 06/07/2021 | +200,00 % | +200,00 % | Regroupement/classe non cotée, volume nul |
| PECO | 15/07/2021 | +281,76 % | +284,09 % | Raccordement pré-IPO/IPO |
| REPX | 21/10/2020 | +46,32 % | +178,21 % | Annonce de fusion du prédécesseur TGC |
| REPX | 28/01/2021 | +165,81 % | 0 % | Autre date encore à qualifier |
| XENE | 04/10/2021 | +101,92 % | +69,94 % | Annonce clinique contemporaine |

Sources de contexte, qui ne certifient pas les cours exacts :

- [AXSM : résultats cliniques du 7 janvier 2019](https://www.sec.gov/Archives/edgar/data/1579428/000110465919000962/a19-1343_1ex99d1.htm).
- [XENE : résultats de phase 2b](https://investor.xenon-pharma.com/news-releases/news-release-details/xenon-pharmaceuticals-announces-positive-topline-results-phase).
- [MFA : difficultés de marge de mars 2020](https://www.mfafinancial.com/sec-filings/all-sec-filings/content/0001055160-20-000010/exhibit991.htm).
- [GRND : combinaison et cotation de novembre 2022](https://investors.grindr.com/news/news-details/2022/Grindr-Announces-Third-Quarter-2022-and-Year-to-Date-Results-After-Listing-on-New-York-Stock-Exchange/default.aspx).
- [REPX/Tengasco : annonce du 21 octobre 2020](https://rileypermian.com/investors/press-releases/news-details/2020/Riley-Exploration--Permian-LLC-and-Tengasco-Inc.-Announce-Merger-Agreement/default.aspx).
- [EVVTY : programme ADR Citi](https://depositaryreceipts.citi.com/adr/guides/bookPdf.aspx?cusip=30051E104&effectDt=2019-05-21&secId=EVVTY).

## Artefacts, tests et suite

Racine :
`artifacts/research/us_concentrated_replay/oracle-feature-outliers-excluded5-20261007-v1/`.

- `report.json`, `protocol.json`, `progress.json` : scan et périmètre.
- `feature-maxima.parquet`, `large-jumps.parquet` : observations détaillées.
- `events/` : BASFY, PECO, MFA, GRND et REPX.
- `events-others/` : les neuf autres titres.
- Chaque dossier de relecture contient fenêtres locales, réponses brutes,
  splits, reconstruction et rapport avec hashes.

Le script de relecture accepte désormais une liste explicite d'événements :

```powershell
python -m scripts.research.us_oracle_remaining_price_events --events BASFY:2017-10-09,PECO:2021-07-15,FBRT:2021-10-19 --output artifacts/research/us_concentrated_replay/remaining-events-NEW
python -m pytest tests/test_us_oracle_remaining_price_events.py tests/test_us_oracle_feature_outliers.py tests/test_us_oracle_price_repair_plan.py tests/test_us_oracle_repair_qualification.py --no-cov -q
```

21 tests ciblés passent, notamment la validation stricte des événements et la
conservation du comportement par défaut du script.

Prochaine décision : qualifier correctement les trois raccordements prioritaires,
ou autoriser explicitement leur exclusion des univers. Aucune de ces deux options
n'a encore été appliquée. Ne pas retirer les 14 titres sur la seule amplitude.

Limites : trois familles de calculs examinées, pas toutes les features du modèle ;
pas de certification indépendante exhaustive OHLCV ; pas de preuve que ces
anomalies expliquent les pertes de 2024 ou l'absence de séparation D1/D10 ;
pas de résultat économique nouveau. Les modèles existants restent inchangés.

## Décision ultérieure — exclusion BASFY / PECO / FBRT

Le 7 octobre 2026, l'utilisateur a autorisé le retrait de ces trois titres des
fichiers d'univers US. Cette décision succède à l'audit : ses chiffres restent
ceux des **1 793 titres**, et ne constituent pas un nouveau scan des 1 790 restants.

| Fichier sous `config/` | Avant | Après | Retirés |
|---|---:|---:|---|
| `univers/univers_filtred.txt` | 2 691 | 2 688 | BASFY, FBRT, PECO |
| `univers/univers_filtred_tradable.txt` | 1 793 | 1 790 | BASFY, FBRT, PECO |
| `univers/univers_filtred_equities.txt` | 1 793 | 1 790 | BASFY, FBRT, PECO |
| `univers_batch/univers_filtred_tradable.txt` | 1 793 | 1 790 | BASFY, FBRT, PECO |
| `univers_bis/ticket_backtest.txt` | 937 | 936 | PECO |
| `univers_bis/ticket_live.txt` | 937 | 936 | PECO |
| `univers_bis/ticket_mid_cap.txt` | 937 | 936 | PECO |
| `univers_bis/univers_filtred_2016.txt` | 2 254 | 2 252 | BASFY, FBRT |

Huit fichiers modifiés ; les 24 fichiers texte des trois répertoires ont été
vérifiés. Aucun ne contient KNTK, AMTB, DEC, TALO, INDV, BASFY, PECO ou FBRT.
Les autres symboles et leur ordre sont conservés. Maintenir ces exclusions au
renouvellement des fichiers tant que les historiques restent non qualifiés.

Aucune suppression SQL ni modification de modèle, de prédiction ou de processus.
Les exclusions concernent les traitements qui relisent ces fichiers ; elles ne
réparent pas les anciens entraînements et ne bloquent pas les sources SQL ou
les listes explicites. Aucun blacklistage applicatif global n'a été ajouté.

## Contrôle après huit exclusions — 1 790 titres

Le nouveau scan du 7 octobre est **terminé**, sur 4 950 873 barres. Même
fenêtre de lecture (27/12/2012–31/12/2024), même début de mesure (01/01/2016),
mêmes trois calculs et mêmes règles de segmentation : les résultats sont
comparables au scan précédent, mais restent un audit partiel des features.

Empreinte SHA-256 de l'univers utilisé :
`d84c50d7b78a74b98c77431d0ab9b230b8e39e53fa703acdd722bfda8ca3290f`.

| Mesure | Avant retrait BASFY/PECO/FBRT | Après retrait |
|---|---|---|
| Titres | 1 793 | 1 790 |
| Barres lues | 4 957 887 | 4 950 873 |
| Grandes variations détectées | 18 sur 14 titres | 14 sur 11 titres |
| Maximum rendement quotidien | BASFY : +299,43 % | MFA, 25/03/2020 : +216,67 % |
| Maximum gap | BASFY : +299,64 % | REPX, 21/10/2020 : +178,21 % |
| Maximum volatilité 20 observations | PECO : 0,781388 | MFA, 08/04/2020 : 0,564659 |

Les 11 titres encore présents dans les alertes sont ANAB, ASTH, AXSM, CAR,
EVVTY, GRND, KALV, KRYS, MFA, REPX et XENE. La liste détaillée plus haut reste
valide pour leurs dates. Les quatre observations supprimées correspondent
à BASFY, FBRT et aux deux dates PECO ; il ne s'agit pas de quatre corrections
de prix démontrées par ce scan.

Les maxima restants MFA et REPX coïncident avec des contextes événementiels
documentés plus haut. Cela évite de conclure automatiquement à une erreur,
mais ne remplace pas une certification indépendante du prix exact ni du
raccordement au prédécesseur. ASTH et EVVTY conservent notamment leurs réserves
de liquidité et d'identité. Il n'est pas justifié de retirer tous ces titres
uniquement parce que leurs rendements sont élevés.

### Trois relectures complémentaires

Pour compléter les dates non relues individuellement lors du passage précédent,
trois fenêtres fournisseur supplémentaires ont été archivées. Toutes ont été
reçues et reproduisent les variations locales :

| Titre | Date | Rendement local et relu | Gap local et relu |
|---|---|---:|---:|
| EVVTY | 04/09/2019 | +113,01 % | +4,26 % |
| REPX | 28/01/2021 | +165,81 % | 0 % |
| KALV | 10/10/2017 | +38,64 % | +105,44 % |

Aucun split reçu ne tombe exactement sur ces trois dates. Cette observation
n'exclut ni une autre opération sur titres ni une série mal raccordée. Un
simple rechargement de ces mêmes réponses ne ferait pas disparaître les sauts.

### Reproduction et limites de clôture

```powershell
python -m scripts.research.us_oracle_feature_outliers --universe config/univers/univers_filtred_tradable.txt --output artifacts/research/us_concentrated_replay/oracle-feature-outliers-excluded8-NEW
python -m scripts.research.us_oracle_remaining_price_events --events EVVTY:2019-09-04,REPX:2021-01-28,KALV:2017-10-10 --output artifacts/research/us_concentrated_replay/oracle-feature-outliers-excluded8-events-NEW
```

Artefacts terminés :

- `artifacts/research/us_concentrated_replay/oracle-feature-outliers-excluded8-20261007-v1/`
  : protocole, progression finale, rapport, maxima et grandes variations.
- `artifacts/research/us_concentrated_replay/oracle-feature-outliers-excluded8-events-20261007-v1/`
  : trois relectures, réponses brutes, fenêtres et hashes.

Les 21 tests ciblés ont été réexécutés avec succès. Aucun processus de recherche
de ce passage ne reste en cours. Aucun nouveau titre retiré ; aucun modèle,
batch, code applicatif ou donnée SQL modifié.

Le contrôle des anciennes valeurs démesurées est réalisé sur cet univers.
Il ne certifie pas toutes les features, les labels H20 ou les données 2025–2026.
Avant de prétendre qu'un nouvel entraînement est assaini, compléter le contrôle
du jeu réellement utilisé : valeurs non finies, couverture, distributions des
features et continuité des labels. La qualification des événements réservés
reste distincte ; ni un écrêtage arbitraire ni un retrait automatique ne sont
validés par cet audit.

Suite lancée : [audit du contrat complet Oracle H20 et des labels existants](us_oracle_h20_dataset_quality_audit.md).
Il distingue reconstruction sur l'univers réduit et validation des anciens labels.
