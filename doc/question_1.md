# Réponses détaillées à `doc/question.txt`

> Document rédigé à partir du code, de la documentation et des tests présents dans le workspace.
> 
> Sources principales vérifiées : `backtesting/data_loader.py`, `backtesting/resilience.py`, `modelFactory/predictor.py`, `modelFactory/features.py`, `modelFactory/champion_selection.py`, `event_sentiment/history_backfill.py`, `event_sentiment/signal_aggregator.py`, `ihm/pages/*.py`, `ihm/services/*.py`, `execution_engine/*.py`, `risk_management/cli.py`, `config.yaml`, ainsi que les docs `doc/*.md`.

## Comment lire ce document

- **Si tu débutes** : lis d'abord chaque **"Réponse courte"**, puis les exemples.
- **Si tu veux comprendre le pourquoi** : lis la partie **"Réponse détaillée"** ou **"Pipeline réel"**.
- **Si tu veux vérifier dans le code** : les chemins de fichiers cités sont ceux qui ont été relus.

### Convention utilisée

- **PIT** = *point-in-time*, donc "tel que connu à cette date".
- **RTH** = *Regular Trading Hours*, donc les heures normales de marché.
- Quand j'écris **"plus sûr"**, cela veut dire **"plus fidèle historiquement"**, pas forcément **"garanti parfait"**.

---

## 1. Questions transverses

### 1.1 Model Factory + backtest : est-ce qu’un modèle entraîné en 2026 peut “fuiter le futur” sur un backtest 2023→2025 ?

### Réponse courte
**Oui, ce risque existe si tu reconstruis des prédictions historiques avec les artefacts actuels de 2026.**
**Non, si le backtest relit de vraies prédictions persistées point-in-time (ou de vrais snapshots historiques) correspondant à chaque date.**

### Réponse détaillée
Il faut distinguer **3 couches** :

1. **Les artefacts de modèle** (`artifacts/models/<symbol>/...`)
2. **Les prédictions déjà persistées** (`model_predictions`)
3. **Le mode de backtest** (`research` vs `pipeline`) et la stratégie ML PIT

#### Ce que fait le code
- Le prédicteur ML borne bien les données d’entrée avec :
  - `cutoff_date = as_of_date or prediction_date` dans `modelFactory/predictor.py`
- Donc **quand on demande une prédiction pour une date donnée**, les features utilisées sont bien coupées à cette date.
- **Mais cela ne suffit pas** à garantir l’absence totale de fuite du futur si :
  - le **modèle lui-même** a été entraîné plus tard, sur des données allant jusqu’en 2026,
  - puis réutilisé pour “prédire” 2023.

Autrement dit :
- **features PIT** ≠ **modèle PIT**
- On peut avoir des features correctement coupées à 2023, mais un modèle entraîné en 2026.

#### Côté backtesting
Dans `backtesting/resilience.py` :
- stratégie `use-persisted` = le backtest **relit les prédictions déjà persistées** et **ne reconstruit rien** si elles manquent ;
- stratégie `rebuild-missing` = le backtest tente de **recalculer** les prédictions manquantes ;
- stratégie `walk-forward-train-then-predict` = **pas encore supportée**.

Donc :

##### Cas A — tu utilises des prédictions déjà persistées, créées historiquement au bon moment
Alors le risque de fuite est fortement réduit :
- le backtest relit simplement `model_predictions` par date,
- et ne réentraîne pas un modèle moderne pour le passé.

⚠️ Point pédagogique important : **"persisté" ne veut pas automatiquement dire "historique propre"**.
Si tu as persisté en 2026 des prédictions reconstruites pour 2023 avec le champion actuel,
elles sont bien "persistées", mais **pas vraiment PIT**.

##### Cas B — tu utilises `rebuild-missing` avec les artefacts actuels de 2026
Alors **oui**, tu peux introduire une fuite du futur :
- le modèle servi aujourd’hui peut avoir appris des patterns de 2025/2026,
- puis on lui demande de prédire 2023,
- ce qui n’est **pas** un vrai replay historique.

##### Cas C — backtest `pipeline` strict
Le mode `pipeline` est strict pour les **scores PIT** (`stock_scores_history`) ;
mais pour la partie ML, la stratégie la plus sûre reste :
- **réutiliser des prédictions persistées historiques**,
- éviter de reconstruire rétroactivement avec le champion actuel si on veut une fidélité historique forte.

### Conclusion pratique
Si ton scénario est :
- modèles entraînés aujourd’hui en 2026 sur 5 ans,
- puis backtest 2023→2025,
- avec reconstruction a posteriori des prédictions,

alors **oui, tu peux contaminer le passé avec de l’information apprise dans le futur**.

### Recommandation simple
Pour un backtest propre :
1. utiliser `stock_scores_history` pour les scores,
2. utiliser des `model_predictions` déjà persistées par date,
3. éviter `rebuild-missing` si tu n’as pas d’artefacts/versionning historique par date,
4. considérer `rebuild-missing` comme **tolérable pour recherche**, mais **pas comme preuve PIT parfaite**.

---

### 1.2 News / sentiment : si tu as lancé l’import 2020→2026, est-ce que les scores existent pour chaque jour de 2023→2025 ?

### Réponse courte
**Oui, les scores sont calculés jour par jour pour les dates de trading effectivement scorées.**
Mais il faut distinguer :
- le **score par article**,
- l’**agrégation journalière ticker/secteur**,
- puis le **score final injecté dans `stock_scores` / `stock_scores_history`**.

### Pipeline réel
#### Niveau 1 — scoring article par article
Quand tu fais l’import + score news, chaque article reçoit un score de sentiment.
En plus, chaque article est aligné sur une **`effective_trade_date`** :
- pré-market → même jour,
- pendant séance → souvent jour suivant pour exploitation swing,
- week-end / hors séance → prochaine séance.

#### Niveau 2 — agrégation journalière
`event_sentiment.history_backfill.py` relit les dates scorées via `list_scored_trade_dates()` puis reconstruit :
- `ticker_daily_sentiment_features`
- `sector_daily_sentiment_features`

Donc, si tu as importé/scoré les news entre 2020 et 2026, le service peut reconstruire les features **pour toutes les dates de trading scorées de cette plage**.

#### Niveau 3 — utilisation en backtest
`event_sentiment.signal_aggregator.py` relit ensuite ces tables journalières sur une fenêtre jusqu’à la `trade_date` du backtest.

Donc pour un backtest 2023→2025 :
- si les features journalières ont bien été backfillées pour cette période,
- elles sont bien utilisées,
- avec décroissance temporelle et agrégation.

### Point important
Ce n’est **pas forcément “une ligne pour chaque jour calendaire”**.
En pratique :
- ce sont surtout les **jours de trading scorés** qui ont des lignes ;
- s’il n’y a pas de news exploitable pour un jour donné, il peut manquer une ligne spécifique ;
- dans ce cas, l’agrégateur retombe vers un comportement neutre / sans boost sentiment.

### Donc, la bonne réponse est
- **Oui**, le système peut couvrir chaque jour de trading de 2023→2025 **si les news ont été importées/scorées et que le backfill a été fait**.
- **Non**, cela ne signifie pas qu’il y a toujours une information sentiment non neutre chaque jour.

### Vérification pratique à retenir
Pour un backtest strictement prêt sur 2023→2025, il faut idéalement que tu aies :
1. les articles scorés,
2. les tables `ticker_daily_sentiment_features` et `sector_daily_sentiment_features` remplies sur la période,
3. et si tu veux un replay PIT complet, les snapshots `stock_scores_history` recalculés avec ce sentiment.

---

