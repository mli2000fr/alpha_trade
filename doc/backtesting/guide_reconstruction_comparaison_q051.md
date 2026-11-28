# Reconstruction complète des neuf courbes Q051, B, anti-SL et SPY

Édition du **28 novembre 2026**. Répertoire du projet : `F:\projets`.
Document de référence de la popin **Voir les courbes et leur comparaison**.

## 1. Périmètre, résultat attendu et modes de reproduction

Ce guide décrit les **neuf cas réellement affichés** : Q051 TOP5/TOP10,
leurs variantes vol20 + régime, le témoin T0 apparié de B, B seul, B + anti-SL,
le plafond de prix avec attente deux séances et SPY. Il décrit l’entraînement,
la prédiction et le replay ; il **ne lance aucune opération**.

Période : **1er janvier 2021–1er octobre 2026**, **4 000 USD** initiaux,
capital et positions transmis entre années. Le 1er janvier férié est une ancre
de capital ; la première entrée réelle se fait à une séance US officielle.
Le signal de la dernière séance de l’année précédente doit donc être présent.

Deux objectifs différents :

1. **Reproduire les chiffres archivés** : réutiliser les mêmes poids, signaux,
   prix, événements, configuration, calendrier et version du moteur, contrôlés
   par leurs empreintes. C’est la voie de référence numérique.
2. **Reconstruire depuis l’entraînement** : repartir des snapshots de données
   qualifiées, refaire les modèles avec les mêmes contrats et graines, puis
   prévoir et rejouer. Cela produit **de nouveaux batches**. Changer les données
   révisées, les bibliothèques ou le code peut changer les poids et le rendement :
   ne pas promettre les mêmes décimales sur une nouvelle collecte.

Le présent dossier contient une **recette et des inventaires**. Il ne contient
pas les poids binaires ni les centaines de fichiers de prix. Il faut conserver
les archives listées. Des identifiants de modèles seuls ne remplacent pas ces fichiers.

### Annexes livrées avec ce document

- [Contrats et configurations intégrales](reconstruction_q051/contrats_et_configurations.json) :
  douze contrats d’entraînement Oracle, huit configurations de portefeuille,
  paramètres des branches, règles anti-SL, chemins des résultats et empreintes.
- [Modèles annuels](reconstruction_q051/modeles_annuels.csv) : dates et identifiants.
- [Folds Oracle](reconstruction_q051/folds_oracle.csv) : bornes causales, disponibilité
  des labels et backend retenu, fold par fold.
- [Fenêtres par titre LONG](reconstruction_q051/fenetres_per_symbol_long.csv) : poids
  réellement utilisés par les deux familles, dates de fit/calibration, disponibilité,
  AUC et SHA-256. Les branches SHORT natives n’entrent dans aucune de ces neuf courbes.
- [Têtes anti-SL](reconstruction_q051/tetes_anti_sl.csv) : années, seuils et poids.
- [Variables ordonnées](reconstruction_q051/variables.json), univers figés
  [Q051](reconstruction_q051/univers_q051.txt) et [B](reconstruction_q051/univers_b.txt).
- [Empreintes de documentation](reconstruction_q051/integrite_documentation.json).

Dans le ZIP proposé dans la popin, ces annexes gardent leur sous-dossier relatif.
Le lecteur peut les ouvrir sans accéder à SQL, au broker ou à un fournisseur.

### Résultats archivés qui servent de contrôles

Les chiffres ci-dessous ne sont pas un objectif d’optimisation à retrouver en
modifiant les seuils. Ils permettent de détecter une différence de reconstruction.
Le DD intraday des stratégies est celui des prix simulés observables ; il ne
certifie pas le pire creux d’une séance dont les bougies sont absentes.


| Courbe | Capital final USD | Rendement | DD intraday | DD clôtures | Gagnants |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q051 témoin — TOP5 | 12 260,32 | 206,51 % | -36,89 % | -36,80 % | 35,01 % |
| Volatilité 20 % + régime — TOP5 | 9 039,00 | 125,98 % | -24,29 % | -23,40 % | 36,17 % |
| Volatilité 20 % + régime — TOP10 | 10 035,92 | 150,90 % | -17,58 % | -16,80 % | 36,33 % |
| Q051 témoin — TOP10 | 15 237,79 | 280,94 % | -40,45 % | -40,29 % | 35,62 % |
| Témoin B — 24 variables, mêmes Oracle | 9 162,34 | 129,06 % | -39,12 % | -38,46 % | 34,23 % |
| B seul — 29 variables, TOP10 | 15 894,14 | 297,35 % | -40,99 % | -39,40 % | 37,63 % |
| B + anti-SL témoin — TOP10 | 16 140,82 | 303,52 % | -34,98 % | -34,08 % | 38,13 % |
| Q051 témoin TOP10 — plafond, attente deux séances | 18 593,49 | 364,84 % | -46,26 % | -45,72 % | 34,63 % |
| SPY | 8 142,50 | 103,56 % | — | -25,36 % | — |

## 2. Deux familles de modèles : différence essentielle

### Famille Q051 classique

Six batches annuels, Oracle H10 à **173 variables**, avec modèles annuels
LONG/SHORT **par titre à 24 variables**. Cette famille alimente Q051 TOP5,
Q051 TOP10, leurs deux versions vol20 + régime, ainsi que le plafond avec attente.
Le passage TOP5 → TOP10 change la sélection, pas l’entraînement des mêmes poids.

### Famille B de recherche

Six autres Oracles annuels, également H10/173 variables, issus de la campagne
`us_q051_features173/20261116-v2`. Leurs poids per-symbol natifs à **173 variables**
existent, mais **ne sont pas les poids LONG utilisés dans les courbes T0/B**.
La recherche `us_q051_feature_groups/20261116-lot1` a réentraîné des poids LONG
spécifiques **T0 à 24** et **B à 29 variables**, sur une cohorte commune et avec
les mêmes lignes de fit/calibration. Leurs fichiers sont dans `jobs/.../models/`.
La courbe anti-SL utilise B et une tête commune à 44 variables.

Conséquence : sélectionner seulement un batch `model-factory-20261116071351-*`
dans l’IHM ne suffit pas à reproduire les courbes B. Il faut réutiliser les
poids/rankings/signaux de recherche, ou reconstruire cette chaîne spécifique.
L’option native actuelle `compact_volatility` permet de préparer de nouveaux
bundles B29 ; elle ne constitue pas une identité automatique avec ces archives.

Les différences +129,06 % du T0 apparié contre +280,94 % du Q051 classique
ne mesurent pas l’apport des cinq variables B. Pour cet apport, comparer
**T0 apparié et B**, puis **B et B + anti-SL**, sur leur famille commune.

## 3. Données et univers nécessaires

### 3.1. Données d’apprentissage

Barres journalières US : `stock_bars_daily`, avec `symbol`, `date`, OHLC,
`adj_close`, `volume`, `is_filled`, `instrument_id`, `data_source`, `data_adjustment`.
SPY est le benchmark. Il faut le passé des fenêtres annuelles dès **2014**
pour l’année test 2021, puis 2015, 2016, 2017, 2018, 2019 pour les suivantes.
Les seules bougies intraday depuis 2016 ne remplacent pas ce passé daily.

Les barres sont sélectionnées **ligne entière** selon le contrat de fournisseur,
sans mélanger open d’un fournisseur et close d’un autre. Éviter doublons de dates,
identités manquantes, ruptures d’instrument et séries remplies artificiellement.
Le registre des discontinuités doit rester identique : une même chaîne de ticker
peut recouvrir des actions différentes après restructuration.

Conserver l’univers **ordonné** du protocole du batch : ici 1 790 symboles.
Les copies figées sont livrées en annexe. Ne pas remplacer cette liste par le
fichier tradable du jour, ni faire un univers rétrospectif à partir des gagnants.
L’univers original est lui-même rétrospectif, pas un registre historique PIT complet.

### 3.2. Prix d’exécution et contexte du portefeuille

Barres 5 minutes SIP archivées, OHLC journaliers canoniques, calendrier US,
SPY, secteurs et événements de corporate actions : ce sont les données du replay.
Les secteurs archivés sont en partie contemporains de la recherche et non PIT.
Les dividendes qualifiés sont comptabilisés par le moteur ; ne pas interpréter
la comparaison SPY en cours seuls comme un rendement total dividendes réinvestis.

Le calendrier est celui de `US_EQ`, y compris jours fériés et clôtures anticipées.
Une séance n’est pas un jour civil et « dix séances » n’est pas « deux semaines ».

### 3.3. Arborescences à conserver

Pour Q051 classique :

```text
artifacts/models/<six batches classiques>/oracle_path/
  protocol.json, feature_profile.json, report.json, quality.json
  folds/<date>/... champion et poids, reçus, empreintes
  chunks/*/bars.parquet, features*.parquet selon les archives
  directional/manifest.json, benchmark.parquet, <titre>/*.joblib
artifacts/research/us_winner_continuous_q051_q088/20261108-v2/
  inputs/manifest.json, base/, extra-*, rankings/, signals-*.parquet
artifacts/research/us_winner_vol20_extensions/20261109-v1/inputs/
artifacts/research/us_q051_selection_variants/20261115-v1/
artifacts/research/us_q051_classic_top10/20261115-v1/
artifacts/research/us_winner_q051_risk_budget/20261109-v1/
```

Pour B/anti-SL, ajouter :

```text
artifacts/models/<six batches famille B>/oracle_path/
artifacts/research/us_q051_features173/20261116-v2/
artifacts/research/us_q051_features173/20261116-v3-sip/
artifacts/research/us_q051_feature_groups/20261116-lot1/
  protocol.json, jobs/*/models.json, jobs/*/models/**/*.joblib
  years/*/oracle.parquet, variants/{T0,B}/models.json, signals.parquet
  inputs/manifest.json, prix supplémentaires et intraday
artifacts/research/us_q051_b_early_sl/20261116-v1/
  heads/*/{models.json,SL10-*.joblib,probabilities.parquet}
  jobs/, variants/SL10/signals.parquet, inputs/, validation*.json
```

Le plafond utilise aussi `us_q051_decline_rebound/20261126-v2/inputs`
et `us_q051_entry_ceiling/20261127-v1`. Son manifeste référence les prix
des racines classiques. Ne pas supprimer une racine simplement parce qu’une
copie de `equity-daily.csv` se trouve ailleurs : ce n’est pas la totalité du graphe de dépendances.

## 4. Cycle économique commun aux huit stratégies

### 4.1. Candidats à la clôture J

1. Scorer l’univers entier du modèle avec les seules informations connues à J.
2. Trier l’Oracle par probabilité d’extrême décroissante, avec ordre de ticker
   déterministe pour les égalités ; conserver `ceil(0,10 × 1790)=179` titres.
3. Dans ce pool figé, classer les probabilités LONG per-symbol décroissantes.
4. Fixer TOP5 ou TOP10 selon le cas, puis appliquer **score >0,50** et
   **AUC de calibration ≥0,50**. Une AUC absente/future/d’autres poids n’est pas admissible.
5. Appliquer les éventuels veto anti-SL ou régime ; **pas de remplacement**
   par le rang suivant. Les titres déjà détenus ne sont pas achetés une seconde
   fois par simple répétition du signal.

Le TOP20 % de la **cible d’apprentissage Oracle** n’est pas le TOP10 %
conservé à la prédiction. Le `oracle_top_n=20` ancien dans certains contrats
de bundle est un défaut de serving : les archives de recherche figent explicitement
**179** pour ces expériences. Ni le nom du batch ni le label d’un profil
ne remplace la sélection archivée.

### 4.2. Entrée, SL et échéance

