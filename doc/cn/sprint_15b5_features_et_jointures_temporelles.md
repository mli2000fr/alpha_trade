# Sprint 15-B5 — Fenêtres de marge et jointures temporelles Oracle

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

29 septembre 2026. Suite du [dataset B4](./sprint_15b4_dataset_szse_et_preregistration.md).

## Périmètre et statut

Service de recherche : [cn_margin_features_15b5.py](../../modelFactory/cn_margin_features_15b5.py). Aucun téléchargement, aucune écriture en base, aucun entraînement, aucune activation live. Les archives B4 sont inchangées ; tous les produits restent sous proxy, avec `strict_ml_allowed=false` et `historical_vintage_proven=false`.

Le programme prépare des données pour évaluer ultérieurement la marge/prêt comme apport directionnel, pas une preuve de performance. Il n'ajoute pas de variables choisies après observation des rendements.

## Construction des quatre variables pré-enregistrées

Soit une séance source S, sur le calendrier ouvert CN figé.

| Variable | Formule | Historique requis |
|---|---|---|
| `financing_buy_to_amount` | achats financés S / montant d'échanges S, CNY | Une observation exploitable |
| `financing_buy_to_amount_mean5` | moyenne arithmétique des cinq ratios S−4 à S | Cinq séances consécutives valides |
| `financing_balance_change5` | encours S / encours S−5 − 1 | Six observations consécutives, encours initial positif |
| `financing_balance_change20` | encours S / encours S−20 − 1 | Vingt et une observations consécutives, encours initial positif |

Les fenêtres suivent les séances de marché, **pas les cinq/vingt dernières observations disponibles**. Un retrait d'éligibilité, une suspension/non-négociation, un montant manquant, une observation absente ou une anomalie interrompt les fenêtres qui la traversent. Une variable redevient calculable après sortie de l'anomalie de sa propre fenêtre ; les autres variables restent éventuellement nulles.

Pas d'imputation à zéro, de division par encours nul, de plafonnement ou de pont sur un trou. Les zéros explicitement observés restent admissibles lorsque les autres contrôles passent.

Le ratio supérieur à 1 de `300957` au 2024-08-26 est isolé avec `FINANCING_BUY_EXCEEDS_AMOUNT`. Sa mesure brute reste conservée en B4 ; cette exclusion est propagée aux fenêtres concernées. La cause du rapprochement achats/montant reste à établir.

## Règle de disponibilité et absence de données périmées

Trois calendriers sont produits, pour les retards pré-enregistrés de 2, 3 et 5 séances :

1. une mesure S devient disponible à la clôture de S+retard ;
2. la décision `decision_at` provient du panel prix CN déjà audité ;
3. on recherche la dernière séance source dont la clôture-proxy est **strictement antérieure** à la décision ;
4. on joint exactement cette séance et cet instrument.

Une mesure dont le proxy égale la décision n'est pas admise. Si le titre n'a pas de ligne pour la dernière séance source attendue, on laisse les features nulles : **aucun retour automatique vers une ancienne ligne valide**.

L'éligibilité de marge est celle de la dernière liste source disponible sous proxy, pas une liste future à la date de décision. L'univers d'actions négociables reste celui du panel Oracle CN existant ; B5 ne remplace pas les règles d'exécution/suspension/limites.

Un retard conservateur ne prouve pas que l'archive n'a jamais été corrigée : tous les résultats futurs devront rester qualifiés de recherche historique sous proxy.

## Population Oracle et labels

Le modèle d'amplitude est fixé à **LightGBM Oracle CN Sprint 10-B H20**, sans sélection selon un résultat directionnel B5. Les huit semestres OOF 2022H1–2025H2 doivent exister, avec empreintes des prédictions, protocole, code et audit des labels concordantes. Les bornes de disponibilité des labels d'apprentissage/validation sont contrôlées.

Le TOP20 est calculé quotidiennement sur **toutes les prédictions CN du fold**, avec ordre score décroissant puis identifiant croissant en cas d'égalité, et arrondi supérieur du nombre de candidats. La qualité future des labels et la disponibilité de marge **ne participent pas** à cette sélection.

Seulement ensuite :

```text
Oracle OOF H20, univers CN complet
  → TOP20 quotidien indépendant des futurs labels
  → actions XSHE du référentiel historique B4
  → panel prix et métadonnées des labels H20
  → dernière séance de marge disponible sous proxy
  → masque commun prix + quatre variables marge + label valide
```

