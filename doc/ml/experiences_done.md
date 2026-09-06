# Registre des expériences ML réalisées

## Objet et règle de lecture

Ce document est l'index central des expériences ML et des recherches directement
liées à la sélection Oracle, à l'amplitude, à la direction et à leur
monétisation. Il doit être complété après chaque nouvelle campagne, y compris
lorsque son résultat est négatif.

Les documents historiques décrivent le protocole et les résultats observés à
leur date. Le code source, les contrats d'artefacts et les prédictions OOF restent
les sources de vérité pour reproduire une expérience. Un `GO_RESEARCH` autorise
une étape de confirmation ; il n'autorise jamais automatiquement le serving.

### États employés

| État | Signification |
|---|---|
| `GO` | gates de l'étape franchis ; la portée exacte est précisée |
| `GO_RESEARCH` | signal à confirmer, non déployable |
| `WEAK_SIGNAL` | information faible ou instable, sans promotion |
| `NO_GO` | hypothèse rejetée dans le contrat testé |
| `INCONCLUSIVE` | données, couverture ou période insuffisantes |
| `IN_PROGRESS` | campagne en cours, aucune conclusion définitive |
| `PROPOSED` | protocole préparé mais non exécuté |

## Résumé décisionnel actuel

1. **Oracle Extreme détecte réellement l'amplitude** : E6-A passe ses six
   gates OOF avec une relation monotone entre score et excursion future.
2. **La direction reste non résolue** : les formulations statiques,
   per-symbol, mutualisées, pairwise, path-aware, first-touch, régime et
   screener n'ont pas produit un avantage LONG/SHORT stable.
3. **Le long straddle est rejeté, y compris avec DTE adapté à l'horizon** :
   E6-B2 reste négatif à H3/H5/H10/H20. Les moyennes vont de `-14,39 %` à
   `-29,68 %`, les médianes sont toutes négatives et seulement 0 à 2 dates sur
   8 sont positives selon l'horizon.
4. **Aucune famille Eroya testée n'est promue**. Quelques effets descriptifs
   existent, mais pas de gain directionnel Walk-Forward suffisamment stable.
5. **La surface Options directionnelle 45 DTE est rejetée** : aucune feature ne
   passe les gates préfixés. Les deux effets descriptifs H10/H20 sont instables
   et défavorables au SHORT ; le volume historique est non testable.
6. **Temporal D1/D10 V2 est en cours** sur Dataset A : 399 symboles, fenêtres
   N=3/5/10, représentations T0/T1/T2 et modèles Logistic/CatBoost/PairLogit.
   Dataset B/C reste conditionné au franchissement des gates Dataset A.

## Campagnes directionnelles récentes après Oracle