### 1.3 `coverage.json` : pourquoi seulement ~4 % alors qu’il y a plein de tests ?

### Réponse courte
Parce que **`coverage.json` ne dit pas “combien de tests existent”**.
Il dit : **“combien de lignes ont réellement été exécutées pendant le run qui a produit ce fichier”**.

### Très important
Dans le workspace actuel, le `coverage.json` que j’ai relu affiche même :
- `covered_lines = 1003`
- `num_statements = 36421`
- `percent_covered = 2.387854581373875`

Donc si toi tu as vu :
- `covered_lines = 1552`
- `num_statements = 37237`
- `percent_covered = 3.587868087521281`

ça veut simplement dire que **le fichier `coverage.json` venait d’un autre run**, mais la logique reste la même.

### Pourquoi un taux si bas ?
Les causes possibles sont les suivantes.

#### 1. Tous les tests du dépôt n’ont pas été exécutés dans ce run
C’est le cas le plus probable.
Exemple :
- tu as 300 fichiers de tests dans le dépôt,
- mais tu lances seulement 2 ou 10 fichiers,
- alors `coverage.json` compte bien tout le code du projet dans le dénominateur,
- mais seulement les lignes touchées par ces quelques tests dans le numérateur.

#### 2. Certains tests existent mais ne passent pas par beaucoup de code métier
Exemple :
- tests unitaires très localisés,
- tests de helpers,
- tests de parsing,
- tests de config,
- mocks qui évitent la vraie logique.

Dans ce cas, tu as bien des tests, mais ils couvrent peu de lignes réelles.

#### 3. Beaucoup de code n’est jamais traversé pendant la mesure
Exemple courant :
- pages IHM peu testées,
- chemins live/paper non simulés,
- branches d’erreur,
- intégrations provider/broker,
- scripts ops,
- commandes rares.

#### 4. `coverage.json` reflète uniquement **le dernier run de couverture**
Le fichier n’est pas une vérité absolue sur le dépôt.
C’est une **photo instantanée** du dernier `pytest --cov ...` lancé.

Si quelqu’un fait :

```powershell
python -m pytest --no-cov tests/test_var_env.py -q
```

cela **ne met pas à jour** la couverture.

Si quelqu’un fait :

```powershell
python -m pytest tests/test_x.py --cov=. --cov-branch --cov-report=json:coverage.json
```

alors `coverage.json` représentera **uniquement ce run-là**.

### Réponse à ta question précise
> est-ce parce que les tests ne couvrent pas toutes les fonctionnalités ?

**Oui, probablement en grande partie.**

> ou parce que certains tests ne sont pas exécutés lors de l’analyse de couverture ?

**Oui, ça aussi.**

En pratique, le faible pourcentage vient souvent de la combinaison des deux :
- tous les tests du repo ne sont pas lancés,
- et ceux qui le sont ne traversent pas tout le code.

### Formule simple pour débutant
- `num_statements` = toutes les lignes “exécutables” du projet
- `covered_lines` = lignes réellement exécutées pendant le run mesuré
- `percent_covered` = rapport entre les deux

Donc **avoir beaucoup de tests dans le repo** ne garantit **pas** un gros taux de couverture.
Il faut que ces tests soient **lancés** et qu’ils **passent réellement dans le code**.

---

## 2. Questions sur la page « Vue d’ensemble »

### 2.1 Message : `Régime marché : normal — risk×1.00 · slots — · max_pos — · new_entries ✅ · 2026-05-06`

- **`risk×1.00`** : multiplicateur global de risque. `1.00` = pas de réduction.
- **`slots`** : nombre de nouvelles places encore autorisées par le régime marché.
  - `—` = non renseigné dans le snapshot courant.
- **`max_pos`** : nombre maximal de positions effectif après application du régime.
  - `—` = non renseigné dans le snapshot.
- **`new_entries ✅`** : les nouvelles entrées sont autorisées.
  - `🛑` voudrait dire : pas de nouvelles entrées.

### En version très simple
Cette bannière dit :
> “Le moteur régime marché est en mode normal, il n’a pas réduit ton risque, et il ne bloque pas les nouvelles positions.”

Le `—` n’est pas un bug visuel grave : cela veut juste dire que le snapshot chargé n’apporte pas de valeur explicite pour ces champs.

---

### 2.2 Bloc « Source screener active » : qu’est-ce que c’est ?

C’est le **répertoire d’artefacts screener** que l’IHM choisit comme **source de référence commune** pour :
- `Overview`
- `Screening`
- et les recommandations issues des outils `diagnose-screener` / `recommend-screener`

L’idée est d’éviter qu’une page lise un dossier et qu’une autre en lise un autre.

#### Quand tu vois
`artifacts\screener_diagnostics | Période non renseignée | MAJ inconnue`

cela signifie :
- **`artifacts\screener_diagnostics`** = dossier actuellement sélectionné
- **`Période non renseignée`** = le fichier `metadata.json` ne contient pas de liste claire des `trading_dates`, ou elle est absente/incomplète
- **`MAJ inconnue`** = l’IHM n’a pas trouvé un fichier de synthèse exploitable pour en déduire une date de mise à jour lisible

Donc cela ne veut pas dire “le screener ne marche pas”.
Cela veut dire plutôt :
> “J’ai bien un dossier d’artefacts, mais je n’ai pas assez de métadonnées pour t’afficher la période couverte et l’horodatage proprement.”

---

### 2.3 Bloc « Calibration screener » : qu’est-ce que c’est ?

Ce bloc lit les **artefacts de recommandation screener** présents dans le dossier sélectionné.

Il affiche notamment :
- les **objectifs** analysés,
- les **scénarios recommandés**,
- leurs scores (`objective_score`, `overall_score`, etc.),
- la période couverte,
- la date de mise à jour,
- et éventuellement un tableau de leaders par objectif.

### En pratique
Ce bloc sert à répondre à une question du type :
> “Parmi plusieurs réglages screener testés, lesquels semblent les plus robustes / offensifs / exécutables ?”

Donc ce n’est pas un calibrage “live” des ordres.
C’est plutôt un **résumé d’analyse de tuning/backtesting du screener**.

---

## 3. Questions sur la page « Pipeline Quotidien »

## Bloc « Paramètres d’exécution »

### 3.1 `Execution hors RTH (file d'attente pour l'ouverture)`

### À quoi ça sert
`RTH` = **Regular Trading Hours**, donc les heures normales d’ouverture de marché.

Si tu coches cette case :
- le moteur peut soumettre les ordres **même quand le marché est fermé** ;
- côté broker, ils restent en attente ;
- ils seront traités à la prochaine ouverture / pré-ouverture selon la fenêtre choisie.

### Exemple simple
- Tu lances l’exécution à **22h** après la clôture.
- Avec cette case cochée, les ordres d’entrée peuvent être placés le soir.
- Ils seront **en file** et ne seront réellement exécutés qu’à l’ouverture suivante.

### Quand c’est utile
- stratégie swing overnight,
- préparation la veille au soir,
- workflow “je veux être prêt avant l’ouverture”.

### Quand éviter
- si tu veux uniquement des entrées décidées en séance,
- si tu ne veux pas d’ordres en attente overnight.

---

### 3.2 `Auto rebalance`

### À quoi ça sert
Cette option active `auto_rebalance_on_reconcile` côté exécution.

Après la réconciliation broker ↔ cible portefeuille :
- si des écarts sont jugés **safe_auto**,
- le moteur peut soumettre des **ordres de rééquilibrage** pour corriger ces écarts.

### Exemple
Le portefeuille cible dit :
- AAPL = 100 actions

Mais le broker a réellement :
- AAPL = 80 actions

