# Sprint 16-A — Contrat de préparation de la prédiction France

## État au 6 octobre 2026

**16-A livré : préparation et contrôles hors ligne. Pas de GO serving, shadow ou trading.**

Ce sous-sprint ne transforme pas un résultat de recherche en modèle de production.
Il fige le candidat, ses dépendances et le format attendu des données quotidiennes.
La commande exécutée sans dataset produit légitimement `BLOCKED`, avec
`QUALIFIED_DAILY_DATASET_MISSING`. Ce n'est pas un entraînement en échec.

Le bilan [15-G](sprint_15g_bilan_cloture_operationnelle.md) reste applicable :
collecte quotidienne encore incomplètement qualifiée, réserves opérationnelles,
publication SQL quotidienne qualifiée non livrée. Aucun batch existant n'est
modifié par 16-A ; aucun accès SQL, téléchargement, désérialisation de modèle,
entraînement ou ordre n'est exécuté.

## 1. Architecture et séparation des marchés

```text
Rapport Oracle H5 réparé + protocole + modèle fold 7 + identités FR
                         │ vérification et empreintes SHA-256
                         ▼
                  manifest.json DRAFT
                         │
Proposition de features quotidiennes ──► contrôles preflight
                                         │
                        ┌────────────────┴──────────────────┐
                        ▼                                   ▼
                     BLOCKED                    PREPARED_NOT_AUTHORIZED
                  anomalies listées            conforme techniquement seulement
                        └────────────────┬──────────────────┘
                                         ▼
                           serving=false / orders=false
```

Le contrat impose `FR_EQ`, `fr_primary`, `alpha_trade_fr`, EUR et XPAR.
Une incohérence ne provoque **aucun fallback US/CN**. La base est une route future
déclarée, pas une connexion effectivement ouverte par ce service.

Implémentation : `service/fr/prediction_contract_16a.py`.
Tests : `tests/test_fr_prediction_contract_16a.py`.

## 2. Modèle candidat, pas modèle promu

La source est la campagne `oracle_h5_repaired` du catalogue
`service/fr/research_catalog_14a.py`, sous :

`artifacts/fr/research/fold7_repair/rebuild-20261003-v1/confirmation/oracle/fr-oracle-h5-6e72b9d2e600/`.

Le candidat est le champion du **fold 7**, sélectionné par average precision de
validation. À cette date il s'agit de `trees`, stocké dans `fold7_trees.joblib`.
Les dates d'entraînement, validation et test sont reprises intégralement du
rapport ; aucun refit plus récent n'est effectué. En particulier, ce fichier
ne signifie pas « entraîné sur toutes les données jusqu'en octobre 2026 ».

Le manifeste décrit un Oracle d'**amplitude H5** : cinq séances, pas cinq jours
calendaires. Il ne donne ni D1/D10, ni conseil LONG/SHORT. Le score binaire brut
avec `calibration: none` n'est pas présenté comme une probabilité directionnelle
ou comme une probabilité calibrée. Le TOP20 est la fraction prévue du classement
transversal, non un seuil de score égal à 0,20. Le classement n'est pas exécuté
dans ce sous-sprint.

Les protections sont explicites :

- `status: DRAFT_RESEARCH_NOT_RELEASED` ;
- `serving_enabled`, `live_enabled`, `canonical_writes_enabled` à `false` ;
- `model_role: ORACLE_AMPLITUDE_ONLY` ;
- aucun modèle directionnel automatiquement chargé ;
- aucun ordre, aucune écriture canonique et aucune promotion automatique.

## 3. Features et transformations

La liste **ordonnée** est celle réellement utilisée par le pilote :

| Position | Feature | Lecture fonctionnelle |
| --- | --- | --- |
| 1–5 | `return_1`, `return_3`, `return_5`, `return_10`, `return_20` | Rendements sur plusieurs horizons passés |
| 6 | `sma20_distance` | Position relative à la moyenne mobile 20 |
| 7 | `atr20_pct` | Amplitude habituelle rapportée au prix |
| 8 | `realized_vol20` | Volatilité réalisée |
| 9 | `range20_position` | Position dans la plage passée |
| 10 | `volume_ratio20` | Volume relatif |
| 11 | `traded_value_mean20_eur` | Valeur moyenne échangée en EUR |
| 12 | `overnight_gap` | Variation entre clôture précédente et ouverture |
| 13 | `intraday_return` | Rendement de la séance |
| 14 | `intraday_range` | Amplitude intrajournalière |

La référence des formules demeure `modelFactory/fr_feature_panel.py` et le
profil figé `modelFactory/fr_feature_profile_freeze.py`.
16-A ne réimplémente pas ces formules. Le contrat enregistre la transformation
`log1p(traded_value_mean20_eur)` de `fr_oracle_h5_pilot.feature_matrix`.
Les valeurs proposées doivent rester **brutes avant transformation modèle** ;
le futur adaptateur ne devra pas appliquer deux fois le logarithme.
Les features doivent toutes être présentes, finies, numériques, et la valeur
échangée non négative. Pas d'imputation silencieuse ni de colonne-cible admise
dans `values`.

## 4. Univers de recherche et éligibilité quotidienne

