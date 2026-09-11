# PROMPT DE RECHERCHE — Multi-Horizon Oracle + Rolling Confirmation + Dynamic Exit

> **Version amendée et gelée — 10 septembre 2026**
> Les règles de cette section prévalent sur toute formulation ambiguë plus bas.
> La campagne commence par un POC *signal-level* isolé. Aucune modification du
> backtest, du live, du lifecycle ou des tables de production n'est autorisée
> avant un verdict `GO_RESEARCH` reproductible.

## A. Contrat exécutable de la phase 1

### A.1 Question réellement testée

L'Oracle reste un modèle d'**amplitude**, jamais un modèle de direction. Les
stratégies `S0` à `S5` sont donc explicitement des diagnostics **LONG-only** :
elles mesurent si le chemin de prix et la persistance de l'amplitude permettent
de conserver ou couper une exposition longue déjà prise. Elles ne prétendent
pas résoudre `D1` contre `D10` à la date initiale.

Une variante directionnelle distincte est obligatoire :

```text
S6-LS — confirmation retardée symétrique
J         : aucune position
close J+5 : le signe du rendement observé choisit LONG ou SHORT
            et l'Oracle restant doit encore être confirmé
open J+6  : entrée dans le sens observé
open suivant la 20e séance depuis l'origine : sortie forcée
```

Cette variante répond à la question « le prix peut-il révéler causalement le
sens après cinq séances ? », au prix assumé d'une entrée plus tardive.

### A.2 Horloge causale unique

```text
close J   : scores Oracle observables et signal construit
open J+1  : exécution initiale éventuelle
close de la 5e/10e/15e séance de détention : checkpoint observable
open suivant : exécution d'une décision prise au checkpoint
open suivant la 20e séance de détention : liquidation théorique
```

Les stops et TP intraday ne sont pas appliqués dans l'event study de phase 1.
Ils seront appliqués uniquement dans le replay portefeuille de phase 2, aux
positions encore ouvertes. Il faut alors publier deux populations : cohorte
d'origine fixe et survivants « at risk ».

### A.3 Contrat des quatre Oracle

La campagne est invalide si les quatre batches ne partagent pas : univers et
empreinte d'univers, période, profil de features, paramètres Walk-Forward,
folds/purge PIT et architecture comparable. L'horizon déclaré dans chaque
artefact doit être exactement H5, H10, H15 ou H20. L'analyse se fait sur
l'intersection `(date, symbol)` commune aux quatre batches et publie la perte de
couverture induite.

