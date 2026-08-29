# α-Trade — Synthèse anti-overfitting et protocole de validation OOS

**Date : 2026-08-22**  
**Objet :** conserver une trace méthodologique des risques d'overfitting accumulés pendant les travaux de recherche, définir ce qui peut encore être considéré comme validé, et établir les règles à suivre avant toute nouvelle optimisation.

---

## 1. Résumé exécutif

Les travaux réalisés sur α-Trade ont apporté beaucoup d'informations utiles : correction de bugs, amélioration de la parité backtest ↔ production, attribution causale des mécanismes de risque, amélioration de `capital_preservation` avec CP-V2, étude du sleeve short, tests de force-close et stress tests.

Cependant, **2022 et 2025 ont maintenant été observées et réutilisées un grand nombre de fois** pour comprendre, concevoir, modifier et sélectionner des règles.

Par conséquent :

> **2022 et 2025 ne doivent plus être considérées comme de véritables périodes OOS indépendantes pour les règles de stratégie/risk management qui ont été conçues à partir de leur observation.**

Cela ne signifie pas que les résultats obtenus sont faux ou inutiles. Cela signifie que leur rôle méthodologique a changé :

- ils restent excellents pour le **diagnostic** ;
- ils restent utiles pour l'**attribution causale** ;
- ils restent utiles pour les **tests de non-régression** ;
- ils restent utiles pour vérifier la **parité backtest ↔ production** ;
- ils restent utiles comme **stress scenarios connus** ;
- mais ils ne doivent plus servir à choisir librement le paramètre qui maximise la performance.

Le principal risque n'est donc pas nécessairement un overfitting du modèle ML B25 lui-même. Il s'agit surtout d'un :

- **strategy overfitting** ;
- **backtest overfitting** ;
- **research overfitting** ;
- ou, autrement dit, d'une consommation progressive de l'information OOS par les décisions humaines de recherche.

La priorité future doit être de **geler une version candidate**, puis de rechercher de nouvelles preuves indépendantes : walk-forward historique avec modèles recalibrés à chaque cutoff, univers holdout complémentaire, stress tests pré-enregistrés, puis forward OOS réel.

---

# 2. Les différents types d'overfitting à distinguer

## 2.1 Overfitting du modèle ML

C'est le cas classique : le modèle apprend trop précisément le train et généralise mal.

Exemples :

- trop de features ;
- hyperparamètres excessivement optimisés ;
- sélection répétée du champion sur la même validation ;
- fuite temporelle ;
- feature calculée avec information future ;
- univers survivorship-biased ;
- tuning indirect sur la période censée être OOS.

Ce risque doit être traité par les procédures ML habituelles : PIT, purge, walk-forward, validation temporelle, holdout, stabilité de l'IC, etc.

---

## 2.2 Overfitting de stratégie

Même si le modèle ML reste complètement gelé, la stratégie peut être overfittée.

Exemple :

1. B25 reste inchangé.
2. On observe 2022.
3. On modifie les shorts.
4. On observe le résultat.
5. On modifie CP.
6. On observe 2025.
7. On modifie la release.
8. On teste plusieurs force-close.
9. On choisit celui qui fonctionne le mieux.

Le modèle ML n'a jamais été réentraîné.

Pourtant, la **stratégie complète** a appris indirectement 2022/2025.

---

## 2.3 Overfitting du risk management

C'est particulièrement important pour α-Trade.

Les paramètres concernés comprennent notamment :

- seuil B4 ;
- pourcentage de force-close ;
- sélection des positions liquidées ;
- CP ;
- budgets par side ;
- durée de release ;
- hystérésis ;
- max gross ;
- max positions ;
- levier ;
- concentration ;
- stops ;
- TP ;
- time stop ;
- trailing ;
- règles long/short.

Une combinaison de paramètres peut parfaitement expliquer 2022 et 2025 tout en étant mauvaise sur la prochaine crise.

---

## 2.4 Overfitting par recherche humaine

C'est le risque le plus subtil.

Même sans sweep automatisé, chaque observation influence la prochaine hypothèse.

Exemple :

> « Les shorts gagnants 2022 ont été bloqués par le gross cap. »

On crée CP-V2.

Puis :

> « L'aftermath >10 jours coûte trop. »

