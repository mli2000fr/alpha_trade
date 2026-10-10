# Oracle US — localisation des features extrêmes et audit des prix

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Résultat et limites

Audit du 7 octobre 2026, suite de l'[audit de reproductibilité](us_oracle_reproducibility_audit.md).
Les trois maxima suspects du journal du batch `model-factory-20261003082853-e98332`
sont reproduits exactement à la précision du log et proviennent de **KNTK**.
La série locale contient des prix incohérents avant le 13 novembre 2018.
**AMTB** présente une deuxième rupture majeure et des features longues polluées.

La relecture EODHD actuelle et sa transformation split-only par l'adaptateur
du projet éliminent ces sauts. Les reconstructions sont des fichiers de
recherche : aucune donnée SQL, aucun modèle ni configuration live n'a été
modifié ; aucun entraînement n'a été lancé.

Il s'agit d'une comparaison avec le **même fournisseur**, pas d'une certification
indépendante de tous les prix. L'origine exacte de la corruption historique
(ancienne réponse EODHD, transformation, cache ou migration) n'est pas établie.
L'impact causal sur les performances 2024 n'est pas mesuré.

## Périmètre et méthode

- Même fichier `config/univers/univers_filtred_tradable.txt` : 1 798 symboles,
  SHA-256 `d57d85d35c18717cc44747cdd99b2b0c8e48319a902402f19c515c2e8fb0001f`,
  identique au protocole de l'audit Oracle précédent.
- Lecture de **4 967 964 barres** entre 2012-12-27 et 2024-12-31, préchauffage
  compris ; classement des features à partir de 2016-01-01.
- Petits lots de 100 symboles, transactions de lecture seule sur `alpha_trade`.
- Mêmes segments de continuité enregistrés que `oracle/dataset.py` : WFRD/CHRD.
- Reconstruction avec `_build_adjusted_price_frame`, puis mêmes formules
  de rendement, gap et écart-type roulant 20, sans nettoyage silencieux.
- Vérification complémentaire avec `compute_features(feature_set="expert",
  include_factors=True)` sur les deux histoires complètes.

Cette dernière reproduction omet benchmark et contexte screener/short-score :
les formules de prix suspectes sont identiques, mais ce n'est pas une
reconstruction intégrale des 173 features ni du dataset d'entraînement figé.
Le dataset historique exact et ses lignes de folds restent non archivés.

## Localisation exacte des trois maxima

| Feature du journal | Titre / date | Valeur reproduite | Origine |
|---|---|---:|---|
| `daily_return` | KNTK / 2018-11-13 | 45 499 | 91 / 0,002 − 1 |
| `overnight_gap` | KNTK / 2018-11-13 | 47 749 | 95,5 / 0,002 − 1 |
| `rolling_volatility_20` | KNTK / 2018-11-29 | 10 173,887636 | écart-type de la fenêtre contenant le saut |

Les valeurs du journal sont en **unités de rendement**, pas en pourcentage.
45 499 correspond à +4 549 900 %, et non +45 499 %.
Le calcul partagé ne crée pas ce prix de 0,002 : il reçoit la série locale et
effectue la division attendue. Les valeurs finies mais absurdes passent les
contrôles qui excluent uniquement NaN/inf.

## KNTK — série locale incompatible avec la reconstruction actuelle

### Comparaison sur une base split-only commune

| Donnée | Base locale | EODHD relu + adaptateur split-only |
|---|---:|---:|
| Clôture 2018-11-12 | 0,002 $ | 99,00 $ |
| Ouverture 2018-11-13 | 95,50 $ | 95,452 $ |
| Clôture 2018-11-13 | 91,00 $ | 91,00 $ |
| Rendement clôture/clôture | +4 549 900 % | −8,08 % |
| Gap ouverture/précédente clôture | +4 774 900 % | −3,58 % |

