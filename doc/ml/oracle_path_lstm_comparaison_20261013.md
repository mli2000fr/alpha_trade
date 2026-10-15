# Oracle parcours H20 — comparaison avec un LSTM global

## GO et périmètre

13 octobre 2026 : GO utilisateur après comparaison LightGBM/CatBoost, puis
confirmation 2024–2026. **Expérience séparée**, aucun raccordement du LSTM
au predict/live/backtest de production et aucune promotion automatique.
SQL et brokers non utilisés : calcul entièrement basé sur les archives locales.

Sources inchangées :

- `artifacts/research/oracle_path_comparison/20261013-v1` : données/folds du training 2016–2023.
- `artifacts/research/oracle_path_confirmation/20261013-v1` : features/labels de 2024–2026.

Run actif : `artifacts/research/oracle_path_lstm/20261013-v2`.
Le dossier v1 conserve le premier essai interrompu et ses checkpoints ; voir
la remédiation technique ci-dessous. Sources historiques/confirmation inchangées.
Univers exact des modèles : **1 790 titres**, fichier tradable du protocole
original ; ordre exact des **173 features** conservé. Aucune nouvelle source,
aucun ajout de consensus/news non présents dans le profil. Les cibles ne changent pas.

## Cible, folds et confirmation

Cible : vrai TOP20 % qualifiable de l'amplitude maximale absolue entre **J+1 et
J+20**, depuis le close ajusté J. Disponibilité conservatrice **J+21**. Toujours
pas une cible LONG/SHORT, TP avant SL ou prix maximal encaissable.

Les **dix mêmes folds** chronologiques sont reconstruits depuis les labels
archivés, puis vérifiés contre les dates et nombres de lignes train/validation
de l'expérience d'origine. Train : disponibilité du label avant début de
validation ; validation : disponibilité avant début de test. Aucune sélection
d'époque, de normalisation, de paramètre ou de seuil sur le test.

Après ces folds, les trois modèles du dernier fold **2023-01-05** sont figés
pour la comparaison 2024–2026. Ils n'apprennent ni toute l'année 2023, ni les
années suivantes. Borne de confirmation reprise : **2026-10-09 as-of**, dernière
date mature théorique **2026-09-10** ; les dates plus récentes restent immatures.
Les années 2024–2026 ont déjà été examinées : **pas un holdout vierge**.

## Contrat séquentiel

Une entrée LSTM comprend **40 séances NYSE consécutives**, de J−39 à J inclus.
Les 173 features de chaque séance sont celles du générateur archivé : elles
peuvent déjà résumer une histoire plus longue (momenta, volatilités, etc.).

- Un seul symbole par séquence, tri date croissant, fin exactement à J.
- Une séance absente invalide la fenêtre ; pas de compression sur les « 40
  dernières lignes disponibles » et pas de forward fill.
- Identité, source et ajustement doivent être connus et stables sur la fenêtre.
  Les ruptures du registre sont exclues, même si les deux côtés ont le même ticker.
- Les fenêtres ne traversent pas une ligne dont toutes les features sont absentes.
  Des features individuelles manquantes sont autorisées avec un masque explicite.
- Le contexte de décembre 2023 sert à janvier 2024 : la séparation d'année
  n'efface pas les informations réellement déjà observables à J.
- Le contexte peut chevaucher les bornes de split s'il est strictement passé :
  seules les **cibles des endpoints** du train pilotent les gradients. Une
  séquence de validation peut légitimement inclure des features antérieures du train.
- Les labels réels gardent leurs rangs d'origine. Ils ne sont jamais reclassés
  après exclusion des titres sans séquence.

## Normalisation et budget figés

Moyenne/écart-type par feature sur les endpoints du **train purgé uniquement**,
avec comptes de valeurs finies archivés. Aucun fit sur validation/test/2024–2026.
Feature absente : remplacement par la moyenne train (zéro standardisé), plus
indicateur explicite de manque. Feature totalement absente au train : moyenne
zéro, écart-type un ; aucun chiffre n'est inféré des périodes futures.
Valeurs standardisées bornées à ±10 (règle figée, pas winsorisation sur le test).

Le LSTM reçoit donc **346 canaux** : 173 valeurs et 173 masques. Les modèles
tabulaires reçoivent les 173 features originales et leurs NaN natifs. La
représentation change : ce n'est pas une mesure de l'architecture seule.