Les déciles ne sont pas recalculés sur Shenzhen ou sur les candidats restants. D10/rest conserve les déciles CN existants ; D1/D10 exclut les déciles intermédiaires uniquement pour cette tâche.

Les labels `oracle_decile`, rendements futurs, qualité future et `available_at_utc` sont des **métadonnées d'évaluation**, jamais des entrées du modèle. La liste d'entrées autorisées par variante est inscrite dans `model_feature_columns` du rapport.

La baseline prix reprend les 33 variables pré-enregistrées du profil Oracle CN, plus le contrôle `log_amount_mean20_cny`, construit uniquement avec le montant moyen historique positif. Aucune capitalisation actuelle ni secteur non daté n'est ajouté. Les trois extensions ajoutent exactement les variables de flux, encours ou les quatre combinées du protocole B4. Baseline et extensions doivent utiliser les **mêmes lignes du masque commun**, même lorsque la baseline pourrait exploiter davantage de données.

## Blocage du calendrier d'évaluation initial

Les événements Oracle OOF existants commencent en 2022. Le protocole B4 demande 504 séances d'apprentissage et 126 de validation, avant purge/embargo des labels.

Les premiers folds de développement ne peuvent donc pas satisfaire cette exigence. Le rapport compte les séances OOF antérieures avec données communes valides par retard et indique `history_gate_passed_before_label_purge`. Un résultat vrai est **nécessaire mais non suffisant** : la purge effective des labels et l'embargo restent à appliquer avant entraînement.

Le statut final de préparation conserve `training_ready=false`. Il est interdit de :

- réduire silencieusement les 504/126 séances ;
- utiliser des scores Oracle in-sample avant 2022 ;
- appliquer le modèle final 2025 aux années antérieures comme prétendu OOF ;
- déclarer les huit semestres évaluables sans audit des fenêtres.

Avant les expériences, choisir et pré-enregistrer une solution : étendre l'Oracle OOF à des semestres antérieurs avec historique suffisant, ou créer une nouvelle campagne au calendrier d'évaluation réalisable. Ce choix n'est pas fait automatiquement par B5.

## Artefacts, exécution et reproduction

Le dossier de sortie doit être neuf : le programme refuse les écrasements et ne reprend pas une préparation partielle. Un premier run incomplet est conservé dans `sprint15b5_features` ; son défaut de collision `cn_breadth_1` est corrigé, avec test de non-régression vérifiant la concordance des colonnes communes.

Les deux premiers essais incomplets sont conservés dans `sprint15b5_features` et `sprint15b5_features_v2` et marqués FAILED. Le second a révélé des déciles nuls : leur conversion est désormais nullable, avec test prouvant qu'un label inconnu ou invalide ne devient pas une classe négative.

Le run final validé utilise :

```powershell
python -u -m modelFactory.cn_margin_features_15b5 --output artifacts/research/cn_margin_lending/sprint15b5_features_v3
```

| Produit | Contenu |
|---|---|
| `margin-YYYY.parquet` | Variables et qualité par séance source/instrument |
| `calendar-lagN.parquet` | Clôtures-proxies calculées sur le calendrier figé |
| `YYYYHN-lagN.parquet` | Candidats Oracle, prix, métadonnées labels, données de marge et masques |
| `report.json` | Statut, empreintes, compteurs, colonnes autorisées et blocages d'historique |

Le rapport est mis à jour à chaque jointure semestre/retard. Les journaux annoncent la progression des 1 942 séances puis les compteurs de jointure. Un échec est explicite ; aucun dossier échoué ne constitue un résultat valide.

Le programme vérifie les empreintes B4 figées, toutes les partitions lues, les panels prix, les fichiers de labels H20 et les prédictions OOF. Les produits parquet sont eux-mêmes empreintés. Les tests couvrent les fenêtres exactes, interruptions, anomalie, encours initial nul, égalité temporelle interdite, absence de fallback périmé, TOP20 sans filtre futur et collision des colonnes.

## Bilan d'exécution

**Préparation et audit terminés.** Rapport : [report.json](../../artifacts/research/cn_margin_lending/sprint15b5_features_v3/report.json). Audit indépendant : [join_audit.json](../../artifacts/research/cn_margin_lending/sprint15b5_features_v3/join_audit.json).

