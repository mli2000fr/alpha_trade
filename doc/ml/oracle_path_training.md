# Oracle Extreme parcours H20 — mode d'entraînement distinct

Implémenté le 11 octobre 2026, **raccordé à ML Predict/backtest/live le 13 octobre**.
Un seul classifieur d'amplitude, sans direction. Oracle terminal et TP avant SL
restent des modes distincts. Les anciens artefacts et résultats ne sont pas
convertis silencieusement. Aucun entraînement réel, ordre broker ou promotion
de batch n'est lancé lors de ce raccordement.

## Lancer depuis l'IHM

1. Ouvrir **Workflow & Orchestration → Pipeline**, marché **US**.
2. Déplier **⚙️ Paramètres d'exécution**, puis **Paramètres Model Factory**.
3. **🔮 Oracle Extreme parcours H20 — modèle séparé** est désormais cochée
   par défaut ; **🎯 Oracle TP avant SL** est décochée. Une session déjà ouverte
   conserve ses choix manuels : régler une fois ces deux cases si nécessaire.
   Le bundle Oracle terminal/LONG/SHORT et
   l'Oracle terminal sont désactivés pour ce lancement ; leurs contrats ne changent pas.
4. Choisir le jeu de features **expert**. Les familles de features cochées sont
   utilisées en mode **Dynamique** ; un profil JSON impose sa propre liste et son
   générateur. Les mêmes réglages sont à conserver pour une comparaison équitable.
5. Dans les paramètres de training, renseigner les dates de début et fin.
   Défaut actuel de fin : **2023-12-31**. Une campagne historique
   **2016-01-01 → 2023-12-31** laisse 2024–2026 hors de l'entraînement, mais elles ont
   déjà été examinées dans les expériences précédentes : elles ne sont pas des
   confirmations entièrement vierges.
6. Garder **Activer walk-forward** (forcé dans ce mode). Pour le premier protocole :
   minimum train **504**, validation **126**, test **126**, pas **126**, maximum
   **15 folds**. Le nombre effectivement disponible dépend de la couverture.
   Le pas doit être au moins aussi grand que la fenêtre de test.
7. Garder **rebuild-all**, puis aller au bloc **9. ML Train**. Choisir le fichier
   **univers_filtred_tradable.txt** dans la liste d'univers, vérifier les dates
   et la commande affichée, puis cliquer **Entraîner l'univers sélectionné**.

La commande doit contenir `--oracle-path-model-only --oracle-horizon 20`, et
**pas** `--oracle-model-only`, `--oracle-barrier-model-only` ou `--enable-oracle-model`.
Après un training terminé, sélectionner **ce nouveau batch parcours** dans
l'étape 10 avant de poursuivre : la case de training n'effectue ni conversion
des anciens modèles ni promotion du batch de production.

### Choisir LightGBM, CatBoost ou comparaison automatique

Depuis le **14 octobre**, sous la case Oracle parcours, la liste
**« Algorithme — Oracle Extreme parcours H20 »** remplace les cases challengers
spécifiques à ce mode.

| Choix | Entraînement | Modèle utilisé ensuite |
| --- | --- | --- |
| LightGBM | LightGBM CPU uniquement | LightGBM dans chaque fold |
| CatBoost | CatBoost CPU uniquement | CatBoost dans chaque fold |
| Comparaison automatique | Les deux, mêmes labels/features/folds | Meilleure AUC de validation par fold ; égalité exacte → LightGBM |

Le défaut IHM est **comparaison automatique**, configurable :

```yaml
oracle_path:
  training_backend: auto  # lightgbm | catboost | auto
  direction_policy: long_only
```

Ce défaut concerne le nouveau widget d'entraînement, pas le modèle déjà chargé.
Une session IHM existante conserve son choix. La commande prévisualisée contient
`--oracle-path-backend lightgbm`, `--oracle-path-backend catboost` ou
`--oracle-path-backend auto`. Pour imposer CatBoost, sélectionner **CatBoost**
avant de lancer **9. ML Train**, puis sélectionner le nouveau batch dans
**10. ML Predict**. Changer la liste ne convertit pas les poids existants.
Le champ générique « champion par défaut » ne remplace pas ce choix dédié.