On ajoute une release plus rapide.

Puis :

> « La liquidation totale rate le V-rebound. »

On conserve KEEP ou WORST_50.

Chaque décision peut être rationnelle et causalement motivée. Mais collectivement, le système incorpore de plus en plus d'information provenant des mêmes années.

---

# 3. Pourquoi 2022 et 2025 sont désormais partiellement “consommées”

Ces périodes ont servi à de nombreux travaux.

## 2022

Parmi les analyses réalisées :

- comportement bear ;
- contribution long/short ;
- replay recherche ;
- comparaison PROD-parity ;
- CP ON/OFF ;
- attribution causale CP ;
- développement CP-V2 ;
- analyse des shorts pendant/hors CP ;
- étude des régimes SPY ;
- long-only ;
- stress d'exposition ;
- B4 ;
- force-close ;
- analyse de drawdown ;
- analyse de concentration.

## 2025

Parmi les analyses réalisées :

- crash/V-recovery ;
- CP ON/OFF ;
- CP-V2 ;
- récupération au pic ;
- long-only ;
- shorts ;
- force-close à −8 % ;
- stress à exposition supérieure ;
- vrai trip B4 −15 % ;
- KEEP / WORST_50 / ALL ;
- attribution position par position ;
- ADD après trip.

Ces années sont donc devenues des **research sets très riches**.

---

# 4. Ce qui reste valide malgré cela

Le risque d'overfitting ne signifie pas qu'il faut jeter les travaux.

Certaines catégories de résultats restent particulièrement solides.

## 4.1 Corrections de bugs

Exemples :

- leakage ;
- mauvaise propagation des paramètres ;
- mapping secteur ;
- problème de feature contract ;
- mauvais chargement de données ;
- incohérence backtest/prod.

Corriger un bug n'est pas une optimisation de performance.

**Risque d'overfit : très faible.**

---

## 4.2 Point-in-time et absence de look-ahead

Tout travail qui améliore :

- PIT ;
- timestamping ;
- purge ;
- availability dates ;
- corporate actions ;
- univers historique ;
- neutralisation causale ;

améliore la validité scientifique du système.

**Risque d'overfit : très faible.**

---

## 4.3 Parité backtest ↔ production

Le harness de parité CP-V2 et les vérifications de propagation des contraintes sont des travaux d'ingénierie.

Ils répondent à :

> « Est-ce que la production exécute réellement ce qui a été testé ? »

Ils ne répondent pas à :

> « Cette règle est-elle profitable dans le futur ? »

**Risque d'overfit de performance : très faible.**

---

## 4.4 Attribution causale

L'attribution CP a été particulièrement utile car elle a expliqué *pourquoi* une différence apparaissait.

Exemple conceptuel :

- entrées empêchées ;
- sizing ;
- composition ;
- lifecycle ;
- contribution long ;
- contribution short ;
- proximité temporelle du régime CP.

Une explication causale est plus crédible qu'un simple classement de backtests.

Mais elle ne transforme pas la période analysée en nouvelle OOS.

---

# 5. Évaluation des principaux chantiers

| Chantier | Risque actuel | Lecture |
|---|---:|---|
| PIT / bugs / data integrity | Très faible | ingénierie |
| Parité PROD/backtest | Très faible | indispensable |
| Attribution causale CP | Faible | mécanisme explicatif |
| CP ON/OFF | Faible à moyen | comparaison large |
| CP-V2 — principe side-aware | Moyen | mécanisme plausible et confirmé causalement |
| CP-V2 — valeurs exactes des budgets | Moyen à élevé | paramètres précis |
| Release J+6 | Moyen à élevé | valeur précise, peu d'épisodes |
| Structure 6L/2S | Moyen | plausible, mais doit être revalidée si modèle/univers change |
| Shorts permanents | Moyen | supportés par 2022, échantillon limité |
| Gates shorts CP/SPY rejetés | Moyen | diagnostic utile mais basé sur peu d'années |
| Long-only | Moyen | différence structurelle claire, mais période limitée |
| Force-close −8 % rejeté | Faible à moyen | V-recovery montre un mécanisme crédible |
| B4 −15 % | Moyen | peu de vrais trips |
| ALL au trip −15 % rejeté | Moyen | mauvais dans l'épisode disponible |
| WORST_50 | Élevé | un seul épisode indépendant |
| “50 %” comme valeur optimale | Très élevé | non démontré |
| Levier optimal | Élevé si tuné sur 2022/2025 | nécessite nouvelle validation |
| Futurs paliers DD 15/20/25 | Très élevé si optimisés sur les mêmes périodes | attention au data mining |