Alors la réconciliation détecte un delta de +20.
Si l’écart est classé “safe_auto” et que `Auto rebalance` est activé,
le moteur peut envoyer un **ordre d’achat de 20 actions** pour recoller à la cible.

### En résumé
- **désactivé** : on constate l’écart mais on ne corrige pas automatiquement ;
- **activé** : le moteur corrige automatiquement certains écarts jugés sûrs.

---

### 3.3 `Execution — fenêtre de soumission`

Options possibles :
- `post_close`
- `pre_open`
- `both`

### Signification
#### `post_close`
Le moteur tente la soumission **après la clôture**.

#### `pre_open`
Le moteur attend la **pré-ouverture** pour soumettre.

#### `both`
Le moteur essaye d’abord la fenêtre `post_close`, puis si elle est ratée ou passée, il retente sur `pre_open`.

### Exemple
- Tu lances à 17h10 → `post_close` est pertinent.
- Tu lances à 8h15 → `pre_open` est pertinent.
- Tu veux couvrir les deux cas opératoires → `both`.

### Réponse simple
C’est la **fenêtre temporelle autorisée** pour envoyer les ordres quand tu fais de l’overnight / du swing préparé hors séance.

---

### 3.4 `Trigger d'activation du trailing`

Options :
- `multiple_r`
- `profit_pct`

### `multiple_r`
Le trailing stop ne s’active qu’après avoir atteint un certain multiple du risque initial (`R`).

### `profit_pct`
Le trailing stop s’active quand le trade a atteint un certain pourcentage de gain.

### Exemple `multiple_r`
- entrée = 100
- stop initial = 95
- risque initial = 5 = `1R`
- si tu mets `1.0R`, le trailing s’active à partir de 105
- si tu mets `2.0R`, il s’active à partir de 110

### Exemple `profit_pct`
- entrée = 100
- trigger = 3 %
- trailing activé à partir de 103

---

### 3.5 `Multiple de R pour activation`

Ce paramètre est utilisé quand le trigger = `multiple_r`.

### Définition
`R` = risque initial par action/trade.

Si ton stop initial est à 5 % sous l’entrée, alors :
- `1R` = +5 %
- `2R` = +10 %
- etc.

### Exemple
- entrée 50
- stop 47
- risque = 3 dollars
- `1R` = 53
- `1.5R` = 54.5
- `2R` = 56

Plus la valeur est élevée, plus tu laisses respirer le trade avant de transformer la protection en trailing dynamique.

---

### 3.6 `Transition — timeout (s)` et `Transition — poll interval (s)`

Ces paramètres pilotent la phase où l’exécuteur surveille la **transition des protections** (par exemple passage d’une protection initiale vers un trailing activé).

#### `Transition — timeout (s)`
Temps maximal d’attente avant d’abandonner la transition.

#### `Transition — poll interval (s)`
Fréquence à laquelle le moteur re-vérifie l’état pendant cette attente.

### Exemple
- timeout = 120 s
- poll interval = 5 s

Le moteur va vérifier toutes les 5 secondes pendant 2 minutes maximum.

### Lecture simple
- timeout grand = plus patient, mais plus lent à conclure qu’il y a échec ;
- poll plus petit = plus réactif, mais plus de polling/logs.

---

### 3.7 Paramètres Risk Management

#### `Risk — risque par trade (fraction)`
Part du capital que tu acceptes de perdre si le stop est touché.
- `0.01` = 1 %
- exemple : compte 10 000 $, risque/trade = 100 $

#### `Risk — poids max par position`
Poids maximal d’une seule ligne dans le portefeuille.
- `0.08` = 8 % du portefeuille max sur une action

#### `Risk — poids score (conviction)`
Poids du score quant/screener dans la conviction finale.

#### `Risk — poids ML predict (conviction)`
Poids de la prédiction ML dans la conviction finale.

Exemple :
- score = 0.40
- ML = 0.60
=> la conviction utilise plus le ML que le screener brut.

#### `Risk — corrélation max`
Corrélation maximale tolérée entre positions.
Exemple :
- si AAPL et MSFT sont trop corrélées,
- l’une des deux peut être réduite ou rejetée.

#### `Risk — positions max`
Nombre maximal de positions simultanées.

#### `Risk — poids max par secteur`
Cap d’exposition sur un secteur entier.
Exemple :
- max secteur = 0.30
- pas plus de 30 % du portefeuille sur la Tech.

#### `Risk — lookback corrélation (jours)`
Fenêtre historique utilisée pour calculer les corrélations.
Exemple :
- 60 jours = corrélation plus réactive
- 252 jours = corrélation plus stable, plus longue

#### `Risk — ticket minimum ($)`
Montant minimal autorisé pour une position.
Exemple :
- si le sizing calcule une cible à 48 $
- et que le minimum est 100 $
- la position peut être rejetée comme trop petite.

---

### 3.8 Bloc `Risk — Kelly sizing & options avancées`

#### `Activer Kelly sizing`
Active un sizing inspiré du critère de Kelly.
But : augmenter/réduire la taille selon l’avantage statistique estimé.

#### `Risk — payoff ratio assumé`
Hypothèse gain/perte moyenne utilisée dans la logique Kelly.
Exemple :
- `2.0` = tu supposes gagner 2 fois ce que tu risques en moyenne

#### `Risk — min overlap corrélation`
Nombre minimal de points communs nécessaires pour considérer la corrélation comme exploitable.

#### `Risk — multiplicateur Kelly fraction`
Permet de n’utiliser qu’une fraction du Kelly théorique.
Exemple :
- Kelly théorique = 20 %
- multiplicateur = 0.25
- Kelly effectif = 5 %

#### `Risk — niveau de log`
Niveau de verbosité du module risk (`DEBUG`, `INFO`, etc.).

#### `Dry run`
Oui : **il n’écrit pas en base**.
Dans `risk_management/cli.py`, quand `dry_run=True`, le code saute l’écriture dans :
- `risk_decisions`
- `portfolio_targets`

Donc le calcul se fait, mais rien n’est persisté comme résultat opérationnel.

---

### 3.9 `Preset ML Train` : différence entre Personnalisé, Prod swing, Debug rapide, Debug GPU

#### `Personnalisé`
Aucun profil automatique imposé.
Tu règles tout toi-même.

#### `Prod swing`
Preset recommandé pour un vrai usage swing :
- accélérateur `auto`
- logs `INFO`
- `walk-forward=True`
- `max_epochs=50`
- `max_workers=4`
- heartbeat 60s
- watchdog 0

#### `Debug rapide`
Preset pour itérations rapides CPU :
- accélérateur `cpu`
- logs `DEBUG`
- `walk-forward=False`
- `max_epochs=10`
- `max_workers=1`
- heartbeat 30s
- watchdog 300s

#### `Debug GPU`
Même logique que debug rapide, mais avec :
- accélérateur `gpu`
- pour valider vite un entraînement sur machine CUDA

### Usage conseillé
- **Prod swing** : backtests/training sérieux
- **Debug rapide** : vérifier qu’un run démarre correctement
- **Debug GPU** : vérifier le pipeline GPU
- **Personnalisé** : cas experts

---

### 3.10 Paramètres avancés Model Factory

#### `Comparer LightGBM local`
Entraîne LightGBM comme **challenger local** en plus du modèle principal.

#### `Comparer CatBoost local`
Même idée pour CatBoost.

#### `Activer la sélection automatique du champion`
Permet de choisir automatiquement le meilleur modèle servi parmi les challengers éligibles.

#### `Métrique de sélection du champion`
Options :
- `selection_score`
- `business_score`
- `auc`

