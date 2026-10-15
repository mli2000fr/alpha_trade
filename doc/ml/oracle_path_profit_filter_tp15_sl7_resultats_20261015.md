# Filtre de rentabilité TP15/SL7 — exécution du point 2

**Terminé et audité le 15 octobre 2026 : `NO_GO_CONDITIONAL_NET_PROFIT_FILTER`.**
Un seul filtre entraîné, aucune entrée acceptée au seuil figé. Pas de calcul
2024–2026 ni de replay économique déclenché après cet échec de validation.

Continuation autorisée le 15 octobre 2026 après la
[préparation TP15/SL7](oracle_path_profit_filter_tp15_sl7_20261015.md).
L'Oracle amont n'est pas réentraîné. Le travail porte sur les cibles et un seul
petit filtre LONG conditionnel, pas sur une nouvelle recherche de TP/SL.

## Contrat et implémentation

Paramètres, 24 features, périodes, seuil 0,50 et gates du protocole sont
inchangés. Entrée open J+1, TP15/SL7 dès l'entrée, sans trailing, expiration
open J+21 ; disponibilité conservatrice J+22. Données manquantes/non qualifiées
conservées comme inconnues avec motif, jamais comme pertes ni remplacements.

La population est celle des 25 200 candidats historiques déjà figés avant les
labels futurs. Les features sont recalculées avec le builder backward-only
existant, sur les prix et le benchmark archivés. Contrôles sur préfixes arrêtés
au premier, milieu et dernier candidat de chaque titre, sans consulter l'issue.

Deux niveaux de référence sont distingués :

1. Le labeler résout le chemin avec le résolveur intrabar commun, puis ouvre et
   clôture **chaque unité dans un nouvel état du moteur comptable natif**. Il ne
   retranche pas un coût forfaitaire au rendement brut. Les deux cash-flows et
   les frais portent sur les notionnels exécutés. Aucun tracker de pertes ou de
   concentration d'un autre exemple n'est réutilisé.
2. Les tests et 24 sondes historiques confrontent cette unité à un ledger
   chronologique complet : exécution/protections/watcher/lifecycle natifs,
   mêmes entrées, sorties et cash-flows. Ces sondes ne constituent pas un
   portefeuille d'investissement.

Le ticket unitaire est de 1 600 USD au close J, quantité fractionnaire normalisée
à neuf décimales. Le moteur natif conserve ici le fill open, sans arrondi au cent
ajouté par le labeler. Le financement de référence reste 50 % du notionnel rempli,
6,5 % ACT/360 selon les nuits calendaires. Il est déduit **une seule fois** du
PnL transactionnel natif, sans prétendre être le financement réel du portefeuille.

Les barrières se basent sur les OHLC archivés sur base split, sans ajustement
dividende additionnel. Les features utilisent le générateur existant basé sur
`adj_close/close` : ce choix et les vintages fournisseurs actuels restent réservés.
Identités/source/ajustement/volumes/barres remplies et ruptures connues sont
contrôlés sur la fenêtre complète ; pas de réparation silencieuse d'un perdant.

### Codes et dossiers

- Dataset : `scripts/research/us_oracle_path_profit_tp15_sl7_dataset.py` ;
  première version `artifacts/research/us_oracle_path_profit_filter/20261015-tp15-sl7-dataset-v1` conservée.
- Version corrigée : `scripts/research/us_oracle_path_profit_tp15_sl7_native_gap.py` ;
  `artifacts/research/us_oracle_path_profit_filter/20261015-tp15-sl7-dataset-v2`.
- Audit séparé : `scripts/research/us_oracle_path_profit_tp15_sl7_audit.py`.
- Fit unique : `scripts/research/us_oracle_path_profit_tp15_sl7_fit.py` ;
  `artifacts/research/us_oracle_path_profit_filter/20261015-tp15-sl7-fit-v1`.

Reprise vérifiée par titre, puis par fit terminé, avec empreintes et verrous.
Le modèle de recherche éventuel reste sous `artifacts/research`, pas dans le
catalogue des champions et sans prédiction SQL.

## Vérification et suivi

55 tests ciblés passent : populations sans futur, purge, amendement sans retouche,
parité native TP/SL/collisions/gaps/expiration, calcul des cash-flows et du
financement, audit indépendant, poids égaux par date, seuil figé et bootstrap.
Premier test de gap : fixture corrigée pour garder un OHLC cohérent ; le contrôle
qualité n'a pas été assoupli. Pas de modification de la configuration native.

