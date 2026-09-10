# TODO 1 — Combinaison Oracle Extreme × modèles Per-Symbol fiables

## Prompt autonome de recherche, validation et intégration éventuelle

> Ce document est un cahier de mission destiné à une IA travaillant de manière autonome sur le projet `alpha-trade`.
> Elle doit commencer par vérifier le code source et les données réellement disponibles. Les documents historiques sont des sources de contexte, jamais la vérité finale.

---

## 1. Mission

Étudier puis, uniquement si les résultats hors échantillon le justifient, mettre en place une combinaison entre :

1. **Oracle Extreme**, qui estime la probabilité qu'un symbole réalise un mouvement futur extrême sans en connaître le sens ;
2. **les modèles Per-Symbol**, qui produisent une information directionnelle propre à chaque symbole ;
3. **un mécanisme causal de sélection des symboles fiables**, destiné à n'utiliser le signal directionnel que sur les symboles pour lesquels il se montre réellement prédictible dans le futur.

Hypothèse centrale :

```text
Oracle Extreme global
    → détecte les candidats susceptibles de beaucoup bouger

Modèle Per-Symbol spécialisé
    → estime le sens probable pour un symbole donné

Gate de fiabilité Per-Symbol
    → autorise cette estimation seulement lorsque sa qualité passée OOS
      est suffisante, stable et disponible avant la décision
```

La question scientifique n'est pas :

> Quels symboles ont obtenu le meilleur F1 sur toute l'histoire ?

La vraie question est :

> Les symboles identifiés comme fiables avec les seules informations disponibles avant une période continuent-ils à mieux distinguer les mouvements haussiers et baissiers parmi les candidats futurs d'Oracle Extreme ?

---

## 2. Contexte et motivation

### 2.1 Limite d'Oracle Extreme

Oracle Extreme prédit l'amplitude, pas la direction :

```text
proba_extreme élevée
    = probabilité élevée d'appartenir à une queue future
    = D1 ou D10
    ≠ probabilité de hausse
```

Selon le contrat courant, vérifier dans le code la définition exacte des labels, des horizons et des percentiles. Les sources principales se trouvent notamment dans :

- `modelFactory/oracle/build_labels.py` ;
- `modelFactory/oracle/` ;
- `modelFactory/predictor.py` ;
- `config.yaml`.

Ne jamais interpréter `proba_extreme` comme `P(LONG)`.

### 2.2 Limite des modèles directionnels globaux

Les travaux précédents indiquent que `GlobalDirection` ne sépare pas D1 et D10 de manière suffisamment stable : performance proche du hasard, gradients instables et absence de gain temporel robuste.

Cette campagne ne doit pas tenter de sauver ou de retuner `GlobalDirection`.

### 2.3 Observation Per-Symbol à vérifier

Sur environ 2 000 symboles entraînés, la moyenne observée de `f1_macro` serait proche de 0,33 et environ 3 % des symboles auraient un `f1_macro > 0,40`, soit approximativement 60 à 70 symboles.

Cette observation est une hypothèse de départ, pas un résultat validé. Elle peut refléter :

- une véritable prédictibilité propre à certains titres ;
- un échantillon trop petit ;
- un régime temporairement favorable ;
- un biais de sélection parmi 2 000 essais ;
- un mélange de scores validation, walk-forward ou entraînement ;
- une fuite temporelle ou une incohérence de label ;
- la chance dans la queue supérieure de la distribution.

### 2.4 Antécédents à respecter

La campagne historique Per-Symbol Directional v2 a conclu à un **NO-GO global** : aucune famille directionnelle testée n'a généralisé de manière persistante sur l'ensemble étudié.

Ce NO-GO ne prouve pas que chaque symbole est imprédictible. La présente hypothèse est différente :

```text
Ancienne question : le Per-Symbol apporte-t-il un signal global stable ?

Nouvelle question : existe-t-il une petite sous-population identifiable à l'avance
                    dont le signal Per-Symbol reste utile dans le pool Oracle futur ?
```

Ne pas retuner les anciennes familles rejetées. Tester la sélection de fiabilité comme une nouvelle hypothèse, avec une discipline anti-surapprentissage stricte.

