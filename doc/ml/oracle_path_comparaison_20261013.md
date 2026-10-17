# Oracle parcours H20 — comparaison LightGBM / CatBoost

## Objectif et protocole figé

Comparer les deux classifieurs sur la **même cible d'amplitude** : TOP20 % des
mouvements absolus maximaux entre J+1 et J+20, depuis le close ajusté J. Aucun
modèle directionnel LONG/SHORT, aucun TP/SL ni PnL dans cette comparaison.

Campagne de recherche : `artifacts/research/oracle_path_comparison/20261013-v1`.
Univers : `config/univers/univers_filtred_tradable.txt`, contenu et SHA-256
figés dans `plan.json`. Historique **2016-01-01 → 2023-12-31**, conformément
au défaut IHM demandé. Les fenêtres cibles doivent être disponibles avant cette
borne. **2024–2026 ne servent pas au choix des champions.** Ces années ont déjà
été examinées dans d'autres expériences ; elles ne sont pas un holdout vierge.

Features dynamiques expert et paramètres tabulaires repris des défauts de
Pipeline ; profil, features exactes et configuration complète archivés.
Walk-forward : train minimum 504 séances, validation 126, test 126, pas 126,
maximum 15 folds. Purge fondée sur la disponibilité J+21 du label. Univers
statique actuel et prix ajustés présents en base : réserves de survivance et
de révision historique, pas certification PIT intégrale.

| Candidat | Objectif | Arrêt / choix |
| --- | --- | --- |
| LightGBM CPU | Binary | Early stopping sur la validation chronologique |
| CatBoost CPU | Logloss, évaluation AUC | Détecteur de surapprentissage sur la même validation |
| Champion de chaque fold | AUC de validation maximale | Égalité exacte → LightGBM |

