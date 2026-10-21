# NOTE DE REPRISE — modèle de choix des configurations Winner / Oracle

**Rédigée le 21 octobre 2026, fuseau Europe/Paris.**

## 0. Reprendre ici en cinq minutes

Sujet volontairement mis de côté pendant le téléchargement intraday, annoncé
par l'utilisateur comme devant durer environ **trois jours**. Cette durée est
une estimation utilisateur, **pas une échéance garantie ni une programmation**.

**Objectif à reprendre :** étudier un modèle séparé qui choisit une
**configuration complète de gestion de campagne LONG** après sélection Oracle,
selon les informations disponibles à la décision. Pas seulement SL/TP : taille
initiale, confirmation, renforcement, trailing, horizon et attente d'entrée.

**Dernier état :** audit de faisabilité terminé, aucun modèle entraîné. Il existe
un espace de gain rétrospectif entre profils, mais les cinq règles contextuelles
simples testées n'ont pas confirmé de gain en 2026. L'échantillon était petit.
Le téléchargement plus profond vise à construire un dataset plus large, **pas
à effacer ce résultat négatif**.

À la reprise, dans cet ordre :

1. Vérifier la fin réelle du backfill et sa couverture, pas seulement sa date
   minimale ou un nombre de tâches terminées.
2. Inventorier les scores Oracle **réellement hors échantillon** sur 2020–2025.
3. Fixer la période exploitable et un nouveau protocole versionné.
4. Préparer le dataset de configurations complètes, sans changer la production.
5. Décider, selon la couverture/effectif, si un petit modèle est justifié.

**Ne pas relancer les anciens audits ou la grille 144 × LONG/SHORT pour repartir
de zéro. Ne pas lancer directement un entraînement, ni un téléchargement
2016–2019, sur la seule base de cette note.**

Phrase de reprise que l'utilisateur peut donner :

> Reprendre `doc/ml/TODO_reprise_selecteur_configurations_winner_20261021.md`.
> Le téléchargement est terminé. Commencer par l'audit de couverture intraday
> et la disponibilité des scores Oracle historiques causaux, puis me présenter
> le périmètre d'apprentissage réellement possible.

## 1. Demande utilisateur et décisions conservées

L'utilisateur ne cherche pas le meilleur réglage d'une année choisie après coup.
Il suppose que régime, macro, secteur ou caractéristiques du titre peuvent
indiquer quel réglage convient à une **situation donnée**. Il demande si un
modèle peut choisir conjointement tous les paramètres de `winner_pyramiding`.

Réponse de travail retenue : oui techniquement, sans garantie de signal. Il est
préférable de sélectionner parmi quelques **configurations complètes figées**
avant d'essayer une génération libre de nombreuses valeurs numériques.

Un modèle ne doit pas optimiser le profit en assouplissant les contrôles de
fraîcheur, en minorant les coûts ou en élargissant le risque autorisé.

L'utilisateur télécharge actuellement six années de bougies de cinq minutes,
dans le contexte d'un apprentissage envisagé **2020–2025**. Il propose aussi
**2016–2019 si nécessaire**. Cette extension est une possibilité, pas un
téléchargement que l'assistant aurait commencé ni une nécessité déjà démontrée.

Cette note est le livrable demandé pour pouvoir travailler sur autre chose
pendant l'attente. Aucun suivi automatique, nouvelle collecte, entraînement ou
changement de batch n'est créé par sa rédaction.

## 2. Configuration observée, à relire à la reprise

Fichier `config.yaml`, section `winner_pyramiding`, observée le 21 octobre :

```yaml
winner_pyramiding:
  enabled: false
  initial_position_fraction: 0.5
  reinforcement_enabled: false
  reinforcement_trigger_pct: 0.05
  confirmation_bars: 2
  stop_loss_pct: 0.07
  take_profit_pct: null
  trailing_stop_pct: 0.15
  horizon_sessions: 20
  entry_valid_sessions: 20
  max_quote_age_seconds: 60
  max_bar_delay_seconds: 60
  cost_reserve_bps_per_leg: 25
```

Cette copie est un repère documentaire, **pas une consigne d'écraser les
éventuelles modifications futures de l'utilisateur**. Le mécanisme reste
désactivé dans la configuration observée.