Dans `modelFactory/champion_selection.py` :
- `selection_score` privilégie le score de sélection global,
- `business_score` regarde le score métier (`threshold_business_score`) puis fallback,
- `auc` privilégie l’AUC.

### En pratique
- `selection_score` = meilleur compromis global
- `business_score` = plus orienté décision opérationnelle
- `auc` = plus “qualité de classification” pure

#### `Entraîner aussi un modèle global multi-symboles`
Ajoute un modèle qui apprend **sur plusieurs symboles à la fois**.

### Avantage
- utile quand un symbole seul n’a pas assez d’historique exploitable,
- peut mieux apprendre des patterns transverses de marché,
- permet parfois de stabiliser la généralisation.

### Inconvénient
- moins spécifique à un symbole donné,
- peut lisser des comportements très particuliers.

#### `Backend du modèle global`
- `catboost`
- `lightgbm`

Cela choisit juste le moteur tabulaire du modèle global.

---

### 3.11 Bloc `Cible swing & horizon`

#### `Mode de cible = binary`
Target simple :
- `1` si le rendement futur dépasse le seuil positif,
- sinon `0`

#### `Mode de cible = swing_cash`
Target plus adaptée au swing cash :
- `1` si le rendement futur dépasse le seuil UP,
- `0` si le rendement futur est en dessous du seuil DOWN,
- `NaN` entre les deux = zone neutre / no-trade, ignorée à l’entraînement

### Pourquoi `swing_cash` est souvent mieux
Parce qu’il évite de forcer le modèle à classer comme “bon” ou “mauvais” des cas ambigus.

#### `Seuil cible UP`
Hausse minimale à atteindre sur l’horizon pour étiqueter un cas “positif”.
Ex. `0.02` = +2 %

#### `Horizon de prédiction`
Nombre de jours regardés dans le futur pour définir la target.
Ex. 5 jours.

#### `Seuil de décision`
Probabilité minimale pour transformer la prédiction en signal exploitable.
Ex. `0.55`

#### `Seuil cible DOWN`
Dans `swing_cash`, seuil de baisse / no-trade.
Ex. `-0.01`

#### `Méthode de calibration`
- `none`
- `platt`

La calibration sert à rendre les probabilités mieux calibrées.
En pratique, `platt` est utile pour que `0.70` signifie davantage “70 % crédible” que “score brut non calibré”.

---

### 3.12 Bloc `ML — Hyperparams & seuils d'optimisation (avancé)`

#### `ML — max workers`
Nombre de workers parallèles pour le training/orchestration.

#### `ML — max epochs (LSTM)`
Nombre maximal d’époques d’entraînement du LSTM.

#### `ML — feature set`
- `v1`
- `expert`

`expert` = set de features plus riche / plus complexe.

#### `ML — taux d'action min`
Borne basse du taux de signaux/trades acceptables lors des optimisations.

#### `ML — taux d'action max`
Borne haute : évite un modèle qui “trade tout”.

#### `ML — précision min (long)`
Seuil minimal de précision souhaitée sur les signaux longs.

#### `ML — niveau de log`
Verbosité des logs ML.

#### `ML — mode debug train`
Logs plus détaillés, comportement plus déterministe pour débugger.

#### `ML — heartbeat interval (s)`
Fréquence à laquelle le run émet un signal “je suis vivant”.
Ce n’est **pas** un timeout.

#### `ML — watchdog timeout (s)`
Délai maximum autorisé depuis le dernier heartbeat avant de considérer le run figé.
- `0` = surveillance seule

---

### 3.13 Bloc `ML — Hyperparams avancés (architecture, boosters, grilles)`

#### Partie LSTM
- `sequence length` : longueur de fenêtre temporelle
- `batch size` : taille des mini-lots
- `hidden size` : taille de la couche cachée

#### Partie artefacts / benchmark
- `Répertoire d'artefacts ML` : dossier lu/écrit par train + predict
- `Symbole benchmark` : benchmark utilisé pour features relatives (souvent `SPY`)
- `Champion par défaut` : modèle servi si la sélection auto n’est pas utilisée
- `Cross-sectional — taille mini univers/date` : taille minimale d’univers pour les features cross-sectionnelles

#### Partie calibration
- `Calibration — min samples`
- `Calibration — max iter`

#### Partie LightGBM
- `max depth`
- `n estimators`
- `learning rate`

#### Partie CatBoost
- `depth`
- `iterations`
- `learning rate`

#### Partie grilles candidate
Utilisées si tu coches `--optimize-target` / `--optimize-thresholds` :
- horizons candidats,
- seuils UP candidats,
- seuils DOWN candidats,
- seuils de décision candidats,
- `min-trades-fraction` pour éviter d’optimiser sur trop peu de trades.

---

### 3.14 Bloc `Diagnostic dépendances Alpha Scanner — seuils quotes/earnings`

Ce bloc sert à définir **quand l’amont data est jugé suffisamment bon** pour que l’Alpha Scanner soit fiable.

Il surveille surtout :
- la **couverture** des quotes,
- leur **fraîcheur**,
- la **couverture** du calendrier earnings,
- l’**horizon futur** disponible.

Ce ne sont pas les règles de trading live.
Ce sont les **règles de diagnostic qualité amont**.

---

### 3.15 `Event Sentiment — mapping ticker`

Options :
- `provider_default`
- `strict`
- `scored`

#### `provider_default`
On garde les tickers tels que fournis par le provider news.

#### `strict`
On ne propage le score qu’au ticker principal / premier ticker.

#### `scored`
On calcule un **score de pertinence** `[0,1]` pour chaque paire `(article, ticker)`.
Ce score sert ensuite de poids dans les agrégats journaliers.

### En pratique
- `provider_default` = le plus simple / historique
- `strict` = plus conservateur
- `scored` = le plus fin, mais aussi le plus sophistiqué

---

### 3.16 Bloc `Niveau 4 — Re-scoring FinBERT contextualisé (opt-in)`

Ce bloc active un scoring FinBERT **par couple `(article, symbole)`**.

### Pourquoi
Un même article peut être positif pour une entreprise et neutre/négatif pour une autre.
Ce bloc cherche à capturer cette nuance.

#### Paramètres
- **Activer le scoring contextuel** : active ce mode plus coûteux
- **Seuil min relevance** : on ne rescrore que les couples suffisamment pertinents
- **Cap dur paires/run** : limite absolue de couples rescorrés pour éviter l’explosion de coût CPU/GPU

### Compromis
- plus fin,
- mais beaucoup plus coûteux.

---

### 3.17 Bloc `7bis — Backfill relevance / contextual (étape dédiée)`

Cette étape relance le recalcul batch de la pertinence ticker et/ou du scoring contextuel.

#### `Dry-run`
Simule sans persister.

#### `Re-scorer toutes les lignes`
Recalcule même celles qui avaient déjà un score.

#### `Phase 2 — contextuel`
Ajoute le rescoring contextuel FinBERT.

#### `Batch size`
Taille des lots de lignes traitées.

#### `Purge below`
Supprime les lignes de `news_ticker_map` dont la pertinence est sous le seuil.
Avec FK cascade, le sentiment associé peut aussi être supprimé.

---

### 3.18 Bloc `Paramètres Signal Aggregator`

Ce bloc pilote la fusion :
- quantitatif
- sentiment ticker
- macro/sectoriel

#### `traiter tous les symboles`
Sinon limité à un sous-ensemble / univers utile.

#### `niveau de log`
Verbosité.

#### `poids sentiment`
Poids de la composante sentiment.

#### `poids macro sectoriel`
Poids de la composante sectorielle/macro.

#### Poids quantitatif implicite
Il n’est pas saisi directement.
Le backend calcule :
`1 - poids sentiment - poids macro`