Les bruts historiques EODHD relus valent 9,90 puis 9,10. La liste complète
des splits renvoie un regroupement 1:20 au 1er juillet 2020, puis 2:1 au
9 juin 2022. Leur facteur cumulé conduit à multiplier ces anciens prix par
dix. Comparer directement 91 local à 9,10 brut serait une fausse anomalie
d'échelle ; l'anomalie réelle est **0,002 contre 99**, avant le raccordement.

Sur les 1 807 dates communes, **265 dates**, du 2 mai 2017 au 12 novembre 2018,
diffèrent de plus de 1 % de la reconstruction actuelle. La série locale de
cette ancienne période est à examiner intégralement, pas seulement sa dernière
barre. Les volumes diffèrent aussi ; ne pas réparer uniquement `close`.

### Identité et événement

Le [communiqué officiel du 12 novembre 2018](https://ir.kinetik.com/news/news-details/2018/Apache-and-Kayne-Anderson-Acquisition-Corporation-Announce-Closing-of-Transaction-to-Create-Altus-Midstream-Company-a-Pure-Play-Permian-Basin-Midstream-C-Corp/default.aspx)
documente la combinaison avec Kayne Anderson Acquisition et le passage KAAC
vers ALTM, à compter du 12 novembre. Ce contexte exige une chaîne historique
de symboles vérifiée ; il ne justifie pas un rendement de plusieurs millions
de pour cent le lendemain. Il ne suffit pas non plus à déclarer arbitrairement
une rupture économique totale ou supprimer l'histoire du SPAC.

Dans les données locales, les deux côtés portent `instrument_id=17005`.
Le référentiel actuel indique Kinetik Holdings, MIC XNYS, sans dates de
cotation/radiation renseignées. Ce MIC actuel n'est pas la preuve de la place
en 2018. Un identifiant constant ne certifie pas le rattachement historique.

### Propagation dans les features

Le 29 novembre 2018, avec le générateur partagé :

| Feature | Historique local | Reconstruction fournisseur |
|---|---:|---:|
| volatilité 20 séances | 10 173,887636 | 0,035721 |
| volatilité 60 séances | 5 873,896004 | 0,021361 |
| momentum 250 séances | 38 199 | −0,212371 |

La contamination touche donc rendements, volatilités et momentums longs,
puis potentiellement les interactions, z-scores et rangs cross-sectionnels.
Les pairs peuvent avoir leurs rangs modifiés si un titre change de rang ;
l'ampleur de cet effet n'a pas été recalculée ici. Les écarts sur des dates
plus tardives ne sont pas tous imputables au seul saut : le fournisseur a
également révisé d'autres prix et certaines dates de disponibilité diffèrent.

**Ne pas confondre avec KNTK novembre 2020** étudié précédemment dans
[la qualification des mouvements extrêmes](us_extreme50_price_qualification.md).
Ce nouveau constat 2018 n'invalide pas automatiquement le saut de 2020, que
la relecture fournisseur reproduisait. Aucun retrait global du symbole.

## AMTB — autre rupture et pollution à longue fenêtre

| Donnée | Base locale | Reconstruction split-only actuelle |
|---|---:|---:|
| Clôture 2018-10-17 | 0,108 $ | 26,25 $ |
| Clôture 2018-10-18 | 30,00 $ | 30,00 $ |
| Rendement | +27 677,78 % | +14,29 % |

L'avis [Nasdaq ECA2018-187](https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2018-187)
documente regroupement 1:3, changement MBNAA/MBNAB vers AMTB/AMTBB et CUSIP.
Le [communiqué de la société du 30 octobre 2018](https://investor.amerantbank.com/sec-filings/all-sec-filings/content/0001734342-18-000015/mercantil3q18earningsrelea.htm)
situe le regroupement au 23 octobre ; EODHD le date du 24. Cette différence
de date opérationnelle doit être conservée comme réserve, pas harmonisée
silencieusement. Elle n'explique pas le saut local du **18 octobre**, ni un
facteur d'environ 278 entre clôtures.

Dans le générateur expert local de contrôle, les premières lignes retenues
commencent le 28 août 2019 : la ligne du saut journalier 2018 est donc éliminée
par le préchauffage. **Cela ne rend pas la série saine** : le momentum 250
atteint encore 221,54 le 28 août 2019, parce qu'il compare au mauvais prix
d'origine. Ne pas affirmer que la ligne `daily_return` du 18 octobre a été
directement entraînée dans ce batch ; le dataset exact n'est pas disponible.

Sur 1 588 dates communes, 44 prix locaux diffèrent de plus de 1 % de la
reconstruction. Ce n'est pas un intervalle continu : outre 2018, des prix
répétés localement en août/septembre 2023 sont différents du fournisseur.
Il faut inventorier les périodes séparément, pas écraser toute l'histoire.

L'identifiant local est constamment `1810`, avec dates listing/delisting
absentes du référentiel actuel. Même réserve de certification historique.

## Provenance en base et pourquoi les contrôles n'ont pas arrêté le calcul

Les mêmes prix suspects sont présents dans **`stock_bars_daily` et `stock_bars`
timeframe `1D`**. Ce n'est pas seulement un artefact du resampling journalier.

- `data_source=eodhd_eod`, `data_adjustment=split`, `is_filled=0` ;
- premières ingestions enregistrées : AMTB 29 avril 2026, KNTK 30 avril 2026 ;
- `last_updated` journalier : 20 septembre 2026 sur les points examinés ;
- aucune ligne corporate-actions locale 2018–2019 pour ces deux titres dans
  `corporate_actions_events` à la consultation ; cette absence n'est pas
  preuve d'absence d'opération historique ;
- le registre de discontinuités ne contient pas ces deux cas.

L'étiquette EODHD ne permet pas de retrouver la réponse brute réellement reçue
en avril. Les prix historiques actuels diffèrent de la relecture ; la version
d'import et les anciens payloads n'ont pas été identifiés dans cette étude.

Important : dans l'adaptateur actuel, **`adj_close=close` est intentionnel** :
la table conserve du split-only, pas le total-return dividendes inclus d'EODHD.
Il ne faut pas remplacer cette colonne uniquement par `adjusted_close`
fournisseur sans revoir tout le contrat OHLC et corporate actions.

Les contrôles actuels sont insuffisants pour ce cas : prix positifs, volumes
positifs, même identifiant et features finies ne garantissent pas une série
cohérente. La validation des labels futurs n'assainit pas automatiquement
les fenêtres passées des features. Un prix faux dans une fenêtre longue
peut polluer le dataset même si son propre label est exclu.

## Autres grandes variations : liste de revue, pas liste d'erreurs

Le balayage repère **27 observations sur 19 titres** avec rendement journalier
absolu supérieur à 100 % ou gap absolu supérieur à 100 % :

AMTB, ANAB, ASTH, AXSM, BASFY, CAR, DEC, EVVTY, FBRT, GRND, INDV, KALV,
KNTK, KRYS, MFA, PECO, REPX, TALO, XENE.

Certains mouvements peuvent être parfaitement réels. Ce seuil est uniquement
un détecteur d'audit et n'a pas été transformé en filtre de production.
Il ne repère pas toutes les erreurs possibles, notamment les baisses proches
de −100 %, les petits sauts d'échelle et les historiques figés.

## Décision et prochaine correction à préparer, après autorisation

1. Conserver les exports avant correction et qualifier les réponses, splits,
   anciens symboles et périodes concernées.
2. Préparer une réparation ciblée et idempotente des deux tables, avec un
   diff OHLCV et journal d'audit ; ne pas patcher une seule clôture ou ajouter
   une fausse discontinuité pour cacher un prix erroné.
3. Ajouter un contrôle bloquant ou une quarantaine explicite avant calcul des
   features : anomalie candidate → preuve/examen, jamais suppression aveugle
   de tout mouvement élevé.
4. Recalculer les features concernées, leurs fenêtres longues et leurs rangs
   cross-sectionnels ; identifier les labels/artefacts dépendants à invalider.
5. Seulement ensuite envisager un nouveau batch versionné et une comparaison
   figée, sans prétendre que cette correction garantira le succès directionnel.

Les modèles existants ne sont pas corrigés par une réparation de la base :
leurs arbres garderaient l'entraînement ancien. Aucune réparation ni invalidation
automatique n'est autorisée ou effectuée par le présent audit.

## Artefacts, commandes et tests

Racine : `artifacts/research/us_concentrated_replay/oracle-feature-outliers-20261007-v1`.

- `protocol.json`, `progress.json`, `report.json` : périmètre et maxima ;
- `feature-maxima.parquet`, `large-jumps.parquet`, `suspect-bars.parquet` ;
- `evidence/` : premières relectures bornées, référentiel et événements locaux ;
- `comparison/` : réponses EODHD complètes des deux titres, listes de splits,
  reconstructions sans écriture SQL et comparaison du générateur ;
- `provenance-v2/` : provenance complète des deux tables et synthèse des écarts.

`provenance/` est le premier essai avec un filtre timeframe `1Day`, qui ne
correspondait pas au stockage `1D`. Sa conclusion vide sur `stock_bars` est
remplacée par **`provenance-v2/`** ; ne pas l'utiliser comme preuve d'absence.

```powershell
python -m scripts.research.us_oracle_feature_outliers --output artifacts/research/us_concentrated_replay/oracle-feature-outliers-NEW
python -m scripts.research.us_oracle_outlier_evidence --source artifacts/research/us_concentrated_replay/oracle-feature-outliers-NEW --output artifacts/research/us_concentrated_replay/oracle-feature-outliers-NEW/evidence
python -m scripts.research.us_oracle_outlier_comparison --source artifacts/research/us_concentrated_replay/oracle-feature-outliers-NEW --output artifacts/research/us_concentrated_replay/oracle-feature-outliers-NEW/comparison
python -m scripts.research.us_oracle_outlier_provenance --root artifacts/research/us_concentrated_replay/oracle-feature-outliers-NEW
```

Utiliser une nouvelle sortie ; relecture réseau = huit requêtes EODHD dans
l'audit effectué, pas de téléchargement de tout l'univers. Les secrets et
URLs contenant des clés API ne sont pas enregistrés dans les rapports.
Les artefacts fournisseur sont une observation actuelle, non PIT historique.

Neuf tests ciblés de recherche passent, dont deux nouveaux sur l'absorption
d'un split normal et la reproduction d'un mauvais prix sans nettoyage masqué.

## Suite : plan de réparation et sensibilité hors base (7 octobre 2026)

Le script `scripts/research/us_oracle_price_repair_plan.py` prépare un diff en
**lecture SQL seule**. Il ne possède volontairement aucun mode d'écriture.
Il reconstruit les propositions depuis les réponses EODHD déjà archivées,
sans nouvel appel fournisseur, en réutilisant le contrat split-only existant.

Sortie de référence :
`artifacts/research/us_concentrated_replay/oracle-feature-outliers-20261007-v1/repair-plan-v2/`.
Le premier `repair-plan-v1/` ne contient pas la sensibilité hors base ; utiliser v2.

| Titre | Dates candidates | Nombre | Statut |
|---|---|---:|---|
| KNTK | 2017-05-02 à 2018-11-12 | 265 | Anomalie ancienne d'échelle ; proposition à valider |
| AMTB | 2018-08-29 à 2018-10-17 | 35 | Anomalie ancienne d'échelle ; réserve supplémentaire ci-dessous |
| AMTB | 2023-08-29 à 2023-09-11 | 9 | Revue distincte requise |

Le critère de sélection est un écart de clôture supérieur à 1 % entre base
actuelle et reconstruction fournisseur. **Ce n'est ni une certification
d'erreur pour chaque date ni un audit exhaustif de tous les champs OHLCV.**
Les 309 dates ont une proposition pour chacune des deux tables : 618 lignes
de table au total, pas 618 journées distinctes.

### Sauvegarde et garanties du plan

- `candidates.parquet` sépare les anomalies anciennes des neuf dates de 2023.
- `stock_bars_daily-before.parquet` et `stock_bars-before.parquet` conservent
  toutes les colonnes des lignes concernées, dont identité et provenance.
- Les fichiers `*-proposed.parquet` et `*-diff.json` détaillent les valeurs
  proposées : 1 863 différences de champs daily et 1 554 dans `stock_bars`.
- `report.json` contient les empreintes des sources, sauvegardes et propositions.
- Aucune insertion de clé manquante : une clé absente ou ambiguë bloque le plan.
- OHLC positifs/finis, cohérence haut/bas et volume entier non négatif sont
  vérifiés ; ces contrôles mécaniques ne certifient pas un historique financier.
- `instrument_id` et les métadonnées non ciblées sont conservés. `adj_close`
  reste égal au close split-only ; le proxy VWAP existant est respecté.
- L'idempotence de la proposition est testée. L'idempotence transactionnelle
  d'une réparation SQL n'est pas revendiquée : aucun applicateur SQL n'existe ici.

### Résultat de la sensibilité et nouvelle réserve AMTB

`offline-sensitivity.json` recalcule les trois features simples sur les deux
historiques exportés : local, remplacement des 300 dates anciennes seulement,
puis remplacement de toutes les 309 dates candidates. Il ne recalcule pas
les 173 features ni les rangs cross-sectionnels de l'univers complet.

Sur KNTK, la proposition supprime les maxima 45 499 / 47 749 / 10 173,89.
Le maximum restant de rendement journalier est +204,49 % au 2020-11-05,
événement distinct déjà étudié : aucun écrêtage automatique n'est appliqué.

Sur AMTB, le saut local de +27 677,78 % au 2018-10-18 disparaît, **mais le
fournisseur reconstruit conserve +518,00 % au 2018-09-04** : clôture 28,17
le 31 août puis 174,09 le 4 septembre. Ce mouvement existe aussi dans
l'historique local avec une autre échelle ; il n'est pas créé par la proposition.
La volatilité quotidienne sur 20 séances reste ainsi très élevée (maximum
1,18219 en unités de rendement).

**Décision : ne pas appliquer automatiquement AMTB.** Qualifier le contexte
de cotation/identité et les cours 2018 avant d'approuver cette branche. La
réponse actuelle du même fournisseur n'est pas une preuve indépendante.
Les neuf dates de 2023 restent un dossier séparé ; leur remplacement ne règle
pas cette réserve de 2018. KNTK peut être traité séparément après validation
de son propre diff, sans attendre ni accepter implicitement AMTB.

Avant toute application future, relire et comparer les lignes courantes aux
sauvegardes, appliquer les deux tables dans une transaction bornée avec journal
de réparation, puis vérifier les fenêtres longues et les dépendances des labels.
Une sauvegarde parquet seule ne constitue pas encore une procédure de rollback
SQL validée. Ne pas réentraîner avant cette qualification.

```powershell
python -m scripts.research.us_oracle_price_repair_plan --root artifacts/research/us_concentrated_replay/oracle-feature-outliers-20261007-v1 --output artifacts/research/us_concentrated_replay/oracle-feature-outliers-20261007-v1/repair-plan-NEW
python -m pytest tests/test_us_oracle_price_repair_plan.py tests/test_us_oracle_feature_outliers.py --no-cov -q
```

Huit tests ciblés passent (six nouveaux et deux tests existants). Aucun modèle,
batch, calcul de production ou ligne SQL n'a été modifié pendant cette suite.

## Qualification distincte des trois dossiers

Résultat conservé dans `qualification-v1/report.json`, sous la même racine
d'audit. Le script `scripts/research/us_oracle_repair_qualification.py` est
entièrement hors base et hors réseau : il vérifie les empreintes du plan v2,
la parité OHLCV daily/1D, le maintien des identités et dates d'ingestion,
ainsi que le contrat split-only. Les 13 tests des trois scripts ciblés passent.

### KNTK : correction fournisseur ciblée étayée, non appliquée

Les 265 clôtures locales du dossier valent **toutes 0,002 $**. Les volumes
ne changent sur aucune de ces 265 propositions ; les différences de volumes
évoquées dans l'audit plus large ne doivent donc pas leur être attribuées.

Le [10-K officiel 2017 de Kayne Anderson Acquisition](https://www.sec.gov/Archives/edgar/data/1692787/000119312518097812/d508785d10k.htm),
Item 5, distingue explicitement les actions KAAC des unités KAACU et warrants
KAACW. Il donne les fourchettes trimestrielles de **bid** suivantes pour les
actions, avant les splits ultérieurs :

| Trimestre 2017 | Bid officiel bas–haut | Clôtures brutes fournisseur min–max | Dates comparées |
|---|---:|---:|---:|
| T2 | 9,70–9,76 $ | 9,70–9,76 $ | 22 |
| T3 | 9,70–9,79 $ | 9,70–9,75 $ | 35 |
| T4 | 9,64–10,01 $ | 9,65–9,78 $ | 51 |

Les 108 observations sont compatibles avec ces fourchettes. **Une fourchette
de bid trimestrielle ne certifie pas les OHLCV journaliers ni leur complétude.**
Ce contrôle indépendant étaye l'ordre de grandeur et le type de titre, pas
une certification quotidienne intégrale.

Les communiqués de l'émetteur confirment aussi les deux opérations nécessaires
à l'échelle proposée : [regroupement 1:20, cotation ajustée au 1er juillet 2020](https://ir.kinetik.com/news/news-details/2020/Altus-Midstream-Announces-One-for-Twenty-Reverse-Stock-Split/default.aspx)
et [split 2:1, cotation ajustée au 9 juin 2022](https://ir.kinetik.com/news/news-details/2022/Kinetik-Announces-Two-For-One-Split-of-its-Common-Stock/default.aspx).
Cela justifie le facteur cumulé 0,1 utilisé par l'adaptateur pour ces dates
anciennes. La proposition KNTK est éligible à une correction fournisseur
ciblée après autorisation, indépendamment d'AMTB ; pas à une déclaration
« historique entièrement certifié ».

### AMTB 2023 : prix figés au transfert de place

Les neuf dates candidates, du 29 août au 11 septembre 2023, ont toutes une
clôture locale de **18,58 $ et un volume nul**, avec `is_filled=0` dans
l'historique audité. La relecture fournit des prix variables de 18,77 à
19,70 $ et des volumes strictement positifs pour les neuf dates.

Le [8-K officiel du 3 août 2023](https://www.sec.gov/Archives/edgar/data/1734342/000173434223000052/amtb-20230803.htm)
annonce la fin de cotation Nasdaq au 28 août et le début NYSE au 29 août,
avec le même symbole AMTB. La [FAQ de l'émetteur](https://investor.amerantbank.com/company-information/faq)
confirme ce transfert. Le début des prix figés coïncide donc exactement avec
le transfert : **hypothèse de raccordement de place**, non preuve de la cause
de l'ancien importeur. Ne pas inventer une nouvelle identité économique,
un split ou une suspension pour masquer ces valeurs.

Ces neuf dates peuvent faire l'objet d'une correction distincte à partir du
fournisseur, sans approuver AMTB 2018. Les valeurs OHLCV journalières proposées
restent une relecture EODHD, pas une seconde source quotidienne indépendante.

### AMTB 2018 : date du split clarifiée, prix encore réservés

L'[avis Nasdaq ECA2018-187](https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2018-187)
annonce explicitement une prise d'effet le **mercredi 24 octobre 2018** pour
le reverse split, le symbole et le CUSIP. Le communiqué de l'émetteur parle
de l'opération le 23 octobre. Il ne faut plus présenter cela comme une preuve
que la date de séance d'EODHD est fausse : elle est conforme à l'avis Nasdaq.
La distinction opération juridique / prise d'effet en cotation explique
plausiblement la différence, sans justifier de déplacer une barre.

Le [S-1 d'octobre 2018](https://investor.amerantbank.com/sec-filings/all-sec-filings/content/0001193125-18-295574/d613972ds1.htm)
signale des échanges peu fréquents depuis la scission. Cette information ne
prouve ni que +518 % est réel, ni qu'il est faux. Les 35 dates anciennes
restent donc **en attente de preuve quotidienne suffisante** : pas de
correction automatique, pas de winsorisation, pas de rupture artificielle.

### Périmètre proposé pour la suite

Traiter séparément **265 dates KNTK + 9 dates AMTB 2023 = 274 dates**, soit
548 lignes dans les deux tables, en conservant les 35 dates AMTB 2018 en revue.
Un futur applicateur devra exiger les empreintes validées, vérifier les valeurs
actuelles sous verrou transactionnel, refuser tout changement concurrent,
mettre à jour les deux tables ensemble et journaliser les valeurs avant/après.
Le plan présent ne l'exécute pas : aucune donnée SQL n'a été changée.

## Décision utilisateur : retrait des fichiers d'univers

À la demande de l'utilisateur, KNTK et AMTB ont été retirés des fichiers
d'univers US plutôt que de réparer leurs prix en base à ce stade.

| Fichier sous `config/` | Avant | Après | Retrait |
|---|---:|---:|---|
| `univers/univers_filtred.txt` | 2 696 | 2 694 | AMTB, KNTK |
| `univers/univers_filtred_tradable.txt` | 1 798 | 1 796 | AMTB, KNTK |
| `univers/univers_filtred_equities.txt` | 1 798 | 1 796 | AMTB, KNTK |
| `univers_batch/univers_filtred_tradable.txt` | 1 798 | 1 796 | AMTB, KNTK |
| `univers_bis/ticket_mid_cap.txt` | 939 | 938 | KNTK (AMTB déjà absent) |
| `univers_bis/ticket_live.txt` | 939 | 938 | KNTK (AMTB déjà absent) |
| `univers_bis/ticket_backtest.txt` | 939 | 938 | KNTK (AMTB déjà absent) |

Vérification des 24 fichiers `.txt` de ces trois répertoires : aucun des deux
symboles n'y reste ; tous les autres symboles et leur ordre sont inchangés.
Les fichiers des marchés CN/FR ne sont pas concernés. Les données SQL, modèles,
prédictions, journaux et univers archivés des anciennes expériences sont conservés.

Ce retrait n'assainit pas rétroactivement les modèles déjà entraînés et n'est
pas une exclusion globale dans le code. Il s'applique aux traitements qui
relisent ces fichiers. Une tâche déjà lancée peut avoir chargé son ancien
univers ; aucun processus n'a été arrêté. Une source SQL, un univers publié
ou une liste explicite peuvent encore contenir ces titres. Un renouvellement
des fichiers doit maintenir cette exclusion tant que les historiques restent
réservés. Les audits antérieurs restent liés à leurs univers et empreintes
originales ; ne pas les présenter comme recalculés sur les 1 796 titres.

### Contrôle réalisé après exclusion

Le [nouveau balayage des 1 796 titres](us_oracle_post_exclusion_price_audit.md)
est terminé : maxima initiaux supprimés, mais raccordement de split DEC
incohérent et grandes ruptures TALO/INDV persistantes chez le fournisseur.
Ne pas considérer l'univers entier comme qualifié sur la seule exclusion
des deux premiers titres. Aucun autre symbole n'a été retiré.
