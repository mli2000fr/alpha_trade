# US — Audit PIT et lineage de l'expérience ratio D10/D1

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

Date : 4 octobre 2026. Audit des trois étapes autorisées : scores Oracle,
disponibilité macro/sentiment, puis correction et rejeu identique **si une
correction documentée est possible**.

## 1. Conclusion

**Aucune utilisation d'un champion Oracle daté après la prédiction n'a été
observée.** Le routage correspond partout au champion le plus récent dont
`t_start <= prediction_date`. Mais cela ne certifie pas toutes les features
historiques, les échantillons d'apprentissage et les versions originales.

Les données macro et sentiment ont été largement reconstruites après les
dates historiques. Une reconstruction n'est pas une fuite par elle-même,
mais les tables et lecteurs ne conservent pas les preuves suffisantes pour
certifier la disponibilité et les versions à chaque décision historique.

**Pas de correction de données justifiable avec les preuves inspectées.**
Le troisième point n'entraîne donc pas un rejeu artificiel sur les mêmes
entrées. Résultats précédents conservés avec réserves renforcées, pas de règle
promue en production ni de comparaison économique lancée.

## 2. Étape 1 — Origine et causalité Oracle

Batch audité : `model-factory-20261003082853-e98332`, H20.

### Vérifications effectuées

- 12 champions présents et hashés, de `t_start=2018-07-05` à `2024-01-08`.
- 3 618 577 lignes de prédiction persistées, 2 071 dates/groupes date-fold.
- Zéro ligne avec `fold_start` absent du manifeste.
- Zéro ligne avec `fold_start > prediction_date`.
- Zéro ligne ne correspondant pas au dernier champion autorisé par sa date.
- Log archivé `artifacts/rapport_ml/model-factory-20261003082853-e98332.log` :
  entraînement Oracle démarré le 3 octobre 2026, puis persistance de
  **2 616 012 prédictions annoncées OOS** et 12 champions.

Le total actuel de prédictions est supérieur au total OOS de l'entraînement.
L'écart est **1 002 565 lignes nettes**, compatible avec une extension de
prédiction, mais ce n'est pas une preuve de l'historique exact des écritures.
La table peut avoir été réécrite ; le journal seul ne permet pas de classer
toutes les lignes actuelles en OOF original, extension ou rejeu.

### Contrats constatés dans les sources

`modelFactory/oracle/walk_forward.py` purge les lignes d'apprentissage avec
label non disponible avant validation, et celles de validation avant test.
Le test ne pilote pas l'early stopping. Cela constitue un contrôle de code
favorable, pas une preuve complète des données exactes du run archivé.

Le manifeste des champions contient `t_start`, fichier et colonnes de features,
mais pas les bornes effectives train/validation, maxima de maturité des labels,
hash du dataset ou identifiants de versions de données.

`modelFactory/oracle/predictions_store.py` effectue un upsert par
date/symbole/batch. Il ne conserve ni historique de versions, ni run de
prédiction, ni hash du champion par ligne. `created_at` ne prouve donc pas
l'origine des valeurs actuelles après mise à jour.

Le prédicteur historique sélectionne le dernier `t_start <= date`. Il contient
aussi un fallback au premier champion si aucun ne convient. **Ce fallback
non causal n'est pas observé dans les lignes auditées** ; ce n'est pas la cause
des résultats actuels et aucune modification de production n'a été engagée.

Le dernier champion reste daté du 8 janvier 2024, y compris pour les dates
plus récentes. Cela peut contribuer à un vieillissement, mais aucun bénéfice
d'un nouveau modèle n'est démontré par cet audit et aucun entraînement n'est
lancé.

### Statut

**Routage temporel conforme observé ; certification OOS/PIT intégrale
incomplète.** Le lineage des features, versions d'OHLC/ajustements et éventuels
scores auxiliaires n'est pas certifié par le seul nom du champion.

## 3. Étape 2 — Disponibilité macro et sentiment

### Macro

1 695 journées inspectées, de 2020 à septembre 2026. Pour toutes, le premier
`created_at` actuel est après J+1. Les créations s'étendent du 7 juillet 2026
au 3 octobre 2026 : c'est une matérialisation historique tardive.

`stock_macro_indicators_daily` contient dates/valeurs et timestamps techniques,
mais pas les vintages, heures de publication par indicateur ou versions
anciennes nécessaires à une certification stricte.

`database/macro_indicators.py` filtre sur `trade_date <= date` (ou strictement
avant si demandé), puis enrichit la lecture par :

