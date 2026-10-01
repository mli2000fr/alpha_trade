# α-Trade — Guide fonctionnel du marché chinois (CN_A)

**État du dépôt au 1er octobre 2026.** Ce guide s'adresse à une personne qui reprend l'application sans la connaître. Il décrit l'implémentation actuelle, puis distingue ce qui est opérationnel, expérimental ou en attente. Les résultats historiques cités ne sont pas des performances futures promises. L'[index CN](./README.md) renvoie aux preuves de chaque sprint.

## 1. Ce qu'est le parcours CN

Le projet historique traite les actions américaines (`US_EQ`). Le parcours chinois ajouté traite les **actions A de Shanghai et Shenzhen** (`CN_A`), en CNY, sur le calendrier `Asia/Shanghai`. Le code connaît également `CN_BJ`, mais ce guide ne lui attribue pas les capacités de recherche ou de trading de CN_A. Un code titre seul ne prouve pas son marché : le couple marché + identité instrument est obligatoire.

Le système CN peut conserver un référentiel, des prix et leurs facteurs ; reconstruire l'univers disponible avant chaque séance ; produire des features et labels de recherche ; entraîner des folds Oracle et Ranking OOS ; rejouer des portefeuilles hypothétiques ; publier un score Oracle prospectif de **recherche** ; observer Dragon/Tiger et réaliser un appariement sans issues ; simuler des intentions d'ordre *shadow*. Il **n'envoie aucun ordre CN paper/live**. Le [contrat de marché](../../config/markets/market_cn.yaml) conserve `enabled: false`, `live_enabled: false`, `short_execution_enabled: false`. Le [routeur broker](../../execution_engine/broker_router.py) rejette une demande CN avant de créer un client.

| Terme | Sens dans α-Trade |
| --- | --- |
| PIT (*point-in-time*) | Utiliser seulement une donnée réellement disponible **avant la décision**. Une archive historique consultée aujourd'hui ne prouve pas sa version passée. |
| Séance J / décision K | Après la clôture de J, le système peut préparer la prochaine séance ouverte K. Les congés ne comptent pas comme séances. |
| OOS / Walk-Forward | Un fold est entraîné sur l'histoire admissible avant son semestre test ; ses prédictions portent sur ce semestre. Un OOS déjà inspecté n'est plus un holdout vierge pour choisir une nouvelle idée. |
| D1 / D10 | Déciles **réalisés** des rendements futurs d'une même séance : environ 10 % des plus faibles / plus forts. Inconnus au moment du signal. |
| Oracle Extreme TOP20 | Les 20 % de meilleurs scores de **mouvement extrême** (D1 **ou** D10). Ce n'est pas une liste d'achats LONG. |
| Ranking signé | Modèle distinct visant à ordonner de D1 vers D10. Une bonne métrique symétrique ne valide pas automatiquement D10/LONG. |
| Replay / shadow / fill hypothétique | Simulation ou observation de recherche, sans ordre broker ni PnL encaissé. |

```text
BaoStock + calendrier + référentiel -> bruts/staging CN horodatés
  -> canonique (titres, séances, OHLCV brut, facteurs, limites)
  -> univers éligible avant ouverture J -> features connues avant J
  -> labels futurs H5/H10/H15/H20 [recherche, seulement quand mûrs]
  -> Oracle amplitude OOS -> TOP20 D1 OU D10
  -> Ranking/veto directionnel -> replay portefeuille hypothétique

Prospectif 2026 : D6 listes Dragon/Tiger + D9 cours/Oracle
  -> D10 appariement sans labels -> D11 cumul -> 17-C qualité
  -> 18-C intentions shadow, aucun broker
```

## 2. Bases, configuration et séparation US/CN

MySQL `alpha_trade` reste la base US ; **`alpha_trade_cn`** est la base CN. Le [registre](../../config/databases.yaml) n'autorise CN_A/CN_BJ qu'avec `cn_primary` et US_EQ avec `us_primary`. Le [routeur de base](../../database/router.py) refuse un mauvais couple marché/base : pas de fallback silencieux vers US. Les identifiants CN sont pris dans l'environnement (`LOGIN_DB_CN`, `PASSWORD_DB_CN` ou fallback déclaré), jamais dans YAML. `instrument_id` est local à une base ; pour transporter une identité entre systèmes, utiliser aussi `market_code` et `instrument_uid`.