Entrée standard **open J+1**, sur le calendrier officiel, sans deux confirmations
5m. Le mode Winner reste utilisé pour le cycle de position, mais `confirmation_bars=0`,
`initial_position_fraction=1`, renforcement désactivé. SL initial **5 % du
prix réellement rempli**, avec arrondi monétaire du moteur. Pas de TP,
pas de trailing. Une ancienne valeur TP/trailing d’un formulaire classique
ne doit pas supplanter ce contrat Winner.

Dix séances de détention, entrée incluse, puis vente **à l’ouverture de la
onzième séance** si aucun SL n’a fermé la position avant. À l’entrée un lundi,
compter les seules séances ouvertes ; les jours fériés ne consomment pas de séance.
Lorsqu’une fenêtre est décalée par le plafond, compter depuis l’entrée effective.

Un stop ne garantit pas une perte maximale de 5 % : un gap sous le stop est
vendu au prix d’ouverture exécutable, potentiellement inférieur. Sur des OHLC
ambigus, la convention de sortie est prudente, pas une reconstruction du carnet.

### 4.3. Dimensionnement, capacité et coûts

| Paramètre commun | Valeur effective |
| --- | --- |
| Capital initial / resets | 4 000 USD / aucun reset annuel |
| Type de compte | margin ; capacité nominale 2× |
| Plafond d’admission des achats | **1× le capital courant** |
| Risque budgété par entrée | 1,25 % du capital courant |
| Poids maximal par titre | 20 % |
| Positions simultanées | 20 |
| Ligne minimale | 50 USD |
| Taille | Actions entières, position complète approuvée |
| Entrées par titre | 10 sur **90 jours calendaires** dans ces configurations figées |
| Pertes consécutives | 3, puis blacklist de **90 jours calendaires** |
| Frais effectifs du replay | 16 pb aller-retour = **8 pb par côté** |
| Réserve de sizing | 25 pb par côté ; distincte des frais comptabilisés |
| Financement | 6,5 % annualisé, appliqué par séance sur cash débiteur, /252 |
| Vente/achat le même jour | Autorisé pour que le SL puisse sortir le jour d’entrée |

Ne pas substituer les anciens essais « 10 entrées sur 180 jours », ni la
pause100 après deux SL : ils ne décrivent pas ces huit configurations.

Le moteur calcule une quantité entière sous le budget SL et coûts, puis borne
par poids, ligne minimale, cash/capacité, contraintes natives et positions existantes.
Une forme du budget initial est :

`floor((equity × 0,0125) / (prix × (0,05 + 2,05 × max(réserve_de_coût, frais_effectifs))))`

Cette expression n’est pas la totalité du risk checker. Tous les plafonds et
arrondis sont ensuite réappliqués. À chaque entrée, le capital et la capacité
sont recalculés ; ne pas faire une simulation de trades indépendants à taille
constante. Le compte peut techniquement offrir 2× et la stratégie n’en admettre
que 1×. Cela ne signifie pas 8 000 USD de budget initial effectivement utilisé.

Le coût effectif est choisi par `cost_round_trip_bps/20000=0,0008` dans le replay.
Les champs hérités `fees_pct`, `commission_bps`, `slippage_bps` qui restent dans
la configuration complète ne sont pas à additionner à nouveau. Les 8 pb sont
une convention de coût globale, pas une reproduction intégrale de spread,
impact et slippage observés sur chaque ordre.

### 4.4. Contrôles désactivés et contrôles conservés

Pour ces huit cas, **contrôleur B4/DD, liquidation globale DD, facteurs,
corrélation, plafonds sectoriels, filtre options et GPT sont désactivés**.
La présence d’un champ `policy=b4`, `max_portfolio_beta=5` ou d’un seuil DD15
stocké dans le JSON ne prouve pas son activation : les interrupteurs effectifs
comptent. Les limitations de capital, de taille, de répétition, d’identité/prix
et de coût restent appliquées. Les cas vol20 ajoutent uniquement leur budget
de volatilité et leur filtre d’entrée SPY, détaillés plus bas.

### 4.5. Résolution des protections et valorisation

Une séance 5m complète et compatible avec le prix daily sert aux protections.
Sinon, le moteur déclare un **repli OHLC journalier**. Il ne fabrique pas 78
bougies à partir d’un high/low. Une entrée journalière à J+1 peut donc avoir
lieu malgré des bougies intraday manquantes, mais la précision des sorties et
de la valorisation est alors moindre. L’ouverture connue peut être conservée
comme marque pendant la séance jusqu’à une clôture observable.

`DD = min_t(equity_t / max(equity_initiale, equity_0..t) − 1)`.
La popin indique le DD intraday simulé quand il existe ; SPY n’a que son DD
aux clôtures. Pour une comparaison de fréquences homogènes, utiliser la
colonne DD sur clôtures. Un résultat marqué `INCOMPLETE_COVERAGE` reste
exploratoire même si le programme a terminé et si la comptabilité est réconciliée.

## 5. Formation des cibles

### Oracle parcours H10 — amplitude, pas direction

À la clôture J ajustée `Cj`, calculer sur J+1..J+10 :

`up=max(0,max(high_ajusté)/Cj−1)` ; `down=max(0,1−min(low_ajusté)/Cj)` ;
`amplitude=max(up,down)`.

La cible binaire d’Oracle distingue les véritables extrêmes du TOP20 % de la
section journalière, avec contrôles de couverture/univers, d’identité et de
fenêtre complète. Elle mûrit seulement à J+11, même si le pic arrive avant.
Ni hausse de 20 %, ni clôture terminale H10, ni étiquette LONG/SHORT.

### LONG per-symbol — rentabilité nette du parcours protégé

Entrée open J+1, SL5 %, sinon open11, coûts de label 8 pb par côté. Le label
est 1 si le résultat net LONG est strictement positif, 0 sinon. Le gap est
pris en compte. Même un stop précoce n’est déclaré disponible pour l’entraînement
qu’à l’échéance complète du label, par prudence. OHLC ajustés sur une base
cohérente et identité/source stables sont nécessaires ; pas de label sur une
fenêtre non qualifiée.

L’AUC mesure le classement, pas une probabilité de gagner, et l’AUC de
calibration est choisie avant le test. Ne pas filtrer avec l’AUC de 2026 pour
acheter en 2021. Un score de 0,60 n’est pas un taux gagnant garanti de 60 %.

### Anti-SL — événement de la première séance seulement

Étiquette 1 si le low de la séance d’entrée atteint le SL5 arrondi au centime,
calculé depuis son open. Disponibilité conservatrice à **J+2**. Ce modèle ne
prédit ni le SL sur l’ensemble de H10 ni la rentabilité finale. Il peut écarter
des titres qui auraient été gagnants après plusieurs séances.


## 6. Identifiants exacts des modèles annuels

Ces identifiants désignent des archives existantes, pas des noms à réutiliser lors d’un nouvel entraînement.

| Famille | Année d’entrée | Batch Oracle | Début données | Fin données | Variables Oracle | Folds |
| --- | --- | --- | --- | --- | ---: | ---: |
| Q051 | 2021 | `model-factory-20261107222539-837309` | 2014-01-01 | 2020-12-31 | 173 | 8 |
| Q051 | 2022 | `model-factory-20261107222557-280d86` | 2015-01-01 | 2021-12-31 | 173 | 8 |
| Q051 | 2023 | `model-factory-20261107222607-f44095` | 2016-01-01 | 2022-12-31 | 173 | 8 |
| Q051 | 2024 | `model-factory-20261107222618-89a4d2` | 2017-01-01 | 2023-12-31 | 173 | 8 |
| Q051 | 2025 | `model-factory-20261106203103-91b063` | 2018-01-01 | 2024-12-31 | 173 | 8 |
| Q051 | 2026 | `model-factory-20261107222627-db80b0` | 2019-01-01 | 2025-12-31 | 173 | 8 |
| B | 2021 | `model-factory-20261116071351-92ea8f` | 2014-01-01 | 2020-12-31 | 173 | 8 |
| B | 2022 | `model-factory-20261116071351-bf5512` | 2015-01-01 | 2021-12-31 | 173 | 8 |
| B | 2023 | `model-factory-20261116071351-429e45` | 2016-01-01 | 2022-12-31 | 173 | 8 |
| B | 2024 | `model-factory-20261116071351-21a7ec` | 2017-01-01 | 2023-12-31 | 173 | 8 |
| B | 2025 | `model-factory-20261116071351-c589d4` | 2018-01-01 | 2024-12-31 | 173 | 8 |
| B | 2026 | `model-factory-20261116071351-4e1392` | 2019-01-01 | 2025-12-31 | 173 | 8 |

## 7. Entraîner et choisir les poids sans anticiper le test

### 7.1. Séparer données admissibles et date physique d’entraînement

Pour le test 2024, le batch annuel s’arrête au 31/12/2023 ; pour 2025,
au 31/12/2024, etc. Les fichiers ont été créés en novembre 2026 : c’est une
reconstruction historique, pas une preuve que le système existait en 2021.
Les chiffres ne constituent pas un nouveau holdout indépendant : les périodes
et paramètres ont déjà été étudiés.

### 7.2. Oracle : expert/173 variables et comparaison des backends

Pipeline de features expert, SPY, facteurs et variables directionnelles selon
`generator_options` et `feature_profile.json`. Les rangs transversaux sont
calculés sur **tout l’univers d’entraînement**, pas sur un mini-lot de 25 titres
ou sur le TOP179 déjà choisi. Leur ordre exact apparaît en section 14.
Les news/sentiments, fondamentaux, consensus et CALL/PUT n’alimentent pas ces
modèles de référence. Certains champs de prix/volume existent dans expert
même si un interrupteur additionnel `include_volume_features` est faux.

Walk-forward activé : minimum train 504 dates, validation 126, test 126,
pas 126, maximum 15 splits dans la configuration de base. Les vrais nombres
et dates retenus après adaptation/purge sont ceux de `folds_oracle.csv`.
Les labels train et validation doivent être mûrs avant leurs frontières.

LightGBM : binaire/AUC, profondeur 5, au plus 15 feuilles, 200 tours,
learning rate 0,03, min_child_samples 150, L1 0,1, L2 0,1,
subsample 0,8, colonnes 0,7 ; early stopping configuré à 30.
CatBoost : profondeur 4, 300 itérations, learning rate 0,03, L2 3,
border_count 128, random_strength 1, bagging_temperature 1, détecteur
`IncToDec`, od_wait 20. La graine est 42, backend CPU auto.

Chaque fold choisit le champion par **AUC de validation**, égalité exacte
en faveur de LightGBM. CatBoost utilise effectivement **Logloss**, même si
un champ partagé `catboost_loss_function=YetiRank` est stocké dans l’ancienne
configuration générale. De même, `target_mode=regression`, les paramètres
LSTM/epochs/sequence ou `forecast_horizons=3,5,10,15,20` ne changent pas
l’Oracle parcours sélectionné : le contrat spécifique fixe **H10/binaire**.

Pour prévoir à une date D, choisir le dernier fold dont le début est ≤D
et dont `train_available_max` et `val_available_max` sont **strictement <D**.
Sans fold causal, refuser la date ; ne pas utiliser le dernier champion futur.
La couverture de label figée historique est généralement 95 % ; le garde de
prédiction/replay a ensuite été configuré à 93 %. Ces seuils n’ont pas le même
rôle. Ne pas remplacer les titres manquants par des probabilités artificielles.

### 7.3. LONG classique — 24 variables par titre

Modèles annuels LightGBM binaires **par symbole et par côté**, et non un seul
classifieur global. Les branches SHORT archivées ne servent pas aux achats.

Pour un modèle d’année Y : fit sur les signaux de date <1er janvier Y−1,
labels disponibles <cette même borne ; calibration sur l’année Y−1, labels
disponibles <1er janvier Y. Minimum fit 756 lignes et calibration 126 ;
au moins 40 de chaque classe en fit et 15 en calibration. Sinon abstention.
Une probabilité constante en calibration est également refusée.