---

# 6. Cas CP-V2 : comment interpréter correctement le résultat

CP-V2 constitue l'un des résultats les plus intéressants de la recherche.

Le mécanisme identifié est cohérent :

1. CP était déjà directionnel sur les nouvelles entrées.
2. Le gross cap global pouvait néanmoins limiter indirectement la capacité short.
3. Les longs existants consommaient le budget.
4. Le sleeve short était particulièrement utile en bear.
5. Une séparation des budgets par side corrige ce défaut.
6. Une release plus courte réduit l'aftermath.

Les résultats observés sur 2022 et 2025 sont encourageants.

Cependant :

> CP-V2 a été conçu après observation de ces mêmes périodes.

Par conséquent, 2022/2025 constituent maintenant :

**discovery + calibration + validation mécanique**

et non :

**validation OOS indépendante finale.**

Il faut distinguer deux niveaux de confiance.

### Principe CP-V2

Le principe « préserver une capacité short séparée du budget long » possède une justification économique et causale.

**Confiance : raisonnable.**

### Paramètres exacts CP-V2

Par exemple :

- budget long exact ;
- budget short exact ;
- gross exact ;
- release exacte à J+6 ;
- hystérésis exacte.

Ces valeurs nécessitent davantage d'observations indépendantes.

**Confiance : plus faible.**

---

# 7. Cas B4 et WORST_50

Le circuit breaker B4 joue le rôle d'airbag.

La distinction essentielle est :

- CP = de-risking courant ;
- B4 = catastrophe ;
- force-close = action exceptionnelle au trip.

Le seuil −15 % n'est pas fréquemment atteint dans la configuration normale.

Pour provoquer des trips, il a fallu augmenter l'exposition dans les stress tests.

L'épisode réellement étudié correspond essentiellement à la crise 2025.

Par conséquent :

> **n = 1 épisode de marché indépendant.**

C'est insuffisant pour déterminer scientifiquement un pourcentage optimal de liquidation.

### Ce que E45 permet de dire

Il fournit des preuves contre :

**CLOSE_ALL / 100 %.**

La liquidation totale a détruit beaucoup de performance sans améliorer suffisamment l'ADD.

Il fournit également une hypothèse intéressante :

**WORST_50 semble préférable à ALL.**

### Ce que E45 ne permet PAS de dire

Il ne permet pas d'affirmer :

> « 50 % est optimal. »

Ni :

> « Les pires PnL sont toujours les bonnes positions à liquider. »

Le cas OBDC montre précisément le problème : une position fortement perdante au trip peut ensuite récupérer fortement.

Donc `0.5` doit être considéré comme :

> **valeur provisoire défendable, pas paramètre statistiquement validé.**

---

# 8. Le piège du sweep de paramètres

À partir de maintenant, éviter les recherches du type :

```text
DD breaker:
10 %
11 %
12 %
13 %
...
25 %
```

puis sélectionner la meilleure equity curve.

Même problème avec :

```text
force_close_pct:
0.10
0.20
0.30
...
1.00
```

ou :

```text
release:
1 jour
2 jours
...
20 jours
```

Cela produit facilement un optimum historique qui n'a aucune robustesse future.

---

# 9. Règle de pré-enregistrement

Avant un nouveau test, écrire :

1. **Hypothèse**
2. **Mécanisme économique**
3. **Paramètre testé**
4. **Valeurs testées**
5. **Métrique principale**
6. **Gates de succès**
7. **Conditions de rejet**
8. **Périodes utilisées**
9. **Statut de ces périodes : train / calibration / OOS / stress**
10. **Décision qui sera prise selon le résultat**

Et seulement ensuite lancer les runs.

Cela réduit fortement les degrés de liberté du chercheur.

---

# 10. Freeze recommandé

Une fois une version candidate jugée suffisamment bonne, créer un **FREEZE**.

Exemple conceptuel :