| Fichier | Usage actuel |
| --- | --- |
| [config_cn.yaml](../../config_cn.yaml) | BaoStock primaire, `cn_primary`, fuseaux, racines d'artefacts, conservation des bruts. `canonical_writes_enabled: false` bloque la promotion **générique** par défaut ; D9 dispose de son chemin explicitement contrôlé. |
| [batch_cn.yaml](../../batch_cn.yaml) | Sauvegarde `cn_db_backup`, qualité `cn_daily_quality_17c`, anciens batchs génériques inactifs, enrichissements optionnels. |
| [batch.yaml](../../batch.yaml) | Catalogue US **et provisoirement quatre batchs prospectifs CN** D6/D9/D10. Leur migration 17-D est préparée, pas effectuée. Ne pas copier manuellement les sections dans les deux catalogues. |
| [config/markets/market_cn.yaml](../../config/markets/market_cn.yaml) | Devise, calendrier, benchmark, capacités et verrous live/short. Le mode recherche utilise des routes dédiées malgré `enabled: false`. |
| [config/universe_cn.yaml](../../config/universe_cn.yaml) | Seuils initiaux d'éligibilité avant ouverture, non optimisés pour le rendement. |
| [config/features_cn/cn_price_v1.yaml](../../config/features_cn/cn_price_v1.yaml) | Profil prix CN, benchmark CSI 300 et 252 séances de chauffe. |
| [config/labels_cn.yaml](../../config/labels_cn.yaml), [config/research_cn](../../config/research_cn) | Labels et protocoles Oracle, Ranking, replay, Dragon/Tiger. Modifier un protocole implique une **nouvelle** campagne identifiée. |
| [calendrier opérationnel 2026](../../config/research_cn/sprint15d6_cn_calendar_2026.yaml) | Congés et séances prospectives. Les runners échouent fermés hors année qualifiée ; 2027 reste à préparer. |

Le code se répartit entre [dataIntegrityEngine](../../dataIntegrityEngine) (collecte/backfill), [service/market](../../service/market) (contrats et opérations), [modelFactory](../../modelFactory) (features, labels, ML, replay), [ihm/services/cn_research_market.py](../../ihm/services/cn_research_market.py) (écrans) et le routeur broker. Les artefacts CN vivent sous `artifacts/cn/` et `artifacts/research/`, pas dans les tables de prédictions US.

### Carte des modules à ouvrir pour comprendre une opération

| Question | Code producteur / contrôleur | Écriture ou sortie |
| --- | --- | --- |
| Comment BaoStock entre-t-il ? | [cn_provider_ingestion.py](../../dataIntegrityEngine/cn_provider_ingestion.py), [cn_ingestion.py](../../dataIntegrityEngine/cn_ingestion.py) | Runs, RAW, staging ; `cn_sprint7c_incremental.py` est le backfill incrémental utilisé par D9. |
| Comment une barre devient-elle canonique ? | [cn_canonicalizer.py](../../service/market/cn_canonicalizer.py), [cn_canonical_full.py](../../service/market/cn_canonical_full.py), [cn_sprint7c_incremental.py](../../dataIntegrityEngine/cn_sprint7c_incremental.py) | Tables canonique CN, selon chemin de promotion explicitement autorisé. |
| Pourquoi un titre est-il candidat ? | [cn_universe_pit.py](../../service/market/cn_universe_pit.py), [cn_sprint8_universe.py](../../dataIntegrityEngine/cn_sprint8_universe.py) | `cn_universe_*` et export de candidats par run. |
| D'où viennent features et labels ? | [cn_feature_panel.py](../../modelFactory/cn_feature_panel.py), [cn_oracle_labels.py](../../modelFactory/cn_oracle_labels.py) | Parquet annuels de recherche, sans table de prédictions. |
| Qui entraîne Oracle/Ranking ? | [cn_oracle_walk_forward.py](../../modelFactory/cn_oracle_walk_forward.py), [cn_global_ranking_walk_forward.py](../../modelFactory/cn_global_ranking_walk_forward.py) | Modèles, `predictions.parquet`, `report.json` par fold. |
| Qui réalise le replay ? | [cn_execution_contract.py](../../service/market/cn_execution_contract.py), [cn_portfolio_replay.py](../../service/market/cn_portfolio_replay.py), [cn_economic_replay_13b.py](../../modelFactory/cn_economic_replay_13b.py) | Rapports de simulation isolés ; aucun broker. |
| Qui publie Oracle prospectif ? | [cn_oracle_daily_15d9.py](../../service/market/cn_oracle_daily_15d9.py), [cn_oracle_prospective_15d8.py](../../modelFactory/cn_oracle_prospective_15d8.py) | État de lots J, export TOP20 K et rapports de recherche. |
| Qui collecte/apparie Dragon/Tiger ? | [cn_dragon_tiger_schedule_15d6.py](../../service/market/cn_dragon_tiger_schedule_15d6.py), [cn_dragon_tiger_matched_15d7.py](../../service/market/cn_dragon_tiger_matched_15d7.py), [cn_dragon_tiger_daily_15d10.py](../../service/market/cn_dragon_tiger_daily_15d10.py) | Snapshots officiels, paires sans issues, rapport quotidien. |
| Qui surveille et sauvegarde ? | [cn_daily_quality_17c.py](../../service/market/cn_daily_quality_17c.py), [cn_db_backup_17b.py](../../service/market/cn_db_backup_17b.py) | Rapport qualité en lecture seule et dump MySQL CN séparé. |

