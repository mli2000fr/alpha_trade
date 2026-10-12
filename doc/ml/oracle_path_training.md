# Oracle Extreme parcours H20 — mode d'entraînement distinct

Implémenté le 11 octobre 2026. L'Oracle terminal actuel, son batch de production,
ses tables et ses paramètres par défaut restent inchangés. L'entraînement sur
l'univers réel n'a pas été lancé pendant cette implémentation.

## Lancer depuis l'IHM

1. Ouvrir **Workflow & Orchestration → Pipeline**, marché **US**.
2. Déplier **⚙️ Paramètres d'exécution**, puis **Paramètres Model Factory**.
3. Cocher **🔮 Oracle Extreme parcours H20 — modèle séparé, recherche uniquement**.
   Cette case est décochée par défaut. Le bundle Oracle terminal/LONG/SHORT et
   l'Oracle terminal sont désactivés pour ce lancement ; leurs contrats ne changent pas.
4. Choisir le jeu de features **expert**. Les familles de features cochées sont
   utilisées en mode **Dynamique** ; un profil JSON impose sa propre liste et son
   générateur. Les mêmes réglages sont à conserver pour une comparaison équitable.
5. Dans les paramètres de training, renseigner les dates de début et fin.
   Pour une première campagne historique : **2016-01-01 → 2024-12-31**. Les années
   2025/2026 ne sont ainsi pas incorporées dans cet entraînement, mais elles ont
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
**pas** `--oracle-model-only` ou `--enable-oracle-model`. Ne pas enchaîner 10/11/12
pour exploiter ce nouveau batch : ce mode est une branche de recherche, pas un
remplacement du modèle de la cascade actuelle.

Le backend est un classifieur **LightGBM CPU**. Les paramètres LightGBM du bloc
avancé (profondeur, itérations, learning rate, régularisation, sous-échantillonnage,
early stopping) et le nombre de workers sont repris. Les options LSTM, CatBoost,
Global Ranking, per-symbol, optimisation des cibles et calibration Platt ne
changent pas ce classifieur ; les probabilités sont des scores non calibrés.

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
| `protocol.json` | Cible, univers, paramètres, registre, empreinte et `serving_ready=false` |
| `progress.json` | Phase dataset/fold, progression, état COMPLETED/FAILED et erreur |
| `chunks/NNNN/` | Barres cibles archivées, features, chemins bruts et empreintes SHA-256 |
| `labels.parquet` | Tous les chemins observés, raisons de réservation et labels parcours |
| `quality.json` | Couverture, titres absents, warm-up et motifs de rejet |
| `feature_profile.json` | Ordre exact des features et générateur |
| `folds/<date>/path_model.txt` | Modèle indépendant de chaque fold |
| `folds/<date>/oof.parquet` | Scores et résultats réels du test de ce fold |
| `oof_predictions.parquet` | Ensemble des tests, sans doublon date/titre |
| `report.json` et `report.md` | AUC, précision/rappel TOP10/TOP20 et amplitudes capturées |

Le journal normal de campagne `model_training_batch` est utilisé lors d'un
entraînement IHM. **Pas d'écriture dans** `global_oracle_labels`,
`oracle_extreme_predictions`, `global_rank_history`, `model_predictions` ni
`oracle_atr_market_regime_daily`. Aucun schéma SQL ni migration nécessaire.
Les champions terminal actuels ne sont ni supprimés ni remplacés.

Les checkpoints sont réutilisables par le trainer pour **le même batch et le
même protocole**, après vérification des empreintes. Ils ne constituent pas une
reprise automatique entre deux clics IHM : un deuxième lancement crée une
nouvelle campagne. Ne pas recopier des checkpoints sous un protocole différent.
Les fichiers de progression ont une écriture atomique avec retry borné Windows.

Le sélecteur de prédiction standard masque les batches parcours situés sous
`artifacts/models` ; le CLI bloque aussi un dossier parcours explicitement choisi.
Il faudra qualifier séparément l'inférence, les seuils et une éventuelle promotion.

## Validation de l'implémentation

Tests synthétiques : mouvements intermédiaires opposés au rendement final,
ajustements de split, égalités, séances manquantes, données remplies/invalides,
ruptures d'identité, maturité J21, rangs globaux, conflits de modes, commande IHM,
petit entraînement LightGBM réel, séparation des folds et reprise des checkpoints.
Ces tests techniques ne constituent pas une preuve de performance économique.

Validation finale ciblée : **221 tests réussis, 2 ignorés**. Les **28 tests du
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
permet explicitement une autre expérience : TP 20 %, SL 7 %, entrée J+1 open,
avec deux modèles LONG/SHORT. Il ne change pas le label d'amplitude de ce guide.