### Paramètres potentiellement choisis par le modèle

| Paramètre | Sens et conséquence pour le dataset |
| --- | --- |
| `initial_position_fraction` | 0,5 ou 1 : change quantité, risque consommé et cash disponible |
| `reinforcement_enabled` | Autorise ou non un ajout gagnant, jamais de moyenne à la baisse |
| `reinforcement_trigger_pct` | Seuil de gain avant confirmation d'un ajout ; change sa date/possibilité |
| `confirmation_bars` | Clôtures 5m complétées consécutives ; change les entrées, pas seulement les sorties |
| `stop_loss_pct` | Stop initial ; change aussi le sizing autorisé par le budget de risque |
| `take_profit_pct` | Barrière de prix ; `null` = aucune |
| `trailing_stop_pct` | Protection sous le plus haut connu ; ne desserre jamais le stop |
| `horizon_sessions` | Durée depuis le premier fill, entrée incluse ; H20 → open de la 21e séance |
| `entry_valid_sessions` | Durée d'attente après Oracle, distincte de la détention |

### Contraintes à ne pas transformer en raccourcis de performance

- `enabled` : autorisation globale, pas un paramètre de profit.
- `max_quote_age_seconds`, `max_bar_delay_seconds` : qualité/fraîcheur réelle,
  pas des leviers pour accepter un prix périmé.
- `cost_reserve_bps_per_leg` : réserve de sizing, **pas le coût comptable réel**.
  Elle doit rester cohérente avec les hypothèses d'exécution ; ne pas la réduire
  pour augmenter artificiellement les quantités.
- Budget de risque, capital, concentration, marge/levier et coupe-circuit restent
  des limites externes au sélecteur. Aucun pouvoir de les contourner.

Le premier sélecteur envisagé choisit à l'entrée une politique qui reste figée
pour la campagne. Changer quotidiennement les pourcentages d'une position déjà
ouverte est un **problème distinct**, non autorisé implicitement ici. Le stop
dur ne doit pas être desserré pour sauver un perdant.

## 3. Ce qui a déjà été testé : ne pas le refaire à l'identique

### 3.1 Ancien sélecteur du 14 octobre : résultat négatif

Référence : [sélecteur de trois profils](oracle_path_selecteur_protections_20261014.md).

- Deux petits régresseurs LightGBM, 24 variables ; trois profils de protection.
- Ils choisissaient finalement **toujours LARGE**, sans personnalisation utile.
- Pas d'avantage stable contre les constantes ; verdict
  `NO_GO_STABLE_PERSONALIZATION`.
- Contrat différent : protections journalières, TOP5, pas d'expiration H20
  forcée, pas le runtime intraday actuel.

Ne pas présenter le futur essai comme le premier modèle de protections de
l'application, ni comme la réactivation d'un modèle déjà performant.

### 3.2 Audit intraday contextuel du 21 octobre : terminé

Document : [audit des protections selon le contexte](winner_protections_contexte_20261021.md).

Dossier faisant foi :
`artifacts/research/us_winner_context_headroom/20261021-v1`.

Programmes et tests :

- `scripts/research/us_winner_context_headroom.py`
- `scripts/research/us_winner_context_headroom_audit.py`
- `tests/test_us_winner_context_headroom.py`
- `tests/test_us_winner_context_headroom_audit.py`
- Suite finale : `artifacts/tmp/winner-context-final-20261021.xml`.

**État terminal : `NO_GO_CONTEXT_NOT_CONFIRMED`, 213/213 campagnes traitées.**

Population héritée des scores **CatBoost PATH_H20 de recherche TOP10**, pas
champion LightGBM de production, pas tout le TOP10 quotidien. Le parent était
déjà conditionné à la couverture de chemins futurs : biais de couverture et de
survivants à conserver dans l'interprétation.

- Snapshot READ ONLY : 523 941 barres, 72 titres.
- 204 entrées/fenêtres communes qualifiées : 113 en 2025, 91 en 2026.
- Neuf réserves communes : cinq trous H20 (KURA, CODI, GPRE, LASR, UCTT), quatre
  immatures au 30 septembre (PENG, MXL, TSEM, MRVL).