Le même nom de « batch » peut désigner une **configuration horaire**, un processus Windows, un run métier et un dossier d'artefacts : ce sont quatre objets distincts. En cas d'incident, vérifier les quatre avant de déclarer l'opération réussie ou échouée.

## 3. Tables `alpha_trade_cn` et leur rôle

Les migrations CN sont indépendantes des US : [alembic_cn.ini](../../alembic_cn.ini), [versions CN](../../alembic_cn/versions) et [SQL de référence](../../database/sql/cn). Alembic CN va actuellement jusqu'à `0007` (index). Les SQL CN `0008`/`0009` créent puis alimentent le contrat d'exécution ; **un simple upgrade Alembic n'installe donc pas automatiquement 0008/0009**. Vérifier le schéma réel avant replay/shadow. `alembic_version` est une table de migration, pas une donnée métier.

| Couche / table | Informations principales | Rôle |
| --- | --- | --- |
| `cn_ingestion_runs` | batch, fournisseur, marché/base, statut, compteurs, erreurs | Audit des collectes ; succès technique ≠ preuve PIT. |
| `cn_raw_payloads` | requête/page, JSON brut, hash, `observed_at`, `available_at`, révision | Trace de la réponse fournisseur et des corrections. |
| `cn_staging_rows` | endpoint, symbole, date, OHLCV/facteur/statut normalisés, hash, disponibilité | Zone tampon multi-fournisseurs avant contrôle et promotion. |
| `cn_staging_quality_metrics` | métrique par run/endpoint, seuil, statut | Contrôles du staging historique, distincts de 17-C. |
| `markets` | marché, base, devise, fuseau, `enabled`, `live_enabled` | Registre et verrou CN. |
| `instruments` | `instrument_id`, `instrument_uid`, MIC, symbole, listing/radiation | Identité stable, y compris radiés. |
| `instrument_provider_symbols` | code fournisseur et dates de validité | Résoudre `sh.600519` ou `sz.000001` à la bonne identité à la date J. |
| `instrument_status_history` | statut de cotation, ST, board, tradabilité, temps | Éviter de projeter le statut actuel dans le passé. |
| `market_sessions` | jour ouvert/fermé, ouverture/clôture UTC, segments | Calendrier et relation J/K. |
| `stock_bars_daily` | clé titre/date, OHLC **brut**, `pre_close`, `adj_close=close`, volume, montant, statut, disponibilité | Prix observés et provenance. Ne pas traiter `adj_close` comme un open exécutable. |
| `instrument_adjustment_factors` | titre/date/fournisseur, facteur et disponibilité | Ajustements et événements de trajectoire. |
| `cn_canonicalization_runs` | cutoff, empreinte, lignes promues/rejetées | Audit staging → canonique. |
| `cn_daily_price_limits` | limites dérivées haut/bas, politique, verrouillage, disponibilité | Exécutabilité par titre/séance ; limite inconnue ≠ fill garanti. |
| `cn_corporate_actions` | annonce/ex-date, espèces/actions/facteur, classification | Distinguer événement économique et simple variation de facteur. |
| `cn_canonical_coverage_metrics` | couverture par marché, board, année | Qualité du backfill. |
| `cn_universe_runs` | décision pré-ouverture, empreintes politique/données | Snapshot quotidien de l'univers. |
| `cn_universe_decisions` | titre candidat/exclu, motifs, liquidité, disponibilité | Expliquer pourquoi un titre était sélectionnable à J. |
| `cn_universe_execution_audit` | candidat et contrôle après clôture | Vérifier les données d'exécution **sans modifier** la décision du matin. |
| `market_execution_rules` | MIC/board, période, lots, tick, T+1, short | Contrat daté du replay ; `research_only` n'autorise aucun ordre. |
| `cn_execution_cost_profiles` | commissions, taxes, slippage, période, type | Coûts `RESEARCH_PROXY` ou broker vérifié ; profils actuels de recherche = hypothèses. |

Le backfill 2018–2025 validé comptait **5 405 actions**, radiées incluses, et le Sprint 8 a produit **1 942 séances** d'univers. Ce sont des résultats historiques, pas la preuve que le flux prospectif 2026 a réussi. D8/D9, D6/D10/D11 et shadow 18-C produisent surtout des **JSON/Parquet hors base** ; `global_oracle_labels`, `global_rank_history` et `model_predictions` US ne sont pas des preuves CN.

Avant toute requête, ouvrir explicitement `alpha_trade_cn` et contrôler `SELECT DATABASE();`. Exemples en **lecture seule** :