L'option dédiée est prioritaire sur `--compare-lightgbm` / `--enable-catboost`.
Les anciennes commandes **sans** cette option restent compatibles : LightGBM
seul sans `--enable-catboost`, comparaison des deux avec ce flag. Un backend
explicite hors `--oracle-path-model-only` est refusé. Les modes terminal, TP avant
SL et les marchés CN/FR ne reçoivent pas de backend Oracle parcours implicite.

Le choix est inscrit dans `protocol.json`, `feature_profile.json`, `report.json`
et dans le champion de chaque fold. ML Predict et les chemins backtest/live
chargent le contrat archivé : ils ne relisent pas le défaut de l'IHM/YAML pour
changer d'algorithme. Backend incohérent, poids absent/corrompu ou demande de
reprise avec un autre choix → échec explicite, sans fallback ni remplacement.
Les anciens modèles continuent de se charger avec leur contrat legacy inchangé.
Les recherches antérieures conservent aussi leurs empreintes de code originales :
leurs résultats restent consultables, mais une reprise avec le code modifié peut
être refusée par le contrôle SHA. Ne pas réécrire ces empreintes pour contourner
le contrôle ; un nouveau protocole/dossier est nécessaire pour un nouveau replay.

Validation de cette évolution : **267 tests ciblés réussis**, incluant les trois
choix du widget et du CLI, petits entraînements CPU réels, reprise, rechargement,
rejet de poids corrompus/choix incohérents et absence d'override à la prédiction.
Les trois campagnes annuelles existantes restent chargeables en lecture seule,
14 folds chacune. Aucun nouveau training de production ou ordre lancé.

Les paramètres avancés de chaque algorithme et le nombre de workers sont repris.
CatBoost utilise **Logloss** pour cette cible binaire, indépendamment du réglage
générique RMSE/YetiRank. L'early stopping utilise seulement la validation.
En comparaison automatique, le champion de chaque fold est choisi sur l'AUC
de validation ; en choix unique, il est imposé, pas rechoisi sur l'AUC.
Les résultats du test ne choisissent ni champion, ni seuil, ni hyperparamètre.
On déploie un seul score d'amplitude, pas une moyenne des deux.
Les métriques des deux candidats et du champion sont archivées hors échantillon :
AUC, précision/rappel TOP10 %/TOP20 %, précision et amplitude moyenne des **10,
20 et 50 premiers titres**. Ces dernières exigent au moins ce nombre de titres
par date ; leur nombre de dates est fourni, sinon la mesure reste `null`.

**Pas de LSTM pour cette première comparaison** : il faudrait qualifier un
nouveau contrat de séquences (warm-up, masque de manque, causalité, architecture)
et distinguer l'effet de cette représentation de celui de l'algorithme. Cela ne
prouve pas qu'il serait moins bon ; ce serait un challenger séparé ultérieur.
Les options Global Ranking, per-symbol, optimisation des cibles et calibration
Platt ne changent pas ces classifieurs ; les scores restent non calibrés.

## Cible exacte

Depuis la clôture ajustée à J :

- excursion haute : `max(0, max(high ajusté J+1…J+20) / close ajusté J − 1)` ;
- excursion basse : `max(0, 1 − min(low ajusté J+1…J+20) / close ajusté J)` ;
- amplitude parcours : le maximum des deux excursions.

Pour chaque date, la cible `oracle_path_extreme20` vaut 1 pour le **TOP20 % des
amplitudes absolues**, dans la population observable et calculable à J. Les
égalités au seuil sont incluses ensemble ; la prévalence peut dépasser 20 %.
Une population à amplitude constante est exclue. Une égalité entre excursions
haute et basse n'empêche pas de connaître l'amplitude : elle reste valide ici,
contrairement au diagnostic directionnel de [P-PATH-0](oracle_dominant_path_separability_h20.md).

Exemple : close J = 20, high à J9 = 32, close J20 = 15. L'amplitude parcours
est au moins **60 %**, même si le rendement terminal est **−25 %**. Le modèle
apprend cette amplitude, **pas** le signe, le jour J9, le prix 32, ni une règle
de vente permettant de capturer le maximum.

L'Oracle terminal garde sa cible TOP/BOTTOM10 % des rendements **finaux**.
Les deux cibles ont donc une sémantique différente, même si chacune vise une
population extrême de l'ordre de 20 %. Aucun avantage du nouveau modèle n'est
encore démontré sur les données réelles.

## Qualité et anti-fuite