- Après réduction des chevauchements par symbole : 95 en 2025 et 74 en 2026.
- **Seulement 84 labels 2025 étaient disponibles avant 2026** ; les onze autres
  ne sont pas utilisables pour choisir la règle avant le test 2026.
- 2026 : 63 observations au premier semestre, onze au second semestre partiel.

Six profils figés : référence **SL7/TR15/H20/sansTP**, puis modification unique
SL5, trailing10, trailing20, horizon15 ou TP10. Sans renforcement. Même entrée
pour tous, et horizon depuis l'entrée, pas l'ancienne expiration OracleJ+H.

Rendements **unitaires moyens nets**, contrôle espacé, pas des rendements annuels
de portefeuille :

| Profil | 2025 | 2026 jusqu'au 30 septembre |
| --- | ---: | ---: |
| REFERENCE | +4,60 % | +3,11 % |
| SL5 | +3,03 % | +2,30 % |
| TRAIL10 | +1,95 % | +2,04 % |
| TRAIL20 | +4,30 % | +2,93 % |
| HOLD15 | +3,70 % | +3,91 % |
| TP10 | +0,66 % | +2,20 % |

Surplus du sélecteur parfait **avec connaissance du futur** contre le meilleur
constant : +3,46 / +5,95 points unitaires. Cela montre un espace théorique,
**pas un signal appris ou réalisable**. 52,63 / 44,59 % des observations perdent
avec les six profils : le gestionnaire ne peut pas forcément sauver une entrée.

Choix par état fondé sur les 84 labels 2025, puis comparaison 2026 :

| Facteur | Écart moyen contre la référence fixe en 2026 |
| --- | ---: |
| Régime prix SPY (SMA50/200) | −0,35 point |
| Momentum relatif titre/SPY | −0,48 point |
| Expansion/contraction vol20/60 | −0,58 point |
| ATR relatif au prix | 0 : choisit toujours REFERENCE |
| Attente d'entrée après Oracle | 0 : choisit toujours REFERENCE |

Stress 25 bps : mêmes signes négatifs. États parfois rares ; intervalles
mensuels traversant zéro ; aucun facteur ne passe le critère annoncé.
Les 437 lignes macro et 72 secteurs actuels ont été archivés, **pas validés PIT
ni utilisés comme prédicteurs**. Les interactions multivariées n'ont pas été
entraînées : ne pas transformer ce NO_GO limité en impossibilité générale.

**84 tests ciblés passent.** Reconstruction scalaire indépendante du code de
sortie : 2 448 chemins profil/frais, 204 entrées, maturités, purge et espacement.
Erreur maximale 5,69e−14 point. Audit
`PASS_SCALAR_EXITS_AND_TEMPORAL_CHOICES`, dans `completion-audit.json`.
Même assistant, pas seconde revue humaine indépendante.

**Cet étage n'était pas un portefeuille** : pas de cash/sizing/risque/levier/
réinvestissement comparés. Changer confirmation, délai, ajout et taille exigera
de reconstruire les actions, pas de réutiliser ses six colonnes comme si elles
décrivaient toutes les configurations complètes.

## 4. Téléchargement en attente : faits et inconnues

Table : **`alpha_trade.stock_bars_intraday`**.

Guide existant : [backfill intraday US](../operations/backfill_intraday_us.md).
Page : **Analyse & Recherche → Barres intraday**.
Service : `service.market.intraday_backfill`.

Défauts observés dans `config.yaml` :

```yaml
intraday_backfill:
  provider: alpaca
  alpaca_feed: sip
  account_id: default
```

Contrôle ponctuel du 21 octobre via l'index `idx_intraday_date_interval` : la
table contient des dates **5m** du **2 janvier 2020 au 15 octobre 2026**.
**Ces bornes toutes provenances confondues ne certifient ni six années SIP
complètes, ni tous les titres, ni la couverture du run en cours.**

L'identifiant exact du backfill actuellement lancé, ses dates et son fichier
univers n'ont pas été figés dans cette note. Les récupérer dans l'IHM/historique
à la reprise ; ne pas inventer un run-id ou supposer qu'il est terminé au bout
de trois jours. Une progression peut être partielle, interrompue ou en échec.

Ne pas supprimer de run, checkpoint, cache, table ou archive pour « repartir
propre ». La suppression d'une exécution visible ne supprime pas forcément les
points de reprise. Ne pas lancer une collecte concurrente du même périmètre.