```sql
SELECT market_code, database_alias, enabled, live_enabled FROM markets;
SELECT session_date, session_status FROM market_sessions
 WHERE market_code='CN_A' ORDER BY session_date DESC LIMIT 10;
SELECT `date`, COUNT(*) AS barres FROM stock_bars_daily
 WHERE market_code='CN_A' GROUP BY `date` ORDER BY `date` DESC LIMIT 10;
SELECT run_id,batch_name,status,started_at,finished_at,
 requested_count,received_count,persisted_count,failed_count
 FROM cn_ingestion_runs ORDER BY started_at DESC LIMIT 10;
```

Ne pas lancer UPDATE, DELETE, migration ou backfill pour « réparer » un retard avant d'avoir contrôlé la séance ouverte, les rapports D9 et les heures de disponibilité.

## 4. De la collecte à la décision : fonctionnement quotidien

**BaoStock est la source gratuite primaire** du référentiel, calendrier, OHLCV, facteurs et indices. Tushare est conservé mais désactivé ; AKShare est un enrichissement possible, non canonique. Les listes Dragon/Tiger officielles SSE/SZSE forment un journal événementiel **distinct**. Les audits flux signés, analystes, marge et guidance n'ont pas créé de features directionnelles servables. Lire [fournisseurs](./actualisation_fournisseurs_chine.md) et [gate 16-A](./sprint_16a_gates_et_protocole_directionnel.md).

Le chemin historique est : collecte brute → staging avec empreintes et heures → contrôle des prix/statuts/facteurs/identités → promotion canonique → snapshots d'univers → panels Parquet. Pour 2026, **D9 est le seul propriétaire planifié des écritures canoniques quotidiennes**. Il prépare master/calendrier/indices, collecte `daily` et `adj_factor` en lots reprenables de 25 titres, promeut la séance J sous contrat insert-only, exige une couverture complète puis publie Oracle pour K. `cn_daily_market_data_sync` reste désactivé pour éviter un deuxième propriétaire. Un rattrapage manuel des cours ne crée jamais rétroactivement une prédiction publiée à temps. [D9](./sprint_15d9_journal_oracle_prospectif_quotidien.md), [17-C](./sprint_17c_qualite_quotidienne_proprietaire_collecte.md).

### Univers tradable : décision puis audit

La [politique V1](../../config/universe_cn.yaml) exige une fenêtre de 60 séances avec au moins 40 barres, au moins 15 barres sur 20 pour la liquidité, close précédent ≥ 1 CNY, montant moyen ≥ 5 M CNY et barre de la séance précédente. Ce sont des seuils **techniques initiaux**, pas un optimum de performance. La décision J n'utilise que les informations `available_at <= decision_at`, généralement jusqu'à J−1. Les IPO futures ne sont pas admises ; les radiés ultérieurs restent dans l'histoire. L'audit de la barre et des limites J arrive **après** la décision. Les anciens conflits de statut et limites inconnues sont explicitement exclus ou `UNVERIFIABLE`, pas convertis en fills. [Contrat détaillé](./contrat_univers_tradable_pit.md), [Sprint 8](./sprint_8_univers_pit.md).

### Chronologie d'une séance CN

Horaires ci-dessous en **Asia/Shanghai**. Paris est six heures en retard pendant l'heure d'été française, sept pendant l'hiver. Le Planificateur Windows peut lancer un contrôle chaque heure ; le lanceur n'exécute le travail qu'à l'heure métier : `NextRunTime` Windows n'est donc pas nécessairement la prochaine collecte effective.

| Moment | Tâche | Résultat attendu |
| --- | --- | --- |
| J 17:30, après clôture | `cn_dragon_tiger_after_close` (D6) | Premier snapshot de la liste officielle Dragon/Tiger J, horodaté. Aucun label. |
| J 18:15 | `cn_oracle_prospective_daily` (D9) | Collecte et canonique J ; export Oracle TOP20 pour prochaine séance ouverte K **avant 09:15 K**. |
| J 23:30 | `cn_daily_quality_17c` | Lecture seule : lots D9, barres, facteurs, limites, Oracle, D6/D10 ; aucune collecte. |
| K 08:30 | `cn_dragon_tiger_before_open` (D6) | Nouvelle observation officielle, pouvant ajouter **ou retirer** un titre. |
| K 09:15 | Cutoff de décision | Un score ou snapshot observé après cette limite ne peut pas décider à K. |
| K 09:30 | `cn_dragon_tiger_daily_match` (D10) | Appariement Oracle + dernier snapshot complet connu avant cutoff ; **sans issues futures**. |
| Après plusieurs séances | D11 manuel | Cumul des appariements et gates de couverture/équilibre ; pas de D1/D10 réalisé. |