---

## 3. État actuel du code à auditer avant toute modification

La combinaison est déjà partiellement câblée. L'IA doit d'abord comprendre et tester l'existant.

Dans `modelFactory/predictor.py`, la branche `extreme_gate` accepte actuellement plusieurs rôles du Per-Symbol :

```text
filter
    veto par long_prob et score Oracle-rank × long_prob

no_filter
    pas de veto, mais classement Oracle-rank × long_prob

bypass
    Oracle seul, Per-Symbol ignoré
```

La configuration `extreme_gate` contient également une pénalité directionnelle anti-D1 fondée sur `long_prob`.

Avant de coder, établir précisément :

- comment `long_prob`, `short_prob` et `flat_prob` sont produits ;
- s'ils sont issus du champion réellement OOS ou d'un modèle final réentraîné ;
- quelle cible ils représentent exactement ;
- si leur date de disponibilité est compatible avec la date du trade ;
- comment `min_prob` est résolu ;
- quel score est réellement utilisé après la cascade ;
- si un autre composant reclasse ensuite les candidats avec `proba_long` ;
- si la branche est réellement LONG-only ;
- comment les candidats sans modèle Per-Symbol sont traités ;
- comment les probabilités sont calibrées ;
- si la logique du backtest et celle de la production sont identiques ;
- si les anciennes anomalies E16/E17, notamment liées au lifecycle/ATR et aux shorts parasites, sont bien corrigées dans le code courant.

Ne pas créer un second mécanisme de combinaison si la cascade existante peut être étendue proprement.

---

## 4. Règles absolues de la campagne

### 4.1 Le code est la vérité

Lire le code source, les migrations, la configuration, les schémas DB et les tests avant d'utiliser les documents historiques. Toute divergence doit être tranchée en faveur du code réellement exécuté, puis documentée.

### 4.2 Séparation stricte recherche / intégration

Procéder dans cet ordre :

1. audit ;
2. construction d'un dataset analytique reproductible ;
3. diagnostic descriptif ;
4. expérience walk-forward imbriquée ;
5. backtest portefeuille PROD ;
6. décision GO/NO-GO ;
7. intégration seulement après GO.

Ne modifier aucun comportement de production pendant les phases 1 à 5. Les nouveaux chemins doivent rester désactivés par défaut.

### 4.3 Causalité/PIT

À une date de trade `T`, toute décision doit utiliser exclusivement des informations disponibles au plus tard à `T` selon le contrat d'entrée.

Sont interdits :

- F1 calculé avec des prédictions postérieures à `T` ;
- sélection d'un symbole à partir de sa performance sur la période où il est tradé ;
- choix du seuil 0,40 sur la période finale ;
- sélection du meilleur modèle après observation du test final ;
- mélange de prédictions in-sample et OOS ;
- utilisation d'un label dont la fenêtre future chevauche incorrectement le train/test ;
- révision a posteriori de la liste des symboles autorisés.

### 4.4 Reproductibilité

Chaque run doit persister :

- IDs exacts des batches Oracle et Per-Symbol ;
- empreintes de configuration et de features ;
- période et folds ;
- seed ;
- univers initial et univers retenu ;
- liste des symboles autorisés par période ;
- métriques de sélection connues à cette période ;
- prédictions OOS utilisées ;
- contrat d'exécution ;
- paramètres de portefeuille ;
- motif d'exclusion de chaque symbole.

### 4.5 Pas d'optimisation opportuniste

Pré-enregistrer les variantes et les gates avant d'observer les résultats finaux. Si une variante échoue, ne pas ajuster successivement seuils, périodes et populations pour la faire passer.

---

## 5. Définir précisément le problème de direction

Avant toute mesure, produire une fiche de contrat indiquant :

- horizon de prédiction du Per-Symbol ;
- cible exacte : LONG/FLAT/SHORT, seuils de rendement et éventuelle normalisation SPY/volatilité ;
- horizon et définition D1/D10 d'Oracle ;
- compatibilité entre l'horizon Per-Symbol et l'horizon Oracle ;
- date du signal, date de disponibilité, date et prix d'entrée ;
- traitement des corporate actions ;
- univers quotidien Oracle ;
- mode de ranking et taille du pool ;
- définition exacte d'un bon signal LONG et d'un bon signal SHORT.