```text
MODEL
  B25

UNIVERSE
  univers courant

PORTFOLIO
  6L / 2S

SIZING
  configuration ATR actuelle

MARKET REGIME
  CP-V2

CIRCUIT BREAKER
  B4

TRIP
  15 %

FORCE CLOSE
  WORST_50 provisoire

LIFECYCLE
  TP / stop / time stop actuellement validés

COST MODEL
  coûts canoniques

VERSION
  candidate_v1
```

À partir du freeze :

> **Ne plus modifier la configuration à partir de 2022/2025.**

Ces périodes deviennent des scénarios connus de regression/stress.

---

# 11. Ce qu'on peut encore faire sur 2022/2025 après freeze

Autorisé :

- vérifier qu'un refactoring ne change pas le résultat ;
- diagnostiquer un bug ;
- vérifier la parité live/backtest ;
- analyser un incident ;
- reproduire une attribution ;
- vérifier les logs ;
- tester la résistance technique ;
- vérifier que les règles restent appliquées.

À éviter :

- chercher le meilleur seuil ;
- choisir le meilleur leverage ;
- optimiser un stop ;
- sélectionner le meilleur ratio L/S ;
- modifier CP parce que le rendement 2022 augmente ;
- choisir un force-close parce que 2025 l'aime davantage.

---

# 12. Comment récupérer de nouvelles preuves OOS

## 12.1 Solution privilégiée : walk-forward historique complet

C'est probablement la méthode la plus importante.

L'idée est de reconstruire ce qu'aurait réellement connu le système à chaque date.

Exemple :

```text
Modèle M2019
Train <= 2019
Test 2020

Modèle M2020
Train <= 2020
Test 2021

Modèle M2021
Train <= 2021
Test 2022

Modèle M2022
Train <= 2022
Test 2023

Modèle M2023
Train <= 2023
Test 2024

Modèle M2024
Train <= 2024
Test 2025
```

Pour chaque test :

- aucune donnée future ;
- features PIT ;
- univers PIT ;
- coûts réalistes ;
- même stratégie gelée ;
- aucun tuning après observation du fold.

Cela produit plusieurs pseudo-OOS temporels.

---

# 13. Attention : 2022 ne redevient pas automatiquement OOS

Supposons qu'on crée maintenant un modèle entraîné seulement jusqu'en 2021 et qu'on rejoue 2022.

Pour **le modèle ML**, 2022 peut être OOS.

Mais pour **la stratégie/risk management**, nous connaissons déjà énormément 2022.

Donc il faut distinguer :

```text
ML OOS = oui
Strategy OOS = non
```

Le résultat reste utile pour tester la généralisation du modèle, mais pas comme validation totalement indépendante de CP-V2/B4/etc.

---

# 14. Univers holdout

Une autre idée est de tester sur un univers similaire mais différent.

C'est utile, notamment pour détecter :

- dépendance à quelques symboles ;
- concentration cachée ;
- alpha spécifique à l'univers ;
- fragilité sectorielle ;
- dépendance à la liquidité.

Mais un univers holdout ne remplace pas le holdout temporel.

Pourquoi ?

Parce que les symboles différents traversent les mêmes :

- taux ;
- VIX ;
- crashs ;
- régimes SPY ;
- politique monétaire ;
- événements macro.

Donc :

> **univers holdout = preuve complémentaire, pas substitut au temporal OOS.**

---

# 15. Forward OOS réel

La preuve la plus forte reste le futur.

Une fois la stratégie gelée :

- aucun changement opportuniste ;
- predictions enregistrées avant résultat ;
- ordres simulés ou live ;
- coûts réels ;
- comparaison avec attentes ;
- analyse uniquement après accumulation suffisante.

Chaque nouvelle période future augmente la crédibilité.

---

# 16. Shadow mode recommandé

Avant d'augmenter le capital ou le levier :

1. geler la version ;
2. exécuter en shadow/paper ;
3. stocker chaque décision ;
4. stocker les contraintes ;
5. stocker les prédictions ;
6. stocker le régime ;
7. stocker les ordres théoriques ;
8. ne jamais reconstruire après coup les décisions manquantes.

Ainsi, la validation future devient réellement causale.

---

# 17. Leverage : traitement anti-overfit