Le calendrier configuré ferme le marché du **1er au 7 octobre 2026**. Le premier cycle réel après l'implémentation est attendu le 8 octobre. L'export Oracle pour le 8 a été préparé le 30 septembre ; cela ne prouve pas que D6/D10/D9 du 8 réussiront. D9 après clôture du 8 préparera normalement le 9. Une tâche Windows `Interactive` ne travaille pas quand la session nécessaire est fermée : garder le PC et la session disponibles pour obtenir une preuve prospective réelle. [Préflight daté](./preflight_premier_cycle_2026_10_08.md).

### Batchs et catalogues effectifs

| Batch | Catalogue | Statut et effet |
| --- | --- | --- |
| `cn_dragon_tiger_after_close`, `cn_dragon_tiger_before_open` | `batch.yaml` | Actifs `RESEARCH_ONLY`, captures D6. |
| `cn_oracle_prospective_daily` | `batch.yaml` | Actif `RESEARCH_ONLY`, seul propriétaire planifié du canonique J et de l'export Oracle K. |
| `cn_dragon_tiger_daily_match` | `batch.yaml` | Actif `RESEARCH_ONLY`, D10 écrit des artefacts d'appariement. |
| `cn_db_backup` | `batch_cn.yaml` | Actif, dimanche 04:00 Europe/Paris ; dump isolé CN, `keep: 3`. |
| `cn_daily_quality_17c` | `batch_cn.yaml` | Actif, 23:30 Shanghai, lecture seule et gate opérationnel. |
| `cn_daily_market_data_sync` | `batch_cn.yaml` | `DISABLED_DUPLICATE_D9` ; ne pas activer en parallèle. |
| `cn_staging_quality_daily` | `batch_cn.yaml` | `SUPERSEDED_BY_17C` ; ancien contrôle désactivé. |
| `cn_master_calendar_sync`, `cn_historical_backfill`, `cn_baostock_smoke` | `batch_cn.yaml` | Déclarés mais désactivés ; backfill historique non quotidien. |
| `cn_akshare_enrichment`, `cn_tushare_optional` | `batch_cn.yaml` | Désactivés ; validation de source/accès/PIT nécessaire. |

**Transition 17-D :** les quatre sections de recherche encore dans `batch.yaml` doivent un jour rejoindre `batch_cn.yaml` sous les **mêmes** noms de tâches, après un premier cycle D6/D9/D10 + 17-C réel et contrôlé. Le plan et un snapshot de retour arrière existent, mais la bascule **n'est pas faite**. La page Batch rejette des noms dupliqués entre catalogues. [Procédure](./sprint_17d_preparation_bascule_catalogues.md).

## 5. ML CN : cibles, modèles et limites des résultats

### Features et labels

Le panel [cn_price_v1](./sprint_9_features_cn_price_v1.md) est construit pour une décision **avant ouverture J**, seulement avec des barres connues jusqu'à J−1 : rendements 1/3/5/10/20/60, tendance SMA, ATR et volatilité, volume/montant, gap passé, CSI 300, rangs transversaux, breadth/dispersion, suspension/ST/limites antérieures et board. Warm-up : 252 séances. La taxonomie `SW_2021` est déclarée, mais **l'appartenance sectorielle historique PIT manque** ; ne pas traiter les champs secteur comme un signal validé. Sortie : `panel.parquet` et `report.json` sous `artifacts/cn/features/cn_price_v1/`.

La [cible Oracle](./sprint_10a_labels_oracle_cn.md) part de l'**open J observé** et se termine au close J+H (H = 5/10/15/20 séances), avec traitement documenté des facteurs. Le label n'est disponible à l'entraînement qu'à J+H+1. Une fin de série sans horizon complet donne **inconnu**, jamais rendement zéro. Pour chaque séance, D1/D10 sont les queues des trajectoires valides ; `oracle_extreme20` = D1 ou D10. Les labels sont des Parquet de recherche sous `artifacts/cn/labels/cn_oracle_labels_v1/`, pas des fills.

| Modèle / expérience | Fonction et constat |
| --- | --- |
| Oracle [10-B](./sprint_10b_oracle_walk_forward.md) | LightGBM/CatBoost sur les 32 variables figées, OOS 2022H1–2025H2. **GO recherche amplitude**, pas direction. H20 LightGBM : AUC 0,682, précision TOP20 38,00 % contre 33,71 % ATR dans cette campagne. |
| Ranking [10-C](./sprint_10c_global_ranking.md) | Apprend l'ordre D1→D10, global puis dans le pool Oracle OOS. Il repère surtout des D1 dans le bas ; D10 haut ne bat pas de façon convaincante une simple réversion. **Pas de LONG autonome validé.** |
| Diagnostic [11-A](./sprint_11a_diagnostic_directionnel.md) | Veto D1, LONG et abstention sur les prédictions OOS sauvegardées. Veto D1 intéressant en recherche ; D10/LONG **NO-GO**. |
| Replay économique [13-C](./sprint_13c_decision_economique.md) | Portefeuille LONG, coûts/lot/T+1/limites/actions d'entreprise. **NO-GO économique de production** : les politiques n'ont pas démontré d'avantage net stable sur cohortes comparables. |
| Familles [16-A](./sprint_16a_gates_et_protocole_directionnel.md) | Flux/analystes sans historique PIT suffisant, marge : douze comparaisons incrémentales NO-GO dans son périmètre ; événementiel prospectif trop jeune. Aucune combinaison déployable. |