Si les horizons ou les cibles ne sont pas compatibles, ne pas multiplier naïvement les probabilités. Tester d'abord l'information directionnelle comme un filtre/ranking empirique.

---

## 6. Phase A — Audit des métriques Per-Symbol

### A1. Identifier la source du F1

Pour chaque symbole, déterminer si le `f1_macro` observé est :

- train ;
- validation ;
- test ;
- moyenne walk-forward ;
- métrique du champion ;
- métrique d'une architecture particulière ;
- calculé sur trois classes ou deux classes ;
- pondéré ou non ;
- basé sur des seuils propres au symbole.

Vérifier notamment `modelFactory/champion_selection.py`, `modelFactory/batch_diagnostics.py`, l'orchestrateur, les tables de métriques et les artefacts de modèles.

### A2. Recalcul indépendant

Ne pas faire confiance aveuglément à la métrique persistée. À partir des prédictions OOS :

- recalculer `f1_macro` ;
- recalculer le support par classe ;
- produire la matrice de confusion ;
- balanced accuracy ;
- précision/rappel/F1 LONG ;
- précision/rappel/F1 SHORT ;
- précision/rappel/F1 FLAT ;
- MCC si pertinent ;
- log loss et Brier si les probabilités sont disponibles ;
- calibration par classe.

Comparer le calcul indépendant à la DB/aux artefacts et expliquer tout écart.

### A3. Baselines correctes

Comparer chaque symbole à :

- prédiction de la classe majoritaire ;
- prédiction selon les fréquences historiques causales ;
- éventuelle baseline momentum simple pré-enregistrée ;
- distribution aléatoire respectant les fréquences de classes.

Un F1 de 0,40 n'est intéressant que relativement à la cible et à ces baselines.

### A4. Incertitude liée à l'échantillon

Pour chaque symbole, reporter :

- nombre total d'observations OOS ;
- nombre par classe ;
- nombre de folds valides ;
- intervalle de confiance bootstrap temporel ou par blocs ;
- moyenne, médiane, minimum et écart-type du F1 par fold ;
- probabilité empirique de battre la baseline.

Interdire une sélection fondée sur un F1 élevé avec un support insuffisant.

---

## 7. Phase B — Vérifier que la qualité est pertinente dans le pool Oracle

La métrique décisive n'est pas nécessairement le F1 du symbole sur toutes les dates.

Construire au minimum :

```text
quality_all(symbol)
    qualité OOS du Per-Symbol sur toutes les dates passées

quality_oracle(symbol)
    qualité OOS du Per-Symbol lorsque le symbole appartenait au pool Oracle

quality_extremes(symbol)
    capacité à distinguer les futurs D1 et D10
```

Pour le sous-ensemble Oracle, mesurer séparément :

- `P(D10 | prédiction LONG)` ;
- `P(D1 | prédiction LONG)` ;
- ratio D10/D1 ;
- `P(D1 | prédiction SHORT)` ;
- `P(D10 | prédiction SHORT)` ;
- rendement futur moyen/médian ;
- BAD5/GOOD5 ou D1–D3/D8–D10 si utile ;
- couverture ;
- calibration de `long_prob` et `short_prob` ;
- performance par régime et semestre, sans sélectionner les régimes après coup.

Si le nombre de cas Oracle par symbole est trop faible, utiliser une estimation hiérarchique/rétrécie plutôt qu'un seuil brutal.

---

## 8. Phase C — Construire un score de fiabilité causal

### C1. Ne pas sélectionner sur le futur

Pour chaque période de test `T`, calculer la qualité uniquement à partir des folds OOS terminés avant `T`.

Exemple semestriel :

```text
Historique et prédictions OOS disponibles jusqu'à 2024H2
    → calcul de qualité
    → liste gelée pour 2025H1

Historique disponible jusqu'à 2025H1
    → recalcul
    → liste gelée pour 2025H2
```

Si les labels H20 ne sont disponibles que 20 séances après le signal, appliquer le délai réel avant de mettre à jour la qualité.