Le panel compact de référence exige notamment 60 séances récentes de barres
qualifiées et au moins 80 % de ses 24 entrées disponibles. Les trois deltas
sur cinq séances exigent six observations consécutives. L’absence n’est pas
remplie depuis le futur. Le panel commun T0/B de recherche ajoute la
qualification des variables B, identique pour les deux branches comparées.

Winsorisation par colonne aux percentiles 1 %/99 % **du fit seulement**,
infinis remplacés par manquants, imputation médiane ajustée sur le fit.
LightGBM : 120 arbres, profondeur 3, 7 feuilles, learning rate 0,03,
min_child_samples 60, L1 1, L2 10, n_jobs 1, seed 42.
Calibration Platt : régression logistique `C=1` sur le logit des probabilités
LightGBM bornées à [1e−6,1−1e−6], fit sur la seule calibration.

Le modèle peut porter une année différente de l’année d’entrée, en particulier
pour le signal du 31 décembre précédant janvier : ne pas choisir un poids
avant sa date `available`. Les fenêtres exactes par titre sont dans le CSV
annexe ; les modèles 2020/2021, par exemple, ne sont pas interchangeables.

### 7.4. T0 apparié et B — recherche à observations communes

Le générateur `us_q051_feature_groups_20261116.py` calcule un panel commun
qualifié à partir des snapshots de la campagne 173. Il refait les poids LONG
**T0/24** et **B/29** avec les mêmes lignes, critères d’éligibilité, split,
hyperparamètres et calibration. Les signes ne sont pas inversés après résultat.

Les cinq ajouts B sont `rolling_volatility_60`, `rolling_volatility_120`,
`rolling_volatility_20_zscore`, `rolling_volatility_60_zscore`,
`rolling_volatility_120_zscore`. Ce sont des variables de titre et de contexte
de volatilité inhabituelle ; **ce n’est pas le budget de volatilité vol20 du
portefeuille**. Les formules sont figées par `modelFactory/factor_features.py`
et les panels archivés, pas remplacées par une nouvelle définition du z-score.

Les poids sont entraînés pour les symboles qui apparaissent dans le pool
Oracle annuel, sans sélectionner selon leur rendement futur. C’est un cache
paresseux de calculs par titre ; cela n’autorise pas à limiter l’historique
d’apprentissage aux seuls jours de futurs trades gagnants.

### 7.5. Tête anti-SL SL10 — 44 variables, modèle commun

Le modèle anti-SL SL10 est **commun aux titres**, entraîné sur les anciens
candidats Oracle TOP179 dont les scores Oracle sont causaux OOF. Ne pas
entraîner sur un pool choisi avec l’Oracle futur final. `oracle-oof-causality.json`
contrôle cette provenance.

Entrées : les 29 B, plus pour chacune de cinq séries (`return_5d`, `rsi_14`,
`vol_ratio_20_60`, `range_position_20`, `rolling_volatility_20_zscore`) :
différence J−(J−9), pente OLS sur exactement dix séances, écart-type sur
exactement dix séances. Cela donne **29+5×3=44**, pas 290 données empilées.
Les fenêtres manquantes restent manquantes, puis sont imputées selon le fit.
Dans le générateur de cette recherche, la pente est celle de l’OLS avec
abscisses −4,5..+4,5 et l’écart-type glissant utilise `ddof=1` (pandas).

Même split temporel fit/calibration que ci-dessus, maturité J+2 pour l’événement.
Minimum 2 000 fit / 500 calibration, classes au moins 30/10 respectivement.
LightGBM et Platt identiques aux réglages compacts. À la fin de la calibration,
fixer le seuil au **percentile 90 des risques calibrés**. À la prédiction,
exclure si risque **strictement supérieur** au seuil. Pas de recherche du meilleur
percentile sur l’année testée. Si le modèle/score est inconnu, **garder B** dans
ce protocole de recherche, sans appeler l’inconnu un « non-SL ».

Le veto intervient après le TOP10 LONG, **sans remplacement**. La fenêtre de dix
séances est passée ; ce n’est pas l’horizon de l’étiquette anti-SL. Des réserves
sur des prix et un label de première séance sont conservées dans le bilan.

### 7.6. Réentraînement natif actuel et reproduction historique

Dans Pipeline T1, choisir Oracle parcours H10 + bundle par titre LONG/SHORT.
Pour Q051 compact, désactiver B et anti-SL ; pour un nouveau B, activer
« Volatilité inhabituelle » ; pour un nouveau B + anti-SL, ajouter son option.
Ne pas activer Global Ranking ni utiliser un modèle H20 pour ces références.
Les seuils de sélection et le TOP final sont des réglages de prédiction/replay,
pas une raison de refaire un modèle pour chaque TOP5/TOP10.

Ces cases natives produisent un **nouvel essai cohérent**, pas nécessairement
les mêmes poids que T0/B de recherche. Pour une identité historique, utiliser
les fit/calibration et fichiers de recherche ci-dessus, ainsi que les snapshots
et sources dont les empreintes sont annexées.


### 7.7. Paramètres Oracle archivés — famille Q051, année 2021

Les autres années et l’intégralité des champs figurent dans l’annexe JSON. Cette extraction distingue la configuration stockée du traitement effectivement utilisé décrit ci-dessus.

```json
{
  "data": {
    "sequence_length": 40,
    "forecast_horizon": 20,
    "forecast_horizons": [
      3,
      5,
      10,
      15,
      20
    ],
    "min_history_days": 504,
    "train_ratio": 0.7,
    "val_ratio": 0.15,
    "include_sentiment_features": false,
    "include_screener_scores": false,
    "include_short_score_features": true,
    "include_macro_vix_features": false,
    "include_macro_vxn_features": false,
    "include_macro_vix3m_features": false,
    "include_macro_move_features": false,
    "include_fundamentals_features": false,
    "include_factors_features": true,
    "include_macro_regime_features": false,
    "include_score_components": false,
    "include_volume_features": false,
    "feature_whitelist_enabled": false,
    "feature_whitelist": [],
    "force_v1_lstm": false,
    "global_model_only": false,
    "exclude_per_symbol_per_sector": false,
    "enable_oracle_model": false,
    "oracle_model_only": false,
    "oracle_path_model_only": true,
    "oracle_barrier_model_only": false,
    "sector_use_symbol_feature": true,
    "enable_cross_sectional_features": false,
    "include_directional_features": true,
    "cross_sectional_min_universe": 20,
    "feature_set": "expert",
    "benchmark_symbol": "SPY",
    "target_mode": "regression",
    "label_method": "fixed_horizon",
    "target_up_threshold": 0.03,
    "target_down_threshold": -0.03,
    "triple_barrier_stop_atr_mult": 2.0,
    "triple_barrier_tp_atr_mult": 3.0,
    "triple_barrier_max_sessions": 20,
    "target_skip_vol_scaling": false,
    "target_excess_vs_spy": true,
    "target_intra_sector_rank": false,
    "target_ternary_intra_sector": false,
    "target_ternary_quantile": 0.3,
    "decision_threshold": 0.55,
    "training_start_date": "2014-01-01",
    "training_end_date": "2020-12-31",
    "enable_liquidity_filter": false,
    "liquidity_min_avg_volume_20d": 500000,
    "liquidity_min_market_cap": 500000000.0,
    "liquidity_max_market_cap": 0.0,
    "liquidity_max_avg_high_low_range_pct": 5.0,
    "liquidity_min_daily_dollar_volume": 0.0,
    "liquidity_min_price": 0.0,
    "liquidity_max_spread_bps": 40.0,
    "liquidity_spread_fallback_mode": "pass",
    "liquidity_spread_max_quote_age_days": 5,
    "global_ranking_max_symbols": 0,
    "global_ranking_selection_stratified": false,
    "per_symbol_max_symbols": 0,
    "per_symbol_selection_stratified": false,
    "exclude_ticket_symbols": false
  },
  "baseline": {
    "enabled": true,
    "enable_catboost": true,
    "model_name": "lightgbm",
    "max_depth": 5,
    "n_estimators": 200,
    "learning_rate": 0.03,
    "lgbm_early_stopping_rounds": 30,
    "catboost_depth": 4,
    "catboost_iterations": 300,
    "catboost_learning_rate": 0.03,
    "random_state": 42,
    "lgbm_reg_alpha": 0.1,
    "lgbm_reg_lambda": 0.1,
    "lgbm_min_child_samples": 150,
    "lgbm_num_leaves": 15,
    "lgbm_subsample": 0.8,
    "lgbm_colsample_bytree": 0.7,
    "catboost_l2_leaf_reg": 3.0,
    "catboost_border_count": 128,
    "catboost_random_strength": 1.0,
    "catboost_bagging_temperature": 1.0,
    "catboost_od_type": "IncToDec",
    "catboost_od_wait": 20,
    "catboost_loss_function": "YetiRank",
    "ranking_top_k_features": 0
  },
  "calibration": {
    "method": "platt",
    "min_samples": 64,
    "max_iter": 100
  },
  "walk_forward": {
    "enabled": true,
    "min_train_size": 504,
    "val_size": 126,
    "test_size": 126,
    "step_size": 126,
    "max_splits": 15
  },
  "reproducibility": {
    "seed": 42,
    "deterministic": true
  }
}
```


### 7.8. Paramètres Oracle archivés — famille B, année 2021

Les autres années et l’intégralité des champs figurent dans l’annexe JSON. Cette extraction distingue la configuration stockée du traitement effectivement utilisé décrit ci-dessus.

```json
{
  "data": {
    "sequence_length": 40,
    "forecast_horizon": 20,
    "forecast_horizons": [
      3,
      5,
      10,
      15,
      20
    ],
    "min_history_days": 504,
    "train_ratio": 0.7,
    "val_ratio": 0.15,
    "include_sentiment_features": false,
    "include_screener_scores": false,
    "include_short_score_features": true,
    "include_macro_vix_features": false,
    "include_macro_vxn_features": false,
    "include_macro_vix3m_features": false,
    "include_macro_move_features": false,
    "include_fundamentals_features": false,
    "include_factors_features": true,
    "include_macro_regime_features": false,
    "include_score_components": false,
    "include_volume_features": false,
    "feature_whitelist_enabled": false,
    "feature_whitelist": [],
    "force_v1_lstm": false,
    "global_model_only": false,
    "exclude_per_symbol_per_sector": false,
    "enable_oracle_model": false,
    "oracle_model_only": false,
    "oracle_path_model_only": true,
    "oracle_barrier_model_only": false,
    "sector_use_symbol_feature": true,
    "enable_cross_sectional_features": false,
    "include_directional_features": true,
    "cross_sectional_min_universe": 20,
    "feature_set": "expert",
    "benchmark_symbol": "SPY",
    "target_mode": "regression",
    "label_method": "fixed_horizon",
    "target_up_threshold": 0.03,
    "target_down_threshold": -0.03,
    "triple_barrier_stop_atr_mult": 2.0,
    "triple_barrier_tp_atr_mult": 3.0,
    "triple_barrier_max_sessions": 20,
    "target_skip_vol_scaling": false,
    "target_excess_vs_spy": true,
    "target_intra_sector_rank": false,
    "target_ternary_intra_sector": false,
    "target_ternary_quantile": 0.3,
    "decision_threshold": 0.55,
    "training_start_date": "2014-01-01",
    "training_end_date": "2020-12-31",
    "enable_liquidity_filter": false,
    "liquidity_min_avg_volume_20d": 500000,
    "liquidity_min_market_cap": 500000000.0,
    "liquidity_max_market_cap": 0.0,
    "liquidity_max_avg_high_low_range_pct": 5.0,
    "liquidity_min_daily_dollar_volume": 0.0,
    "liquidity_min_price": 0.0,
    "liquidity_max_spread_bps": 40.0,
    "liquidity_spread_fallback_mode": "pass",
    "liquidity_spread_max_quote_age_days": 5,
    "global_ranking_max_symbols": 0,
    "global_ranking_selection_stratified": false,
    "per_symbol_max_symbols": 0,
    "per_symbol_selection_stratified": false,
    "exclude_ticket_symbols": false
  },
  "baseline": {
    "enabled": true,
    "enable_catboost": true,
    "model_name": "lightgbm",
    "max_depth": 5,
    "n_estimators": 200,
    "learning_rate": 0.03,
    "lgbm_early_stopping_rounds": 30,
    "catboost_depth": 4,
    "catboost_iterations": 300,
    "catboost_learning_rate": 0.03,
    "random_state": 42,
    "lgbm_reg_alpha": 0.1,
    "lgbm_reg_lambda": 0.1,
    "lgbm_min_child_samples": 150,
    "lgbm_num_leaves": 15,
    "lgbm_subsample": 0.8,
    "lgbm_colsample_bytree": 0.7,
    "catboost_l2_leaf_reg": 3.0,
    "catboost_border_count": 128,
    "catboost_random_strength": 1.0,
    "catboost_bagging_temperature": 1.0,
    "catboost_od_type": "IncToDec",
    "catboost_od_wait": 20,
    "catboost_loss_function": "YetiRank",
    "ranking_top_k_features": 0
  },
  "calibration": {
    "method": "platt",
    "min_samples": 64,
    "max_iter": 100
  },
  "walk_forward": {
    "enabled": true,
    "min_train_size": 504,
    "val_size": 126,
    "test_size": 126,
    "step_size": 126,
    "max_splits": 15
  },
  "reproducibility": {
    "seed": 42,
    "deterministic": true
  }
}
```


