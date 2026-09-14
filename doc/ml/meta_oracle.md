# Meta-Oracle — filtre des faux positifs Oracle

## Contrat autoritatif corrigé

Cette campagne est research-only. Batch recommandé : `model-factory-20260909051302-323684`. Le shadow 2025-07-14 → 2026-06-30 reste un holdout fermé jusqu'au gel du contrat.

Les règles suivantes remplacent toute formulation historique contradictoire dans le protocole détaillé ci-dessous.

1. **Cible** : utiliser `global_oracle_labels.oracle_extreme10`, uniquement avec `target_quality_valid = 1`. `oracle_decile` sert à reporter D1 et D10 séparément, jamais à reconstruire la cible.
2. **Population TOP20** : lire directement `directional_oracle_oof_available = 1` et `directional_oracle_eligible = 1` dans `_oracle_oof_gate.parquet`. Ne pas recalculer le ranking depuis le percentile.
3. **Disponibilité et purge** : un exemple n'entre dans le train que si `oracle_available_date < test_start`. Reporter également une purge nominale d'au moins 20 séances et l'étendre à l'horizon maximal réellement consulté.
4. **V5 et comparateurs** : Meta keep80 conserve exactement 80 % du TOP20 par date. Comparer à nombre quotidien identique avec Oracle TOP16 direct, Oracle-score keep80 et Random keep80. `oracle_pct * p_true_extreme` est un score de ranking, pas une probabilité.
5. **V2/V3** : V3 est le complément mathématique de V2 et seulement une sensibilité de pondération préfixée. Pas de focal loss, hard mining ou sweep avant un signal V2 répétable.
6. **Ordre d'exécution** : étape A = M0/M1 et baselines ; étape B = M2 Logistic/CatBoost fixes, M4/M5 keep80 et M7 bandes Oracle ; arrêt sans AUC/lift/monotonie incrémentale. Étape C seulement après signal : M3, M6 calibré nested-OOF, M8 séparé et une famille F3 à la fois.

---
# CAMPAGNE DE RECHERCHE — META-ORACLE / FALSE-POSITIVE FILTER

## 0. CONTEXTE

Nous disposons déjà d’un modèle Oracle Extreme qui fonctionne correctement pour détecter les titres ayant une forte probabilité de devenir des extrêmes futurs.

Le modèle Oracle ne cherche PAS la direction.

Son objectif est :

    à la date J
    → sélectionner les titres susceptibles d’avoir un mouvement futur extrême
    → extrême négatif D1 OU extrême positif D10

La cible Oracle actuelle est cross-sectionnelle :

    TRUE EXTREME = D1 ou D10
    NON EXTREME  = D2 à D9

L’Oracle possède déjà une capacité prédictive significative sur l’amplitude.

Cependant, même parmi ses meilleures sélections, une proportion importante des candidats finit encore dans D2-D9.

Exemple conceptuel :

    Oracle TOP20 :
        45 % D1/D10
        55 % D2-D9

L’objectif de cette campagne n’est PAS de prédire D1 contre D10.

L’objectif est :

    parmi les candidats déjà sélectionnés par Oracle,
    peut-on identifier ceux qui sont probablement des faux positifs Oracle ?

Autrement dit :

    Oracle
        ↓
    détecteur large d’extrêmes potentiels
        ↓
    Meta-Oracle
        ↓
    filtre / veto / reranking des faux positifs
        ↓
    concentration plus élevée en D1+D10

Cette campagne doit uniquement chercher à améliorer la PURETÉ / PRECISION de l’Oracle.

Elle ne doit pas rechercher la direction.


============================================================
1. HYPOTHÈSE DE RECHERCHE
============================================================

Hypothèse principale :

    les faux positifs de l’Oracle ne sont peut-être pas aléatoires.

Parmi les titres Oracle-selected, certaines caractéristiques disponibles à J peuvent éventuellement distinguer :

    TRUE POSITIVE :
        candidat Oracle qui finit réellement D1 ou D10

    FALSE POSITIVE :
        candidat Oracle qui finit D2 à D9

Si cette distinction est prédictible, un deuxième modèle conditionnel pourrait retirer les faux positifs sans retirer trop de vrais extrêmes.

