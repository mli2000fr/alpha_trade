# TODO — Ranker directionnel conditionné au TOP20 Oracle Extreme

## Prompt autonome d’audit, d’expérimentation et d’intégration éventuelle

> Ce document est un cahier de mission destiné à une IA travaillant de manière
> autonome sur le projet `alpha-trade`. Le code source, les schémas de données,
> les artefacts et les tests sont la vérité. Les documents historiques servent
> uniquement à comprendre le contexte et ne doivent jamais remplacer l’audit du
> comportement réellement exécuté.

---

## 1. Mission

Évaluer une nouvelle couche directionnelle située après Oracle Extreme :

```text
univers quotidien complet
        ↓
Oracle Extreme OOF : détection de magnitude
        ↓
TOP20 % Oracle, sans interprétation du sens
        ↓
ranker mutualisé entraîné uniquement dans ce pool
        ↓
haut du ranking = candidats LONG
bas du ranking  = candidats SHORT potentiels
```

Le ranker doit apprendre l’ordre relatif des rendements futurs au sein des
événements Oracle. Il ne doit pas apprendre les classes D1 à D10 d’Oracle et ne
doit pas considérer `proba_extreme` comme une probabilité LONG.

Question scientifique :

> Parmi les titres déjà identifiés comme susceptibles de produire un mouvement
> extrême, les informations disponibles à la date D permettent-elles de classer
> de façon stable ceux qui monteront le plus haut et ceux qui baisseront le plus ?

Ne modifier ni le serving, ni la cascade, ni le backtest de production avant un
GO explicite fondé sur des prédictions strictement OOS.

---

## 2. Pourquoi cette hypothèse est distincte des modèles existants

### 2.1 Oracle Extreme

Oracle répond à une question de magnitude :

```text
P(mouvement futur extrême)
```

Une forte `proba_extreme` peut annoncer une forte hausse ou une forte baisse.
Elle ne doit jamais être utilisée directement comme `P(LONG)`.

### 2.2 Global Ranking existant

Le Global Ranking actuel classe l’univers transversal complet, avec des groupes
par date et des cibles de rendement relatif transformées en rangs/labels. La
nouvelle expérience peut réutiliser ses briques techniques, mais son contrat est
différent :

- population d’apprentissage : uniquement les événements TOP20 Oracle OOF ;
- objectif : ordonner les rendements futurs à l’intérieur de ce pool ;
- Oracle reste un gate amont ;
- métriques calculées conditionnellement au pool Oracle ;
- aucune dépendance aux labels D1/D10 de l’Oracle.

Ne pas brancher simplement le Global Ranking existant après l’Oracle et appeler
cela une validation. Il faut réentraîner un ranker sur la population
conditionnelle réellement ciblée.

### 2.3 Modèles directionnels précédents

Cette hypothèse diffère également :

- du Per-Symbol, qui entraîne de petits modèles indépendants par titre ;
- de la classification mutualisée D1 contre D10 ;
- de la régression E1 du rendement moyen ;
- des deux têtes probabilistes E2 LONG/SHORT.

Le ranker optimise un ordre quotidien, pas une probabilité absolue ni une erreur
de rendement moyenne.

---

## 3. Avertissement essentiel : le bas du ranking n’est pas automatiquement SHORT

Un classement est relatif. Si tous les membres du TOP20 Oracle montent, le titre
classé dernier est seulement le moins haussier ; le vendre à découvert peut
rester perdant. Inversement, dans une journée très baissière, le premier du
ranking peut simplement être le moins mauvais.

Il faut donc publier séparément :

1. la qualité de l’ordre : IC, NDCG, spread haut-bas ;
2. le rendement absolu du haut du ranking ;
3. le rendement absolu du bas du ranking ;
4. le rendement signé d’une position LONG en haut ;
5. le rendement signé d’une position SHORT en bas ;
6. la fréquence réelle des événements `>= +3 %` et `<= -3 %` dans chaque queue.

Une branche peut recevoir un GO indépendamment de l’autre. Ne jamais forcer une
symétrie LONG/SHORT si seule la queue haute ou basse est exploitable.

---

## 4. Sources à auditer avant de coder

Lire au minimum :

- `modelFactory/oracle/` : labels, dataset, Walk-Forward, prédictions et gate ;
- `modelFactory/shared_directional.py` : expériences conditionnelles déjà faites ;
- `modelFactory/global_ranking.py` : groupes par date, rankers et métriques ;
- `modelFactory/cross_sectional.py` et `modelFactory/features.py` ;
- `modelFactory/data_loader.py` ;
- `modelFactory/predictor.py` ;
- consommateurs de `extreme_gate` dans `backtesting/` ;
- migrations et SQL des tables Oracle/Global Rank ;
- tests associés ;
- contrats des batches et caches OOF réellement utilisés.