La précision TOP20 Oracle est la part de mouvements extrêmes **parmi les titres retenus**, pas un taux de trades gagnants : D1 et D10 comptent tous deux comme « succès Oracle ». AUC/F1/IC de recherche n'incluent ni frais ni négociabilité. Un score prospectif D8/D9 existe **hors IHM de serving**, mais ce n'est pas un modèle CN de production.

### Artefacts et provenance à retrouver

| Étape | Emplacement typique | Contrôle avant interprétation |
| --- | --- | --- |
| Univers historique | `artifacts/cn/universe/<run_id>/` | `report.json`, `universe.txt`, fingerprints de politique et données. |
| Features | `artifacts/cn/features/cn_price_v1/<run>/` | `panel.parquet` et rapport : marché, dates, disponibilité, SHA-256. |
| Labels | `artifacts/cn/labels/cn_oracle_labels_v1/` | Horizon, qualité, dates de maturité et valeurs inconnues. |
| Oracle/Ranking OOS | `artifacts/cn/oracle/sprint10b/`, `artifacts/cn/ranking/sprint10c/` | Protocole, fold, modèle, rapport et empreinte des prédictions. |
| Journal D9 | `artifacts/cn/sprint7c_daily/<J>/`, `artifacts/research/cn_oracle_daily_15d9/runs/` | Tous les lots terminés, session J et publication avant cutoff K. |
| Export D8 | `artifacts/research/cn_oracle_prospective_15d8/<K>/` | `oracle_top20.parquet`, rapport, horodatages et empreinte concordants. |
| D6/D10/D11 | `artifacts/research/cn_dragon_tiger_15d6/`, `..._15d10/`, `..._15d11/` | Snapshot complet avant cutoff, paires sans labels, gates de cumul. |
| Qualité et shadow | `artifacts/research/cn_daily_quality_17c/runs/`, `artifacts/research/cn_shadow_18c/` | Rapport de séance, preuves de non-ordre et statut strictement hypothétique. |

Ces chemins sont des **emplacements types**, pas la preuve qu'un fichier pour la séance demandée existe. Les rapports portent des empreintes : ne pas éditer un Parquet/JSON ancien pour le « réparer ». Créer une nouvelle campagne ou suivre la procédure de reprise documentée.

## 6. IHM : où aller et comment lire les écrans

Sur **Pipeline**, **Diagnostic ML** et **Backtesting**, le sélecteur **Marché** offre `US_EQ` et `CN_A — recherche uniquement`. Le choix est indépendant pour chaque page : CN_A dans Pipeline ne modifie pas la page US voisine. En CN_A, les formulaires US sont masqués ; les chiffres viennent d'artefacts CN, pas des tables de métriques US. [Code IHM](../../ihm/services/cn_research_market.py), [guide 14-A](./sprint_14a_ihm_recherche_isolee.md).

| Écran | Utilisation | À ne pas conclure |
| --- | --- | --- |
| **Diagnostic ML → CN_A** | Voir campagnes Oracle/Ranking/directionnel autorisées, horizons, métriques par semestre et comparaison économique 13-C. | Registre **lecture seule**, pas un champion CN servable. Un rapport absent ne doit jamais être remplacé par US. |
| **Pipeline → CN_A** | Choisir `oracle` ou `ranking`, H5/H10/H15/H20, semestre OOS 2022–2025, `lightgbm`/`catboost` ; cliquer « Entraîner et prédire ce fold OOS CN ». Lire historique, journal, jalons. | **Un fold à la fois**, ni campagne complète ni prédiction future. Ranking exige les deux folds Oracle OOS compatibles. Sortie isolée sous `artifacts/ihm_pipeline_runs/cn-research-fold/`. |
| **Backtesting → CN_A** | Choisir semestre, politique, seed, scénario de fill et coûts du protocole 13-A ; lancer une cellule de replay ; lire journal et historique CN. | Ce n'est **pas** `python -m backtesting run` US. Fills et PnL hypothétiques ; `completed` ≠ GO économique. Sortie sous `artifacts/ihm_backtesting_runs/cn-research-replay/`. |
| **Workflow & Orchestration → Batch** | Chercher `cn_` ; examiner catalogue effectif, fuseau, calendrier, fournisseur, tables, tâche Windows, rapports/logs ; installer, lancer maintenant, désinstaller. | Désinstaller enlève **la tâche Windows**, pas les données. Une tâche installée mais `enabled: false` reste inactive. Les rapports CN hors base ne sont pas les lignes US de `pit_collection_runs`. |

