# Sources de données complémentaires pour améliorer la classification D1/D10

## Contexte

L’objectif de ces différents batchs est d’enrichir le pipeline de données afin d’améliorer la capacité du modèle à distinguer les mouvements extrêmes haussiers et baissiers, notamment dans le cadre du problème de classification **D1/D10**.

Les sources envisagées couvrent plusieurs dimensions complémentaires :

- révisions fondamentales des analystes ;
- anticipations implicites du marché des options ;
- comportement du prix et du volume à l’ouverture ;
- tension réelle sur le prêt de titres ;
- microstructure options officielle ;
- déséquilibres d’enchères d’ouverture et de clôture.

---

# 1. `analyst_snapshot_collection` Yahoo — actif

## Objectif

Capturer prospectivement l’évolution du consensus des analystes avant qu’une
publication ou un mouvement important survienne. L'ancien candidat
`business_quant_analyst_snapshot` est remplacé par cette collecte Yahoo gratuite
et demeure désactivé.

## Données recherchées

- consensus EPS et Revenue moyen/bas/haut et nombre d'analystes ;
- tendance EPS courante et valeurs 7/30/60/90 jours auparavant ;
- nombres de révisions EPS positives/négatives à 7 et 30 jours ;
- objectifs de cours et recommandations agrégées ;
- horizon Yahoo relatif `0q`, `+1q`, `0y`, `+1y` ;
- heure réelle de collecte `observed_at` ;
- date de disponibilité PIT `available_at` ;
- hash du payload ;
- identifiant du run.

## Données dérivables ultérieurement

- révision du consensus sur 1, 5, 20 ou 60 jours ;
- accélération ou détérioration des estimations ;
- dispersion entre estimation haute et basse ;
- direction et amplitude de la révision ;
- nombre de révisions positives contre négatives.

## Limites

- Yahoo/yfinance est une interface non officielle, sans SLA, réservée ici à la
  recherche personnelle/éducative et non redistribuable ;
- pas de détail analyste par analyste ;
- horizons relatifs : contrôler le rollover avant de calculer une révision J/J-1.

## Table

`stock_analyst_estimate_history`, `stock_analyst_eps_trend_history`,
`stock_analyst_eps_revision_history`, `stock_analyst_target_history`,
`stock_analyst_recommendation_history` et `analyst_snapshot_collection_run`.

## Utilité ML potentielle

Détecter une amélioration ou une détérioration fondamentale avant un événement **Oracle Extreme**.

---

# 2. `<<oracle_options_indicative_snapshot>>`

## Objectif

Mesurer les anticipations directionnelles et le risque implicite exprimés par les options.

> Malgré son nom historique, le batch doit couvrir **tout l’univers tradable**, et pas seulement les candidats Oracle.

## Données déjà prévues

- symbole du sous-jacent ;
- symbole complet du contrat ;
- expiration ;
- strike ;
- type `CALL` ou `PUT` ;
- bid et ask ;
- tailles bid et ask ;
- dernier prix négocié ;
- taille du dernier trade ;
- volatilité implicite ;
- delta ;
- gamma ;
- theta ;
- vega ;
- timestamp fournisseur ;
- heure d’observation ;
- heure de disponibilité ;
- hash du snapshot.

## Couverture effective des champs

- l'open interest est récupéré séparément depuis
  `/v2/options/contracts` puis joint au snapshot par symbole de contrat ;
- si cet endpoint ne retourne pas l'open interest, le contrat peut être conservé
  avec une valeur `NULL` et une alerte de run ;
- le volume journalier reste indisponible dans la chaîne bulk gratuite et vaut
  `NULL` ;
- `trade_size` représente la taille du dernier trade et ne doit jamais être
  interprété comme le volume de séance.

## Features potentielles

- put/call skew ;
- asymétrie d’IV entre puts et calls ;
- pente de volatilité par strike ;
- pente de volatilité par expiration ;
- variation du `delta-weighted call/put pressure` ;
- écart entre volatilité implicite et réalisée ;
- concentration des contrats autour d’un strike ;
- pression directionnelle sur plusieurs échéances.

## Horaires actifs

- **16:20 New York**, après la clôture ;
- **19:00 New York**, passage de rattrapage.

Pour une table quotidienne de features, conserver une seule observation par
séance selon une règle PIT déterministe.

## Limites

- feed Alpaca `indicative`, pas OPRA/NBBO officiel ;
- tout l'univers d'environ **1 798 titres** est parcouru ;
- les appels restent unitaires par sous-jacent et peuvent durer plusieurs
  dizaines de minutes ;
- la pagination augmente le nombre réel d'appels sur les chaînes fournies ;
- le contrat limite les strikes à 80–120 % du spot et sélectionne les expirations
  les plus proches de DTE 5/10/20 ;
- la normalisation échantillonne ensuite, pour CALL et PUT, les moneyness
  0,85/0,90/0,95/1,00/1,05/1,10/1,15 afin de maîtriser le stockage tout en
  conservant une surface comparable ;
- le rythme par défaut de 0,35 seconde protège la limite gratuite de 200
  requêtes/minute ;