Les modèles ont leurs hyperparamètres propres (pas nécessairement le même
nombre d'arbres), mais **les lignes et colonnes d'entrée sont identiques**.
Aucun ajustement automatique de poids, seuils ou hyperparamètres sur le test.
Un seul backend sert le score de chaque fold, sans ensemble moyen. CatBoost
est obligatoire pour terminer une comparaison demandée ; une erreur ne fait
pas disparaître le challenger du rapport. Une classe constante dans le test
ne retire pas le fold : l'AUC de test reste indisponible, les autres mesures
restent rapportées.

## Ce qui est mesuré

- AUC, prévalence et couverture du test.
- Précision/rappel des TOP10 % et TOP20 % (fractions de l'univers).
- Précision et amplitude moyenne des **10, 20 et 50 premiers titres**, triés
  par score puis symbole pour départager les égalités.
- Nombre de dates ayant assez de titres pour chaque taille, sinon `null`.
- Même diagnostic pour chacun des candidats et pour les champions sélectionnés.

Les amplitudes réalisées sont des maxima a posteriori, **pas des rendements
encaissables**. L'OOF permet de comparer, pas de rechoisir rétrospectivement le
modèle servi. Une supériorité moyenne ne démontre ni stabilité annuelle ni
profitabilité ; il faudra regarder les folds et les dates, puis un replay
avec mêmes coûts, sizing et sorties, après décision distincte.

## Pas de LSTM à cette étape

Le LSTM n'est pas exclu par principe. Il exige une entrée séquentielle, alors
que ces deux challengers reçoivent un vecteur de features à J comprenant déjà
des historiques calculés. Ajouter des séquences change aussi la représentation,
le warm-up et la couverture : ce ne serait plus le même simple comparatif.
Premier jalon : LightGBM/CatBoost, puis éventuel challenger LSTM indépendant,
avec protocole de séquences et budget de calcul explicites. Aucun LSTM n'est
entraîné ici malgré les anciens paramètres génériques de la page.

## Fichiers et suivi

`scripts/research/oracle_path_comparison.py` exécute uniquement des lectures SQL
sur `alpha_trade` ; les sessions MySQL sont configurées en transaction read-only.
Les modèles sont stockés dans le dossier de recherche, pas promus dans les
sélecteurs de production. Aucun journal SQL de campagne, prédiction, modèle
actuel, batch, compte ou ordre n'est modifié.

- `plan.json` : configuration, univers et empreintes du code, sans secrets.
- `run.json` : RUNNING/COMPLETED/FAILED, PID et erreur éventuelle.
- `models/oracle-path-comparison/oracle_path/progress.json` : phase, tranche/fold.
- `models/oracle-path-comparison/oracle_path/report.json` et `report.md` : résultats.
- `folds/<date>/done.json` : choix en validation, diagnostics test séparés et hashes.
- `oof_predictions.parquet` : deux scores candidats, score choisi et backend.
- `stdout.log` / `stderr.log` : sortie du lancement local.

Commande reproductible (une seule instance à la fois) :

```powershell
python -u -m scripts.research.oracle_path_comparison --output artifacts/research/oracle_path_comparison/20261013-v1
```

Les défauts sont 2016–2023 et le fichier tradable ; `--start`, `--end` et
`--symbol-source` permettent un **nouveau** protocole. Le même dossier est
repris uniquement si le plan est identique et les checkpoints intacts.
Ne pas effacer le plan ou altérer les flags pour contourner cette vérification.

## IHM et serving

Dans le mode parcours, LightGBM est le candidat de base obligatoire ;
« Comparer CatBoost à LightGBM — Oracle parcours » est cochée par défaut
dans une nouvelle session. Le CLI garde CatBoost opt-in `--enable-catboost`.
Le loader commun à ML Predict/backtest/live suit le champion de chaque fold,
vérifie ses poids et l'ordre des features ; aucun fallback silencieux.
Les modèles LightGBM seuls d'avant ce comparatif restent lisibles.

Validation technique : vrais petits entraînements locaux des deux algorithmes,
reprise et corruption des checkpoints, fit CatBoost en échec, serving réel d'un
champion CatBoost, sélection inchangée lorsque seuls les labels de test sont
inversés. Ces fixtures **ne sont pas** une démonstration de supériorité financière.

Statut des résultats réels : consulter `run.json` et les rapports de la campagne ;
ne pas prendre cette description du protocole pour un résultat terminé.

## Résultats vérifiés après exécution — 13 octobre 2026

**COMPLETED**, fin à 20:32:52 Paris. Dix folds disponibles, aucun fold réservé.
1 790 titres observés, 173 features, 2 146 823 lignes OOF et 1 260 séances
testées entre **2018-07-05 et 2023-07-07**. La période demandée était 2016–2023 :
le début sert au train/validation ; les dates finales qui ne forment pas un
fold complet ou dont les labels ne sont pas matures ne sont pas incluses dans
ces métriques. **Ce rapport ne teste pas 2024, 2025 ou 2026.**

| Mesure OOF | LightGBM | CatBoost | Champions choisis en validation |
| --- | ---: | ---: | ---: |
| AUC agrégée | 0,7991 | 0,8088 | 0,7990 |
| Précision des 10 premiers titres | 85,51 % | 86,89 % | 85,33 % |
| Précision des 20 premiers titres | 82,08 % | 82,90 % | 81,87 % |
| Précision des 50 premiers titres | 76,63 % | 76,73 % | 76,67 % |
| Amplitude moyenne des 10 premiers titres | 35,29 % | 36,08 % | 35,07 % |
| Amplitude moyenne des 20 premiers titres | 32,70 % | 33,37 % | 32,52 % |
| Amplitude moyenne des 50 premiers titres | 29,20 % | 29,22 % | 29,15 % |

Précision = part des sélections appartenant au **vrai TOP20 % d'amplitude
parcours du jour**, pas taux de trades gagnants, réussite directionnelle ou
probabilité d'atteindre +20 %. L'amplitude maximale est absolue, hausse **ou**
baisse ; la moyenne de tout l'univers est 13,23 %. Pas d'exécution au pic.

### Stabilité et décision

- CatBoost est retenu par le critère figé de validation dans **6 folds**, et
  LightGBM dans **4**. Les différences de validation sont souvent petites.
- En test, CatBoost gagne sur l'AUC dans **6/10 folds**, mais sur la précision
  TOP10 et l'amplitude TOP10 dans seulement **5/10**.
- Son avantage global TOP10 (+1,38 point de précision et +0,79 point
  d'amplitude) est porté surtout par **2020-07-07 → 2021-01-04** : précision
  85,71 % contre 70,95 %, amplitude 46,16 % contre 35,14 %.
- Diagnostic rétrospectif sans ce fold : sur les neuf autres, delta moyen
  CatBoost − LightGBM **−0,106 point de précision** et **−0,351 point d'amplitude**
  TOP10. Il ne s'agit **pas** d'une règle d'exclusion, ni d'un signal permettant
  d'anticiper 2020, ni d'une nouvelle sélection de champion.
- La politique de champions choisis en validation n'améliore pas ici le TOP10
  agrégé par rapport à LightGBM seul. Mélanger des probabilités non calibrées de
  folds/backends change aussi leur comparabilité : l'AUC poolée n'est pas une
  mesure de stabilité annuelle. Les sélections quotidiennes sont plus directement
  liées à notre objectif de concentration.

**Conclusion : CatBoost est un challenger crédible avec un petit avantage moyen,
pas un gagnant stable démontré ni une promotion automatique.** Conserver le
comparatif et son protocole ; ne pas réécrire les champions après lecture du test.
Pas de conclusion directionnelle ni économique, aucune comparaison à ATR ou à
l'ancien Oracle terminal dans ce run. LSTM non ajouté.

### Contrôles de fin

Les dix contrats et choix de validation sont valides ; SHA-256 des sources
inchangés et tous les poids/parquets de fold contrôlés. Scores finis, score
du champion égal à celui de son candidat, disponibilité train avant validation
et validation avant test, **zéro doublon date/titre**. Rapports locaux concordants,
`run.json` et `progress.json` terminés. Pas de SQL, prédiction de production,
ordre ni promotion déclenchés par cet audit.

Suite proposée puis **autorisée et lancée le 13 octobre** : comparer ces branches figées sur 2024–2026,
avec couverture et résultats par année, puis seulement un replay économique
identique si justifié. Un training IHM jusqu'à une autre borne est une nouvelle
campagne, pas la validation de cette expérience.
[Protocole de confirmation et suivi](oracle_path_confirmation_2024_2026.md).

Lancement vérifié le **13 octobre à 20:13 Paris** : 1 790 symboles, 72 tranches
dataset, processus Python de calcul 33644 (launcher venv 12412). Au premier
contrôle, `run.json` et `progress.json` indiquent RUNNING/dataset. Aucun résultat
historique n'est encore conclu. Validation technique finale : **274 tests
ciblés passent**, dont cinq tests de comparaison et les tests path/barrier,
serving, commande Pipeline, contrat d'artefacts, cascade et source des prédictions.