### C2. Rétrécissement vers la moyenne

Tester une mesure simple pénalisant les petits échantillons :

```text
w_symbol = n_eff / (n_eff + K)

f1_shrunk =
    w_symbol * f1_symbol
    + (1 - w_symbol) * f1_population
```

`K` doit être pré-enregistré ou choisi dans les folds internes, jamais sur le test final.

Construire ensuite éventuellement :

```text
reliability =
    f1_shrunk
    - pénalité_instabilité
    - pénalité_faible_support
    - pénalité_mauvaise_calibration
```

Rester simple. Ne pas créer un méta-modèle complexe avant d'avoir démontré la persistance brute.

### C3. Variantes pré-enregistrées

Comparer au minimum :

```text
U0 — Tous les symboles Per-Symbol disponibles
U1 — F1 OOS passé > 0,40
U2 — Top 3 % par F1 OOS passé
U3 — Top 3 % par F1 rétréci
U4 — Top 3 % par fiabilité rétrécie + stabilité
U5 — Sélection aléatoire de même taille (placebo multi-seeds)
U6 — Oracle pur, Per-Symbol bypass
```

Le seuil 0,40 et le top 3 % sont des hypothèses distinctes. Ne pas choisir rétroactivement celui qui produit le meilleur PnL.

### C4. Persistance de la liste

Mesurer :

- Spearman des qualités entre périodes consécutives ;
- taux de symboles restant dans le top 3 % ;
- turnover de la liste ;
- durée médiane d'éligibilité ;
- qualité future des entrants, persistants et sortants ;
- concentration sectorielle ;
- dépendance à la liquidité et à l'ancienneté des données.

Si le groupe change presque intégralement à chaque période et ne conserve pas son avantage, conclure à une queue chanceuse.

---

## 9. Phase D — Expérience walk-forward imbriquée

Mettre en œuvre une validation imbriquée :

```text
Fenêtre d'entraînement modèle
    ↓
Fold OOS interne servant à mesurer la fiabilité par symbole
    ↓
Sélection et gel de l'univers fiable
    ↓
Période OOS externe totalement intacte
    ↓
Évaluation Oracle × Per-Symbol
```

La période externe ne doit servir ni à :

- choisir le seuil de fiabilité ;
- choisir le modèle champion ;
- calibrer les probabilités ;
- choisir le nombre de symboles ;
- décider LONG/SHORT ;
- sélectionner le régime.

Appliquer purge/embargo compatibles avec les horizons futurs et éviter que des fenêtres de labels se chevauchent entre sélection et évaluation externe.

Produire les résultats :

- par fold externe ;
- par semestre ;
- consolidés ;
- avec dispersion, pas seulement moyenne ;
- avec liste exacte des symboles de chaque fold.

---

## 10. Phase E — Tester la combinaison

### E1. Baselines obligatoires

Comparer sur le même pool, les mêmes dates et le même contrat :

```text
A — Oracle pur (`bypass`)
B — Oracle + Per-Symbol actuel (`filter`)
C — Oracle + Per-Symbol sans veto (`no_filter`)
D — Oracle + Per-Symbol limité aux symboles fiables
E — Oracle + Per-Symbol fiable avec abstention directionnelle
F — Oracle + sélection aléatoire de même taille
```

Si pertinent, ajouter une baseline utilisant tous les symboles mais avec un rang aléatoire intra-pool pour isoler l'effet du classement directionnel.

### E2. Règles de combinaison à tester sans explosion combinatoire

Commencer avec des règles simples :

```text
Gate Oracle : top pool_pct intra-date par proba_extreme

Gate symbole : reliability_symbol >= seuil causal

LONG : long_prob >= seuil haut
SHORT : short_prob >= seuil haut, uniquement si les shorts sont autorisés
Sinon : NO-TRADE
```

Comparer deux façons de classer les candidats :

```text
ranking_1 = long_prob
ranking_2 = oracle_percentile * long_prob
```

Ne pas supposer que le produit est une probabilité jointe : Oracle et Per-Symbol ne sont pas nécessairement indépendants et peuvent être mal calibrés. Le produit peut être testé comme score de ranking uniquement.

Une interprétation probabiliste :