## 8. Variantes de gestion et d’entrée

### Volatilité 20 % + régime SPY

Deux mécanismes indépendants, ajoutés ensemble dans les deux courbes :

1. **Régime** : à la clôture J, `SPY(J) > 0,98 × SMA200(J)`, calculée avec
   200 clôtures positives qualifiées connues, sinon pas de nouvel achat J+1.
2. **Budget portefeuille** : covariance des 60 dernières séances connues
   avant l’entrée, annualisation 252. Partir de la quantité native, estimer
   le risque du portefeuille détenu + ordres en attente + candidat, résoudre
   la quantité admissible sous la cible annualisée 20 %, puis refaire le
   contrôle natif sur la taille réduite. La quantité ne peut pas augmenter.

Ne pas remplacer cela par une réduction selon la volatilité individuelle seule.
L’objectif 20 % n’est ni un DD garanti de 20 %, ni une liquidation quotidienne
du portefeuille. Les positions détenues conservent SL5/open11. Le paramétrage
est identique entre TOP5 et TOP10 ; les covariances et le capital changent
parce que les positions admises diffèrent.

### Plafond avec attente de deux séances

Base **Q051 classique TOP10**, pas B. Après la clôture J :

`plafond = close(J) + 0,5 × ATR20(J)`

ATR20 est ici la **moyenne simple des vingt true ranges**, avec vingt et une
séances valides. Il n’est pas substituable à Wilder/EMA ni à un ATR en %.

- Open J+1 ≤ plafond : achat selon les contrôles et tailles natifs.
- Sinon, attendre au plus J+1 et J+2 ; premier **open observé 5m** ≤ plafond,
  ou open journalier J+2 ≤ plafond, admissible. Pas d’achat sur le seul low.
- À la clôture J+2, expiration. Un nouveau signal du même titre remplace
  l’ancien plan non exécuté ; un refus de risque n’est pas retenté.
- Signal/rang d’origine conservés dans les événements ; aucune promotion
  d’un nouveau titre extérieur au TOP10 d’origine.
- Dix séances de détention depuis l’entrée effective, puis open11.

Le niveau était connu à J : cette règle n’utilise pas une confirmation de
deux bougies retardées. Elle suppose des fills aux opens observés ; elle ne
certifie pas une exécution réelle sans spread/slippage. Les entrées tardives
requièrent un jour 5m complet et compatible, qualification de couverture connue
ex post : cette réserve technique doit rester dans toute comparaison.

Le résultat +364,84 %/DD−46,26 % n’est pas une amélioration sur les deux axes.
2022 passe de −2,13 % à −21,75 %. Seulement 28 achats sont différés, dont trois
durant J+2 : le changement de capital et de disponibilités amplifie ensuite
les différences. Ne pas attribuer tout le rendement aux seuls trades retardés.

### SPY

Acheter/conserver SPY sur la même période, sans levier, dividendes ou frais.
Nombre d’unités théorique fractionnaire = `4000 / première ouverture SPY`.
Capital quotidien = unités × close SPY. Les 4 000 USD au 01/01 sont un repère,
pas un fill un jour férié. Aucun Oracle, per-symbol, anti-SL, SL5 ou open11.

## 9. Fiches individuelles : quelles règles charger pour chaque courbe ?

Les huit fiches suivantes renvoient à une configuration complète distincte,
même lorsque l’essentiel du portefeuille est commun. La neuvième, SPY,
est décrite ci-dessus. Choisir/cocher une courbe dans la popin n’exécute rien.


### Fiche Q051_TOP5 — Q051 témoin — TOP5

- Famille Oracle : **Q051**, TOP179 ; TOP LONG : **5**, puis score >0,50/AUC ≥0,50.
- Vol20 + régime : **non**. Anti-SL : **non**.
- Archive économique : `artifacts/research/us_winner_continuous_q051_q088/20261108-v2/cases/Q051_050/result`.
- Capital final : **12 260,32 USD** ; rendement **206,51 %** ; DD **-36,89 %**.
- Clôtures : **1234** ; gagnants **35,01 %**.
- Engagement brut moyen : **5 461,32 USD**, soit **83,43 %** du capital courant en moyenne.
- Configuration intégrale : clé `cases.Q051_TOP5.configuration` de `contrats_et_configurations.json`.
- Vérification des sorties : `cases.Q051_TOP5.files` contient chemins et SHA-256.


### Fiche Q051_VOL20_TOP5 — Volatilité 20 % + régime — TOP5

- Famille Oracle : **Q051**, TOP179 ; TOP LONG : **5**, puis score >0,50/AUC ≥0,50.
- Vol20 + régime : **oui**. Anti-SL : **non**.
- Archive économique : `artifacts/research/us_winner_q051_risk_budget/20261109-v1/REGIME_VOL20/result`.
- Capital final : **9 039,00 USD** ; rendement **125,98 %** ; DD **-24,29 %**.
- Clôtures : **940** ; gagnants **36,17 %**.
- Engagement brut moyen : **2 396,13 USD**, soit **44,76 %** du capital courant en moyenne.
- Configuration intégrale : clé `cases.Q051_VOL20_TOP5.configuration` de `contrats_et_configurations.json`.
- Vérification des sorties : `cases.Q051_VOL20_TOP5.files` contient chemins et SHA-256.


### Fiche Q051_VOL20_TOP10 — Volatilité 20 % + régime — TOP10

- Famille Oracle : **Q051**, TOP179 ; TOP LONG : **10**, puis score >0,50/AUC ≥0,50.
- Vol20 + régime : **oui**. Anti-SL : **non**.
- Archive économique : `artifacts/research/us_q051_selection_variants/20261115-v1/cases/TOP10_SCORE050/result`.
- Capital final : **10 035,92 USD** ; rendement **150,90 %** ; DD **-17,58 %**.
- Clôtures : **1112** ; gagnants **36,33 %**.
- Engagement brut moyen : **2 532,37 USD**, soit **45,67 %** du capital courant en moyenne.
- Configuration intégrale : clé `cases.Q051_VOL20_TOP10.configuration` de `contrats_et_configurations.json`.
- Vérification des sorties : `cases.Q051_VOL20_TOP10.files` contient chemins et SHA-256.


### Fiche Q051_TOP10 — Q051 témoin — TOP10

- Famille Oracle : **Q051**, TOP179 ; TOP LONG : **10**, puis score >0,50/AUC ≥0,50.
- Vol20 + régime : **non**. Anti-SL : **non**.
- Archive économique : `artifacts/research/us_q051_classic_top10/20261115-v1/cases/TOP10/result`.
- Capital final : **15 237,79 USD** ; rendement **280,94 %** ; DD **-40,45 %**.
- Clôtures : **1471** ; gagnants **35,62 %**.
- Engagement brut moyen : **7 187,51 USD**, soit **88,72 %** du capital courant en moyenne.
- Configuration intégrale : clé `cases.Q051_TOP10.configuration` de `contrats_et_configurations.json`.
- Vérification des sorties : `cases.Q051_TOP10.files` contient chemins et SHA-256.


### Fiche B_CONTROL_T0 — Témoin B — 24 variables, mêmes Oracle

- Famille Oracle : **B**, TOP179 ; TOP LONG : **10**, puis score >0,50/AUC ≥0,50.
- Vol20 + régime : **non**. Anti-SL : **non**.
- Archive économique : `artifacts/research/us_q051_feature_groups/20261116-lot1/variants/T0/cases/T0_SIMPLE/result`.
- Capital final : **9 162,34 USD** ; rendement **129,06 %** ; DD **-39,12 %**.
- Clôtures : **1420** ; gagnants **34,23 %**.
- Engagement brut moyen : **5 475,08 USD**, soit **88,14 %** du capital courant en moyenne.
- Configuration intégrale : clé `cases.B_CONTROL_T0.configuration` de `contrats_et_configurations.json`.
- Vérification des sorties : `cases.B_CONTROL_T0.files` contient chemins et SHA-256.


### Fiche B_TOP10 — B seul — 29 variables, TOP10

- Famille Oracle : **B**, TOP179 ; TOP LONG : **10**, puis score >0,50/AUC ≥0,50.
- Vol20 + régime : **non**. Anti-SL : **non**.
- Archive économique : `artifacts/research/us_q051_feature_groups/20261116-lot1/variants/B/cases/B_SIMPLE/result`.
- Capital final : **15 894,14 USD** ; rendement **297,35 %** ; DD **-40,99 %**.
- Clôtures : **1419** ; gagnants **37,63 %**.
- Engagement brut moyen : **6 401,43 USD**, soit **87,63 %** du capital courant en moyenne.
- Configuration intégrale : clé `cases.B_TOP10.configuration` de `contrats_et_configurations.json`.
- Vérification des sorties : `cases.B_TOP10.files` contient chemins et SHA-256.


### Fiche B_ANTI_SL — B + anti-SL témoin — TOP10

- Famille Oracle : **B**, TOP179 ; TOP LONG : **10**, puis score >0,50/AUC ≥0,50.
- Vol20 + régime : **non**. Anti-SL : **oui**.
- Archive économique : `artifacts/research/us_q051_b_early_sl/20261116-v1/cases/SL10/result`.
- Capital final : **16 140,82 USD** ; rendement **303,52 %** ; DD **-34,98 %**.
- Clôtures : **1356** ; gagnants **38,13 %**.
- Engagement brut moyen : **7 069,05 USD**, soit **84,57 %** du capital courant en moyenne.
- Configuration intégrale : clé `cases.B_ANTI_SL.configuration` de `contrats_et_configurations.json`.
- Vérification des sorties : `cases.B_ANTI_SL.files` contient chemins et SHA-256.


### Fiche Q051_CEILING_WAIT2 — Q051 témoin TOP10 — plafond, attente deux séances