Architecture cible :

    UNIVERS COMPLET
          ↓
    ORACLE EXTREME
          ↓
    score Oracle OOF
          ↓
    Oracle TOP20
          ↓
    META-ORACLE
          ↓
    P(true_extreme | Oracle-selected)
          ↓
    veto / rerank
          ↓
    sélection finale plus concentrée en D1/D10


============================================================
2. POINT CRITIQUE : NE PAS ENTRAÎNER UN SIMPLE "ORACLE INVERSE"
============================================================

Ne PAS considérer comme modèle principal :

    cible universe-wide :
        D2-D9 = 1
        D1/D10 = 0

avec exactement les mêmes données et mêmes features que l’Oracle.

Pourquoi :

ce modèle risque uniquement d’apprendre :

    P(non-extreme) ≈ 1 - P(extreme)

Il serait alors presque parfaitement redondant avec le modèle Oracle existant.

Cette variante pourra être exécutée uniquement comme contrôle diagnostique.

Elle ne doit PAS être la variante principale.


============================================================
3. POPULATION PRINCIPALE
============================================================

Population de recherche principale :

    uniquement les observations sélectionnées OOF par Oracle.

Contrat recommandé :

    oracle_pct >= 0.80

c’est-à-dire le TOP20 intra-date Oracle.

IMPORTANT :

utiliser exactement la définition du TOP20 déjà utilisée dans le pipeline Oracle officiel.

Ne pas reconstruire un autre ranking.

Ne pas réentraîner Oracle pour cette expérience.

Utiliser les prédictions OOF/PIT déjà produites par l’Oracle de référence.

Si plusieurs versions Oracle existent, utiliser uniquement la version officiellement retenue pour la recherche actuelle.

Enregistrer dans le rapport :

    oracle_batch_id
    oracle_model_version
    oracle_target_version
    universe_version
    feature_contract_version
    label_builder_version


============================================================
4. TARGET META-ORACLE
============================================================

Pour chaque observation Oracle-selected :

    y_meta = 1
        si realized_decile ∈ {D1, D10}

    y_meta = 0
        si realized_decile ∈ {D2,D3,D4,D5,D6,D7,D8,D9}

Donc :

    y_meta = TRUE_EXTREME

Alternative équivalente :

    y_false_positive = 1 - y_meta

La sortie finale recommandée est :

    p_true_extreme

et éventuellement :

    p_false_positive = 1 - p_true_extreme


============================================================
5. IMPORTANT : "NON EXTREME" ≠ "NE BOUGE PAS"
============================================================

Ne pas confondre :

    D2-D9

avec :

    abs(return) faible

La cible Oracle est cross-sectionnelle.

Un titre peut par exemple :

    +5 %

et rester D6 dans une journée extrêmement volatile.

Inversement :

    +1.5 %

peut être D10 dans une journée calme.

La campagne principale doit donc rester :

    D1/D10
    versus
    D2-D9

Une cible "faible mouvement absolu" pourra être testée séparément comme variante expérimentale, mais elle ne doit pas remplacer la cible principale.


============================================================
6. VARIANTES À TESTER
============================================================

Les variantes doivent être pré-enregistrées avant lancement.

Pas de sweep libre après observation des résultats.


------------------------------
V0 — BASELINE
------------------------------

Oracle uniquement :

    oracle_pct >= 0.80

Mesurer :

    taux D1+D10
    nombre de candidats
    candidats/date
    nombre de symboles uniques
    mean abs(H20 return)
    median abs(H20 return)

Ce baseline est la référence absolue.


------------------------------
V1 — INVERSE UNIVERSE-WIDE
------------------------------

Contrôle diagnostique uniquement.

Population :

    univers complet

Target :

    D2-D9 = 1
    D1/D10 = 0

Features :

    exactement les mêmes que l’Oracle

Objectif :

vérifier si ce modèle n’est qu’un complément mathématique de l’Oracle.

Mesurer :

    corr(
        p_non_extreme,
        1 - p_oracle_extreme
    )

Si :

    corr > 0.95

ou si aucune information incrémentale n’est observée :

    verdict = REDUNDANT_CONTROL

Cette variante ne doit pas être promue en production.