- Vingt **séances NYSE**, pas vingt jours civils ; J et J21 sont exclus du maximum.
- Facteur `adj_close/close` appliqué aussi aux high/low. Si adj_close manque,
  fallback close comme dans le contrat historique ; source/convention archivées.
- Aucun remplissage des séances manquantes. Toutes les barres de J à J20 doivent
  avoir OHLC cohérents, prix positifs, volume positif, `is_filled=0`.
- Identité, fournisseur et convention doivent être connus et stables. Les
  ruptures du registre et sauts ajustés inexpliqués d'un facteur 20 sont exclus.
- Features et rangs transverses construits **avant** la sélection des chemins
  qualifiés futurs. Une absence future ne supprime pas rétrospectivement un titre
  de la population des features à J. Un titre sans warm-up observable à J est
  réservé, avec `feature_eligible=false`, avant classement des cibles.
- Minimum vingt titres et **95 %** de chemins qualifiés par journée ; sinon
  aucun label d'entraînement pour cette journée.
- Disponibilité du label fixée à **J21**, même si le maximum arrive à J3.
  La borne de fin de training exclut les fenêtres qui ne sont pas encore disponibles.
- Train : label disponible avant le début de validation. Validation : label
  disponible avant le début du test. Aucun early stopping sur le test.
- Univers de fichier actuel = biais de survivance possible. Les prix ajustés
  sont les versions présentes en base ; ce n'est pas une certification PIT des
  corrections historiques. Les familles optionnelles gardent leurs propres
  réserves de couverture/disponibilité. Ne pas présenter cela comme un PnL.

## Stockage, suivi et séparation

Chaque lancement IHM crée un nouveau batch sous :
`artifacts/models/<nouveau_batch>/oracle_path/`.

| Artefact | Usage |
| --- | --- |
| `protocol.json` | Cible, univers, paramètres, registre, empreinte, backend demandé/politique de sélection et `serving_ready=true` (capacité technique uniquement) |
| `progress.json` | Phase dataset/fold, progression, état COMPLETED/FAILED et erreur |
| `chunks/NNNN/` | Barres cibles archivées, features, chemins bruts et empreintes SHA-256 |
| `labels.parquet` | Tous les chemins observés, raisons de réservation et labels parcours |
| `quality.json` | Couverture, titres absents, warm-up et motifs de rejet |
| `feature_profile.json` | Ordre exact des features et générateur |
| `folds/<date>/path_model.txt` | Poids LightGBM en choix LightGBM ou automatique |
| `folds/<date>/catboost_model.cbm` | Poids CatBoost en choix CatBoost ou automatique |
| `folds/<date>/done.json` | Champion, critère de sélection, métriques validation/test séparées, hashes des deux modèles et du test |
| `folds/<date>/oof.parquet` | Scores et résultats réels du test de ce fold |
| `oof_predictions.parquet` | Ensemble des tests, scores de chaque candidat et du champion, sans doublon date/titre |
| `report.json` et `report.md` | Comparaison OOF AUC/TOP10 %/TOP20 %/10–20–50 titres et amplitudes capturées, pas un PnL |

Le journal normal de campagne `model_training_batch` est utilisé lors d'un
entraînement IHM. **Pas d'écriture dans** `global_oracle_labels`,
`oracle_extreme_predictions`, `global_rank_history`, `model_predictions` ni
`oracle_atr_market_regime_daily` **pendant le training**. La prédiction, elle,
alimente désormais les tables décrites ci-dessous.
Les champions terminal actuels ne sont ni supprimés ni remplacés.

Les checkpoints sont réutilisables par le trainer pour **le même batch et le
même protocole**, après vérification des empreintes. Ils ne constituent pas une
reprise automatique entre deux clics IHM : un deuxième lancement crée une
nouvelle campagne. Ne pas recopier des checkpoints sous un protocole différent.
Les fichiers de progression ont une écriture atomique avec retry borné Windows.
Une comparaison demandée doit terminer **les deux candidats** : aucune panne
CatBoost n'est convertie en succès LightGBM. La reprise vérifie les poids des
deux candidats ; un checkpoint LightGBM seul ne vaut pas comparaison.
Une modification de `--enable-catboost` exige une nouvelle campagne.