#### `lookback (jours)`
Fenêtre historique relue.

#### `news mini`
Nombre minimal de news avant de considérer le signal comme assez soutenu.

#### `demi-vie décroissance`
Contrôle la vitesse à laquelle les news anciennes perdent du poids.

---

### 3.19 Bloc `Screener amont — univers & scores de base`

Ce bloc pilote le préfiltrage large avant l’Alpha Scanner.

#### Paramètres principaux
- `taille de chunk`
- `max workers`
- `benchmark`
- `liquidité mini`
- `RS mini vs benchmark`
- `chargement en 2 passes`
- `fenêtre range historique`
- `score mini range historique`
- `fenêtre passe 1`

### En version simple
C’est le bloc qui répond à :
> “Dans quel univers large je cherche des actions suffisamment liquides, fortes et exploitables avant le filtrage final ?”

---

### 3.20 Bloc `Paramètres Data Integrity`

Ce bloc pilote les étapes d’intégrité data : quotes, earnings, fondamentaux, import EODHD.

#### Quotes
- `limite optionnelle`
- `taille de batch`

#### Earnings
- `limite optionnelle`
- `taille de batch`
- `pause Finnhub`
- `journaliser tous les N symboles`
- `reprendre depuis le bookmark local`
- `fenêtre de dates personnalisée`
- `date début` / `date fin`

#### Fondamentaux
- `limite optionnelle`
- `pause Finnhub`
- `journaliser tous les N symboles`

#### Import Bars EODHD
- `commit intermédiaire tous les N symboles`
- `activer le cross-check Stooq après import`

### Sens pratique
- petits batches + pause = plus sûr côté quotas provider
- gros batches = plus rapide mais plus risqué sur gros runs

---

### 3.21 Bloc `Paramètres Corporate Actions`

#### `CA Sync — skip existing`
Ignore les symboles déjà présents en base.
Plus rapide, mais peut rater un événement nouveau sur un symbole déjà vu.

#### `CA Sync — batch size`
Nombre de symboles par lot provider.

#### `CA Sync — restreindre la fenêtre temporelle`
Permet d’envoyer `--start` / `--end` au lieu de rebalayer un historique très long.

#### `date début` / `date fin`
Fenêtre custom de recherche des événements.

### Usage recommandé
- au début : sync large
- ensuite en quotidien : petite fenêtre récente (ex. J-7 → J)

---

### 3.22 Bloc `Paramètres Backfill historique EODHD (B3)`

#### `profondeur historique (années)`
Nombre d’années demandées au provider.

#### `reprendre via bookmark`
Réutilise l’état sauvegardé pour ne pas refaire les symboles déjà terminés.

#### `symboles (CSV)`
Laisser vide = univers complet éligible.

#### `mode écriture (insère en base)`
- coché = vrai backfill avec insert DB dans `stock_bars` / `stock_bars_daily`
- décoché = dry-run sans insert

### En simple
B3 sert à reconstruire l’historique OHLCV long, utile pour :
- ML
- backtests
- robustesse des indicateurs

---

## 4. Questions sur la page « Supervision Ops »

### 4.1 `Limit watch`, `Interval service (s)`, `Interval idle (s)`, `Heartbeat (s)`

#### `Limit watch`
Nombre maximal d’éléments/positions que le watcher inspecte par cycle.

#### `Interval service (s)`
Fréquence normale de boucle du service watcher quand il est actif.

#### `Interval idle (s)`
Fréquence de boucle plus lente quand il n’y a rien d’urgent à faire.

#### `Heartbeat (s)`
Fréquence attendue d’émission d’un signal de vie du service.
C’est la référence utilisée pour juger si le service est frais, lent ou stale.

---

### 4.2 Message : `Service Watcher protections scope=default en état STALE`

Cela veut dire :
- un résumé de service watcher existe,
- mais son **heartbeat est trop ancien**,
- donc l’IHM considère que le service n’est plus frais.

### En langage simple
> “Le watcher a probablement tourné, mais il ne donne plus signe de vie depuis trop longtemps.”

### Conséquence pratique
- les protections peuvent ne plus être surveillées correctement,
- il faut vérifier si le watcher est réellement mort, bloqué, ou juste silencieux.

### `scope=default`
Cela désigne le périmètre du service (compte/scope principal par défaut).

---

## 5. Questions sur la page « Exécution »

### 5.1 `Kill switch — annuler tous les ordres ouverts` : à quoi ça sert ?

### But
C’est le bouton d’urgence qui lance :

```powershell
python -m execution_engine cancel-all ...
```

Il sert à :
- annuler tous les ordres **ouverts** du compte sélectionné,
- en paper ou live,
- typiquement en cas d’incident, doute, ou arrêt d’urgence.

### Comment l’utiliser
1. choisir `paper` ou `live`
2. éventuellement laisser `Dry-run` coché pour juste lister
3. saisir une raison
4. lancer

### Le message WinError 123 est-il normal ?
**Non.**
C’était un **bug local de l’IHM sous Windows**, pas un comportement normal du broker.

### Cause simple
Le message du type :

`F:\projets\artifacts\ihm_pipeline_runs\ops:execution_kill_switch\...`

révèle que l’IHM essayait de créer un dossier à partir du `step_key` brut.

Or sous Windows :
- `:` est **interdit** dans un nom de dossier,
- donc `ops:execution_kill_switch` cassait la création du répertoire,
- et l’erreur remontait avant même la vraie logique métier du kill switch.

### Ce que ça voulait dire en pratique
- **le bouton avait du sens** fonctionnellement ;
- **le broker n’était pas forcément en faute** ;
- le plantage venait d’abord du **stockage local des runs IHM**.

### Correctif appliqué
Le registre IHM conserve maintenant :
- le **`step_key` métier inchangé** dans l’historique et les métadonnées ;
- mais utilise un **alias filesystem compatible Windows** pour le nom du dossier de run.

Exemple :
- `step_key` logique : `ops:execution_kill_switch`
- dossier créé sur disque : `ops__execution_kill_switch`

### Conclusion simple
Si tu revoyais ce `WinError 123`, il fallait l’interpréter comme :
> "Le run IHM n’arrive même pas à créer son dossier local sous Windows."

Ce n’était donc **ni un refus broker certain**, ni une preuve que le kill switch était conceptuellement mauvais.

---

### 5.2 `Snapshot des cibles consommées`

C’est la **copie figée des cibles risk** réellement utilisées par ce run d’exécution.

On y voit par exemple :
- `symbol`
- `target_shares`
- `entry_price`
- `target_weight`
- `stop_price_initial`
- `risk_per_share`
- `risk_budget_dollars`

### Pourquoi c’est utile
Pour ne pas confondre :
- ce que le risk module avait calculé au moment du run,
- avec ce qu’on verrait plus tard si `portfolio_targets` a changé.

---

### 5.3 `Requests et ordres broker`

Ce bloc montre le journal canonique des demandes envoyées au broker et leur état.

On y trouve typiquement :
- ordres d’entrée,
- enfants TP/SL/trailing,
- statuts broker,
- prix/quantités,
- identifiants broker.

### En clair
C’est l’endroit où tu comprends :
> “Qu’a demandé Alpha Trade au broker, et qu’est-ce que le broker en a fait ?”

---

### 5.4 `Positions et détentions du run`

Ce bloc reconstruit les positions projetées **dans le scope de ce run précis**.

Il sert à isoler l’effet de ce run, sans mélanger avec tout l’historique compte.

---

### 5.5 `Lots touchés par ce run`

Un **lot** = un paquet d’actions acheté à un certain moment/prix.