- le volume journalier n'est pas disponible en bulk gratuit ;
- les quotes indicatives peuvent différer du véritable marché OPRA.

## Table

`stock_option_snapshots`. Les pages fournisseur intégrales sont également
conservées dans `pit_raw_payloads`.

## État

`ACTIVE_RESEARCH_ONLY`. L'activation signifie que la collecte prospective est
planifiée ; elle ne qualifie pas la donnée comme source de production.

## Utilité ML potentielle

Confirmer **LONG**, **SHORT** ou **abstention** après détection d’une forte amplitude probable.

---

# 3. `oracle_opening_window_sync`

## Objectif

Observer comment le marché se comporte entre le prémarché et les premières minutes de séance.

## Données recherchées

Pour chaque minute :

- symbole ;
- timestamp de la barre ;
- open ;
- high ;
- low ;
- close ;
- volume cumulé ;
- volume propre à la minute ;
- session `PRE` ou `OPEN` ;
- timestamp d’observation ;
- timestamp de disponibilité ;
- hash du payload.

## Fenêtre configurée

- début : **04:00 New York** ;
- ouverture officielle : **09:30** ;
- fin : **10:30**.

## Features potentielles

- rendement overnight ;
- direction du prémarché ;
- gap open ;
- conservation ou comblement du gap ;
- volume relatif du prémarché ;
- accélération du volume à l’ouverture ;
- breakout du high prémarché ;
- rupture du low prémarché ;
- range des 5, 15, 30 et 60 premières minutes ;
- trajectoire continue contre retournement ;
- VWAP approximatif si le fournisseur permet sa reconstruction ;
- confirmation ou invalidation du signal Oracle de la veille.

## Limites actuelles

- environ **90 appels Business Quant par passage** avec des lots de 20 ;
- quota gratuit insuffisant ;
- pagination et limite de lignes à valider pour éviter une fenêtre tronquée ;
- il s’agit de barres OHLCV, pas de trades et quotes complets ;
- `fallback_window_start` est configuré mais n’est pas encore réellement exploité par le handler.

## Table

`stock_opening_window_bars`

## Utilité ML potentielle

Retarder l’entrée et ne prendre que les mouvements dont la direction commence réellement à se confirmer.

---

# 4. `securities_lending_sync`

## Objectif

Mesurer la difficulté et le coût réel d’emprunter une action pour la vendre à découvert.

## Données indispensables recherchées

- symbole ;
- statut empruntable ou non ;
- borrow fee annualisé ;
- rebate rate, si disponible ;
- utilization ;
- quantité disponible au prêt ;
- `lendable supply` ;
- nombre de titres déjà empruntés ou `shares on loan` ;
- évolution intraday de la disponibilité ;
- timestamp fournisseur ;
- heure d’observation ;
- `available_at`.

## Données complémentaires souhaitables

- coût indicatif d’un locate ;
- niveau `easy-to-borrow` / `hard-to-borrow` ;
- concentration des prêteurs ;
- jours de couverture ;
- taux de rappel ou variation brutale de l’offre ;
- historique des corrections du fournisseur.

## Features potentielles

- variation du borrow fee ;
- accélération de l’utilisation ;
- contraction de la quantité disponible ;
- risque de short squeeze ;
- pression short réellement accumulée ;
- veto SHORT si le titre est non empruntable ou trop coûteux ;
- signal LONG contrarian en cas de squeeze potentiel.

## Différence avec le batch Alpaca actif

Alpaca fournit surtout :

- `shortable` ;
- `easy_to_borrow` ;
- `marginable` ;
- `tradable`.

En revanche, Alpaca ne fournit pas :

- les frais d’emprunt ;
- l’utilisation ;
- la quantité disponible ;
- les actions effectivement prêtées.

## État actuel

- aucun fournisseur complet choisi ;
- aucune table métier créée ;
- aucun collecteur implémenté.

---

# 5. `official_options_nbbo_sync`

## Objectif

Obtenir une version fiable et exploitable professionnellement des données options.

## Données recherchées

- sous-jacent ;
- identifiant OCC du contrat ;
- call/put ;
- strike ;
- expiration ;
- bid NBBO ;
- ask NBBO ;
- taille bid/ask ;
- timestamp précis de la quote ;
- dernier trade ;
- taille du trade ;
- place d’exécution ;
- conditions du trade ;
- volume journalier ;
- open interest ;
- volatilité implicite ;
- Greeks ;
- corrections fournisseur ;
- statut du marché ;
- heure de réception ;
- `available_at`.

## Contrats indispensables

Le système devra gérer correctement :

- splits ;
- changement de multiplicateur ;
- contrats ajustés ;
- fusion ou spin-off ;
- changement de ticker ;
- mapping OCC historique ;
- conservation des corrections tardives.

## Différence avec `oracle_options_indicative_snapshot`

- le batch Alpaca est adapté à un **POC** ;
- ce batch doit fournir une référence officielle ou consolidée **OPRA/NBBO** ;
- il doit permettre un backtest réaliste du spread et de la liquidité.

## État actuel

- aucun fournisseur officiel retenu ;
- aucune table définitive ;
- aucun connecteur.