------------------------------
V2 — META-ORACLE CONDITIONNEL
------------------------------

VARIANTE PRINCIPALE.

Population :

    Oracle TOP20 OOF uniquement.

Target :

    1 = D1/D10
    0 = D2-D9

Features :

    features PIT disponibles à J

avec possibilité d’inclure :

    oracle_score_oof
    oracle_pct_oof

Sortie :

    p_true_extreme

Cette variante cherche directement :

    P(
        D1 ou D10
        |
        Oracle TOP20,
        information disponible à J
    )


------------------------------
V3 — HARD NEGATIVE MODEL
------------------------------

Même population que V2.

Mais objectif explicitement orienté faux positifs :

    1 = FALSE POSITIVE Oracle
    0 = TRUE EXTREME Oracle

Les exemples D2-D9 sélectionnés par Oracle sont considérés comme :

    HARD NEGATIVES

Objectif :

identifier les caractéristiques communes des erreurs de l’Oracle.

Sortie :

    p_false_positive

Cette variante peut être équivalente mathématiquement à V2 mais elle peut utiliser :

    class weighting
    focal loss
    hard-example emphasis

sans optimisation de nombreux hyperparamètres.


------------------------------
V4 — META VETO
------------------------------

Utiliser V2 ou V3.

Ne pas modifier Oracle.

Pipeline :

    Oracle TOP20
          ↓
    Meta score
          ↓
    retirer les candidats les plus probablement faux positifs

Primary veto contract :

    retirer les 20 % de candidats ayant
    le plus fort p_false_positive

IMPORTANT :

ce quota doit être calculé intra-date.

Donc par date :

    Oracle TOP20
        ↓
    rank meta
        ↓
    drop worst 20 %

Ne pas optimiser le seuil global sur toute l’histoire.

Sensibilités autorisées :

    drop 10 %
    drop 30 %

Mais :

    20 % = PRIMARY

10 % et 30 % = SENSITIVITY ONLY.


------------------------------
V5 — META RERANK
------------------------------

Ne supprimer initialement aucun titre.

À l’intérieur du pool Oracle TOP20 :

    rerank par p_true_extreme

Puis conserver le même nombre de candidats qu’un contrat baseline donné.

Deux scores autorisés :

    META_ONLY =
        p_true_extreme

et

    PRODUCT =
        oracle_pct * p_true_extreme

Ne pas tester d’autres coefficients arbitraires.

Interdiction :

    alpha * oracle + beta * meta

avec recherche libre de alpha/beta.


------------------------------
V6 — RESIDUAL META-ORACLE
------------------------------

Variante secondaire.

Objectif :

forcer le modèle à apprendre ce que l’Oracle ne sait PAS déjà.

Exemple :

    residual_target =
        y_true_extreme
        -
        calibrated_oracle_probability

ou apprentissage de :

    P(
        true_extreme
        |
        oracle_score_band
    )

Utiliser uniquement si V2 montre quelque chose.

Ne pas commencer par V6.


------------------------------
V7 — ORACLE-SCORE-BAND MODEL
------------------------------

Variante de contrôle très importante.

Découper les candidats Oracle par bandes de score :

    80-85 %
    85-90 %
    90-95 %
    95-100 %

Puis tester si le Meta-Oracle distingue encore :

    D1/D10
    vs
    D2-D9

à l’intérieur de bandes Oracle similaires.

Objectif :

prouver que Meta-Oracle apporte une information nouvelle
et ne fait pas simplement :

    "garder les meilleurs scores Oracle"


------------------------------
V8 — ABSOLUTE NON-MOVER MODEL
------------------------------

EXPÉRIMENTAL UNIQUEMENT.

Target possible :

    abs(H20 return) < seuil fixe

ou

    future excursion faible

Cette variante correspond davantage à l’idée intuitive :

    "ce titre ne va pas vraiment bouger"

Mais elle teste une hypothèse différente de D1/D10 vs D2-D9.

Elle doit avoir un rapport distinct.

Ne pas mélanger son verdict avec celui du Meta-Oracle principal.


============================================================
7. FEATURES
============================================================

Créer plusieurs familles de tests clairement séparées.


------------------------------
F0 — ORACLE SCORE ONLY
------------------------------