- Famille Oracle : **Q051**, TOP179 ; TOP LONG : **10**, puis score >0,50/AUC ≥0,50.
- Vol20 + régime : **non**. Anti-SL : **non**.
- Archive économique : `artifacts/research/us_q051_entry_ceiling/20261127-v1/cases/CAP_WAIT2/result`.
- Capital final : **18 593,49 USD** ; rendement **364,84 %** ; DD **-46,26 %**.
- Clôtures : **1444** ; gagnants **34,63 %**.
- Engagement brut moyen : **6 842,92 USD**, soit **88,61 %** du capital courant en moyenne.
- Configuration intégrale : clé `cases.Q051_CEILING_WAIT2.configuration` de `contrats_et_configurations.json`.
- Vérification des sorties : `cases.Q051_CEILING_WAIT2.files` contient chemins et SHA-256.


## 10. Recette de reconstruction de A à Z

### A — Installer et isoler la reproduction

1. Restaurer le dépôt et les racines de données/modèles nécessaires, ainsi que
   le calendrier figé et les registres d’identité. Conserver les empreintes.
2. Recréer l’environnement Python depuis le lock/dependencies du projet.
   Les versions présentes lors de cette documentation sont listées plus bas.
3. Préparer une **instance MySQL US de reconstruction séparée** si entraînement
   et prédictions doivent écrire, en conservant le nom de schéma `alpha_trade`
   attendu par les gardes US ; ne pas remplacer ni renommer la base de production.
4. Paramétrer les variables DB de cette base dans un environnement dédié.
   Les étapes documentées n’ont pas besoin de comptes broker ni de clés GPT.