Les sélecteurs de prédiction standard et LLM proposent les campagnes parcours
terminées. Les nouveaux contrats portent `serving_ready=true`, au sens de
**capacité technique d'inférence**, pas de performance validée ou de promotion
automatique. Les anciens artefacts `serving_ready=false` restent refusés :
recréer une campagne sous le nouveau contrat, ne pas changer ce flag à la main.

## Prédiction, tables et causalité

`modelFactory.oracle_path.predict` vérifie le protocole/fingerprint, le rapport
terminé, le profil exact, les folds et les empreintes des poids,
et charge le backend choisi pour chaque fold : LightGBM `.txt` ou CatBoost
`.cbm`, avec vérification de l'ordre des features et des empreintes. Pour une
comparaison, la sélection de validation et les deux poids sont contrôlés ;
aucun fallback silencieux. Les anciens contrats LightGBM seuls restent lisibles.
À chaque J,
le fold le plus récent doit démarrer au plus tard J et avoir ses labels train
et validation disponibles **strictement avant J**. Avant le premier fold causal,
la commande est refusée : jamais de fallback vers un modèle appris dans le futur.

Le générateur réutilise le profil archivé, le warm-up et les rangs transverses
sur toute la population entraînée, avant restriction à l'univers demandé.
Aucune cible future/label/parcours réalisé n'est chargé pour prédire. Un symbole
hors univers entraîné, une séance absente, un modèle corrompu ou un profil
incompatible provoquent un échec explicite. H20 est fixe.

| Table | Données parcours |
| --- | --- |
| `oracle_extreme_predictions` | Score d'amplitude sous `proba_extreme`, même clé date/titre/batch. `future_return` et `oracle_extreme10` restent NULL : pas des labels terminaux inventés. |
| `oracle_path_prediction_lineage` | Fold, dernière disponibilité des labels du modèle, cible `oracle_path_extreme20`, horizon 20, hash des poids et du profil. |
| `model_predictions` | Adaptateur de politique explicite `source=oracle_path_policy`, `selected_model=oracle_path_long_policy`, `calibration_method=rank_policy`. La force d'allocation est un percentile, **pas une probabilité de hausse**. |

Les scores et leur lineage sont persistés **dans la même transaction**, par
tranches de vingt séances, avec upsert idempotent. La table compagnon est créée
au premier predict via DDL idempotent (SQL aussi dans
`database/sql/oracle/oracle_path_prediction_lineage.sql`). Le chargement strict
vérifie lineage/hashes/disponibilité et refuse les lignes mélangées avec des
labels terminaux. L'adaptateur politique n'est publié qu'après un predict réussi.

## Sens des positions et raccordement 10 → 11 → 12

```yaml
oracle_path:
  direction_policy: long_only  # long_only | abstain
```

Sans filtre directionnel, `long_only` signifie **une stratégie volontaire**
sur le pool d'amplitude, pas une direction apprise. `abstain` n'autorise aucune
nouvelle entrée. Tous les titres scorés ont une ligne politique ; le TOP est
déterminé ensuite par le gate Oracle/tradable et éventuellement ATR. Cela évite
un préfiltrage sur un autre dénominateur d'univers.

1. Dans **10. ML Predict**, choisir le batch parcours terminé. En historique,
   définir début/fin puis **Prédire l'univers sélectionné**. En quotidien,
   la date de signal est la dernière séance clôturée résolue par le calendrier US.
2. Sans LLM, **11. Risk Management** reçoit le même batch (choix quotidien
   conservé en session), une politique Oracle/tradable `filter_then_top20` et la
   racine d'artefacts. Scores/date/batch sont exacts ; aucun score ancien ou d'une
   autre source ne sert de fallback. Les percentiles sur l'univers tradable sont
   utilisés pour l'allocation. Kelly est interdit pour cette force non directionnelle.
3. Les gardes de nouvelles entrées, régime, capital, positions, liquidité et
   données restent actives. **12. Exécution** conserve les gardes PAPER/LIVE,
   l'autorisation du compte et les protections normales existantes. Aucune nouvelle
   politique SL/TP/trailing n'est activée par la case d'entraînement.
4. Le filtre GPT/DeepSeek peut consommer ces scores, avec contrôle de lineage.
   Il fournit alors LONG/SHORT/abstention séparément et garde son contrat **PAPER
   uniquement** ; ni Web historique ni utilisation LLM en LIVE ne sont autorisés.