Features :

    oracle_score_oof
    oracle_pct_oof

Objectif :

baseline minimal.


------------------------------
F1 — ORACLE ORIGINAL FEATURES
------------------------------

Features PIT utilisées par l’Oracle.

Objectif :

tester si les mêmes variables contiennent encore de l’information conditionnelle.


------------------------------
F2 — FEATURES ANTI-FAUX-POSITIF
------------------------------

Construire des variables conceptuellement liées à la validation/invalidation d’un vrai mouvement.

Exemples possibles :

    volatility already consumed
    recent range expansion
    distance to recent high
    distance to recent low
    gap already consumed
    intraday reversal
    volume confirmation
    relative volume
    volume acceleration
    liquidity
    spread proxy
    sector confirmation
    market confirmation
    beta-adjusted move
    residual move
    cross-sectional divergence
    failed breakout
    failed breakdown
    compression / expansion state
    recent reversal score

Toutes doivent être PIT.


------------------------------
F3 — NEW INFORMATION FAMILIES
------------------------------

Si disponibles historiquement/PIT :

    analyst revisions
    options features
    securities lending
    premarket/opening window
    event information
    earnings proximity

IMPORTANT :

une famille nouvelle doit être testée séparément.

Exemple :

    BASE
    BASE + ANALYST
    BASE + OPTIONS
    BASE + LENDING

Pas :

    ajouter toutes les nouvelles sources d’un coup.


============================================================
8. MODÈLES
============================================================

Ne pas lancer une compétition de 50 modèles.

Models autorisés initialement :

    Logistic Regression
    LightGBM
    CatBoost

Logistic Regression :

    baseline de référence

LightGBM / CatBoost :

    modèles non linéaires fixes

Pas de sweep massif d’hyperparamètres.

Utiliser les configurations standard déjà employées dans le repository lorsque possible.

Interdit initialement :

    Transformer
    LSTM
    stacking complexe
    AutoML
    Bayesian optimization
    100 hyperparameter trials


============================================================
9. PROTOCOLE OOF / PIT OBLIGATOIRE
============================================================

C’est la partie la plus importante.

Aucune observation ne doit être construite à partir d’une prédiction Oracle in-sample.

Le Meta-Oracle doit utiliser :

    Oracle score OOF uniquement.


Pipeline conceptuel :

OUTER FOLD k

    1. Oracle a déjà été entraîné sur le passé uniquement.

    2. Oracle génère ses prédictions OOF
       sur la période k.

    3. Sélectionner Oracle TOP20
       à partir de ces prédictions OOF.

    4. Construire :
           TRUE_EXTREME
           FALSE_POSITIVE

       uniquement après maturation H20.

    5. Les exemples Meta-Oracle disponibles
       pour l’entraînement doivent appartenir
       à des dates antérieures au test.

    6. Appliquer purge >= horizon.

    7. Meta-Oracle prédit le fold futur.

Donc :

    Oracle OOF
        ↓
    Meta train historical
        ↓
    Meta OOF


INTERDICTION ABSOLUE :

    entraîner Meta sur des erreurs Oracle calculées
    à partir de prédictions Oracle in-sample.


============================================================
10. PURGE ET EMBARGO
============================================================

Pour cible H20 :

    purge minimale = 20 sessions de marché

entre train et test.

Si labels utilisent un maximum/minimum futur au-delà de H20 :

    purge = horizon maximum réel utilisé.

Documenter précisément :

    train_end
    purge_start
    purge_end
    test_start


============================================================
11. CROSS-SECTION ET WEIGHTING
============================================================

Comme la cible est cross-sectionnelle :

éviter qu’une date ayant énormément de symboles domine les résultats.

Produire :

    metrics observation-weighted
    metrics equal-date-weighted

Primary :

    equal-date-weighted

Bootstrap :

    cluster bootstrap par date

PAS bootstrap observation par observation.


============================================================
12. MÉTRIQUES ML
============================================================

Pour V2/V3 :

    ROC-AUC
    PR-AUC
    logloss
    Brier score

Mais ces métriques sont secondaires.

Les métriques principales sont économiques/structurelles.


============================================================
13. MÉTRIQUES PRINCIPALES
============================================================