| Réglage | Valeur initiale figée |
| --- | --- |
| Architecture | LSTM + attention temporelle du projet, classifieur global binaire |
| Hidden size / couches | 64 / 1 |
| Dropout | 0,1 |
| Séquence | 40 séances |
| Batch | 512 endpoints |
| Optimiseur | AdamW, learning rate 0,001, weight decay 0,00001 |
| Loss | CrossEntropy, classes amplitude 0/1, sans poids de classe |
| Gradient clipping | Norme maximum 1 |
| Budget | 10 époques maximum, patience 3 |
| Choix des poids | Meilleure AUC validation ; égalité → première époque |
| Seed | 42, une seule répétition |
| Device | CUDA, RTX 5060 Ti détectée |

Pas de tuning de ces paramètres après lecture de 2024–2026. Le budget borne
ce premier challenger : un résultat négatif ne démontre pas que tous les LSTM,
architectures ou entraînements plus longs échoueraient. Seeds fixés et options
déterministes demandées ; les kernels GPU avertis non déterministes et les
différences d'environnement restent des réserves de reproductibilité.

## Comparaison équitable : copies tabulaires appariées

Des fenêtres peuvent manquer même lorsque les features de J existent. Les
trois candidats sont donc entraînés sur **les mêmes endpoints éligibles aux
séquences**, dans les mêmes train/validation, avec les mêmes labels.

LightGBM et CatBoost sont **réentraînés en copies de recherche**, avec les
hyperparamètres et seed du protocole original. Leurs modèles d'origine, résultats
et usage opérationnel restent intacts. Les copies s'appellent `matched_lightgbm.txt`
et `matched_catboost.cbm`. CatBoost garde l'objectif Logloss, LightGBM Binary.

Les trois candidats sont scorés sur la population commune observable à J,
**avant exclusion des résultats futurs manquants**. Le comparatif n'est pas
directement interchangeable avec les chiffres des anciennes populations complètes.
Les nombres de lignes exclus et la couverture de séquences doivent être lus
avant toute conclusion. Le LSTM bénéficie d'une séquence plus riche, alors que
les tabulaires ont déjà plusieurs indicateurs de trajectoire : gains éventuels
de représentation et d'architecture ne sont pas identifiés séparément ici.

## Mesures et réserves

Rapports historiques par fold/année et confirmation par année, candidats séparés.
Précision/amplitude des **10, 20 et 50 premiers titres**, sur les mêmes dates
dont toutes les sélections initiales sont qualifiées. Aucun résultat manquant
n'est remplacé par le titre suivant. Couverture/date et nombre de manquants affichés.
Les métriques conditionnelles AUC/TOP10 %/TOP20 % sont conservées séparément.

Le calcul à trois branches réutilise la routine éprouvée de confirmation ;
son troisième champ interne est adapté explicitement en `lstm` dans les
résultats. Il ne remplace pas le champion original et ne modifie aucune constante
du module de confirmation.

Précision = appartenance au TOP20 % réel **qualifiable** d'amplitude, pas taux
de trades gagnants, direction ou TP effectivement atteignable. Maxima a
posteriori sans sizing/coûts/exécution : **pas un PnL**. Univers survivant et
prix ajustés actuels ; PIT complet des familles optionnelles non certifié.
Les fenêtres H20 et séquences 40 séances se chevauchent : observations corrélées,
pas autant de tests indépendants que de lignes. Une seule seed, aucune
significativité ou supériorité économique présumée.

## Suivi et reprise

```powershell
Get-Content F:\projets\artifacts\research\oracle_path_lstm\20261013-v2\progress.json
Get-Content F:\projets\artifacts\research\oracle_path_lstm\20261013-v2\stderr.log -Tail 20 -Wait
```