### Checklist de fin de téléchargement

- [ ] Identifier précisément run-id, commande, fournisseur/flux, intervalle,
  compte, univers, bornes et politique de reprise.
- [ ] Vérifier état terminal, tâches réussies/vides/échouées/en attente,
  pagination, logs et éventuel arrêt sur limite/quota.
- [ ] Figer la liste et l'empreinte de l'univers utilisé. Le fichier historique
  `config/univers_batch/univers_filtred_tradable.txt` est un repère, pas une preuve
  que le run courant utilise encore exactement ce fichier.
- [ ] Mesurer couverture **titre × séance × année**, avec distinction séance
  entière / trous / séance absente / absence attendue par cotation.
- [ ] Vérifier `provider=alpaca`, `data_source=alpaca_sip`, `interval_code=5m`,
  `market_code=US_EQ`, `session_tag=regular`, `data_adjustment=raw`, `is_filled=0`.
- [ ] Contrôler horodatages UTC, date New York, grille 5m, fins de bougie,
  séances courtes/jours fériés/DST ; ne pas exiger 78 barres les jours écourtés.
- [ ] Vérifier OHLCV, doublons/conflits, provenance `payload_hash`/`run_id`,
  identités et événements ; ne pas remplir artificiellement les trous.
- [ ] Préserver les dates réelles de récupération : `observed_at` n'est pas
  une réception historique Alpha Trade reconstituée.
- [ ] Vérifier également le daily nécessaire aux features et au warm-up.

Les bornes MIN/MAX globales ne remplacent jamais ce bilan. Une ancienne requête
MIN/MAX avec tous les filtres a dépassé dix secondes ; préférer un inventaire
indexé/partitionné et des requêtes bornées plutôt qu'un scan géant répétitif.

## 5. Verrou essentiel : Oracle causal pour chaque date

Les bougies seules ne suffisent pas. Il faut connaître les titres que l'Oracle
aurait sélectionnés **sans connaître leurs mouvements futurs**.

- Inventorier `oracle_extreme_predictions` et la lineage dédiée
  `oracle_path_prediction_lineage` si utilisés, ainsi que les archives de folds
  `oracle_path/oof_predictions.parquet` et `folds/<date>/oof.parquet`.
- Contrôler la cible : **Oracle Extreme parcours H20**, pas un mélange silencieux
  H20 terminal / TP avant SL / parcours, ni des champions de backends différents.
- Contrôler modèle/fold disponible avant la date de score, empreintes des poids,
  profil de features, univers/rangs transverses et date limite des labels.
- Reconstituer le TOP10 sur tout le pool scoré admissible **avant** les exclusions
  de qualité future. Pas de TOP11 en remplacement d'un titre perdant/manquant.
- Ne jamais scorer 2020 avec un modèle entraîné jusqu'en 2025 et appeler cela OOS.
- Si une lineage ou des poids ont disparu, conserver une réserve ; ne pas
  reconstruire de fausses empreintes ni mélanger d'anciens scores avec de nouveaux.

Références de modèles existants dans l'historique, **pas une affectation autorisée
aux années 2020–2023** :

- `model-factory-20261014113215-437ed1` : ancien test annuel 2024.
- `model-factory-20261014113226-102eca` : ancien test annuel 2025.
- `model-factory-20261014113232-bc35a7` : ancien test annuel 2026.
- `model-factory-20261016180250-3b0515` : référence de production citée dans le
  pipeline ; relire la configuration et le contrat, ne pas supposer son rôle.

La première année réellement exploitable dépend du warm-up et des folds
entraînés antérieurement. **Des cours dès 2016 ne signifient pas que l'on peut
entraîner le sélecteur dès 2016.** Les premières années peuvent servir au seul
apprentissage initial de l'Oracle.

Un nouvel entraînement/re-score historique Oracle, s'il est nécessaire, est une
étape à proposer explicitement avec périmètre/coût avant lancement, pas un
fallback caché du chargement de scores.

Guide : [Oracle parcours H20](oracle_path_training.md).

## 6. Futur dataset : ce qui doit être construit, pas encore implémenté

### Unité d'observation