- huit partitions annuelles : 2 229 675 lignes sources, dont 2 170 197 avec les quatre variables de marge calculables ;
- 24 jointures produites : huit semestres × trois retards ;
- contrôles indépendants réussis : empreintes, calendriers recalculés sur le référentiel B4, clés uniques, strict antériorité, absence de labels dans les entrées, compteurs et statut de recherche ;
- **47 tests ciblés réussissent** ; contrôle de style réussi ;
- aucune AUC, précision D1/D10, rentabilité ou recommandation de production mesurée.

### Couverture du retard principal de deux séances

| Semestre | TOP20 Oracle XSHE | Quatre variables marge valides | Lignes communes prix/marge/label | Dont D1 ou D10 | Séances OOF antérieures | Gate 630 avant purge |
|---|---:|---:|---:|---:|---:|---|
| 2022H1 | 61 314 | 22 865 | 5 251 | 1 683 | 0 | Bloqué |
| 2022H2 | 66 659 | 25 850 | 5 669 | 2 183 | 117 | Bloqué |
| 2023H1 | 62 414 | 36 033 | 9 008 | 3 607 | 242 | Bloqué |
| 2023H2 | 67 917 | 40 016 | 10 793 | 4 211 | 360 | Bloqué |
| 2024H1 | 63 979 | 35 372 | 8 746 | 2 832 | 484 | Bloqué |
| 2024H2 | 77 002 | 43 787 | 15 142 | 6 026 | 601 | Bloqué |
| 2025H1 | 68 036 | 38 855 | 10 392 | 4 162 | 726 | Passé, purge restant à faire |
| 2025H2 | 67 718 | 43 433 | 9 778 | 4 311 | 843 | Passé, purge restant à faire |

Les retards 3/5 ont des chiffres proches, détaillés dans le rapport. Aucun retard n'est choisi selon des performances.

### Pourquoi la population finale est beaucoup plus petite

La couverture de 99,9996 % en B4 concerne les **actions éligibles à la marge**, pas tous les candidats Oracle. Beaucoup de titres TOP20 XSHE n'appartiennent pas à cette liste source, et sont donc exclus de cette étude.

Ensuite, la baseline exige ici toutes ses variables prix finies, conformément à l'absence d'imputation. Parmi les 38 855 événements 2025H1 disposant des quatre variables de marge, `position_52w` manque sur 28 264 et `sma200_distance` sur 21 585. Ces absences se recoupent : les compteurs ne s'additionnent pas. Le panel prix neutralise explicitement les positions/SMA longues après événement de facteur, et exige un historique roulant complet ; suspensions, fenêtres insuffisantes et autres contrôles peuvent aussi produire des valeurs manquantes. B5 n'a pas désactivé ces protections ni recalculé ces variables arbitrairement.

Au final, seules 8,50 à 19,66 % des lignes TOP20 XSHE par semestre passent le masque commun du retard principal. **Un éventuel résultat positif sur cette population ne serait pas automatiquement généralisable au TOP20 entier.** Le périmètre restreint et la sensibilité à cette sélection doivent être explicités avant l'expérience ; supprimer les variables longues ou autoriser une imputation constituerait une nouvelle définition de baseline à pré-enregistrer.

### Reproduire le contrôle indépendant

Service : [cn_margin_features_audit_15b5.py](../../modelFactory/cn_margin_features_audit_15b5.py).

```powershell
python -u -m modelFactory.cn_margin_features_audit_15b5 --root artifacts/research/cn_margin_lending/sprint15b5_features_v3
```

Cette commande ne reconstruit pas les sorties, ne télécharge rien et n'écrit pas en base ; elle renouvelle le rapport d'audit.

### Suite recommandée avant tout entraînement

B5 est clôturé pour les features et jointures. Le protocole d'évaluation à huit semestres n'est pas réalisable tel quel : six folds manquent d'historique OOF et seuls les deux folds 2025 dépassent le minimum avant purge.

La prochaine tranche doit auditer/pré-enregistrer un calendrier réalisable, notamment la possibilité de générer un Oracle OOF antérieur (par exemple 2021, sous réserve des fenêtres d'apprentissage réellement disponibles) et de fixer de nouvelles périodes directionnelles. Des scores OOF supplémentaires pourront rendre certains folds plus récents réalisables ; ils ne garantissent pas à eux seuls les huit folds initiaux. Toute révision des dates, du nombre de folds ou de la baseline exige une campagne distincte avec critères adaptés fixés **avant** les performances.
