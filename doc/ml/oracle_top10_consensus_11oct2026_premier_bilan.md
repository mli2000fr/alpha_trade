# TOP10 Oracle du week-end du 11 octobre : consensus et prix au 19 octobre 2026

## Conclusion bornée

**Pas d'avantage directionnel observé sur ces cinq séances**, avec les deux
lectures simples du consensus examinées. Cela n'établit ni une fiabilité ni une
absence définitive d'utilité du consensus : dix titres, un seul contexte de
marché, périodes/units fiscales encore non qualifiées, horizon H20 non arrivé.
Les résultats ci-dessous ne justifient ni de promouvoir ni d'inverser une règle.
Il s'agit de concordance directionnelle avec le **cours**, pas d'une mesure
de l'exactitude des bénéfices estimés. Cette dernière demande les résultats
publiés de la même période et une identité fiscale qualifiée.

## Dates, sélection et provenance

Le **11 octobre 2026 était un dimanche**. Il n'existe pas de séance/prédiction
daily de cette date dans la table Oracle actuelle. Le classement réellement
disponible ce week-end est conservé dans l'archive d'analyse :

- Run : `llm-bc155d0d71484217b0bdc98cd9e06c7d` ; terminé le 10 octobre à 17:10:59 UTC.
- Modèle : `model-factory-20261003082853-e98332`, ancien Oracle, pas le nouveau
  modèle entraîné le 16 octobre.
- Séance du classement : **9 octobre**, univers archivé
  `universe-file:univers_filtred_tradable.txt`.
- Dix premiers parmi les 100 candidats archivés, ordre `oracle_rank` original,
  sans filtre GPT et sans retri selon les rendements. Empreinte d'archive vérifiée.
- Le sous-run de comparaison GPT/DeepSeek sur **11 titres** n'est pas ce TOP10 :
  il s'agissait d'un sous-ensemble de recherche différent ; il n'a pas été utilisé.

Les anciennes prédictions de cette période ne sont plus dans
`oracle_extreme_predictions`. Leur classement est repris de l'archive existante,
pas recalculé avec un modèle plus récent. Aucun réentraînement ni remplissage SQL.

Consensus : uniquement `stock_analyst_consensus_eodhd_history.snapshot_date =
2026-10-11`, réception effective avant l'ouverture du 12 octobre. Valeurs
originellement reçues, pas les snapshots du 18/19 substitués.

Au contrôle du 19 octobre au matin, avant ouverture US, le dernier cours de
clôture disponible est celui du **16 octobre**. Il ne s'agit pas d'une quote
temps réel du 19. Barres `stock_bars_daily`, provenance `eodhd_eod`, ajustement
`split`, OHLC positifs/cohérents, séances complètes, pas de barre synthétique.
Les dix cours du 9 octobre correspondent exactement aux clôtures archivées
avec le classement. Aucun événement d'opération sur titres connu dans la table
source pour ces dix titres entre les deux dates ; ce contrôle n'est pas une
certification indépendante exhaustive des prix/identités.

## Prix et lecture EPS du 11 octobre

Prix en USD. Variation de clôture à clôture du 9 au 16 octobre. EPS : variation
de `eps_current` par rapport à `eps_7d_ago`, divisée par la valeur absolue de
la référence ; une amélioration d'un EPS négatif est bien une amélioration,
pas une détérioration. Les cas près de zéro peuvent afficher de grands ratios.

| Rang | Titre | Clôture 09/10 | Clôture 16/10 | Variation prix | Variation consensus EPS / réf. J−7 | Solde révisions 30 j |
|---:|---|---:|---:|---:|---:|---:|
| 1 | CCOI | 8,54 | 8,07 | −5,50 % | +2,84 % | −1 |
| 2 | MXL | 96,16 | 71,32 | −25,83 % | 0,00 % | +8 |
| 3 | SSTK | 4,35 | 4,44 | +2,07 % | +191,67 % | −1 |
| 4 | COHR | 312,62 | 232,90 | −25,50 % | +0,23 % | +17 |
| 5 | CCB | 40,74 | 42,02 | +3,14 % | −2,76 % | −1 |
| 6 | QDEL | 13,42 | 12,91 | −3,80 % | −14,36 % | 0 |
| 7 | FICO | 667,58 | 771,19 | +15,52 % | −0,48 % | +1 |
| 8 | BAND | 53,27 | 43,34 | −18,64 % | 0,00 % | +2 |
| 9 | PENG | 76,28 | 57,10 | −25,14 % | +0,74 % | +1 |
| 10 | VICR | 266,07 | 191,50 | −28,03 % | +19,61 % | +2 |

Le solde 30 jours est `revisions_up_30d − revisions_down_30d`, pas le nombre
d'analystes ni une probabilité. Pour SSTK, EPS passe de **−0,12 à +0,11** : le
+191,67 % ne signifie pas une prévision de hausse du cours de 191,67 %.

## Deux règles descriptives, sans optimisation