Ce bloc montre quels lots ont été :
- ouverts,
- partiellement réduits,
- fermés,
- impactés par ce run.

Très utile pour :
- audit,
- fiscalité,
- compréhension fine des sorties.

---

### 5.6 `Réconciliation actionnable`

C’est la comparaison entre :
- la position interne/cible,
- la position réellement vue chez le broker.

Elle est dite **actionnable** car le système classe les écarts selon ce qu’on peut faire :
- `SAFE_AUTO`
- `MANUAL_REVIEW`
- `BLOCKED`

---

### 5.7 `Motifs de réconciliation`

Ce bloc regroupe les **raisons** pour lesquelles une ligne est dans tel ou tel état.
Exemples :
- écart de quantité,
- ordre encore ouvert,
- protection manquante,
- position broker différente de la position interne.

Il sert à comprendre **pourquoi** une réconciliation n’est pas propre.

---

### 5.8 `Événements`

C’est le journal des événements métier du run :
- soumission,
- fills,
- réconciliation,
- armement de protections,
- incidents,
- transitions watcher/executor.

### Rôle
C’est le fil d’audit chronologique du run.

---

### 5.9 Bloc `Watcher protections — supervision secondaire`

Ce bloc montre ce que le watcher post-exécution a fait **après** le run principal :
- transitions vers trailing dynamique,
- armement de protections manquantes,
- santé du service watcher,
- heartbeat,
- dernier cycle,
- nombre d’éléments surveillés.

### En simple
L’exécuteur lance le trade.
Le watcher continue ensuite à surveiller que les protections vivent correctement.

---

## 6. Questions sur la page « Risk »

### À quoi sert cette page ?
Cette page sert à lire **les décisions de gestion du risque** déjà calculées.
Elle ne sert pas à envoyer des ordres.
Elle sert à comprendre :
- quels candidats ont été acceptés,
- lesquels ont été rejetés,
- pourquoi,
- et quel portefeuille cible a été construit.

### Bloc par bloc
#### 1. Bannière régime marché
Rappelle le contexte marché global qui peut influencer le sizing/slots.

#### 2. Sélecteur de run
Permet de choisir quel `risk_run_id` tu veux inspecter.

#### 3. Résumé métier persistant
Affiche les KPI synthétiques du run risk.

#### 4. `Décisions de risque`
Tableau principal avec :
- symbole,
- décision (`ACCEPTED`, `REDUCED`, `REJECTED`),
- motif,
- prix d’entrée,
- ATR,
- sizing,
- dates as-of des données,
- conviction,
- probabilité ML, etc.

C’est le meilleur endroit pour comprendre :
> “Pourquoi cette action a été gardée/réduite/rejetée ?”

#### 5. `Portefeuille cible`
Montre uniquement les lignes retenues dans le portefeuille final.
On y voit notamment :
- `shares`
- `entry_price`
- `stop_price_initial`
- `target_notional`
- `target_weight`
- `sector`

### En une phrase
La page Risk = **le pont entre les idées de trading et le portefeuille concret à exécuter**.

---

## 7. Questions sur la page « Régime Marché »

La page lit `config.yaml > market_regimes` et permet :
- d’afficher la config active,
- de calculer un snapshot à la volée,
- de visualiser l’historique des snapshots persistés.

### Paramètres de `config.yaml > market_regimes`

#### `enabled`
Active ou non toute la couche market-aware.

#### `cache_ttl_seconds`
Durée de cache des calculs/snapshots.

#### `enforce_min_notional`
Minimum notionnel compatible/exigé pour l’exécution.

#### `allow_neutral_fallback_on_missing_macro_data`
Autorise un fallback neutre si les données macro sont indisponibles.

#### `macro_provider`
Source des données macro (`eodhd`, `stooq`, `composite`, `none`).

#### `sentinel.enabled`
Active la logique sentinelle / préflight.

#### `sentinel.preflight_summary`
Inclut un résumé préflight.

#### Bloc `vix`
- `enabled`
- `symbol`
- `short_symbol`
- `high_threshold`
- `inverted_curve_mode`

But : détecter stress volatilité / inversion de courbe VIX courte.

#### Bloc `yields`
- `enabled`
- `symbol_10y`
- `lookback_days`
- `relative_spike_threshold`
- `block_sectors`
- `block_high_beta`
- `high_beta_threshold`
- `risk_mult`

But : détecter un choc de taux qui justifie prudence sectorielle.

#### Bloc `sentiment_circuit_breaker`
- `enabled`
- `lookback_days`
- `warning_threshold`
- `critical_threshold`
- `warning_max_positions`
- `critical_mode_live`
- `critical_mode_backtest`

But : réduire/stopper les entrées si le sentiment agrégé devient trop mauvais.

#### Bloc `sector_limits`
- `enabled`
- `max_tickers_per_sector`

#### Bloc `earnings_shield`
- `enabled`
- `days_before`
- `days_after`
- `mode`
- `negative_score_value`

But : protéger le portefeuille autour des publications de résultats.

#### Bloc `buyback_blackout`
- `enabled`
- `days_before_earnings`
- `ml_score_multiplier`

But : durcir la prudence sur certaines zones pré-earnings.

#### Bloc `patterns`
Patterns calendaires activables :
- `tax_day`
- `sept_slump`
- `santa_rally`
- `january_effect`
- `institutional_opex`
- `month_end`

Chaque pattern peut ajuster par exemple :
- `risk_mult`
- `screener_expansion_pct`
- `sentiment_threshold_addon`
- ou bloquer certaines entrées.

### En résumé simple
Cette page explique :
> “Comment le système adapte son agressivité selon le contexte de marché.”

---

## 8. Questions sur la page « Compte Alpaca »

### 8.1 Vente manuelle refusée avec `Échec de la clôture de COCO : [403] Forbidden` : est-ce normal ?

### Réponse courte
**Oui, cela peut arriver.**
Ce n’est pas “normal” au sens “souhaité”, mais c’est un **refus broker possible**.

### Ce que cela signifie
Le bouton IHM appelle Alpaca pour fermer la position.
Le `403 Forbidden` veut dire :
- la requête a bien atteint le broker,
- mais le broker a refusé l’action.

### Causes possibles
Sans le payload broker complet, on ne peut pas affirmer laquelle est la bonne, mais les causes classiques sont :
- actif non tradable / restreint,
- permissions insuffisantes,
- compte bloqué,
- problème de mode compte,
- position plus disponible telle qu’attendue,
- cas spécifique d’asset corporate/reverse split/restriction broker.

### Conclusion pratique
Donc :
- oui, **c’est possible**,
- non, ce n’est pas un bug d’affichage pur,
- il faut lire le détail broker pour savoir pourquoi COCO a été refusé.

---

### 8.2 `Historique broker détaillé`

C’est l’historique prioritaire récupéré depuis l’endpoint Alpaca `portfolio history`.

On y voit généralement :
- `timestamp`
- `equity`
- `profit_loss`
- `profit_loss_pct`

### But
Visualiser l’évolution du capital telle que renvoyée directement par le broker.

---

### 8.3 `Snapshots broker persistés`

Ce sont les snapshots enregistrés dans la base Alpha Trade (`broker_account_snapshots`).

### À quoi ça sert
- conserver un historique canonique local,
- avoir un fallback si le broker live ne répond pas,
- relier les chiffres broker aux runs d’exécution.

---

### 8.4 `Ordres canoniques d'exécution (DB)`

Ce sont les ordres persistés dans la base Alpha Trade comme journal canonique d’exécution.

### Différence avec l’historique broker live
- **broker live** = ce qu’Alpaca retourne maintenant
- **ordres canoniques DB** = ce qu’Alpha Trade a enregistré dans sa propre piste d’audit