| ID | Expérience | Population/cible | Résultat essentiel | État | Documentation |
|---|---|---|---|---|---|
| D0 | Bundle Oracle + deux modèles Per-Symbol | Oracle Extreme puis branches ternaires LONG et SHORT par ticker | Architecture entraînement/prédiction/backtest rendue cohérente, mais la direction per-symbol conditionnelle n'a pas généralisé à 2026H1 | `NO_GO` ML pour le batch étudié ; capacité technique conservée | [Bundle Oracle + Per-Symbol](per_symbol/07_bundle_oracle_long_short.md) |
| D1 | Classifieur mutualisé D1/D10 | D1 contre D10 dans Oracle TOP20 OOF | Sans contexte : AUC 0,503 et IC quotidien +0,004 ; contexte symbole/secteur dégrade | `NO_GO` | [Modèle mutualisé](shared_directional_oracle_events.md#campagne-initiale-du-5-septembre-2026) |
| D1-P | Ranker pairwise D1/D10 | PairLogit groupé par date | AUC 0,500, IC +0,006 ; faible purification instable | `NO_GO` | [Objectif pairwise](shared_directional_oracle_events.md#objectif-pairwise) |
| E1 | Rendement signé continu multi-horizons | Rendements H3/H5/H10/H20 dans Oracle TOP20 OOF | IC proche de zéro, signe correct inférieur à 50 %, branche SHORT négative | `NO_GO` | [E1](shared_directional_oracle_events.md#e1--rendement-signé-continu-multi-horizons) |
| E2 | Deux probabilités indépendantes | `P(Hx >= +3%)` et `P(Hx <= -3%)` | SHORT rejeté partout ; petit signal LONG H3, AUC moyenne 0,544 et 9/9 folds > 0,50, mais probabilités mal calibrées | `GO_RESEARCH` LONG H3 uniquement | [E2](shared_directional_oracle_events.md#e2--deux-probabilités-directionnelles-indépendantes) |
| E2-B | Calibration imbriquée et confirmation LONG H3 | Platt sur validation de chaque fold, test OOF puis confirmation 2026H1 | Confirmation AUC 0,536 mais aucun lift top10 suffisant ; gates de confirmation et développement non franchis | `NO_GO` | [E2-B](shared_directional_oracle_events.md#e2-b--confirmation-long-h3-avec-calibration-imbriquée) |
| E3-A | Rentabilité path-aware binaire | Replay LONG et SHORT séparé, stop 2,5 ATR, TP 3 ATR/7 %, H20 | LONG AUC moyenne 0,541 mais lift économique -0,064 point ; SHORT AUC 0,508 et top10 -0,624 % | `NO_GO` | [E3](shared_directional_oracle_events.md#e3--deux-têtes-de-rentabilité-conditionnelles-au-chemin) |
| E3-A2 | Utilité économique path-aware | Rendement net prédit moins pénalité de perte extrême | IC fold LONG +0,009, SHORT -0,010 ; aucun côté ne passe les gates | `NO_GO` | [E3-A2](path_aware_economic_utility.md) |
| E3-R | Veto de risque path-aware | Rejeter les événements au risque extrême prévu | Réduit certains risques mais conflit avec la sélection de tête ; stabilité insuffisante | `NO_GO` production | [E3-R](path_risk_veto.md) |
| E3-D | Direction par asymétrie du tail-risk | Comparaison du risque prévu LONG contre SHORT | Décision correcte 49,9 %, lift négatif, aucun avantage au meilleur côté statique | `NO_GO` définitif pour cette formulation | [E3-D](path_risk_direction.md) |
| E4 | Première barrière symétrique touchée, quatre classes | `UP_FIRST`, `DOWN_FIRST`, `AMBIGUOUS`, `NO_TOUCH` | Surabstention et absence d'avantage directionnel stable | `NO_GO` | [E4](first_touch_directional.md) |
| E4-B | Première barrière, contrôle binaire | `UP_FIRST` contre `DOWN_FIRST`, cas ambigus retirés | AUC fold 0,501 ; couverture 4,10 %, précision 41,09 %, rendement -2,36 % | `NO_GO` | [E4-B](first_touch_binary.md) |
| E5 | Direction quotidienne du régime Oracle | Choisir un côté commun pour tout le panier du jour | Ridge Spearman 0,000 ; CatBoost -0,008 ; aucune stabilité exploitable | `NO_GO` | [E5](oracle_daily_regime_direction.md) |
| R1 | Ranker conditionnel au TOP20 Oracle | Ranking de rendement réel uniquement dans le pool Oracle | H3 IC +0,0136 ; H20 +0,0266, mais seulement 5/9 folds stables à H20 et Oracle seul reste meilleur LONG | `NO_GO` | [Ranker conditionnel](conditional_oracle_ranker.md) |
| C1 | Consensus des modèles OOF existants | Moyenne équipondérée de rangs quotidiens, 2 à 7 familles selon H3/H5/H10/H20, sans réentraînement ni optimisation | IC -0,0014 à +0,0118, inférieur au meilleur composant ; SHORT signé négatif partout ; unanimité et régime E5 ne sauvent pas la direction | `NO_GO` | [Audit de consensus OOF](oof_consensus_audit.md) |
| T-V2-A | Temporal D1/D10 V2 — Dataset A | État J contre trajectoires `[J-N,...,J]`, N=3/5/10, Logistic/CatBoost/PairLogit, labels H20 autoritatifs | Campagne principale locale lancée sur 399 symboles ; 21 variantes avec reprise par artefact | `IN_PROGRESS` | [Temporal D1/D10 V2](temporal_d1d10_v2.md) |
| S1 | Règles screener PIT post-Oracle | Signaux screener LONG/SHORT H3/H10/H20 | Couverture fraîche 10,44 %, meilleurs effets instables ; aucun gate LONG/SHORT | `NO_GO_PREDICTIVE` | [Screener post-Oracle](screener_post_oracle.md) |
| S1-D | Recontrôle screener sur panel dense | Six signaux quotidiens recalculés sur tout le pool | Couverture réparée mais verdict prédictif inchangé | `NO_GO_PREDICTIVE` | [Panel dense](panel_screener_dense.md), [résultat](screener_post_oracle.md#source-dense-recommandée) |

## Campagnes directionnelles antérieures retrouvées dans les archives ML

Ces campagnes précèdent la série E1–E6. Elles sont importantes car plusieurs
hypothèses récentes en sont des reformulations. Elles ne doivent pas être
relancées sans information nouvelle.

| ID historique | Expérience | Résultat essentiel | État | Documentation |
|---|---|---|---|---|
| GD-H20-V1 | GlobalDirection binaire D1/D10 | Modèle partagé avec features directionnelles minimales ; purification non monotone, seulement 2/3 folds favorables | `NO_GO` | [GlobalDirection H20](../experiences/archives_recherche/global_direction_h20.md#v1-binaire-seul-2026-08-26-premier-run) |
| GD-H20-C1/C2/C3 | Cibles binaire, ordinale et rank | D1 parfois réduit mais D10 non monotone ; rendement inférieur aux baselines | `NO_GO` intermédiaire | [Comparaison C1/C2/C3](../experiences/archives_recherche/global_direction_h20.md#c1-binaire--c2-ordinal--c3-rank-2026-08-26) |
| GD-H20-C4 | Ajout des features sectorielles | Échec des cinq critères pré-enregistrés contre B1 ; BAD5 augmente et GOOD5 diminue | `NO_GO` final | [Test sectoriel](../experiences/archives_recherche/global_direction_h20.md#étude-de-séparabilité-étapes-7-8--2026-08-26) |
| GD-SEP | Séparabilité univariée des features existantes | IC maximum 0,033, AUC direction maximum 0,515 ; les meilleures features expliquent davantage l'amplitude | `NO_GO` | [Séparabilité GlobalDirection](../experiences/archives_recherche/global_direction_h20.md#étude-de-séparabilité-étapes-7-8--2026-08-26) |
| GD-T0 | Audit de couverture temporelle | Historique `stock_scores_history` initialement trop discontinu pour les trajectoires | `INCONCLUSIVE_COVERAGE` initial | [Audit temporel](../experiences/archives_recherche/global_direction_temporal.md#audit-de-couverture-stock_scores_history-2026-08-26--insuffisant) |
| GD-T1 | Backfill PIT puis dérivées J-3/J-5/J-10 | 252 résultats : 0 GO, 108 NO-GO et 144 couvertures insuffisantes ; meilleure AUC environ 0,51 | `NO_GO` | [GlobalDirectionTemporal](../experiences/archives_recherche/global_direction_temporal.md#construire-la-couverture-via-le-backfill-pit-2026-08-27--résultat-inchangé) |
| DDR-1 | Estimates et révisions fondamentales | Données de consensus historiques absentes ; proxies trailing sans signal | `NON_TESTABLE` / `NO_GO` proxies | [DirectionalDataResearch — famille 1](../experiences/archives_recherche/directional_data_research.md#famille-1--estimateearnings-revisions-2026-08-26) |
| DDR-2 | Sentiment news événementiel | IC maximal absolu 0,028, AUC autour de 0,49–0,50 | `NO_GO` | [DirectionalDataResearch — famille 2](../experiences/archives_recherche/directional_data_research.md#famille-2--news-sentiment-événementiel-2026-08-26) |
| DDR-3 | Short interest et short volume historiques | Huit features, AUC maximum 0,501 et IC maximal absolu 0,044 | `NO_GO` | [DirectionalDataResearch — famille 3](../experiences/archives_recherche/directional_data_research.md#famille-3--short-interest--short-volume-2026-08-26) |
| DDR-4 | Options skew et insiders, premier audit | Options absentes de la base historique à cette date ; insiders non exploitables proprement | `NON_TESTABLE` historique | [DirectionalDataResearch — famille 4](../experiences/archives_recherche/directional_data_research.md#famille-4--options-skew--insiders-2026-08-26) |
| DDR-5 | Surprise earnings et distance aux résultats | `earn_surprise_eps_prev` AUC 0,519 et IC +0,034 stable, mais lift de tête nul et AUC sous le gate | `WEAK_SIGNAL`, non promu | [DirectionalDataResearch — famille 5](../experiences/archives_recherche/directional_data_research.md#famille-5--analyst-surprise-earnings--days-to-earnings-2026-08-27) |

Attention : l'ancien indicateur `dir_vs_amp` de
`modelFactory/global_direction/temporal.py` possède une définition amplitude
incorrecte. Les AUC directionnelles des campagnes GD-T restent utilisables, mais
leur comparaison direction/amplitude doit être recalculée avant réutilisation.

## E6 — amplitude Oracle et monétisation direction-neutral

| ID | Expérience | Résultat essentiel | État | Documentation |
|---|---|---|---|---|
| E6-A | Audit OOF de l'amplitude Oracle | 600 717 observations ; TOP20/REST80 environ +86 % d'excursion relative ; Spearman quotidien 0,551 à 0,570 ; 6/6 gates | `GO` amplitude, pas direction | [Audit amplitude](oracle_amplitude_audit.md) |
| E6-B0 | Faisabilité historique des options | Snapshot local insuffisant ; REST historique utilisable, flat files bulk non autorisés dans le trial | `GO` pilote REST ciblé, `NO_GO` bulk actuel | [Faisabilité options](oracle_options_feasibility.md) |
| E6-B1 | Long straddle ATM fixe ~45 DTE | 588 événements, entrée NBBO 67,52 % ; rendement ask→bid négatif à H3/H5/H10/H20, jusqu'à -29,68 % à H20 | `NO_GO` pour 45 DTE fixe | [Résultat E6-B1](oracle_options_feasibility.md#résultat-e6-b1--straddle-45-dte) |
| E6-B2 | DTE adapté à chaque horizon | 588 événements sur 8 dates. Couverture H3/H5/H10/H20 : 43,71/42,35/23,13/41,33 %. Rendement net moyen : -15,76/-14,39/-22,33/-29,68 % ; médiane : -17,49/-19,31/-25,21/-33,22 % ; dates positives : 1/8, 2/8, 0/8, 0/8 | `NO_GO` ; adapter le DTE ne répare pas le straddle long | [Résultat E6-B2](oracle_options_feasibility.md#résultat-e6-b2--dte-adapté-à-lhorizon) |
| E6-B3 | Confirmation options indépendante | Était conditionnée au franchissement des gates E6-B2, qui ont échoué | `NO_GO` pour l'escalade du straddle long ; non exécutée | [Décision E6-B2](oracle_options_feasibility.md#verdict-e6-b2) |

## Nouvelles données directionnelles — campagnes Eroya et autres sources

Toutes ces expériences utilisent ou visent la population Oracle TOP20 OOF. Les
effets exploratoires ne sont pas des règles de production.

| Famille | Données testées | Conclusion actuelle | État | Documentation |
|---|---|---|---|---|
| Short volume | ratio quotidien, variations et niveaux disponibles | Pas de signal directionnel stable H3/H10/H20 | `NO_GO` | [POC Eroya — Short volume](eroya_directional_poc.md#short-volume) |
| Short interest | niveaux et observations PIT disponibles | Fréquence/couverture insuffisante et absence de lift robuste | `NO_GO` | [POC Eroya — Short interest](eroya_directional_poc.md#short-interest) |
| Analyst Insights | scores et observations analystes | Quelques candidats descriptifs, aucune confirmation intacte | `INCONCLUSIVE` | [Analyst Insights](eroya_directional_poc.md#analyst-insights) |
| Analyst revisions Yahoo | révisions et objectifs | Aucun signal durable dans le harnais historique | `NO_GO` | [Synthèse historique des données directionnelles](../experiences/archives_recherche/directional_data_research.md) |
| Form 4 / insiders | transactions d'initiés avec date de dépôt PIT | Effets LONG descriptifs non stables ; ablation modèle ne passe pas les gates | `NO_GO` | [Form 4](eroya_directional_poc.md#résultats-form-4-pit) |
| News/sentiment multi-source | sentiment et événements Eroya comparés aux données internes | Contenu partiellement nouveau mais aucune preuve historique directionnelle | `NO_GO` historique ; collecte prospective possible | [News Eroya](eroya_directional_poc.md#news-multi-source-eroya-versus-sentiment-existant) |
| Earnings/surprise EPS | résultats trimestriels, surprise brute, distance earnings | Surprise brute rejetée comme signal autonome | `NO_GO` | [Earnings](eroya_directional_poc.md#résultats-trimestriels-et-surprises-eps) |
| Dépôts 8-K | catégories structurées et compteurs événementiels | Information descriptive, mais répétitions et concentration interdisent une règle | `INCONCLUSIVE`, non promu | [8-K](eroya_directional_poc.md#dépôts-8-k-structurés) |
| Options directionnelles | ratios de prix, skew approximé, profondeur et volume put/call sur surface 45 DTE | 625 événements/8 dates, 323 surfaces complètes. Aucun gate complet ; meilleur signal H10 IC +0,035/AUC 0,548 mais 2/4 années et lift SHORT négatif. Volume 4 jambes absent partout, donc non testable | `NO_GO` direction ; volume `NON_TESTABLE` | [Protocole et résultat E7](options_directional_poc.md#résultat-de-la-campagne-e7-a) |
| Trades/quotes | microstructure et flux signés | Non testé : volume très lourd et contrat d'heure d'entrée à définir | `PROPOSED` | [Limites options et ticks](eroya_directional_poc.md#options-tradesquotes-et-13f) |
| 13F | positions institutionnelles trimestrielles retardées | Non testé, priorité faible pour H3/H10/H20 | `PROPOSED` faible priorité | [Limites options et ticks](eroya_directional_poc.md#options-tradesquotes-et-13f) |

## Expériences historiques Per-Symbol

| Campagne | Axes testés | Verdict durable | Documentation |
|---|---|---|---|
| S7 — whitelist de features | Réduction contrôlée des features per-symbol, comparaison architecture/champion | Mécanisme conservé, gain OOS rejeté | [S7 Feature whitelist](../experiences/archives_ml/synthese_s7_feature_whitelist_2026-08-18.md) |
| Per-Symbol Directional V2 F0/F1/F2/F3a/F3b | Familles directionnelles, architectures LSTM/LightGBM/CatBoost, champion et stabilité | Aucun gain OOS stable ; `NO_GO` | [Synthèse Per-Symbol V2](../experiences/archives_ml/synthese_per_symbol_v2_2026-08-19.md) |
| Sélection des tickers par F1 LONG/SHORT | Gates par côté, folds valides, listes STRICT et DISCOVERY | Outil de screening disponible ; ne prouve pas la performance portefeuille | [Sélection des candidats](per_symbol/06_selection_candidats_directionnels.md) |
| Entraînement conditionnel aux événements Oracle | Branches LONG/SHORT entraînées dans le bundle sur les événements Oracle | Technique fonctionnelle ; généralisation directionnelle rejetée sur le batch étudié | [Population conditionnelle](per_symbol/07_bundle_oracle_long_short.md#population-dentraînement-conditionnelle--étape-3) |

## Persistance, confirmation prix et filtre DIP

Ces expériences concernent principalement Global Ranking. Elles ne doivent pas
être attribuées à Oracle Extreme par erreur.

| Expérience | Population et résultat | Verdict actuel | Documentation |
|---|---|---|---|
| Persistance + confirmation prix après Oracle TOP10 | Taux GOOD resté pratiquement plat autour de 50,2–50,3 % | `NO_GO` pour Oracle | [Persistent tail price](../experiences/archives_recherche/persistent_tail_price.md#oracle-top10--hypothèse-non-soutenue) |
| Persistance Global Rank TOP10 + hausse | GOOD rate 0,521 → environ 0,556 sur un échantillon viable | Signal historique soutenu, distinct d'Oracle | [Persistent tail price — LONG](../experiences/archives_recherche/persistent_tail_price.md#global-rank-top10-long--hypothèse-soutenue) |
| Persistance Global Rank BOTTOM10 + baisse | GOOD SHORT environ 0,512 → 0,529 | `WEAK_SIGNAL` SHORT | [Persistent tail price — SHORT](../experiences/archives_recherche/persistent_tail_price.md#global-rank-bottom10-short--faible-gain) |
| TOP10 persistant + baisse récente | Rebond observé avec GOOD rate autour de 0,567 | Découverte exploratoire, non assimilable à une direction Oracle | [Inversion TOP10](../experiences/archives_recherche/persistent_tail_price.md#inversion-top10--baisse--signal-le-plus-fort) |
| DIP N4/X2 Global Rank | Filtre DIP puis veto de régime ; +5,5 % en 2025 OOS et +4,3 % en 2026H1 contre baselines négatives | `GO` historique dans son contrat Global Rank ; paramètres gelés | [Persistent TOP10 DIP](../experiences/archives_recherche/persistent_top10_dip.md#phase-3--audit-de-parité-reclaim-validation-oos-et-implémentation-2026-08-27) |
| DIP reclaim R50/R100 | Attendre la reprise consomme le rebond et dégrade D0 | `NO_GO`, garder entrée directe | [Reclaim](../experiences/archives_recherche/persistent_top10_dip.md#32-reclaim-r50r100--no-go) |
| Tiebreaker `dip_quality` | Amélioration mécanique et métriques favorables, mais seulement 18 substitutions OOS | `INCONCLUSIVE_LOW_SAMPLE` | [Tiebreaker DIP](../experiences/archives_recherche/Tiebreaker.md) |
| Smart sector cap | Cap exposition 20 % et hybride count/exposition/corrélation retirent ou ajoutent de mauvais ensembles de trades | C0 count=2 conservé ; C1/C2 `NO_GO` | [Smart sector cap](../experiences/archives_recherche/smart_sector_cap_verdict_2026-08-27.md) |

## Calibration et transformation des scores Oracle

| Expérience | Résultat | Statut | Documentation |
|---|---|---|---|
| Percentile quotidien `rank` | Transformation déterministe, sans cible ni fit ; préserve l'ordre relatif | Contrat adapté au gate percentile | [Calibration Oracle](../experiences/archives_recherche/calibration_oracle_exterme.md#rank--percentile-intra-jour-relatif) |
| Calibration isotonic | Mapping score → fréquence d'extrême ; améliore la sémantique probabiliste mais pas l'AUC ou le classement | Non utilisable en backtest strict sans artefact calibré PIT gelé | [Isotonic](../experiences/archives_recherche/calibration_oracle_exterme.md#isotonic--proba-calibrée-absolue-pav), [contrat actuel](oracle/04_train_walk_forward_et_calibration.md#calibrationcombinaison) |
| Oracle brut `none` | Score OOS brut utilisé lorsque le consommateur reclasse quotidiennement et qu'aucun calibrateur PIT antérieur n'est disponible | Contrat actuel du backtest strict | [Entraînement/calibration Oracle](oracle/04_train_walk_forward_et_calibration.md#calibrationcombinaison) |

## Oracle Extreme — campagnes de construction et d'ablation

| Campagne | Axes testés | Conclusion conservée | Documentation |
|---|---|---|---|
| Oracle historique TOP/BOTTOM | Deux modèles directionnels au-dessus du ranking | Les deux côtés apprenaient surtout une magnitude commune ; architecture remplacée | [Synthèse Oracle](../experiences/oracle_extreme.md) |
| Oracle O0 binaire | `D1 ∪ D10` contre le milieu, sans Global Rank comme entrée | Contrat actuel : magnitude uniquement, gate percentile quotidien | [Concept Oracle](oracle/01_concept_et_architecture.md) |
| Diagnostics hard negatives/confounders | Faux positifs, sévérité, features, fondamentaux, cas catastrophiques | Diagnostics utiles, pas de gate live automatiquement validé | [Diagnostics Oracle](oracle/06_diagnostics_et_historique.md) |
| Ablations Oracle 01–11 | Ranks XS, raw simple, momentum, tendance, volatilité, volume, RSI, régime, transformations et z-scores | Campagne terminée ; résultats à relire via les artefacts avant toute nouvelle sélection | `config/features/oracle/` et [entraînement Oracle](oracle/04_train_walk_forward_et_calibration.md) |
| Combinaisons Oracle 12–14 | Retraits combinés marché/régime, engineered transforms et momentum | Campagne terminée ; aucune promotion ne doit être déduite sans comparaison OOF consolidée | `config/features/oracle/` et [diagnostics Oracle](oracle/06_diagnostics_et_historique.md) |

## Global Ranking et Per-Sector — historique B0 à B44

Les campagnes B0–B44 ont testé les familles de features, backends, objectifs de
ranking, profondeur historique, taille d'univers et volume. Le dossier suivant
contient les rapports détaillés batch par batch :
[campagnes Global Ranking](../experiences/campagnes_global_ranking/README.md).

| Série | Variantes documentées | Documentation |
|---|---|---|
| B0–B3 | baseline, sentiment, scores screener, short score | [B0](<../experiences/campagnes_global_ranking/test/B0 Baseline.md>), [B1](<../experiences/campagnes_global_ranking/test/B1 sentiement.md>), [B2](<../experiences/campagnes_global_ranking/test/B2 scores screnner.md>), [B3](<../experiences/campagnes_global_ranking/test/B3 scores short.md>) |
| B4–B14 | SPY, VIX/VXN/VIX3M/MOVE, fondamentaux, CAPM, macro, historique de scores, secteur et stacking | [B4](<../experiences/campagnes_global_ranking/test/B4 Short + SPY.md>), [B5](<../experiences/campagnes_global_ranking/test/B5 Short + SPY + Vix.md>), [B6](<../experiences/campagnes_global_ranking/test/B6 Short + SPY + Vxn.md>), [B7](<../experiences/campagnes_global_ranking/test/B7 Short + SPY + Vix3m.md>), [B8](<../experiences/campagnes_global_ranking/test/B8 Short + SPY + Move.md>), [B9](<../experiences/campagnes_global_ranking/test/B9 Short + SPY + Fondamentaux.md>), [B10](<../experiences/campagnes_global_ranking/test/B10 Short + SPY + CAPM.md>), [B11](<../experiences/campagnes_global_ranking/test/B11 Short + SPY + Macro.md>), [B12](<../experiences/campagnes_global_ranking/test/B12 Short + SPY + Score histo.md>), [B13](<../experiences/campagnes_global_ranking/test/B13 Short + SPY + sectoriel.md>), [B14](<../experiences/campagnes_global_ranking/test/B14 Short + SPY + stacking.md>) |
| B15–B19 | transformations T1/T2/T3 et profondeur/folds | [B15](<../experiences/campagnes_global_ranking/test/B15 Short + SPY + T1.md>), [B16](<../experiences/campagnes_global_ranking/test/B16 Short + SPY + T2.md>), [B17](<../experiences/campagnes_global_ranking/test/B17 Short + SPY + T3.md>), [B18](<../experiences/campagnes_global_ranking/test/B18 Short + SPY + from 2011 + max 8 slits.md>), [B19](<../experiences/campagnes_global_ranking/test/B19 Short + SPY + from 2011 + max 16 slits.md>) |
| B20–B27 | YetiRank, QueryRMSE, QuerySoftMax, puis variantes CAPM | [B20](<../experiences/campagnes_global_ranking/test/B20 Short + SPY + YetiRank.md>), [B21](<../experiences/campagnes_global_ranking/test/B21 Short + SPY + QueryRMSE.md>), [B22](<../experiences/campagnes_global_ranking/test/B22 Short + SPY + QuerySoftMax.md>), [B25](<../experiences/campagnes_global_ranking/test/B25 Short + SPY + CAPM + YetiRank.md>), [B26](<../experiences/campagnes_global_ranking/test/B26 Short + SPY + CAPM + QueryRMSE.md>), [B27](<../experiences/campagnes_global_ranking/test/B27 Short + SPY + CAPM + QuerySoftMax.md>) |
| B30–B34 | P1–P3, fondamentaux, historique scores, secteur, screener avec YetiRank | [B30](<../experiences/campagnes_global_ranking/test/B30 Short + SPY + YetiRank +  P1-3.md>), [B31](<../experiences/campagnes_global_ranking/test/B31 Short + SPY + Fondamentaux + YetiRank.md>), [B32](<../experiences/campagnes_global_ranking/test/B32 Short + SPY + Score histo + YetiRank.md>), [B33](<../experiences/campagnes_global_ranking/test/B33 Short + SPY + sectoriel + YetiRank.md>), [B34](<../experiences/campagnes_global_ranking/test/B34 scores screnner + YetiRank.md>) |
| B35–B39 | univers 196/300/393 et challenger XGBoost rank | [B35](<../experiences/campagnes_global_ranking/test/B35 B25 + symbols 196.md>), [B36](<../experiences/campagnes_global_ranking/test/B36 B20 + symbols 196.md>), [B37](<../experiences/campagnes_global_ranking/test/B37 B25 + symbols 393.md>), [B38](<../experiences/campagnes_global_ranking/test/B38 B25 avec 300 symblos (parmi les 400).md>), [B39](<../experiences/campagnes_global_ranking/test/B39-B25-XGBoost-rank-ndcg-P3-3.md>) |
| B40–B44 | volume features, configurations B4/B20/B25 et extension train 2024 | [B40](<../experiences/campagnes_global_ranking/test/B40-B4-volume-features-P3-5.md>), [B41](<../experiences/campagnes_global_ranking/test/B41-B25-volume-features-P3-5.md>), [B42](<../experiences/campagnes_global_ranking/test/B42-B20-volume-features-P3-5.md>), [B44](<../experiences/campagnes_global_ranking/test/B44-B41-config-global-only-train-end-2024-12-31.md>) |
| Synthèse Global/Per-Sector | comparaison de tous les horizons, champions, splits, régimes et backtests | [Rapport comparatif](<../experiences/campagnes_global_ranking/test/test_global_per_sector.md>), [synthèse durable](../experiences/global_ranking_et_per_sector.md) |

## Expériences risque, exécution et lifecycle liées à l'interprétation ML

Ces campagnes ne cherchent pas directement D1/D10, mais elles déterminent si un
signal ML observé peut être monétisé sans biais d'exécution.

| Campagne | Conclusion | Documentation |
|---|---|---|
| Audit du backtest historique | Biais pullback et propagation TP découverts puis corrigés ; nécessité de la parité production | [Audit backtest](../experiences/archives_recherche/backtest_audit.md) |
| TP / risk-execution | Plusieurs TP testés ; amélioration locale non confirmée OOS | [Synthèse TP/risk](../experiences/archives_ml/synthese_tp_risk_execution_2026-08-18.md) |
| Time-stop/parité | Différence entre lifecycle de recherche et production mise en évidence | [Synthèse risque/lifecycle](../experiences/risque_execution_lifecycle.md) |
| Drawdown controller B4 | Contrôleur et gates paper validés dans son contrat historique | [B4 paper](../experiences/archives_recherche/c2_b4_breaker_go_paper_2026-08-21.md) |
| Force-close catastrophe | `CLOSE_ALL` et `CLOSE_LONGS` à -8 % rejetés | [E44](../experiences/archives_recherche/b4_force_close_side_attribution.md) |
| Validation/recalibration | Séparation entraînement, calibration, promotion et OOS | [Synthèse validation](../experiences/validation_et_recalibration.md) |

## Pistes préparées mais non encore exécutées

| Priorité actuelle | Piste | Question | Statut | Protocole |
|---:|---|---|---|---|
| 1 | Microstructure proche de l'entrée | Le flux de clôture J, pré-market ou opening range donne-t-il la direction ? | `PROPOSED`, contrat d'exécution à choisir | À formaliser |
| 2 | Modèle temporel multi-horizon | Un apprentissage commun H3/H5/H10/H20 régularise-t-il la direction ? | `PROPOSED`, conditionnel à V2 | À formaliser |
| 3 | Portefeuille relatif | Un spread dollar-neutral peut-il monétiser un faible ranking sans direction absolue ? | `PROPOSED` secondaire | Dérivé du [ranker conditionnel](conditional_oracle_ranker.md) |

## Audit des 49 méthodes de la roadmap professionnelle

Cette section confronte
[la roadmap des méthodes quant](alpha_trade_quant_professional_methods_roadmap.md)
au code et aux expériences réellement présents au 6 septembre 2026. Les états
ont le sens suivant :

- `ACTIF` : méthode intégrée et utilisée dans l'application ou ses harnais ;
- `FAIT_NO_GO` : expérience exécutée, hypothèse non promue ;
- `EN_COURS` : campagne actuellement exécutée ;
- `PARTIEL` : une partie seulement du contrat a été testée ou industrialisée ;
- `À_FAIRE_CONDITIONNEL` : pertinent uniquement si son prérequis passe ;
- `À_FAIRE_PRIORITAIRE` : information nouvelle potentiellement utile ;
- `DIFFÉRÉ` : intérêt possible mais rapport signal/complexité faible maintenant ;
- `À_ÉVITER` : non justifié dans l'état actuel des preuves.

### 1–10 — formulation du signal et trajectoires

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 1 | Tail Classification D1/D10 | `FAIT_NO_GO` statique ; `EN_COURS` temporel | GlobalDirection binaire et le modèle mutualisé statique ont échoué. Temporal V2 reteste uniquement l'information nouvelle de trajectoire. Voir [GlobalDirection](../experiences/archives_recherche/global_direction_h20.md), [shared directional](shared_directional_oracle_events.md) et [Temporal V2](temporal_d1d10_v2.md). |
| 2 | Temporal Feature Engineering | `FAIT_NO_GO` ancien ; `EN_COURS` V2 | L'ancien test sur scores clairsemés n'a donné aucun GO. V2 corrige le contrat avec 27 séries locales denses, N=3/5/10 et T0/T1/T2. Voir [historique temporel](../experiences/archives_recherche/global_direction_temporal.md). |
| 3 | Meta-Labeling | `PARTIEL` | La cascade Oracle → spécialistes LONG/SHORT existe techniquement. L'entraînement directionnel conditionnel Oracle a échoué en généralisation ; le méta-label temporel n'est pas validé. Conserver l'architecture, pas la considérer comme alpha démontré. Voir [bundle](per_symbol/07_bundle_oracle_long_short.md). |
| 4 | Cross-Sectional Ranking | `ACTIF` global ; `FAIT_NO_GO` post-Oracle | Global Ranking est une brique complète. Le ranker restreint au TOP20 Oracle n'a pas franchi les gates ; PairLogit est retesté dans V2 sur les trajectoires. Voir [Global Ranking](global_ranking/README.md) et [ranker conditionnel](conditional_oracle_ranker.md). |
| 5 | Cross-Feature Divergence | `PARTIEL`, `À_FAIRE_CONDITIONNEL` | Plusieurs divergences existent déjà parmi les features EXPERT (`momentum_5_minus_momentum_20`, spread SMA, accélération), et CatBoost apprend des interactions. Une petite ablation dédiée de divergences économiquement motivées reste pertinente seulement si V2 trouve d'abord un signal temporel. |
| 6 | Relative Trajectory | `PARTIEL`, priorité conditionnelle élevée | Les niveaux de force relative, features SPY/secteur et neutralisations existent ; V2 teste leurs deltas/pentes. La vraie trajectoire stock moins secteur à chaque point de la fenêtre n'est pas encore une ablation autonome. À faire après un GO Dataset A, sur les mêmes lignes. |
| 7 | Multi-Horizon Agreement | `PARTIEL`, `À_FAIRE_CONDITIONNEL` | Les features momentum multi-horizons et l'audit de consensus existent, mais pas un test figé de cohérence directionnelle H3/H5/H10/H20 après sélection de N. À ouvrir seulement si V2 montre de l'information. Voir [consensus OOF](oof_consensus_audit.md). |
| 8 | Persistence | `ACTIF` ailleurs ; `EN_COURS` D1/D10 | Persistance Global Rank/DIP déjà étudiée et intégrée dans son propre contrat. V2 inclut la fraction de variations positives sur N pour la polarité D1/D10. Ne pas confondre les deux populations. Voir [DIP historique](../experiences/archives_recherche/persistent_top10_dip.md). |
| 9 | Velocity / Acceleration | `PARTIEL`, `EN_COURS` | Des pentes/accélérations existent dans EXPERT ; V2 construit une définition canonique trainée avec les autres trajectoires. Aucun verdict D1/D10 séparé avant la fin du run. |
| 10 | Change-Point Detection | `DIFFÉRÉ` | Aucun test causal dédié CUSUM/PELT n'a été trouvé. À envisager seulement si V2 montre qu'une dynamique simple existe mais reste mal captée ; sinon ce serait du feature mining supplémentaire. |

### 11–19 — conditionnement, spécialistes et modèles séquentiels

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 11 | Event-Conditioned Models | `PARTIEL` / majoritairement `FAIT_NO_GO` | Earnings, Form 4, news, analystes et 8-K ont été audités. Form 4 et earnings ne passent pas ; 8-K et Analyst Insights restent inconclusifs. Un nouveau modèle conditionné exige une série PIT plus dense ou une source nouvelle. Voir [POC Eroya](eroya_directional_poc.md). |
| 12 | Regime-Conditioned Models | `FAIT_NO_GO` pour la direction | Les régimes sont disponibles comme features et dans le risque. Le modèle directionnel quotidien de régime Oracle n'a produit aucun avantage stable. Ne pas créer maintenant des experts séparés par régime. Voir [E5](oracle_daily_regime_direction.md). |
| 13 | Mixture of Experts | `DIFFÉRÉ` | Aucun ensemble de patterns directionnels validés ne justifie encore un gating model. Requis : au moins deux experts complémentaires ayant chacun un avantage OOF. |
| 14 | Trajectory Clustering | `À_FAIRE_CONDITIONNEL` diagnostique | Non exécuté pour D1/D10. Autorisé uniquement après un signal V2, pour comprendre plusieurs formes de D1/D10 ; pas pour réoptimiser la même période. |
| 15 | Contrastive Learning | `À_ÉVITER` maintenant | Non implémenté et disproportionné sans séparabilité tabulaire préalable. |
| 16 | 1D-CNN / TCN | `À_FAIRE_CONDITIONNEL` | Non exécuté pour la polarité Oracle. À tester seulement si T2 ou une séquence aplatie apporte déjà au moins +0,01 d'AUC same-date contre T0. |
| 17 | LSTM séquentiel | `ACTIF` per-symbol générique ; `À_FAIRE_CONDITIONNEL` D1/D10 | LSTM existe dans ModelFactory, mais cela ne valide pas un LSTM mutualisé de polarité. Challenger seulement après TCN/flattened et GO tabulaire. |
| 18 | Transformer temporel | `À_ÉVITER` | Séquences de 4 à 11 observations et absence actuelle de signal ne justifient ni paramètres ni complexité supplémentaires. |
| 19 | Calibration | `ACTIF`, application conditionnelle | Platt/isotonic/temperature-vector et la gouvernance existent. E2-B a montré qu'une calibration correcte ne sauve pas un ranking faible. Calibrer Temporal uniquement après Dataset C et stabilité du classement. Voir [recalibration](recalibration_et_promotion.md). |

### 20–29 — protocole scientifique et traitement des données

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 20 | Feature Ablation | `ACTIF` et largement `FAIT` | Campagnes Global Ranking B0–B44, Oracle 01–14, Per-Symbol S7/V2 et sources Eroya. Continuer seulement par familles préfixées sur mêmes lignes, pas par suppression opportuniste. |
| 21 | Direction vs Amplitude Audit | `ACTIF` / `FAIT` | E6-A valide l'amplitude Oracle ; tous les harnais directionnels récents séparent rendement signé et amplitude. V2 recalcule correctement tail-vs-middle, contrairement à l'ancien `dir_vs_amp`. Voir [E6-A](oracle_amplitude_audit.md). |
| 22 | Same-Date Evaluation | `ACTIF` | Métrique centrale des modèles mutualisés, rankers, consensus et V2. Elle évite qu'un régime de date soit pris pour une séparation cross-sectionnelle. |
| 23 | Pairwise Ranking | `FAIT_NO_GO` statique ; `EN_COURS` temporel | R1 PairLogit sur le pool Oracle a échoué. V2 compare de nouveau PairLogit aux classifieurs sur les mêmes folds et trajectoires. |
| 24 | Purged Walk-Forward | `ACTIF` | Oracle, Global Ranking, Per-Symbol et recherches partagées utilisent le WF. V2 impose `oracle_available_date < test_start`, donc les targets H20 du train sont connus avant le test. |
| 25 | Embargo / Leakage Controls | `ACTIF` | Assertions de features interdites/futures, garde de disponibilité target, Oracle OOF, preprocessing train-only et contrôles PIT sont présents. La confirmation finale V2 reste déclarée indisponible car 2018–2025 a déjà été observé. |
| 26 | Missingness as Information | `PARTIEL` | `is_filled`, âges de snapshots et âges d'événements existent dans plusieurs datasets. V2 local n'ajoute pas mécaniquement des centaines de flags. À compléter seulement pour les sources irrégulières réellement retenues. |
| 27 | Event Recency | `PARTIEL` / sources testées non promues | Distance aux earnings, récence Form 4/news/événements ont été testées dans les POC correspondants sans signal suffisant. Garder comme contrat standard pour toute nouvelle source événementielle. |
| 28 | Ensemble Models | `ACTIF` pour championnat ; `FAIT_NO_GO` pour consensus directionnel | La sélection de champion LSTM/LightGBM/CatBoost existe. Le consensus OOF des modèles directionnels n'améliore pas le meilleur composant ; ne pas rechercher des poids post-hoc. Voir [C1](oof_consensus_audit.md). |
| 29 | Feature Neutralization | `ACTIF` / `FAIT` | Features SPY/secteur, CAPM et cibles résiduelles ont été testées. Les campagnes Global Ranking montrent leur utilité contextuelle ; les cibles directionnelles résidualisées n'ont pas résolu D1/D10. Voir [campagnes Global](../experiences/campagnes_global_ranking/README.md) et [E1](shared_directional_oracle_events.md). |

### 30–39 — risque, portefeuille et formulations alternatives

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 30 | Risk Overlay | `ACTIF` | Moteur risque/exécution séparé, stops, TP, drawdown, volatilité cible et protections sont implémentés et documentés. Le risque ne doit pas être utilisé pour masquer un signal directionnel absent. Voir [risque/lifecycle](../experiences/risque_execution_lifecycle.md). |
| 31 | Portfolio Constraints | `ACTIF` | Max positions, exposition sectorielle, exposition brute/nette, drawdown et liquidité sont consommés par le backtest/production. Smart sector cap a été testé sans remplacer le cap canonique. |
| 32 | Transaction Cost Awareness | `ACTIF` | Commission, slippage, spread, intérêt de marge et replay d'exécution font partie des contrats canoniques. Les diagnostics ML purs restent avant coûts ; tout GO doit ensuite passer le backtest net. |
| 33 | Probability Thresholding | `FAIT`, non promu | Les seuils 0,55/0,80/0,85/0,90 ont été comparés sur le bundle directionnel ; aucune politique robuste n'en est sortie. Ne pas reprendre un sweep fin sans nouveau modèle validé. |
| 34 | Symbol-Specific Thresholds | `À_ÉVITER` | Les gates de sélection de candidats per-symbol sont des contrôles de qualité, pas des seuils de trading optimisés par ticker. L'échantillon de tails reste trop faible pour cette recherche. |
| 35 | Per-Symbol Fine-Tuning | `FAIT_NO_GO` pour la mission Oracle | Les spécialistes LONG/SHORT et leur population conditionnelle Oracle sont implémentés. L'amélioration développement ne s'est pas généralisée. Capacité technique conservée, hypothèse ML non promue. |
| 36 | Hierarchical Models | `PARTIEL`, `DIFFÉRÉ` | Global, Per-Sector et Per-Symbol existent comme modules distincts, mais pas comme modèle hiérarchique joint avec shrinkage. Inutile avant un signal partagé stable. Voir [Per-Sector](per_sector/README.md). |
| 37 | Survival / Time-to-Event | `PARTIEL`, `FAIT_NO_GO` proche | First-touch, rentabilité path-aware et veto de risque ont étudié le chemin et l'ordre des barrières ; ils ont échoué. Un vrai modèle de durée n'est pas prioritaire tant que H20 reste le contrat. |
| 38 | Régression directe des rendements | `FAIT_NO_GO` | E1 a prédit le rendement signé H3/H5/H10/H20 ; IC proche de zéro et branche SHORT négative. Ne pas relancer sans données nouvelles. |
| 39 | Ordinal Classification | `FAIT_NO_GO` | GlobalDirection ordinal D1/milieu/D10 et objectif rank ont été testés sans battre les baselines. Dataset C V2 sera un audit de scoring du milieu, pas une réouverture opportuniste de cette cible. |

### 40–49 — méthodes avancées, robustesse et données alternatives

| N° | Méthode | État réel | Décision et preuve |
|---:|---|---|---|
| 40 | Multitask Learning | `À_ÉVITER` maintenant | Aucun avantage à remélanger amplitude, direction et rendement après avoir clarifié leurs rôles. Une future tête multi-horizon directionnelle serait une expérience distincte, pas un modèle end-to-end. |
| 41 | Reinforcement Learning | `À_ÉVITER` | Ne résout ni la faiblesse informationnelle D1/D10 ni les problèmes de couverture. |
| 42 | Genetic Programming / Symbolic Search | `À_ÉVITER` | Risque de data mining excessif sur une période déjà largement observée. |
| 43 | SHAP Pattern Discovery | `À_FAIRE_CONDITIONNEL` diagnostique | Feature importance existe dans plusieurs entraînements, mais une analyse SHAP de trajectoires n'est utile qu'après un GO OOF V2. Elle n'est jamais une preuve autonome d'alpha. |
| 44 | Counterfactual Analysis | `PARTIEL` | Des contrefactuels de lifecycle/stops et de risque existent. Aucun contrefactuel directionnel de trajectoire n'est justifié avant un modèle V2 informatif. |
| 45 | Placebo Tests | `PARTIEL`, **reste obligatoire pour V2** | Des placebos ont validé Global Ranking et certains backtests. Le run V2 courant ne contient pas encore son shuffle-label dédié ; ajouter au minimum un contrôle Logistic sur la représentation candidate avant promotion Dataset B. |
| 46 | Bootstrap par Date | `ACTIF` backtest ; **reste obligatoire pour V2** | Le moteur possède des bootstraps trades/blocs. V2 doit encore bootstrapper la différence d'AUC same-date entre N/T2 et T0 avant de sélectionner N ; calculable après les prédictions OOF sans réentraînement. |
| 47 | Stability Selection | `PARTIEL` | Les gates fold/année et ablations par famille existent. La stabilité des rangs d'importance feature par fold n'est pas encore produite dans V2 ; à ajouter seulement pour une variante candidate. |
| 48 | Data Source Incrementality | `FAIT` sur les sources disponibles | Form 4 a eu une ablation modèle, les autres familles ont été comparées sur des populations communes lorsque la couverture le permettait. Aucune source Eroya testée n'est promue. Réouvrir seulement avec une série PIT réellement nouvelle et dense. |
| 49 | Alternative Data Families | `PARTIEL` | Déjà testés : short volume/intérêt, news, analystes, earnings, Form 4, 8-K et surface Options. Restent potentiellement sérieux : microstructure/order flow proche de l'entrée et borrow fee/utilization si historique PIT accessible. Capital flow mérite un audit de source. 13F/institutionnel reste faible priorité pour H3–H20. |

## Pistes encore intéressantes après cet audit

### Priorité P0 — terminer correctement Temporal V2

1. Attendre Dataset A T0/T1/T2 en cours.
2. Si une variante passe les gates, calculer le bootstrap par date de son delta
   d'AUC contre T0.
3. Exécuter un placebo shuffle-label limité à la représentation candidate.
4. Seulement après ces contrôles, ouvrir Dataset B Oracle OOF puis Dataset C.
5. Relative trajectory, divergences et multi-horizon agreement sont des
   ablations de phase 2 : elles restent interdites si Dataset A est `NO_GO`.

### Priorité P1 — information véritablement nouvelle si V2 échoue

1. **Microstructure/order flow aligné sur l'entrée** : déséquilibre trades/quotes
   en clôture J, pré-market ou opening range. Il faut d'abord choisir le cutoff
   de décision et évaluer le volume/coût du backfill.
2. **Borrow fee/utilization/shares available** : piste squeeze/pression short,
   uniquement si une source offre un historique PIT suffisamment dense.
3. **Capital flow signé** : auditer l'existence, la profondeur et la sémantique
   de l'agresseur avant toute collecte.

### Priorité P2 — uniquement après découverte d'un signal stable

- cross-feature divergence contrôlée ;
- trajectoire relative secteur/SPY ;
- cohérence multi-horizon ;
- SHAP et stability selection diagnostiques ;
- séquence aplatie puis TCN/1D-CNN ;
- intégration séparée dans LONG et SHORT, puis calibration et backtest net.

### Faible priorité ou arrêt actuel

- change-point avancé, clustering et mixture of experts sans patterns validés ;
- 13F/institutionnel pour des décisions H3–H20 ;
- LSTM D1/D10 avant TCN et avant preuve tabulaire ;
- Transformer, contrastive learning, multitask end-to-end, RL, genetic
  programming et seuils spécifiques par symbole.

## Procédure de mise à jour du registre

Après chaque expérience, ajouter ou mettre à jour une ligne avec :

```text
ID / nom
hypothèse falsifiable
population exacte
target et horizon
protocole OOF/PIT
artefact canonique
métriques principales
gates passés/échoués
verdict séparé LONG, SHORT et AMPLITUDE si applicable
lien vers le document détaillé
prochaine action autorisée
```

Ne jamais remplacer un `NO_GO` par une nouvelle interprétation sans nouvelle
information, nouveau contrat pré-enregistré et nouvelle validation. Conserver
les résultats négatifs : ils empêchent de répéter les mêmes recherches sous un
autre nom.