Les 330 identités vérifiées de
`artifacts/fr/sprint6c_reference/identities.jsonl.gz` sont archivées dans le
manifeste avec `research_uid`, ISIN, symbole fournisseur et MICs.
**330 identités de recherche ne veut pas dire 330 titres négociables aujourd'hui.**
Le rôle est `RESEARCH_IDENTITIES_NOT_DAILY_TRADABLE` : les statuts courants ne
sont pas appliqués rétroactivement à l'historique. Chaque ligne quotidienne
devra porter l'identité correcte et une qualification à sa séance.

Le preflight vérifie l'identité contre le manifeste, le MIC et les assertions
`identity_qualified_at_session` / `tradable_at_session`. Ces assertions ne sont
pas une preuve suffisante pour promouvoir des données : leur production à
partir des preuves ESMA/prix/opérations sur titres appartient à **16-B**.
Un simple `true` ajouté à la main ne déverrouille jamais le serving en 16-A.

## 5. Format de proposition quotidienne

Le dataset optionnel est un fichier JSON, contenant :

| Champ | Contrat |
| --- | --- |
| `schema_version` / `market_code` | `1` / `FR_EQ` |
| `features` | Les 14 noms dans l'ordre du manifeste |
| `feature_stage` | `RAW_BEFORE_MODEL_TRANSFORMS` |
| `decision_at` | Heure de décision avec fuseau explicite |
| `expected_feature_session` | Dernière séance requise par le calendrier qualifié |
| `rows` | Une seule ligne par identité |

Chaque ligne contient : identité (`research_uid`, `isin`, `provider_symbol`,
`mic`), éligibilité quotidienne, `feature_session`, `available_at`,
`observed_at`, `source`, `source_payload_sha256`, `qualification`, `values`.
La source initiale attendue est `eodhd`, avec empreinte SHA-256 hexadécimale
de 64 caractères et qualification `QUALIFIED`.

Les horodatages doivent être explicites ; `observed_at <= available_at <=
decision_at`. On ne fait pas passer une barre téléchargée aujourd'hui pour
une observation réellement disponible lors d'une décision historique.
Une date manquante ou ancienne est rejetée ; le service ne remplace pas la
dernière séance attendue par la dernière barre disponible.

**Limite importante :** le calendrier, les payloads et la qualification des
features ne sont pas reconstruits par 16-A. Leurs champs sont contrôlés comme
un contrat d'interface. 16-B devra vérifier leurs pièces, la clôture XPAR, les
fenêtres d'historique et les corrections. La conformité de cet envelope seule
ne prouve ni PIT complet ni autorisation d'utilisation.

Au moins 20 lignes conformes sont nécessaires. Toute ligne rejetée bloque
le dossier entier à ce stade ; le preflight n'ajuste pas silencieusement le
TOP20 à un sous-univers arbitrairement réduit.

## 6. Intégrité et sorties

Quatre preuves sont hachées : rapport, protocole, fichier modèle candidat et
identités. Elles doivent rester sous `artifacts/fr` après résolution du chemin.
Le preflight reconstruit le manifeste depuis ces preuves pour détecter aussi
une modification de l'univers ou d'un paramètre JSON. Il ne charge pas le
contenu exécutable du fichier joblib.

La sortie contient les motifs globaux, le nombre de lignes admissibles et les
motifs par ligne : identité, MIC, éligibilité, séance, PIT, source ou features.
`technical_checks_passed` distingue un dossier conforme d'un dossier bloqué.
`serving_allowed` et `orders_allowed` restent **toujours false**.

Il n'y a pas de migration Alembic ni de nouvelle table pour cette préparation.
L'interface IHM existante et les tâches planifiées ne sont pas modifiées.

## 7. Utilisation

Depuis la racine du projet :

```powershell
python -m service.fr.prediction_contract_16a --output-dir artifacts/fr/research/prediction_preparation_16a/preparation-20261006-v1
```

Cette exécution a été réalisée. Elle a produit `manifest.json` et
`preflight.json`, avec blocage attendu faute de dataset quotidien qualifié.
Pour une nouvelle exécution utiliser **un nouveau nom de dossier** : aucun
dossier existant n'est écrasé. Un résultat `BLOCKED` est un diagnostic enregistré,
pas une exception CLI ; consulter le champ `status` du rapport.

Un futur dataset peut être contrôlé en ajoutant `--dataset <chemin.json>`.
Cela ne lance toujours aucune prédiction. Ne pas construire manuellement des
assertions de qualification pour contourner les étapes suivantes.

## 8. Suite : 16-B puis shadow

16-B devra assembler les archives quotidiennes qualifiées, calculer le profil
figé sans données futures et vérifier les preuves des identités et actions sur
titres. Il faudra ensuite une décision explicite sur le modèle à libérer et
sur sa date réelle de disponibilité, puis le protocole prospectif verrouillé.
La publication idempotente par séance dans `alpha_trade_fr`, le classement
Oracle, la reprise et le reporting du shadow restent à implémenter/tester.

Les réserves du Sprint 15 ne sont pas levées par ce contrat. Le Sprint 16
complet n'est donc **pas terminé**, et aucun résultat économique ou gain
directionnel supplémentaire n'est démontré ici.
