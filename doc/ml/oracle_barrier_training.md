# Oracle TP avant SL — amplitude et direction, mode de recherche séparé

Implémentation du 12 octobre 2026, autorisée avec apprentissage directionnel.
La livraison initiale n'avait pas lancé de campagne réelle. Le batch utilisateur
`model-factory-20261011221400-867a1e` est désormais **entraîné** : 12 folds,
OOF juillet 2018–juillet 2024. [Audit TOP10 et direction](oracle_barrier_top10_audit_20261012.md) :
classement par sens informatif, choix LONG/SHORT non validé. **Aucun résultat
économique ou serving obtenu**, 2025–2026 pas testées dans la campagne OOF.
Une [comparaison économique LONG séparée et une grille TP/SL](oracle_tp_sl_grid_20261012.md)
ont ensuite été lancées sur 2025–2026, avec modèles figés et réserves de données
explicites ; ce n'est pas une validation du choix automatique LONG/SHORT.
L'Oracle terminal H20, l'Oracle parcours et la cascade PAPER/LIVE ne sont pas
remplacés. Une mauvaise confirmation directionnelle permettra d'abandonner cette
branche sans changer les modèles existants.

## Paramètres configurables et figés par campagne

Dans `config.yaml` :

```yaml
oracle_barrier:
  take_profit_pct: 0.20
  stop_loss_pct: 0.07
  max_sessions: 20
```

Ce sont des **fractions** : `0.20` = 20 %, pas `20`. TP/SL doivent être finis,
strictement entre 0 et 1 ; la durée est un entier de 1 à 60 séances. Le formulaire
affiche les valeurs et sa commande les reprend explicitement. Les overrides CLI
sont possibles ; chaque valeur effectivement utilisée est archivée. Un changement
TP/SL/durée/features/seuil/protocole exige une **nouvelle campagne**.

Ce bloc ne change pas les protections des ordres existants, le profil LLM, les
barrières ATR de l'ancien triple-barrier ni les listes de l'étude quotidienne.
Pas de trailing dans ce contrat de recherche.

## Lancer depuis l'IHM

1. **Workflow & Orchestration → Pipeline**, marché **US**.
2. Déplier **⚙️ Paramètres d'exécution → Paramètres Model Factory**.
3. Vérifier **🎯 Oracle TP avant SL — amplitude + direction LONG/SHORT, recherche uniquement**.
   Depuis le 13 octobre 2026, cette case est **décochée par défaut** ; le défaut
   est [Oracle Extreme parcours H20](oracle_path_training.md), un classifieur
   d'amplitude unique. Décocher parcours avant de sélectionner TP avant SL.
   **Entraîner aussi le modèle Oracle Extreme** reste décochée. Les choix manuels
   sont conservés en session.
   Oracle terminal, Oracle parcours et bundle
   per-symbol ne sont pas combinés à ce lancement.
4. Choisir le jeu **expert** et les familles souhaitées, ou un profil JSON de
   features Oracle. En mode dynamique, les familles cochées sont reprises ; le
   profil JSON impose sa liste. Le modèle est global multi-titres, **pas per-symbol**.
5. Dans le bloc **9. ML Train**, choisir **univers_filtred_tradable.txt** et
   renseigner une date de début **et** de fin. Pour un protocole historique initial,
   `2016-01-01 → 2024-12-31` garde 2025/2026 hors de cette campagne ; ces années ont
   toutefois déjà été analysées ailleurs et ne sont pas des holdouts entièrement vierges.
6. Walk-forward est forcé : minimum train **504**, validation **126**, test
   **126**, pas **126**, maximum **15 folds**, à adapter seulement **avant** le run.
   Le pas doit être au moins aussi grand que le test. Choisir **rebuild-all**.
7. Vérifier la commande, puis **Entraîner l'univers sélectionné**.

La commande doit contenir :

```text
--oracle-barrier-model-only --oracle-barrier-tp-pct 0.2 --oracle-barrier-sl-pct 0.07 --oracle-barrier-max-sessions 20 --walkforward
```

Elle ne doit pas contenir `--oracle-model-only`, `--oracle-path-model-only` ou
`--directional-feature-profiles`. Les champs génériques LSTM/CatBoost/Global
Ranking, cible terminale, multiples ATR, calibration Platt et sélection champion
ne pilotent pas ce mode ; le backend est **deux LightGBM binaires CPU**, avec les
hyperparamètres LightGBM et le nombre de workers configurés.
Le générateur partagé est actuellement adossé à **SPY** ; un autre benchmark est
refusé dans ce nouveau mode, plutôt que d'afficher un paramètre qui serait ignoré.

Ne pas enchaîner 10/11/12 avec ce batch de recherche. L'inférence standard le
refuse et le sélecteur Pipeline le masque. Il n'émet **aucun ordre**.

