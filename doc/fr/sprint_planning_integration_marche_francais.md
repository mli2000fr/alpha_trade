# Sprint planning détaillé — intégration du marché français dans α-Trade

État de référence : 1er octobre 2026. Ce document est un **plan de mise en œuvre**, pas le constat que les sprints sont réalisés. Pour l'état effectivement exécuté des Sprints 2 à 5 au 2 octobre, lire [le rapport d'exécution](execution_sprints_2_5_2026-10-02.md). Il complète [l'étude France](etude_integration_marche_francais.md) et [le POC guidance](poc_guidance_120_emetteurs.md), et prend pour référence l'architecture effectivement présente dans le code et le [planning CN](../cn/sprint_planning_integration_marche_chinois.md).

Le [Sprint 5](sprint_5_finalisation_go_limite_2018_2026.md) est désormais clos avec `GO_RESEARCH_J1` sur 2018–2026 : 561 001 barres, 330 titres dont 36 radiés (10,91 %) et 2 209 séances admissibles. La source publique Euronext a corroboré exactement 5 733 séances de 34 radiés récents, en complément des deux radiés déjà couverts. Ce GO autorise uniquement les travaux ML/backtest de recherche avec disponibilité J+1 ; aucune table canonique, aucun live, aucun paper trading et aucun serving ne sont autorisés. Les actions sur titres économiques, la preuve PIT stricte et la chaîne TLS du POC restent à fermer. Les barres 2016–2017 restent archivées mais hors du premier périmètre exploitable.

Le [GO limité à un sous-ensemble](sprint_5_sous_ensemble_verifie.md) est en préparation : 490 codes satisfont le préfiltre mécanique, mais aucun n'est promu sans vérification externe des identités, périodes, MIC et prix.

## 1. Décision d'architecture et résultat attendu

La décision du propriétaire du projet prévaut sur l'ancienne étude : **une seule application et un seul dépôt**, mais trois bases physiques indépendantes. `alpha_trade` reste US, `alpha_trade_cn` reste CN et **`alpha_trade_fr` est réservée à la France**. Cette dernière existe déjà et ne contient aucune table : ne pas la recréer, ne pas y copier indistinctement les tables US/CN et ne pas faire de migration US sur elle. La phrase de l'ancienne étude disant qu'une base France séparée n'était pas nécessaire est désormais obsolète sur ce point précis.

Périmètre initial : **actions ordinaires cotées à Paris, cotées en EUR, recherche → ML → prédiction → backtest → exploitation des données**. Définir dès le Sprint 0 si le segment Euronext Growth Paris entre dans le premier univers ; par défaut, le traiter comme un segment distinct jusqu'à validation des métadonnées, coûts et règles. ETF, ETN, fonds, warrants, droits et obligations sont exclus du premier univers d'actions. Une action étrangère cotée à Paris n'est pas rejetée mécaniquement sur son préfixe ISIN : son éligibilité dépend du MIC, du type de titre, de la devise et de la politique d'univers. L'éligibilité PEA est un attribut éventuel **distinct** de l'appartenance au marché parisien.

`FR_EQ` / `fr_primary` sont les identifiants projet proposés ; ils devront être verrouillés dans un ADR avant migration. EUR est la devise de base de recherche ; aucune conversion USD cachée. Le courtier, le paper et le live ne sont **pas** des prérequis au POC historique. Aucun ordre français ne doit être routé vers Alpaca par défaut. Le long est étudié d'abord ; le short peut être étudié comme label, diagnostic ou veto, mais aucune vente à découvert réelle sans disponibilité de prêt, coûts et route courtier vérifiés.

```text
US_EQ ── us_primary ── alpha_trade     ── données/artefacts US ── broker US actuel
CN_A  ── cn_primary ── alpha_trade_cn  ── données/artefacts CN ── recherche/shadow
FR_EQ ── fr_primary ── alpha_trade_fr  ── données/artefacts FR ── recherche d'abord
  │
  └─ identités ISIN + MIC + instrument_id → sessions XPAR → univers PIT
     → barres validées → features/labels FR → Oracle/ranking → backtest EUR
     → prédiction shadow → paper puis live uniquement après un GO séparé
```

L'objectif scientifique comporte **deux questions distinctes** : l'Oracle trouve-t-il l'amplitude extrême en France ? Et, parmi ces extrêmes, existe-t-il un signal PIT robuste pour D1/D10 ? Un GO technique sur la première n'implique pas un GO directionnel ou économique sur la seconde. La démarche doit préserver un vrai OOS jamais utilisé pour choisir les features/seuils.

## 2. Ce qui existe déjà et ce qui manque

| Couche | Réutilisable dans le code actuel | Travail FR encore nécessaire |
| --- | --- | --- |
| Marchés et bases | `common/market_context.py`, `database/router.py`, `config/databases.yaml` : allowlist stricte US/CN et vérification de la base réellement ouverte. | Ajouter `FR_EQ` et `fr_primary`, puis des tests qui interdisent les mauvaises bases ; ne pas changer les defaults US. |
| Calendrier | `common/market_calendar.py` encapsule NYSE et des sessions CN ; cutoff PIT par marché. | Brancher un calendrier XPAR/Europe/Paris, vérifier jours fériés, demi-séances, changements d'heure et enchères ; aucun fallback « lundi-vendredi » silencieux. |
| Identité et tables | CN possède staging, master, barres, ajustements, univers PIT et migrations dans `alembic_cn/` et `database/sql/cn/`. Le canonique US a déjà été migré vers `instrument_id` selon le planning CN. | Schéma **propre à `alpha_trade_fr`**, migrations `alembic_fr/`, SQL de référence `database/sql/fr/`, adaptation aux sources et aux règles FR ; ne pas copier les limites de prix/T+1 chinoises. |
| Recherche ML | Découpage CN `cn_feature_panel`, labels Oracle, walk-forward, ranking et replay ; modèle Oracle et ranking US. | Profiles, benchmark, population et labels FR mono-marché ; nouveaux artefacts `artifacts/fr/` ; zéro poids US/CN servi comme modèle FR. |
| Batch et IHM | `batch.yaml` et `batch_cn.yaml` ; page Batch et vues CN de Pipeline/Diagnostic/Backtest. | `batch_fr.yaml`, launchers/notifications FR, garde anti-doublon des catalogues et vue FR de recherche ; ne pas transformer le formulaire US en formulaire FR par simple étiquette. |
| Exécution | `execution_engine/broker_router.py` rejette tout marché non US. | **Conserver ce refus** jusqu'au sprint courtier ; recherche et backtest ne doivent pas activer d'ordres. |
| Études FR | POC AMF/INFO-FINANCIERE et 120 émetteurs avec contrôles PDF. | Rejouer sur un véritable univers PIT XPAR et avec source de prix qualifiée ; POC ≠ feature ou modèle de production. |

Point de vigilance sur les documents : le POC de 120 émetteurs sélectionne des **publications**, non 120 actions tradables. Les 18 titres du POC AMF ne définissent pas les vrais déciles du marché. Ne transférer ni leurs taux ni leurs règles dans la production sans nouvelle validation.

## 3. Règles de livraison communes à tous les sprints

1. Chaque sprint a un responsable, un état (`À FAIRE`, `EN COURS`, `GO`, `NO_GO`, `BLOCKED`), une configuration effective, des tests et une décision écrite. Une estimation de durée ne remplace pas le gate.
2. Une migration de base a : révision Alembic FR, SQL lisible de référence, vérification `SELECT DATABASE() = 'alpha_trade_fr'`, test sur base vide et sur base déjà migrée, sauvegarde et procédure de retour arrière. Pas d'`ALTER` manuel non traçable.
3. Les sorties de recherche, modèles, prédictions, logs et backups restent isolés FR ; chaque run porte `market_code`, `database_alias`, `currency`, `calendar_id`, source/version de données, période, univers, horizon, git SHA et config hash.
4. Les join critiques utilisent `instrument_id` et date/validité, non un symbole nu. `ISIN` identifie un titre mais **pas seul une ligne de cotation** ; conserver MIC/venue, fournisseur et validité des symboles.
5. Toutes les features, exclusions, corporate actions, annonces et coûts sont évalués à la date de décision. `published_at`, `observed_at`, `available_at` et éventuellement `revised_at` ne sont pas interchangeables.
6. Séparer prix brut de négociation, prix corrigé et total-return. Les labels, features et fills disent explicitement lequel ils utilisent. Tester l'invariance économique autour des splits/dividendes.
7. Aucune cross-section ne mélange US/CN/FR. Si l'univers journalier est trop petit, le label D1/D10 est invalide ce jour-là ; ne pas créer artificiellement un « décile » de 1–2 titres.
8. Tout travail sur les chemins communs exécute tests US et CN pertinents et une comparaison golden ; le défaut US doit rester inchangé. Aucun batch en cours n'est relancé, arrêté ou redirigé par le projet FR.
9. Les sources gratuites et licences sont vérifiées pour l'usage réel (recherche interne, stockage, redistribution, paper/live) ; le coût, le quota et l'historique PIT sont documentés avant ingestion de masse.
10. Recherche, prédiction, shadow, paper et live ont des portes de promotion distinctes. Un résultat ML ou backtest positif n'autorise jamais implicitement le live.

Traces attendues : `artifacts/audits/fr_integration/sprint_<NN>/effective_config.json`, `tests_summary.json`, `data_quality.json` si données, `us_cn_parity.json` si code commun touché, `decisions.md` et `gate_result.json`. Tout batch long a run ID, logs, statut final, reprise, compteurs demandé/reçu/persisté/échoué/alertes et garde de concurrence. Le secret fournisseur n'apparaît ni dans les manifests, ni dans les logs.

## 4. Dépendances et gates de programme

| Sprint | Livraison principale | Dépend de | Porte de sortie |
| ---: | --- | --- | --- |
| 0 | ADR, périmètre, baseline US/CN | — | G0 |
| 1 | `FR_EQ` + route `alpha_trade_fr` fail-closed | 0 | routage sûr |
| 2 | schéma FR/Alembic/SQL et instrument master | 1 | migration isolée |
| 3 | fournisseur historique qualifié | 0–2 | source/licence validées |
| 4 | sessions XPAR et disponibilité PIT | 1–3 | calendrier fiable |
| 5 | backfill/canonique/actions | 2–4 | G1 données prix |
| 6 | univers tradable PIT/benchmark/secteur | 5 | G1 univers |
| 7 | profils de features FR | 4–6 | panel sans fuite |
| 8 | labels Oracle et D1/D10 | 5–7 | labels audités |
| 9 | Oracle amplitude OOS | 8 | G2 amplitude |
| 10 | direction/ranking/abstention | 9 | G2 direction ou NO_GO |
| 11 | AMF/DILA/guidance incrémental | 6–10 | signal PIT ou NO_GO |
| 12 | simulation/coûts FR | 4–6 | fills et coûts valides |
| 13 | replay net, stress, confirmation | 9–12 | G3 |
| 14 | parcours IHM/CLI FR recherche | 1–13 selon page | isolation IHM |
| 15 | batchs/sauvegarde/monitoring | 2–6, sources qualifiées | G4 ops |
| 16 | prédiction shadow | 9–15, politique retenue | G4 shadow |
| 17 | courtier/paper optionnel | 13,16 + fournisseur broker | G5 paper |
| 18 | canary live optionnel | 17 + accord explicite | G5 live |

| Porte | Pour avancer il faut | Si échec |
| --- | --- | --- |
| G0 — architecture | Scope XPAR, identifiants et DB séparée signés ; baseline US/CN sauvegardée | Aucun code transverse |
| G1 — données historiques | Master, calendrier, barres/actions, radiés, qualité et PIT conformes | Pas de labels/ML |
| G2 — qualité ML | OOS Oracle amplitude et D1/D10 évalués par horizon, couverture suffisante, pas de fuite | Recherche uniquement, pas de claim directionnel |
| G3 — économie | Replay net de frais, stress, sensibilité, coûts/taxes vérifiés et OOS final gelé | Pas de stratégie déployée |
| G4 — exploitation | Jobs et IHM isolés FR, alertes, sauvegarde/restauration, prédiction shadow fiable | Pas de paper |
| G5 — courtier | Éligibilité XPAR, prix, ordres, fills, réconciliation et kill switch prouvés | Pas de live |

Les sprints 0–5 sont essentiellement séquentiels. Une fois le référentiel et la qualité verrouillés, les chantiers ML et événements FR peuvent avancer en parallèle **sur des jeux figés**, sans changer l'OOS final.

## 5. Sprints de fondation et données

### Sprint 0 — Contrat France et baseline non-régression

**Objectif.** Rendre les choix vérifiables avant toute table. Inventorier lecteurs/écrivains de marché, règles US/CN déjà généralisées, source de vérité des configurations et dépendances d'exécution.

**Travaux.** (a) Écrire les ADR `FR_EQ`, `fr_primary`, `alpha_trade_fr`, EUR, XPAR, définition précise des segments admissibles, univers par date, market cap/liquidité, benchmark candidat et absence de broker FR. (b) Décider si la première tranche couvre uniquement le marché réglementé Paris ou aussi Growth ; séparer le segment dans le master dans tous les cas. (c) Cartographier toutes les tables parent/enfant et tous les chemins `symbol`-only, hardcodages `SPY`, NYSE, USD, Alpaca, frais US, et pages IHM. (d) Figer hashes et résultats d'un chargement, d'un entraînement, d'une prédiction et d'un backtest US, plus un scénario CN ; enregistrer les échecs de tests préexistants. (e) Relever les conditions d'utilisation des fournisseurs et le budget ; laisser les tarifs non confirmés comme décisions ouvertes, pas comme hypothèses.

**Livrables.** ADR France, matrice des impacts par fichier/table, registre de risques, tests golden et inventaire des prérequis fournisseurs. **Gate GO.** Périmètre instrument/venue explicite, baseline reproductible, aucune écriture sur les trois bases pendant l'audit.

### Sprint 1 — Routage France et base vide isolée

**Objectif.** Pouvoir désigner la France sans jamais ouvrir la mauvaise base et sans changer les valeurs par défaut US.

**Travaux.** Ajouter `MarketCode.FR_EQ` et l'allowlist `fr_primary` dans `common/market_context.py`, avec pays FR, EUR, `Europe/Paris`, calendrier XPAR et capacités `research/training/prediction/backtest` ; laisser `live_enabled=false`, `short_execution_enabled=false`. Ajouter `fr_primary` à `config/databases.yaml` avec valeurs/env FR explicites. Créer `config_fr.yaml` et `config/markets/market_fr.yaml` (désactivé tant que le schéma et le calendrier ne passent pas), plus un validateur des profils FR. Faire passer le contexte explicitement jusqu'aux points d'entrée de recherche ; rejeter toute commande France sans contexte/base compatible. Laisser le refus FR dans `execution_engine/broker_router.py`.

**Préflight de la base déjà créée.** Lire seulement l'existence, les permissions, le charset/collation, la version MySQL et `SELECT DATABASE()` ; confirmer zéro table métier (hors éventuelle table technique). Ne **pas** lancer une création de base, ne pas utiliser le compte US sans décision explicite, et tester qu'une route `FR_EQ→us_primary`, `US_EQ→fr_primary` ou `CN_A→fr_primary` échoue avant écriture.

**Livrables.** Registre/configuration FR, matrice de routage, tests d'isolation et procédure de credentials. **Gate GO.** La seule résolution valide est `FR_EQ/fr_primary/alpha_trade_fr`; le broker refuse FR ; golden US/CN identiques.

### Sprint 2 — Référentiel d'instruments et schéma initial FR

**Objectif.** Préparer un schéma versionné dans la base vide, sans refaire les migrations CN telles quelles.

**Travaux.** Installer un track `alembic_fr.ini` + `alembic_fr/versions/` pointant **seulement** vers `alpha_trade_fr`; créer `database/sql/fr/` comme reflet lisible des migrations. Modéliser `markets`, `instruments` (ID interne stable, type, devise, statut), `instrument_listings` (ISIN, MIC, segment, date début/fin), `provider_symbols` (fournisseur, symbole, validité), `instrument_status_history` (IPO, suspension, radiation, changement de nom), `market_sessions` et `fr_ingestion_runs`. Définir PK, uniques, FK, index date/instrument et une stratégie de corrections ; une ligne de cotation XPAR n'est pas fusionnée avec une autre venue portant le même ISIN. Prévoir sources brutes/staging séparées du canonique et un `schema_version` de contrat.

**Tests.** Upgrade sur base FR vide ; upgrade répété sans effet ; rollback sur copie/fixture si faisable ; refus de deux symboles fournisseurs valides qui se chevauchent pour la même identité ; historique d'un changement de ticker ; contrôle que les migrations FR ne voient jamais `alpha_trade` ni `alpha_trade_cn`.

**Gate GO.** Schéma initial installé et documenté, SQL et Alembic cohérents, aucune table US/CN modifiée, restauration testée sur une base FR de test.

### Sprint 3 — Qualification des fournisseurs et POC de données reproductible

**Objectif.** Choisir les fournisseurs sur des données réelles, licences et PIT, pas sur une simple promesse commerciale.

**Travaux.** Mettre en concurrence au moins une source historique EOD/ref officielle ou contractuelle avec une référence indépendante sur un échantillon stratifié (grandes/moyennes/petites valeurs, dividendes, splits, radiations, titres anciens, trous). Vérifier profondeur, présence des radiés, OHLCV brut/ajusté, splits/dividendes, devises, ISIN/MIC, heures de disponibilité, pagination, corrections tardives, quotas et droits de stockage. Évaluer EODHD `PA` si l'abonnement choisi permet l'usage, sans supposer qu'il remplace les données officielles de place ; Yahoo `.PA` peut servir de contrôle exploratoire, pas de vérité canonique contractuelle. Qualifier séparément DILA/INFO-FINANCIERE, AMF, INPI et tout benchmark/secteur. Rédiger une matrice `source → champs → dates → licence → coût → couverture → niveau de confiance` et échantillonner manuellement les discordances.

**Livrables.** POC figé (payload/hash/date), scorecard fournisseur, décision de source primaire/fallback par famille. **Gate GO.** La source prix couvre la fenêtre cible et les radiés à un niveau acceptable défini **avant** le backfill ; ajustements et licence ne sont pas ambigus. Si aucun fournisseur ne satisfait ce gate, arrêter ici le ML historique, mais poursuivre éventuellement une collecte prospective de recherche.

### Sprint 4 — Calendrier XPAR et politique PIT

**Objectif.** Une seule notion vérifiable de « séance française » et d'information disponible avant décision.

**Travaux.** Étendre `common/market_calendar.py` pour XPAR ; importer/versionner horaires officiels, jours fermés, demi-séances et exceptionnelles, ouverture/clôture et passage UTC↔Paris avec DST. Définir les cutoffs distincts : signal EOD utilisable au plus tôt après publication de la barre, ordre hypothétique à l'ouverture suivante, annonces à heure inconnue à la séance suivante par prudence, snapshot fournisseur non rétroactif. Définir `exchange_session`, `decision_time_utc`, `available_at`, `execution_session`. Les enchères d'ouverture et de clôture restent un contrat séparé ; elles ne se déduisent pas d'un prix journalier. Comparer le calendrier embarqué à la source officielle [Euronext horaires/jours fériés](https://www.euronext.com/en/trading/trading-hours-holidays) et journaliser les divergences ; aucun fallback weekday-only en FR.

**Tests.** Jours fériés, demi-séances, vendredi→lundi, changement d'heure, annonce pendant/après séance, entrée `J+1`, horizons mesurés en *séances* et non jours calendaires. **Gate GO.** Toute date de signal et de fill possède une séance et une preuve de disponibilité ; une date inconnue échoue fermement.

### Sprint 5 — Backfill historique, corporate actions et canonique

**Objectif.** Obtenir un panel prix utilisable par recherche, incluant titres radiés et changements historiques.

**Tables candidates.** `fr_raw_payloads` ou tables brutes par fournisseur, `stock_bars_daily` FR canonique, `corporate_actions`, `adjustment_factors`, `canonicalization_runs`, `data_anomalies`, `source_versions`. Les noms définitifs sont fixés par le dictionnaire Sprint 2 ; la même table logique peut s'appeler `stock_bars_daily` car elle vit dans **une autre base**.

**Travaux.** Backfill par tranches datées et instrument, reprise après crash, checksum, pagination, rate limiting et corrections historisées. Stocker OHLCV brut avec unité/devise, ajustement split et total-return séparés ; ne pas remplir `vwap` par un substitut non documenté. Traiter splits, dividendes, droits, fusions, changement de ticker et radiation : contrôle économique de `close/open/volume` avant/après opération. Conserver la source/provenance par ligne et une règle de canonicalisation versionnée. Faire une seconde ingestion pour démontrer l'idempotence. Vérifier couverture par année/secteur/capitalisation/état de cotation et comparer aux [données de référence Euronext](https://live.euronext.com/en/datashop/reference-data) lorsque accessibles.

**Gate GO.** Rapport de couverture et d'anomalies pré-enregistré, aucun double `(instrument_id, session_date)` canonique, corrections explicables, radiés représentés, vérification manuelle de cas corporate actions. Toute zone historique insuffisante est **exclue** des entraînements ; elle n'est pas comblée artificiellement.

### Sprint 6 — Univers tradable PIT et benchmark/secteur

**Objectif.** Reconstruire à chaque date les actions que le système *aurait pu* connaître et négocier.

**État au 3 octobre 2026.** Le [Sprint 6-A — contrat d’univers PIT](sprint_6a_contrat_univers_pit.md) est clos avec `GO_6A_CONTRACT_ONLY`. La politique versionnée, les tables `fr_universe_runs` / `fr_universe_decisions` et l’audit complet des 811 954 lignes sont en place. Les 561 001 lignes `RESEARCH_J1_ELIGIBLE` sont seulement `observable`; `training` reste `UNKNOWN`, tandis que `tradable` et `servable` sont explicitement `PROHIBITED`. Le prochain lot est 6-B, consacré à l’historique et à la liquidité PIT J+1 ; benchmark et secteurs restent hors de 6-A.

**Sprint 6-B clos.** Le [contrôle historique et liquidité PIT J+1](sprint_6b_historique_liquidite.md) passe avec `GO_6B_TRAINING_UNIVERSE` : 170 046 snapshots entraînables sur 561 001 observations, couvrant 168 symboles au moins une fois. Les seuils ont été pré-enregistrés et la seconde persistance est idempotente. Les identités canoniques restent absentes, et les périmètres `tradable` / `servable` demeurent interdits. Le prochain lot est 6-C : identité, benchmark large France et secteurs datés.

**Sprint 6-C réalisé, GO limité prix.** Le [contrat identité/benchmark/secteurs](sprint_6c_identite_benchmark_secteurs.md) produit `GO_6C_RESEARCH_PRICE_ONLY` : 330 identités de recherche, 15 historiques multi-MIC conservés et benchmark synthétique `FR_RESEARCH_EW_PRICE_V1`, composition connue avant chaque séance, disponible J+1. Sur 2 209 séances, 1 927 sont `KNOWN` et 282 restent `UNKNOWN`. Migration FR 0008 et persistance réalisées. L'accès sectoriel EODHD testé renvoie HTTP 403 : 330 secteurs historiques inconnus, neutralisation sectorielle bloquée. Les `instrument_id` restent NULL. Le Sprint 6 global n'est pas clos pour le tradable ; le prochain lot autorisé est Sprint 7-A, panel prix uniquement.

**Travaux.** Créer `universe_runs`, `universe_decisions`, `fr_liquidity_snapshots`, `sector_memberships` datés et tables d'audit. Filtres pré-enregistrés : type de titre, MIC/segment, devise, statut cotation/suspension, historique minimal, prix/volume/spread si disponible, market cap **PIT** seulement, corporate action/radiation ; les manquants ont un état `UNKNOWN`, non un faux zéro. Séparer (1) univers observable pour labels, (2) univers éligible à l'entraînement, (3) univers tradable pour backtest, (4) disponibilité modèle. Évaluer le benchmark large et la taxonomie de secteur sur source disponible/licenciée ; ne pas prendre CAC 40 comme proxy large sans justification et ne jamais utiliser SPY implicitement. Figer les versions de tous les seuils.

**Tests.** Titres entrés/sortis, suspensions, changement de MIC, action étrangère sur XPAR, petites valeurs, doublons ISIN, absence cap, univers à date antérieure indépendant d'une liste actuelle. **Gate GO.** Coverage et motifs de rejet par jour/année ; aucune survivorship leakage, aucune microcap incluse ou exclue sans règle explicite.

## 6. Sprints de recherche et de validation économique

### Sprint 7 — Features France et dictionnaire de disponibilité

**Sprint 7-B réalisé le 3 octobre 2026.** Le [profil relatif au benchmark](sprint_7b_features_relatives_benchmark.md) ajoute 12 features au profil prix figé (26 au total), avec contrôle J+1, fenêtres KNOWN sans franchissement de segments et disponibilité maximale. Deux reconstructions identiques ; 164 tests ciblés passent. Support commun : 119 505 lignes prêtes contre 146 293 en prix-only (perte 18,31 %), 41 282 dans les quatre semestres qualifiés : 2022H2, 2023H1, 2024H2 et 2025H2. Gates de couverture inchangés. Aucun entraînement ni démonstration de prédictivité ; réserves de disponibilité recherche et secteurs UNKNOWN maintenues. Le prochain lot supervisé devra qualifier labels, maturité et folds avant comparaison prix-only/benchmark sur support commun.

**Sprint 7-A2 réalisé le 3 octobre 2026.** Le [profil prix figé par période](sprint_7a2_profil_prix_fige_par_periode.md) fixe `fr_price_short_v1` : mêmes 14 features sur toutes les périodes, 146 293 lignes prêtes séance par séance et 121 016 dans les 12 semestres complets qualifiés. Les seuils de couverture sont 80 % des lignes, 80 % des séances XPAR, 40 séances minimum et semestre complet. 2018 est en burn-in ; 2019H1, 2021H1 et 2024H1 restent bloqués, 2026H2 partiel. Qualification des données uniquement, sans labels ou performance ML ; le gate semestre hors ligne n'est pas un signal PIT. Aucun benchmark ajouté à ce stade. Le prochain lot est le profil relatif au benchmark, comparé sur un support commun.

**Sprint 7-A réalisé le 3 octobre 2026.** Le [panel price-only et dictionnaire](sprint_7a_panel_features_price_only.md) est produit avec `GO_7A_RESEARCH_PANEL` et reconstruction identique. Il conserve 170 046 observations sur 168 titres, 18 features et leurs masques ; 146 799 lignes disposent du noyau à 20 séances, 38 456 des 18 features, et 35 080 sont complètes dans une cross-section d'au moins 20 titres. Les fenêtres longues ont une couverture historique très limitée ; les années 2019–2021 n'ont aucune ligne prête selon ce masque complet. Le GO porte sur la construction traçable du panel, pas sur un walk-forward complet ni sur sa prédictivité. Aucune écriture SQL, cible ou entraînement. Benchmark/secteurs absents du profil 7-A. Voir aussi la [couverture de l'univers](couverture_univers_et_exclusions.md).

**Objectif.** Produire un panel prédictif traçable sans importer les hypothèses US/CN.

**Travaux.** Profils FR séparés `price_only`, `price_market_sector`, puis profils événementiels optionnels. Pour chaque feature : formule, unité, fenêtre en séances, source, heure `available_at`, taux de manquants, comportement en suspension/split et preuve d'absence de futur. Candidats initiaux : rendements/volatilité/ATR/range, gap, momentum/reversal, volume/turnover, relatif au benchmark FR et au secteur. `target_excess_vs_spy`, VIX/MOVE US et paramètres de score US restent désactivés sauf hypothèse cross-asset spécifique pré-enregistrée. Réutiliser la mécanique de panel CN, pas ses noms/règles de marché. Versionner le profil, tester l'égalité d'un panel reconstruit deux fois et la neutralisation sectorielle sans données futures.

**Gate GO.** Taux de couverture/minimum d'historique publiés par feature, PIT prouvé, aucune feature US implicite et golden de panel stable.

### Sprint 8 — Labels Oracle et D1/D10 France

**Sprint 8-B réalisé le 3 octobre 2026.** La [revue des chemins et supports](sprint_8b_revue_chemins_et_support_folds.md) contrôle les clés, disponibilités, maturités et cross-sections après masques. Seuls les folds H5 prix-only 4/5/6 satisfont les gates de support sur leurs trois phases ; aucun fold complet H10/H20 ou benchmark. Dossier de 325 chemins développement (aucune sélection par rendements 2026), zéro split fournisseur dans l'échantillon, 37 cas dividendes et 58 grands mouvements à documenter. Deux reconstructions identiques, 185 tests ciblés passants. Les réserves PIT, radiés et économiques persistent ; aucun entraînement effectué. Un éventuel pilote Sprint 9 doit rester H5 prix-only recherche-only sur le support admis, sans prétendre une validation globale 2019–2026.

**Sprint 8-A réalisé le 3 octobre 2026, GO limité labels bruts de recherche.** Le [contrat labels et évaluation](sprint_8a_labels_et_contrat_evaluation.md) produit H5/H10/H20 depuis l'ouverture de décision J vers la clôture J+H, disponibles J+H+1. Sur 510 138 lignes : 462 047 chemins valides, 44 709 censurés, 3 382 immatures ; 454 506 labels Oracle et 454 303 déciles connus. Cross-section ≥20 et couverture ≥80 %, égalités de frontière censurées. Huit folds chronologiques proposés, sans training ; supports bruts seulement, confirmation 2026 séparée. Reconstruction identique et 176 tests ciblés passants. Réserves : cinq radiés et 86 observations par horizon seulement, prix bruts sans règlement/corporate actions économiques validés, revue humaine encore requise et disponibilité recherche J+1. **Sprint 8 complet non clos ; aucune autorisation d'entraînement économique ou live.**

**Objectif.** Définir correctement les cibles avant de lancer un modèle.

**Travaux.** Pour H5/H10/H20 au départ (H15 option à tester séparément), calculer les rendements futurs économiques et l'amplitude avec conventions d'entrée/sortie explicites : décision à J, premier prix réellement accessible pour l'entrée, sortie à `J+H` sessions, corporate actions, suspensions et radiations. Calculer D1 et D10 uniquement sur la cross-section FR éligible de la date ; enregistrer dénominateur, effectifs des tails, règles de tie, poids et masques de censure. Le label Oracle amplitude TOP20 peut coexister avec le label direction D1/D10, mais ils sont distincts. Empêcher labels immatures en fin d'historique ; embargo/purge d'au moins l'horizon plus la latence utile dans le walk-forward. Audit manuel de journées extrêmes, splits et marchés baissiers. Publier fréquence des labels par date, année, secteur et taille.

**Gate GO.** Recalcul indépendant des labels sur un échantillon, pas de fuite et pas de décile lorsque le dénominateur est insuffisant. **Aucun entraînement** tant que le gate est rouge.

### Sprint 9 — Oracle Extreme France : baseline amplitude

**Objectif.** Savoir si l'amplitude extrême est prédictible hors échantillon sur Paris.

**Travaux.** Baselines simples (volatilité/ATR, mouvement passé, ranking mécanique) puis modèles Oracle avec profils du Sprint 7. Walk-forward chronologique purgé/embargué, folds et éligibilité fixes, sélection champion sans regarder le test final. Évaluer par horizon H5/H10/H20 : precision/recall TOP20, lift contre base rate, AUC/PR-AUC lorsque pertinent, calibration/fiabilité, couverture de tous les jours, stabilité par année/régime/taille/secteur et sensibilité aux radiés. Comparer prix-only, benchmark/secteur et éventuellement données événementielles **uniquement après** baseline figée. Conserver manifeste du modèle, features, calibration, folds, provenance et métadonnées de serving. Aucune règle LONG n'est inférée de l'amplitude.

**Gate GO recherche.** Gain OOS reproductible et non concentré sur quelques titres/folds ; confirmation finale intacte. Sinon Oracle FR reste exploratoire et le programme directionnel conditionnel n'est pas promu.

### Sprint 10 — D1/D10, ranking conditionnel et abstention

**Objectif.** Mesurer la direction **conditionnellement aux signaux Oracle**, et non réutiliser sans preuve les modèles Per-Symbol US.

**Travaux.** Comparer Oracle seul, heuristiques simples, modèle mutualisé, ranking au sein des candidats Oracle et, uniquement si support suffisant, modèle par titre/secteur. Les scores OOF Oracle qui entraînent la direction doivent eux-mêmes être OOF ; jamais des sorties du modèle ajusté sur la même cible/date. Mesurer `precision(D10 | Oracle TOP20)`, `precision(D1 | Oracle TOP20)`, AUC pairwise, IC, spread de rangs, rendements H, courbes de fiabilité, stabilité par semestre et sens. Politique `LONG / SHORT / abstention` distincte du classement ; les seuils sont choisis sur validation puis gelés. Comparer les performances sur tout l'univers éligible et sur le seul sous-ensemble de positions servables ; faire des contrôles de concentration par symbole/secteur.

**Gate GO.** Un signal stable sur plusieurs folds et un OOS final réellement non consulté, avec effectifs et incertitude ; un IC proche de zéro ou une amélioration dépendant d'un semestre = NO_GO directionnel, même si F1 global semble bon.

### Sprint 11 — Données événementielles et PIT directionnel FR

**Objectif.** Tester seulement les familles de données susceptibles d'apporter un signal supplémentaire après un contrat PIT solide.

**Sous-projets indépendants.** (1) AMF : import historique des positions courtes *publiques* par ISIN, dates de position/publication distinctes, censure du seuil, absence = `NOT_OBSERVED`; no short-volume proxy. (2) DILA : métadonnées + documents versionnés/hashés, correspondance ISIN et heure de disponibilité vérifiée, types d'annonce. (3) Guidance : extraction *ancienne valeur/nouvelle valeur*, métrique, unité, période, périmètre et citation/page, contrôles humains et état `NON_COMPARABLE`. Le POC 120 émetteurs a trouvé 4 paires comparables parmi 12 PDF présélectionnés : cela justifie un parseur supervisé, **pas** un signal prêt à trader. (4) INPI/RNE/fondamentaux si calendrier de publication exploitable. (5) Consensus/borrow/quotes/auction/options uniquement si historique légalement accessible et horodaté est acquis ; un snapshot collecté aujourd'hui n'est pas un backfill PIT de 2016.

**Évaluation.** Baseline Oracle/price gelée, ajout *un groupe à la fois*, puis petit ensemble si gains OOF; couverture, biais de sélection et amélioration **incrémentale** par côté LONG/SHORT. Conserver avis négatifs. **Gate GO.** Les données ont lineage/licence/PIT et l'amélioration traverse les années et coûts ; sinon la collecte peut rester prospective sans feature de serving.

### Sprint 12 — Contrat d'exécution simulée et coûts français

**Objectif.** Traduire un score en trade possible, sans supposer le lifecycle US ou les règles CN.

**Travaux.** Contrat versionné `config/markets/fr_execution_*.yaml` : entrée au prochain prix effectivement accessible (pas la clôture du signal), spread/slippage/commission et liquidité en EUR, tailles et arrondis selon instrument/courtier, calendrier XPAR, gaps, suspensions, opérations sur titres et delistings. Prévoir facture et taxes françaises **par instrument et date**, après vérification réglementaire et de la liste applicable ; ne pas hardcoder un taux unique ou taxer chaque action. Pour shorts de recherche, modéliser borrow/éligibilité/recalls et produire une branche `UNEXECUTABLE` si les données manquent. Documenter stops, TP, trailing, time stop et résolution intrabar ; ne pas importer par défaut des paramètres US gelés pour ce marché. Définir clairement base EUR, equity, notionnel et exposition brute/nette ; si comparaison globale multi-devises, FX PIT explicite.

**Tests.** Cas gagnant/perdant, ouverture en gap, demi-séance, split/dividende, suspension jusqu'au-delà de H, absence de prix fill, taxe applicable/non applicable, frais nuls vs plausibles, courtier indisponible. **Gate GO.** Pas de fill impossible ou de coût silencieusement nul ; parité entre replay de recherche et moteur de backtest FR.

### Sprint 13 — Validation économique gelée et revue de décision

**Objectif.** Déterminer si la politique apporte une valeur *nette* et résistante, pas seulement un bon métrique ML.

**Travaux.** Rejouer Oracle pur, sélection directionnelle, abstention, benchmark FR et contrôles naïfs avec exactement le même univers/calendrier/coûts. Rapporter PnL net, Sharpe, drawdown, exposition, turnover, capacité, nombre de trades, gagnants/perdants, coûts décomposés, répartition par année/semestre et scénario de frais/spread ×2. Tests de sensibilité : portefeuille LONG-only, petite/moyenne capitalisation, secteurs, 1–2 titres dominants, retards d'entrée, trous de données, segments Growth vs marché réglementé. Geler **avant** la dernière confirmation les seuils/horizons/seeds/features ; ne pas choisir ex post le meilleur sous-ensemble. Audit PnL attribué à sélection, direction, lifecycle et frais. Interdire conclusion positive si la comparaison dépend d'un univers survivant ou d'un benchmark inadapté.

**Décision.** `GO_RESEARCH_ONLY` si amplitude robuste mais direction non démontrée ; `GO_SHADOW` uniquement si économie et qualité passent ; `NO_GO` pour une politique fragile. **Gate.** Rapport signé, sorties OOF et confirmation conservées, aucune activation live.

## 7. Sprints application, opérations et exécution optionnelle

### Sprint 14 — IHM et CLI France en mode recherche

**Objectif.** Rendre le parcours FR utilisable dans l'application sans qu'un sélecteur visuel ne lance accidentellement une commande US.

**Travaux.** Ajouter FR aux sélecteurs Pipeline, Diagnostic ML, Backtest et page Batch via une entrée « France — recherche uniquement ». Afficher base `alpha_trade_fr`, EUR, XPAR, univers, benchmark, fournisseur/version, horizon Oracle, règles de coûts, période et manifest. Commandes FR spécifiques ou adaptateurs à contrat partagé ; ne pas réemployer une CLI US avec le seul libellé changé. L'IHM bloque les boutons de paper/live, signale les données ou modèles manquants et ne mélange pas les historiques de runs. Les écrans de progression affichent logs et jalons (ingestion, folds, replay), pas seulement « en cours ». Les exports et téléchargements portent clairement `FR_EQ` et la devise. Tester que les pages US/CN et leurs valeurs par défaut sont inchangées.

**Gate GO.** Démo de bout en bout FR recherche sur un petit univers, résultat retrouvé en IHM, aucune route de broker possible, non-régression UI US/CN.

### Sprint 15 — Batchs prospectifs, surveillance, sauvegarde et restauration

**Objectif.** Maintenir les données FR à jour et auditables une fois l'historique qualifié.

**Configuration.** Créer `batch_fr.yaml`, séparé de `batch.yaml` et `batch_cn.yaml`, avec `market_code=FR_EQ`, `database_alias=fr_primary`, fournisseur, licence, priorité, calendrier XPAR, timezone `Europe/Paris`, fenêtre de rattrapage, cadence, politique d'upsert/version, quotas et alertes. Étendre la page Batch pour trois catalogues avec détection des doublons. Les launchers affichent demandé/reçu/persisté/échoué/alertes, clôturent leurs runs sur exception, notifications mail/Telegram et statut de fraîcheur. Installer/désinstaller uniquement les batches FR explicitement actifs. Aucun batch France ne lit `config/univers_batch` US par défaut.

**Catalogue initial à planifier** (activer seulement après la source qualifiée) :

| Famille FR | Sources pressenties / dépendance | Politique de collecte | Priorité |
| --- | --- | --- | --- |
| Master / symboles / statuts | Référence cotation Euronext ou source validée | Snapshot versionné, changements et radiation ; backfill historique distinct | P0 |
| Sessions XPAR | Calendrier officiel / contrôles ponctuels | Mise à jour anticipée, exceptions et revalidation | P0 |
| Barres EOD + corporate actions | Fournisseur retenu Sprint 3 | J−N→J si permis ; corrections/versions, pas de doublon canonique | P0 |
| Qualité PIT | Tables ci-dessus | Contrôles de couverture, fraîcheur, doublon, OHLC, actions ; ne produit pas de données marché | P0 |
| AMF shorts publics | Publication AMF officielle | Import historique puis incrémental, `available_at` prudent | P1 |
| DILA annonces / pièces | INFO-FINANCIERE | Métadonnées et pièces hashées ; limites de quota, erreurs de PDF visibles | P1 |
| Fondamentaux et secteurs | INPI ou source qualifiée | Dates de publication et versions | P2 |
| Consensus/borrow/enchères/options | Aucun historique bas coût confirmé | **Dormant** tant que fournisseur/PIT/licence non validés | P3 |
| Backup base/artefacts FR | `alpha_trade_fr`, `artifacts/fr` | Rétention paramétrée, test régulier de restauration | P0 ops |

Les horaires doivent être déterminés *après* vérification de l'heure de publication réelle, des jours XPAR et des bascules heure d'été ; pas de copier-coller de l'horaire NYSE. Pour un flux snapshot non reconstructible, prévoir un second passage **conditionnel** qui saute si le premier a réussi. Pour un flux J−N/J idempotent, un rattrapage par fenêtre suffit. Mesurer backlog, latence et coût API ; conserver raw payload seulement selon licence et rétention autorisées.

**Gate GO.** Une semaine de collecte vérifiable, deux passages sans doublon métier, arrêt brutal puis reprise, notifications d'échec avec vrais compteurs, backup restauré dans une base de test. Ne pas déclencher FR en masse avant d'avoir qualifié les quotas.

### Sprint 16 — Prédiction FR et shadow prospectif

**Objectif.** Prouver que le modèle retenu peut servir sans accès au futur et sans ordre réel.

**Travaux.** Manifeste FR avec modèle/feature/label/source/horizon et univers servable ; contrôle d'éligibilité de chaque instrument avant prédiction ; prédiction incrémentale par séance et upsert idempotent dans `alpha_trade_fr`. Journaliser Oracle TOP20 avant direction, probas directionnelles/calibration, abstention, motifs de rejet et couverture. Reproduire une date historique en simulation PIT puis comparer au shadow prospectif lorsque maturité des labels atteinte ; aucun re-fit caché. Surveiller dérive des features, fréquence de signaux, missingness, couverture et performance réalisée après H sessions ; un signal passé sans données n'est pas synthétisé. Désactiver automatiquement le serving si schéma, fraîcheur, modèle ou marché incohérents.

**Gate GO.** Traçabilité signal→donnée→modèle→décision, reproductibilité du run, maturité des labels respectée et au moins une fenêtre prospective suffisante selon protocole pré-enregistré. Shadow n'émet aucun ordre.

### Sprint 17 — Courtier France et paper : conditionnel, hors POC historique

**Prérequis.** Décision utilisateur sur un courtier/API disponible pour XPAR ; contrat commercial, droits de données, ouverture de compte, commissions et ordres vérifiés. Ne pas imposer IBKR, déjà écarté par préférence utilisateur pour un autre POC. Sans courtier, conserver `BLOCKED_BROKER` et s'arrêter au shadow.

**Travaux si débloqué.** Implémenter un adaptateur qui satisfait le port du `BrokerRouter` (soumission, statut, annulation, positions, compte, marché ouvert, protections), avec identités ISIN/MIC et non ticker seul. Séparer clés et comptes FR/US, vérifier devise, tailles/minimums, ordre d'ouverture, partial fills, corporate actions, échecs réseau et réconciliation du lendemain. Simuler puis paper des ordres LONG seulement ; le short exige preuve supplémentaire d'emprunt et de disponibilité par titre. Kill switch et limites notional/exposition, clôture opérationnelle et alertes indépendantes du signal ML. Tests de concurrence et de duplicate order idempotency.

**Gate GO paper.** Parité signal→ordre→fill→position→compte et aucune route d'ordre vers US/CN par erreur ; incidents et rollback testés. Ceci n'est toujours pas un GO live.

### Sprint 18 — Canary live et exploitation durable : optionnel

**Prérequis.** Gates G0–G5 verts, approbation explicite du propriétaire, bilan paper, profil de risque/capital autorisé, conformité et flux data licenciés.

**Travaux.** Canary taille très limitée, limites quotidiennes, blocage si données tardives ou ordre non réconcilié, kill switch, revue humaine des premières séances, audit des coûts réels vs backtest, procédure de désactivation par marché sans affecter US/CN. Documenter incidents, reprise, changement de modèle, restauration DB, rotation secrets, contrôle des accès et alertes. Ne jamais promouvoir automatiquement un champion ML en live.

**Gate GO live.** Sign-off technique, données, risques et utilisateur ; sinon retour shadow/paper sans toucher aux bases historiques.

## 8. Matrice des fichiers et schémas à produire

Ce sont des **cibles proposées**, à valider par l'inventaire du Sprint 0, pas la preuve qu'elles existent déjà.

| Famille | Cibles probables | Contrat attendu |
| --- | --- | --- |
| Configuration marché | `config/markets/market_fr.yaml`, `config_fr.yaml`, `config/databases.yaml` | `FR_EQ`/`fr_primary`, EUR/XPAR, live OFF, credentials FR dédiés |
| Configuration jobs | `batch_fr.yaml`, launchers Windows FR, `ihm/services/batch_management.py` | Catalogue séparé, installation active-only, statuts et notification fiables |
| Migrations/SQL | `alembic_fr.ini`, `alembic_fr/versions/`, `database/sql/fr/` | Révisions exclusives à `alpha_trade_fr`, SQL de référence synchronisé |
| Acquisition et qualité | `service/fr/` ou services existants market-aware, `dataIntegrityEngine/fr_*` | Raw/staging/canonique, lineage, reprise, contrôle fournisseur |
| Univers/temps | `common/market_context.py`, `common/market_calendar.py`, `database/router.py` | Identité/venue, XPAR sessions, PIT, fail-closed |
| Recherche ML | `modelFactory/fr_*`, `config/features_fr/`, `artifacts/fr/` | Panels, labels, WF, manifests, aucun modèle US/CN implicite |
| Backtest et coûts | `backtesting/` + profils d'exécution FR | Cash EUR, fills XPAR, corporate actions et taxes datées |
| IHM | `ihm/services/fr_research_market.py` ou service transversal, pages Pipeline/Diagnostic/Backtest/Batch | Vue FR sûre, progression, monnaie et preuve du run |
| Exécution future | `execution_engine/broker_router.py` et adaptateur FR distinct | Fail-closed tant qu'aucun courtier approuvé |
| Tests/docs | `tests/test_fr_*`, `doc/fr/` | DB routing, PIT, split, labels, backtest, UI et manuel opérateur |

## 9. Registre de risques et décisions à ne pas escamoter

| Risque | Preuve à demander avant GO |
| --- | --- |
| Couverture biaisée des radiés | Inventaire des cotations à date et taux des radiés dans le panel, pas seulement titres actuels |
| Ajustements de prix ambigus | Comparaison source indépendante, cas split/dividende/droit, prix de fill brut conservé |
| ISIN unique mais plusieurs lignes de cotation | ISIN + MIC + validité + devise et `instrument_id` explicite |
| AMF « aucun short » interprété comme zéro | État censuré/non observé, publication vs position, aucune rétroprojection |
| DILA PDF/changement d'API | Hash, version brute, disponibilité, contrôle manuel et classe non comparable |
| Taxes ou frais FR sous-estimés | Règles datées et instrumentées, facture courtier/sensibilité de coûts |
| Euronext Growth traité comme XPAR réglementé | Segment et règles distincts, validation du fournisseur et du backtest |
| Labels D1/D10 sur trop peu de titres | Dénominateur, support minimal et jours exclus publiés |
| Tests multiples sur le même OOS | Pré-enregistrement, folds/embargo, confirmation finale non consultée |
| Mélange des trois bases ou artefacts | Router/permissions, prefix run, tests de mauvaises routes, sauvegardes séparées |
| « Gratuit » sans droits de stockage/trading | Contrat/licence et quota réellement vérifiés sur le compte utilisé |

## 10. Première séquence d'exécution recommandée

Commencer par **Sprints 0 → 1 → 2** : ils sécurisent la base `alpha_trade_fr` vide sans acheter de données ni lancer de modèle. Puis **3 → 4 → 5 → 6** construisent la vérité historique ; si l'historique radié/PIT échoue, on arrête le ML plutôt que d'optimiser un jeu biaisé. Ensuite **7 → 8 → 9** testent l'amplitude Oracle ; **10 et 11** recherchent une direction incrémentale, avec abstention possible. Le backtest et les coûts (**12–13**) décident si l'application peut dépasser la recherche. L'IHM et les batchs (**14–15**) industrialisent uniquement les branches dont les sources sont qualifiées ; le shadow (**16**) précède toute discussion paper/live (**17–18**).

Les références externes à revalider à la date d'exécution sont : [calendrier officiel Euronext](https://www.euronext.com/en/trading/trading-hours-holidays), [jeu AMF des positions courtes publiques](https://www.data.gouv.fr/datasets/historique-des-positions-courtes-nettes-sur-actions-rendues-publiques-depuis-le-1er-novembre-2012), [API DILA INFO-FINANCIERE](https://www.data.gouv.fr/dataservices/api-info-financiere) et [catalogue Euronext corporate actions](https://live.euronext.com/en/datashop/corporate-actions). Leurs conditions/prix peuvent évoluer : ce planning ne préjuge pas des droits futurs.