5. Copier les univers annexés dans un répertoire de travail neuf **sous config/**
   (la CLI refuse les fichiers d’univers sous doc/). Les options
   des modèles doivent être rechargées depuis les snapshots, pas depuis des
   presets de capital modifiés depuis novembre 2026.

### B — Refaire les six entraînements annuels classiques

Gabarit CLI pour un **nouvel** batch 2021, à confronter aux contrats JSON
intégraux (la commande n’a pas été exécutée pour rédiger ce guide) :

```powershell
Set-Location F:\projets
$universeDirectory = 'config\univers_batch\reconstruction_q051'
New-Item -ItemType Directory -Path $universeDirectory -Force | Out-Null
if (Test-Path "$universeDirectory\univers_q051.txt") {
  throw 'Univers de reconstruction déjà présent : vérifier son empreinte ou choisir un dossier neuf.'
}
Copy-Item -LiteralPath 'doc\backtesting\reconstruction_q051\univers_q051.txt' `
  -Destination "$universeDirectory\univers_q051.txt"
& .\.venv\Scripts\python.exe -u -m modelFactory `
  --mode train --accelerator auto `
  --symbol-source universe-file:config/univers_batch/reconstruction_q051/univers_q051.txt `
  --artifacts-dir artifacts/reconstruction/models `
  --training-start-date 2014-01-01 --training-end-date 2020-12-31 `
  --feature-set expert --benchmark-symbol SPY --no-force-v1-lstm --oracle-path-model-only `
  --oracle-horizon 10 --oracle-path-directional --oracle-path-directional-features compact `
  --oracle-path-backend auto --include-factors --include-short-score --include-directional-features `
  --no-include-score-components --compare-lightgbm --enable-catboost --select-champion `
  --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 `
  --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 `
  --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 `
  --catboost-depth 4 --catboost-iterations 300 --catboost-learning-rate 0.03 `
  --catboost-l2-leaf-reg 3 --catboost-border-count 128 --catboost-random-strength 1 `
  --catboost-bagging-temperature 1 --catboost-od-type IncToDec --catboost-od-wait 20 `
  --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 `
  --wf-step-size 126 --wf-max-splits 15 --max-workers 6 --seed 42
```

Répéter avec les cinq autres fenêtres du tableau annuel. Les arguments non
mentionnés restent à aligner avec le snapshot complet, notamment la graine 42,
les filtres de données désactivés et les options spécifiques Oracle. Ne pas
réutiliser un ancien batch-id pour écraser ses poids. `max-workers` gère les
ressources, pas le périmètre économique ; éviter de saturer la machine qui exécute
le pipeline quotidien.

Pour restaurer une configuration sans ambiguïté depuis le JSON, le projet
fournit `restore_config(TrainingConfig(), values)` dans
`scripts/research/us_q051_features173_20261116.py`, utilisé par la campagne figée.
Il valide les noms de champs et reconstruit dataclasses/dates/Path. Pour une
nouvelle exécution, ajuster uniquement les **répertoires de sortie et nouveaux
identifiants**, puis charger les barres gelées dans les chunks du nouveau root
avant `train_oracle_path`. `engine=None` n’autorise pas à omettre les données :
les archives préchargées restent obligatoires.

### C — Produire les prédictions nécessaires

Pour des entrées de l’année 2021, prévoir les signaux depuis la dernière
séance 2020 jusqu’à la dernière séance précédant la dernière entrée 2021.
Pour 2026 au 1er octobre, inclure les signaux jusqu’au 30 septembre.
Utiliser les calendriers, pas simplement « 1 janvier → 31 décembre ».

Gabarit de prédiction classique, sur la base de reconstruction et le nouveau batch :

```powershell
& .\.venv\Scripts\python.exe -u -m modelFactory `
  --mode predict --accelerator auto `
  --batch-id NOUVEAU_BATCH_2021 `
  --artifacts-dir artifacts/reconstruction/models/NOUVEAU_BATCH_2021 `
  --symbol-source universe-file:config/univers_batch/reconstruction_q051/univers_q051.txt `
  --training-start-date 2020-12-31 --training-end-date 2021-12-30 `
  --predict-max-date-workers 4
```

Dans ce mode, ces deux bornes désignent la période de prédiction. Il ne
réentraîne pas le modèle sur la période test. Cette commande peut persister
des scores : elle n’est pas à exécuter depuis le backtest SQL en lecture seule.
Vérifier la présence des scores Oracle **et** LONG, leurs dates de disponibilité,
empreintes de poids/profil et couverture. Le replay ne les invente pas.

### D — Refaire la famille B, puis les poids comparatifs

Pour la fidélité à la courbe B, les phases historiques réelles sont :

1. Campagne `us_q051_features173_20261116` : préparation des snapshots et
   nouvelles racines annuelles, entraînement Oracle/173 + branches natives/173.
2. Production des prédictions Oracle par année à partir des features figées,
   avec le dernier fold causal (`us_q051_features173_replay_20261116.py`,
   phase `predict --year ANNEE`, puis `assemble`).
3. Gel/corroboration des prix SIP dans `20261116-v3-sip`. Cette ancienne phase
   a pu appeler Alpaca ; **pour une reproduction exacte, réutiliser les preuves
   déjà présentes**, ne pas substituer un nouveau téléchargement.
4. `us_q051_feature_groups_20261116.py` : panels communs, nouveaux poids
   T0/B, assemblage des rankings puis TOP179 → TOP10 et seuils.
5. `us_q051_feature_groups_replay_20261116.py` : prix communs et replays.

Exemples des points d’entrée existants, pour comprendre l’ordonnancement :

```powershell
# Ces scripts sont datés et visent des racines historiques figées.
# Dans une copie de travail, rediriger leurs ROOT/sorties vers une version neuve.
& .\.venv\Scripts\python.exe -m scripts.research.us_q051_features173_20261116 --phase prepare
& .\.venv\Scripts\python.exe -m scripts.research.us_q051_features173_20261116 --phase train
& .\.venv\Scripts\python.exe -m scripts.research.us_q051_feature_groups_20261116 --phase prepare
& .\.venv\Scripts\python.exe -m scripts.research.us_q051_feature_groups_20261116 --phase worker --key CLE_DE_TASK
# Les clés admissibles sont dans protocol.json → tasks[].key.
```

Les scripts datés ne sont pas une API de réexécution sur n’importe quel dossier :
plusieurs `mkdir(exist_ok=False)` refusent de remplacer une archive. Le script
`--phase all` des groupes traite aussi A et vol20 : ne pas le lancer pour
refaire uniquement B si l’on ne veut pas ces travaux supplémentaires.
Le driver de reprise `us_q051_feature_groups_resume_20261116.py` corrige un
ancien import de ROOT ; il ne remplace pas les poids déjà entraînés et ne
justifie pas de recalibrer après avoir vu les résultats.

### E — Entraîner et appliquer l’anti-SL

`us_q051_b_early_sl_20261116.py` expose `--phase prepare`, `worker --key`,
`head --key ANNEE`, `case --key SL10` et `all`. L’ordre est :

1. Qualifier les Oracle OOF, figer univers, panels historiques et labels.
2. Exécuter les tasks de préparation `worker` ; conserver leurs reçus et
   empreintes de `training.parquet` / `testing.parquet`.
3. Pour chaque année, `head` entraîne les têtes SLJ/SL10 et fige le seuil de
   calibration passé. Le cas affiché utilise **SL10**, pas SLJ ou LONG10.
4. `assemble()` applique le veto à la sélection B figée ; ne jamais choisir
   le seuil en maximisant le rendement 2021–2026.
5. Préparer le marché commun puis `case --key SL10`.
6. Exécuter les contrôles post-run et lire les réserves, sans les supprimer.

Une nouvelle version native peut être entraînée avec `compact_volatility`
et `--oracle-path-anti-sl`. C’est un nouveau bundle utilisable par la chaîne
native ; ce n’est pas le renommage des poids de recherche de novembre.

### F — Rejouer les cas classiques

Points d’entrée et sources exactes :

| Courbe | Driver / entrée historique |
| --- | --- |
| Q051 TOP5 | `us_winner_continuous_q051_q088_20261108.run_case(root, 'Q051_050')` |
| Vol20 + régime TOP5 | `us_winner_q051_risk_budget_20261109.py --output-dir DOSSIER_NEUF` ; variante `REGIME_VOL20` |
| Vol20 + régime TOP10 | `us_q051_selection_variants_20261115.py`, cas `TOP10_SCORE050` |
| Q051 TOP10 | `us_q051_classic_top10_20261115.py`, cas `TOP10` |
| T0 apparié / B | `us_q051_feature_groups_replay_20261116.run_case('T0_SIMPLE' / 'B_SIMPLE')` |
| B + anti-SL | `us_q051_b_early_sl_20261116.py --phase case --key SL10` |
| Plafond + attente | `us_q051_entry_ceiling_20261127.py --phase case --case CAP_WAIT2` |
| SPY | Formule de la section 8 et les prix SPY du même manifeste |

Les drivers de portefeuille utilisent `BacktestEngine`/Winner avec cash et
positions partagés, pas un collage de rendements annuels indépendants.
Ils prennent des signaux et des prix gelés. Les phases de **préparation** de
certains anciens drivers peuvent lire SQL pour compléter une archive, et les
phases d’entraînement/prédiction ont un autre périmètre de droits. Ne pas
confondre cela avec un replay déjà préparé, sans téléchargement ni écriture SQL.

Les interfaces CLI des scripts datés sont leur `--help` et leur bloc `main`.
Vérifier les phases avant exécution ; ne pas supposer qu’ils ont tous `--resume`
ou `--output-dir`. Quand une racine est codée dans un module, utiliser une
copie versionnée ou un adaptateur explicite vers une **nouvelle** racine.

### G — Refaire le plafond en préservant le témoin

Phases réelles du pilote du 27 novembre :

```powershell
& .\.venv\Scripts\python.exe -m scripts.research.us_q051_entry_ceiling_20261127 --phase prepare
& .\.venv\Scripts\python.exe -m scripts.research.us_q051_entry_ceiling_20261127 --phase reference
& .\.venv\Scripts\python.exe -m scripts.research.us_q051_entry_ceiling_20261127 --phase variants
& .\.venv\Scripts\python.exe -m scripts.research.report_q051_entry_ceiling_20261127
```

Ces commandes décrivent une exécution neuve après redirection de ROOT. Elles
ne sont pas à lancer telles quelles pour écraser `20261127-v1`, déjà terminé.
L’exécution réelle a réutilisé le témoin validé du 26 novembre après contrôle
de 96 sources économiques, configuration et signaux identiques ; voir
`baseline-reuse.json` et le passage partiel conservé. Le reporter fournit
des contrôles scalaires et non un nouveau choix des seuils.

L’attente utilise un adaptateur en mémoire de deux points d’entrée du moteur,
sans modifier ses fichiers de production ; **le profil actuel du formulaire
ne suffit pas à activer ce mécanisme expérimental**. Les sources et leur
empreinte font partie de cette recette.

## 11. Utiliser l’IHM sans confondre un replay annuel et le continu

Dans Backtest, choisir Winner, le bon batch, les dates, puis le profil.
Le bouton Réappliquer le profil recharge les réglages du formulaire. L’univers
doit être celui du batch, pas un champ remplacé à la main. Vérifier explicitement
TOP Oracle en %, TOP LONG, score/AUC, entrée daily, SL/horizon, risque et coûts.

**Un seul batch choisi dans l’écran ne remplace pas automatiquement les six
modèles annuels.** Pour reproduire un continu, assembler les sélections de
chaque année avec son batch et conserver le même portefeuille. Un modèle
entraîné fin 2025 utilisé sur 2021 introduit une fuite, même si l’application
permet techniquement un replay diagnostique.

La popin présente des résultats archivés. Cocher une courbe, la masquer ou
afficher les cinq meilleurs rendements n’entraîne aucun modèle, n’achète rien
et ne charge pas automatiquement des poids de recherche.

## 12. Ce qui doit être conservé lors d’un déplacement sur un autre PC

- Les douze racines Oracle et leurs poids, manifests, chunks nécessaires et
  branches réellement utilisées ; les poids T0/B de recherche et les têtes anti-SL.
- Les prix journaliers/5m et preuves SIP qualifiées, les signaux/rankings figés,
  les événements de corporate actions et snapshots de secteurs/calendriers.
- Les scripts et contrats dont les empreintes figurent dans les protocoles,
  l’environnement Python et la configuration du portefeuille de **chaque cas**.
- Les contrôles de validation, les réserves et les rapports complets, pas
  seulement les PNG ou `annual-summary.csv`.

Le ZIP de documentation fourni ici contient des fichiers texte de description,
pas ces données lourdes. Une sauvegarde « exploitation quotidienne US » ne
conserve pas nécessairement tout le passé utile à cette reconstruction de recherche.


## 13. Référence complète du portefeuille Q051 TOP10

Voici la configuration stockée du témoin, pour éviter de perdre les contrôles secondaires. Les règles prioritaires et champs hérités inactifs sont expliqués aux sections 4 et 8. Les sept autres configurations sont conservées intégralement dans l’annexe JSON.

```json
{
  "start_date": "2021-01-01",
  "end_date": "2026-10-01",
  "initial_equity": 4000.0,
  "risk_config": {
    "account_equity": 4000.0,
    "risk_per_trade_pct": 0.0125,
    "atr_window": 20,
    "quote_spread_check_enabled": false,
    "atr_stop_multiple": 2.0,
    "best_horizon": 10,
    "fixed_stop_pct": 0.05,
    "disable_price_take_profit": true,
    "_atr_stop_multiple_map": {
      "3": 1.5,
      "5": 2.0,
      "10": 2.5,
      "15": 3.0,
      "20": 3.5
    },
    "_tp_atr_multiple_map": {
      "3": 2.0,
      "5": 2.5,
      "10": 3.0,
      "15": 3.5,
      "20": 4.0
    },
    "_tp_max_pct_map": {
      "3": 0.03,
      "5": 0.04,
      "10": 0.07,
      "15": 0.1,
      "20": 0.13
    },
    "max_positions": 20,
    "max_long_positions": 20,
    "max_short_positions": 5,
    "max_position_weight": 0.2,
    "max_sector_weight": 0.5,
    "sector_weight_limit_enabled": false,
    "max_gross_exposure": 1.0,
    "max_long_exposure": null,
    "max_short_exposure": null,
    "min_position_notional": 50.0,
    "sizing_mode": "atr",
    "sector_multipliers_path": null,
    "sizing_min_weight_pct": 0.005,
    "sizing_max_weight_pct": 0.2,
    "max_portfolio_drawdown_pct": 0.15,
    "max_daily_loss_pct": 0.03,
    "degraded_entry_allocation_pct": 0.06,
    "rolling_peak_window_days": 252,
    "recovery_pct": 0.92,
    "regime_ramp_up_enabled": true,
    "regime_ramp_up_pct_per_day": 0.06,
    "regime_ramp_up_max_pct": 0.25,
    "regime_ramp_up_peak_window_days": 5,
    "policy": "b4",
    "spy_regime_map": null,
    "concentration_max_trades_per_symbol": 10,
    "concentration_window_calendar_days": 90,
    "concentration_max_consecutive_losses": 3,
    "concentration_blacklist_duration_days": 90,
    "min_breakout_days": 1,
    "min_score_threshold": 0.4,
    "min_score_veto_long": 0.4,
    "max_score_veto_short": 0.15,
    "min_proba_long": 0.0,
    "min_proba_short": 0.0,
    "force_close_on_breaker": false,
    "force_close_pct": 0.5,
    "short_selling_enabled": true,
    "short_min_score": 0,
    "short_rotation_required": true,
    "short_tp_pct": 0.08,
    "short_trailing_pct": 0.1,
    "short_time_stop_days": 20,
    "min_score_threshold_short": 0.15,
    "filter_unmodeled_selections": false,
    "close_longs_on_defensive_regime": true,
    "short_require_bearish_benchmark": true,
    "target_annual_vol": null,
    "vol_target_lookback_days": 60,
    "dry_run": false,
    "correlation_threshold": 0.9,
    "correlation_check_enabled": false,
    "correlation_lookback_days": 40,
    "correlation_min_overlap": 25,
    "enable_factor_model": false,
    "use_factor_correlation_filter": true,
    "factor_correlation_threshold": 0.7,
    "max_portfolio_beta": 5.0,
    "beta_exposure_basis": "account_equity",
    "max_factor_concentration_pct": 0.6,
    "market_factor_concentration_check_enabled": false,
    "min_factor_diversification": 2,
    "factor_diversification_check_enabled": false,
    "factor_diversification_small_account_threshold": 100000.0,
    "factor_diversification_small_account_min": 1,
    "factor_ewma_half_life": 60,
    "factor_lookback_days": 252,
    "enable_kelly_sizing": false,
    "assumed_payoff_ratio": 1.5,
    "kelly_fraction_multiplier": 0.25,
    "max_kelly_fraction": 0.25,
    "min_effective_probability": 0.52,
    "default_win_rate": 0.55,
    "score_weight": 0.4,
    "prediction_weight": 0.6,
    "prediction_confidence_weight": 0.6,
    "historical_win_rate_weight": 0.4,
    "risk_multiplier": 1.0,
    "enforce_min_notional": null,
    "effective_max_positions_override": null,
    "max_tickers_per_sector": null,
    "sector_ticker_limit_enabled": false,
    "allow_fractional_shares": false,
    "sector_cap_mode": "count",
    "sector_exposure_cap_pct": 0.2,
    "sector_corr_threshold": 0.4,
    "sector_corr_map": null,
    "max_position_pct_of_adv": null,
    "enforce_net_exposure": false,
    "net_exposure_target": 0.0,
    "net_exposure_tolerance": 0.1,
    "max_long_short_correlation": null
  },
  "winner_global_drawdown_halt": false,
  "winner_hard_drawdown_pct": null,
  "winner_cycle_drawdown_pct": null,
  "winner_drawdown_cooldown_months": 0,
  "winner_drawdown_controller_enabled": false,
  "winner_daily_entry_enabled": true,
  "exec_config": {
    "market_code": "US_EQ",
    "broker_mode": "paper",
    "dry_run": true,
    "account_id": null,
    "execution_profile": "overnight_cash_swing",
    "submission_window": "both",
    "account_type": "margin",
    "swing_only": true,
    "cash_settlement_days": 1,
    "simulated_account_equity": 4000.0,
    "simulated_margin_buying_power_multiplier": 2.0,
    "entry_order_type": "market",
    "limit_price_buffer_bps": 10,
    "max_entry_gap_pct": 0.0,
    "profit_taker_pct": 0.12,
    "trailing_stop_pct": 0.1,
    "manual_buy_stop_loss_pct": 0.05,
    "trailing_stop_type": "percent",
    "enable_dynamic_trailing_transition": true,
    "trailing_activation_trigger": "multiple_r",
    "trailing_activation_r_multiple": 0.0,
    "trailing_activation_profit_pct": 0.03,
    "trailing_pct_override": null,
    "trailing_pct_long_override": 0.07,
    "trailing_pct_short_override": null,
    "tp_anchor_entry": false,
    "sl_anchor_entry": false,
    "llm_protection_profile": null,
    "protection_transition_timeout_seconds": 0,
    "protection_transition_poll_interval_seconds": 2.0,
    "allow_fractional_shares": false,
    "allow_fractional_live_protections": false,
    "fractional_live_mode": "entry_only",
    "max_slippage_bps": 30,
    "max_order_retries": 3,
    "retry_base_delay_seconds": 1.0,
    "inter_order_delay_ms": 350,
    "poll_interval_seconds": 2.0,
    "fill_timeout_seconds": 180,
    "cancel_timeout_seconds": 30,
    "market_clock_skew_seconds": 5,
    "allow_outside_rth": false,
    "market_calendar_name": "NYSE",
    "enable_kill_switch": true,
    "max_consecutive_failures": 3,
    "execution_batch_size": 20,
    "reconcile_after_submit": true,
    "reconcile_tolerance_shares": 0.0,
    "reconcile_tolerance_epsilon": 1e-09,
    "auto_rebalance_on_reconcile": false,
    "force_close_on_protection_breach": true,
    "enable_tca": true,
    "entry_mode": "normal",
    "regime_max_positions": null,
    "regime_max_position_weight": null,
    "regime_max_sector_weight": null,
    "regime_max_gross_exposure": null,
    "force_close_on_breaker": false,
    "force_close_pct": 0.5,
    "leverage": {
      "enabled": true,
      "mode": "regt_swing",
      "max_leverage": 2.0,
      "min_equity_usd": 2000.0,
      "require_margin_account": true,
      "only_in_entry_mode": "normal",
      "disable_in_capital_preservation": true,
      "disable_if_buying_power_field_missing": false,
      "buying_power_field_priority": [
        "regt_buying_power",
        "buying_power"
      ],
      "dry_run_simulated_leverage": 2.0,
      "audit_log": true
    },
    "trailing_stop": {
      "enabled": false,
      "mode": "fixed",
      "atr_period": 14,
      "atr_multiplier": 2.5,
      "fallback_fixed_pct": 5.0,
      "break_even_after_atr_multiple": 2.0,
      "eod_check_time_est": "15:50",
      "apply_to_manual_orphan_buys": true
    },
    "time_stop": {
      "enabled": false,
      "max_business_days": 20,
      "min_tp_progress_ratio": 0.5,
      "near_zero_return_pct": 0.005
    },
    "winner_pyramiding": {
      "enabled": true,
      "initial_position_fraction": 1.0,
      "reinforcement_enabled": false,
      "reinforcement_trigger_pct": 0.05,
      "confirmation_bars": 0,
      "standard_entry_quote_check_enabled": false,
      "stop_loss_pct": 0.05,
      "take_profit_pct": null,
      "trailing_stop_pct": null,
      "horizon_sessions": 10,
      "entry_valid_sessions": 1,
      "max_quote_age_seconds": 60,
      "max_bar_delay_seconds": 60,
      "market_data_delay_seconds": 0,
      "delayed_entry_limit_buffer_pct": 0.01,
      "cost_reserve_bps_per_leg": 25
    },
    "paper_strategy_profile": null
  },
  "profit_taker_pct": 0.12,
  "trailing_stop_pct": 0.1,
  "use_live_protection_logic": true,
  "time_stop_enabled": false,
  "time_stop_max_business_days": 20,
  "time_stop_min_tp_progress_ratio": 0.5,
  "time_stop_near_zero_return_pct": 0.005,
  "max_positions": 20,
  "fees_pct": 0.001,
  "commission_bps": 5.0,
  "slippage_bps": 5.0,
  "use_tiered_commission": false,
  "trading_cost_model": null,
  "use_canonical_costs": true,
  "margin_interest_rate_annual": 0.065,
  "cost_multiplier": 1.0,
  "cost_round_trip_bps": 16.0,
  "fallback_spread_bps": null,
  "trading_constraints": {
    "account_type": "margin",
    "swing_only": false,
    "cash_settlement_days": 1
  },
  "execution_timing": "next_open",
  "execution_replay_mode": "off",
  "protection_replay_mode": "off",
  "watcher_replay_mode": "off",
  "exit_lifecycle_replay_mode": "off",
  "research_sizing": false,
  "require_replay_quantities": false,
  "reject_constrained_replay_entries": false,
  "require_replay_protections": false,
  "exposure_multiplier": 1.0,
  "microstructure": {
    "slippage": {
      "base_bps": 0.0,
      "impact_coef": 0.0,
      "model": "fixed"
    },
    "initial_stop_pct": 0.0,
    "max_entry_gap_pct": 0.0,
    "intrabar_priority": "conservative",
    "execution_model": {
      "model": "next_open",
      "split_threshold_adv_pct": 0.0,
      "split_slices": 5,
      "arrival_slippage_factor": 0.5
    }
  },
  "risk_overlay": {
    "sizing": {
      "mode": "equal_weight",
      "min_weight_pct": 0.005,
      "max_weight_pct": 0.2,
      "sector_multipliers": null,
      "sector_map": null
    },
    "regime_filter": {
      "enabled": false,
      "sma_window": 200,
      "bear_threshold": -0.02
    },
    "bull_strict": {
      "enabled": false,
      "mode": "no_shorts",
      "sma_window": 200,
      "ret_window": 60,
      "ret_threshold": 0.03
    },
    "sectoral_cap": {
      "enabled": false,
      "max_sector_exposure_pct": 0.4
    },
    "drawdown_breaker": {
      "enabled": false,
      "max_dd_pct": 0.2,
      "recovery_pct": 0.92,
      "rolling_peak_window_days": 252,
      "degraded_entry_allocation_pct": 0.0,
      "regime_ramp_up_enabled": false,
      "regime_ramp_up_pct_per_day": 0.025,
      "regime_ramp_up_max_pct": 0.4,
      "regime_ramp_up_peak_window_days": 5,
      "force_close_on_breaker": false,
      "force_close_pct": 0.5,
      "force_close_losers_on_breaker": false,
      "policy": "b0",
      "spy_regime_map": null,
      "research_force_close_at_dd_pct": null,
      "research_force_close_side": null,
      "_research_peak_episode": 0.0,
      "_research_fired_in_episode": false,
      "_tripped": false,
      "_was_tripped": false,
      "_equity_window": [],
      "_normal_streak": 0,
      "_equity_prev": 0.0,
      "_equity_peak_window": [],
      "_episode": null,
      "_regime_today": null,
      "_alloc_today": 1.0
    },
    "target_annual_vol": null
  },
  "benchmark_close": null,
  "seed": null,
  "atr_trailing_stop_multiplier": 0.0,
  "trailing_stop_long_pct": null,
  "trailing_stop_short_pct": null,
  "atr_risk_stop_multiple": 0.0,
  "initial_stop_atr_multiple": 0.0,
  "tp_atr_multiple": 0.0,
  "tp_max_pct": 0.0,
  "concentration_max_trades_per_symbol": 10,
  "concentration_window_calendar_days": 90,
  "concentration_max_consecutive_losses": 5,
  "concentration_blacklist_duration_days": 30,
  "min_breakout_days": 1,
  "min_score_threshold": 0.7,
  "entry_limit_offset_pct": 0.0
}
```


## 14. Variables exactes et ordre des colonnes

L’ordre fait partie du contrat. Toutes les listes, pour les douze batches, sont aussi conservées dans `variables.json`.


### Oracle Q051 — 2021

```text
001. daily_return
002. log_return
003. intraday_range
004. overnight_gap
005. close_to_vwap
006. volume_ratio_20
007. rolling_volatility_20
008. rolling_volatility_60
009. rolling_mean_return_5
010. rolling_mean_return_20
011. rsi_14
012. atr_14_norm
013. is_filled
014. sma20_distance
015. sma50_distance
016. sma100_distance
017. sma200_distance
018. ema20_distance
019. ema50_distance
020. momentum_10
021. momentum_20
022. momentum_60
023. vol_ratio_20_60
024. range_position_20
025. market_return_20
026. market_volatility_20
027. market_trend_strength_50
028. relative_strength_20
029. relative_strength_60
030. regime_bull_market
031. regime_risk_off
032. adx_14
033. atr_ratio_5_20
034. atr20_pct
035. ema20_slope_10
036. ema50_slope_20
037. return_2d
038. range_position_50
039. distance_high_20
040. distance_low_20
041. body_range
042. close_location_value
043. relative_strength_5
044. volume_zscore_20
045. cmf_20
046. selector_short_score
047. momentum_20_x_bull
048. momentum_20_x_risk_off
049. momentum_60_x_bull
050. momentum_60_x_risk_off
051. relative_strength_20_x_bull
052. relative_strength_20_x_risk_off
053. relative_strength_60_x_bull
054. relative_strength_60_x_risk_off
055. rolling_volatility_20_x_bull
056. rolling_volatility_20_x_risk_off
057. vol_ratio_20_60_x_bull
058. vol_ratio_20_60_x_risk_off
059. rsi_14_x_bull
060. rsi_14_x_risk_off
061. sma20_distance_x_bull
062. sma20_distance_x_risk_off
063. sma50_distance_x_bull
064. sma50_distance_x_risk_off
065. momentum_3
066. momentum_5
067. momentum_120
068. momentum_250
069. rolling_volatility_5
070. rolling_volatility_10
071. rolling_volatility_120
072. sma10_distance
073. sma250_distance
074. rsi_2
075. rsi_3
076. rsi_5
077. rsi_21
078. dist_to_sma_5d
079. volume_zscore_5d
080. volume_ratio_5
081. zscore_close_vs_ma10
082. momentum_20_div_vol_20
083. momentum_60_div_vol_60
084. momentum_5_minus_momentum_20
085. momentum_20_minus_momentum_60
086. volume_ratio_5_div_volume_ratio_20
087. rsi_14_times_volume_ratio_20
088. rsi_14_div_volatility_20
089. sma20_minus_sma50
090. sma50_minus_sma200
091. ema20_minus_sma20
092. intraday_range_div_atr_14
093. range_position_20_times_vol_ratio_20_60
094. daily_return_times_volume_ratio_20
095. log_return_div_intraday_range
096. relative_strength_20_times_market_trend
097. relative_strength_60_div_market_volatility
098. accel_3_5
099. decay_5_10
100. rsi_slope
101. vol_expansion
102. meanrev_signal
103. gap_fade
104. momentum_5_zscore
105. momentum_10_zscore
106. momentum_20_zscore
107. momentum_60_zscore
108. momentum_120_zscore
109. momentum_250_zscore
110. rolling_volatility_5_zscore
111. rolling_volatility_10_zscore
112. rolling_volatility_20_zscore
113. rolling_volatility_60_zscore
114. rolling_volatility_120_zscore
115. rsi_5_zscore
116. rsi_14_zscore
117. rsi_21_zscore
118. sma10_distance_zscore
119. sma20_distance_zscore
120. sma50_distance_zscore
121. sma100_distance_zscore
122. sma200_distance_zscore
123. sma250_distance_zscore
124. volume_ratio_20_zscore
125. intraday_range_zscore
126. beta_252
127. alpha_252
128. r_squared_252
129. momentum_252_vs_market
130. momentum_3_xs_rank
131. momentum_5_xs_rank
132. momentum_10_xs_rank
133. momentum_20_xs_rank
134. momentum_60_xs_rank
135. momentum_120_xs_rank
136. momentum_250_xs_rank
137. rolling_volatility_5_xs_rank
138. rolling_volatility_10_xs_rank
139. rolling_volatility_20_xs_rank
140. rolling_volatility_60_xs_rank
141. rsi_2_xs_rank
142. rsi_3_xs_rank
143. rsi_5_xs_rank
144. rsi_14_xs_rank
145. rsi_21_xs_rank
146. sma10_distance_xs_rank
147. sma20_distance_xs_rank
148. sma50_distance_xs_rank
149. sma100_distance_xs_rank
150. sma200_distance_xs_rank
151. sma250_distance_xs_rank
152. ema20_distance_xs_rank
153. ema50_distance_xs_rank
154. dist_to_sma_5d_xs_rank
155. zscore_close_vs_ma10_xs_rank
156. daily_return_xs_rank
157. volume_ratio_5_xs_rank
158. volume_ratio_20_xs_rank
159. volume_zscore_5d_xs_rank
160. rolling_mean_return_5_xs_rank
161. rolling_mean_return_20_xs_rank
162. intraday_range_xs_rank
163. overnight_gap_xs_rank
164. close_to_vwap_xs_rank
165. atr_14_norm_xs_rank
166. range_position_20_xs_rank
167. vol_ratio_20_60_xs_rank
168. accel_3_5_xs_rank
169. decay_5_10_xs_rank
170. rsi_slope_xs_rank
171. vol_expansion_xs_rank
172. meanrev_signal_xs_rank
173. gap_fade_xs_rank
```


### Oracle B — 2021

```text
001. daily_return
002. log_return
003. intraday_range
004. overnight_gap
005. close_to_vwap
006. volume_ratio_20
007. rolling_volatility_20
008. rolling_volatility_60
009. rolling_mean_return_5
010. rolling_mean_return_20
011. rsi_14
012. atr_14_norm
013. is_filled
014. sma20_distance
015. sma50_distance
016. sma100_distance
017. sma200_distance
018. ema20_distance
019. ema50_distance
020. momentum_10
021. momentum_20
022. momentum_60
023. vol_ratio_20_60
024. range_position_20
025. market_return_20
026. market_volatility_20
027. market_trend_strength_50
028. relative_strength_20
029. relative_strength_60
030. regime_bull_market
031. regime_risk_off
032. adx_14
033. atr_ratio_5_20
034. atr20_pct
035. ema20_slope_10
036. ema50_slope_20
037. return_2d
038. range_position_50
039. distance_high_20
040. distance_low_20
041. body_range
042. close_location_value
043. relative_strength_5
044. volume_zscore_20
045. cmf_20
046. selector_short_score
047. momentum_20_x_bull
048. momentum_20_x_risk_off
049. momentum_60_x_bull
050. momentum_60_x_risk_off
051. relative_strength_20_x_bull
052. relative_strength_20_x_risk_off
053. relative_strength_60_x_bull
054. relative_strength_60_x_risk_off
055. rolling_volatility_20_x_bull
056. rolling_volatility_20_x_risk_off
057. vol_ratio_20_60_x_bull
058. vol_ratio_20_60_x_risk_off
059. rsi_14_x_bull
060. rsi_14_x_risk_off
061. sma20_distance_x_bull
062. sma20_distance_x_risk_off
063. sma50_distance_x_bull
064. sma50_distance_x_risk_off
065. momentum_3
066. momentum_5
067. momentum_120
068. momentum_250
069. rolling_volatility_5
070. rolling_volatility_10
071. rolling_volatility_120
072. sma10_distance
073. sma250_distance
074. rsi_2
075. rsi_3
076. rsi_5
077. rsi_21
078. dist_to_sma_5d
079. volume_zscore_5d
080. volume_ratio_5
081. zscore_close_vs_ma10
082. momentum_20_div_vol_20
083. momentum_60_div_vol_60
084. momentum_5_minus_momentum_20
085. momentum_20_minus_momentum_60
086. volume_ratio_5_div_volume_ratio_20
087. rsi_14_times_volume_ratio_20
088. rsi_14_div_volatility_20
089. sma20_minus_sma50
090. sma50_minus_sma200
091. ema20_minus_sma20
092. intraday_range_div_atr_14
093. range_position_20_times_vol_ratio_20_60
094. daily_return_times_volume_ratio_20
095. log_return_div_intraday_range
096. relative_strength_20_times_market_trend
097. relative_strength_60_div_market_volatility
098. accel_3_5
099. decay_5_10
100. rsi_slope
101. vol_expansion
102. meanrev_signal
103. gap_fade
104. momentum_5_zscore
105. momentum_10_zscore
106. momentum_20_zscore
107. momentum_60_zscore
108. momentum_120_zscore
109. momentum_250_zscore
110. rolling_volatility_5_zscore
111. rolling_volatility_10_zscore
112. rolling_volatility_20_zscore
113. rolling_volatility_60_zscore
114. rolling_volatility_120_zscore
115. rsi_5_zscore
116. rsi_14_zscore
117. rsi_21_zscore
118. sma10_distance_zscore
119. sma20_distance_zscore
120. sma50_distance_zscore
121. sma100_distance_zscore
122. sma200_distance_zscore
123. sma250_distance_zscore
124. volume_ratio_20_zscore
125. intraday_range_zscore
126. beta_252
127. alpha_252
128. r_squared_252
129. momentum_252_vs_market
130. momentum_3_xs_rank
131. momentum_5_xs_rank
132. momentum_10_xs_rank
133. momentum_20_xs_rank
134. momentum_60_xs_rank
135. momentum_120_xs_rank
136. momentum_250_xs_rank
137. rolling_volatility_5_xs_rank
138. rolling_volatility_10_xs_rank
139. rolling_volatility_20_xs_rank
140. rolling_volatility_60_xs_rank
141. rsi_2_xs_rank
142. rsi_3_xs_rank
143. rsi_5_xs_rank
144. rsi_14_xs_rank
145. rsi_21_xs_rank
146. sma10_distance_xs_rank
147. sma20_distance_xs_rank
148. sma50_distance_xs_rank
149. sma100_distance_xs_rank
150. sma200_distance_xs_rank
151. sma250_distance_xs_rank
152. ema20_distance_xs_rank
153. ema50_distance_xs_rank
154. dist_to_sma_5d_xs_rank
155. zscore_close_vs_ma10_xs_rank
156. daily_return_xs_rank
157. volume_ratio_5_xs_rank
158. volume_ratio_20_xs_rank
159. volume_zscore_5d_xs_rank
160. rolling_mean_return_5_xs_rank
161. rolling_mean_return_20_xs_rank
162. intraday_range_xs_rank
163. overnight_gap_xs_rank
164. close_to_vwap_xs_rank
165. atr_14_norm_xs_rank
166. range_position_20_xs_rank
167. vol_ratio_20_60_xs_rank
168. accel_3_5_xs_rank
169. decay_5_10_xs_rank
170. rsi_slope_xs_rank
171. vol_expansion_xs_rank
172. meanrev_signal_xs_rank
173. gap_fade_xs_rank
```


### Per-symbol T0 — 24

```text
001. return_5d
002. return_10d
003. return_20d
004. momentum_60
005. rsi_14
006. adx_14
007. atr20_pct
008. ema20_slope_10
009. ema50_slope_20
010. distance_ema20
011. distance_ema50
012. range_position_20
013. range_position_50
014. vol_ratio_20_60
015. rolling_volatility_20
016. relative_strength_20
017. relative_strength_60
018. benchmark_return_5
019. benchmark_return_20
020. market_volatility_20
021. market_trend_strength_50
022. return_5d_delta5
023. rsi_14_delta5
024. vol_ratio_20_60_delta5
```


### Per-symbol B — 29

```text
001. return_5d
002. return_10d
003. return_20d
004. momentum_60
005. rsi_14
006. adx_14
007. atr20_pct
008. ema20_slope_10
009. ema50_slope_20
010. distance_ema20
011. distance_ema50
012. range_position_20
013. range_position_50
014. vol_ratio_20_60
015. rolling_volatility_20
016. relative_strength_20
017. relative_strength_60
018. benchmark_return_5
019. benchmark_return_20
020. market_volatility_20
021. market_trend_strength_50
022. return_5d_delta5
023. rsi_14_delta5
024. vol_ratio_20_60_delta5
025. rolling_volatility_60
026. rolling_volatility_120
027. rolling_volatility_20_zscore
028. rolling_volatility_60_zscore
029. rolling_volatility_120_zscore
```


### Anti-SL trajectoire — 44

```text
001. return_5d
002. return_10d
003. return_20d
004. momentum_60
005. rsi_14
006. adx_14
007. atr20_pct
008. ema20_slope_10
009. ema50_slope_20
010. distance_ema20
011. distance_ema50
012. range_position_20
013. range_position_50
014. vol_ratio_20_60
015. rolling_volatility_20
016. relative_strength_20
017. relative_strength_60
018. benchmark_return_5
019. benchmark_return_20
020. market_volatility_20
021. market_trend_strength_50
022. return_5d_delta5
023. rsi_14_delta5
024. vol_ratio_20_60_delta5
025. rolling_volatility_60
026. rolling_volatility_120
027. rolling_volatility_20_zscore
028. rolling_volatility_60_zscore
029. rolling_volatility_120_zscore
030. return_5d_path10_delta
031. return_5d_path10_slope
032. return_5d_path10_std
033. rsi_14_path10_delta
034. rsi_14_path10_slope
035. rsi_14_path10_std
036. vol_ratio_20_60_path10_delta
037. vol_ratio_20_60_path10_slope
038. vol_ratio_20_60_path10_std
039. range_position_20_path10_delta
040. range_position_20_path10_slope
041. range_position_20_path10_std
042. rolling_volatility_20_zscore_path10_delta
043. rolling_volatility_20_zscore_path10_slope
044. rolling_volatility_20_zscore_path10_std
```


## 15. Validation de la reconstruction et symptômes fréquents

### Contrôles avant d’interpréter le rendement

1. Valider SHA-256 des modèles, profils, manifests de prix et signaux.
2. Vérifier les 1 790 symboles exacts, les 179 candidats Oracle et les dates
   préalables de signal, y compris le dernier jour de l’année précédente.
3. Contrôler que modèle, AUC et labels étaient disponibles **avant** le signal.
   Le CSV des folds et celui des fenêtres LONG permettent cette vérification.
4. Comparer les comptes de signaux, les titres et leurs rangs **avant risque**.
   Pas de rang suivant promu en cas de refus, ni d’inconnu appelé perdant.
5. Reproduire le témoin avant les variantes : chaque clôture de capital,
   nombre de trades, prix/quantités et coûts, pas seulement le capital final.
6. Contrôler `pnl = quantité × (sortie−entrée) − frais_entrée − frais_sortie + dividendes`.
   Capital final = cash réglé + cash non réglé + valeur des positions + dividendes à recevoir.
7. Vérifier le /252 du financement, les minimums, quantités entières, capacité,
   répétitions de titre et absence de reset annuel.
8. Vérifier SL5, gaps, open11 par calendrier, absence de TP/trailing inattendu,
   et pour le plafond, chaque prix/date/identité de signal à J+1 ou J+2.
9. Recalculer le DD sur la même fréquence et contrôler les états de couverture.
10. Conserver les imports IHM comme copies de résultats, sans les confondre
    avec les sources de simulation. Une courbe statique ou une moyenne par
    année n’est pas un replay avec capital partagé.

### Manifests et réserves à lire

| Famille | Contrôles principaux |
| --- | --- |
| Q051 classique | protocoles annuels, manifests modèles/prix, validations des continu et TOP10 |
| B/T0 appariés | `validation.json`, `price-window-validation.json`, `recovery-validation.json` |
| Anti-SL | `selection-validation.json`, `oracle-oof-causality.json`, `post-run-review.json` |
| Plafond | `baseline-reuse.json`, `baseline-reproduction.json`, `validation.json`, `entry-audit.csv` |

Le bilan anti-SL conserve des réserves de prix et de labels d’événement ;
les accepter comme réserve de recherche ne signifie pas les avoir corrigées
ni obtenir une disponibilité historique certifiée. La comparaison n’a pas
été relue par une personne indépendante simplement parce qu’un autre script
de vérification a été exécuté par le même assistant.

### Pourquoi une reconstruction peut différer

- **Zéro achat** : signaux absents, fenêtre initiale décalée, aucun fold causal,
  score/AUC trop restrictifs, contrôles de données/facteurs non désactivés comme
  dans le témoin, minimum de position trop élevé, ou archive intraday manquante.
- **Même nom, autre résultat** : mauvais batch annuel, mauvais TOP5/TOP10,
  famille B substituée à Q051, base de prix changée, reset de capital,
  activation B4/DD, autre plafond 1×/2×, confirmation 5m ou fraction de position.
- **Capital faible** : tailles natives entières, minimum, poids, absence de
  candidat qualifié, positions détenues et répétitions ; ne pas seulement
  multiplier les rendements par le levier.
- **Beaucoup moins de SL** ne prouve pas un meilleur filtre : vérifier aussi
  les occasions gagnantes supprimées, l’exposition et le rendement net.
- **DD plus petit sur l’image** : celle-ci montre des clôtures ; le chiffre
  intraday du rapport peut être plus profond et le daily fallback peut manquer
  une partie de la trajectoire réelle.

### Gel des livrables et lecture finale

Enregistrer `protocol.json`, `configuration.json`, `report.json`, signaux,
`trades.csv`, `events.csv`, `equity-daily.csv`, `equity-5m.parquet`,
`risk-5m.csv`, `annual-summary.csv`, receipts d’isolation et validation,
ainsi que la commande et les versions exactes. Ne jamais effacer une tentative
échouée pour la transformer a posteriori en succès complet.

Le programme de construction de ce guide est
`scripts/research/build_q051_comparison_guide_20261128.py` : il lit les
archives et écrit la documentation/annexes, sans entraîner, prédire, rejouer,
appeler un fournisseur, écrire SQL ou passer un ordre.

Les clés `cases.*.historical_code_expected_hashes` et
`cases.*.code_at_documentation_time` de l’annexe permettent de repérer un code
actuel différent de celui du replay scellé. Une différence doit être expliquée
ou résolue en restaurant cette version ; elle ne doit pas être ignorée pour
affirmer une reproduction exacte. Les empreintes et les snapshots sont
documentés ; aucun identifiant de commit historique absent des archives n’est inventé.


### Versions installées au moment de cette documentation

Ces versions ont été relevées le 28 novembre 2026. Elles ne prouvent pas les versions historiques de chaque entraînement : conserver l’ancien environnement si une identité binaire est nécessaire.

```json
{
  "python": "3.14.4",
  "numpy": "2.4.6",
  "pandas": "2.3.3",
  "scikit-learn": "1.9.0",
  "lightgbm": "4.6.0",
  "catboost": "1.2.10",
  "joblib": "1.5.3",
  "SQLAlchemy": "2.0.50",
  "streamlit": "1.58.0",
  "plotly": "6.8.0"
}
```