| Fichier | Usage |
| --- | --- |
| `plan.json` | Budget, univers/features, environnement, hashes code/archives, pas de secrets |
| `run.json` | RUNNING/COMPLETED/FAILED, PID et erreur |
| `progress.json` | Précontrôle/cache, fold, époque, exemples traités, AUC validation et temps |
| `dataset/matrix.npy` | Matrice brute float32 sur disque, pas matérialisation de toutes les fenêtres |
| `dataset/meta.parquet` | Dates/titres, labels d'origine, identité et raisons d'exclusion de séquence |
| `folds/<date>/scaler.json` | Moyenne/std et couverture train uniquement |
| `folds/<date>/epoch_state_N.pt` | Poids courants, optimiseur et états RNG à chaque époque terminée |
| `folds/<date>/epoch_state.json` | Pointeur atomique vers la dernière époque commise et son hash |
| `folds/<date>/lstm_best_epoch_N.pt` | Meilleure époque disponible en validation, fichiers distincts pour reprise sûre |
| `folds/<date>/lstm_best.pt` | Poids retenus après early stopping/budget, aucune sélection sur le test |
| `folds/<date>/done.json` | Empreintes du fold terminé, couverture et métriques de validation |
| `historical_scores.parquet` / `confirmation_scores.parquet` | Les trois scores sur la population commune |
| `*_coverage.parquet` / `*_daily_top.parquet` | Dates comparables, maturité, résultats absents et bornes |
| `report.json` / `report.md` | Résultats historiques et 2024–2026, sans promotion automatique |

La matrice est ouverte en mémoire mappée ; une seule mini-batch de fenêtres est
matérialisée à la fois. Verrou OS empêche deux instances dans un même dossier.
JSON/poids écrits atomiquement avec retries Windows. Chaque époque a ses propres
fichiers ; une interruption avant mise à jour du pointeur reprend l'époque
précédente, pas un fichier partiellement commis. Un arrêt **au milieu** d'une
époque la rejouera depuis son début. Les folds terminés sont réutilisés après
contrôle des hashes. Aucun checkpoint provenant d'un autre plan n'est recyclé.

Relance à l'identique après arrêt (ne pas relancer pendant qu'il tourne) :

```powershell
python -u -m scripts.research.oracle_path_lstm_comparison --output artifacts/research/oracle_path_lstm/20261013-v2 --device cuda
```

Pour modifier le budget, modifier explicitement `SequenceSpec` dans une nouvelle
campagne/dossier ; le protocole et hash de code refusent une reprise incompatible.
Pas de reconnexion SQL ou téléchargement lors d'une relance.

## Statut initial

Préparation testée : **121 tests ciblés passent**, dont neuf tests du challenger
(frontières symbole/séance/identité, scaler causal, masques, CPU/GPU réel,
checkpoint/reprise, cache décembre→janvier et comparaison TOP-K sans remplacement).
Lancement vérifié le **13 octobre 2026 à 21:28 Paris**, processus Python de
calcul **17772** (launcher venv 21840). Le cache est construit et les dix folds
sont reconstruits à l'identique. Premier fold : 656 831 endpoints train communs
sur 722 039 originaux, validation 162 891 sur 163 842, test 198 728 séquences.
Cette baisse de population est explicitement prise en compte par les copies
tabulaires appariées. Vérifier les fichiers de suivi pour l'état
réel ; aucun avantage LSTM n'est encore démontré. Aucun test économique ni
intégration live ne sera lancé automatiquement à la fin.

### Remédiation technique v1 → v2

Le premier essai a commis l'époque 1 du fold 2018-07-05, puis le callback
d'affichage a échoué : `dict() got multiple values for keyword argument 'epoch'`.
La sauvegarde précédait le callback, donc poids/optimiseur/RNG restent valides.
Correction : fusion explicite des champs de progression, test de régression ajouté.
**Aucun changement de gradients, scaler, dates, cibles, population ou budget.**

Nouvelle campagne de fichiers v2 pour respecter le gel des empreintes du code,
avec copie contrôlée du cache et de l'époque commise ; la copie ne modifie pas
v1. Hashes du cache, de l'état époque et des poids retenus contrôlés, puis
revérifiés à la reprise. Les copies tabulaires sont réajustées sur les mêmes lignes.
`resume_provenance.json` explique cette continuité. v1 demeure FAILED technique ;
seul v2 fait foi pour le statut courant. Pas de sélection sur un résultat test.

Reprise lancée à **21:34 Paris**, processus de calcul **6284**, launcher venv 40228.
Progression vérifiée après remédiation : premier fold, époque 3, état RUNNING.
Validation finale après correctif : **122 tests ciblés passent**.
L'époque 1 avait pris
45,7 secondes sur le premier train commun ; cela ne fournit pas une ETA fiable
pour les neuf autres folds, plus grands, et leurs autres étapes.