Établir avant toute implémentation :

- comment le TOP20 est calculé et sur quelle population quotidienne ;
- si les égalités et valeurs manquantes sont déterministes ;
- comment une prédiction Oracle est prouvée OOF ;
- la date de disponibilité de chaque label futur ;
- la date exacte d’entrée du backtest ;
- les horizons réellement compatibles avec le lifecycle ;
- la liste exacte des features disponibles PIT ;
- les mécanismes de ranking réutilisables sans modifier le Global Ranking actuel.

---

## 5. Contrat scientifique initial à pré-enregistrer

### 5.1 Population

Utiliser uniquement les prédictions Oracle OOF du batch source explicitement
fourni. Pour chaque date :

1. partir de la population Oracle canonique complète ;
2. recalculer le percentile Oracle dans cette population ;
3. retenir le TOP20 % par `proba_extreme` ;
4. conserver l’identifiant du batch, la taille avant/après gate et le score
   Oracle pour les diagnostics ;
5. exclure le score Oracle des features du ranker principal.

Le TOP20 doit être calculé avant tout filtre directionnel aval. Filtrer les
symboles avant le percentile Oracle changerait le sens du gate.

### 5.2 Horizon primaire

Commencer par H3 uniquement. E2 a produit son seul signal directionnel répétable
sur H3 LONG ; multiplier immédiatement les horizons augmenterait le risque de
sélection opportuniste. H5/H10/H20 ne pourront être ouverts qu’après décision
formelle sur H3 ou comme campagne distincte pré-enregistrée.

### 5.3 Cible primaire

Le label de ranking primaire doit être l’ordre transversal du rendement futur
ajusté H3 observé dans le pool Oracle de la date. Étudier dans le code la
définition canonique du prix de départ, du prix final et des corporate actions.

Conserver pour évaluation, sans les fournir comme features :

- rendement brut H3 ;
- rendement excess-SPY H3 ;
- rendement résiduel secteur si sa couverture est suffisante ;
- indicateur hausse `>= +3 %` ;
- indicateur baisse `<= -3 %`.

Le rang/rendement brut correspond le mieux à la recherche du sens absolu. Une
cible excess-SPY mesure de la surperformance et ne suffit pas à autoriser un
short. Si elle est testée, elle doit constituer une variante séparée.

### 5.4 Modèle

Construire une requête par date (`group_id = date`) et comparer au minimum :

- CatBoostRanker avec une loss ranking déjà supportée par le projet ;
- une baseline simple de score/régression si nécessaire au contrôle technique ;
- tirage aléatoire apparié comme témoin nul.

Réutiliser l’infrastructure existante lorsque son contrat convient. Ne pas
dupliquer les transformations, le chargement PIT ou le calcul des folds.

### 5.5 Politique figée

Dans le TOP20 Oracle, sélectionner quotidiennement :

- les 20 % les mieux classés comme candidats LONG ;
- les 20 % les moins bien classés comme candidats SHORT potentiels.

Cela représente environ 4 % de l’univers Oracle initial par côté. Par exemple,
sur 400 symboles observables : environ 80 franchissent Oracle, puis environ 16
sont dans chaque queue du ranker. Définir et persister la règle exacte
d’arrondi, les minimums de groupe et le traitement des scores égaux.

Ne pas optimiser ce pourcentage après lecture du test. Les déciles et autres
fractions peuvent être publiés comme diagnostics, mais la politique primaire
reste figée à 20 % / 20 %.

---

## 6. Étanchéité temporelle obligatoire

Utiliser un Walk-Forward chronologique et purgé :

```text
train antérieur -> validation -> purge horizon -> test postérieur
```

Respecter les règles suivantes :

- le modèle Oracle qui crée le pool doit être OOF à chaque date ;
- le rendement H3 d’une ligne de train doit être entièrement connu avant la
  prochaine fenêtre ;
- les transformations, winsorisations, imputations et mappings sont ajustés sur
  train seulement ;
- aucune sélection de features ne peut consulter validation et test ensemble ;
- le test final de confirmation ne doit servir qu’une fois ;
- les groupes d’une même date ne doivent jamais être séparés entre train/test ;
- tout fallback in-sample ou modèle final non daté doit provoquer une erreur.

Ajouter des assertions de fuite et des tests synthétiques qui échouent si une
date, une cible future ou un score Oracle interdit entre dans les features.

---

## 7. Baselines obligatoires

Comparer la politique du ranker, à nombre de candidats identique et par date, à :