Très utile pour audit, replay et explication des runs.

---

### 8.5 `Runs d'exécution récents (DB)`

Ce tableau affiche les derniers runs `execution` persistés dans la base :
- identifiant de run,
- statut,
- compte,
- métriques globales,
- timestamps.

C’est la vue de haut niveau des dernières exécutions historiques côté Alpha Trade.

---

## 9. Questions sur la page « Screening »

### 9.1 `Qualité amont & contexte pipeline`, `Derniers résumés par étape`, `Étapes 4 → 5 · détail quotes / earnings utilisé par Alpha Scanner`

#### `Qualité amont & contexte pipeline`
Ce bloc sert à vérifier que l’amont data est sain avant d’interpréter les scores screener.

#### `Derniers résumés par étape`
Tableau synthétique des dernières étapes du pipeline amont (jusqu’à l’étape 8 environ).

#### `Étapes 4 → 5 · détail quotes / earnings utilisé par Alpha Scanner`
Diagnostic ciblé sur :
- fraîcheur / couverture des quotes,
- qualité / horizon du calendrier earnings,
- afin de savoir si l’Alpha Scanner s’appuie sur un amont data crédible.

### En clair
Avant de regarder “quels symboles sont bons”, la page vérifie d’abord :
> “Est-ce que les données sur lesquelles l’Alpha Scanner s’appuie sont assez bonnes ?”

---

### 9.2 `Source d'artefacts screener`

C’est le dossier d’artefacts screener retenu comme **base d’analyse**.
Il sert à lire :
- recommandations,
- CSV de diagnostics,
- leaderboard,
- métadonnées de couverture.

Il est partagé avec la page `Overview` pour garder la même référence partout.

---

### 9.3 `Filtres opérateur`

Ce bloc sert à filtrer visuellement les résultats déjà chargés :
- symbole,
- secteur,
- candidats uniquement,
- score minimum,
- sentiment actif uniquement.

### Rôle
Ce n’est pas un recalcul du pipeline.
C’est un **filtre de lecture opérateur** sur les résultats disponibles.

---

## 10. Questions sur la page « Backtesting »

### 10.1 Onglet `Diagnose screener`

Lance `python -m backtesting diagnose-screener ...`

### But
Tester plusieurs réglages du screener sur une période passée pour comprendre :
- pourquoi il y a trop peu / trop de candidats,
- quels seuils semblent robustes,
- quels scénarios sont intéressants.

En bref : **diagnostic de tuning du screener**.

---

### 10.2 Onglet `Recommend screener`

Lance `python -m backtesting recommend-screener ...`

### But
Prendre les résultats du diagnostic screener existant et produire :
- des recommandations de scénarios,
- des leaders par objectif,
- un compromis exploitable.

En bref : **transformer les diagnostics en recommandations lisibles**.

---

### 10.3 Onglet `Calibrate sentiment`

Lance `calibrate-sentiment-weights`.

### But
Calibrer les poids :
- `sentiment_weight`
- `macro_sector_weight`

à partir des performances historiques et des forward returns.

En clair :
> “Quelle pondération du sentiment semble la plus utile historiquement ?”

---

### 10.4 Onglet `Walk-forward sentiment`

Lance `walk-forward-sentiment`.

### But
Faire une calibration sentiment plus rigoureuse, en séparant :
- période d’apprentissage,
- période de test hors échantillon,
- folds successifs.

En clair :
> “Est-ce que mon réglage sentiment tient hors échantillon, pas juste sur le passé appris ?”

---

### 10.5 Onglet `Calibration trimestrielle poids`

Lance `scripts/run_quarterly_weights_calibration.py`.

### But
Recalibrer périodiquement les poids de score sur les **4 derniers trimestres**.
La page parle de Sharpe / hit-ratio / IC.

Donc c’est une calibration plus macro des **poids de scoring**, pas seulement du sentiment brut.

---

## 11. À quoi sert la page « Parité Backtest ↔ Live » ?

Elle compare les décisions du monde :
- **live/paper réel**
- et **replay backtest**

pour une même date.

### Ce que la page montre
- score global de divergence,
- nombre de lignes match / divergence,
- détail par symbole,
- vue rolling sur plusieurs jours,
- top symboles divergents récurrents,
- relance du job de parité.

### Pourquoi c’est important
Cette page sert à détecter les drifts entre :
- ce que le système fait réellement en production,
- et ce que le replay historique pense qu’il aurait dû faire.

C’est une page d’**audit de cohérence**.

---

## 12. Questions sur la page « ML / Prédictions »

### 12.1 `Symbole à inspecter (artefacts)`

Cela veut dire :
> “Choisis le symbole dont tu veux lire les artefacts `modelFactory` sur disque.”

La page lit notamment :
- `config.json`
- `metrics.json`
- le routing des modèles

### Exemple
`Symbole: A, Champion servi: lstm_attention, Mode de sélection: auto_selected_champion, Decision threshold: 0.55`

Signifie :
- **Symbole `A`** : on inspecte les artefacts du ticker `A`
- **Champion servi = `lstm_attention`** : c’est ce modèle qui est actuellement routé pour l’inférence
- **Mode de sélection = `auto_selected_champion`** : il a été choisi automatiquement par la gouvernance challenger/champion
- **Decision threshold = 0.55** : il faut dépasser 0.55 de proba pour déclencher un signal long

---

### 12.2 `Routes d'inférence`, `Ranking challengers`, `Manifestes bruts`

#### `Routes d'inférence`
Montre comment le serving est routé :
- quel backend sert quoi,
- où sont les chemins d’artefacts,
- quel modèle est sélectionné.

#### `Ranking challengers`
Classement des modèles challengers :
- rang,
- score de sélection,
- statut,
- éligibilité,
- éventuelle raison d’exclusion.

#### `Manifestes bruts (config / metrics)`
Affichage brut des fichiers `config.json` et `metrics.json`.
C’est la source la plus proche de la vérité artefact.

---

### 12.3 Comment interpréter `Runs d'entraînement`

Ce tableau vient de `model_training_run`.
Il sert à lire l’historique des entraînements :
- quand le run a commencé,
- sur quel symbole,
- avec quel statut,
- dans quel contexte de training.

### Lecture simple
- cherche d’abord les statuts (`completed`, `failed`, etc.)
- regarde la récence du run
- puis compare avec les artefacts servis aujourd’hui

---

### 12.4 Comment interpréter `Métriques par symbole`

Ce tableau vient de `model_metrics`.
Il résume les métriques ML par symbole et par split (`val`, `test`, `wf`).

### Comment le lire
- compare les symboles entre eux,
- compare les splits,
- regarde si un symbole est bon en validation mais mauvais en test,
- surveille la stabilité hors échantillon.

### En clair
Un symbole avec une belle métrique `val` mais mauvaise `test` est suspect d’overfitting.

---

### 12.5 Comment interpréter `Audit serving ↔ gouvernance`

Ce tableau joint :
- `model_predictions`
- `model_governance`

pour vérifier si le modèle effectivement servi correspond bien au champion attendu.

### Colonnes importantes
- `served_model`
- `governance_champion_model`
- `governance_link_status`

### Statuts possibles
- `aligned` = tout est cohérent
- `missing_governance_snapshot`
- `prediction_missing_selected_model`
- `served_model_missing_in_governance`
- `served_model_differs_from_governance_champion`

### Lecture simple
Si ce tableau n’est pas aligné, cela veut dire :
> “Le modèle utilisé pour prédire n’est pas exactement celui que la gouvernance dit devoir servir.”

---

### 12.6 Comment interpréter `Gouvernance challengers / champion`