Dans Pipeline, la barre de progression reflète des **jalons observés**, pas le temps restant. Dans Backtesting, une cellule peut être techniquement complète et économiquement censurée. Dans Batch, `LastRunTime` Windows peut être un simple contrôle horaire `SKIP`; une tâche `Ready` n'atteste pas une collecte réussie. Examiner les **rapports métier, heures et empreintes**. [Guide fold](./sprint_14d_pipeline_recherche_cn.md), [guide replay](./sprint_14c_replay_recherche_ihm.md).

## 7. Procédure quotidienne minimale

1. **Avant ouverture K :** vérifier qu'un export Oracle K a été publié avant 09:15 Shanghai et que D6 a réellement observé un snapshot officiel complet avant cutoff. Si absent, ne pas « compléter » après coup en prétendant avoir une décision PIT. Un jour fermé répond normalement `SKIP_CLOSED`.
2. **Après 09:30 K :** vérifier rapport D10. Périodiquement, produire un nouveau rapport [D11](./sprint_15d11_cumul_d7_outcome_blind.md). Il mesure suffisance de l'échantillon, **pas** la valeur directionnelle.
3. **Après clôture J :** contrôler les lots D9, le rapport `COMPLETED_RESEARCH_ONLY`, l'export pour K+1 et la qualité 17-C à 23:30 Shanghai. Un lot manquant, une couverture insuffisante ou une empreinte divergente demande audit, pas un rendement imputé à zéro.
4. **Chaque semaine :** contrôler l'archive `cn_db_backup` dans `backups/cn/db`, la rétention et les notifications. Refaire périodiquement une **restauration isolée** : la présence d'un `.sql.gz` ne garantit pas sa restaurabilité. Les artefacts sous `artifacts/` ne font pas partie du dump MySQL. [17-B](./sprint_17b_sauvegarde_restauration_cn.md).
5. **Gate 17-C :** sept séances **ouvertes consécutives** sans anomalie critique inexpliquée sont requises. Les premières candidates théoriques sont 8, 9, 12, 13, 14, 15 et 16 octobre 2026 ; leurs dates ne prouvent pas que les exécutions auront réussi.

Contrôles non destructifs depuis `F:\projets` :

```powershell
# Décision horaire D9, sans téléchargement ni écriture.
.\.venv\Scripts\python.exe -m service.market.cn_oracle_daily_15d9 --batch cn_oracle_prospective_daily --dry-run

# Éligibilité D10, sans créer de paire.
.\.venv\Scripts\python.exe -m service.market.cn_dragon_tiger_daily_15d10 --batch cn_dragon_tiger_daily_match --batch-config batch.yaml --dry-run

# Lire les derniers rapports plutôt que le seul statut Windows.
Get-ChildItem artifacts/research/cn_oracle_daily_15d9/runs -Filter 'run-*.json' | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name,LastWriteTime
Get-ChildItem artifacts/research/cn_daily_quality_17c/runs -Filter 'run-*.json' | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name,LastWriteTime
Get-ScheduledTaskInfo -TaskName AlphaTrade-CnDbBackup | Select-Object LastRunTime,LastTaskResult,NextRunTime
```

Un `Get-ChildItem` peut échouer tant que le premier dossier de rapports n'existe pas. Pour les commandes **qui écrivent**, suivre [le préflight du premier cycle](./preflight_premier_cycle_2026_10_08.md), [D9](./sprint_15d9_journal_oracle_prospectif_quotidien.md), [D10](./sprint_15d10_appariement_d7_quotidien.md) et [17-C](./sprint_17c_qualite_quotidienne_proprietaire_collecte.md). Ne pas effacer un `state.json` ou lancer plusieurs backfills pour « débloquer » sans identifier le run et son verrou.

## 8. Dépannage et interprétations dangereuses