## Ce que les modèles apprennent exactement

Décision avec les features connues à **J**, entrée hypothétique à l'**open J+1**.
Le prix de clôture J n'est pas le prix d'entrée. La séance d'entrée est la séance
de détention 1 ; les barrières sont surveillées jusqu'à la séance 20 incluse.
Si aucune barrière n'a été atteinte, sortie à l'open de la séance de détention 21,
donc **J+21** dans le calendrier des décisions. Ce ne sont pas des jours civils.

| Modèle | TP | SL | Cible positive |
| --- | --- | --- | --- |
| LONG | entrée × 1,20 | entrée × 0,93 | TP atteint avant SL pendant la détention |
| SHORT | entrée × 0,80 | entrée × 1,07 | TP atteint avant SL pendant la détention |

Une sortie SL ou expiration vaut **0** pour le sens concerné. Une expiration
peut être légèrement profitable, mais n'est pas un succès TP. Un arrêt déjà
touché ne peut pas redevenir un succès lorsque le prix s'inverse plus tard.

Exemple illustratif : entrée 100, high 122 à J9, low 69 à J18, close 74 à J20.
Si aucune barrière adverse n'a été touchée avant J9 : LONG = succès TP 20 %, SHORT
= échec SL. La chute finale ne transforme pas cet exemple en succès SHORT.
Le maximum absolu et le rendement terminal donnent donc des cibles différentes.

Ces cibles sont des **succès de barrières**, pas les déciles D1/D10 terminaux.
Ce modèle peut apprendre une orientation exploitable hypothétique, mais ni sa
fiabilité ni sa rentabilité ne sont garanties par le changement de label.

## Ordre des contacts et exclusions

- L'open de chaque séance est examiné **avant** ses high/low. Un gap traversant
  une barrière est un contact résolu à l'open ; une perte peut dépasser 7 %.
- Sinon, un seul niveau touché donne TP ou SL à ce niveau. Si high et low
  touchent **les deux barrières du même sens dans la même bougie**, l'ordre est
  inconnu : cible de ce sens `NULL`, `AMBIGUOUS`, jamais ordre inventé.
- Le sens opposé peut rester qualifié s'il a un contact non ambigu. Le label
  agrégé `either_tp_before_sl` n'est renseigné que si les deux sens sont qualifiés.
- Aucun prix d'exécution ou rendement n'est publié pour une cible réservée.
- Les contacts/gaps sont des hypothèses OHLC, **pas des fills garantis**. En
  particulier, liquidité, spread, slippage, frais, emprunt SHORT et contraintes
  portefeuille ne sont pas incorporés dans ces labels.

## Sorties et lecture de la direction

- `long_tp_before_sl`, `short_tp_before_sl` : les deux labels 0/1/NULL.
- `proba_long_tp_before_sl`, `proba_short_tp_before_sl` : les deux scores appris,
  **non calibrés**, pas des probabilités complémentaires ; leur somme n'est pas 1.
- `max_tp_before_sl_score` : maximum des deux scores, utilisable pour classer
  le potentiel de succès. Ce n'est **pas** une probabilité d'union calibrée.
- `research_direction` : sens du score le plus élevé uniquement si celui-ci
  atteint le `decision_threshold` choisi avant entraînement ; égalité à
  `1e-12` près, score manquant ou scores trop faibles → `ABSTAIN`.
- `chosen_tp_before_sl` : résultat réel du sens choisi, pour l'évaluation OOF.
- `long/short_outcome`, dates/prix de sortie et `gross_return` : diagnostic
  hypothétique brut, **pas un backtest du portefeuille**.

Le seuil est archivé dans le protocole et ne doit pas être ajusté après lecture
des pertes. L'agrégat et la direction sont distincts : un bon classement
d'amplitude n'implique pas une direction fiable. Ne pas convertir ces scores en
ordres ou en tailles de position avant une qualification séparée.

## Anti-fuite, prix et couverture

Toutes les séances J à J+21 doivent avoir des OHLC positifs/cohérents, un volume
fini positif et `is_filled=0`, avec identité/source/convention connues et stables.
Les ruptures du registre, identités nulles/0 et sauts ajustés inexpliqués 20× sont
exclus. Pas de remplissage des prix manquants. Même un TP précoce exige la
qualification du chemin complet : cela est conservateur et limite la couverture.

