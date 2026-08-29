# Page Screening — scores, recommandations et explicabilité

## Ce que représente un score

La page consulte les sorties de screening persistées et les artefacts associés.
Un score ordonne ou caractérise un candidat selon le contrat du screener ; il
n’est ni une probabilité universelle de gain, ni une décision de risque, ni un
ordre. Sa signification dépend de la date, de la version des composants, de la
population comparée et des poids/calibrations actifs.

## 1. Qualité amont et contexte pipeline

Toujours commencer par le bloc de qualité. Il relie les résultats au pipeline
qui les a produits et signale les conditions susceptibles de rendre la lecture
incomplète. Vérifier date, fraîcheur, volume, présence des composants attendus
et cohérence de l’univers. Un tableau de scores non vide peut néanmoins être
partiel.

## 2. Deux vues distinctes

L’onglet Recommandations exploite les artefacts synthétiques construits par le
screener, notamment par objectif. L’onglet CSV explore les fichiers produits et
permet une inspection plus brute. La prévisualisation CSV peut être limitée ou
typée différemment du stockage métier : utiliser l’inventaire et les détails de
lecture avant de conclure qu’une colonne ou une ligne est absente.

Les recommandations ne doivent pas être reconstituées en triant arbitrairement
une preview CSV : les règles de sélection et les métadonnées de l’artefact font
partie du résultat.

## 3. Filtres opérateur

Les filtres de symbole, secteur, statut sélectionné, score minimal et sentiment
modifient uniquement la vue sauf indication contraire. Ils ne recalculent pas
le screener. Pour une analyse reproductible, noter les filtres et conserver la
population avant/après filtrage.

Pièges fréquents :

- interpréter un percentile sans connaître l’univers du jour ;
- comparer deux dates dont les calibrations ou colonnes diffèrent ;
- confondre `selected` avec l’acceptation par le risque ;
- filtrer sur le sentiment puis attribuer la performance au score global ;
- analyser uniquement les survivants d’un filtre et ignorer les exclus.

## 4. Résultats filtrés

Lire ensemble identité, secteur, composants, score final et indicateurs de
sélection. Pour comparer des candidats, privilégier des lignes produites au même
as-of et sous le même contrat. Un export doit conserver ces métadonnées ; un
simple fichier de tickers ne permet pas l’audit.

## 5. Explainability candidat

Le bloc d’explicabilité détaille pourquoi un candidat apparaît avec son score.
Il sert à vérifier la contribution des composantes et à repérer une donnée
manquante, plafonnée ou incohérente. Il ne fournit pas une explication causale
de la performance future.

Avant de transmettre un candidat au workflow aval, répondre à quatre questions :

1. les données amont et la date sont-elles cohérentes ?
2. le score est-il élevé pour les bonnes raisons, sans composante manquante ?
3. le candidat est-il couvert par le modèle attendu ?
4. les règles de risque et d’exécution peuvent-elles encore le réduire ou le
   rejeter ?

## Aller plus loin

- [Architecture du scoring](../13_screener_selector_sentiment.md)
- [Sélection et scoring](../signals/selection_et_scoring.md)
- [Global ranking](../07_ml_global_ranking.md)
- [Expériences historiques ranking/per-sector](../experiences/global_ranking_et_per_sector.md)