Une opportunité issue d'un signal Oracle causal, son contexte disponible à la
décision et les chemins de chaque configuration admissible. Conserver les
opportunités sans entrée, refusées, incomplètes et non matures, avec leurs motifs.
Un renforcement ne crée pas un nouveau label indépendant de sa campagne.

Choisir les configurations avant de lire les nouvelles performances. Ne pas
multiplier librement les valeurs continues ou prendre le meilleur réglage de
2026 comme point de départ « confirmé ». Le nombre de profils complet est à
fixer selon l'effectif et la complexité ; aucun nombre définitif n'est approuvé.

### Exécution et portefeuille

Chaque configuration doit réellement recalculer :

- première confirmation/entrée possible, expiration de l'attente, absence
  d'achats supplémentaires si le titre est déjà détenu ;
- quantité approuvée et fraction initiale avec budget du risque ;
- ajout gagnant éventuel, confirmation, cash et budget restant ;
- ancrage des barrières aux fills, arrondis, SL/TP/trailing/gaps ;
- échéance de détention depuis le premier fill, **sans reset lors de l'ajout** ;
- réinvestissement, contraintes de portefeuille, frais et financement quand
  l'étage économique sera autorisé/raccordé.

Ne pas figer les mêmes fills/quantités si l'on change confirmation, attente,
renforcement ou SL : ce serait un faux contrefactuel. Une politique peut modifier
les capitaux disponibles pour d'autres campagnes. Un label unitaire est un
outil d'apprentissage potentiel, pas une preuve de performance du portefeuille.

### Contexte d'entrée

Commencer par des informations réellement connues : historiques de volatilité,
ATR/prix, gaps, liquidité, tendances, force relative, évolution sur plusieurs
séances, régime prix du marché, éventuellement secteur/macro **après qualification**.
Éviter un identifiant symbole/année qui permettrait seulement de mémoriser.

Les variables macro révisables, consensus, news, secteurs actuels et données
récupérées aujourd'hui ont chacune un contrat de disponibilité à établir.
Leur présence en base ne les rend pas toutes utilisables dans un backtest PIT.

### Récompense, métriques et causalité

Ne pas apprendre seulement « quel profil a donné le plus gros profit » sans
regarder risque et capital immobilisé. Comparer avantage net contre un profil
constant, dispersion, drawdown/risque, durée, turnover et coûts au bon étage.

La disponibilité du label doit couvrir toute la fenêtre commune nécessaire :
**attente d'entrée + détention maximale + sortie**, pas simplement vingt jours
depuis Oracle. Une sortie précoce gagnante n'autorise pas à apprendre ce label
avant que la comparaison avec les autres profils soit mûre.

La purge entre train/validation/test suit ces dates réelles de disponibilité,
avec contrôle des chevauchements par titre et des blocs temporels. Ne pas
compter chaque barre, chaque profil simulé ou chaque ajout comme un nouvel
exemple indépendant. Vingt variantes d'une campagne ne créent pas vingt
campagnes de marché indépendantes.

## 7. Découpage temporel envisagé — proposition, pas protocole approuvé

Si 2020–2025 est exploitable et les scores Oracle disponibles :

| Période indicative | Rôle |
| --- | --- |
| 2020–2023 | Apprentissage du petit sélecteur |
| 2024 | Validation, sélection du modèle/hyperparamètres limités |
| 2025 | Test sans modification après lecture des résultats |
| 2026 partiel | Confirmation supplémentaire, pas réglage |

Si 2016–2019 est nécessaire et réellement disponible, décider d'abord quelle
partie sert à entraîner l'Oracle initial et à fournir du warm-up. Ensuite
redéfinir les bornes en fonction des **premiers vrais scores OOS**, pas d'une
date désirée. Ne pas dépenser sur cette extension avant d'avoir mesuré les trous
et l'effectif de 2020–2025.

Les années 2024–2026 ont déjà été largement étudiées dans le projet : séparation
temporelle oui, prétention de test totalement vierge non. Une confirmation
prospective restera nécessaire avant une éventuelle promotion PAPER/live.

Six/dix années peuvent suffire à un premier petit modèle si la diversité et le
nombre de campagnes le permettent. **Aucun seuil magique de nombre d'années
ou garantie de rentabilité n'est établi.**

## 8. Plan de reprise opérationnel avec points d'arrêt