Les résultats connus indiquent qu'augmenter l'exposition ne garantit pas un rendement supérieur.

Dans les stress tests E45 :

- 2022 a bénéficié d'une exposition supérieure ;
- 2025 a atteint le breaker −15 % et la performance s'est détériorée.

Donc le levier doit être considéré comme un **nouveau paramètre de risque**, pas comme du rendement gratuit.

## Mauvaise méthode

Tester 20 niveaux de leverage et choisir le meilleur CAGR.

## Meilleure méthode

Pré-spécifier quelques niveaux économiquement significatifs.

Exemple conceptuel :

```text
L0 = sizing actuel
L1 = exposition intermédiaire
L2 = exposition élevée
L3 = stress / plafond
```

Mesurer :

- CAGR ;
- MaxDD ;
- Sharpe ;
- Sortino ;
- Calmar ;
- worst month ;
- worst 3m ;
- trips B4 ;
- temps passé en CP ;
- turnover ;
- coût ;
- gross/net ;
- margin utilization ;
- recovery ;
- Expected Shortfall ;
- performance long/short.

La question n'est pas :

> « Quel niveau donne le meilleur rendement historique ? »

Mais :

> « Quel niveau offre une amélioration robuste du rendement sans transformer B4 en mécanisme courant ? »

---

# 18. DD maximum : ne pas augmenter le seuil simplement pour permettre plus de levier

Un raisonnement dangereux serait :

```text
DD historique = 8 %
breaker = 15 %

donc :
augmentons le leverage

puis si DD > 15 % :
passons le breaker à 25 %
```

Cela revient à déplacer le filet parce que le système prend plus de risque.

Le seuil de catastrophe doit être défini par :

- tolérance économique ;
- survie du compte ;
- risque de ruine ;
- margin requirements ;
- perte acceptable ;
- récupération nécessaire ;
- capital réellement supportable.

Pas simplement par optimisation du CAGR historique.

---

# 19. Paliers de drawdown

Une structure du type :

```text
DD 15 % → réduction partielle
DD 20 % → réduction supplémentaire
DD 25 % → réduction forte
```

peut avoir du sens architecturalement.

Mais elle crée de nombreux degrés de liberté :

- seuil 1 ;
- réduction 1 ;
- seuil 2 ;
- réduction 2 ;
- seuil 3 ;
- réduction 3 ;
- règles de reprise ;
- hysteresis ;
- side selection ;
- ordre de liquidation.

Avec seulement quelques épisodes, l'overfit peut devenir énorme.

Par conséquent, si cette architecture est étudiée :

1. pré-enregistrer les paliers ;
2. ne pas faire de sweep fin ;
3. utiliser des stress scenarios multiples ;
4. tester des épisodes indépendants ;
5. privilégier la robustesse à l'optimum historique.

---

# 20. Changement majeur de modèle ou d'univers

Un nouveau modèle ou un nouvel univers peut invalider les calibrations actuelles.

Pourquoi ?

Parce qu'il peut modifier :

- fréquence des signaux ;
- distribution des scores ;
- hit rate ;
- turnover ;
- holding period ;
- volatilité ;
- corrélation ;
- concentration ;
- beta ;
- exposition sectorielle ;
- long/short asymmetry ;
- coûts ;
- drawdown ;
- comportement en régime.

Par conséquent, après changement majeur :

> **les paramètres de stratégie et de risque doivent être considérés comme candidats à recalibration.**

Cela ne signifie pas qu'il faut automatiquement tout changer.

Cela signifie qu'il faut **revalider**.

---

# 21. Paramètres à revalider après changement majeur

## Modèle / signal

- horizon ;
- calibration des scores ;
- thresholds ;
- ranking ;
- top/bottom selection ;
- IC ;
- spread top-bottom ;
- stabilité temporelle ;
- long/short asymmetry.

## Portfolio construction

- nombre de longs ;
- nombre de shorts ;
- max positions ;
- weighting ;
- gross ;
- net ;
- sector caps ;
- symbol caps ;
- concentration.

## Sizing

- ATR risk ;
- risk per trade ;
- min/max notional ;
- leverage ;
- cash reserve ;
- margin usage.

## Lifecycle

- initial stop ;
- trailing ;
- TP ;
- time stop ;
- intrabar assumptions.