```text
p_D10 ≈ p_extreme × p_direction
p_D1  ≈ p_extreme × (1 - p_direction)
```

n'est autorisée que si `p_direction` correspond réellement à `P(D10 | extrême)` et si la calibration conditionnelle est démontrée.

### E3. Zone d'abstention

Ne jamais forcer un sens pour chaque candidat Oracle. Évaluer une zone `NO-TRADE` définie dans les folds internes.

Mesurer la courbe couverture/qualité :

- couverture quotidienne ;
- précision D10/D1 ;
- rendement ;
- nombre de jours sans candidat ;
- capacité à remplir les slots ;
- concentration induite.

### E4. Long et short séparément

La validation LONG ne valide pas automatiquement le SHORT.

Évaluer séparément :

- Oracle + Per-Symbol pour éliminer les mauvais LONG ;
- Oracle + Per-Symbol pour prioriser les bons LONG ;
- éventuelle branche SHORT, avec son propre gate et son propre GO/NO-GO.

Le premier objectif peut être uniquement anti-D1 : réduire les D1 parmi les LONG sans nécessairement ouvrir de shorts.

---

## 11. Phase F — Tests statistiques et placebos

### F1. Sélection multiple

Avec environ 2 000 modèles, quantifier la part attendue de symboles dépassant 0,40 par hasard.

Utiliser notamment :

- permutation des labels dans le respect de la structure temporelle ;
- bootstrap par blocs ;
- distribution du maximum/top 3 % sous le null ;
- correction ou contrôle du false discovery rate si des tests par symbole sont utilisés.

### F2. Placebo univers aléatoire

Pour chaque fold externe :

1. prendre le même nombre de symboles que la sélection fiable ;
2. tirer plusieurs centaines de listes aléatoires comparables ;
3. conserver si possible les distributions secteur/liquidité ;
4. exécuter la même combinaison et le même portefeuille ;
5. situer la variante réelle dans la distribution placebo.

### F3. Placebo métrique

Comparer le F1 à des critères arbitraires ou inversés :

- symboles médians ;
- bottom 3 % ;
- qualité passée permutée ;
- liste retardée ou ancienne.

Le top fiable doit montrer une hiérarchie cohérente, pas seulement battre une seule baseline.

---

## 12. Phase G — Évaluation économique PROD

Une bonne classification ne suffit pas. Exécuter les variantes retenues dans le moteur de backtest canonique avec :

- lifecycle PROD exact ;
- entry timing exact ;
- coûts et slippage ;
- gap filter ;
- contraintes de liquidité ;
- sizing et budget de risque ;
- `max_positions` ;
- contraintes long/short ;
- résolution intrabar canonique ;
- mêmes seeds/périodes pour les comparaisons.

Reporter :

- PnL et return ;
- profit factor ;
- Sharpe/Sortino si pertinents ;
- max drawdown ;
- nombre de trades ;
- win rate ;
- PnL par exit reason ;
- exposition et turnover ;
- D1/D10 et D10/D1 ;
- MFE/MAE ;
- couverture et candidats/jour ;
- jours sans trade ;
- concentration top 1/5/10 symboles ;
- contribution par secteur ;
- résultat par semestre et régime ;
- sensibilité multi-seeds.

Comparer à Oracle pur, au `filter` existant et aux univers aléatoires de même taille.

Attention : 60 à 70 symboles peuvent être suffisants en nombre absolu mais insuffisants en breadth quotidienne dans le top Oracle. Mesurer l'intersection réelle :

```text
univers_fiable ∩ pool_Oracle_du_jour
```

---

## 13. Gates GO/NO-GO pré-enregistrés

### 13.1 GO prédictif minimal

La piste ne peut continuer vers le portefeuille que si, sur les folds externes :

- la sélection passée reste meilleure que les baselines futures ;
- l'avantage existe sur la majorité des folds ;
- les LONG prédits contiennent moins de D1 et/ou plus de D10 ;
- le ratio D10/D1 s'améliore ;
- la performance n'est pas portée par un seul semestre ;
- le top fiable bat les sélections aléatoires comparables ;
- le support et la couverture restent exploitables.