Le chargement général des prévisions directionnelles exclut `oracle_path_policy`
sans demande explicite : aucun autre pipeline ne peut prendre ces rangs
d'amplitude pour des probabilités LONG/SHORT. Sélectionner un modèle ne démarre
ni broker ni watcher ni ordre automatiquement.

## Backtest

Après le predict historique, choisir le même batch ML et batch Oracle dans
**Backtesting**. Mode `extreme_gate` : LONG-only, score d'amplitude seul, bypass
des confirmations per-symbol inexistantes. Le CLI impose cette sémantique pour
un batch parcours ; pas de short implicite ni calibrateur appris sur les labels
terminaux H20. Les options tradable/ATR, capital, sizing, coûts et sorties du
backtest restent configurables. Pour comparer au live, choisir la **même**
politique tradable/preset et les mêmes protections ; ce raccordement ne certifie
pas une parité avec des fills broker réels.

`oracle_path.direction_policy=abstain` bloque le backtest LONG-only ; choisir
explicitement `long_only` pour cette expérience. Les labels d'amplitude ne
constituent ni un PnL ni une promesse de vente au maximum futur.

## Validation de l'implémentation

Raccordement du **13 octobre 2026** : **631 tests ciblés réussis**, dont vingt
tests d'inférence/lineage/politique dédiés, avec un vrai petit LightGBM local.
Couverts : refus des folds futurs, modèle/profil corrompu ou non prêt,
univers/DB incorrects, rangement sans cible future, score et lineage atomiques,
lecture stricte, propagation du batch 10→11, et classement backtest amplitude
sans direction inventée. Risque, LLM, protections, commandes backtest et batchs
existants sont aussi testés. Deux anciennes assertions ont été rendues
compatibles avec la configuration utilisateur (modèle supprimé après reset,
horaire us_pipeline actuellement 23:05), sans changer cette configuration.

Cette validation est **technique et hors ligne**. Après la remise à zéro, les
trois campagnes US fournies sont des modèles **TP avant SL**, pas parcours H20.
Il faut entraîner une **nouvelle campagne parcours** depuis l'IHM, puis la
sélectionner dans 10. Aucun modèle réel parcours n'a été entraîné ici, aucune
prédiction de portefeuille réel n'a été publiée, aucun ordre n'a été envoyé.

Un ancien test de reset non isolé a été exécuté ensuite : risque de suppression
des historiques/cache réels, désormais bloqué et testé. Les trois modèles
avaient déjà été retirés depuis Diagnostics ML avant ce test ; les rapports
des neuf simulations sont conservés. [Chronologie et correctifs](securisation_tests_reset_20261013.md).

Tests synthétiques : mouvements intermédiaires opposés au rendement final,
ajustements de split, égalités, séances manquantes, données remplies/invalides,
ruptures d'identité, maturité J21, rangs globaux, conflits de modes, commande IHM,
petit entraînement LightGBM réel, séparation des folds et reprise des checkpoints.
Ces tests techniques ne constituent pas une preuve de performance économique.

Validation initiale du 11 octobre : **221 tests réussis, 2 ignorés**. Les **28 tests du
nouveau mode** passent, dont le formulaire Streamlit complet, le changement de
mode et un vrai petit entraînement LightGBM synthétique. Deux tests E2E plus
anciens restent en échec (clés du bloc sentiment et attente `cash` au lieu du
défaut courant `margin`) ; l'échec est reproduit en mémoire sur le code Git
antérieur, sans nos modifications. Ils ne sont pas comptés comme réussis et
aucun changement de configuration trading n'a été fait pour les faire passer.

Code principal : `modelFactory/oracle_path/`, orchestration Model Factory,
`ihm/pages/_execution_center/` et constructeur des commandes Pipeline.

## Suite après le premier entraînement

Lire d'abord qualité et coverage. Comparer ensuite les deux modèles sur les
mêmes dates, titres, features et folds, avec capture du TOP réel des amplitudes
parcours à taille de sélection identique. ATR seul doit rester une baseline.
N'ajouter ni TP/SL optimisé ni une promesse D1/D10 à partir des maxima ex post.

Depuis le 12 octobre, le [mode séparé TP avant SL](oracle_barrier_training.md)
permet explicitement une autre expérience : TP 20 %, SL 10 % actuellement configurable, entrée J+1 open,
avec deux modèles LONG/SHORT. Il ne change pas le label d'amplitude de ce guide.