---

# 6. `auction_imbalance_sync`

## Objectif

Mesurer la pression acheteuse ou vendeuse avant les enchères d’ouverture et de clôture.

## Données recherchées

- symbole ;
- marché : Nasdaq ou NYSE ;
- type d’enchère : ouverture ou clôture ;
- timestamp de chaque publication ;
- numéro de séquence ;
- quantité appariée ;
- quantité déséquilibrée ;
- côté du déséquilibre : `BUY` ou `SELL` ;
- prix indicatif de croisement ;
- prix de référence ;
- near price ;
- far price ;
- prix final de l’enchère ;
- statut de l’enchère ;
- corrections ou annulations ;
- heure de disponibilité réelle.

## Features potentielles

- imbalance signé rapporté au volume moyen ;
- accélération du déséquilibre ;
- changement de côté avant le fixing ;
- distance entre prix indicatif et dernier cours ;
- pression acheteuse/vendeuse persistante ;
- confirmation d’un gap ;
- risque de retournement après un déséquilibre excessif ;
- confirmation LONG/SHORT juste avant l’ouverture ou la clôture.

## État actuel

- aucun fournisseur Nasdaq/NYSE validé ;
- aucun schéma définitif ;
- aucun collecteur ;
- droits de stockage et d’utilisation historique à déterminer.

---

# Synthèse

| Batch | Nature principale | État technique |
|---|---|---|
| `business_quant_analyst_snapshot` | Consensus challenger | Désactivé, remplacé par `analyst_snapshot_collection` Yahoo ; ne pas activer sans besoin licencié explicite |
| `oracle_options_indicative_snapshot` | Anticipations options exploratoires | Collecteur et table prêts |
| `oracle_opening_window_sync` | Confirmation prix/volume après signal | Collecteur et table prêts |
| `securities_lending_sync` | Coût et tension réelle du prêt | À construire |
| `official_options_nbbo_sync` | Options fiables et microstructure | À construire |
| `auction_imbalance_sync` | Pression d’achat/vente avant fixing | À construire |

---

# Priorité théorique pour le problème D1/D10

Les données probablement les plus utiles pour distinguer correctement les extrêmes **D1** et **D10** sont, par ordre d’intérêt théorique :

1. **Opening window**
2. **Auction imbalance**
3. **Securities lending**
4. **Options NBBO officiel**
5. **Révisions analystes**
6. **Options indicatives Alpaca**

## Lecture rapide

### 1. Opening window — priorité la plus élevée

C’est probablement la source la plus directement exploitable pour résoudre un problème de **direction** après détection d’un mouvement extrême.

Elle permet d’observer si le marché confirme réellement :

- un gap haussier ;
- un gap baissier ;
- une continuation ;
- un rejet ;
- une accélération de volume ;
- une rupture du high ou du low prémarché.

Elle peut donc servir de **gate directionnel après Oracle Extreme**.

### 2. Auction imbalance

Très utile pour mesurer une pression d’achat ou de vente réelle juste avant le fixing.

Cette donnée peut permettre de différencier :

- un gap soutenu par une vraie demande ;
- un gap fragile susceptible d’être comblé ;
- un mouvement directionnel institutionnel ;
- un excès temporaire.

### 3. Securities lending

Particulièrement utile pour les signaux SHORT.

Le coût et la tension sur le prêt peuvent aider à détecter :

- un short overcrowded ;
- un risque de squeeze ;
- une difficulté réelle à shorter ;
- une pression short institutionnelle.

### 4. Options NBBO officiel

Très riche pour la direction, le risque implicite et la microstructure, mais plus coûteux et techniquement plus lourd.

La valeur ajoutée principale viendrait de :

- la structure de volatilité ;
- la pression calls/puts ;
- les spreads réels ;
- l’open interest ;
- les volumes ;
- les changements de skew.

### 5. Révisions analystes

Signal potentiellement utile à moyen terme, notamment pour anticiper une amélioration ou une détérioration fondamentale avant publication.

Cependant, ce signal est moins directement lié à la direction intraday ou au comportement immédiatement après un événement extrême.

### 6. Options indicatives Alpaca

Intéressant pour un POC et pour tester rapidement des hypothèses, mais moins fiable que des données OPRA/NBBO officielles.

Cette source peut servir à valider la pertinence de certaines features options avant d’investir dans un fournisseur plus coûteux.

---

# Conclusion

L’architecture cible devrait idéalement séparer trois étapes :

1. **Détection de l’amplitude potentielle**
   - Oracle Extreme.

2. **Détermination de la direction**
   - opening window ;
   - auction imbalance ;
   - options ;
   - analyst revisions ;
   - securities lending.

3. **Décision d’exécution**
   - LONG ;
   - SHORT ;
   - abstention ;
   - timing d’entrée ;
   - contrôle de liquidité et du coût réel d’exécution.

Dans cette logique, `oracle_opening_window_sync` est probablement le batch à plus forte valeur ajoutée immédiate pour votre problème D1/D10, car il transforme un signal d’amplitude prévisionnelle en un signal pouvant être confirmé par le comportement réel du marché.