### 13.2 GO économique minimal

L'intégration n'est autorisée que si :

- le backtest PROD améliore une baseline pertinente ;
- l'amélioration survit aux coûts ;
- le drawdown ne se détériore pas de manière disproportionnée ;
- la stabilité multi-périodes est acceptable ;
- la concentration reste maîtrisée ;
- le résultat n'est pas expliqué par quelques symboles ;
- les variantes aléatoires ne reproduisent pas facilement la performance.

### 13.3 NO-GO immédiat

Conclure NO-GO sans tentative de sauvetage si :

- le top 3 % passé revient vers la moyenne dans le fold suivant ;
- le classement des symboles n'est pas persistant ;
- la sélection fiable ne bat pas les univers aléatoires ;
- le F1 n'est pas relié à D1/D10 ou à la performance économique dans le pool Oracle ;
- la couverture devient trop faible ;
- les résultats changent de signe selon les périodes ;
- une fuite PIT ou une insuffisance de données empêche une conclusion fiable.

Un NO-GO est un résultat valide. Ne pas modifier la production dans ce cas.

---

## 14. Intégration éventuelle après GO seulement

Si et seulement si les gates sont satisfaits :

### 14.1 Conception

Étendre le mécanisme `extreme_gate` existant avec un gate de fiabilité Per-Symbol, sans dupliquer la cascade.

Prévoir une configuration explicitement désactivée par défaut, par exemple conceptuellement :

```yaml
extreme_gate:
  reliable_per_symbol:
    enabled: false
    source_batch_id: null
    quality_metric: f1_macro_shrunk
    selection_mode: top_pct
    top_pct: 0.03
    min_samples: ...
    refresh_frequency: semester
    abstention_enabled: true
```

Les noms réels doivent respecter les conventions du projet après audit. Ne pas recopier cette proposition aveuglément.

### 14.2 Persistance causale

La liste de symboles fiables doit être versionnée par :

- batch Per-Symbol ;
- date d'effet ;
- période de calcul ;
- métrique ;
- support ;
- seuil ;
- fingerprint de configuration.

La production doit charger la dernière liste dont la date d'effet est antérieure ou égale à la date de décision. Aucun fallback silencieux vers une liste calculée avec le futur.

### 14.3 Fallback explicite

Définir le comportement lorsque :

- aucune liste fiable n'existe ;
- un symbole n'a pas de modèle ;
- une probabilité est absente ;
- la liste est périmée ;
- le batch Oracle et le batch Per-Symbol sont incompatibles.

Préférer un rejet/no-trade ou le comportement baseline explicitement configuré. Journaliser le motif.

### 14.4 Observabilité

Ajouter des diagnostics permettant de connaître pour chaque candidat :

- percentile Oracle ;
- statut de fiabilité du symbole ;
- score et support historiques ;
- probabilités LONG/SHORT/FLAT ;
- décision du gate ;
- score final ;
- motif d'acceptation/rejet ;
- version de la liste utilisée.

### 14.5 Tests

Ajouter ou adapter des tests couvrant :

- sélection strictement antérieure à la date du trade ;
- absence de look-ahead ;
- versionnement des listes ;
- symbole fiable/non fiable ;
- données manquantes ;
- modes `filter`, `no_filter`, `bypass` inchangés quand la fonctionnalité est OFF ;
- branche LONG-only ;
- éventuelle branche SHORT ;
- reproductibilité ;
- compatibilité backtest/production ;
- migrations et chargement DB éventuels.

Exécuter les tests pertinents puis la suite complète. Ne pas masquer un défaut applicatif en assouplissant artificiellement les assertions.

---

## 15. Livrables obligatoires

Créer un répertoire d'artefacts dédié et produire :