### A — Inventaire après backfill

- [ ] Retrouver le run exact et vérifier sa terminaison.
- [ ] Produire la couverture par année/titre/séance et la liste motivée des trous.
- [ ] Figer snapshots, univers, conventions de prix et empreintes dans un dossier neuf.
- [ ] Ne pas réparer/re-télécharger silencieusement : proposer les rattrapages ciblés.

**Sortie attendue :** tableau de couverture, nombre de symboles/séances et
fenêtres qualifiées ; décision sur l'intérêt réel d'étendre 2016–2019.

### B — Scores Oracle

- [ ] Inventorier les dates/folds/poids OOS utilisables.
- [ ] Mesurer le TOP10 disponible avant qualité future et les réserves.
- [ ] Si incomplet, présenter le besoin de génération historique causale séparé.

**Arrêt si nécessaire :** bougies complètes mais aucun score Oracle causal
utilisable. Ne pas remplacer par des scores rétrospectifs contaminés.

### C — Protocole et dataset contrefactuel

- [ ] Définir une petite famille de configurations complètes, paramètres de
  sécurité fixes et reward/métriques avant résultats.
- [ ] Vérifier réutilisation du runtime partagé et des contrats d'exécution.
- [ ] Construire les labels avec motifs d'abstention, disponibilité et coût.
- [ ] Mesurer effectifs bruts, campagnes distinctes, chevauchements, concentration,
  couverture par régime et qualité PIT des features.
- [ ] Prévoir un témoin constant et tous les audits prix/cash/temps nécessaires.

### D — Décision d'entraîner

- [ ] Vérifier qu'il reste une différence utile entre configurations et un
  effectif raisonnable pour les distinguer.
- [ ] Proposer un petit sélecteur régularisé, pas directement un gros réseau ou
  du reinforcement learning ; aucune supériorité supposée.
- [ ] Fixer validation, seuils d'abstention/fallback, tests et coûts avant fit.
- [ ] Confirmer le GO d'entraînement et son périmètre avant de le lancer.

### E — Seulement si justifié, comparaison économique

- [ ] Comparer choix appris / profil constant sélectionné en validation / témoins.
- [ ] Rejouer les portefeuilles avec capital partagé, frais, risque, levier
  configuré, refus réels du simulateur et réinvestissements.
- [ ] Publier rendement, capital final, gains/pertes, taux gagnant, DD, capital
  moyen utilisé, durées et concentration — pas seulement le meilleur chiffre.
- [ ] Pas de connexion live ni activation automatique à partir de cette recherche.

## 9. Repères techniques à lire avant d'implémenter

| Fichier | Rôle |
| --- | --- |
| `common/winner_pyramiding.py` | Configuration partagée, confirmation, quantités, ajout, stop/trailing/TP, échéance |
| `execution_engine/winner_runtime.py` | Coordinateur courant de campagne |
| `execution_engine/winner_risk.py` | Réapprobation du risque |
| `backtesting/winner_intraday.py` | Replay du runtime, capital, frais et contrôles du risque |
| `backtesting/winner_campaign_replay.py` | Entrée de replay historique ; lecture SQL sans génération implicite de scores |
| `service/market/intraday_backfill.py` | Collecte/reprise intraday existante ; ne pas modifier le run actif |
| `database/sql/stock/stock_bars_intraday.sql` | Colonnes, clé et index |
| `doc/ml/experiences_done.md` | Registre des essais déjà faits, résultats négatifs inclus |

Le replay actuel est **LONG uniquement**. Ne pas présenter un changement de
`side` comme un raccordement SHORT validé. Un volet SHORT demanderait contrat,
borrow/locates/coûts et tests distincts.

Conserver les modifications utilisateur et dossiers existants. Les protocoles
et artefacts scellés du 14/21 octobre ne doivent pas être réécrits pour masquer
une évolution de code ou faire passer les nouveaux scores pour les anciens.

## 10. État final de cette note

**Sujet en attente de fin/qualification du téléchargement, pas un run de
recherche encore actif.** L'audit du 21 octobre est terminé. Aucun entraînement,
nouveau téléchargement, ordre, changement SQL ou activation de batch n'est
lancé par ce document. Il fournit le point de reprise complet demandé.