1. tirage aléatoire dans le TOP20 Oracle ;
2. pool TOP20 Oracle non trié ;
3. tri par amplitude Oracle seule, uniquement comme témoin de magnitude ;
4. Global Ranking existant appliqué au même pool, sans le présenter comme modèle
   conditionnel ;
5. signal mutualisé E2-B H3 LONG si ses prédictions OOS sont disponibles ;
6. règles triviales de momentum/relative strength pour vérifier que le ranker
   apporte davantage qu’un seul facteur connu.

Les comparaisons doivent utiliser exactement les mêmes dates, symboles
éligibles, tailles de queues et rendements.

---

## 8. Métriques à produire

### 8.1 Qualité du ranking

- Spearman IC quotidien moyen et médian ;
- distribution et intervalle de confiance de l’IC ;
- NDCG aux tailles cohérentes avec les queues ;
- spread de rendement haut moins bas ;
- monotonie des buckets de score ;
- turnover quotidien et stabilité du classement.

### 8.2 Branche LONG

- rendement moyen/médian H3 ;
- taux de rendement positif ;
- précision sur `rendement >= +3 %` ;
- lift contre le pool Oracle et le témoin apparié ;
- drawdown d’une simulation simple, sans modifier les exits de production.

### 8.3 Branche SHORT

- rendement brut moyen/médian des titres sélectionnés ;
- rendement signé du short ;
- taux de rendement négatif ;
- précision sur `rendement <= -3 %` ;
- lift contre le pool Oracle et le témoin apparié.

### 8.4 Stabilité

Décomposer toutes les métriques :

- par fold ;
- par semestre ;
- par régime PIT ;
- par secteur ;
- par symbole, avec support ;
- par tranche d’amplitude Oracle ;
- avec et sans valeurs extrêmes de rendement dans les métriques de robustesse.

Les rendements économiques principaux restent non tronqués. Une version
winsorisée peut être publiée en contrôle, jamais en remplacement silencieux.

---

## 9. Gates et décision

Pré-enregistrer des gates avant le run complet. Au minimum :

- IC moyen positif avec majorité nette de folds positifs ;
- spread haut-bas positif et stable ;
- lift économique contre le tirage apparié ;
- absence de dépendance à un seul semestre, secteur ou symbole ;
- couverture quotidienne suffisante ;
- performance confirmée sur une période strictement intacte.

Décider séparément :

```text
GO_LONG
GO_SHORT
GO_BOTH
NO_GO
```

Un bon spread ne suffit pas à `GO_SHORT` si le bas du ranking conserve un
rendement absolu positif. De même, NDCG/IC sans avantage économique ne permet
pas une intégration portefeuille.

Ne pas ajuster successivement loss, profondeur, horizons, fractions et features
sur la confirmation. Toute nouvelle variante après lecture du test devient une
nouvelle campagne avec une nouvelle période intacte.

---

## 10. Artefacts et livrables

Persister dans un répertoire de recherche séparé :

- contrat JSON complet ;
- batch Oracle source et empreinte ;
- profil ordonné des features ;
- folds et dates de purge ;
- modèles par fold ;
- prédictions OOS ligne à ligne ;
- rang quotidien et queue attribuée ;
- rendements/labels réalisés ;
- métriques globales, folds, semestres, secteurs et symboles ;
- baselines appariées ;
- rapport Markdown de décision ;
- commande exacte de reproduction.

Le contrat doit rester `research_only=true` et `serving_ready=false` jusqu’au GO.

---

## 11. Intégration éventuelle après GO seulement

Après validation, proposer sans l’activer par défaut :

```text
Oracle TOP20
    -> reconstruction exacte des features du ranker
    -> score transversal sur tous les survivants du jour
    -> rang conditionnel dans le pool
    -> queue LONG et/ou SHORT autorisée selon le verdict
    -> filtres risque/exécution/lifecycle existants
```

L’intégration doit :

- posséder un mode de cascade explicite, sans changer les modes historiques ;
- refuser une couverture ou un contrat de features incomplet ;
- ne jamais synthétiser une direction depuis Oracle en fallback ;
- persister score brut, rang, taille du pool, côté, batch et modèle ;
- exposer les diagnostics dans l’IHM ;
- être couverte par tests unitaires, intégration, PIT et non-régression ;
- être documentée dans les documents ML/cascade concernés.

---

## 12. Condition de fin de mission

La mission n’est pas terminée lorsqu’un modèle s’entraîne. Elle se termine avec :

1. un audit du contrat courant ;
2. un dataset conditionnel PIT reproductible ;
3. des prédictions Walk-Forward strictement OOS ;
4. les comparaisons appariées ;
5. un verdict LONG et SHORT séparé ;
6. une confirmation intacte ;
7. une intégration désactivée par défaut uniquement en cas de GO ;
8. les tests et la documentation correspondants.