- `available_at` synthétisé à **21 h UTC** à partir de la date ;
- `source_revision=None` ;
- `ingested_at` égal à l'heure de lecture.

Ces champs ne sont pas des timestamps historiques prouvés. Une heure UTC fixe
ne décrit pas les publications propres à chaque série, les demi-séances et
les changements d'heure. **Notre expérience utilise les colonnes brutes
décalées d'une séance, pas ce champ synthétique**, mais le décalage ne certifie
pas l'absence de révision ultérieure.

### Sentiment

Les 1 695 journées macro attribuent le score à
`ticker_daily_sentiment_features`. Aucun fallback secteur n'apparaît dans ces
sources enregistrées.

Pour 1 694 des 1 695 journées de features ticker, même la première création
est après J+1. Les premiers timestamps de matérialisation par date vont du
20 mai au 3 octobre 2026. Cela ne prouve pas que des nouvelles futures ont été
utilisées, mais confirme que ce n'est pas un historique de snapshots collectés
et gelés au fil de ces années.

`service/market/sentiment_provider.py` calcule une moyenne pondérée par nombre
de news, sur une fenêtre de jours calendaires et un score net dans **[-1,1]**.
Il filtre les dates métier de la fenêtre, pas les timestamps de publication,
d'observation, de classification ou les versions du modèle NLP. Le score
de marché n'est pas le maximum `positive_score` d'un article ni une probabilité
de hausse. Une hypothèse comme `VIX × (1-sentiment)` n'a pas de justification
de probabilité automatique sur cette échelle.

La présence de `latest_event_timestamp_ny` dans les features ticker apporte
un indice d'événement, mais pas la liste des articles, leur disponibilité,
leurs révisions et le lineage complet de chaque agrégat historique.

### Statut

**Disponibilité de séance antérieure simulée ; PIT historique non certifié.**
Ne pas remplacer ces valeurs par zéro, ni utiliser `created_at` tardif comme
date de publication. À l'inverse, ne pas qualifier de fuite démontrée chaque
backfill : il manque les preuves pour le décider.

## 4. Étape 3 — Correction et reprise du même protocole

On a trouvé des **lacunes de traçabilité** et un contrat de timestamp macro
synthétique, pas une valeur erronée avec une version correcte attestée.
Il serait incorrect d'inventer des timestamps, de retrancher un nombre
arbitraire de jours ou de reconstruire des vintages inconnus pour obtenir
un meilleur résultat.

**Aucun rejeu modifié n'est effectué.** Le protocole et les résultats de
[validation chronologique](us_d10_d1_ratio_validation_chronologique.md) sont
conservés. Son verdict d'absence d'avantage stable reste exploratoire,
sans affirmer que ces données prouvent une absence absolue de signal macro.

Pour débloquer une correction certifiée, il faut au minimum :

1. Les bornes effectives et hashes d'apprentissage/validation des champions,
   et l'association run/modèle/version aux prédictions historiques.
2. Une source archivée donnant valeurs et publication/vintage par série macro,
   ou un contrat de disponibilité documenté et vérifié série par série.
3. Pour sentiment : corpus d'articles avec timestamps historiques, règle de
   cutoff, version NLP et méthode d'agrégation reproduisible.

Si ces preuves deviennent disponibles : créer un **nouveau dossier**, conserver
les entrées initiales, corriger uniquement ce qui est attesté et refaire le
même modèle Ridge alpha=10, mêmes variables, purge, années et références.
Ne pas changer les seuils après observation. Toute évolution de persistance
ou migration de production doit faire l'objet d'un GO séparé.

## 5. Artefacts et périmètre

Audit en lecture seule : `scripts/research/us_ratio_lineage_audit.py`.
Dossier : `artifacts/research/us_ratio_regime_validation/lineage-20261004-v1`.

- `prediction_dates.parquet`, `prediction_lineage_checks.parquet` : routage.
- `macro_dates.parquet`, `sentiment_dates.parquet` : matérialisation et sources.
- `schemas.parquet` : colonnes disponibles, dont tables news inspectées au
  niveau schéma seulement ; aucune lecture du contenu complet des articles.
- `report.json` : compteurs, limites, hashes des modèles et sources de code.

L'audit n'est pas une reconstitution exhaustive article par article, ni une
certification des publications des fournisseurs. Aucun SQL d'écriture,
entraînement, suppression, activation, nouvelle installation de batch ou
correction du code de production n'a été réalisé.