Baseline Oracle :

    extreme_precision_baseline =
        #(D1+D10) / #Oracle_candidates

Après Meta :

    extreme_precision_meta =
        #(D1+D10) / #Meta_candidates


Primary Lift :

    precision_lift =
        extreme_precision_meta
        -
        extreme_precision_baseline

et :

    relative_precision_lift =
        extreme_precision_meta
        /
        extreme_precision_baseline
        - 1


Mesurer également :

    extreme_recall

    TP_removed
    FP_removed

    false_positive_removal_rate

    true_positive_loss_rate

    FP_removed_per_TP_removed

    mean_abs_return
    median_abs_return

    mean_excursion
    median_excursion

    candidates_per_date

    unique_symbols

    concentration_by_symbol

    concentration_by_sector

    turnover_of_selection


============================================================
14. MÉTRIQUE TRÈS IMPORTANTE : FP REMOVED / TP REMOVED
============================================================

Calculer :

    removal_efficiency =
        false_positives_removed
        /
        true_extremes_removed

Exemple bon :

    FP removed = 260
    TP removed = 40

    efficiency = 6.5

Exemple mauvais :

    FP removed = 100
    TP removed = 90

    efficiency = 1.11

Cette métrique doit figurer dans le résumé.


============================================================
15. META SCORE BUCKETS
============================================================

Dans le pool Oracle uniquement :

créer 10 déciles de p_true_extreme.

Pour chaque décile Meta :

    count
    %D1
    %D10
    %D1+D10
    mean abs return
    median abs return
    mean excursion

On recherche une relation monotone :

    Meta Q1
        faible D1+D10

    ...

    Meta Q10
        fort D1+D10

Le graphe / tableau doit montrer clairement la monotonicité.


============================================================
16. IMPORTANT : D1 ET D10 SÉPARÉS
============================================================

Même si la cible Meta est :

    D1 OU D10

toujours reporter séparément :

    %D1
    %D10

Objectif :

s’assurer que Meta-Oracle n’augmente pas artificiellement la pureté
en ne conservant qu’un seul côté.

Exemple problématique :

    baseline :
        D1 = 22 %
        D10 = 23 %

    Meta :
        D1 = 5 %
        D10 = 48 %

Ce n’est pas nécessairement mauvais pour amplitude,
mais cela change fortement la nature du système.

Cela doit être visible.


============================================================
17. STABILITÉ TEMPORELLE
============================================================

Reporter :

    par fold
    par année
    par régime si disponible

Pour chaque période :

    baseline D1+D10
    Meta D1+D10
    delta

Ne pas accepter un résultat uniquement porté par une année.


============================================================
18. STABILITÉ PAR ORACLE SCORE
============================================================

Comparer Meta à Oracle à l’intérieur de bandes fixes :

    Oracle pct 80-85
    85-90
    90-95
    95-100

Si Meta n’apporte rien à Oracle score égal :

    signal probablement redondant.

Si Meta continue à distinguer les vrais extrêmes :

    preuve d’information incrémentale.


============================================================
19. PLACEBO TESTS
============================================================

Obligatoires.

PLACEBO 1 :

    shuffle target par date

Résultat attendu :

    AUC ≈ 0.50
    precision lift ≈ 0


PLACEBO 2 :

    décaler les features d’une date future incorrecte
    uniquement dans environnement contrôlé
    pour vérifier que le harness détecte la fuite.

Ce test ne doit jamais être mélangé aux résultats réels.


PLACEBO 3 :

    random veto

Retirer aléatoirement 20 % des candidats Oracle.

Comparer :

    Meta veto
    versus
    Random veto

Meta doit battre clairement random.


============================================================
20. BASELINE DE RÉDUCTION MÉCANIQUE
============================================================

Comparer Meta à :

    keep Oracle TOP16%

si Meta veto de 20 % réduit Oracle TOP20 à environ 16 % de l’univers.

Pourquoi :

si Meta améliore la précision uniquement parce qu’il garde moins de titres,
il faut savoir si :

    Oracle TOP16 direct

fait aussi bien.

Donc comparer :

    Oracle TOP20
    Oracle TOP16
    Oracle TOP20 + Meta drop20