Le protocole est écrit avant lecture des prix futurs. Période EPS primaire :
`horizon_raw = 0q`, période fiscale la plus proche du 11 octobre dans J−120 à
J+400 jours ; aucune substitution par une période ayant mieux prédit le prix.
Les autres horizons sont conservés dans le rapport pour examen, pas utilisés
pour choisir rétroactivement le signal gagnant.

Ce choix est une convention de recherche, **pas** une certification que `0q`
désigne bien le prochain trimestre à publier. Les dix champs restent
`RESEARCH_ONLY`, sans qualification des unités et de l'identité fiscale.
Pour SSTK, la période retenue est le 30 juin ; pour PENG le 31 août ; pour les
huit autres le 30 septembre. Cette réserve doit précéder toute utilisation ML.

Afin de ne pas attribuer au signal du dimanche un gap déjà passé, la mesure
prospective part de **l'ouverture du lundi 12**, jusqu'à la clôture du vendredi 16.

| Lecture simple du consensus | Effectif | Résultat observé |
|---|---:|---|
| EPS amélioré depuis la référence J−7 | 5 | 1 hausse, 4 baisses ; variation moyenne de prix −15,96 % |
| EPS dégradé | 3 | 1 baisse, 2 hausses ; variation moyenne +4,36 % |
| EPS inchangé | 2 | 2 baisses ; pas de direction prédite |
| Solde révisions 30 j positif | 6 | 1 hausse, 5 baisses ; variation moyenne −17,64 % |
| Solde révisions 30 j négatif | 3 | 1 baisse, 2 hausses |
| Solde nul | 1 | 1 baisse ; pas de direction prédite |

Concordance brute signe/variation finale : **2/8 (25 %) pour EPS J−7**,
**2/9 (22,22 %) pour le solde des révisions 30 j**. Titres neutres exclus du
dénominateur, pas transformés en prédictions gagnantes. Les deux règles se
recouvrent : ne pas additionner leurs effectifs. Ce ne sont pas des probabilités
validées ni des scores de classification H20.

Pour repère, **7 des 10 titres ont baissé**, indépendamment du consensus ; une
comparaison future devra donc contrôler cette forte asymétrie. SPY a perdu
**1,99 %** de l'ouverture du 12 à la clôture du 16. L'ensemble des dix affiche
une variation moyenne de prix de −10,83 % sur ces bornes. Ce ne sont **pas** des
performances de portefeuille : pas de sizing, frais, dividendes, levier ou stops.

## Parcours observé, pas seulement clôture

Amplitude depuis l'ouverture du 12 ; hauts/bas daily observés jusqu'au 16,
sans supposer un ordre intraday des extrêmes ni une exécution à ces prix.

| Titre | Hausse maximale observée | Baisse maximale observée |
|---|---:|---:|
| CCOI | +4,74 % | −16,34 % |
| MXL | +0,06 % | −25,00 % |
| SSTK | +6,98 % | −6,98 % |
| COHR | 0,00 % | −24,31 % |
| CCB | +8,11 % | −1,32 % |
| QDEL | +9,00 % | −4,84 % |
| FICO | +16,56 % | −1,16 % |
| BAND | +1,11 % | −20,85 % |
| PENG | +6,30 % | −24,83 % |
| VICR | +0,55 % | −30,40 % |

Une petite excursion positive ne prouve pas un avantage exploitable : neuf des
dix ont connu un haut au-dessus de leur prix d'ouverture du 12. Aucune réussite
TP/SL n'est calculée avec ces seuls maxima. Les vingt séances depuis le 12 ne
seront écoulées qu'à la clôture du **6 novembre 2026** ; aucune validation H20
ou D1/D10 final n'est revendiquée avant cette maturité.

## Limite fournisseur observée

`revisions_down_7d` est NULL pour les dix périodes primaires. Le champ natif
`epsRevisionsDownLast7days` manque aussi dans les **payloads archivés** des dix
titres : ce n'est pas un zéro et aucun solde sur sept jours n'est inventé.
Les révisions à 30 jours sont présentes et servent à la deuxième lecture.
Parser et tables ne sont pas modifiés par ce diagnostic.

## Livrables et reproductibilité

- Rapport exact avec IDs, dates, valeurs de consensus, payloads sources, autres
  horizons et prix : `artifacts/research/us_top10_consensus_20261011/20261019-v2/report.json`.
- Protocole figé : même dossier, `protocol.json`. V1 conservé ; v2 ajoute les
  contrôles SPY/opérations sur titres sans changer sélection, règles ou résultats.
- Recherche : `scripts/research/us_oracle_top10_consensus_20261011.py`.
- Tests ciblés : **11 passent** (EPS négatif, référence zéro, NULL non imputé,
  bornes d'entrée, prix synthétiques/manquants/incohérents, provenance, neutralité).

Aucun appel fournisseur/GPT/DeepSeek, aucun entraînement, ordre ou écriture SQL.
Les requêtes du script sont gardées en SELECT uniquement. Les modèles, batchs,
prompts et protections opérationnels ne sont pas modifiés par cette étude.