Les OHLC sont ramenés sur la même base par `adj_close/close` (fallback close
lorsqu'adj_close manque). Les splits cohérents ne deviennent pas des faux TP.
Cette base ajustée actuelle n'est **pas** une preuve historique des révisions
ni un traitement complet des dividendes cash pour une exécution réelle.

Disponibilité conservatrice du label à **J+22** pour les deux sens, même si TP
arrive J2. Train : disponibilité strictement avant validation ; validation :
strictement avant test. L'early stopping ne lit jamais le test. La fin de
training borne la disponibilité, pas uniquement la date de décision.

Les rangs de features sont construits sur toute la population observable à J,
avant sélection des labels futurs qualifiés et **après** réunion des tranches.
Les tests OOF conservent aussi les candidats aux chemins futurs inconnus. Les
sélections TOP10/TOP20 sont faites **avant** de retirer les résultats inconnus :
pas de remplacement par des titres mieux documentés. Le rapport donne toujours
sélectionnés, évalués et exclusions. Il n'impose pas le seuil de couverture du
modèle parcours : ces cibles absolues ne sont pas des rangs de la population.

L'univers est un fichier actuel, pas un univers historique PIT : survivance
possible. Les familles optionnelles gardent leurs propres limites PIT/lineage.
Il faut lire `quality.json`, les résultats par fold et leurs couvertures avant
toute interprétation de performance.

## Stockage et suivi

Répertoire : `artifacts/models/<nouveau_batch>/oracle_barrier/`.

| Artefact | Contenu |
| --- | --- |
| `protocol.json` | TP/SL/durée, seuil, univers, features, registre, contrat et empreinte |
| `progress.json` | Dataset/fold, compteurs et état COMPLETED/FAILED |
| `chunks/NNNN/` | Barres, labels, features, SHA-256 ; reprise par tranche |
| `labels.parquet` | Chemins, contacts LONG/SHORT, qualifications et labels |
| `quality.json` | Couverture, titres absents, warm-up, motifs et types de sorties |
| `feature_profile.json` | Colonnes X ordonnées et générateur |
| `folds/<date>/long_model.txt` et `short_model.txt` | Deux modèles du fold |
| `folds/<date>/oof.parquet` | Scores et choix sur le test non utilisé pour régler le modèle |
| `oof_predictions.parquet` | Tous les tests sans doublon date/titre |
| `report.json` et `report.md` | AUC/TP-rate/précision, couverture, abstention et baselines directionnelles |

Un sens à cible train/validation constante est réservé, sans inventer son score.
La campagne exige au moins un fold où les deux modèles ont pu être entraînés.
Le test à cible constante reste évalué ; son AUC peut être `NULL`.

Les checkpoints sont réutilisables pour le même batch/protocole après vérification
de leurs empreintes ; chaque nouveau clic IHM crée cependant une nouvelle campagne.
La progression JSON est atomique avec retry Windows. Aucun artefact terminal ou
parcours existant ne peut être remplacé par cette branche.

Le journal normal de campagne `model_training_batch` s'applique à un futur
lancement IHM. Aucun changement de schéma ni écriture dans les tables de labels,
prédictions Oracle terminal, classement global ou étude Oracle × ATR. Les tests
d'implémentation utilisent des données synthétiques, sans base/API/broker.

## Décision après la première campagne

Comparer d'abord les AUC et TP-rate **par fold**, la stabilité et la couverture.
Le diagnostic de direction compare les choix à toujours LONG et toujours SHORT
sur les **mêmes observations qualifiées**, avec toutes les abstentions et exclusions
visibles. Ce n'est pas encore un test de coûts/risque net.

Si la direction n'apporte rien de stable, ne pas promouvoir les choix LONG/SHORT.
On pourra revenir, avec un nouveau protocole explicite, à une branche amplitude
uniquement ; cela ne transforme pas automatiquement les deux modèles en un
Oracle d'amplitude validé. TP 20 % est le point de départ demandé, pas un optimum.

Références : [Oracle parcours](oracle_path_training.md), [Oracle terminal](oracle/README.md).

## Vérification technique

Tests sur prix synthétiques : hausse puis chute, baisse puis reprise, arrêt des
deux sens avant un mouvement tardif, entrée J+1, gaps, contacts exacts, collisions
intrabar, expiration, split, données manquantes/remplies, identité, maturité et
conflits de modes. Petit entraînement LightGBM réel à deux modèles, checkpoints
par tranche/fold, empreintes et reprise, purge temporelle et formulaire Streamlit
complet. Aucune base externe, API ou exécution broker utilisée par ces tests.

La vérification ciblée inclut aussi les configurations/CLI/orchestration et les
parcours Pipeline/Oracle existants. Ce n'est pas l'exécution de toute la suite
du dépôt ni une certification économique ou PIT du corpus réel.

Résultat final : **295 tests réussis, 2 ignorés**, dont **51 tests du nouveau mode**.
La couverture globale du dépôt n'est pas mesurée par ce sous-ensemble (`--no-cov`) ;
son seuil général de 70 % ne peut pas être satisfait en n'exécutant que ces tests.