| Symptôme | Réaction sûre |
| --- | --- |
| Aucun run durant un congé CN | Vérifier calendrier ; `SKIP_CLOSED` est normal. Ne pas forcer une prévision sur une séance fermée. |
| Tâche Windows `Ready`, aucune donnée | Vérifier rapport métier et journal. Le déclencheur technique a pu seulement constater « pas l'heure ». Une session `Interactive` fermée empêche le traitement utile. |
| D9 partiellement terminé | Lire `artifacts/cn/sprint7c_daily/<J>/state.json`, manifeste et lots ; la reprise est prévue. Pas de publication Oracle avant complétude, ni de score rétrodaté après 09:15 K. |
| D6 absent ou corrigé tardivement | Absence de snapshot complet ≠ absence d'événement. D10 doit refuser/signaler la lacune, sans fabriquer des témoins négatifs. |
| Pipeline CN s'arrête aux folds 2025 | Il s'agit du formulaire OOS 14-D. D8/D9 est un **autre** chemin prospectif de recherche, hors serving IHM de production. |
| Fold terminé mais replay médiocre | L'amplitude ne donne pas la direction. Coûts, prix d'ouverture, T+1 et limites changent le résultat. Lire le [NO-GO 13-C](./sprint_13c_decision_economique.md). |
| Bootstrap `--audit` annonce mauvaise révision | [bootstrap_database.py](../../service/tushare/bootstrap_database.py) attend encore `0005_canonical_full_coverage`, tandis que les migrations Alembic CN vont jusqu'à `0007`. Ce test de version est obsolète ; vérifier révision et tables réelles, puis corriger l'outil séparément. Ne pas réappliquer une migration au hasard. |
| Besoin d'un ordre CN | **Interdit actuellement.** `live_enabled=false` et le routeur broker bloquent paper/live. Un `HYPOTHETICAL_FILL` shadow n'est pas un ordre. |

## 9. Travaux ouverts, sans les présenter comme terminés

- **Premier cycle réel du 8 octobre** : D6 avant ouverture, D10 après 09:15, D9 après clôture, contrôle 17-C. Le [TODO D7–D11](./TODO_reprise_oracle_dragon_tiger_D7_D11.md) et le [TODO shadow](./TODO_sprint_18c_post_cloture_2026_10_08.md) fixent les preuves. Le plan shadow de 12 intentions existe ; tentative et marque attendent encore les observations.
- **17-D** : déplacer de manière contrôlée les quatre batchs de recherche de `batch.yaml` à `batch_cn.yaml` après le premier vrai cycle. Un snapshot de retour arrière existe ; aucune bascule encore.
- **17-C** : sept séances ouvertes successives sans gate critique. Un jour réussi n'est pas suffisant.
- **16-B et D1/D10** : aucune nouvelle campagne multi-familles honnête sans source PIT historique ou échantillon prospectif indépendant mûr. Pour Dragon/Tiger : au moins 60 séances, 200 exposés, 80 % appariés, deux trimestres et covariables équilibrées **avant** étude d'issues H20 mûres. [16-A](./sprint_16a_gates_et_protocole_directionnel.md).
- **Suite longue** : qualifier calendrier 2027, droits et stabilité des fournisseurs, sauvegarde hors machine des artefacts, tarifs broker réels et validation économique indépendante avant même d'envisager paper/live.

## 10. Parcours conseillé à la personne qui reprend

1. Lire ce guide, [l'architecture](./architecture_bases_batchs_configuration_cn.md) et le [planning](./sprint_planning_integration_marche_chinois.md). Identifier physiquement les deux bases ; ne jamais utiliser un script US sur `alpha_trade_cn`.
2. Dans **Diagnostic ML → CN_A**, retrouver Oracle, Ranking, diagnostic directionnel et NO-GO 13-C. Savoir expliquer pourquoi TOP20 Oracle ≠ TOP20 LONG.
3. Dans **Workflow & Orchestration → Batch**, filtrer `cn_` et noter catalogue effectif, fuseau, tâche Windows, dernier rapport métier et désactivations. Ne rien réinstaller pendant l'attente de 17-D.
4. En lecture seule, comparer un `cn_universe_runs` et ses `cn_universe_decisions` aux features et au rapport Oracle de la même séance. Vérifier qu'aucune donnée de J n'est introduite dans une décision avant ouverture J.
5. Lire un fold OOS dans Pipeline et une cellule de replay dans Backtesting : distinguer **fin technique**, **validité de donnée**, **performance statistique** et **GO économique**.
6. Suivre le premier cycle prospectif selon le [préflight daté](./preflight_premier_cycle_2026_10_08.md). Devant une base, une heure, un hash ou un cutoff incohérent, suspendre l'interprétation et conserver les preuves.

Pour aller plus loin : [univers PIT](./contrat_univers_tradable_pit.md), [features](./sprint_9_features_cn_price_v1.md), [labels](./sprint_10a_labels_oracle_cn.md), [Oracle](./sprint_10b_oracle_walk_forward.md), [Ranking](./sprint_10c_global_ranking.md), [contrat d'exécution](./sprint_12a_contrat_execution.md), [replay](./sprint_12b_replay_portefeuille_cn.md), [D7](./sprint_15d7_protocole_appariement_dragon_tiger.md), [sauvegarde](./sprint_17b_sauvegarde_restauration_cn.md), [qualité](./sprint_17c_qualite_quotidienne_proprietaire_collecte.md) et [verrou broker](./sprint_18a_routage_broker_fail_closed.md).