## Risk regime

- CP trigger ;
- CP budgets ;
- side budgets ;
- release ;
- hysteresis ;
- relapse.

## Catastrophe

- B4 ;
- DD threshold ;
- force-close ;
- force-close percentage ;
- selection method ;
- recovery logic.

## Costs

- commission ;
- spread ;
- slippage ;
- borrow ;
- margin interest ;
- liquidity assumptions.

Tous ne doivent pas forcément être modifiés, mais tous doivent être **audités**.

---

# 22. Hiérarchie de confiance recommandée

## Niveau A — très forte confiance

- absence de look-ahead ;
- PIT ;
- corrections de bugs ;
- parité live/backtest ;
- cohérence comptable ;
- logging ;
- risk limits techniques.

## Niveau B — confiance raisonnable

- architecture long/short ;
- principe CP side-aware ;
- B4 comme filet catastrophe ;
- réduction d'exposition en stress.

## Niveau C — à confirmer

- 6L/2S exact ;
- budgets CP exacts ;
- durée de release exacte ;
- niveau de gross optimal ;
- sizing précis.

## Niveau D — expérimental

- WORST_50 exact ;
- −15 % comme seuil optimal ;
- éventuels paliers 15/20/25 ;
- levier optimal ;
- sélection sophistiquée de positions au trip.

Cette hiérarchie doit apparaître dans la documentation afin qu'un futur mainteneur ne traite pas tous les paramètres comme également prouvés.

---

# 23. Journal des expériences

Créer un registre unique.

Exemple :

| ID | Hypothèse | Données | Paramètres | Résultat | Décision | Statut données |
|---|---|---|---|---|---|---|
| E39 | attribution CP | 2022/2025 | CP ON/OFF | mécanisme identifié | continuer | research |
| E40 | CP-V2 | 2022/2025 | side budgets | positif | candidate | calibration |
| E44 | close à −8 % | 2025 | KEEP/ALL/LONG | NO-GO | rejet | research |
| E45 | B4 airbag | stress 2025 | KEEP/50/ALL | 50 provisoire | conserver | stress |

Le but est de savoir exactement combien de fois une période a influencé une décision.

---

# 24. Versionner les décisions, pas seulement le code

Pour chaque candidate production, enregistrer :

```text
strategy_version
model_batch
universe_version
feature_contract
config_hash
risk_policy_version
cost_model_version
data_snapshot
git_commit
training_cutoff
validation_period
research_periods_seen
true_holdout_periods
```

Ainsi, il devient possible de répondre plusieurs mois plus tard à :

> « Cette règle connaissait-elle déjà cette période lorsqu'elle a été choisie ? »

---

# 25. Classification obligatoire des données

Chaque période doit avoir un statut explicite.

Valeurs recommandées :

```text
TRAIN
ML_VALIDATION
STRATEGY_CALIBRATION
KNOWN_RESEARCH
STRESS
PSEUDO_OOS
TRUE_OOS
FORWARD_OOS
```

Une même période peut avoir des statuts différents selon la couche.

Exemple 2022 :

```text
ML layer:
possible OOS pour un modèle cutoff 2021

Risk-management layer:
KNOWN_RESEARCH
```

Cette distinction est fondamentale.

---

# 26. Critère de promotion en production

Une amélioration ne devrait pas être promue uniquement parce que :

```text
Return_new > Return_old
```

Elle devrait satisfaire plusieurs dimensions.

Exemple de gate :

### Alpha

- performance nette positive ;
- IC/spread cohérent ;
- stabilité long/short.

### Risque

- MaxDD acceptable ;
- Expected Shortfall acceptable ;
- pas d'explosion des worst windows ;
- pas d'augmentation incontrôlée des trips.

### Robustesse

- plusieurs folds ;
- plusieurs régimes ;
- univers holdout si possible ;
- stress costs ;
- stress liquidity ;
- perturbation des paramètres.

### Implémentation

- PIT ;
- parité ;
- aucune divergence live/backtest ;
- logs complets ;
- rollback disponible.

---

# 27. Test de sensibilité plutôt que recherche d'optimum

Un bon paramètre doit fonctionner dans un voisinage.

Exemple :

Si une stratégie fonctionne uniquement avec :