Le premier lancement détaché dans le bac à sable n'a pas démarré Python : logs
vides conservés. Reprise autorisée et masquée avec logs `*-retry1.log`, PID lanceur
29424. Cela ne correspond pas à un chemin économique abandonné.

```powershell
Get-Content F:\projets\artifacts\research\us_oracle_path_profit_filter\20261015-tp15-sl7-dataset-v2\progress.json
Get-Content F:\projets\artifacts\research\us_oracle_path_profit_filter\20261015-tp15-sl7-fit-v1\report.json
```

## Résultats

### Qualification v1 et anomalie technique bornée

V1 terminée : 25 200 candidats, 24 852 admissibles à J et 20 870 labels connus.
Audit séparé des comptes, dates, rangs et frais réussi ; 24 sondes complètes,
293 titres avec contrôles sur préfixes. 499 expirations positives, 16 doubles
contacts conservateurs, 1 227 gaps de stop défavorables : les expirations sans
TP ne sont pas toutes des pertes, et les gaps ne sont pas plafonnés au SL7.

Le gate de couverture a correctement empêché le fit : validation 2022,
4 015 / 5 020 = **79,98008 %**, contre 80 % requis. Les 1 005 inconnus étaient
975 refus de gap d'entrée et 30 dates MLTX avec historique/identité/features J
non qualifiés. Les autres contrôles de taille, dates, classes et features passaient.
Aucun entraînement ni ajustement du seuil de couverture sur cette v1.

L'examen de **toutes** les ouvertures 2022 a trouvé une divergence technique :
CUK signal du 3 octobre 2022, close 6,00 USD, open du 4 octobre 6,18 USD.
La forme `abs(open/close-1)>0.03` rejetait ce +3 % exact par arrondi flottant,
alors que la fonction native `should_skip_entry_for_gap`, partagée par les phases
d'exécution, l'accepte. Le seul cas à moins de 1e−12 du seuil en 2022 était celui-ci.

Correction : **appeler la fonction native**, sans epsilon ni nouveau seuil, sur
tous les candidats historiques. Le module de recherche v1 reste intact ; un
adaptateur de recherche versionné injecte seulement cette qualification dans
la v2 et lie son code/test au manifeste. Pas de modification du moteur partagé,
des gates, des protections, du TOP, des features ou des périodes. Sept tests
additionnels couvrent les bords positifs/négatifs, un vrai dépassement, un chemin
invalide et l'exécution native complète du cas 6 → 6,18.

Le fait qu'une correction puisse suffire à franchir 80 % ne constitue **aucun
gain prédictif**. V1, verdict initial, fichiers et code restent conservés ; la
v2 doit être réauditée avant tout fit. Aucun refus réel pour gap >3 % n'est
artificiellement transformé en ordre admissible.

### Qualification v2 et fit unique

V2 terminée : **20 875 labels connus**, sur les mêmes 25 200 candidats et
24 852 admissibles à J. La correction native touche exactement cinq cas :
CUK 03/10/2022, NMM 03/01/2019, PARR 26/05/2020, REPX 29/10/2018 et 13/11/2018.
Trois nouveaux labels sont positifs, deux négatifs ; aucun choix sur ce signe.
**25 195 autres lignes sont strictement identiques**, toutes colonnes comparées.
La validation passe de 4 015 à 4 016 labels connus sur 5 020, soit **80 % exacts**.
Les gates n'ont pas été abaissés et cela ne renforce pas leur portée statistique.

| Partition | Candidats initiaux | Labels après purge | Séances après purge | Classes négative / positive |
| --- | ---: | ---: | ---: | ---: |
| Fit 2018–2021 | 17 620 | 14 201 | 847 | 9 206 / 4 995 |
| Validation 2022 | 5 020 | 3 642 | 227 | 2 575 / 1 067 |
| Contrôle 2023 partiel | 2 560 | 2 278 | 128 | 1 250 / 1 028 |