1. `execution_contract.md` — contrats Oracle, Per-Symbol et portefeuille réellement utilisés ;
2. `data_audit.md` — couverture, unicité, PIT, labels, batches et anomalies ;
3. `per_symbol_quality.csv` — métriques par symbole et période ;
4. `eligible_symbols_by_fold.csv` — listes gelées et motifs de sélection ;
5. `selection_persistence.csv` — stabilité/turnover ;
6. `oracle_conditional_metrics.csv` — D1/D10 et métriques dans le pool Oracle ;
7. `nested_walk_forward_results.csv` — résultats externes ;
8. `placebo_results.csv` — distributions aléatoires/permutations ;
9. `portfolio_results.csv` — métriques PROD par variante ;
10. `concentration_and_breadth.csv` ;
11. `final_report.md` — conclusion complète et reproductible ;
12. si GO : documentation technique et fonctionnelle de l'intégration ;
13. si GO : tests et liste exacte des fichiers modifiés.

Le rapport final doit répondre sans ambiguïté :

1. Les 3 % de symboles performants le restent-ils dans la période suivante ?
2. Leur F1 élevé est-il robuste au support et aux placebos ?
3. Sont-ils meilleurs spécifiquement dans le pool Oracle ?
4. Réduisent-ils D1 et/ou augmentent-ils D10 ?
5. La relation F1 → performance est-elle monotone ?
6. L'intersection quotidienne fournit-elle assez de candidats ?
7. L'amélioration survit-elle au portefeuille PROD et aux coûts ?
8. Le gain est-il stable ou concentré ?
9. Quelle variante exacte est GO, le cas échéant ?
10. Faut-il intégrer, poursuivre la recherche ou abandonner ?

---

## 16. Ordre d'exécution autonome demandé à l'IA

L'IA doit avancer sans demander de validation intermédiaire tant qu'elle reste dans le périmètre suivant : audit, scripts de recherche, tests, artefacts, documentation et intégration derrière un flag OFF après GO démontré.

Ordre obligatoire :

```text
R0 — Lire le code et établir le contrat réel
R1 — Auditer les batches, métriques et prédictions OOS
R2 — Recalculer la distribution des F1 sur ~2 000 symboles
R3 — Mesurer support, incertitude et baselines
R4 — Mesurer la qualité conditionnelle au pool Oracle
R5 — Construire la sélection causale par fold
R6 — Tester sa persistance sur le fold suivant
R7 — Exécuter placebos et permutations
R8 — Tester les combinaisons prédictives pré-enregistrées
R9 — Backtester sous contrat PROD
R10 — Appliquer les gates GO/NO-GO
R11 — Si NO-GO : documenter et arrêter sans toucher à la production
R12 — Si GO : intégrer derrière configuration OFF, tester et documenter
R13 — Exécuter la suite de tests et rendre le rapport final
```

À chaque étape :

- conserver les résultats négatifs ;
- ne pas écraser les artefacts historiques ;
- utiliser de nouveaux IDs de run ;
- journaliser les hypothèses ;
- expliquer les écarts entre documents et code ;
- ne jamais annoncer un GO sur une seule période ou un unique run.

---

## 17. Verdict attendu, sans présupposer le résultat

Trois conclusions sont possibles :

### GO

Une population de symboles est identifiable causalement, reste directionnellement prédictible dans le pool Oracle futur et améliore le portefeuille PROD.

→ Intégrer le gate fiable, désactivé par défaut jusqu'à promotion explicite.

### GO LIMITÉ / RESEARCH

Le signal directionnel existe mais sa couverture, sa stabilité ou sa valeur économique reste insuffisante.

→ Conserver les artefacts et le pipeline de recherche ; ne pas promouvoir en production.

### NO-GO

Les 3 % correspondent principalement à une queue chanceuse, ne persistent pas ou n'améliorent pas Oracle en véritable OOS.

→ Documenter, arrêter la piste et conserver le comportement de production actuel.

---

## 18. Résumé opérationnel

L'idée est prometteuse parce qu'elle sépare correctement les responsabilités :

```text
Oracle = amplitude
Per-Symbol = direction spécialisée
Fiabilité historique causale = droit d'utiliser cette direction
NO-TRADE = réponse normale lorsque le sens n'est pas démontré
```

Mais la découverte de 60 à 70 modèles avec `f1_macro > 0,40` parmi environ 2 000 modèles n'est pas encore une preuve. La campagne doit démontrer que ces symboles peuvent être identifiés **avant** leur période de trading, qu'ils restent bons **dans le pool Oracle**, et que cette information améliore réellement le portefeuille sous le contrat PROD.