```text
release = exactement 5 jours
```

mais s'effondre à :

```text
4 jours
6 jours
```

c'est inquiétant.

En revanche :

```text
4 jours → correct
5 jours → bon
6 jours → correct
```

indique un plateau robuste.

Le but d'un test de sensibilité est de vérifier un **plateau**, pas de sélectionner le maximum.

---

# 28. Robustesse économique

Toujours demander :

> « Pourquoi cette règle devrait-elle fonctionner en dehors de l'échantillon ? »

Exemples de mécanismes plausibles :

- diversification long/short ;
- réduction du gross pendant stress ;
- capacité short préservée ;
- contrôle de concentration ;
- réduction de risque après rupture majeure.

Exemples beaucoup plus fragiles :

- « 17 % de DD marche mieux que 16 et 18 » ;
- « release exactement 7 jours maximise le CAGR » ;
- « force-close 43 % donne le meilleur Sharpe ».

Plus le paramètre est précis sans mécanisme économique fort, plus le risque d'overfit augmente.

---

# 29. Ce qu'il faut faire si un nouveau test échoue

Ne pas immédiatement ajuster le paramètre pour sauver le test.

Procédure :

1. vérifier data integrity ;
2. vérifier PIT ;
3. vérifier parité ;
4. attribuer la perte ;
5. déterminer si le mécanisme attendu est absent ;
6. décider si l'hypothèse est réfutée ;
7. documenter le NO-GO.

Un **NO-GO propre** apporte de l'information.

Chercher continuellement une variante jusqu'à obtenir PASS détruit progressivement la valeur OOS.

---

# 30. Règle du nombre d'essais

Pour chaque chantier, conserver :

```text
nombre d'hypothèses essayées
nombre de variantes
nombre de périodes inspectées
nombre de métriques consultées
nombre de décisions modifiées après résultat
```

Plus ces nombres augmentent, plus la performance historique doit être décotée mentalement.

Une amélioration de +1 % après 50 variantes n'a pas la même valeur qu'une amélioration de +1 % obtenue avec une hypothèse pré-enregistrée unique.

---

# 31. Recommandation immédiate pour α-Trade

À ce stade :

## Étape 1 — Freeze

Créer une candidate gelée avec les composants actuellement retenus.

## Étape 2 — Marquer 2022 et 2025

Les marquer :

```text
KNOWN_RESEARCH / STRATEGY_CALIBRATION
```

pour les couches de stratégie et risk management.

## Étape 3 — Stopper l'optimisation libre

Ne plus utiliser ces années pour choisir le meilleur seuil ou le meilleur paramètre.

## Étape 4 — Construire un vrai protocole walk-forward

Reformer des modèles historiques avec cutoff causal.

## Étape 5 — Univers holdout

Ajouter une validation cross-sectional indépendante si possible.

## Étape 6 — Stress tests

Conserver des scénarios prédéfinis sans optimiser les paramètres sur chacun.

## Étape 7 — Forward test

Accumuler des décisions réellement produites avant observation des résultats.

---

# 32. Checklist avant chaque nouveau chantier

Avant lancement :

- [ ] L'hypothèse est écrite.
- [ ] Le mécanisme économique est expliqué.
- [ ] Les paramètres sont pré-spécifiés.
- [ ] Les métriques sont pré-spécifiées.
- [ ] Le gate PASS/FAIL est écrit.
- [ ] Les périodes utilisées sont classifiées.
- [ ] Le nombre de variantes est limité.
- [ ] On sait quelles données ont déjà été vues.
- [ ] Le code est PIT.
- [ ] Les coûts sont réalistes.
- [ ] La baseline est actuelle et reproductible.
- [ ] Le test ne dépend pas d'une baseline stale.
- [ ] Le résultat sera documenté même s'il est négatif.

Après lancement :

- [ ] Aucun paramètre n'est modifié avant lecture complète.
- [ ] Attribution causale si résultat surprenant.
- [ ] Vérification parité si promotion envisagée.
- [ ] Sensibilité autour du candidat.
- [ ] Mise à jour du registre d'expériences.
- [ ] Mise à jour du statut des données consommées.
- [ ] GO / NO-GO explicite.
- [ ] Pas de “nouveau sweep” improvisé après un NO-GO.