Les 380 labels de bord fit et 374 de bord validation sont purgés selon J+22.
Couvertures connues **avant purge** : 82,75 %, 80,00 %, 88,98 %. Features finies
à 100 % sur les populations examinées ; leur qualité physique J écarte encore
certaines lignes. Aucun exemple 2024–2026 ne sert au fit ou à l'early stopping.
Audit indépendant v2 : clés/rangs/dates, deux cash-flows, financement, labels,
prix TP/SL, préfixes et 24 sondes complets, statut `AUDITED_NATIVE_TP15_SL7_DATASET`.

Un seul LightGBM conforme au protocole a été entraîné : profondeur 3, sept
feuilles, maximum 150 itérations, early stopping 15 sur le logloss pondéré 2022,
poids égaux par date, pas de refit ni calibration. **Meilleure itération : 1.**
La probabilité constante témoin, apprise sur le fit, vaut **0,3528712**.

| Mesure | Validation 2022 | Contrôle 2023 partiel | Gate prévu |
| --- | ---: | ---: | --- |
| AUC quotidienne moyenne | **0,4656** | **0,4772** | ≥0,53 |
| Dates évaluables AUC, au moins deux exemples de chaque classe | 134 | 120 | ≥50 |
| AUC poolée, descriptive | 0,4478 | 0,4948 | Ne remplace pas l'AUC quotidienne |
| Brier du filtre, plus bas = mieux | 0,210225 | 0,257302 | Meilleur que le témoin |
| Brier constant témoin | **0,210094** | 0,257355 | — |
| Probabilités minimale–maximale | 0,35190–0,35981 | 0,34635–0,35369 | Seuil fixé 0,50 |
| Candidats acceptés | **0 / 3 642** | **0 / 2 278** | 20–80 % |

Le filtre n'améliore pas le Brier en validation ; la très petite amélioration du
Brier en contrôle ne sauve ni l'AUC ni l'absence d'activité. Avec zéro accepté,
le lift et son intervalle sont **inconnus**, pas zéro ni « pertes évitées ».
Les deux partitions échouent aux gates. Pas d'inversion des scores sous 0,50,
de seuil abaissé, de nouvel horizon, de nouvelles features ou d'autre backend.

À titre descriptif seulement, le rendement unitaire moyen du pool connu, dates
à poids égal, est −1,05 % en validation et +2,21 % en contrôle. **Ce ne sont pas
des rendements de portefeuille**, et ils ne deviennent pas la performance du
filtre qui n'accepte rien.

### Audit du modèle et décision

Audit final séparé : **268 entrées et quatre fichiers de fit** vérifiés par
empreintes ; scores reproduits depuis les poids, AUC quotidienne et Brier
recalculés indépendamment, dates/purge contrôlées. Un arbre retenu, 24 features
présentes et **toutes variables dans le fit**. L'arbre utilise volatilité60,
ATR20, tendance marché50 et force relative60. Les probabilités étroites ne
proviennent donc pas de colonnes toutes nulles/constantes : l'early stopping
figé ne trouvait pas de meilleur logloss en poursuivant l'apprentissage.

Verdict : **cette formulation de filtre n'est pas retenue**. La cible de chemin
et la comptabilité sont maintenant qualifiées pour ce contrat exploratoire,
mais cela n'a pas créé de séparation prédictive utile. Cela ne prouve pas
l'impossibilité de toute nouvelle information directionnelle ; ce test ne
contient pas de nouvelle source consensus/news PIT.

L'Oracle d'amplitude reste inchangé. Le modèle auxiliaire demeure archivé sous
`artifacts/research`, non servi. `completion-audit.json` du fit :
`AUDITED_SINGLE_FIT_NO_GO_STOP_CONFIRMED`.
**Un fit total, zéro inférence 2024–2026, zéro portefeuille simulé, zéro SQL/API/
GPT/courtier et aucune promotion de production.** Aucun run ne reste en cours.

La règle d'arrêt demeure impérative : si couverture/chronologie/parité échouent,
pas de fit ; si validation ou contrôle échouent, pas d'inférence récente ni de
backtest 2024–2026, pas de nouveau seuil choisi après les pertes. Si les gates
passent, un replay ultérieur exigera deux nouvelles variantes TP15/SL7 appariées,
jamais les anciens résultats TP10/SL10 réétiquetés.

Pas d'accès SQL, API, GPT ou courtier dans ces scripts. Secteurs/macro historiques,
univers survivant et lineage Oracle gardent leurs réserves ; 2024–2026 déjà
explorés ne deviennent pas des holdouts vierges.