## Résultat final vérifié — 13 octobre 2026 à 22:54 Paris

**v2 COMPLETED**, dix folds terminés et confirmation 2024–2026 effectuée.
Le v1 reste FAILED technique et n'est pas le rapport de référence.
Contrôles : hashes de tous les artefacts de fold valides, sources inchangées,
disponibilités train/validation causales, scores finis dans [0,1], aucun doublon
date/titre. Historique : 2 136 465 lignes, 1 260 séances du 2018-07-05 au 2023-07-07.
Confirmation : 1 237 285 scores, 696 séances du 2024-01-02 au 2026-10-09 ; les
scores récents ne deviennent pas des labels matures pour autant.

### Confirmation : précision sur les 10 premiers titres

| Année | Dates communes complètes / matures | LightGBM apparié | CatBoost apparié | LSTM |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 252 / 252 | 70,67 % | 71,23 % | 71,19 % |
| 2025 | 250 / 250 | 78,32 % | 78,08 % | 79,96 % |
| 2026 partiel | 153 / 173 | 76,54 % | 76,54 % | 72,16 % |

Ce sont les copies appariées : ne pas confondre avec les chiffres des modèles
originaux sur la population précédente. Précision = appartenance au TOP20 %
réel qualifiable d'amplitude, pas hausse ou taux de trades gagnants.

### Confirmation : amplitude absolue moyenne des 10 premiers titres

| Année | LightGBM apparié | CatBoost apparié | LSTM |
| --- | ---: | ---: | ---: |
| 2024 | 20,58 % | 20,69 % | 21,00 % |
| 2025 | 27,38 % | 27,39 % | 28,16 % |
| 2026 partiel | 29,27 % | 29,34 % | 27,11 % |

### Concentration plus large et stabilité

En 2025, le bénéfice LSTM est limité au TOP10 : sa précision TOP20 est **74,98 %**
contre 76,22 % / 75,52 %, et TOP50 **68,38 %** contre 70,53 % / 69,59 %.
En 2026, il est derrière les deux tabulaires sur TOP10, TOP20 et TOP50 :
précisions LSTM **72,16 % / 70,07 % / 68,05 %** ; les dates communes sont
153 / 141 / 125 sur 173 matures selon la taille. L'amplitude est aussi plus faible.
La couverture des lignes observables ayant une séquence est 99,980 % en 2024,
99,982 % en 2025 et **98,463 %** en 2026 ; ce n'est pas la couverture des
résultats futurs de toutes les sélections, qui est moins élevée.

Sur l'historique, les résultats varient : LSTM utile sur certaines mesures
de 2019/2020/2022, derrière en 2018/2021 et en précision en 2023. Aucun avantage
constant sur toutes les tailles/périodes. Dans les dix folds, l'AUC de validation
du LSTM est inférieure au meilleur tabulaire apparié.

**Chaque fold a retenu l'époque 1**, puis s'est arrêté après l'époque 4,
conformément à la patience 3. La loss train baisse tandis que l'AUC validation
ne retrouve pas sa valeur initiale. C'est compatible avec du surapprentissage
ou une inadéquation de ce protocole d'optimisation, **pas une preuve de bug**.
Augmenter simplement le plafond d'époques n'aurait pas modifié le choix de ce run.
Aucun réglage n'a été changé après lecture de ces résultats.

### Conclusion et suite bornée

**Pas d'avantage stable démontré pour ce LSTM ; pas de promotion par défaut.**
Le petit avantage TOP10 de 2025 ne compense pas une preuve de stabilité absente
et le recul de 2026. Conserver LightGBM/CatBoost comme références ; les fichiers
du challenger restent archivés pour recherche. Cela ne condamne pas tous les
LSTM : une seule seed, une architecture et un budget ont été testés.

Le run ne démontre ni direction LONG/SHORT ni performance économique. Aucun
nouveau training, tuning, replay économique ou changement de production lancé
après la lecture. Toute nouvelle hypothèse nécessite un protocole distinct et
un nouveau GO, sans modifier les résultats ou paramètres de cette expérience.