---

# 33. Checklist avant promotion PROD

- [ ] Modèle/version gelés.
- [ ] Univers/version gelés.
- [ ] Feature contract gelé.
- [ ] Config hash enregistré.
- [ ] Cutoff d'entraînement enregistré.
- [ ] Toutes les périodes utilisées documentées.
- [ ] Validation temporelle suffisante.
- [ ] Stress coûts.
- [ ] Stress exposition.
- [ ] Stress liquidité.
- [ ] Attribution long/short.
- [ ] Concentration auditée.
- [ ] MaxDD acceptable.
- [ ] Expected Shortfall acceptable.
- [ ] B4 testé mécaniquement.
- [ ] Parité backtest/live.
- [ ] Tests unitaires.
- [ ] Tests d'intégration.
- [ ] Shadow mode si changement majeur.
- [ ] Plan de rollback.
- [ ] Aucun paramètre sélectionné uniquement pour améliorer une année connue.

---

# 34. Checklist après changement radical de modèle/univers

Considérer la calibration précédente comme **non automatiquement transférable**.

Revalider au minimum :

- [ ] distribution des scores ;
- [ ] IC ;
- [ ] spread top-bottom ;
- [ ] horizons ;
- [ ] fréquence des signaux ;
- [ ] turnover ;
- [ ] nombre de positions ;
- [ ] ratio long/short ;
- [ ] gross/net ;
- [ ] concentration symbole ;
- [ ] concentration secteur ;
- [ ] beta/factors ;
- [ ] ATR/risk sizing ;
- [ ] leverage ;
- [ ] stops ;
- [ ] TP ;
- [ ] time stop ;
- [ ] CP ;
- [ ] budgets CP par side ;
- [ ] release/hysteresis ;
- [ ] B4 ;
- [ ] force-close ;
- [ ] coûts ;
- [ ] spread/slippage ;
- [ ] capacité/liquidité ;
- [ ] parité live/backtest.

---

# 35. Principe de gouvernance pour le futur mainteneur

La règle centrale est :

> **Une equity curve historique n'est pas une preuve indépendante si les règles ont été conçues en regardant cette equity curve.**

Toujours demander :

1. Quand cette règle a-t-elle été conçue ?
2. Quelles données avaient déjà été vues ?
3. Quels paramètres ont été essayés ?
4. Quel était le gate avant de voir le résultat ?
5. Existe-t-il une période réellement indépendante ?
6. Le mécanisme est-il économiquement plausible ?
7. La performance est-elle robuste autour du paramètre ?
8. Le comportement existe-t-il sur plusieurs régimes ?

---

# 36. Conclusion

Les travaux réalisés jusqu'ici ne doivent pas être considérés comme perdus à cause du risque d'overfitting.

Au contraire, ils ont permis :

- d'éliminer plusieurs erreurs ;
- d'améliorer la fidélité production ;
- de comprendre le comportement long/short ;
- d'identifier des mécanismes causaux ;
- d'écarter plusieurs mauvaises idées ;
- d'améliorer CP ;
- de comprendre les limites de B4 et du force-close.

Mais le niveau de connaissance accumulé sur 2022 et 2025 impose maintenant une discipline différente.

La bonne transition est :

```text
EXPLORATION
      ↓
COMPRÉHENSION
      ↓
CALIBRATION
      ↓
FREEZE
      ↓
VALIDATION INDÉPENDANTE
      ↓
SHADOW / FORWARD OOS
      ↓
PRODUCTION
```

et non :

```text
BACKTEST
 ↓
MODIFICATION
 ↓
BACKTEST
 ↓
MODIFICATION
 ↓
BACKTEST
 ↓
jusqu'à obtenir une courbe parfaite
```

Le prochain gain de confiance ne viendra probablement pas d'un paramètre historique encore meilleur.

Il viendra de la capacité de la configuration **gelée** à survivre à des données qu'elle n'a jamais utilisées pour être conçue.

---

## Mémo en une phrase

> **2022/2025 peuvent continuer à servir de laboratoires et de stress tests connus, mais plus de juges OOS indépendants ; les prochaines décisions importantes doivent être pré-enregistrées et confirmées par walk-forward causal, holdout complémentaire et surtout forward OOS.**