Les protections déjà présentes dans `modelFactory/oracle/walk_forward.py`
(purge selon l'horizon et disponibilité des features) doivent être auditées,
pas réimplémentées différemment.

### A.4 Univers de la campagne actuelle

```text
config/univers/univers_filtred_equities.txt
```

Le manifeste conserve le chemin, le nombre de symboles et le SHA-256 du fichier.
Cet univers courant introduit un biais de survivance sur un historique ancien.
Il autorise au mieux `GO_RESEARCH`; `STRONG_GO` exige un univers historique PIT.

### A.5 Normalisation et règles d'entrée gelées

Les probabilités brutes de différents horizons ne sont pas moyennées. Pour
chaque date, les percentiles sont recalculés sur la même intersection commune.

```text
MH0 = percentile H20 >= 0.80
MH1 = les quatre percentiles H5/H10/H15/H20 >= 0.80
MH2 = au moins trois des quatre percentiles >= 0.80
MH3 = percentile quotidien de mean(pct_H5,pct_H10,pct_H15,pct_H20) >= 0.80
```

`MH3` est donc parfaitement défini et ne possède aucun seuil implicite.

### A.6 Confirmation Oracle restante

La règle principale est un TOP20 quotidien du consensus restant :

```text
J+5  : rank(mean(pct_H5,pct_H10,pct_H15)) >= 0.80
J+10 : rank(mean(pct_H5,pct_H10)) >= 0.80
J+15 : pct_H5 >= 0.80
```

L'intersection stricte de tous les horizons restants est conservée uniquement
comme diagnostic secondaire. Elle ne remplace pas la politique principale.

### A.7 Rendements et confirmation prix

Pour une branche LONG, le rendement signé est le rendement brut du titre. Pour
une branche SHORT, il est son opposé. La confirmation primaire utilise le
rendement *mark-to-liquidation* net estimé des coûts d'entrée et de sortie ; le
rendement brut est toujours publié en parallèle.

```text
perdant        : net <= 0
gagnant faible : 0 < net < 3 %
gagnant fort   : net >= 3 %
```

Le terme `oracle_decay` est remplacé par `oracle_rank_change` : une variation
de percentile mesure une variation de rang relatif, pas nécessairement une
baisse absolue de conviction. Le delta de score brut reste diagnostique et ne
peut piloter une règle que si les scores sont calibrés et comparables.

### A.8 Contrôles statistiques obligatoires

- résultats globaux, par fold, semestre, secteur et symbole ;
- intervalles à 95 % par bootstrap en blocs de dates ;
- regroupement des observations par date de signal et contrôle du chevauchement ;
- placebo aléatoire du même jour et contrôles appariés volatilité/secteur/bêta
  lorsqu'ils sont disponibles ;
- rendement brut, net, absolu, excédentaire à SPY et au secteur ;
- double tri conviction initiale × conviction restante ;
- déduplication : aucun nouveau signal tant qu'une position théorique du symbole
  est ouverte ; réentrée autorisée seulement après sa sortie.

### A.9 Persistance et promotion

La table existante `oracle_extreme_predictions`, séparée par `batch_id`, suffit
au POC. Aucun schéma SQL n'est créé maintenant. Le run produit des Parquet/CSV,
un rapport JSON/Markdown et un manifeste immuable associant chaque horizon à son
batch, avec empreintes des entrées.

Les tables de cohorte/checkpoint, l'intégration multi-horizon au backtest, les
sorties dynamiques et le live sont une **phase 2 conditionnelle**. Elles ne sont
implémentées que si le signal incrémental survit aux folds, semestres, coûts,
placebos et contrôles de couverture.

### A.10 Ordre de décision

```text
Phase 1A : alignement, couverture, corrélations et overlaps
Phase 1B : event study fixe J+5/J+10/J+15/J+20
Phase 1C : valeur incrémentale du rolling Oracle
Phase 1D : S6-LS retardée et symétrique
Gate      : NO_GO / WEAK_SIGNAL / GO_RESEARCH / EXPERIMENT_INVALID
Phase 2   : replay portefeuille et lifecycle, uniquement après GO_RESEARCH
Phase 3   : shadow/live, uniquement après validation OOS indépendante
```

Un résultat obtenu uniquement avec l'univers courant ne peut pas être classé
`STRONG_GO`, même si ses métriques sont excellentes.

### A.11 Challenger ciblé après `WEAK_SIGNAL` — variante 2

La phase 1 n'ouvre pas la phase 2 générale. Elle autorise uniquement un replay
trade-level ciblé des événements `MH0/H20` gagnants et encore confirmés à J+5 :

```text
entrée LONG open J+6 après prix J→J+5 positif et consensus H5/H10/H15 confirmé
puis, toutes les 5 séances, conserver si PnL net positif ET H5 quotidien TOP20
sinon sortir à l'open suivant ; TP/stop/trailing PROD prioritaires ; plafond 60
```

Trois politiques doivent partager les mêmes entrées : H20 fixe, extension
passive 60 séances, extension rolling H5 60 séances. Le gate porte d'abord sur
`rolling_h5_60 - extended_60_no_rolling`, avec bootstrap par blocs de dates.
Une absence de score H5 futur exclut l'observation et ne vaut pas rejet. Aucun
branchement dans le backtest ou le live n'est permis avant validation.

## 0. Contexte général

Nous travaillons sur l’architecture de recherche quantitative **α-Trade**.

Le constat actuel est le suivant :

```text
Oracle Extreme
→ détecte réellement les mouvements futurs d'amplitude élevée / tails

MAIS

les nombreuses tentatives pour prédire directement la direction à J
→ D1 vs D10
→ LONG vs SHORT
→ modèles mutualisés
→ modèles per-symbol
→ temporal J-N → J
→ pairwise
→ path-aware
→ first-touch
→ régimes
→ news/sentiment
→ short-interest
→ options
→ microstructure
→ intraday
```

n’ont pas produit un avantage directionnel suffisamment robuste pour être promu.

La nouvelle campagne ne doit donc **pas** essayer une nouvelle fois de forcer un modèle à connaître la direction dès `J`.

La nouvelle hypothèse est différente :

> **Oracle sait détecter qu’un mouvement important est probable. On entre tôt sur les candidats les plus convaincants, puis on laisse le prix réalisé révéler progressivement le sens. À chaque checkpoint, on vérifie aussi si Oracle continue à détecter un potentiel d’extrême sur l’horizon restant.**

Cette campagne doit tester cette hypothèse de façon causale, simple et falsifiable.

---

# 1. Architecture et principe

Créer quatre Oracle Extreme distincts :

```text
Oracle H5
Oracle H10
Oracle H15
Oracle H20
```

À la date `J`, chaque Oracle répond uniquement :

```text
"Ce symbole a-t-il une forte probabilité
de faire partie des mouvements extrêmes
sur cet horizon ?"
```

Ils ne répondent PAS :

```text
"va-t-il monter ?"
"va-t-il baisser ?"
```

Exemple :

```text
Date J

Oracle H5  percentile = 0.94
Oracle H10 percentile = 0.91
Oracle H15 percentile = 0.89
Oracle H20 percentile = 0.93
```

Cela signifie :

```text
forte conviction multi-horizon d'AMPLITUDE
```

et non :

```text
forte conviction LONG
```

---

# 2. Logique complète de la stratégie

## À J

Calculer :

```text
Oracle H5
Oracle H10
Oracle H15
Oracle H20
```

Construire un consensus multi-horizon.

Si le candidat passe la règle d’entrée :

```text
ENTRY
```

selon le contrat d’exécution production.

## À J+5

Recalculer avec les données réellement disponibles à `J+5` :

```text
Oracle H5
Oracle H10
Oracle H15
```

Vérifier aussi :

```text
return_since_entry
```

Décider :

```text
EXIT
ou
HOLD
```

## À J+10

Recalculer :

```text
Oracle H5
Oracle H10
```

et vérifier :

```text
return_since_entry
```

Puis :

```text
EXIT
ou
HOLD
```

## À J+15

Recalculer :

```text
Oracle H5
```

et vérifier :

```text
return_since_entry
```

Puis :

```text
EXIT
ou
HOLD
```

## À J+20

```text
EXIT forcée
```

sauf si le contrat de risque/exécution existant impose une sortie plus tôt.

---

# 3. Pourquoi les horizons diminuent avec le temps

L’horizon initial maximal est :

```text
H20
```

Donc :

```text
à J      → 20 séances restantes
à J+5    → 15 séances restantes
à J+10   → 10 séances restantes
à J+15   → 5 séances restantes
```

La logique devient :

```text
J     : H5 + H10 + H15 + H20
J+5   : H5 + H10 + H15
J+10  : H5 + H10
J+15  : H5
J+20  : EXIT
```

C’est une logique de :

```text
rolling horizon
receding horizon
dynamic re-evaluation
```

---

# 4. Hypothèse économique

La campagne doit tester si :

```text
Oracle
→ détecte une zone de potentiel extrême

puis

les premières séances de prix
→ commencent à révéler le côté réel

et

Oracle recalculé
→ permet de savoir si le potentiel d'amplitude
  existe encore devant la position
```

Le point clé est :

```text
PRICE CONFIRMATION
+
REMAINING ORACLE CONVICTION
```

---

# 5. Hypothèse A — continuation après J+5

Pour tous les candidats sélectionnés à J :

```text
R0_5   = return entrée → J+5
R5_10  = return J+5 → J+10
R5_15  = return J+5 → J+15
R5_20  = return J+5 → J+20

R0_10
R0_15
R0_20
```

Séparer :

```text
WINNER_5:
R0_5 > 0

LOSER_5:
R0_5 <= 0
```

Mesurer :

```text
E[R5_10 | WINNER_5]
E[R5_15 | WINNER_5]
E[R5_20 | WINNER_5]

P(R5_20 > 0 | WINNER_5)
```

Comparer à :

```text
E[R5_20 | LOSER_5]
P(R5_20 > 0 | LOSER_5)
```

Question :

> **Les gagnants à J+5 ont-ils une vraie continuation future ?**

---

# 6. Hypothèse B — valeur incrémentale d’Oracle rolling

Parmi les `WINNER_5`, séparer :

```text
WINNER_5 + ORACLE_STRONG_5
WINNER_5 + ORACLE_WEAK_5
```

Puis comparer :

```text
R5_10
R5_15
R5_20
```

Même logique à J+10 :

```text
winner jusqu'à J+10
+
Oracle H5/H10 fort
```

vs :

```text
winner jusqu'à J+10
+
Oracle H5/H10 faible
```

Comparer :

```text
R10_15
R10_20
```

Même logique à J+15 :

```text
winner
+
Oracle H5 fort
```

vs :

```text
winner
+
Oracle H5 faible
```

Comparer :

```text
R15_20
```

Question centrale :

> **Une position gagnante dont la conviction Oracle reste élevée continue-t-elle davantage qu'une position gagnante dont la conviction Oracle s'est éteinte ?**

---

# 7. Hypothèse C — Oracle decay

Grâce aux prédictions persistées, calculer :

```text
initial_consensus
consensus_J5
consensus_J10
consensus_J15
```

Puis :

```text
oracle_decay_5
= consensus_J5 - initial_consensus

oracle_decay_10
= consensus_J10 - initial_consensus

oracle_decay_15
= consensus_J15 - initial_consensus
```

et :

```text
oracle_momentum_5_10
= consensus_J10 - consensus_J5
```

Question :

> **Une chute rapide de la conviction Oracle permet-elle de détecter qu’un mouvement est en train de s’épuiser ?**

Cette analyse est d’abord diagnostique.

Ne pas transformer immédiatement `oracle_decay` en nouveau seuil optimisé.

---

# 8. Variantes d’entrée multi-horizon pré-enregistrées

Tester seulement les variantes suivantes.

## MH0 — baseline H20

```text
Oracle H20 TOP20
```

## MH1 — intersection stricte

```text
H5 TOP20
AND
H10 TOP20
AND
H15 TOP20
AND
H20 TOP20
```

## MH2 — majorité

```text
au moins 3 horizons sur 4
sont TOP20
```

## MH3 — consensus continu

```text
initial_consensus =
mean(
    percentile_H5,
    percentile_H10,
    percentile_H15,
    percentile_H20
)
```

Poids égaux.

Interdiction dans cette campagne :

```text
optimiser les poids par horizon
```

---

# 9. Cohérence multi-horizon

Calculer :

```text
consensus_min
consensus_max
consensus_mean
consensus_std
```

Exemple :

```text
A:
H5  .94
H10 .93
H15 .92
H20 .91

mean élevé
std faible
```

vs :

```text
B:
H5  .99
H10 .82
H15 .52
H20 .92

mean raisonnable
mais std élevé
```

Le rapport doit distinguer :

```text
ORACLE STRENGTH
```

et :

```text
ORACLE CONSISTENCY
```

sans introduire immédiatement de seuil optimisé sur `std`.

---

# 10. Corrélation entre horizons

Avant tout backtest, mesurer par date puis agréger :

```text
Spearman(score_H5, score_H10)
Spearman(score_H5, score_H15)
Spearman(score_H5, score_H20)
Spearman(score_H10, score_H15)
Spearman(score_H10, score_H20)
Spearman(score_H15, score_H20)
```

Mesurer également :

```text
Jaccard TOP20 H5/H10
Jaccard TOP20 H5/H15
Jaccard TOP20 H5/H20
...
```

Question :

> **Les quatre Oracle apportent-ils réellement plusieurs informations ou presque la même ?**

---

# 11. Information incrémentale de chaque horizon

Comparer comme audit :

```text
H20 seul

H20 + H15

H20 + H15 + H10

H20 + H15 + H10 + H5
```

Mesurer :

```text
candidate count
tail enrichment
future excursion
future continuation
```

Ne pas utiliser cet audit pour optimiser après coup les poids ou la combinaison.

---

# 12. Persistance obligatoire des prédictions Oracle

Pour rendre cette stratégie possible en backtest et en production, conserver toutes les prédictions Oracle dans MySQL.

Créer ou adapter :

```text
oracle_prediction_history
```

Grain :

```text
1 ligne
=
1 symbol
× 1 session_date
× 1 horizon
× 1 model_batch/version
```

Colonnes minimales :

```text
id

symbol
market

session_date
horizon

raw_score
percentile_rank

is_top10
is_top20

model_batch_id
model_version

prediction_provenance

feature_cutoff_at
predicted_at
available_at

universe_id
universe_size
universe_hash

created_at
```

---

# 13. Provenance des prédictions

Valeurs recommandées :

```text
LIVE_PRODUCTION
OOF_WALK_FORWARD
RESEARCH_VALIDATION
```

Le backtest strict ne doit consommer que :

```text
OOF_WALK_FORWARD
```

ou une provenance explicitement compatible avec son contrat causal.

Interdire par défaut :

```text
IN_SAMPLE
FULL_HISTORY_REPLAY
```

---

# 14. Clé unique et append-only

Clé logique :

```text
(symbol, session_date, horizon, model_batch_id, prediction_provenance)
```

La table historique doit être :

```text
APPEND-ONLY
```

Ne jamais remplacer une ancienne prédiction par la sortie d’un modèle plus récent.

Une prédiction historique doit rester :

```text
"ce que le modèle savait ce jour-là"
```

---

# 15. Stocker tous les symboles

Ne pas faire :

```text
if percentile >= .80:
    persist
```

Persist :

```text
tous les symboles scorés
```

pour :

```text
H5
H10
H15
H20
```

Cela permet de tester ultérieurement sans recalcul historique :

```text
TOP10
TOP20
3/4
4/4
mean percentile
minimum percentile
dispersion
decay
```

---

# 16. Universe metadata obligatoire

Le percentile étant cross-sectionnel, stocker :

```text
universe_id
universe_size
universe_hash
```

afin d’assurer :

```text
reproductibilité
audit de survivorship
audit de population
future dynamic universe
```

---

# 17. Table de cohorte / trade d'origine

Créer ou adapter :

```text
oracle_trade_cohort
```

Colonnes :

```text
id
symbol

origin_signal_date
entry_date

origin_h5_pct
origin_h10_pct
origin_h15_pct
origin_h20_pct

origin_consensus_mean
origin_consensus_min
origin_consensus_std

origin_model_set_id
origin_universe_id

status
exit_date
exit_reason

created_at
updated_at
```

---

# 18. Table de checkpoints

Créer ou adapter :

```text
oracle_position_checkpoint
```

Grain :

```text
1 position
× 1 checkpoint
```

Colonnes :

```text
id
cohort_id
symbol

checkpoint_type
checkpoint_date

sessions_since_entry

entry_price
checkpoint_price
return_since_entry

oracle_h5_pct
oracle_h10_pct
oracle_h15_pct
oracle_h20_pct

remaining_consensus_mean
remaining_consensus_min
remaining_consensus_std

oracle_decay_from_entry
oracle_change_from_previous_checkpoint

price_confirmed
oracle_confirmed

decision
decision_reason

created_at
```

---

# 19. Checkpoints autorisés

Première campagne :

```text
J+5
J+10
J+15
J+20
```

Ne pas tester :

```text
J+3
J+4
J+6
J+7
...
```

Pas de sweep de checkpoint.

---

# 20. Convention de calendrier

Les checkpoints sont exprimés en :

```text
NYSE trading sessions
```

et non en jours calendaires.

Réutiliser le calendrier de marché existant.

---

# 21. Définition du rendement au checkpoint

Utiliser :

```text
return_since_entry
```

depuis le prix d’entrée réel simulé selon le contrat production.

Formule :

```text
return_since_entry =
checkpoint_mark_price / executed_entry_price - 1
```

Documenter exactement le prix de checkpoint :

```text
close
ou
autre mark production
```

et garder la même convention partout.

---

# 22. Première règle de price confirmation

Pour l’expérience initiale :

```text
return_since_entry > 0
→ PRICE_CONFIRMED

return_since_entry <= 0
→ PRICE_NOT_CONFIRMED
```

Ne pas optimiser immédiatement :

```text
-1%
0%
+0.5%
+1%
+2%
```

---

# 23. Rolling Oracle à J+5

```text
remaining_consensus_J5 =
mean(
    H5_pct_at_J5,
    H10_pct_at_J5,
    H15_pct_at_J5
)
```

STRICT :

```text
H5 TOP20
AND
H10 TOP20
AND
H15 TOP20
```

---

# 24. Rolling Oracle à J+10

```text
remaining_consensus_J10 =
mean(
    H5_pct_at_J10,
    H10_pct_at_J10
)
```

STRICT :

```text
H5 TOP20
AND
H10 TOP20
```

---

# 25. Rolling Oracle à J+15

```text
remaining_consensus_J15 =
H5_pct_at_J15
```

STRICT :

```text
H5 TOP20
```

---

# 26. Première logique de décision complète

## À J+5

```text
if return_since_entry <= 0:
    EXIT_PRICE_FAILURE

else:
    if remaining_oracle_confirmed:
        HOLD
    else:
        EXIT_ORACLE_DECAY
```

## À J+10

```text
if return_since_entry <= 0:
    EXIT_PRICE_FAILURE

else:
    if remaining_oracle_confirmed:
        HOLD
    else:
        EXIT_ORACLE_DECAY
```

## À J+15

```text
if return_since_entry <= 0:
    EXIT_PRICE_FAILURE

else:
    if H5_remaining_confirmed:
        HOLD
    else:
        EXIT_ORACLE_DECAY
```

## À J+20

```text
EXIT_MAX_HOLD
```

---

# 27. Oracle rolling doit être recalculé au checkpoint

À J+5, utiliser une vraie prédiction avec les données disponibles à J+5 :

```text
Oracle_H5.predict(X_J5)
Oracle_H10.predict(X_J5)
Oracle_H15.predict(X_J5)
```

Pas :

```text
les scores calculés à J
```

et surtout pas :

```text
les labels futurs réalisés
```

Même principe à :

```text
J+10
J+15
```

---

# 28. PIT obligatoire

Au jour `t` :

```text
features.available_at <= decision_cutoff(t)
```

Le modèle utilisé doit être causal vis-à-vis du fold.

Interdiction :

```text
modèle entraîné jusqu'en 2025
→ recalcul des scores 2022
→ considéré comme OOF
```

---

# 29. Reconstituer les prédictions historiques si nécessaire

Si `oracle_prediction_history` n’existe pas historiquement :

```text
pour chaque fold:
    train Oracle H5/H10/H15/H20
    predict test fold
    persist predictions OOF
```

À la fin :

```text
tous les symboles
toutes les dates OOF
quatre horizons
```

---

# 30. Ne jamais remplacer prediction par target

Interdit :

```text
"le titre était effectivement D10 H5,
donc Oracle H5 = fort"
```

La stratégie doit utiliser exclusivement :

```text
score prédit à cette date
```

---

# 31. Risk / execution parity

Conserver le contrat production actuel :

```text
commission
slippage
spread
margin costs
ATR stop
TP
risk overlay
sector cap
max positions
capital constraints
```

La logique J+5/J+10/J+15 est un nouveau motif de sortie.

Elle ne remplace pas les protections de risque.

---

# 32. Priorité des sorties

Documenter explicitement l’ordre.

Exemple :

```text
1. catastrophic/risk force-close
2. stop loss
3. take profit
4. rolling checkpoint exit
5. max-hold J+20
```

Chaque trade doit avoir un :

```text
exit_reason
```

auditable.

---

# 33. Event study obligatoire AVANT portefeuille

Pour chaque signal d’entrée collecter :

```text
entry
J+5
J+10
J+15
J+20

returns
Oracle rolling scores
Oracle consistency
future returns after checkpoint
```

---

# 34. Event study J+5

Créer :

```text
G1 = loser J+5
G2 = winner J+5 + Oracle weak
G3 = winner J+5 + Oracle strong
```

Comparer :

```text
future return J+5→J+10
future return J+5→J+15
future return J+5→J+20
```

Mesurer :

```text
mean
median
win rate
P(return > 0)
quantiles
n
```

---

# 35. Event study J+10

Parmi les positions encore ouvertes :

```text
G1 = cumulative <= 0
G2 = winner + Oracle H5/H10 weak
G3 = winner + Oracle H5/H10 strong
```

Comparer :

```text
R10_15
R10_20
```

---

# 36. Event study J+15

Créer :

```text
G1 = cumulative <= 0
G2 = winner + H5 weak
G3 = winner + H5 strong
```

Comparer :

```text
R15_20
```

---

# 37. Continuation spread

À chaque checkpoint :

```text
ContinuationSpread =
future_return(PRICE_CONFIRMED + ORACLE_CONFIRMED)
-
future_return(PRICE_CONFIRMED + ORACLE_NOT_CONFIRMED)
```

C’est une métrique clé.

---

# 38. Valeur du price path

Comparer :

```text
future return des winners
vs
future return des losers
```

indépendamment d’Oracle rolling.

Question :

```text
le prix seul révèle-t-il déjà suffisamment la direction ?
```

---

# 39. Valeur incrémentale d’Oracle rolling

Comparer :

```text
winner only
```

vs :

```text
winner + Oracle confirmed
```

Si Oracle rolling n’améliore pas les winners :

```text
ROLLING_ORACLE_NO_INCREMENTAL_VALUE
```

---

# 40. Stratégies obligatoires

## S0 — baseline actuelle

```text
Oracle H20
+
lifecycle actuel
```

## S1 — H20 + price checkpoints

```text
Oracle H20 entrée

J+5
J+10
J+15

cut losers
hold winners

J+20 exit
```

## S2 — Multi-Horizon entrée uniquement

```text
MH1/MH2/MH3 à J
+
lifecycle actuel
```

## S3 — Multi-Horizon + price checkpoints

```text
consensus à J
+
price confirmation
```

## S4 — Multi-Horizon + rolling Oracle only

```text
consensus à J
+
rolling Oracle
```

sans utiliser le signe du rendement.

## S5 — Multi-Horizon + price + rolling Oracle

```text
consensus à J
+
price confirmation
+
remaining Oracle confirmation
```

C’est la stratégie cible.

---

# 41. Baseline delayed confirmation

## S6 — WAIT UNTIL J+5

À J :

```text
signal multi-horizon
mais aucune entrée
```

À J+5 :

```text
si return théorique J→J+5 > 0
ET Oracle remaining confirmé
→ ENTRY
```

Puis gérer jusqu’au J+20 initial.

Question :

> **Est-il préférable d’entrer tôt puis couper les mauvais côtés, ou d’attendre que le prix révèle déjà la direction ?**

---

# 42. Pourquoi S6 est indispensable

EARLY :

```text
capture J→J+5
mais prend les losers initiaux
```

DELAYED :

```text
évite une partie des mauvais côtés
mais abandonne le premier mouvement positif
```

Comparer :

```text
return
DD
exposure
costs
trade count
```

---

# 43. Pyramiding — uniquement campagne ultérieure

Si S5/S6 passent :

```text
50% à J
50% à J+5 si confirmé
```

peut être étudié séparément.

Ne pas inclure maintenant.

---

# 44. Thresholds

Première campagne :

```text
TOP20
4/4
3/4
mean equal-weight
price confirmation > 0
```

Pas de sweep fin de seuil.

---

# 45. Rolling consensus continu

Pour l’étude événementielle, analyser :

```text
remaining_consensus
```

par :

```text
quintiles
ou
déciles
```

avant de fixer une règle.

Une éventuelle règle de threshold devient une nouvelle campagne pré-enregistrée.

---

# 46. Pas de poids optimisés

Pas de :

```text
0.40 H5
0.30 H10
0.20 H15
0.10 H20
```

dans cette campagne.

Utiliser :

```text
mean simple
```

---

# 47. Stabilité temporelle

Produire :

```text
global OOF
par fold
par année
par semestre si échantillon suffisant
```

Un effet porté par une seule période n’est pas un GO robuste.

---

# 48. Régimes

Analyse secondaire :

```text
bull
bear
stress
rebound
```

Ne pas créer des règles spécifiques par régime dans cette campagne.

---

# 49. Secteurs

Mesurer :

```text
candidate count
continuation spread
S5 performance
```

par secteur.

Pas de thresholds sectoriels.

---

# 50. Symboles

Mesurer si assez d’échantillons :

```text
n candidates
winner rate J+5
Oracle persistence
future continuation
```

Pas de whitelist post-hoc.

---

# 51. Effet de l’univers

Comme les percentiles dépendent de l’univers :

```text
universe_id
universe_size
universe_hash
```

doivent être présents.

Le rapport doit préciser :

```text
univers fixe actuel
ou
univers historique PIT dynamique
```

---

# 52. Métriques signal-level

Avant portefeuille :

```text
candidate count/day
distinct symbols
coverage

Oracle score correlations
TOP20 overlaps

winner rate J+5
winner rate J+10
winner rate J+15

future continuation after winner
future continuation after loser

rolling Oracle incremental spread
oracle decay relation
```

---

# 53. Métriques portefeuille

Produire :

```text
total return
CAGR
Sharpe
Sortino
max drawdown
profit factor
win rate
trade count
average trade duration
average winner
average loser
turnover
gross exposure
net exposure
capital utilization
fees
slippage
spread costs
margin costs
```

---

# 54. Attribution PnL

Séparer :

```text
PnL STOP
PnL TP
PnL EXIT_PRICE_FAILURE
PnL EXIT_ORACLE_DECAY
PnL EXIT_MAX_HOLD
```

---

# 55. Holding time et exposition

Comparer :

```text
durée moyenne S0
durée moyenne S1
durée moyenne S5
```

et :

```text
average gross exposure
average net exposure
capital utilization
return / exposure
```

---

# 56. Coûts

Les exits supplémentaires peuvent augmenter :

```text
turnover
spread
slippage
```

Tout verdict économique doit être net des coûts canoniques.

---

# 57. Coverage

Pour MH0/MH1/MH2/MH3 :

```text
candidates/day
% dates sans candidat
% dates avec 1 candidat
% dates avec >= max_positions
distinct symbols
```

---

# 58. Concentration

Mesurer :

```text
sector concentration
symbol concentration
beta concentration
volatility concentration
```

notamment pour l’intersection stricte 4/4.

---

# 59. Amplitude audit

Comparer multi-horizon vs H20 seul sur :

```text
abs forward return
MFE
MAE
future excursion
```

---

# 60. Continuation vs mean reversion

Très important :

```text
winners J+5
→ continuent-ils ?

losers J+5
→ continuent-ils à perdre
ou rebondissent-ils ?
```

Si les losers rebondissent fortement, `cut losers` peut être destructeur.

---

# 61. Valeur marginale des checkpoints

Comparer de manière pré-déclarée :

```text
J+5 seulement

J+5 + J+10

J+5 + J+10 + J+15
```

Objectif :

```text
J+10 apporte-t-il encore quelque chose ?
J+15 apporte-t-il encore quelque chose ?
```

Ne pas tester d’autres dates.

---

# 62. Aucun nouveau modèle ML au départ

Ne pas lancer :

```text
nouveau CatBoost
LSTM
Transformer
nouveau D1/D10
```

La première question est purement :

```text
price path + Oracle rolling
contiennent-ils une information exploitable ?
```

---

# 63. Placebo P1

Appliquer exactement les price checkpoints à :

```text
candidats H20 seuls
```

Comparer au multi-horizon.

Question :

```text
gain du multi-horizon
ou simple effet cut-losers/hold-winners ?
```

---

# 64. Placebo P2

Si possible, construire une population :

```text
volatility-matched
```

et appliquer la même logique.

Question :

```text
est-ce simplement une propriété
des actifs à forte volatilité ?
```

---

# 65. Pas de cherry-picking

Interdit après observation :

```text
J+4 marchait mieux
TOP17 marchait mieux
H5/H15/H20 sans H10 marchait mieux
0.83 est le meilleur seuil
```

Toute modification devient une nouvelle campagne.

---

# 66. Gates GO_RESEARCH

`GO_RESEARCH` si :

```text
1. winners J+5 montrent une continuation future positive
2. effet présent dans la majorité des folds
3. rolling Oracle ajoute un spread positif vs winner-only
4. résultat non porté par une seule année
5. coverage suffisante
6. S5 améliore clairement return/Sharpe/DD/PF
7. coûts et turnover restent acceptables
```

---

# 67. WEAK_SIGNAL

```text
WEAK_SIGNAL
```

si :

```text
continuation présente mais faible
ou
rolling Oracle améliore légèrement sans stabilité suffisante
```

---

# 68. NO_GO

```text
NO_GO
```

si :

```text
winners J+5 ne continuent pas

losers rebondissent autant ou plus

rolling Oracle n'ajoute rien à winner-only

multi-horizon ≈ H20 seul

4/4 détruit la couverture

S5 dégrade après coûts

effet concentré sur une seule année
```

---

# 69. EXPERIMENT_INVALID

```text
EXPERIMENT_INVALID
```

si :

```text
Oracle historique non OOF
PIT invalide
prédictions recalculées avec champion futur
universe non traçable
checkpoint utilisant label futur
preprocessing leakage
execution non comparable
```

---

# 70. Ordre exact d’exécution

```text
STEP 1
Audit infrastructure et données disponibles

STEP 2
Construire Oracle H5/H10/H15 manquants

STEP 3
Produire H5/H10/H15/H20 OOF/WF/PIT

STEP 4
Persister toutes les prédictions dans oracle_prediction_history

STEP 5
Auditer corrélations et overlap entre horizons

STEP 6
Construire MH0/MH1/MH2/MH3

STEP 7
Event study H20 baseline

STEP 8
Event study multi-horizon

STEP 9
Tester continuation price-path à J+5

STEP 10
Tester rolling Oracle à J+5

STEP 11
Répéter à J+10

STEP 12
Répéter à J+15

STEP 13
Construire S0-S6

STEP 14
Backtests à coûts et exécution identiques

STEP 15
Attribuer les motifs d'exit

STEP 16
Tester robustesse folds/années/régimes/secteurs

STEP 17
Placebos

STEP 18
Verdict final
```

---

# 71. Rapport final attendu

Créer :

```text
MULTI_HORIZON_ORACLE_ROLLING_CONFIRMATION_REPORT.md
```

Sections :

```text
1. Executive summary
2. Hypothesis
3. Oracle H5/H10/H15/H20 contracts
4. PIT / OOF audit
5. Prediction-history storage audit
6. Universe metadata
7. Multi-horizon correlations
8. TOP20 overlap
9. MH0 baseline
10. MH1 strict 4/4
11. MH2 majority 3/4
12. MH3 continuous consensus
13. J+5 continuation study
14. J+10 continuation study
15. J+15 continuation study
16. Rolling Oracle incremental value
17. Oracle decay
18. S0-S6 strategy comparison
19. Exit attribution
20. Costs / turnover
21. Exposure
22. Fold stability
23. Annual stability
24. Regime analysis
25. Sector analysis
26. Placebo tests
27. Final verdict
28. Authorized next step
```

---

# 72. Table principale de comparaison

| Strategy | Entry logic | J+5 | J+10 | J+15 | Return | Sharpe | Max DD | PF | Trades | Turnover | Avg exposure |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| S0 | H20 baseline | existing | existing | existing | | | | | | | |
| S1 | H20 | price | price | price | | | | | | | |
| S2 | Multi-H | existing | existing | existing | | | | | | | |
| S3 | Multi-H | price | price | price | | | | | | | |
| S4 | Multi-H | Oracle | Oracle | Oracle | | | | | | | |
| S5 | Multi-H | price+Oracle | price+Oracle | price+Oracle | | | | | | | |
| S6 | delayed J+5 | price+Oracle | price+Oracle | price+Oracle | | | | | | | |

---

# 73. Table event-study J+5

| Population | N | Mean R5→20 | Median R5→20 | P(R5→20>0) | Mean MAE | Mean MFE |
|---|---:|---:|---:|---:|---:|---:|
| Loser J+5 | | | | | | |
| Winner J+5 | | | | | | |
| Winner + Oracle weak | | | | | | |
| Winner + Oracle strong | | | | | | |

---

# 74. Table rolling Oracle

| Checkpoint | Group | N | Future return | Win rate | Oracle mean | Oracle decay | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| J+5 | winner + weak | | | | | | |
| J+5 | winner + strong | | | | | | |
| J+10 | winner + weak | | | | | | |
| J+10 | winner + strong | | | | | | |
| J+15 | winner + weak | | | | | | |
| J+15 | winner + strong | | | | | | |

---

# 75. Questions finales obligatoires

```text
Q1
Les Oracle H5/H10/H15/H20 sont-ils suffisamment différents
pour que le multi-horizon apporte quelque chose ?

Q2
L'intersection stricte 4/4 améliore-t-elle vraiment la qualité
ou détruit-elle surtout la couverture ?

Q3
La majorité 3/4 est-elle plus robuste que 4/4 ?

Q4
Le consensus continu apporte-t-il un ranking monotone ?

Q5
Les winners à J+5 continuent-ils réellement jusqu'à J+20 ?

Q6
Les losers à J+5 continuent-ils à perdre
ou rebondissent-ils ?

Q7
Parmi les winners, Oracle rolling ajoute-t-il une information
au-delà du prix seul ?

Q8
Le decay d'Oracle prédit-il l'épuisement du mouvement ?

Q9
J+10 apporte-t-il encore une décision utile après J+5 ?

Q10
J+15 apporte-t-il encore une décision utile après J+10 ?

Q11
EARLY entry est-il meilleur que DELAYED J+5 confirmation ?

Q12
La stratégie complète S5 améliore-t-elle le rendement net,
le Sharpe ou le drawdown de façon robuste ?

Q13
Le gain reste-t-il présent après coûts réels ?

Q14
L'effet est-il stable sur plusieurs folds/années ?

Q15
Le résultat dépend-il excessivement d'un secteur,
d'un régime ou de quelques symboles ?
```

---

# 76. Freeze de campagne

Une fois la campagne commencée, figer :

```text
horizons = 5,10,15,20
checkpoints = 5,10,15,20
TOP20 definition
MH1 = 4/4
MH2 = >=3/4
MH3 = equal-weight mean
price confirmation = cumulative return > 0
Oracle prediction provenance rules
risk/execution contract
cost model
metrics
GO / NO_GO gates
```

---

# 77. Ce qu’il ne faut PAS faire

Ne pas :

```text
réentraîner un nouveau modèle directionnel

utiliser les labels futurs à la place des prédictions Oracle

recalculer 2022 avec un modèle entraîné jusqu'en 2025

optimiser les poids H5/H10/H15/H20

sweeper TOP15/TOP17/TOP23

tester J+4/J+6/J+7 après coup

modifier stop/TP en même temps

changer l'univers sans séparer la campagne

faire une whitelist de symboles après observation

sélectionner uniquement l'année favorable
```

---

# 78. Critère de réussite conceptuel

La campagne est particulièrement intéressante si elle démontre :

```text
Oracle à J
→ identifie un mouvement potentiel important

Prix J→J+5
→ révèle progressivement le bon côté

Oracle à J+5
→ distingue les winners encore "chargés"
   des winners dont le potentiel est déjà épuisé

Rolling confirmation
→ améliore la conservation des vrais winners
   et élimine plus tôt les mauvaises trajectoires
```

Dans ce cas :

```text
on ne prédit pas forcément la direction à J

on détecte l'amplitude à J

puis

on exploite l'information nouvelle
qui apparaît pendant la vie du trade
```

---

# 79. Architecture cible si GO

```text
                       DATA PIT
                          │
                          ▼
          ┌────────────────────────────┐
          │ Multi-Horizon Oracle       │
          │ H5 / H10 / H15 / H20      │
          └─────────────┬──────────────┘
                        │
                        ▼
                Initial Consensus
                        │
                        ▼
                     ENTRY
                        │
                        ▼
                      J+5
                        │
             ┌──────────┴──────────┐
             │                     │
       Price Confirmation     Oracle H5/H10/H15
             │                     │
             └──────────┬──────────┘
                        ▼
                    HOLD / EXIT
                        │
                        ▼
                      J+10
                        │
             ┌──────────┴──────────┐
             │                     │
       Price Confirmation       Oracle H5/H10
             │                     │
             └──────────┬──────────┘
                        ▼
                    HOLD / EXIT
                        │
                        ▼
                      J+15
                        │
             ┌──────────┴──────────┐
             │                     │
       Price Confirmation         Oracle H5
             │                     │
             └──────────┬──────────┘
                        ▼
                    HOLD / EXIT
                        │
                        ▼
                      J+20
                        │
                        ▼
                    FORCED EXIT
```

---

# 80. Principe final

> **Ne plus demander au modèle de connaître à J une direction qui semble peu observable. Utiliser Oracle pour détecter l'amplitude, puis exploiter les nouvelles informations réellement apparues après J — prix réalisé et persistance Oracle — pour gérer dynamiquement la position.**

Le test doit être mené comme une nouvelle expérience scientifique indépendante, avec :

```text
PIT
OOF
walk-forward
same execution contract
same costs
frozen rules
event study avant portfolio
```

Verdict obligatoire :

```text
STRONG_GO
GO_RESEARCH
WEAK_SIGNAL
NO_GO
EXPERIMENT_INVALID
```