Ceci est obligatoire.


============================================================
21. AUTRE BASELINE : ORACLE SCORE RERANK
============================================================

Comparer :

    Oracle TOP20 + Meta veto

à :

    Oracle TOP20
    puis simplement retirer les 20 % ayant
    le plus faible Oracle score.

Si Meta ne fait pas mieux :

    Meta n’apporte probablement rien d’incrémental.


============================================================
22. BREADTH / CAPACITY
============================================================

Une amélioration de pureté n’est pas suffisante si elle détruit complètement la breadth.

Reporter :

    mean candidates/day
    median candidates/day
    p10/p90 candidates/day

    unique symbols/year
    Herfindahl symbol concentration
    sector concentration

Exemple :

    55 % D1+D10
    mais seulement 2 candidats/jour

n’est pas nécessairement utile.

Comparer toujours au baseline Oracle.


============================================================
23. PAS DE PNL DIRECTIONNEL EN PRIMARY
============================================================

Cette campagne ne prédit PAS :

    LONG
    SHORT

Donc ne pas utiliser comme critère principal :

    portfolio return
    Sharpe
    win rate LONG
    win rate SHORT

Ce serait méthodologiquement incorrect.

Primary objective :

    améliorer la concentration en extrêmes.

L’évaluation portfolio ne pourra arriver qu’après validation du Meta-Oracle
et combinaison avec un système directionnel indépendant.


============================================================
24. CRITÈRES GO / NO-GO
============================================================

Créer quatre niveaux.


NO_GO

si :

    aucune amélioration stable
    OU
    lift essentiellement nul
    OU
    Meta seulement équivalent au ranking Oracle
    OU
    résultat instable par année/fold
    OU
    breadth fortement détruite
    OU
    placebo/random veto équivalent.


WEAK_SIGNAL

si :

    amélioration faible mais cohérente
    avec CI incluant encore zéro
    ou stabilité insuffisante.


GO_RESEARCH

si :

    precision D1+D10 augmente clairement
    sur majorité des folds

ET

    date-cluster bootstrap favorable

ET

    Meta bat :
        random veto
        Oracle-score veto
        direct TOP16 baseline

ET

    relation Meta bucket → D1+D10 monotone

ET

    breadth reste acceptable.


STRONG_GO

si :

    lift important
    stable temporellement
    bootstrap significatif
    breadth correcte
    information incrémentale claire
    inside-oracle-band signal stable.


============================================================
25. EXEMPLES DE GATES À RAPPORTER
============================================================

Ne pas imposer un chiffre arbitraire comme règle universelle.

Mais fournir dans le rapport :

    baseline precision
    meta precision
    absolute lift
    relative lift

    TP retained %
    FP removed %

    FP_removed / TP_removed

    candidate retention %

    fold-positive ratio

    year-positive ratio

    bootstrap CI


============================================================
26. STOP RULE
============================================================

Si la variante principale V2 :

    AUC ≈ 0.50

ET

    aucun lift D1+D10

ET

    aucun bucket monotone

alors :

    STOP

Ne pas lancer :

    40 hyperparameter sweeps
    neural networks
    feature mining massif

Verdict :

    META-ORACLE_NO_SIGNAL


============================================================
27. CAS OÙ IL FAUT CONTINUER
============================================================

Continuer uniquement si :

    V2/V3 montre un signal répétable

mais :

    trop faible pour promotion.

Alors seulement tester :

    nouvelles familles de données PIT
    nouvelles informations structurellement différentes

Par exemple :

    analyst revisions
    options
    lending
    auction imbalance
    earnings/event features

Pas simplement :

    plus de transformations OHLCV.


============================================================
28. PAS DE RETUNING DU TOP20
============================================================

Ne pas lancer :

    Oracle TOP10
    TOP12
    TOP13
    TOP15
    TOP17
    TOP19
    etc.

dans le but d’optimiser le résultat.

Le TOP20 est le contrat principal.

Une éventuelle analyse TOP10 peut exister comme robustesse secondaire
si elle est déjà une définition historique officielle,
mais elle ne doit pas servir à choisir le meilleur seuil après coup.


============================================================
29. PAS DE LEAKAGE PAR LE LABEL
============================================================