Ce tableau vient de `model_governance`.
Il contient notamment :
- `run_id`
- `symbol`
- `model_name`
- `rank`
- `is_selected_model`
- `selection_mode`
- `selection_metric`
- `selection_score`
- `selection_eligible`
- `eligibility_reason`
- `inference_backend`
- AUC / business scores selon split

### Comment le lire
1. repérer la ligne `is_selected_model = 1`
2. regarder `selection_mode`
3. comparer le champion aux challengers
4. vérifier si un challenger a été exclu pour raison d’éligibilité

### En version débutant
Ce tableau explique :
> “Quels modèles ont couru, lequel a gagné, et pourquoi.”

---

## 13. Questions sur la page « Paramètres / Santé »

## Bloc `Seuils diagnostic Alpha Scanner`

### 13.1 Impact du `contexte marché` pour les presets Alpha Scanner

Très important :
ce **n’est pas** le même “régime marché” que la page `Régime Marché`.

Ici, le contexte marché sert seulement à rendre les **seuils de diagnostic plus ou moins stricts**.

Options :
- `normal`
- `weak`
- `very_selective`

### Effet
- plus le marché est jugé faible/sélectif,
- plus on exige des quotes fraîches / bien couvertes,
- et un calendrier earnings plus complet.

Donc :
- `normal` = seuils de base
- `weak` = un peu plus strict
- `very_selective` = encore plus strict

### Conséquence pratique
Avec un contexte plus strict, la page de diagnostic passera plus facilement en orange/rouge si la qualité amont est moyenne.

---

### 13.2 Étape 4 — `Sync Latest Quotes`

#### `Quotes — couverture orange (%)`
Seuil sous lequel la couverture passe en warning.

#### `Quotes — couverture rouge (%)`
Seuil sous lequel la couverture passe en erreur.

#### `Quotes — âge orange (jours)`
Âge maximum toléré avant warning.

#### `Quotes — âge rouge (jours)`
Âge maximum toléré avant erreur.

### Lecture simple
- couverture faible = pas assez de quotes utiles
- âge élevé = quotes trop vieilles

---

### 13.3 Étape 5 — `Sync Earnings Calendar`

#### `Earnings — couverture orange (%)`
Seuil de warning sur la couverture du calendrier earnings.

#### `Earnings — couverture rouge (%)`
Seuil d’erreur.

#### `Earnings — horizon orange (jours)`
Si l’horizon futur disponible est trop court, warning.

#### `Earnings — horizon rouge (jours)`
Si encore plus court, erreur.

### Sens pratique
L’Alpha Scanner utilise un blackout earnings.
Si ton calendrier earnings ne regarde pas assez loin, ce blackout devient peu fiable.

---

## 14. Questions sur la page « Compliance & Audit »

Dans `Relancer un job de conformité` :

### `Pré-live checklist`
Lance le wrapper de recette pré-live.
Il vérifie notamment :
- secrets,
- accès Alpaca,
- kill switch,
- dry-run récent,
- drift ML,
- verrou pipeline IHM.

### `Audit chain`
Vérifie la chaîne d’audit / hash des décisions.
But : s’assurer que la piste d’audit n’a pas été rompue.

### `Scan CVE`
Scanne les dépendances Python pour détecter des vulnérabilités connues.

### `Vault rotation`
Vérifie l’âge et la rotation des secrets/clefs.

### `Rapport mensuel broker`
Génère un rapport mensuel broker (PDF/JSON selon le script).

### `Réconciliation broker`
Relance un calcul de réconciliation broker ↔ base locale.

---

## 15. Questions sur la page « Tax Compliance »

La page est actuellement en **mode démo** avec des lots de référence.
Elle n’est pas encore branchée en prod sur les `fills` réels.

### Paramètres / filtres du bloc principal
#### `Période — début`
Début de la période fiscale analysée.

#### `Période — fin`
Fin de la période analysée.

#### `Symbole (optionnel)`
Filtre sur un seul ticker.

#### `Compte`
Compte concerné par l’analyse.

### Comment les utiliser
- pour un contrôle trimestriel : choisir le trimestre,
- pour une vérification annuelle : choisir l’année fiscale,
- pour un litige sur une wash sale : filtrer un symbole précis.

### Ce que la page calcule
- nombre de lots,
- ajustements wash sale,
- perte non déductible,
- export CSV type 1099-B équivalent,
- détail des ajustements.

### À quoi ça sert pour la conformité fiscale
La page aide à repérer :
- les ventes avec perte non déductible,
- les lots de remplacement,
- les ajustements à reporter.

---

## 16. Questions sur la page « Sandbox health (30 j) »

Cette page sert à suivre la **stabilité de la sandbox nightly paper sur 30 jours glissants**.

Elle affiche :
- la streak verte,
- le nombre d’échecs,
- le nombre de succès,
- le nombre de jours observés,
- un calendrier par jour,
- le détail JSON d’un jour,
- le dernier échec,
- des boutons pour relancer des checks.

### En version simple
C’est la page qui répond à :
> “Est-ce que mon environnement sandbox/paper a été stable ces 30 derniers jours ?”

Très utile avant live : un environnement instable en sandbox est un mauvais signal.

---

## 17. Questions sur la page « Corporate Actions »

Cette page sert à suivre les événements corporate qui affectent le portefeuille :
- dividendes,
- splits,
- reverse splits,
- autres événements de corporate action.

### Ce qu’elle montre
- résumé par statut/type,
- lancement manuel de `status` ou `apply`,
- résumés métier persistants,
- dividendes cumulés,
- historique des runs,
- événements récents,
- applications récentes.

### En pratique
Elle sert surtout à vérifier que :
1. les événements ont bien été synchronisés,
2. ils ont bien été appliqués,
3. le cash ledger et les positions restent cohérents.

### Très important
Les corporate actions servent ici surtout à la **cohérence comptable / portefeuille**, pas à “corriger magiquement” tout l’historique de prix du backtest.

---

## 18. Résumé ultra-court des points les plus importants

Si tu devais retenir seulement 10 choses :

1. **Backtest ML** : danger de fuite si tu reconstruis le passé avec des modèles entraînés aujourd’hui.
2. **Mode `pipeline`** : strict pour `stock_scores_history`, donc plus sûr côté PIT.
3. **Sentiment** : oui, il peut être reconstruit jour par jour sur la période backtestée, mais pas forcément avec un signal non neutre chaque jour.
4. **Coverage** : `coverage.json` ne mesure que le dernier run de couverture, pas “tous les tests existants”.
5. **Overview / Source screener active** : c’est juste le dossier d’artefacts choisi comme référence commune.
6. **Execution hors RTH** : ordres en file avant l’ouverture, utile pour swing overnight.
7. **Auto rebalance** : corrige automatiquement certains écarts broker ↔ cible.
8. **Risk dry-run** : ne persiste ni `risk_decisions` ni `portfolio_targets`.
9. **WinError 123 sur kill switch** : c’était un bug Windows de nom de dossier côté IHM ; le stockage des runs utilise désormais un alias filesystem compatible tout en gardant le `step_key` métier brut.
10. **Parité Backtest ↔ Live** : page d’audit de cohérence entre le replay et la vraie prod.

---

## 19. Remarque finale

Certaines pages de manuel dans `doc/manuel/` sont légèrement en retard par rapport au code actuel (par exemple certains blocs aujourd’hui exposés dans l’IHM alors que l’ancienne doc les présentait encore comme “gap connu”).

Quand il y avait divergence, j’ai privilégié :
1. **le code actuel**,
2. puis les **requêtes / services réellement appelés**,
3. puis la **doc** comme aide pédagogique.