Vérifier explicitement :

    aucune feature n’utilise :

        future return
        future high
        future low
        realized decile
        future volume
        future Oracle output
        revised future fundamental
        future earnings actual

Toutes les features doivent respecter :

    feature.available_at <= decision_time_J


============================================================
30. DONNÉES RÉVISABLES
============================================================

Pour les données pouvant être révisées :

    fundamentals
    analysts
    earnings
    options derived metrics
    etc.

utiliser :

    available_at

et non uniquement :

    fiscal_date
    period_end
    publication_date approximative


============================================================
31. MISSINGNESS
============================================================

Ne pas remplacer automatiquement les valeurs manquantes par zéro.

Créer si nécessaire :

    feature_is_available
    feature_age
    feature_staleness

Un missing peut être informatif,
mais ne doit pas être confondu avec une vraie valeur zéro.


============================================================
32. RAPPORT FINAL OBLIGATOIRE
============================================================

Produire :

    report.md
    report.json
    candidates.csv
    fold_metrics.csv
    yearly_metrics.csv
    meta_decile_metrics.csv
    oracle_band_metrics.csv
    veto_comparison.csv

Graphiques recommandés :

    baseline vs Meta extreme rate
    Meta decile → D1+D10
    precision vs retention
    FP removed vs TP removed
    yearly lift
    fold lift


============================================================
33. TABLEAU SYNTHÈSE FINAL
============================================================

Produire au minimum :

| Variant | Retention | D1 | D10 | D1+D10 | Lift | FP removed | TP removed | Efficiency |
|---------|-----------|----|-----|--------|------|------------|------------|------------|

Puis :

| Variant | Cand/day | Unique symbols | Fold positive | Year positive | Bootstrap CI |
|---------|----------|----------------|---------------|---------------|--------------|


============================================================
34. VERDICT FINAL
============================================================

Le rapport doit terminer par UNE décision explicite :

    NO_GO
    WEAK_SIGNAL
    GO_RESEARCH
    STRONG_GO

et répondre précisément :

1. Meta-Oracle arrive-t-il à distinguer les vrais extrêmes
   des faux positifs Oracle ?

2. L’information est-elle réellement incrémentale
   par rapport au score Oracle ?

3. Combien de faux positifs sont retirés
   pour chaque vrai extrême perdu ?

4. Quelle concentration D1+D10 est atteinte ?

5. Quel pourcentage des candidats Oracle est conservé ?

6. La relation est-elle stable par année et par fold ?

7. Le signal survit-il dans les mêmes bandes de score Oracle ?

8. Meta bat-il :
       random veto
       Oracle score veto
       direct narrower Oracle cutoff ?

9. Le résultat justifie-t-il une intégration future
   ou faut-il clôturer la branche ?


============================================================
35. INTÉGRATION PRODUCTION INTERDITE À CE STADE
============================================================

Cette campagne est RESEARCH ONLY.

Aucune modification :

    production cascade
    live selection
    risk management
    position sizing
    execution

tant qu’un verdict GO_RESEARCH ou STRONG_GO
n’a pas été obtenu et validé sur une période temporelle indépendante.


============================================================
36. NOM RECOMMANDÉ DE LA CAMPAGNE
============================================================

Nom :

    META_ORACLE_FALSE_POSITIVE_FILTER

Sous-expériences :

    M0_BASELINE
    M1_INVERSE_CONTROL
    M2_CONDITIONAL_META
    M3_HARD_NEGATIVE
    M4_META_VETO
    M5_META_RERANK
    M6_RESIDUAL
    M7_ORACLE_BAND
    M8_ABSOLUTE_NON_MOVER


============================================================
37. PRINCIPE FINAL À RESPECTER
============================================================

Le but n’est PAS :

    "construire un meilleur Oracle à tout prix"

Le but est de tester une hypothèse très précise :

    "les erreurs de l’Oracle sont-elles prévisibles
     avec l’information disponible à J ?"

Si oui :

    Oracle
        = détecteur large d’amplitude

    Meta-Oracle
        = détecteur de faux positifs

    combinaison
        = sélection plus pure


Si non :

    conserver Oracle seul
    et clôturer la branche sans retuning massif.